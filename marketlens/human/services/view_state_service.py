from __future__ import annotations

from marketlens.human.orchestration import ParticipantStage
from marketlens.human.schemas import (
    ParticipantAllowedActions,
    ParticipantAssessmentMode,
    ParticipantMarketView,
    ParticipantRequiredAction,
    ParticipantViewState,
)
from marketlens.human.services.orchestration_service import ExperimentOrchestrationService
from marketlens.human.services.trusted_context_service import (
    TrustedParticipantContextInvariantError,
    TrustedParticipantContextResolver,
)
from marketlens.market.status import TradingCalendar, TradingCalendarError


VIEW_CONTRACT_VERSION = "1.0"


class ParticipantViewStateUnavailableError(ValueError):
    pass


class ParticipantViewStateInvariantError(ValueError):
    pass


_JUDGEMENT_MODES = {
    ParticipantStage.J0_REQUIRED: ParticipantAssessmentMode.PRE_UPDATE,
    ParticipantStage.J1_REQUIRED: ParticipantAssessmentMode.POST_UPDATE,
    ParticipantStage.J2_REQUIRED: ParticipantAssessmentMode.PRE_UPDATE,
    ParticipantStage.J3_REQUIRED: ParticipantAssessmentMode.POST_UPDATE,
    ParticipantStage.J4_REQUIRED: ParticipantAssessmentMode.LATER,
}

_JUDGEMENT_EVENT_MODES = {
    "J0": ParticipantAssessmentMode.PRE_UPDATE,
    "J1": ParticipantAssessmentMode.POST_UPDATE,
    "J2": ParticipantAssessmentMode.PRE_UPDATE,
    "J3": ParticipantAssessmentMode.POST_UPDATE,
    "J4": ParticipantAssessmentMode.LATER,
}


def assessment_mode_for_judgement_event(event: str) -> ParticipantAssessmentMode:
    try:
        return _JUDGEMENT_EVENT_MODES[event]
    except KeyError as exc:
        raise ParticipantViewStateInvariantError(
            f"unknown formal judgement event: {event!r}"
        ) from exc


def _required_action(stage: ParticipantStage) -> ParticipantRequiredAction:
    if stage is ParticipantStage.BACKGROUND_REQUIRED:
        return ParticipantRequiredAction.LOAD_MARKET_INFORMATION
    if stage in _JUDGEMENT_MODES:
        return ParticipantRequiredAction.SUBMIT_ASSESSMENT
    if stage in {
        ParticipantStage.MISINFORMATION_DELIVERY_REQUIRED,
        ParticipantStage.CORRECTION_DELIVERY_REQUIRED,
    }:
        return ParticipantRequiredAction.LOAD_INFORMATION_UPDATE
    if stage is ParticipantStage.ROUND_ACTIVE:
        return ParticipantRequiredAction.ROUND_ACTIVE
    if stage is ParticipantStage.FEEDBACK_REQUIRED:
        return ParticipantRequiredAction.VIEW_FEEDBACK
    if stage is ParticipantStage.DEBRIEF_REQUIRED:
        return ParticipantRequiredAction.VIEW_DEBRIEF
    if stage is ParticipantStage.COMPLETED:
        return ParticipantRequiredAction.COMPLETED
    raise ParticipantViewStateInvariantError(
        f"unsupported participant orchestration stage: {stage.value}"
    )


class ParticipantViewStateService:
    """Read-only participant presentation adapter over frozen server-owned state.

    Raw Phase 14 orchestration stage names and J0..J4 identities are deliberately
    not returned to the frontend. The adapter exposes only neutral presentation
    actions derived from authoritative backend state.
    """

    def __init__(
        self,
        *,
        orchestration: ExperimentOrchestrationService,
        context: TrustedParticipantContextResolver,
        calendar: TradingCalendar,
        target_stock_id: str,
    ):
        self.orchestration = orchestration
        self.context = context
        self.calendar = calendar
        self.target_stock_id = target_stock_id
        self._checkpoint_count = len(
            [
                row
                for row in self.orchestration.contract.protocol["timeline"]
                if row.get("experiment_step") is not None
            ]
        )

    def get(self, session_id: str) -> ParticipantViewState:
        state = self.orchestration.get(session_id)
        trusted = self.context.resolve(session_id)

        if state.participant_id != trusted.participant_id:
            raise ParticipantViewStateInvariantError(
                "orchestration participant disagrees with trusted participant context"
            )
        if state.experiment_step != trusted.experiment_step:
            raise ParticipantViewStateInvariantError(
                "orchestration step disagrees with trusted participant context"
            )
        if state.agent_world_date != trusted.agent_world_date:
            raise ParticipantViewStateInvariantError(
                "orchestration date disagrees with trusted participant context"
            )
        if state.current_stage is None:
            raise ParticipantViewStateUnavailableError(
                "participant experiment orchestration is not initialized"
            )

        try:
            stage = ParticipantStage(state.current_stage)
        except ValueError as exc:
            raise ParticipantViewStateInvariantError(
                "participant orchestration contains an unknown stage"
            ) from exc

        if state.completed != (stage is ParticipantStage.COMPLETED):
            raise ParticipantViewStateInvariantError(
                "participant completion flag disagrees with server-owned stage"
            )
        if state.experiment_step < 0 or state.experiment_step >= self._checkpoint_count:
            raise ParticipantViewStateInvariantError(
                "participant step is outside the frozen checkpoint range"
            )

        try:
            market = self.calendar.status(trusted.agent_world_date)
        except TradingCalendarError as exc:
            raise ParticipantViewStateUnavailableError(str(exc)) from exc

        if bool(market.market_open) != trusted.market_open:
            raise TrustedParticipantContextInvariantError(
                "view-state market status disagrees with trusted participant context"
            )
        if bool(market.participant_trading_enabled) != trusted.participant_trading_enabled:
            raise TrustedParticipantContextInvariantError(
                "view-state trading gate disagrees with trusted participant context"
            )

        required_action = _required_action(stage)
        assessment_mode = _JUDGEMENT_MODES.get(stage)
        round_active = stage is ParticipantStage.ROUND_ACTIVE and not state.completed
        can_trade = round_active and trusted.participant_trading_enabled
        interstitial = (
            stage
            in {
                ParticipantStage.FEEDBACK_REQUIRED,
                ParticipantStage.DEBRIEF_REQUIRED,
            }
            and not state.completed
        )

        return ParticipantViewState(
            contract_version=VIEW_CONTRACT_VERSION,
            session_id=state.session_id,
            current_step_assertion=state.experiment_step,
            period_number=state.experiment_step + 1,
            period_count=self._checkpoint_count,
            current_date=trusted.agent_world_date,
            experiment_status=state.experiment_status,
            completed=state.completed,
            assessment_target_stock_id=self.target_stock_id,
            required_action=required_action,
            assessment_mode=assessment_mode,
            market=ParticipantMarketView(
                market_open=bool(market.market_open),
                market_status_reason=str(market.market_status_reason),
                current_market_date=(
                    None if market.current_market_date is None else str(market.current_market_date)
                ),
                next_trading_date=(
                    None if market.next_trading_date is None else str(market.next_trading_date)
                ),
                closure_start_date=(
                    None if market.closure_start_date is None else str(market.closure_start_date)
                ),
                closure_end_date=(
                    None if market.closure_end_date is None else str(market.closure_end_date)
                ),
                market_state_date=(
                    None if market.market_state_date is None else str(market.market_state_date)
                ),
                trading_enabled_by_market=bool(market.participant_trading_enabled),
            ),
            allowed_actions=ParticipantAllowedActions(
                load_market_information=(
                    stage is ParticipantStage.BACKGROUND_REQUIRED and not state.completed
                ),
                load_information_update=(
                    stage
                    in {
                        ParticipantStage.MISINFORMATION_DELIVERY_REQUIRED,
                        ParticipantStage.CORRECTION_DELIVERY_REQUIRED,
                    }
                    and not state.completed
                ),
                submit_assessment=(stage in _JUDGEMENT_MODES and not state.completed),
                view_portfolio=not interstitial,
                preview_trade=can_trade,
                submit_trade=can_trade,
                complete_round=round_active,
            ),
        )

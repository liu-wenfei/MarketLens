from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from marketlens.episode.contract import (
    EPISODE_IDS as DEFAULT_EPISODE_IDS,
    EPISODE_POOL_ID as DEFAULT_EPISODE_POOL_ID,
)
from marketlens.experiment.protocol import load_protocol, validate_protocol
from marketlens.human.services.episode_assignment_service import EpisodeAssignmentService
from marketlens.human.services.session_service import SessionService
from marketlens.market.status import TradingCalendar, TradingCalendarError


class TrustedParticipantContextUnavailableError(ValueError):
    """Raised when a participant session has not reached a resolvable checkpoint."""


class TrustedParticipantContextInvariantError(ValueError):
    """Raised when authoritative backend sources disagree about experiment state."""


@dataclass(frozen=True)
class TrustedParticipantContext:
    session_id: str
    participant_id: str
    assignment_id: str
    episode_pool_id: str
    episode_id: str
    assignment_method: str
    assignment_version: str
    protocol_version: str
    experiment_step: int
    agent_world_date: str
    market_open: bool
    market_status_reason: str
    current_market_date: str
    market_state_date: str | None
    participant_trading_enabled: bool


class TrustedParticipantContextResolver:
    """Resolve participant provenance only from authoritative backend state.

    The resolver deliberately accepts only ``session_id`` from its caller. It does
    not accept participant_id, episode_id, experiment_step, agent_world_date or
    market status as client assertions. Those values are derived from existing
    MarketLens domain stores, the frozen protocol and the authoritative trading
    calendar.

    This service is read-only. It does not write participant events, mutate the
    participant session/portfolio, perform episode allocation, or touch the Agent
    world.
    """

    def __init__(
        self,
        *,
        sessions: SessionService,
        assignments: EpisodeAssignmentService,
        calendar: TradingCalendar,
        episode_pool_id: str = DEFAULT_EPISODE_POOL_ID,
        episode_ids: Sequence[str] = DEFAULT_EPISODE_IDS,
        protocol: Mapping[str, Any] | None = None,
    ):
        resolved_episode_ids = tuple(str(value) for value in episode_ids)

        if not str(episode_pool_id).strip():
            raise TrustedParticipantContextInvariantError(
                "runtime episode_pool_id must be non-empty"
            )
        if not resolved_episode_ids:
            raise TrustedParticipantContextInvariantError(
                "runtime episode_ids must be non-empty"
            )
        if len(set(resolved_episode_ids)) != len(resolved_episode_ids):
            raise TrustedParticipantContextInvariantError(
                "runtime episode_ids must be unique"
            )

        self.sessions = sessions
        self.assignments = assignments
        self.calendar = calendar
        self.episode_pool_id = str(episode_pool_id)
        self.episode_ids = resolved_episode_ids
        self.protocol = validate_protocol(protocol) if protocol is not None else load_protocol()
        self._checkpoint_by_step = {
            int(row["experiment_step"]): row
            for row in self.protocol["timeline"]
            if row.get("experiment_step") is not None
        }

    def resolve(self, session_id: str) -> TrustedParticipantContext:
        session = self.sessions.get(session_id)
        assignment = self.assignments.get(session_id)
        if assignment is None:
            raise TrustedParticipantContextUnavailableError(
                "participant session has no canonical episode assignment"
            )

        if assignment.session_id != session.session_id:
            raise TrustedParticipantContextInvariantError(
                "episode assignment session_id disagrees with the authoritative session"
            )
        if assignment.participant_id != session.participant_id:
            raise TrustedParticipantContextInvariantError(
                "episode assignment participant_id disagrees with the authoritative session"
            )
        if assignment.episode_pool_id != self.episode_pool_id:
            raise TrustedParticipantContextInvariantError(
                "episode assignment pool identity drifted from the frozen canonical pool"
            )
        if assignment.episode_id not in self.episode_ids:
            raise TrustedParticipantContextInvariantError(
                "episode assignment identity is not in the frozen canonical episode pool"
            )

        if session.current_date is None:
            raise TrustedParticipantContextUnavailableError(
                "participant session has no authoritative agent_world_date"
            )

        try:
            checkpoint = self._checkpoint_by_step[int(session.current_step)]
        except KeyError as exc:
            raise TrustedParticipantContextUnavailableError(
                f"session current_step {session.current_step} is not a participant checkpoint in the frozen protocol"
            ) from exc

        protocol_date = str(checkpoint["agent_world_date"])
        if protocol_date != session.current_date:
            raise TrustedParticipantContextInvariantError(
                "session current_date disagrees with the frozen protocol checkpoint date"
            )

        try:
            market = self.calendar.status(session.current_date)
        except TradingCalendarError as exc:
            raise TrustedParticipantContextUnavailableError(str(exc)) from exc

        protocol_open = checkpoint.get("market_status") == "OPEN"
        if bool(market.market_open) != protocol_open:
            raise TrustedParticipantContextInvariantError(
                "authoritative trading calendar disagrees with frozen protocol market status"
            )

        return TrustedParticipantContext(
            session_id=session.session_id,
            participant_id=session.participant_id,
            assignment_id=assignment.assignment_id,
            episode_pool_id=assignment.episode_pool_id,
            episode_id=assignment.episode_id,
            assignment_method=assignment.assignment_method,
            assignment_version=assignment.assignment_version,
            protocol_version=str(self.protocol["protocol_version"]),
            experiment_step=int(session.current_step),
            agent_world_date=session.current_date,
            market_open=bool(market.market_open),
            market_status_reason=str(market.market_status_reason),
            current_market_date=str(market.current_market_date),
            market_state_date=(
                None if market.market_state_date is None else str(market.market_state_date)
            ),
            participant_trading_enabled=bool(market.participant_trading_enabled),
        )

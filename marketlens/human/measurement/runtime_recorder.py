from __future__ import annotations

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from marketlens.human.measurement.event_store import ParticipantEventStore
from marketlens.human.measurement.models import ParticipantEvent, ParticipantEventType
from marketlens.human.schemas import DecisionRead, PortfolioTransactionRead
from marketlens.human.services.trusted_context_service import (
    TrustedParticipantContext,
    TrustedParticipantContextResolver,
)


class ParticipantRuntimeEventInvariantError(ValueError):
    """Raised when a completed domain record disagrees with trusted experiment context."""


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ParticipantRuntimeEventInvariantError(
            "authoritative domain timestamp must be timezone-aware"
        )
    return value.astimezone(timezone.utc).isoformat()


def _event_id(session_id: str, request_id: str, event_type: ParticipantEventType) -> str:
    """Deterministic replay identity for a domain event.

    Phase 14A idempotency compares event_id and occurred_at_utc as part of the
    stored payload. Domain records already provide a stable request_id and
    authoritative timestamp, so a UUID5 makes retries reproduce the exact same
    event envelope without weakening the append-only ledger contract.
    """

    identity = f"marketlens:participant-event:{session_id}:{request_id}:{event_type.value}"
    return str(uuid5(NAMESPACE_URL, identity))


class ParticipantRuntimeEventRecorder:
    """Record provenance for already-successful participant domain writes.

    This component never submits a judgement, settles an order, mutates a
    portfolio, advances a session, allocates an episode, or writes Agent-world
    state. Callers must first complete the authoritative domain operation and
    then pass the resulting read model here.

    Exposure delivery (background/stimulus) is deliberately out of scope for
    Phase 14B3A because those events require a participant-visible delivery
    boundary rather than a domain-record completion boundary.
    """

    def __init__(
        self,
        *,
        store: ParticipantEventStore,
        context: TrustedParticipantContextResolver,
    ):
        self.store = store
        self.context = context

    @staticmethod
    def _validate_domain_context(
        trusted: TrustedParticipantContext,
        *,
        session_id: str,
        experiment_step: int,
    ) -> None:
        if trusted.session_id != session_id:
            raise ParticipantRuntimeEventInvariantError(
                "domain record session_id disagrees with trusted participant context"
            )
        if trusted.experiment_step != int(experiment_step):
            raise ParticipantRuntimeEventInvariantError(
                "domain record experiment step disagrees with trusted participant context"
            )

    def _append_domain_event(
        self,
        *,
        trusted: TrustedParticipantContext,
        request_id: str,
        event_type: ParticipantEventType,
        domain_record_id: str,
        occurred_at: datetime,
    ):
        event = ParticipantEvent(
            event_id=_event_id(trusted.session_id, request_id, event_type),
            request_id=request_id,
            session_id=trusted.session_id,
            participant_id=trusted.participant_id,
            episode_id=trusted.episode_id,
            experiment_step=trusted.experiment_step,
            agent_world_date=trusted.agent_world_date,
            event_type=event_type,
            domain_record_id=domain_record_id,
            market_open=trusted.market_open,
            participant_trading_enabled=trusted.participant_trading_enabled,
            occurred_at_utc=_utc_iso(occurred_at),
        )
        return self.store.append_idempotent(event)

    def record_decision(self, decision: DecisionRead) -> tuple[object, object]:
        """Reference one authoritative decision from judgement + confidence events."""

        trusted = self.context.resolve(decision.session_id)
        self._validate_domain_context(
            trusted,
            session_id=decision.session_id,
            experiment_step=decision.step,
        )
        judgement = self._append_domain_event(
            trusted=trusted,
            request_id=decision.request_id,
            event_type=ParticipantEventType.JUDGEMENT_SUBMITTED,
            domain_record_id=decision.decision_id,
            occurred_at=decision.submitted_at,
        )
        confidence = self._append_domain_event(
            trusted=trusted,
            request_id=decision.request_id,
            event_type=ParticipantEventType.CONFIDENCE_RECORDED,
            domain_record_id=decision.decision_id,
            occurred_at=decision.submitted_at,
        )
        return judgement, confidence

    def record_transaction(
        self,
        transaction: PortfolioTransactionRead,
    ) -> tuple[object, object, object]:
        """Reference one settled transaction from order/trade/post-state events.

        The current participant portfolio domain commits order acceptance,
        settlement, and resulting portfolio state atomically in one transaction
        record. Therefore all three provenance events reference the same
        authoritative transaction_id rather than inventing duplicate domain
        records in the event ledger.
        """

        trusted = self.context.resolve(transaction.session_id)
        self._validate_domain_context(
            trusted,
            session_id=transaction.session_id,
            experiment_step=transaction.step,
        )
        event_types = (
            ParticipantEventType.ORDER_SUBMITTED,
            ParticipantEventType.TRADE_SETTLED,
            ParticipantEventType.PORTFOLIO_STATE_RECORDED,
        )
        rows = tuple(
            self._append_domain_event(
                trusted=trusted,
                request_id=transaction.request_id,
                event_type=event_type,
                domain_record_id=transaction.transaction_id,
                occurred_at=transaction.submitted_at,
            )
            for event_type in event_types
        )
        return rows  # type: ignore[return-value]

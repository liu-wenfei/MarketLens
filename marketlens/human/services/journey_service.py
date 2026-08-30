from __future__ import annotations

from typing import Mapping

from marketlens.human.feedback.journey import ParticipantDecisionJourney
from marketlens.human.feedback.journey_source import (
    JourneyAuthoritativeSourceAdapter,
)
from marketlens.human.services.episode_assignment_service import (
    EpisodeAssignmentService,
)
from marketlens.human.services.session_service import (
    SessionNotFoundError,
    SessionService,
)


class ParticipantJourneyUnavailableError(ValueError):
    pass


class ParticipantJourneyConfigurationError(ValueError):
    pass


class ParticipantJourneyService:
    """Build a read-only decision journey from authoritative participant data.

    The service resolves the participant's canonical episode from the persisted
    session assignment and uses only that episode's explicitly bound canonical
    close-price provider.

    It performs no writes, creates no second source of truth, and never falls
    back to CSV or another episode.
    """

    def __init__(
        self,
        *,
        sessions: SessionService,
        assignments: EpisodeAssignmentService,
        judgements: object,
        portfolios: object,
        rounds: object,
        price_providers: Mapping[str, object],
        calendar: object,
        contract: object,
        target_stock_id: str,
    ) -> None:
        self.sessions = sessions
        self.assignments = assignments
        self.judgements = judgements
        self.portfolios = portfolios
        self.rounds = rounds
        self.price_providers = dict(price_providers)
        self.calendar = calendar
        self.contract = contract
        self.target_stock_id = target_stock_id

        if not self.price_providers:
            raise ParticipantJourneyConfigurationError(
                "participant Journey requires explicitly bound canonical "
                "episode price providers"
            )

    def get(self, session_id: str) -> ParticipantDecisionJourney:
        # Resolve the session first so an unknown session preserves the existing
        # participant API's SessionNotFoundError semantics.
        self.sessions.get(session_id)

        assignment = self.assignments.get(session_id)
        if assignment is None:
            raise ParticipantJourneyUnavailableError(
                "participant session has no canonical episode assignment"
            )

        price_provider = self.price_providers.get(
            assignment.episode_id
        )
        if price_provider is None:
            raise ParticipantJourneyConfigurationError(
                "no canonical close-price provider is bound for "
                f"episode {assignment.episode_id!r}"
            )

        adapter = JourneyAuthoritativeSourceAdapter(
            judgements=self.judgements,
            portfolios=self.portfolios,
            rounds=self.rounds,
            price_provider=price_provider,
            calendar=self.calendar,
            contract=self.contract,
            target_stock_id=self.target_stock_id,
        )

        return adapter.build(session_id)

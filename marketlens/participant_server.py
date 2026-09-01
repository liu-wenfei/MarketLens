"""Formal MarketLens participant-server composition.

This module composes the already-frozen participant-facing runtime:

- canonical episode pool v2
- frozen participant text pack v2
- formal controlled stimulus
- episode-keyed participant background projections
- canonical journey price providers
- participant event provenance store
- independent FastAPI HTTP backend with explicit frontend CORS

It does not execute the Agent world or perform live translation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Mapping, Sequence

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from marketlens.episode.contract_v2 import (
    EPISODE_IDS,
    EPISODE_POOL_ID,
    FORMAL_POOL_MANIFEST,
    file_sha256,
    formal_episode_paths,
    validate_formal_episode_pool_manifest,
)
from marketlens.human.formal_feedback_generator import (
    FORMAL_GENERATION_STATUS,
    FORMAL_GENERATOR_ID,
    is_formal_feedback_generator,
)
from marketlens.human.feedback import (
    ContextLimits,
    FrozenFeedbackPrompt,
)
from marketlens.human.measurement.event_store import ParticipantEventStore
from marketlens.human.services.feedback_preparation_service import (
    ParticipantFeedbackPreparationService,
)
from marketlens.information.projection import (
    CanonicalEpisodeBinding,
    ParticipantBackgroundProjection,
)
from marketlens.information.text_pack import FrozenTextPack
from marketlens.main import create_app
from marketlens.stimulus.engine import StimulusEngine
from marketlens.stimulus.material import load_material


DEFAULT_FRONTEND_ORIGINS = ("http://localhost:5173",)

FORMAL_TEXT_PACK = (
    "data/marketlens/information/"
    "participant_text_pack_v2.formal.json"
)

FORMAL_STIMULUS = (
    "data/marketlens/stimuli/"
    "stimulus_v1.formal.json"
)

DEFAULT_PARTICIPANT_EVENT_DB = (
    "data/marketlens/human/"
    "participant_events.db"
)


class FormalParticipantServerConfigurationError(ValueError):
    pass


NONFORMAL_SMOKE_CONTEXT_LIMITS = ContextLimits(
    policy_version=(
        "marketlens-nonformal-smoke-context-v1"
    ),
    max_news_items=50,
    max_community_posts=50,
    max_news_chars=1000,
    max_community_chars=1000,
    max_rationale_chars=2000,
    max_evidence_sources=12,
    max_evidence_source_chars=300,
    max_controlled_headline_chars=500,
    max_controlled_body_chars=5000,
    max_source_label_chars=200,
    max_source_descriptor_chars=500,
)


_NONFORMAL_MID_REFLECTION = (
    "Across the recent market periods, your recorded assessments, "
    "reported confidence, and trading choices provide several points "
    "for reflection. Changes in a stated view do not always need to "
    "be accompanied by an immediate portfolio change, and periods "
    "without a trade can sit alongside changes in confidence or "
    "assessment. The information available during these periods "
    "included market updates and community discussion, while your "
    "own recorded rationale and evidence selections remain the "
    "clearest source for any information you explicitly considered. "
    "As you continue, consider how closely your reported confidence "
    "matched the strength of your actions, and whether the reasons "
    "you recorded for changing or maintaining your view were also "
    "reflected in your trading or no-trading choices across the "
    "period."
)


_NONFORMAL_FINAL_REFLECTION = (
    "Across the session, your recorded assessments form a sequence "
    "that can be viewed as a developing decision journey rather than "
    "as isolated choices. Some parts of the record may show "
    "continuity in your stated view, while other parts may show "
    "revision as the participant-visible information environment "
    "changed. The useful point for reflection is the pattern of "
    "stability and change across the whole sequence, together with "
    "the reasons and evidence you explicitly recorded at the time. "
    "Reading the assessments together can help you notice how your "
    "stated market view developed across different parts of the "
    "session without treating any single response as the whole "
    "story. "
    "\n\n"
    "Your reported confidence and your trading or no-trading "
    "behaviour provide another perspective on that journey. A "
    "change in assessment may or may not have been accompanied by "
    "an immediate portfolio action, and confidence can move "
    "differently from the direction of a stated view. Looking "
    "across the session, these records make it possible to compare "
    "what you said about the market with how strongly you chose to "
    "act, while keeping judgement and trading as distinct measures. "
    "Portfolio changes are included only as descriptive records of "
    "participant behaviour, alongside periods in which you chose "
    "not to trade. "
    "\n\n"
    "The information available to you across the session included "
    "changing market information and community discussion, "
    "alongside additional study material shown through "
    "the study interface. Availability alone does not show which "
    "items you read, considered, or used, so this reflection relies "
    "on your own rationale and evidence selections when referring "
    "to information you explicitly considered. Taken together, the "
    "session record offers a basis for reflecting on where your "
    "views remained stable, where they changed, where uncertainty "
    "appeared in confidence or action, and how your stated "
    "reasoning related to the choices you recorded over time."
)


def nonformal_smoke_feedback_generator(
    prompt: FrozenFeedbackPrompt,
) -> Mapping[str, object]:
    if (
        prompt.feedback_kind
        == "multi_period_decision_feedback"
    ):
        reflection = _NONFORMAL_MID_REFLECTION
    elif (
        prompt.feedback_kind
        == "final_session_summary"
    ):
        reflection = _NONFORMAL_FINAL_REFLECTION
    else:
        raise FormalParticipantServerConfigurationError(
            "unsupported feedback kind for NON-FORMAL "
            "deterministic smoke generation"
        )

    return {
        "feedback_kind": prompt.feedback_kind,
        "reflection": reflection,
    }


def _load_formal_text_pack(
    repo_root: Path,
) -> FrozenTextPack:
    path = repo_root / FORMAL_TEXT_PACK

    if not path.is_file():
        raise FormalParticipantServerConfigurationError(
            f"formal participant text pack not found: {path}"
        )

    try:
        payload = json.loads(
            path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise FormalParticipantServerConfigurationError(
            "cannot load formal participant text pack"
        ) from exc

    try:
        pack = FrozenTextPack(
            pack_id=payload["pack_id"],
            version=payload["version"],
            status=payload["status"],
            translations=payload["translations"],
            expected_manifest_sha256=(
                payload["expected_manifest_sha256"]
            ),
        )
        pack.validate(formal=True)
    except Exception as exc:
        raise FormalParticipantServerConfigurationError(
            "formal participant text pack failed validation"
        ) from exc

    return pack


def _load_formal_v2_pool(
    repo_root: Path,
) -> dict:
    path = repo_root / FORMAL_POOL_MANIFEST

    if not path.is_file():
        raise FormalParticipantServerConfigurationError(
            f"formal v2 pool manifest not found: {path}"
        )

    try:
        payload = json.loads(
            path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise FormalParticipantServerConfigurationError(
            "cannot load formal v2 pool manifest"
        ) from exc

    try:
        validate_formal_episode_pool_manifest(
            payload,
            repo_root=repo_root,
            verify_files=True,
        )
    except Exception as exc:
        raise FormalParticipantServerConfigurationError(
            "formal v2 canonical episode pool failed validation"
        ) from exc

    return payload


def _build_formal_background_projections(
    repo_root: Path,
    text_pack: FrozenTextPack,
) -> dict[str, ParticipantBackgroundProjection]:
    projections: dict[
        str,
        ParticipantBackgroundProjection,
    ] = {}

    for episode_id in EPISODE_IDS:
        paths = formal_episode_paths(episode_id)

        agent_world_db = (
            repo_root / paths["agent_world_db"]
        )
        forum_db = repo_root / paths["forum_db"]

        if not agent_world_db.is_file():
            raise FormalParticipantServerConfigurationError(
                f"formal Agent-world DB missing: "
                f"{agent_world_db}"
            )

        if not forum_db.is_file():
            raise FormalParticipantServerConfigurationError(
                f"formal forum DB missing: {forum_db}"
            )

        binding = CanonicalEpisodeBinding(
            episode_id=episode_id,
            user_db_path=agent_world_db,
            forum_db_path=forum_db,
            status="formal_frozen",
            user_db_sha256=file_sha256(
                agent_world_db
            ),
            forum_db_sha256=file_sha256(
                forum_db
            ),
        )

        binding.validate(formal=True)

        projections[episode_id] = (
            ParticipantBackgroundProjection(
                episode=binding,
                text_pack=text_pack,
                formal=True,
            )
        )

    if set(projections) != set(EPISODE_IDS):
        raise FormalParticipantServerConfigurationError(
            "formal participant projections do not "
            "cover the complete v2 episode pool"
        )

    return projections


def create_formal_participant_app(
    *,
    repo_root: str | Path | None = None,
    db_path: str | Path | None = None,
    participant_event_db_path: str | Path | None = None,
    allowed_origins: Sequence[str] = (
        DEFAULT_FRONTEND_ORIGINS
    ),
    feedback_generator: (
        Callable[
            [FrozenFeedbackPrompt],
            object,
        ]
        | None
    ) = None,
    feedback_context_limits: ContextLimits | None = None,
    feedback_generator_id: str | None = None,
    feedback_generation_status: str | None = None,
    feedback_generation_metadata: (
        Mapping[str, object] | None
    ) = None,
    _allow_nonformal_feedback: bool = False,
) -> FastAPI:
    root = (
        Path(repo_root).resolve()
        if repo_root is not None
        else Path(__file__).resolve().parents[1]
    )

    if (
        feedback_generator is not None
        and not _allow_nonformal_feedback
    ):
        if not is_formal_feedback_generator(
            feedback_generator
        ):
            raise FormalParticipantServerConfigurationError(
                "formal participant feedback requires the "
                "frozen formal feedback generator"
            )

        if feedback_generator_id not in (
            None,
            FORMAL_GENERATOR_ID,
        ):
            raise FormalParticipantServerConfigurationError(
                "formal feedback generator_id conflicts "
                "with the frozen generator identity"
            )
        if feedback_generation_status not in (
            None,
            FORMAL_GENERATION_STATUS,
        ):
            raise FormalParticipantServerConfigurationError(
                "formal feedback generation_status conflicts "
                "with the frozen generator identity"
            )
        if feedback_generation_metadata:
            raise FormalParticipantServerConfigurationError(
                "formal feedback generation metadata is derived "
                "from the frozen generator configuration"
            )

        feedback_generator_id = FORMAL_GENERATOR_ID
        feedback_generation_status = (
            FORMAL_GENERATION_STATUS
        )
        feedback_generation_metadata = (
            feedback_generator.config.static_metadata()
        )

    _load_formal_v2_pool(root)

    text_pack = _load_formal_text_pack(root)

    projections = (
        _build_formal_background_projections(
            root,
            text_pack,
        )
    )

    stimulus_path = root / FORMAL_STIMULUS
    if not stimulus_path.is_file():
        raise FormalParticipantServerConfigurationError(
            f"formal stimulus missing: "
            f"{stimulus_path}"
        )

    stimulus_engine = StimulusEngine(
        load_material(
            stimulus_path,
            formal=True,
        )
    )

    event_path = (
        Path(participant_event_db_path)
        if participant_event_db_path is not None
        else root / DEFAULT_PARTICIPANT_EVENT_DB
    )

    events = ParticipantEventStore(event_path)

    app = create_app(
        db_path=db_path,
        participant_runtime_enabled=True,
        participant_event_store=events,
        background_projections=projections,
        stimulus_engine=stimulus_engine,
        participant_episode_pool_id=EPISODE_POOL_ID,
        participant_episode_ids=EPISODE_IDS,
    )

    feedback_enabled = feedback_generator is not None

    if feedback_enabled:
        if feedback_context_limits is None:
            raise FormalParticipantServerConfigurationError(
                "feedback generator requires explicit "
                "ContextLimits"
            )
        if not feedback_generator_id:
            raise FormalParticipantServerConfigurationError(
                "feedback generator requires generator_id"
            )
        if not feedback_generation_status:
            raise FormalParticipantServerConfigurationError(
                "feedback generator requires generation_status"
            )

        runtime = app.state.participant_runtime
        if runtime is None:
            raise FormalParticipantServerConfigurationError(
                "participant runtime was not composed"
            )

        preparation = ParticipantFeedbackPreparationService(
            assignments=runtime.assignments,
            projections=projections,
            judgements=runtime.journey.judgements,
            portfolios=runtime.journey.portfolios,
            rounds=runtime.journey.rounds,
            events=events,
            price_providers=(
                runtime.journey.price_providers
            ),
            calendar=runtime.journey.calendar,
            contract=runtime.orchestration.contract,
            stimulus_engine=stimulus_engine,
            target_stock_id=runtime.target_stock_id,
            limits=feedback_context_limits,
            delivery=runtime.feedback,
            generator=feedback_generator,
            generator_id=feedback_generator_id,
            generation_status=(
                feedback_generation_status
            ),
            generation_metadata=(
                feedback_generation_metadata
                or {}
            ),
        )

        runtime.rounds.bind_feedback_preparer(
            preparation.prepare
        )
        app.state.feedback_preparation_service = (
            preparation
        )
    else:
        if any(
            value is not None
            for value in (
                feedback_context_limits,
                feedback_generator_id,
                feedback_generation_status,
                feedback_generation_metadata,
            )
        ):
            raise FormalParticipantServerConfigurationError(
                "feedback preparation options require an "
                "explicit feedback generator"
            )

        app.state.feedback_preparation_service = None

    app.state.formal_participant_event_store = events
    app.state.formal_participant_text_pack = text_pack
    app.state.formal_participant_episode_pool_id = (
        EPISODE_POOL_ID
    )
    app.state.formal_participant_episode_ids = (
        tuple(EPISODE_IDS)
    )

    resolved_origins = tuple(
        str(origin).rstrip("/")
        for origin in allowed_origins
        if str(origin).strip()
    )

    if not resolved_origins:
        raise FormalParticipantServerConfigurationError(
            "at least one frontend origin is required"
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


def create_nonformal_smoke_participant_app(
    *,
    repo_root: str | Path | None = None,
    db_path: str | Path | None = None,
    participant_event_db_path: (
        str | Path | None
    ) = None,
    allowed_origins: Sequence[str] = (
        DEFAULT_FRONTEND_ORIGINS
    ),
) -> FastAPI:
    """Compose formal frozen inputs with ZERO-LLM smoke feedback.

    NON-FORMAL / DEVELOPMENT ONLY / NOT FOR DATA COLLECTION.
    """

    return create_formal_participant_app(
        repo_root=repo_root,
        db_path=db_path,
        participant_event_db_path=(
            participant_event_db_path
        ),
        allowed_origins=allowed_origins,
        feedback_generator=(
            nonformal_smoke_feedback_generator
        ),
        feedback_context_limits=(
            NONFORMAL_SMOKE_CONTEXT_LIMITS
        ),
        feedback_generator_id=(
            "marketlens-nonformal-"
            "deterministic-smoke-v1"
        ),
        feedback_generation_status=(
            "nonformal_smoke_validated"
        ),
        _allow_nonformal_feedback=True,
        feedback_generation_metadata={
            "mode": (
                "NON-FORMAL / DETERMINISTIC "
                "FEEDBACK SMOKE"
            ),
            "llm_calls": 0,
            "external_api_calls": 0,
            "formal_evidence": False,
        },
    )


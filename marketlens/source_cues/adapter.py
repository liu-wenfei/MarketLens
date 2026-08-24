"""Thin participant-facing source-cue adapter for Phase 12.

Design rules:
- Agent source status comes from inherited TwinMarket ``Profiles.user_type`` via
  ``util.UserDB.get_user_profile``. Phase 12 does not create a second identity DB.
- Controlled-stimulus timing and text come only from Phase 11 participant payloads.
  Phase 12 decorates an already-visible item; it never decides visibility.
- Dynamic graph prominence / ``is_top_user`` is deliberately absent. Influence is
  not treated as credibility.
- The adapter is read-only with respect to TwinMarket state.
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Mapping, Any


class SourceCueError(ValueError):
    """Raised when source identity cannot be resolved without guessing."""


CUE_VERSION = "1.0"
CUE_STATUS = "formal_frozen"
SOURCE_CUE_MANIFEST_SHA256 = "67e567351eb77a1edf186239f6205dc43840fbf6e59076813f702fef55b7d5ef"

# Direct display mapping of the inherited TwinMarket Profiles.user_type values.
# These are source-status labels only; none encodes truth, expertise or reliability.
_USER_TYPE_LABELS = MappingProxyType(
    {
        "普通股民": "Individual Investor",
        "小博主": "Market Blogger",
        "大V": "Influential Market Commentator",
    }
)

# Candidate presentation metadata for the two already-frozen Phase 11 stimuli.
# Phase 12 does not store dates or text and cannot release an item on its own.
_CONTROLLED_STIMULUS_CUES = MappingProxyType(
    {
        "MISINFO_MEI_OWNERSHIP_001": MappingProxyType(
            {
                "source_label": "Market News Report",
                "source_descriptor": "Market media report",
            }
        ),
        "CORRECTION_MEI_OWNERSHIP_001": MappingProxyType(
            {
                "source_label": "LONGi Green Energy",
                "source_descriptor": "Official company announcement",
            }
        ),
    }
)

_PHASE11_PARTICIPANT_KEYS = frozenset(
    {"stimulus_id", "kind", "headline", "body", "corrects_stimulus_id"}
)
_PHASE12_ADDED_KEYS = frozenset({"source_label", "source_descriptor"})


def source_label_for_user_type(user_type: str) -> str:
    """Map an inherited TwinMarket user_type to a neutral English display label."""
    try:
        return _USER_TYPE_LABELS[user_type]
    except KeyError as exc:
        raise SourceCueError(
            f"unsupported inherited TwinMarket user_type {user_type!r}; fail closed rather than inventing a source status"
        ) from exc


def resolve_agent_source_cue(
    user_id: str,
    *,
    db_path: str,
    created_at: str,
) -> dict[str, str]:
    """Resolve an Agent source cue by directly calling inherited TwinMarket UserDB.

    ``created_at`` is required because inherited ``get_user_profile`` addresses an
    exact Profiles snapshot. No graph/top-user information is consulted.
    """
    if not isinstance(created_at, str) or not created_at.strip():
        raise SourceCueError("created_at is required for exact inherited Profiles lookup")

    # Local import keeps the adapter thin while explicitly reusing inherited code.
    from util.UserDB import get_user_profile

    profile = get_user_profile(str(user_id), db_path=db_path, created_at=created_at)
    if not profile:
        raise SourceCueError(
            f"no inherited TwinMarket profile found for user_id={user_id!r} at created_at={created_at!r}"
        )
    user_type = profile.get("user_type")
    if not isinstance(user_type, str) or not user_type:
        raise SourceCueError("inherited TwinMarket profile has no usable user_type")
    return {
        "user_id": str(user_id),
        "user_type": user_type,
        "source_label": source_label_for_user_type(user_type),
    }


def decorate_controlled_stimulus_payload(
    payload: Mapping[str, Any],
) -> dict[str, str | None]:
    """Attach source metadata to one *already-visible* Phase 11 participant payload.

    This function has no date/step/moment arguments by design. Visibility must be
    resolved upstream by ``StimulusEngine.participant_payload``. Unknown fields or
    stimulus IDs fail closed so internal metadata cannot leak through this layer.
    """
    extra = set(payload) - _PHASE11_PARTICIPANT_KEYS
    if extra:
        raise SourceCueError(
            f"controlled stimulus payload contains unsupported participant fields: {sorted(extra)}"
        )
    missing = {"stimulus_id", "kind", "headline", "body"} - set(payload)
    if missing:
        raise SourceCueError(f"controlled stimulus payload is missing required fields: {sorted(missing)}")

    stimulus_id = payload.get("stimulus_id")
    try:
        cue = _CONTROLLED_STIMULUS_CUES[str(stimulus_id)]
    except KeyError as exc:
        raise SourceCueError(
            f"no Phase 12 source cue declared for controlled stimulus {stimulus_id!r}"
        ) from exc

    # Explicit allow-list projection: Phase 11 text/IDs are copied unchanged and
    # only the two source presentation fields are added.
    decorated: dict[str, str | None] = {
        "stimulus_id": str(payload["stimulus_id"]),
        "kind": str(payload["kind"]),
        "headline": str(payload["headline"]),
        "body": str(payload["body"]),
        "corrects_stimulus_id": (
            None if payload.get("corrects_stimulus_id") is None else str(payload["corrects_stimulus_id"])
        ),
        "source_label": cue["source_label"],
        "source_descriptor": cue["source_descriptor"],
    }
    if set(decorated) != _PHASE11_PARTICIPANT_KEYS | _PHASE12_ADDED_KEYS:
        raise SourceCueError("internal source-cue projection invariant failed")
    return decorated


def source_cue_manifest_payload() -> dict[str, object]:
    """Return the exact formal Phase 12 display mapping in canonical-hash form."""
    return {
        "cue_version": CUE_VERSION,
        "cue_status": CUE_STATUS,
        "agent_user_type_labels": dict(_USER_TYPE_LABELS),
        "controlled_stimulus_cues": {
            stimulus_id: dict(cue)
            for stimulus_id, cue in _CONTROLLED_STIMULUS_CUES.items()
        },
    }


def source_cue_manifest_sha256() -> str:
    """Hash the formal mapping using the already-frozen Phase 11 canonical JSON helper."""
    from marketlens.stimulus.manifest import sha256_json

    return sha256_json(source_cue_manifest_payload())


def assert_formal_source_cue_freeze() -> str:
    """Fail closed unless the exact Phase 12 formal mapping is intact."""
    if CUE_STATUS != "formal_frozen" or CUE_VERSION != "1.0":
        raise SourceCueError(
            f"formal source-cue use rejected: version/status are {CUE_VERSION!r}/{CUE_STATUS!r}"
        )
    actual = source_cue_manifest_sha256()
    if actual != SOURCE_CUE_MANIFEST_SHA256:
        raise SourceCueError(
            "formal source-cue mapping hash mismatch; create a new cue version rather than silently changing frozen wording"
        )
    return actual

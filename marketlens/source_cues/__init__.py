"""MarketLens Phase 12 thin source-cue adapter."""

from .adapter import (
    CUE_STATUS,
    CUE_VERSION,
    SOURCE_CUE_MANIFEST_SHA256,
    SourceCueError,
    assert_formal_source_cue_freeze,
    decorate_controlled_stimulus_payload,
    resolve_agent_source_cue,
    source_cue_manifest_payload,
    source_cue_manifest_sha256,
    source_label_for_user_type,
)

__all__ = [
    "CUE_STATUS",
    "CUE_VERSION",
    "SOURCE_CUE_MANIFEST_SHA256",
    "SourceCueError",
    "assert_formal_source_cue_freeze",
    "decorate_controlled_stimulus_payload",
    "resolve_agent_source_cue",
    "source_cue_manifest_payload",
    "source_cue_manifest_sha256",
    "source_label_for_user_type",
]

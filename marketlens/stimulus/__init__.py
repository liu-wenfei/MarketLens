"""MarketLens Phase 11 participant-only controlled-stimulus layer."""

from .engine import StimulusEngine, StimulusVisibilityError, VisibilityMoment
from .material import default_development_material_path, load_material
from .schema import (
    CORRECTION_RELEASE_EVENT,
    MISINFORMATION_RELEASE_EVENT,
    FormalUseStatus,
    StimulusItem,
    StimulusKind,
    StimulusMaterial,
    StimulusValidationError,
)

__all__ = [
    "CORRECTION_RELEASE_EVENT",
    "MISINFORMATION_RELEASE_EVENT",
    "FormalUseStatus",
    "StimulusEngine",
    "StimulusItem",
    "StimulusKind",
    "StimulusMaterial",
    "StimulusValidationError",
    "StimulusVisibilityError",
    "VisibilityMoment",
    "default_development_material_path",
    "load_material",
]

"""MarketLens Phase 3A: bounded Agent source validation and selection."""

from .selection import PopulationSelection, select_population
from .source import AgentPersona, SourcePopulation, validate_source_population

__all__ = [
    "AgentPersona",
    "PopulationSelection",
    "SourcePopulation",
    "select_population",
    "validate_source_population",
]

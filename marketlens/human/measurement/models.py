from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


DEFAULT_PARTICIPANT_EVENT_DB = "data/marketlens/human/participant_events.db"


class ParticipantEventType(StrEnum):
    BACKGROUND_EXPOSED = "BACKGROUND_EXPOSED"
    CONTROLLED_STIMULUS_EXPOSED = "CONTROLLED_STIMULUS_EXPOSED"
    JUDGEMENT_SUBMITTED = "JUDGEMENT_SUBMITTED"
    CONFIDENCE_RECORDED = "CONFIDENCE_RECORDED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    TRADE_SETTLED = "TRADE_SETTLED"
    PORTFOLIO_STATE_RECORDED = "PORTFOLIO_STATE_RECORDED"


@dataclass(frozen=True)
class ParticipantEvent:
    event_id: str
    request_id: str
    session_id: str
    participant_id: str
    episode_id: str
    experiment_step: int
    agent_world_date: str
    event_type: ParticipantEventType
    market_open: bool
    participant_trading_enabled: bool
    occurred_at_utc: str
    domain_record_id: str | None = None
    stimulus_id: str | None = None
    stimulus_version: str | None = None
    stimulus_sha256: str | None = None
    source_cue: str | None = None
    payload_digest: str | None = None

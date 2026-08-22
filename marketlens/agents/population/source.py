"""Read and validate the inherited TwinMarket Agent persona source database.

Phase 3 treats ``data/sys_1000.db`` as an inherited, read-only source pool.
Nothing in this module assigns source status, evaluates performance, or runs an
Agent. It validates identity/strategy integrity and returns immutable metadata
for deterministic bounded-population selection.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
from pathlib import Path
import sqlite3
from typing import Any, Mapping


FUNDAMENTAL_LABEL = "基本面"
TECHNICAL_LABEL = "技术面"
ALLOWED_STRATEGIES = frozenset({FUNDAMENTAL_LABEL, TECHNICAL_LABEL})

REQUIRED_TABLES = frozenset(
    {"Profiles", "Strategy", "TradingDetails", "StockProfile", "StockData"}
)

# These fields describe the inherited persona rather than mutable investment
# outcomes. The fingerprint is audit evidence only; it is never a selection
# input.
PERSONA_IDENTITY_FIELDS = (
    "user_id",
    "gender",
    "location",
    "user_type",
    "bh_disposition_effect_category",
    "bh_lottery_preference_category",
    "bh_total_return_category",
    "bh_annual_turnover_category",
    "bh_underdiversification_category",
    "trade_count_category",
    "sys_prompt",
    "prompt",
    "self_description",
    "trad_pro",
    "fol_ind",
    "strategy",
)


class PopulationSourceError(RuntimeError):
    """Raised when the inherited source population is structurally ambiguous."""


@dataclass(frozen=True)
class AgentPersona:
    user_id: str
    strategy: str
    user_type: str
    gender: str | None
    location: str | None
    persona_fingerprint_sha256: str


@dataclass(frozen=True)
class SourcePopulation:
    source_db: Path
    source_sha256: str
    agents: Mapping[str, AgentPersona]
    strategy_counts: Mapping[str, int]
    user_type_counts: Mapping[str, int]
    joint_counts: Mapping[str, Mapping[str, int]]

    @property
    def total_agents(self) -> int:
        return len(self.agents)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _connect_read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise PopulationSourceError(f"source population database does not exist: {path}")
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _fingerprint_profile(row: sqlite3.Row) -> str:
    values = []
    keys = set(row.keys())
    for field in PERSONA_IDENTITY_FIELDS:
        if field not in keys:
            raise PopulationSourceError(f"Profiles is missing required persona field {field!r}")
        value = row[field]
        values.append(f"{field}={value!r}")
    return hashlib.sha256("\n".join(values).encode("utf-8")).hexdigest()


def _required_tables(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }


def validate_source_population(source_db: str | Path) -> SourcePopulation:
    """Validate and load the inherited Agent population without modifying it.

    Validation intentionally fails on ambiguous identity/strategy state instead
    of guessing which row is authoritative. ``user_type`` is required and
    inherited, but it is not constrained to a quota here.
    """

    path = Path(source_db).resolve()
    hash_before = sha256_file(path)
    connection = _connect_read_only(path)
    try:
        missing = REQUIRED_TABLES - _required_tables(connection)
        if missing:
            raise PopulationSourceError(
                f"source population is missing required table(s): {sorted(missing)}"
            )

        profile_rows = connection.execute(
            "SELECT * FROM Profiles ORDER BY CAST(user_id AS TEXT), created_at"
        ).fetchall()
        if not profile_rows:
            raise PopulationSourceError("Profiles contains no Agents")

        profile_counts = Counter(str(row["user_id"]) for row in profile_rows)
        duplicates = sorted(uid for uid, count in profile_counts.items() if count != 1)
        if duplicates:
            raise PopulationSourceError(
                "Profiles must contain exactly one row per Agent for Phase 3; "
                f"ambiguous user_id(s): {duplicates[:10]}"
            )

        strategy_rows = connection.execute(
            'SELECT user_id, strategy FROM "Strategy" ORDER BY CAST(user_id AS TEXT)'
        ).fetchall()
        strategy_counts_by_id = Counter(str(row["user_id"]) for row in strategy_rows)
        duplicate_strategy = sorted(
            uid for uid, count in strategy_counts_by_id.items() if count != 1
        )
        if duplicate_strategy:
            raise PopulationSourceError(
                "Strategy must contain exactly one row per Agent; "
                f"ambiguous user_id(s): {duplicate_strategy[:10]}"
            )

        profile_ids = set(profile_counts)
        strategy_ids = set(strategy_counts_by_id)
        if profile_ids != strategy_ids:
            missing_strategy = sorted(profile_ids - strategy_ids)
            orphan_strategy = sorted(strategy_ids - profile_ids)
            raise PopulationSourceError(
                "Profiles/Strategy Agent membership mismatch: "
                f"missing_strategy={missing_strategy[:10]}, "
                f"orphan_strategy={orphan_strategy[:10]}"
            )

        strategy_by_id = {str(row["user_id"]): row["strategy"] for row in strategy_rows}
        agents: dict[str, AgentPersona] = {}
        strategy_counter: Counter[str] = Counter()
        user_type_counter: Counter[str] = Counter()
        joint_counter: dict[str, Counter[str]] = {}

        for row in profile_rows:
            user_id = str(row["user_id"])
            profile_strategy = row["strategy"]
            table_strategy = strategy_by_id[user_id]
            if profile_strategy not in ALLOWED_STRATEGIES:
                raise PopulationSourceError(
                    f"Agent {user_id} has unexpected Profiles.strategy {profile_strategy!r}"
                )
            if table_strategy not in ALLOWED_STRATEGIES:
                raise PopulationSourceError(
                    f"Agent {user_id} has unexpected Strategy.strategy {table_strategy!r}"
                )
            if profile_strategy != table_strategy:
                raise PopulationSourceError(
                    f"Agent {user_id} strategy disagreement: "
                    f"Profiles={profile_strategy!r}, Strategy={table_strategy!r}"
                )

            user_type = row["user_type"]
            if user_type is None or not str(user_type).strip():
                raise PopulationSourceError(f"Agent {user_id} has empty user_type")
            user_type = str(user_type)

            persona = AgentPersona(
                user_id=user_id,
                strategy=str(profile_strategy),
                user_type=user_type,
                gender=None if row["gender"] is None else str(row["gender"]),
                location=None if row["location"] is None else str(row["location"]),
                persona_fingerprint_sha256=_fingerprint_profile(row),
            )
            agents[user_id] = persona
            strategy_counter[persona.strategy] += 1
            user_type_counter[persona.user_type] += 1
            joint_counter.setdefault(persona.user_type, Counter())[persona.strategy] += 1

        orphan_trades = connection.execute(
            """
            SELECT DISTINCT CAST(t.user_id AS TEXT)
            FROM TradingDetails AS t
            LEFT JOIN Profiles AS p
              ON CAST(p.user_id AS TEXT) = CAST(t.user_id AS TEXT)
            WHERE p.user_id IS NULL
            LIMIT 10
            """
        ).fetchall()
        if orphan_trades:
            raise PopulationSourceError(
                "TradingDetails contains Agent IDs absent from Profiles: "
                f"{[str(row[0]) for row in orphan_trades]}"
            )
    finally:
        connection.close()

    hash_after = sha256_file(path)
    if hash_after != hash_before:
        raise PopulationSourceError(
            "source population database changed during the read-only validation pass"
        )

    return SourcePopulation(
        source_db=path,
        source_sha256=hash_before,
        agents=agents,
        strategy_counts=dict(sorted(strategy_counter.items())),
        user_type_counts=dict(sorted(user_type_counter.items())),
        joint_counts={
            user_type: dict(sorted(counts.items()))
            for user_type, counts in sorted(joint_counter.items())
        },
    )

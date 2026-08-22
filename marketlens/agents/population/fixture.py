"""Phase 3B: freeze a Phase 3A selection into a bounded TwinMarket runtime fixture."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
from typing import Sequence

from .selection import PopulationSelection, select_population
from .source import SourcePopulation, sha256_file, validate_source_population


BUNDLE_STATUS = "PROVISIONAL / DEVELOPMENT / NOT FORMAL POPULATION FREEZE"
MANIFEST_SCHEMA_VERSION = "marketlens-agent-population-manifest/1.0"
RUNTIME_FIXTURE_VERSION = "twinmarket-bounded-user-db/1.0"
SOURCE_TABLES = ("Profiles", "Strategy", "TradingDetails", "StockProfile", "StockData")


class PopulationFixtureError(RuntimeError):
    """Raised when a bounded runtime fixture cannot be built safely."""


def _connect_ro(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _table_ddl(connection: sqlite3.Connection, table: str) -> str:
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if row is None or not row[0]:
        raise PopulationFixtureError(f"source database has no table {table!r}")
    return str(row[0])


def _columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in connection.execute(f'PRAGMA table_info("{table}")')]


def _copy_rows(
    source: sqlite3.Connection,
    destination: sqlite3.Connection,
    table: str,
    *,
    selected_ids: Sequence[str] | None = None,
) -> int:
    columns = _columns(source, table)
    quoted_columns = ", ".join(f'"{column}"' for column in columns)
    query = f'SELECT {quoted_columns} FROM "{table}"'
    params: tuple[str, ...] = ()

    if selected_ids is not None:
        if not selected_ids:
            return 0
        placeholders = ",".join("?" for _ in selected_ids)
        query += f" WHERE CAST(user_id AS TEXT) IN ({placeholders})"
        params = tuple(str(user_id) for user_id in selected_ids)

    rows = source.execute(query, params).fetchall()
    if rows:
        insert_placeholders = ",".join("?" for _ in columns)
        destination.executemany(
            f'INSERT INTO "{table}" ({quoted_columns}) VALUES ({insert_placeholders})',
            [tuple(row[column] for column in columns) for row in rows],
        )
    return len(rows)


def _table_digest(
    connection: sqlite3.Connection,
    table: str,
    *,
    selected_ids: Sequence[str] | None = None,
) -> str:
    columns = _columns(connection, table)
    quoted_columns = ", ".join(f'"{column}"' for column in columns)
    query = f'SELECT {quoted_columns} FROM "{table}"'
    params: tuple[str, ...] = ()
    if selected_ids is not None:
        placeholders = ",".join("?" for _ in selected_ids)
        query += f" WHERE CAST(user_id AS TEXT) IN ({placeholders})"
        params = tuple(str(user_id) for user_id in selected_ids)

    rows = [tuple(row) for row in connection.execute(query, params).fetchall()]
    rows.sort(key=lambda row: tuple("" if value is None else repr(value) for value in row))
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_runtime_fixture(
    source_db: str | Path,
    output_db: str | Path,
    selected_agent_ids: Sequence[str],
) -> dict[str, object]:
    """Create a bounded UserDB from an already selected Agent membership.

    Phase 3B does not decide who should be selected. It consumes the exact
    selected IDs produced by the Phase 3A selector. The inherited source is
    opened read-only and hashed before/after. Profiles, Strategy and
    TradingDetails are filtered to selected Agents; StockProfile and StockData
    are copied unchanged.
    """

    source_path = Path(source_db).resolve()
    output_path = Path(output_db).resolve()
    selected_ids = tuple(str(user_id) for user_id in selected_agent_ids)
    if not selected_ids:
        raise PopulationFixtureError("selected_agent_ids must not be empty")
    if len(set(selected_ids)) != len(selected_ids):
        raise PopulationFixtureError("selected_agent_ids contains duplicates")
    if output_path.exists():
        raise PopulationFixtureError(f"refusing to overwrite existing fixture: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    source_hash_before = sha256_file(source_path)
    source = _connect_ro(source_path)
    destination = sqlite3.connect(output_path)
    try:
        destination.execute("PRAGMA foreign_keys = OFF")
        destination.execute("BEGIN")
        for table in SOURCE_TABLES:
            destination.execute(_table_ddl(source, table))

        counts = {
            "Profiles": _copy_rows(source, destination, "Profiles", selected_ids=selected_ids),
            "Strategy": _copy_rows(source, destination, "Strategy", selected_ids=selected_ids),
            "TradingDetails": _copy_rows(
                source, destination, "TradingDetails", selected_ids=selected_ids
            ),
            "StockProfile": _copy_rows(source, destination, "StockProfile"),
            "StockData": _copy_rows(source, destination, "StockData"),
        }
        destination.commit()

        expected_ids = set(selected_ids)
        fixture_ids = {
            str(row[0])
            for row in destination.execute("SELECT user_id FROM Profiles").fetchall()
        }
        if fixture_ids != expected_ids:
            raise PopulationFixtureError(
                "runtime fixture Profiles membership differs from selected Agent IDs"
            )
        if counts["Profiles"] != len(expected_ids) or counts["Strategy"] != len(expected_ids):
            raise PopulationFixtureError(
                "runtime fixture does not contain exactly one Profiles/Strategy row per Agent"
            )

        orphan_trade = destination.execute(
            """
            SELECT 1
            FROM TradingDetails AS t
            LEFT JOIN Profiles AS p
              ON CAST(p.user_id AS TEXT) = CAST(t.user_id AS TEXT)
            WHERE p.user_id IS NULL
            LIMIT 1
            """
        ).fetchone()
        if orphan_trade is not None:
            raise PopulationFixtureError("runtime fixture contains orphan TradingDetails rows")

        table_digests: dict[str, str] = {}
        for table in SOURCE_TABLES:
            selected_filter = selected_ids if table in {
                "Profiles",
                "Strategy",
                "TradingDetails",
            } else None
            source_digest = _table_digest(source, table, selected_ids=selected_filter)
            fixture_digest = _table_digest(destination, table)
            if fixture_digest != source_digest:
                raise PopulationFixtureError(
                    f"runtime fixture table {table!r} is not an exact inherited copy/filter"
                )
            table_digests[table] = fixture_digest
    except Exception:
        destination.rollback()
        destination.close()
        source.close()
        if output_path.exists():
            output_path.unlink()
        raise
    else:
        destination.close()
        source.close()

    source_hash_after = sha256_file(source_path)
    if source_hash_after != source_hash_before:
        if output_path.exists():
            output_path.unlink()
        raise PopulationFixtureError("source database changed while building runtime fixture")

    return {
        "fixture_version": RUNTIME_FIXTURE_VERSION,
        "fixture_db": str(output_path),
        "fixture_sha256": sha256_file(output_path),
        "row_counts": counts,
        "table_digests_sha256": table_digests,
        "source_sha256_before": source_hash_before,
        "source_sha256_after": source_hash_after,
    }


def _manifest(
    source: SourcePopulation,
    selection: PopulationSelection,
    fixture_info: dict[str, object],
) -> dict[str, object]:
    selected_agents = [source.agents[user_id] for user_id in selection.selected_agent_ids]
    strategy_counts = Counter(agent.strategy for agent in selected_agents)
    user_type_counts = Counter(agent.user_type for agent in selected_agents)
    joint: dict[str, Counter[str]] = {}
    for agent in selected_agents:
        joint.setdefault(agent.user_type, Counter())[agent.strategy] += 1

    user_type_coverage = {
        user_type: user_type_counts.get(user_type, 0) > 0
        for user_type in sorted(source.user_type_counts)
    }
    warnings = [
        f"source user_type {user_type!r} is absent from this bounded population; "
        "this is reported, not repaired, because user_type is inherited rather than quota-controlled"
        for user_type, present in user_type_coverage.items()
        if not present
    ]

    return {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "status": BUNDLE_STATUS,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "database": str(source.source_db),
            "sha256": source.source_sha256,
            "total_agents": source.total_agents,
            "strategy_counts": dict(source.strategy_counts),
            "user_type_counts": dict(source.user_type_counts),
            "joint_strategy_user_type_counts": dict(source.joint_counts),
        },
        "selection": {
            "phase3a_owner": "marketlens.agents.population.selection",
            "algorithm": selection.algorithm,
            "seed": selection.seed,
            "population_size": selection.population_size,
            "strategy_policy": (
                "source-ratio stratified; exact integer allocation by largest remainder"
            ),
            "user_type_policy": (
                "inherited from selected source personas; no user_type quota or forced coverage"
            ),
            "selection_inputs": ["user_id", "strategy", "seed"],
            "explicitly_not_selection_inputs": [
                "user_type",
                "gender",
                "location",
                "trad_pro",
                "current_cash",
                "cur_positions",
                "total_return",
                "return_rate",
                "TradingDetails",
                "participant data",
            ],
            "strategy_allocation": dict(selection.strategy_allocation),
            "selected_agent_ids": list(selection.selected_agent_ids),
            "selected_agent_ids_sha256": selection.selected_agent_ids_sha256,
        },
        "selected_population": {
            "strategy_counts": dict(sorted(strategy_counts.items())),
            "user_type_counts": dict(sorted(user_type_counts.items())),
            "joint_strategy_user_type_counts": {
                user_type: dict(sorted(counts.items()))
                for user_type, counts in sorted(joint.items())
            },
            "user_type_coverage": user_type_coverage,
            "coverage_warnings": warnings,
            "agents": [
                {
                    "user_id": agent.user_id,
                    "strategy": agent.strategy,
                    "user_type": agent.user_type,
                    "persona_fingerprint_sha256": agent.persona_fingerprint_sha256,
                }
                for agent in selected_agents
            ],
        },
        "runtime_fixture": fixture_info,
        "scope": {
            "phase": "3B",
            "includes": [
                "freeze exact Phase 3A membership",
                "population manifest",
                "TwinMarket-compatible filtered runtime UserDB",
                "source and fixture integrity evidence",
            ],
            "excludes": [
                "selection-policy changes",
                "Agent activation",
                "LLM inference",
                "belief evolution",
                "social graph / is_top_user",
                "news or market trajectory control",
                "misinformation / correction stimuli",
                "participant-visible source-cue policy",
                "formal population-size feasibility evidence",
            ],
        },
    }


def build_population_bundle(
    *,
    source_db: str | Path,
    population_size: int,
    seed: str,
    output_dir: str | Path,
) -> dict[str, object]:
    """Freeze one provisional population using the committed Phase 3A selector.

    Phase 3B owns orchestration and fixture construction only. Membership is
    produced by calling the Phase 3A `select_population` API; this module does
    not implement or alter the selection algorithm.
    """

    output_path = Path(output_dir).resolve()
    if output_path.exists():
        raise PopulationFixtureError(
            f"refusing to overwrite existing population bundle directory: {output_path}"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    source = validate_source_population(source_db)
    selection = select_population(source, population_size=population_size, seed=seed)

    with tempfile.TemporaryDirectory(
        prefix=f".{output_path.name}-", dir=str(output_path.parent)
    ) as temp_dir:
        temp_path = Path(temp_dir)
        runtime_db = temp_path / "population_runtime.db"
        fixture_info = build_runtime_fixture(
            source.source_db, runtime_db, selection.selected_agent_ids
        )
        fixture_info = dict(fixture_info)
        fixture_info["fixture_db"] = "population_runtime.db"
        manifest = _manifest(source, selection, fixture_info)

        (temp_path / "selected_agent_ids.txt").write_text(
            "\n".join(selection.selected_agent_ids) + "\n", encoding="utf-8"
        )
        (temp_path / "population_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        shutil.move(str(temp_path), str(output_path))

    return manifest

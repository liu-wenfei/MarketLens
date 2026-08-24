from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from marketlens.agents.population.fixture import build_population_bundle
from marketlens.episode.contract import EPISODE_IDS, EXPECTED_EXECUTION_PLAN_SHA256
from marketlens.episode.producer import (
    PRODUCER_CONTRACT_SHA256,
    CanonicalEpisodeProducerError,
    _next_attempt_dir,
    dry_run_summary,
    execute_formal_episode_slot,
    finalize_formal_episode_pool,
    load_producer_contract,
    validate_forum_profile_source_cue_join,
    validate_participant_price_coverage,
    validate_runtime_dependencies,
    verify_candidate_fixture,
)
from marketlens.market.asset_catalog import AssetCatalog
from marketlens.experiment.protocol import load_protocol

REPO_ROOT = Path(__file__).resolve().parents[3]


def _copy_required_repo_inputs(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for relative in (
        "data/sys_1000.db",
        "data/trading_days.csv",
        "data/sorted_impact_news.pkl",
        "util/belief/belief_1000_0129.csv",
        "data/stock_profile.csv",
        "data/stock_data.csv",
        "marketlens/experiment/protocol_v1.json",
    ):
        src = REPO_ROOT / relative
        dst = root / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    config = root / "config/api.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        "model_name: gpt-5.4-mini\nbase_url: https://zhi-api.com/v1\napi_key: test-only\n",
        encoding="utf-8",
    )
    fixture_dir = root / "artifacts/preflight/phase10/n30_candidate_fixture"
    build_population_bundle(
        source_db=root / "data/sys_1000.db",
        population_size=30,
        seed="marketlens-dev-population-01",
        output_dir=fixture_dir,
    )
    return root


def test_phase13d_contract_binds_exact_phase13c_plan():
    contract = load_producer_contract()
    assert contract["phase13c_execution_plan_sha256"] == EXPECTED_EXECUTION_PLAN_SHA256
    assert contract["episode_ids"] == list(EPISODE_IDS)
    assert PRODUCER_CONTRACT_SHA256 == "14db0ae7a525ef464975f7ba4da69d98eb8ffd4058d491555a32ee25f92a9126"


def test_phase13d_contract_defaults_zero_llm_and_forbids_execute_all():
    controls = load_producer_contract()["execution_controls"]
    assert controls["default_mode"] == "dry_run_zero_llm"
    assert controls["full_pool_execute_command_allowed"] is False
    assert controls["one_explicit_episode_slot_per_execute_command"] is True
    assert controls["partial_resume_allowed"] is False
    assert controls["overwrite_formal_slot_allowed"] is False


def test_phase13d_contract_has_no_outcome_acceptance_gate():
    acceptance = load_producer_contract()["technical_acceptance"]
    for key in (
        "minimum_post_count",
        "minimum_trade_count",
        "price_direction",
        "sentiment",
        "misinformation_effect",
        "cross_episode_divergence",
    ):
        assert acceptance[key] is None


def test_runtime_dependency_gate_accepts_predeclared_hashes_and_backend(tmp_path):
    root = _copy_required_repo_inputs(tmp_path)
    observed = validate_runtime_dependencies(repo_root=root, require_api_key=True)
    assert observed["backend"]["model_name"] == "gpt-5.4-mini"
    assert observed["backend"]["base_url"] == "https://zhi-api.com/v1"
    assert observed["backend"]["api_key_configured"] is True


def test_runtime_dependency_gate_rejects_protected_input_drift(tmp_path):
    root = _copy_required_repo_inputs(tmp_path)
    with (root / "data/trading_days.csv").open("a", encoding="utf-8") as handle:
        handle.write("\n")
    with pytest.raises(CanonicalEpisodeProducerError, match="protected formal input drifted"):
        validate_runtime_dependencies(repo_root=root)


def test_runtime_dependency_gate_rejects_backend_identity_drift(tmp_path):
    root = _copy_required_repo_inputs(tmp_path)
    (root / "config/api.yaml").write_text(
        "model_name: another-model\nbase_url: https://zhi-api.com/v1\napi_key: x\n",
        encoding="utf-8",
    )
    with pytest.raises(CanonicalEpisodeProducerError, match="formal model mismatch"):
        validate_runtime_dependencies(repo_root=root)


def test_phase13d_dry_run_verifies_fixture_without_writing_formal_assets(tmp_path):
    root = _copy_required_repo_inputs(tmp_path)
    summary = dry_run_summary(repo_root=root)
    assert summary["status"] == "READY / ZERO-LLM / NO FORMAL EPISODE MUTATION"
    assert summary["llm_api_calls"] == 0
    assert summary["formal_execution_performed"] is False
    assert summary["world_ticks_per_episode"] == 27
    assert summary["agent_pipeline_executions_per_episode"] == 193
    assert summary["expected_pool_agent_pipeline_executions"] == 579
    assert not (root / "data/marketlens/canonical_episode/v1").exists()


def test_phase13d_candidate_fixture_reuses_phase10_semantic_guard(tmp_path):
    root = _copy_required_repo_inputs(tmp_path)
    observed = verify_candidate_fixture(repo_root=root)
    assert len(observed["population_ids"]) == 30
    assert observed["runtime_sha256"]
    assert observed["population_manifest_sha256"]


def _decision_dates() -> tuple[str, ...]:
    protocol = load_protocol(REPO_ROOT / "marketlens/experiment/protocol_v1.json")
    return tuple(
        row["agent_world_date"] for row in protocol["timeline"] if row.get("shadow_trade_enabled")
    )


def test_participant_exact_price_coverage_gate_accepts_complete_canonical_db(tmp_path):
    db = tmp_path / "world.db"
    assets = AssetCatalog(REPO_ROOT / "data/stock_profile.csv").ids()
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE StockData (stock_id TEXT, close_price REAL, date TEXT)")
        conn.executemany(
            "INSERT INTO StockData(stock_id, close_price, date) VALUES (?, ?, ?)",
            [(stock, 10.0, day) for day in _decision_dates() for stock in assets],
        )
    result = validate_participant_price_coverage(repo_root=REPO_ROOT, agent_world_db=db)
    assert result["complete"] is True
    assert result["decision_date_count"] == 15
    assert result["expected_exact_price_cells"] == len(assets) * 15


def test_participant_exact_price_coverage_gate_fails_closed_on_missing_cell(tmp_path):
    db = tmp_path / "world.db"
    assets = AssetCatalog(REPO_ROOT / "data/stock_profile.csv").ids()
    rows = [(stock, 10.0, day) for day in _decision_dates() for stock in assets]
    rows.pop()
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE StockData (stock_id TEXT, close_price REAL, date TEXT)")
        conn.executemany("INSERT INTO StockData VALUES (?, ?, ?)", rows)
    result = validate_participant_price_coverage(repo_root=REPO_ROOT, agent_world_db=db)
    assert result["complete"] is False
    assert len(result["missing"]) == 1


def test_forum_profile_join_gate_accepts_same_day_source_snapshot(tmp_path):
    world = tmp_path / "world.db"
    forum = tmp_path / "forum.db"
    with sqlite3.connect(world) as conn:
        conn.execute("CREATE TABLE Profiles (user_id TEXT, user_type TEXT, created_at TEXT)")
        conn.execute("INSERT INTO Profiles VALUES ('u1', '普通股民', '2023-06-19 00:00:00')")
    with sqlite3.connect(forum) as conn:
        conn.execute("CREATE TABLE posts (id INTEGER, user_id TEXT, type TEXT, created_at TEXT)")
        conn.execute("INSERT INTO posts VALUES (1, 'u1', 'type1', '2023-06-19 12:00:00')")
    result = validate_forum_profile_source_cue_join(agent_world_db=world, forum_db=forum)
    assert result["complete"] is True
    assert result["participant_visible_nonrepost_posts_checked"] == 1


def test_forum_profile_join_gate_fails_closed_on_missing_same_day_snapshot(tmp_path):
    world = tmp_path / "world.db"
    forum = tmp_path / "forum.db"
    with sqlite3.connect(world) as conn:
        conn.execute("CREATE TABLE Profiles (user_id TEXT, user_type TEXT, created_at TEXT)")
        conn.execute("INSERT INTO Profiles VALUES ('u1', '普通股民', '2023-06-18 00:00:00')")
    with sqlite3.connect(forum) as conn:
        conn.execute("CREATE TABLE posts (id INTEGER, user_id TEXT, type TEXT, created_at TEXT)")
        conn.execute("INSERT INTO posts VALUES (1, 'u1', 'type1', '2023-06-19 12:00:00')")
    result = validate_forum_profile_source_cue_join(agent_world_db=world, forum_db=forum)
    assert result["complete"] is False
    assert result["missing_same_day_profile_snapshots"][0]["post_id"] == "1"


def test_execute_slot_requires_explicit_acknowledgement_before_backend_use():
    with pytest.raises(CanonicalEpisodeProducerError, match="explicit acknowledgement"):
        execute_formal_episode_slot(
            repo_root=REPO_ROOT,
            episode_id=EPISODE_IDS[0],
            acknowledge_formal_execution=False,
        )


def test_execute_slot_rejects_unknown_episode_id():
    with pytest.raises(CanonicalEpisodeProducerError, match="unknown formal episode slot"):
        execute_formal_episode_slot(
            repo_root=REPO_ROOT,
            episode_id="episode_99",
            acknowledge_formal_execution=True,
        )


def test_attempt_numbering_never_overwrites_previous_attempt(tmp_path):
    root = tmp_path / "raw"
    root.mkdir()
    (root / "attempt_001").mkdir()
    (root / "attempt_002").mkdir()
    number, path = _next_attempt_dir(root)
    assert number == 3
    assert path.name == "attempt_003"
    assert not path.exists()


def test_pool_finalization_fails_closed_until_all_slots_exist(tmp_path):
    with pytest.raises(CanonicalEpisodeProducerError, match="cannot finalize pool"):
        finalize_formal_episode_pool(repo_root=tmp_path)

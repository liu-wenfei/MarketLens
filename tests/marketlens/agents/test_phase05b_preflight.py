from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from marketlens.agents.runtime.preflight import (
    HISTORY_CUTOFF,
    FORCED_SINGLE_AGENT_DRAW_ALGORITHM,
    Phase05BPreflightError,
    build_forced_single_agent_batch,
    build_phase4_activation_batch,
    create_empty_forum_db,
    load_day1_frames,
    load_initial_beliefs,
    run_phase05b_preflight,
    sha256_file,
    verify_population_fixture,
)


def _build_runtime(path: Path) -> tuple[str, ...]:
    ids = ("101", "202", "303")
    con = sqlite3.connect(path)
    try:
        con.execute(
            """
            CREATE TABLE Profiles (
                user_id TEXT PRIMARY KEY,
                user_type TEXT,
                trade_count_category TEXT,
                strategy TEXT,
                created_at TEXT
            )
            """
        )
        con.execute("CREATE TABLE Strategy (user_id INTEGER, strategy TEXT)")
        con.execute("CREATE TABLE StockData (stock_id TEXT, close_price REAL, date TEXT)")
        con.executemany(
            "INSERT INTO Profiles VALUES (?, ?, ?, ?, ?)",
            [
                ("101", "普通股民", "低", "基本面", "2023-06-14 00:00:00"),
                ("202", "小博主", "中", "技术面", "2023-06-14 00:00:00"),
                ("303", "普通股民", "高", "技术面", "2023-06-14 00:00:00"),
            ],
        )
        con.executemany(
            "INSERT INTO Strategy VALUES (?, ?)",
            [(101, "基本面"), (202, "技术面"), (303, "技术面")],
        )
        con.executemany(
            "INSERT INTO StockData VALUES (?, ?, ?)",
            [
                ("S1", 10.0, "2023-06-13"),
                ("S1", 11.0, "2023-06-14"),
                ("S1", 999.0, "2023-06-15"),
            ],
        )
        con.commit()
    finally:
        con.close()
    return ids


def _write_manifest(path: Path, runtime_db: Path, ids: tuple[str, ...]) -> Path:
    manifest = {
        "status": "PROVISIONAL / DEVELOPMENT / NOT FORMAL POPULATION FREEZE",
        "selection": {"selected_agent_ids": list(ids)},
        "runtime_fixture": {"fixture_sha256": sha256_file(runtime_db)},
    }
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def _write_beliefs(path: Path, ids: tuple[str, ...]) -> Path:
    path.write_text(
        "user_id,belief,attitude\n"
        + "\n".join(f'{uid},"belief-{uid}",neutral' for uid in ids)
        + "\n",
        encoding="utf-8",
    )
    return path


def _forum_initializer(*, db_path: str) -> None:
    con = sqlite3.connect(db_path)
    try:
        con.execute("CREATE TABLE posts (id INTEGER PRIMARY KEY, user_id TEXT, content TEXT)")
        con.execute("CREATE TABLE reactions (id INTEGER PRIMARY KEY, post_id INTEGER)")
        con.execute(
            "CREATE TABLE post_references (id INTEGER PRIMARY KEY, reference_id INTEGER, repost_id INTEGER)"
        )
        con.commit()
    finally:
        con.close()


def _fixture(tmp_path: Path):
    runtime = tmp_path / "population_runtime.db"
    ids = _build_runtime(runtime)
    manifest = _write_manifest(tmp_path / "population_manifest.json", runtime, ids)
    beliefs = _write_beliefs(tmp_path / "belief.csv", ids)
    config = tmp_path / "api.yaml"
    # The test deliberately contains an API-key-looking field so we can prove it
    # is never copied into Phase 5B artifacts.
    config.write_text(
        "api_key:\n  - SHOULD_NEVER_APPEAR_IN_ARTIFACTS\n"
        "model_name: fake-model\nbase_url: https://example.invalid/v1\n",
        encoding="utf-8",
    )
    return runtime, manifest, beliefs, config, ids


def test_population_fixture_verification_matches_manifest_and_membership(tmp_path):
    runtime, manifest, _, _, ids = _fixture(tmp_path)
    verified = verify_population_fixture(runtime, manifest)
    assert verified.population_ids == ids
    assert verified.runtime_sha256 == sha256_file(runtime)
    assert verified.manifest_path == manifest.resolve()


def test_population_fixture_hash_mismatch_fails_closed(tmp_path):
    runtime, manifest, _, _, _ = _fixture(tmp_path)
    doc = json.loads(manifest.read_text())
    doc["runtime_fixture"]["fixture_sha256"] = "0" * 64
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(Phase05BPreflightError, match="hash does not match"):
        verify_population_fixture(runtime, manifest)


def test_forced_one_agent_gate_keeps_complete_population_mapping_but_exactly_one_active(tmp_path):
    runtime, _, _, _, ids = _fixture(tmp_path)
    batch = build_forced_single_agent_batch(runtime, "202")
    assert tuple(result.user_id for result in batch.results) == ids
    assert batch.active_agent_ids == ("202",)
    assert sum(result.is_active for result in batch.results) == 1
    assert batch.draw_algorithm == FORCED_SINGLE_AGENT_DRAW_ALGORITHM


def test_forced_one_agent_gate_rejects_agent_outside_bounded_population(tmp_path):
    runtime, _, _, _, _ = _fixture(tmp_path)
    with pytest.raises(Phase05BPreflightError, match="outside the bounded"):
        build_forced_single_agent_batch(runtime, "999")


def test_phase4_activation_mode_is_reproducible_and_uses_real_phase4_sampler(tmp_path):
    runtime, _, _, _, _ = _fixture(tmp_path)
    first = build_phase4_activation_batch(runtime, seed="phase05b-fixed-seed")
    second = build_phase4_activation_batch(runtime, seed="phase05b-fixed-seed")
    assert first.active_agent_ids == second.active_agent_ids
    assert [r.random_draw for r in first.results] == [r.random_draw for r in second.results]
    assert first.draw_algorithm.startswith("sha256_agent_step_uniform_bernoulli/")


def test_day1_stock_loader_removes_future_rows(tmp_path):
    runtime, _, _, _, _ = _fixture(tmp_path)
    _, stock = load_day1_frames(runtime)
    assert stock["date"].max() == HISTORY_CUTOFF
    assert 999.0 not in set(stock["close_price"])


def test_initial_belief_loader_fails_closed_for_missing_executing_agent(tmp_path):
    _, _, beliefs, _, _ = _fixture(tmp_path)
    with pytest.raises(Phase05BPreflightError, match="missing=.*404"):
        load_initial_beliefs(beliefs, ("101", "404"))


def test_empty_forum_scaffold_uses_initializer_and_contains_zero_rows(tmp_path):
    forum = create_empty_forum_db(
        tmp_path / "forum.db", forum_initializer=_forum_initializer
    )
    con = sqlite3.connect(forum)
    try:
        assert con.execute("SELECT COUNT(*) FROM posts").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM reactions").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM post_references").fetchone()[0] == 0
    finally:
        con.close()


def test_fake_backend_preflight_uses_phase5a_adapter_and_persists_only_minimal_artifacts(tmp_path):
    runtime, manifest, beliefs, config, ids = _fixture(tmp_path)
    artifacts = tmp_path / "artifacts"
    source_hash = sha256_file(runtime)
    calls = []

    def fake_process(**kwargs):
        calls.append(kwargs)
        uid = kwargs["user_id"]
        return uid, {"read_only_for_test": True}, {"action": "HOLD"}, None

    outcome = run_phase05b_preflight(
        repo_root=tmp_path,
        runtime_db=runtime,
        population_manifest=manifest,
        belief_csv=beliefs,
        config_path=config,
        artifact_root=artifacts,
        mode="one-agent",
        user_id="202",
        process_user_input_fn=fake_process,
        forum_initializer=_forum_initializer,
        require_clean_git=False,
        git_state_override={"commit": "abc12345", "clean": True, "status": ""},
    )

    assert [call["user_id"] for call in calls] == ["202"]
    assert calls[0]["day_1st"] is True
    assert calls[0]["prob_of_technical"] == 0.0
    assert calls[0]["top_user"] == []
    assert calls[0]["import_news"] == []
    assert calls[0]["current_user_graph"].number_of_edges() == 0
    assert set(calls[0]["current_user_graph"].nodes()) == set(ids)

    summary = json.loads((outcome.run_dir / "summary.json").read_text())
    agent = json.loads((outcome.run_dir / "agents" / "202.json").read_text())
    assert summary["status"] == "PASS"
    assert summary["formal_experiment_evidence"] is False
    assert summary["participant_database_used"] is False
    assert summary["day1_context"]["news_supplied"] == 0
    assert summary["day1_context"]["dynamic_top_users_enabled"] is False
    assert summary["agent_execution"]["agent_decisions_applied_to_market"] is False
    assert agent["decision_result"] == {"action": "HOLD"}
    assert agent["user_type"] == "小博主"
    assert sha256_file(runtime) == source_hash

    # Successful runs keep no writable runtime/forum DB copy.
    assert not (outcome.run_dir / "runtime.db").exists()
    assert not (outcome.run_dir / "forum.db").exists()
    assert not (outcome.run_dir / "debug_workspace").exists()

    serialized = (outcome.run_dir / "summary.json").read_text() + agent.__repr__()
    assert "SHOULD_NEVER_APPEAR_IN_ARTIFACTS" not in serialized
    assert summary["backend"]["api_key_recorded"] is False

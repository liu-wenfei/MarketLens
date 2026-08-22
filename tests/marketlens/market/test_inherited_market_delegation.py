from __future__ import annotations

from pathlib import Path

from marketlens.market.runtime import inherited_market


def _file(tmp_path: Path, name: str, content: bytes = b"x") -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


def test_reset_delegates_to_inherited_init_system(monkeypatch, tmp_path):
    runtime = _file(tmp_path, "runtime.db")
    forum = _file(tmp_path, "forum.db")
    seen = {}

    def fake_init_system(current_date, user_db, forum_db):
        seen["current_date"] = current_date
        seen["user_db"] = user_db
        seen["forum_db"] = forum_db

    monkeypatch.setattr(inherited_market, "_twinmarket_init_system", fake_init_system)

    result = inherited_market.reset_agent_world(
        current_date="2023-06-15",
        runtime_db=runtime,
        forum_db=forum,
    )

    assert str(seen["current_date"].date()) == "2023-06-15"
    assert seen["user_db"] == str(runtime.resolve())
    assert seen["forum_db"] == str(forum.resolve())
    assert result.inherited_function == "trader.utility.init_system"
    assert result.participant_data_used is False
    assert result.custom_market_logic_used is False


def test_trading_day_delegates_exact_inherited_signature(monkeypatch, tmp_path):
    runtime = _file(tmp_path, "runtime.db")
    decisions = _file(tmp_path, "decisions.json", b"{}")
    log_dir = tmp_path / "logs"
    seen = {}

    def fake_matching(**kwargs):
        seen.update(kwargs)

    monkeypatch.setattr(
        inherited_market,
        "_twinmarket_test_matching_system",
        fake_matching,
    )

    result = inherited_market.advance_trading_day(
        current_date="2023-06-15",
        runtime_db=runtime,
        decision_json=decisions,
        log_dir=log_dir,
    )

    assert seen == {
        "current_date": "2023-06-15",
        "base_path": str(log_dir.resolve()),
        "db_path": str(runtime.resolve()),
        "json_file_path": str(decisions.resolve()),
    }
    assert result.inherited_function == "trader.matching_engine.test_matching_system"
    assert result.participant_data_used is False
    assert result.custom_market_logic_used is False


def test_non_trading_day_delegates_to_inherited_holiday_update(monkeypatch, tmp_path):
    runtime = _file(tmp_path, "runtime.db")
    seen = {}

    def fake_holiday(**kwargs):
        seen.update(kwargs)

    monkeypatch.setattr(
        inherited_market,
        "_twinmarket_update_profiles_table_holiday",
        fake_holiday,
    )

    result = inherited_market.advance_non_trading_day(
        current_date="2023-06-17",
        runtime_db=runtime,
    )

    assert seen == {
        "current_date": "2023-06-17",
        "db_path": str(runtime.resolve()),
    }
    assert (
        result.inherited_function
        == "trader.matching_engine.update_profiles_table_holiday"
    )


def test_protected_runtime_fails_before_inherited_mutation(monkeypatch, tmp_path):
    runtime = _file(tmp_path, "runtime.db")
    decisions = _file(tmp_path, "decisions.json", b"{}")
    called = False

    def fake_matching(**_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(
        inherited_market,
        "_twinmarket_test_matching_system",
        fake_matching,
    )

    try:
        inherited_market.advance_trading_day(
            current_date="2023-06-15",
            runtime_db=runtime,
            decision_json=decisions,
            log_dir=tmp_path / "logs",
            protected_paths=[runtime],
        )
    except ValueError as exc:
        assert "protected/frozen" in str(exc)
    else:
        raise AssertionError("protected runtime must fail closed")

    assert called is False


def test_runtime_hash_audit_detects_inherited_mutation(monkeypatch, tmp_path):
    runtime = _file(tmp_path, "runtime.db", b"before")
    decisions = _file(tmp_path, "decisions.json", b"{}")

    def fake_matching(**kwargs):
        Path(kwargs["db_path"]).write_bytes(b"after")

    monkeypatch.setattr(
        inherited_market,
        "_twinmarket_test_matching_system",
        fake_matching,
    )

    result = inherited_market.advance_trading_day(
        current_date="2023-06-15",
        runtime_db=runtime,
        decision_json=decisions,
        log_dir=tmp_path / "logs",
    )

    assert result.runtime_db_changed is True
    assert result.runtime_db_sha256_before != result.runtime_db_sha256_after

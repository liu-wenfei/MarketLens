from pathlib import Path

SCRIPT = Path("scripts/preflight/run_phase07_top_user_news_gate.py")


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_gate_uses_phase6_dynamic_graph_and_prominence():
    source = _source()
    assert "build_bounded_social_graph" in source
    assert "make_prominence_snapshot" in source
    assert "top_user_ids[0]" in source
    assert '["user_type"]' not in source
    assert '.get("user_type")' not in source
    assert "user_type =" not in source


def test_gate_delegates_to_phase7c_inherited_reasoning_path():
    source = _source()
    assert "execute_active_agents" in source
    assert '"simulation.process_user_input"' in source
    assert "from simulation import process_user_input" not in source


def test_gate_supplies_news_and_verifies_inherited_conversation_prompt():
    source = _source()
    assert "load_daily_news" in source
    assert "TradingPrompt.get_news_analysis_prompt" in source
    assert "conversation_records" in source
    assert '"top_user_direct_news_branch_exercised": True' in source


def test_gate_is_explicitly_forced_nonformal_and_does_not_advance_market():
    source = _source()
    assert "NOT NATURAL ACTIVATION OR FORMAL EXPERIMENT EVIDENCE" in source
    assert '"natural_phase4_activation_evidence": False' in source
    assert '"forced_branch_coverage": True' in source
    assert '"market_advance_executed": False' in source
    assert "advance_trading_day" not in source
    assert "test_matching_system" not in source


def test_gate_does_not_import_or_use_participant_runtime():
    source = _source().lower()
    assert "marketlens.human" not in source
    assert "participant_db" not in source
    assert '"participant_data_used": false' in source


def test_gate_requires_real_backend_and_explicit_acknowledgements():
    source = _source()
    assert "--execute-real-backend" in source
    assert "--acknowledge-forced-routing" in source
    assert "--acknowledge-non-formal" in source

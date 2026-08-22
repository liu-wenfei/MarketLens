from pathlib import Path


SCRIPT = Path("scripts/preflight/run_phase07_matched_trade_gate.py")


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_gate_delegates_through_marketlens_inherited_wrapper():
    source = _source()
    assert "from marketlens.market.runtime.inherited_market import" in source
    assert "advance_trading_day" in source
    assert "reset_agent_world" in source
    assert "from trader.matching_engine" not in source


def test_gate_does_not_import_participant_runtime():
    source = _source().lower()
    assert "marketlens.human" not in source
    assert "participant_db" not in source


def test_gate_is_explicitly_non_formal_and_zero_llm():
    source = _source()
    assert "NOT FORMAL EXPERIMENT EVIDENCE" in source
    assert '"llm_backend_used": False' in source
    assert '"natural_activation_evidence": False' in source


def test_controlled_fixture_is_balanced_and_fixed():
    source = _source()
    assert 'STOCK_ID = "CGEI"' in source
    assert 'BUYER_ID = "22543333014"' in source
    assert 'SELLER_ID = "25901251490"' in source
    assert "PRICE = 9.75" in source
    assert "QUANTITY = 100" in source

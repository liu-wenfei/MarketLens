from __future__ import annotations

import inspect
import sqlite3
from pathlib import Path

import networkx as nx
import pandas as pd
import pytest

from marketlens.market.runtime import full_chain


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "api.yaml"
    path.write_text("model_name: fake\n", encoding="utf-8")
    return path


def test_active_agents_receive_phase6_top_users_and_complete_daily_news(tmp_path: Path):
    calls = []
    graph = nx.Graph()
    graph.add_nodes_from(["a", "b", "c"])
    news = ["n1", "n2", "n3"]

    def fake_process(**kwargs):
        calls.append(kwargs)
        uid = kwargs["user_id"]
        return uid, {}, {"stock_decisions": {}}, {}

    strategy = pd.DataFrame(
        [
            {"user_id": "a", "strategy": "基本面"},
            {"user_id": "b", "strategy": "技术面"},
            {"user_id": "c", "strategy": "基本面"},
        ]
    )
    executions = full_chain.execute_active_agents(
        population_ids=("a", "b", "c"),
        active_agent_ids=("b", "c"),
        top_user_ids=("c",),
        graph=graph,
        news_items=news,
        working_user_db=tmp_path / "runtime.db",
        working_forum_db=tmp_path / "forum.db",
        df_stock=pd.DataFrame({"date": [pd.Timestamp("2023-06-14")]}),
        df_strategy=strategy,
        belief_args=pd.DataFrame(
            [
                {"user_id": "b", "belief": "x"},
                {"user_id": "c", "belief": "y"},
            ]
        ),
        current_date="2023-06-15",
        log_dir=tmp_path / "logs",
        config_path=_config(tmp_path),
        process_user_input_fn=fake_process,
    )

    assert [call["user_id"] for call in calls] == ["b", "c"]
    for call in calls:
        assert call["current_user_graph"] is graph
        assert call["import_news"] == news
        assert call["top_user"] == ["c"]
        assert call["day_1st"] is True
        assert call["is_trading_day"] is True
        assert call["prob_of_technical"] == 0.0
        assert call["activate_maapping"] == {"a": False, "b": True, "c": True}
        assert set(call["user_config_mapping"]) == {"a", "b", "c"}

    assert [item.user_id for item in executions] == ["b", "c"]
    assert executions[0].is_top_user is False
    assert executions[1].is_top_user is True
    assert all(item.completed_successfully for item in executions)


def test_reasoning_failure_stops_paid_batch_and_blocks_partial_market_input(tmp_path: Path):
    calls = []

    def fake_process(**kwargs):
        calls.append(kwargs["user_id"])
        raise RuntimeError("synthetic failure")

    executions = full_chain.execute_active_agents(
        population_ids=("a", "b", "c"),
        active_agent_ids=("b", "c"),
        top_user_ids=(),
        graph=nx.Graph(),
        news_items=["n"],
        working_user_db=tmp_path / "runtime.db",
        working_forum_db=tmp_path / "forum.db",
        df_stock=pd.DataFrame({"date": [pd.Timestamp("2023-06-14")]}),
        df_strategy=pd.DataFrame(
            [
                {"user_id": "a", "strategy": "基本面"},
                {"user_id": "b", "strategy": "基本面"},
                {"user_id": "c", "strategy": "技术面"},
            ]
        ),
        belief_args=pd.DataFrame(),
        current_date="2023-06-15",
        log_dir=tmp_path / "logs",
        config_path=_config(tmp_path),
        process_user_input_fn=fake_process,
    )

    assert calls == ["b"]
    assert executions[0].completed_successfully is False
    assert "synthetic failure" in executions[0].exception_error

    with pytest.raises(full_chain.Phase07FullChainError, match="full active batch"):
        full_chain.write_inherited_decision_json(
            path=tmp_path / "decisions.json",
            active_agent_ids=("b", "c"),
            executions=executions,
        )


def test_decision_json_keeps_inherited_user_to_decision_shape(tmp_path: Path):
    executions = (
        full_chain.Phase07AgentExecution(
            user_id="b",
            is_top_user=False,
            completed_successfully=True,
            returned_tuple_shape_ok=True,
            returned_user_id="b",
            inherited_error=None,
            decision_result_present=True,
            decision_result={"stock_decisions": {"CGEI": {"action": "hold"}}},
        ),
    )
    path = full_chain.write_inherited_decision_json(
        path=tmp_path / "decisions.json",
        active_agent_ids=("b",),
        executions=executions,
    )
    assert '"b"' in path.read_text(encoding="utf-8")
    assert '"stock_decisions"' in path.read_text(encoding="utf-8")


def test_post_market_validation_allows_zero_matched_trades(tmp_path: Path):
    db = tmp_path / "runtime.db"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            CREATE TABLE StockProfile (stock_id TEXT);
            CREATE TABLE StockData (stock_id TEXT, date TEXT);
            CREATE TABLE Profiles (user_id TEXT, created_at TEXT);
            CREATE TABLE TradingDetails (user_id TEXT, date_time TEXT);
            INSERT INTO StockProfile VALUES ('A');
            INSERT INTO StockProfile VALUES ('B');
            INSERT INTO StockData VALUES ('A', '2023-06-15');
            INSERT INTO StockData VALUES ('B', '2023-06-15');
            INSERT INTO Profiles VALUES ('u1', '2023-06-15 00:00:00');
            INSERT INTO Profiles VALUES ('u2', '2023-06-15 00:00:00');
            """
        )
        conn.commit()

    state = full_chain.inspect_runtime_day_state(db, current_date="2023-06-15")
    assert state["tradingdetails_rows_on_date"] == 0
    full_chain.validate_runtime_day_state(state, population_size=2)


def test_phase07c_contains_no_custom_market_mechanics():
    source = inspect.getsource(full_chain)
    forbidden = [
        "def calculate_closing_price",
        "def process_trading_day",
        "def generate_stock_data",
        "from trader.matching_engine import",
        "UPDATE StockData",
        "UPDATE Profiles",
        "INSERT INTO StockData",
        "INSERT INTO Profiles",
        "upper_limit =",
        "lower_limit =",
    ]
    for token in forbidden:
        assert token not in source


def test_phase07c_contains_no_participant_dependency():
    source = inspect.getsource(full_chain).lower()
    forbidden = [
        "from marketlens.human",
        "import marketlens.human",
        "participant_repository",
        "participant_service",
    ]
    for token in forbidden:
        assert token not in source

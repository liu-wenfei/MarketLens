import json
from pathlib import Path
import sqlite3

from marketlens.agents.population.fixture import BUNDLE_STATUS, build_population_bundle
from marketlens.agents.population.source import sha256_file


REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_DB = REPO_ROOT / "data" / "sys_1000.db"


def _count(connection, table):
    return connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]


def test_bundle_builds_exact_bounded_twinmarket_fixture_without_touching_source(tmp_path):
    source_hash_before = sha256_file(SOURCE_DB)
    output = tmp_path / "population"

    manifest = build_population_bundle(
        source_db=SOURCE_DB,
        population_size=20,
        seed="fixture-test",
        output_dir=output,
    )

    assert manifest["status"] == BUNDLE_STATUS
    assert manifest["scope"]["phase"] == "3B"
    assert manifest["selection"]["strategy_allocation"] == {"基本面": 8, "技术面": 12}
    assert manifest["selection"]["user_type_policy"].startswith("inherited")
    assert sha256_file(SOURCE_DB) == source_hash_before

    manifest_on_disk = json.loads(
        (output / "population_manifest.json").read_text(encoding="utf-8")
    )
    selected_ids = (
        output / "selected_agent_ids.txt"
    ).read_text(encoding="utf-8").splitlines()
    runtime_db = output / "population_runtime.db"

    assert manifest_on_disk["selection"]["selected_agent_ids"] == selected_ids
    assert manifest_on_disk["runtime_fixture"]["fixture_sha256"] == sha256_file(runtime_db)

    source = sqlite3.connect(SOURCE_DB)
    fixture = sqlite3.connect(runtime_db)
    try:
        assert _count(fixture, "Profiles") == 20
        assert _count(fixture, "Strategy") == 20
        assert _count(fixture, "StockProfile") == _count(source, "StockProfile")
        assert _count(fixture, "StockData") == _count(source, "StockData")

        fixture_ids = {
            str(row[0]) for row in fixture.execute("SELECT user_id FROM Profiles").fetchall()
        }
        assert fixture_ids == set(selected_ids)

        trade_ids = {
            str(row[0])
            for row in fixture.execute("SELECT DISTINCT user_id FROM TradingDetails").fetchall()
        }
        assert trade_ids <= set(selected_ids)
    finally:
        source.close()
        fixture.close()

    # Inherited TwinMarket population discovery sees exactly the bounded fixture
    # membership, so Phase 3B does not modify util/UserDB.py or simulation.py.
    from util.UserDB import get_all_user_ids

    assert set(get_all_user_ids(str(runtime_db))) == set(selected_ids)


def test_missing_user_type_is_reported_as_warning_not_repaired(tmp_path):
    output = tmp_path / "population"
    manifest = build_population_bundle(
        source_db=SOURCE_DB,
        population_size=1,
        seed="coverage-warning-test",
        output_dir=output,
    )

    coverage = manifest["selected_population"]["user_type_coverage"]
    assert sum(bool(value) for value in coverage.values()) == 1
    assert manifest["selected_population"]["coverage_warnings"]
    assert manifest["selection"]["population_size"] == 1

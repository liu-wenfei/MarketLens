from __future__ import annotations

import shutil
import sqlite3
from hashlib import sha256
from pathlib import Path

import pytest
import yaml

from marketlens.agents.population.fixture import build_population_bundle
from marketlens.episode.contract import load_execution_plan as load_v1_execution_plan
from marketlens.episode.contract_v2 import (
    EPISODE_IDS,
    EPISODE_POOL_ID,
    EXPECTED_EXECUTION_PLAN_SHA256,
    load_execution_plan,
)
from marketlens.episode.entity_names import (
    EXPECTED_ENTITY_REGISTRY_SHA256,
    forum_entity_glossary,
    load_entity_registry,
)
from marketlens.episode.language import (
    validate_english_forum_post,
    validate_forum_db_english_posts,
)
from marketlens.episode.producer_v2 import (
    PRODUCER_CONTRACT_SHA256,
    CanonicalEpisodeProducerError,
    dry_run_summary,
    execute_formal_episode_slot,
    load_producer_contract,
)
from trader.prompts import (
    TradingPrompt,
    current_forum_post_language,
    forum_post_language,
)

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
        "marketlens/episode/entity_name_registry_v2_1.json",
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


def test_default_inherited_prompt_mode_remains_chinese_and_v2_mode_is_scoped():
    assert current_forum_post_language() == "zh"
    inherited = TradingPrompt.get_intention_prompt("原有 belief")
    assert "MarketLens v2.2 forum-post language constraint" not in inherited
    assert sha256(inherited.encode("utf-8")).hexdigest() == (
        "8111c8837796b3f428d5717f4ef25e9537eb9bb49257613c9e428d348a92d0c9"
    )

    with forum_post_language("en"):
        assert current_forum_post_language() == "en"
        v2_prompt = TradingPrompt.get_intention_prompt("原有 belief")
        assert "MarketLens v2.2 forum-post language constraint" in v2_prompt
        assert "`post` 必须直接使用自然、完整的英文撰写，不得包含任何中文/CJK字符" in v2_prompt
        assert "`belief` 不受此英文约束影响" in v2_prompt
        assert "`post` 必须使用 YAML block scalar：`post: |-`" in v2_prompt
        assert "即使上文中的公司名、行业名、术语或短语是中文，也不得原样复制到 `post`" in v2_prompt
        assert "MarketLens v2.1 frozen entity-name glossary" in v2_prompt
        assert "SH601888 | 中国中免 => China Tourism Group Duty Free Corporation Limited" in v2_prompt
        assert "SH688981 | 中芯国际 => Semiconductor Manufacturing International Corporation" in v2_prompt
        assert "不得自行翻译、缩写、音译或创造另一种英文名称" in v2_prompt
        assert "在输出最终 YAML 前，请在同一次回答中检查 `post`" in v2_prompt
        assert "post: |-" in v2_prompt
        assert "post: 你的帖子内容" not in v2_prompt
        assert "明确说明帖子类型（type1/type2/type3）。" not in v2_prompt
        assert (
            "帖子类型必须且只能通过独立的 YAML `type` 字段声明（type1/type2/type3）"
            in v2_prompt
        )
        assert "`post` 正文只写帖子内容，不要写或重复 type1/type2/type3 标签" in v2_prompt

    assert current_forum_post_language() == "zh"



def test_v2_yaml_block_scalar_survives_natural_english_colons_without_repair_llm():
    payload = """post: |-
  I remain cautious: valuations are elevated, but the trend is improving.
type: type3
belief: 我仍然保持谨慎，并继续观察市场。
"""
    parsed = yaml.safe_load(payload)
    assert parsed["post"] == (
        "I remain cautious: valuations are elevated, but the trend is improving."
    )
    assert parsed["type"] == "type3"
    assert parsed["belief"] == "我仍然保持谨慎，并继续观察市场。"


def test_v2_raw_formal_evidence_namespace_is_git_ignored_but_ignore_file_is_tracked():
    ignore_file = REPO_ROOT / "artifacts/formal/canonical_episode_v2/.gitignore"
    assert ignore_file.read_text(encoding="utf-8") == "*\n!.gitignore\n"

def test_forum_post_language_context_rejects_unknown_mode():
    with pytest.raises(ValueError, match="unsupported forum post language"):
        with forum_post_language("fr"):
            pass


def test_deterministic_english_post_gate_accepts_english_and_rejects_cjk():
    good = validate_english_forum_post(
        "I remain cautious on transport stocks after today's market update."
    )
    assert good["complete"] is True

    bad = validate_english_forum_post("I remain cautious, 但我还会继续观察市场。")
    assert bad["complete"] is False
    assert "contains_cjk_character" in bad["violations"]




def test_deterministic_english_post_gate_rejects_type_prefix_in_post():
    bad = validate_english_forum_post(
        "type2: I trimmed FSEI and kept TSEI unchanged today."
    )
    assert bad["complete"] is False
    assert "type_prefix_in_post" in bad["violations"]


def test_deterministic_english_post_gate_accepts_ticker_instead_of_chinese_entity_name():
    good = validate_english_forum_post(
        "I am watching TSEI closely and using SH601888 only as the component ticker."
    )
    assert good["complete"] is True


def test_forum_db_language_gate_is_read_only_and_checks_all_stored_posts(tmp_path: Path):
    db = tmp_path / "forum.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE posts (id INTEGER PRIMARY KEY, user_id TEXT, content TEXT, created_at TEXT)"
        )
        conn.executemany(
            "INSERT INTO posts VALUES (?, ?, ?, ?)",
            [
                (1, "u1", "English market view with MEI and TTEI.", "2023-06-19"),
                (2, "u2", "Mixed English 和中文。", "2023-06-20"),
            ],
        )
    before = db.read_bytes()
    result = validate_forum_db_english_posts(db)
    after = db.read_bytes()
    assert result["complete"] is False
    assert result["posts_checked"] == 2
    assert result["invalid_post_count"] == 1
    assert result["invalid_posts"][0]["post_id"] == "2"
    assert before == after


def test_v2_plan_preserves_v1_world_population_activation_and_days_exactly():
    v1 = load_v1_execution_plan()
    v2 = load_execution_plan()
    assert v2["episode_pool"]["pool_id"] == EPISODE_POOL_ID
    assert tuple(v2["episode_pool"]["episode_ids"]) == EPISODE_IDS
    assert v2["population"] == v1["population"]
    assert v2["activation"] == v1["activation"]
    assert v2["world"] == v1["world"]
    assert v2["days"] == v1["days"]
    assert v2["protocol_version"] == v1["protocol_version"] == "1.1"
    assert v2["plan_version"] == "2.2"
    assert v2["v2_forum_output"]["intervention_scope"] == "final_agent_forum_post_field_only"
    assert v2["v2_forum_output"]["live_translation_used"] is False
    assert EXPECTED_EXECUTION_PLAN_SHA256 == "dfd0b2f2cca6dd61639425ac19dedd9f508d730359d9834da507cf3823698565"


def test_v2_producer_contract_is_zero_llm_by_default_and_language_gate_is_predeclared():
    contract = load_producer_contract()
    assert PRODUCER_CONTRACT_SHA256 == "7ea0697cd13a5c8ce1c54a781797325b6edebcdc2c2b3c232386150317b67d22"
    assert contract["episode_pool_id"] == EPISODE_POOL_ID
    assert contract["contract_version"] == "2.2"
    assert contract["episode_ids"] == list(EPISODE_IDS)
    assert contract["execution_controls"]["default_mode"] == "dry_run_zero_llm"
    assert contract["execution_controls"]["full_pool_execute_command_allowed"] is False
    assert contract["technical_acceptance"]["forum_post_language_complete"] is True
    assert contract["forum_output_contract"]["live_translation_used"] is False
    assert contract["forum_output_contract"]["agent_reasoning_pipeline_rewritten"] is False
    gate = contract["forum_output_contract"]["deterministic_language_gate"]
    assert gate["type_prefix_allowed_in_post"] is False
    assert contract["forum_output_contract"]["chinese_source_terms_may_be_copied_into_post"] is False
    assert contract["forum_output_contract"]["post_type_declaration_policy"] == "yaml_type_field_only"
    assert contract["forum_output_contract"]["inherited_type_instruction_clarified_in_v2_prompt"] is True
    registry_contract = contract["forum_output_contract"]["entity_name_registry"]
    assert registry_contract["sha256"] == EXPECTED_ENTITY_REGISTRY_SHA256
    assert registry_contract["known_entity_policy"] == "exact_canonical_english_display_or_stable_code"
    assert registry_contract["unknown_entity_fallback"] == "ticker_or_index_code"
    assert registry_contract["free_model_translation_or_transliteration"] is False
    assert registry_contract["post_generation_entity_rewriting"] is False



def test_v21_frozen_entity_registry_is_complete_unique_and_time_anchored():
    registry = load_entity_registry()
    assert registry["registry_id"] == "marketlens-entity-name-registry-v2.1"
    assert registry["registry_version"] == "2.1"
    assert registry["status"] == "formal_v2_entity_name_registry_frozen"
    assert registry["simulation_reference_date"] == "2023-06-15"
    assert registry["counts"] == {
        "sectors": 10,
        "indices": 10,
        "companies": 50,
        "total_entities": 70,
    }
    keys = [item["canonical_key"] for item in registry["entities"]]
    assert len(keys) == len(set(keys)) == 70


def test_v21_frozen_entity_registry_covers_source_constituents_exactly():
    import csv
    import re

    registry = load_entity_registry()
    mapped = {
        item["canonical_key"]: item["source_zh"]
        for item in registry["entities"]
        if item["entity_type"] == "company"
    }
    source: dict[str, str] = {}
    pattern = re.compile(r"(?:包括)?([^、，]+?)\((SH\d+),\s*权重[0-9.]+%\)")
    with (REPO_ROOT / "data/stock_profile.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            for source_zh, code in pattern.findall(row["description"]):
                source[code] = source_zh.strip()
    assert source == mapped


def test_v21_entity_glossary_uses_canonical_2023_names_and_no_free_translation_policy():
    registry = load_entity_registry()
    by_key = {item["canonical_key"]: item for item in registry["entities"]}
    assert by_key["SH603501"]["canonical_display_en"] == "Will Semiconductor Co., Ltd. Shanghai"
    assert by_key["SH603986"]["canonical_display_en"] == "GigaDevice Semiconductor (Beijing) Inc."
    assert by_key["SH601888"]["canonical_display_en"] == "China Tourism Group Duty Free Corporation Limited"
    assert registry["policy"]["free_model_translation_or_transliteration"] is False
    assert registry["policy"]["post_generation_entity_rewriting"] is False
    glossary = forum_entity_glossary()
    assert "TSEI | 旅游与服务指数 => Tourism & Services Index" in glossary
    assert "SH601888 | 中国中免 => China Tourism Group Duty Free Corporation Limited" in glossary


def test_v2_dry_run_is_zero_llm_and_does_not_write_v2_formal_assets(tmp_path: Path):
    root = _copy_required_repo_inputs(tmp_path)
    summary = dry_run_summary(repo_root=root)
    assert summary["status"] == "READY / ZERO-LLM / NO FORMAL EPISODE MUTATION"
    assert summary["llm_api_calls"] == 0
    assert summary["formal_execution_performed"] is False
    assert summary["episode_pool_id"] == EPISODE_POOL_ID
    assert summary["world_ticks_per_episode"] == 27
    assert summary["agent_pipeline_executions_per_episode"] == 193
    assert summary["forum_output_contract"]["participant_visible_agent_forum_language"] == "English"
    assert summary["entity_name_registry"]["sha256"] == EXPECTED_ENTITY_REGISTRY_SHA256
    assert summary["entity_name_registry"]["counts"]["companies"] == 50
    assert not (root / "data/marketlens/canonical_episode/v2").exists()


def test_v2_paid_execution_requires_explicit_acknowledgement_before_any_backend_use():
    with pytest.raises(CanonicalEpisodeProducerError, match="explicit acknowledgement"):
        execute_formal_episode_slot(
            repo_root=REPO_ROOT,
            episode_id=EPISODE_IDS[0],
            acknowledge_formal_execution=False,
        )

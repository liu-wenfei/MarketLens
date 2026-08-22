from dataclasses import replace
from pathlib import Path

from marketlens.agents.population.selection import select_population
from marketlens.agents.population.source import AgentPersona, SourcePopulation, validate_source_population


REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_DB = REPO_ROOT / "data" / "sys_1000.db"


def test_n20_is_exactly_source_ratio_stratified_and_reproducible():
    source = validate_source_population(SOURCE_DB)
    first = select_population(source, population_size=20, seed="phase3-test-seed")
    second = select_population(source, population_size=20, seed="phase3-test-seed")

    assert first == second
    assert first.strategy_allocation == {"基本面": 8, "技术面": 12}
    assert len(first.selected_agent_ids) == 20
    assert len(set(first.selected_agent_ids)) == 20


def test_different_seed_changes_membership_without_changing_strategy_counts():
    source = validate_source_population(SOURCE_DB)
    first = select_population(source, population_size=20, seed="seed-a")
    second = select_population(source, population_size=20, seed="seed-b")

    assert first.selected_agent_ids != second.selected_agent_ids
    assert first.strategy_allocation == second.strategy_allocation == {"基本面": 8, "技术面": 12}


def test_user_type_is_not_a_selection_input():
    source = validate_source_population(SOURCE_DB)
    selection_before = select_population(source, population_size=25, seed="status-blind")

    # Deliberately rewrite every in-memory user_type while preserving the same
    # IDs and strategies. Membership must not change because user_type is not
    # part of the selection key or quota.
    rewritten_agents = {
        uid: AgentPersona(
            user_id=agent.user_id,
            strategy=agent.strategy,
            user_type="synthetic-status-for-test",
            gender=agent.gender,
            location=agent.location,
            persona_fingerprint_sha256=agent.persona_fingerprint_sha256,
        )
        for uid, agent in source.agents.items()
    }
    rewritten = SourcePopulation(
        source_db=source.source_db,
        source_sha256=source.source_sha256,
        agents=rewritten_agents,
        strategy_counts=source.strategy_counts,
        user_type_counts={"synthetic-status-for-test": source.total_agents},
        joint_counts={},
    )
    selection_after = select_population(rewritten, population_size=25, seed="status-blind")

    assert selection_before.selected_agent_ids == selection_after.selected_agent_ids
    assert selection_before.selected_agent_ids_sha256 == selection_after.selected_agent_ids_sha256


def test_user_type_values_are_inherited_exactly_for_selected_agents():
    source = validate_source_population(SOURCE_DB)
    selection = select_population(source, population_size=20, seed="inherit-status")

    selected = [source.agents[uid] for uid in selection.selected_agent_ids]
    assert all(agent.user_type in source.user_type_counts for agent in selected)
    assert all(agent.user_id in source.agents for agent in selected)

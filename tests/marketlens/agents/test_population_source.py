from pathlib import Path

import pytest

from marketlens.agents.population.source import (
    FUNDAMENTAL_LABEL,
    TECHNICAL_LABEL,
    PopulationSourceError,
    sha256_file,
    validate_source_population,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_DB = REPO_ROOT / "data" / "sys_1000.db"


def test_inherited_source_population_matches_audited_structure():
    before = sha256_file(SOURCE_DB)
    population = validate_source_population(SOURCE_DB)
    after = sha256_file(SOURCE_DB)

    assert population.total_agents == 1000
    assert population.strategy_counts == {
        FUNDAMENTAL_LABEL: 400,
        TECHNICAL_LABEL: 600,
    }
    assert population.user_type_counts == {
        "大V": 11,
        "小博主": 77,
        "普通股民": 912,
    }
    assert sum(sum(row.values()) for row in population.joint_counts.values()) == 1000
    assert before == after == population.source_sha256


def test_read_only_validator_rejects_profile_strategy_disagreement(tmp_path):
    import shutil
    import sqlite3

    broken = tmp_path / "broken.db"
    shutil.copy2(SOURCE_DB, broken)
    connection = sqlite3.connect(broken)
    try:
        user_id = connection.execute("SELECT user_id FROM Profiles LIMIT 1").fetchone()[0]
        strategy = connection.execute(
            'SELECT strategy FROM "Strategy" WHERE CAST(user_id AS TEXT)=?',
            (str(user_id),),
        ).fetchone()[0]
        replacement = TECHNICAL_LABEL if strategy == FUNDAMENTAL_LABEL else FUNDAMENTAL_LABEL
        connection.execute(
            "UPDATE Profiles SET strategy=? WHERE CAST(user_id AS TEXT)=?",
            (replacement, str(user_id)),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(PopulationSourceError, match="strategy disagreement"):
        validate_source_population(broken)

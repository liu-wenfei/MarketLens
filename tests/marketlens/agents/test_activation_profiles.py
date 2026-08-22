from __future__ import annotations

import hashlib
import sqlite3

import pytest

from marketlens.agents.activation.profiles import (
    ActivationProfileError,
    load_activation_profiles,
)


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_runtime_profile_loader_reads_only_activation_fields_and_is_read_only(tmp_path):
    db = tmp_path / "runtime.db"
    con = sqlite3.connect(db)
    con.execute(
        """CREATE TABLE Profiles (
            user_id TEXT,
            trade_count_category TEXT,
            user_type TEXT,
            strategy TEXT,
            trad_pro REAL
        )"""
    )
    con.executemany(
        "INSERT INTO Profiles VALUES (?, ?, ?, ?, ?)",
        [
            ("2", "高", "大V", "基本面", 0.0),
            ("1", "低", "普通股民", "技术面", 0.0),
        ],
    )
    con.commit()
    con.close()
    before = _sha256(db)

    profiles = load_activation_profiles(db)

    assert [(p.user_id, p.activity_category) for p in profiles] == [
        ("1", "低"),
        ("2", "高"),
    ]
    assert not hasattr(profiles[0], "user_type")
    assert not hasattr(profiles[0], "strategy")
    assert _sha256(db) == before


def test_runtime_profile_loader_rejects_unknown_activity_category(tmp_path):
    db = tmp_path / "runtime.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE Profiles (user_id TEXT, trade_count_category TEXT)")
    con.execute("INSERT INTO Profiles VALUES ('1', 'very-active')")
    con.commit()
    con.close()

    with pytest.raises(ActivationProfileError, match="unsupported trade_count_category"):
        load_activation_profiles(db)

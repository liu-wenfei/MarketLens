from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from marketlens.market.runtime.news import load_daily_news, load_trading_day_set


def test_daily_news_preserves_complete_list_and_order(tmp_path: Path):
    path = tmp_path / "news.pkl"
    expected = ["item A", "item B", "item C"]
    pd.DataFrame(
        [{"cal_date": "2023-06-15", "news": expected}]
    ).to_pickle(path)

    actual = load_daily_news(path, current_date="2023-06-15")

    assert actual == expected
    assert actual is not expected


def test_daily_news_does_not_split_or_summarise_string(tmp_path: Path):
    path = tmp_path / "news.pkl"
    pd.DataFrame(
        [{"cal_date": "2023-06-15", "news": "one inherited news item"}]
    ).to_pickle(path)

    assert load_daily_news(path, current_date="2023-06-15") == [
        "one inherited news item"
    ]


def test_missing_news_date_fails_closed(tmp_path: Path):
    path = tmp_path / "news.pkl"
    pd.DataFrame(
        [{"cal_date": "2023-06-14", "news": ["old"]}]
    ).to_pickle(path)

    with pytest.raises(ValueError, match="no row"):
        load_daily_news(path, current_date="2023-06-15")


def test_duplicate_news_date_fails_closed(tmp_path: Path):
    path = tmp_path / "news.pkl"
    pd.DataFrame(
        [
            {"cal_date": "2023-06-15", "news": ["a"]},
            {"cal_date": "2023-06-15", "news": ["b"]},
        ]
    ).to_pickle(path)

    with pytest.raises(ValueError, match="exactly one row"):
        load_daily_news(path, current_date="2023-06-15")


def test_trading_calendar_uses_inherited_pretrade_date_column(tmp_path: Path):
    path = tmp_path / "trading_days.csv"
    pd.DataFrame(
        {"pretrade_date": ["2023-06-15", "2023-06-16"]}
    ).to_csv(path, index=False)

    assert load_trading_day_set(path) == frozenset(
        {"2023-06-15", "2023-06-16"}
    )

from marketlens.experiment.long_horizon_design import (
    LONG_HORIZON_DECISION_DAY_CANDIDATES,
    build_long_horizon_candidates,
)


OPEN_DATES = (
    "2023-06-19", "2023-06-20", "2023-06-21", "2023-06-26", "2023-06-27",
    "2023-06-28", "2023-06-29", "2023-06-30", "2023-07-03", "2023-07-04",
    "2023-07-05", "2023-07-06", "2023-07-07", "2023-07-10", "2023-07-11",
    "2023-07-12", "2023-07-13",
)

NEWS_DATES = {
    f"2023-06-{day:02d}" for day in range(15, 31)
} | {
    f"2023-07-{day:02d}" for day in range(1, 14)
}


def _rows():
    return {
        row.decision_days: row
        for row in build_long_horizon_candidates(
            initialization_date="2023-06-15",
            visible_start_date="2023-06-19",
            open_dates=OPEN_DATES,
            news_dates=NEWS_DATES,
        )
    }


def test_candidate_counts_map_to_5_6_7_8_open_transitions():
    assert LONG_HORIZON_DECISION_DAY_CANDIDATES == (11, 13, 15, 17)
    rows = _rows()
    assert rows[11].open_transitions_per_phase == 5
    assert rows[13].open_transitions_per_phase == 6
    assert rows[15].open_transitions_per_phase == 7
    assert rows[17].open_transitions_per_phase == 8
    assert rows[11].intermediate_points_per_phase == 4
    assert rows[13].intermediate_points_per_phase == 5
    assert rows[15].intermediate_points_per_phase == 6
    assert rows[17].intermediate_points_per_phase == 7


def test_exact_dates_and_world_horizons_are_deterministic():
    rows = _rows()
    assert (rows[11].correction_date, rows[11].end_date, rows[11].world_ticks) == (
        "2023-06-28", "2023-07-05", 21
    )
    assert (rows[13].correction_date, rows[13].end_date, rows[13].world_ticks) == (
        "2023-06-29", "2023-07-07", 23
    )
    assert (rows[15].correction_date, rows[15].end_date, rows[15].world_ticks) == (
        "2023-06-30", "2023-07-11", 27
    )
    assert (rows[17].correction_date, rows[17].end_date, rows[17].world_ticks) == (
        "2023-07-03", "2023-07-13", 29
    )


def test_calendar_span_and_closed_ticks_are_explicit():
    rows = _rows()
    assert (
        rows[11].misinformation_to_correction_calendar_days,
        rows[11].correction_to_later_calendar_days,
        rows[11].visible_calendar_days_inclusive,
        rows[11].phase1_closed_ticks,
        rows[11].phase2_closed_ticks,
    ) == (9, 7, 17, 4, 2)
    assert (
        rows[13].misinformation_to_correction_calendar_days,
        rows[13].correction_to_later_calendar_days,
        rows[13].visible_calendar_days_inclusive,
        rows[13].phase1_closed_ticks,
        rows[13].phase2_closed_ticks,
    ) == (10, 8, 19, 4, 2)
    assert (
        rows[15].misinformation_to_correction_calendar_days,
        rows[15].correction_to_later_calendar_days,
        rows[15].visible_calendar_days_inclusive,
        rows[15].phase1_closed_ticks,
        rows[15].phase2_closed_ticks,
    ) == (11, 11, 23, 4, 4)
    assert (
        rows[17].misinformation_to_correction_calendar_days,
        rows[17].correction_to_later_calendar_days,
        rows[17].visible_calendar_days_inclusive,
        rows[17].phase1_closed_ticks,
        rows[17].phase2_closed_ticks,
    ) == (14, 10, 25, 6, 2)
    assert all(row.news_coverage_complete for row in rows.values())


def test_decisions_cover_every_open_state_and_burden_proxy_is_monotonic():
    rows = _rows()
    for count in LONG_HORIZON_DECISION_DAY_CANDIDATES:
        assert len(rows[count].decision_dates) == count
        assert rows[count].participant_response_events == count + 5
    assert [rows[count].participant_response_events for count in LONG_HORIZON_DECISION_DAY_CANDIDATES] == [16, 18, 20, 22]

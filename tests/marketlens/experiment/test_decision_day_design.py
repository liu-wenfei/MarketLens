from marketlens.experiment.decision_day_design import (
    DECISION_DAY_CANDIDATES,
    build_cadence_candidates,
    build_dynamic_horizon_candidates,
    evenly_spaced_indices,
)


OPEN_11 = (
    "2023-06-19", "2023-06-20", "2023-06-21", "2023-06-26", "2023-06-27",
    "2023-06-28", "2023-06-29", "2023-06-30", "2023-07-03", "2023-07-04", "2023-07-05",
)


def test_even_spacing_is_deterministic_for_requested_counts():
    assert DECISION_DAY_CANDIDATES == (0, 2, 4, 7, 9, 11)
    assert evenly_spaced_indices(11, 0) == ()
    assert evenly_spaced_indices(11, 2) == (0, 10)
    assert evenly_spaced_indices(11, 4) == (0, 3, 7, 10)
    assert evenly_spaced_indices(11, 7) == (0, 2, 3, 5, 7, 8, 10)
    assert evenly_spaced_indices(11, 9) == (0, 1, 2, 4, 5, 6, 8, 9, 10)
    assert evenly_spaced_indices(11, 11) == tuple(range(11))


def test_cadence_candidates_expose_structural_difference():
    rows = {row.decision_days: row for row in build_cadence_candidates(OPEN_11)}
    assert rows[0].resolution_class == "judgement_only_no_behaviour"
    assert rows[2].formal_anchor_coverage == 2
    assert rows[4].correction_anchor_included is False
    assert rows[4].phase1_intermediate_points == 1
    assert rows[4].phase2_intermediate_points == 1

    assert rows[7].formal_anchor_coverage == 3
    assert rows[7].phase1_intermediate_points == 2
    assert rows[7].phase2_intermediate_points == 2
    assert rows[7].resolution_class == "minimum_symmetric_dynamic_behaviour"

    assert rows[9].phase1_intermediate_points == 3
    assert rows[9].phase2_intermediate_points == 3
    assert rows[9].resolution_class == "high_resolution_dynamic_behaviour"

    assert rows[11].unobserved_open_states == 0
    assert rows[11].resolution_class == "complete_open_state_behaviour"


def test_dynamic_family_maps_7_9_11_to_3_4_5_open_transitions():
    news_dates = {
        f"2023-06-{day:02d}" for day in range(15, 31)
    } | {f"2023-07-{day:02d}" for day in range(1, 6)}
    rows = {
        row.decision_days: row
        for row in build_dynamic_horizon_candidates(
            initialization_date="2023-06-15",
            visible_start_date="2023-06-19",
            open_dates=OPEN_11,
            news_dates=news_dates,
        )
    }
    assert rows[7].open_transitions_per_phase == 3
    assert rows[7].intermediate_points_per_phase == 2
    assert rows[7].correction_date == "2023-06-26"
    assert rows[7].end_date == "2023-06-29"
    assert rows[7].world_ticks == 15

    assert rows[9].open_transitions_per_phase == 4
    assert rows[9].intermediate_points_per_phase == 3
    assert rows[9].correction_date == "2023-06-27"
    assert rows[9].end_date == "2023-07-03"
    assert rows[9].world_ticks == 19

    assert rows[11].open_transitions_per_phase == 5
    assert rows[11].intermediate_points_per_phase == 4
    assert rows[11].correction_date == "2023-06-28"
    assert rows[11].end_date == "2023-07-05"
    assert rows[11].world_ticks == 21

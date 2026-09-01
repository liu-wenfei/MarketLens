from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from marketlens.human.schemas import (
    ParticipantFeedbackContinueCreate,
    ParticipantFeedbackContinueRead,
    ParticipantFeedbackRead,
)
from marketlens.human.services.feedback_delivery_service import (
    ParticipantFeedbackConflictError,
    ParticipantFeedbackNotPreparedError,
    ParticipantFeedbackStateError,
)
from marketlens.human.services.session_service import (
    SessionNotFoundError,
)


router = APIRouter()


def _participant_reflection_stage(
    *,
    feedback_kind: str,
    statistics: object,
) -> str:
    if not isinstance(statistics, dict):
        raise ParticipantFeedbackConflictError(
            "prepared feedback statistics are invalid"
        )

    window = statistics.get("window")
    if not isinstance(window, dict):
        raise ParticipantFeedbackConflictError(
            "prepared feedback window is missing"
        )

    start = window.get("start_period")
    end = window.get("end_period")

    if feedback_kind == "final_session_summary":
        if (start, end) != (1, 15):
            raise ParticipantFeedbackConflictError(
                "final feedback window is inconsistent"
            )
        return "final"

    if feedback_kind != "multi_period_decision_feedback":
        raise ParticipantFeedbackConflictError(
            "unsupported participant feedback kind"
        )

    if (start, end) == (1, 4):
        return "early"

    if (start, end) == (5, 11):
        return "mid_session"

    raise ParticipantFeedbackConflictError(
        "multi-period feedback window is inconsistent"
    )


def _statistics_group(
    statistics: dict[str, object],
    key: str,
) -> dict[str, object]:
    value = statistics.get(key)
    if not isinstance(value, dict):
        raise ParticipantFeedbackConflictError(
            f"prepared feedback statistics missing {key}"
        )
    return value


def _select_metrics(
    source: dict[str, object],
    names: tuple[str, ...],
) -> dict[str, object]:
    selected: dict[str, object] = {}
    for name in names:
        if name not in source:
            raise ParticipantFeedbackConflictError(
                f"prepared feedback metric missing {name}"
            )
        selected[name] = source[name]
    return selected


def _participant_statistics_projection(
    *,
    reflection_stage: str,
    statistics: object,
) -> dict[str, object]:
    if not isinstance(statistics, dict):
        raise ParticipantFeedbackConflictError(
            "prepared feedback statistics are invalid"
        )

    window = _statistics_group(statistics, "window")
    judgement = _statistics_group(
        statistics,
        "judgement_metrics",
    )
    confidence = _statistics_group(
        statistics,
        "confidence_metrics",
    )
    trading = _statistics_group(
        statistics,
        "trading_metrics",
    )

    projected: dict[str, object] = {
        "window": _select_metrics(
            window,
            (
                "start_period",
                "end_period",
                "periods_reviewed",
            ),
        ),
        "judgement_metrics": _select_metrics(
            judgement,
            (
                "first_assessment",
                "latest_assessment",
                "revision_count",
            ),
        ),
    }

    if reflection_stage == "early":
        projected["confidence_metrics"] = _select_metrics(
            confidence,
            (
                "first",
                "latest",
                "change_points",
            ),
        )
        projected["trading_metrics"] = _select_metrics(
            trading,
            (
                "trade_periods",
                "no_trade_periods",
                "transaction_count",
            ),
        )
        return projected

    if reflection_stage in {"mid_session", "final"}:
        projected["confidence_metrics"] = _select_metrics(
            confidence,
            (
                "first",
                "latest",
                "change_points",
                "mean",
                "minimum",
                "maximum",
            ),
        )
        projected["trading_metrics"] = _select_metrics(
            trading,
            (
                "eligible_periods",
                "trade_periods",
                "no_trade_periods",
                "transaction_count",
                "buy_actions",
                "sell_actions",
                "trading_activity_pct",
            ),
        )

        portfolio = _statistics_group(
            statistics,
            "portfolio_metrics",
        )
        projected["portfolio_metrics"] = _select_metrics(
            portfolio,
            (
                "starting_value",
                "ending_value",
                "absolute_change",
                "change_pct",
            ),
        )

        information = _statistics_group(
            statistics,
            "information_metrics",
        )
        reported_evidence = _statistics_group(
            information,
            "participant_reported_evidence",
        )
        projected["reported_evidence_metrics"] = (
            _select_metrics(
                reported_evidence,
                (
                    "total_selections",
                    "assessments_with_evidence",
                    "unique_reported_sources",
                    "repeated_selections",
                    "evidence_set_changes",
                ),
            )
        )

        if reflection_stage == "final":
            projected["trading_metrics"][
                "gross_executed_notional"
            ] = _select_metrics(
                trading,
                ("gross_executed_notional",),
            )["gross_executed_notional"]

            if "final_only_metrics" in statistics:
                final_only = _statistics_group(
                    statistics,
                    "final_only_metrics",
                )
                projected["final_only_metrics"] = dict(
                    final_only
                )

        return projected

    raise ParticipantFeedbackConflictError(
        "unsupported participant reflection stage"
    )


def _runtime(request: Request):
    runtime = getattr(
        request.app.state,
        "participant_runtime",
        None,
    )
    if runtime is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Participant runtime is not configured",
        )
    return runtime


@router.get(
    "/session/{session_id}/feedback/current",
    response_model=ParticipantFeedbackRead,
)
def get_current_feedback(
    session_id: str,
    request: Request,
) -> ParticipantFeedbackRead:
    runtime = _runtime(request)

    try:
        feedback = runtime.feedback.get_current(
            session_id
        )
        reflection_stage = _participant_reflection_stage(
            feedback_kind=feedback.feedback_kind,
            statistics=feedback.statistics,
        )
        participant_statistics = (
            _participant_statistics_projection(
                reflection_stage=reflection_stage,
                statistics=feedback.statistics,
            )
        )
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Unknown session",
        ) from exc
    except (
        ParticipantFeedbackStateError,
        ParticipantFeedbackNotPreparedError,
        ParticipantFeedbackConflictError,
    ) as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return ParticipantFeedbackRead(
        feedback_kind=feedback.feedback_kind,
        reflection_stage=reflection_stage,
        statistics=participant_statistics,
        reflection=feedback.reflection,
    )


@router.post(
    "/session/{session_id}/feedback/current/continue",
    response_model=ParticipantFeedbackContinueRead,
)
def continue_current_feedback(
    session_id: str,
    payload: ParticipantFeedbackContinueCreate,
    request: Request,
) -> ParticipantFeedbackContinueRead:
    runtime = _runtime(request)

    try:
        continued = runtime.feedback.continue_current(
            session_id,
            payload.request_id,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Unknown session",
        ) from exc
    except (
        ParticipantFeedbackStateError,
        ParticipantFeedbackNotPreparedError,
        ParticipantFeedbackConflictError,
    ) as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return ParticipantFeedbackContinueRead(
        continued=continued
    )

"""Participant-safe canonical market overview projection.

This service is read-only. It never advances the participant session,
changes a portfolio, invokes TwinMarket matching, or exposes future
canonical market state.

The participant chart contains a fixed common pre-experiment historical
price context plus participant-visible experiment checkpoints. Historical
context is observational only and remains separate from experimental
checkpoint history and portfolio/feedback calculations.
"""
from __future__ import annotations

from datetime import date, timedelta

from marketlens.human.participant_asset_labels import (
    participant_asset_display_name,
    participant_asset_short_name,
    validate_participant_asset_labels,
)


from math import isfinite
from typing import Mapping

from marketlens.human.orchestration import ParticipantStage
from marketlens.human.schemas import (
    ParticipantHistoricalMarketPricePointRead,
    ParticipantMarketAssetRead,
    ParticipantMarketOverviewRead,
    ParticipantMarketPricePointRead,
)
from marketlens.market.price_provider import PriceNotFoundError
from marketlens.market.status import TradingCalendarError


HISTORICAL_PRICE_CONTEXT_VERSION = (
    "marketlens-historical-price-context-v1"
)
HISTORICAL_PRICE_CONTEXT_START = date(
    2023,
    1,
    3,
)
HISTORICAL_PRICE_CONTEXT_END = date(
    2023,
    6,
    14,
)
HISTORICAL_PRICE_CONTEXT_EXPECTED_POINTS = 108


class ParticipantMarketOverviewUnavailableError(ValueError):
    pass


class ParticipantMarketOverviewInvariantError(ValueError):
    pass


class ParticipantMarketOverviewService:
    def __init__(
        self,
        *,
        context: object,
        orchestration: object,
        assets: object,
        price_providers: Mapping[str, object],
        calendar: object,
    ):
        self.context = context
        self.orchestration = orchestration
        self.assets = assets
        self.price_providers = dict(price_providers)
        self.calendar = calendar

    def _historical_price_dates(
        self,
    ) -> tuple[str, ...]:
        """Resolve the frozen common market-close dates from the calendar."""

        resolved_dates: list[str] = []
        seen: set[str] = set()

        cursor = (
            HISTORICAL_PRICE_CONTEXT_START
        )

        while (
            cursor
            <= HISTORICAL_PRICE_CONTEXT_END
        ):
            try:
                market = self.calendar.status(
                    cursor.isoformat()
                )
            except TradingCalendarError as exc:
                raise ParticipantMarketOverviewUnavailableError(
                    str(exc)
                ) from exc

            raw_price_date = (
                None
                if market.market_state_date is None
                else str(
                    market.market_state_date
                )
            )

            if raw_price_date:
                try:
                    price_date = (
                        date.fromisoformat(
                            raw_price_date
                        )
                    )
                except ValueError as exc:
                    raise ParticipantMarketOverviewInvariantError(
                        "historical market-state date "
                        "is malformed"
                    ) from exc

                if price_date > cursor:
                    raise ParticipantMarketOverviewInvariantError(
                        "historical market-state date "
                        "cannot point into the future"
                    )

                if (
                    HISTORICAL_PRICE_CONTEXT_START
                    <= price_date
                    <= HISTORICAL_PRICE_CONTEXT_END
                    and raw_price_date not in seen
                ):
                    seen.add(
                        raw_price_date
                    )
                    resolved_dates.append(
                        raw_price_date
                    )

            cursor += timedelta(
                days=1
            )

        expected = (
            HISTORICAL_PRICE_CONTEXT_EXPECTED_POINTS
        )

        if len(resolved_dates) != expected:
            raise ParticipantMarketOverviewInvariantError(
                "frozen historical price context "
                f"expected {expected} market closes "
                f"but resolved {len(resolved_dates)}"
            )

        if (
            resolved_dates[0]
            != HISTORICAL_PRICE_CONTEXT_START.isoformat()
            or resolved_dates[-1]
            != HISTORICAL_PRICE_CONTEXT_END.isoformat()
        ):
            raise ParticipantMarketOverviewInvariantError(
                "frozen historical price context "
                "has unexpected date boundaries"
            )

        if (
            "2023-06-15" in seen
            or "2023-06-16" in seen
        ):
            raise ParticipantMarketOverviewInvariantError(
                "episode-specific pre-roll dates "
                "must not enter common historical context"
            )

        return tuple(
            resolved_dates
        )

    def get(
        self,
        session_id: str,
    ) -> ParticipantMarketOverviewRead:
        trusted = self.context.resolve(session_id)

        state = self.orchestration.get(session_id)

        if (
            state.current_stage
            == ParticipantStage.BACKGROUND_REQUIRED.value
        ):
            raise ParticipantMarketOverviewUnavailableError(
                "market overview is unavailable before "
                "current-period market information is delivered"
            )

        provider = self.price_providers.get(
            trusted.episode_id
        )

        if provider is None:
            raise ParticipantMarketOverviewInvariantError(
                "assigned canonical episode has no bound "
                "market price provider"
            )

        protocol = getattr(
            self.context,
            "protocol",
            None,
        )

        if not isinstance(protocol, dict):
            raise ParticipantMarketOverviewInvariantError(
                "trusted participant protocol is unavailable"
            )

        timeline = protocol.get("timeline")

        if not isinstance(timeline, list):
            raise ParticipantMarketOverviewInvariantError(
                "trusted participant protocol timeline "
                "is unavailable"
            )

        visible_rows: list[tuple[int, dict]] = []

        for raw_row in timeline:
            if not isinstance(raw_row, dict):
                continue

            raw_step = raw_row.get(
                "experiment_step"
            )

            if raw_step is None:
                continue

            step = int(raw_step)

            if step <= trusted.experiment_step:
                visible_rows.append(
                    (step, raw_row)
                )

        visible_rows.sort(
            key=lambda item: item[0]
        )

        if not visible_rows:
            raise ParticipantMarketOverviewInvariantError(
                "no participant-visible protocol checkpoint "
                "exists for the current session"
            )

        steps = [
            step
            for step, _row in visible_rows
        ]

        if len(set(steps)) != len(steps):
            raise ParticipantMarketOverviewInvariantError(
                "participant-visible protocol checkpoint "
                "steps are duplicated"
            )

        if (
            visible_rows[-1][0]
            != trusted.experiment_step
        ):
            raise ParticipantMarketOverviewInvariantError(
                "current participant checkpoint is absent "
                "from visible market history"
            )

        visible_price_dates: list[
            tuple[str, str]
        ] = []

        for _step, row in visible_rows:
            participant_date = str(
                row.get("agent_world_date", "")
            ).strip()

            if not participant_date:
                raise ParticipantMarketOverviewInvariantError(
                    "participant-visible checkpoint has "
                    "no agent_world_date"
                )

            try:
                market = self.calendar.status(
                    participant_date
                )
            except TradingCalendarError as exc:
                raise ParticipantMarketOverviewUnavailableError(
                    str(exc)
                ) from exc

            price_date = (
                None
                if market.market_state_date is None
                else str(
                    market.market_state_date
                )
            )

            if not price_date:
                raise ParticipantMarketOverviewUnavailableError(
                    "participant-visible checkpoint has "
                    "no authorised market-state price date"
                )

            visible_price_dates.append(
                (
                    participant_date,
                    price_date,
                )
            )

        current_price_date = (
            visible_price_dates[-1][1]
        )

        trusted_price_date = (
            None
            if trusted.market_state_date is None
            else str(
                trusted.market_state_date
            )
        )

        if (
            trusted_price_date is None
            or current_price_date
            != trusted_price_date
        ):
            raise ParticipantMarketOverviewInvariantError(
                "current visible price date disagrees "
                "with trusted participant market state"
            )

        historical_price_dates = (
            self._historical_price_dates()
        )

        stock_ids = tuple(
            self.assets.ids()
        )

        validate_participant_asset_labels(
            stock_ids
        )

        if not stock_ids:
            raise ParticipantMarketOverviewInvariantError(
                "participant market asset catalog is empty"
            )

        projected_assets: list[
            ParticipantMarketAssetRead
        ] = []

        for stock_id in stock_ids:
            asset = self.assets.get(
                stock_id
            )

            historical_context: list[
                ParticipantHistoricalMarketPricePointRead
            ] = []

            history_reader = getattr(
                provider,
                "get_close_history",
                None,
            )

            try:
                if callable(
                    history_reader
                ):
                    raw_historical_records = tuple(
                        history_reader(
                            stock_id,
                            HISTORICAL_PRICE_CONTEXT_START,
                            HISTORICAL_PRICE_CONTEXT_END,
                        )
                    )

                    historical_rows = tuple(
                        (
                            record.date.isoformat(),
                            record,
                        )
                        for record
                        in raw_historical_records
                    )
                else:
                    # Compatibility path for lightweight test doubles.
                    # The requested exact price date remains server-owned.
                    # Formal canonical providers implement get_close_history.
                    historical_rows = tuple(
                        (
                            price_date,
                            provider.get_close(
                                stock_id,
                                price_date,
                            ),
                        )
                        for price_date
                        in historical_price_dates
                    )
            except PriceNotFoundError as exc:
                raise ParticipantMarketOverviewUnavailableError(
                    "frozen historical close-price context "
                    f"is unavailable for {stock_id}"
                ) from exc

            historical_record_dates = tuple(
                price_date
                for (
                    price_date,
                    _record,
                )
                in historical_rows
            )

            if (
                historical_record_dates
                != historical_price_dates
            ):
                raise ParticipantMarketOverviewInvariantError(
                    "canonical historical close-price "
                    "dates disagree with the frozen "
                    "historical context"
                )

            for (
                historical_price_date,
                record,
            ) in historical_rows:
                historical_close = float(
                    record.close
                )

                if (
                    not isfinite(
                        historical_close
                    )
                    or historical_close <= 0.0
                ):
                    raise ParticipantMarketOverviewInvariantError(
                        "historical canonical close must "
                        "be finite and positive"
                    )

                historical_context.append(
                    ParticipantHistoricalMarketPricePointRead(
                        price_date=(
                            historical_price_date
                        ),
                        close=historical_close,
                    )
                )

            history: list[
                ParticipantMarketPricePointRead
            ] = []

            for (
                participant_date,
                price_date,
            ) in visible_price_dates:
                try:
                    market_close = (
                        provider.get_close(
                            stock_id,
                            price_date,
                        )
                    )
                except PriceNotFoundError as exc:
                    raise ParticipantMarketOverviewUnavailableError(
                        "canonical exact-date close price "
                        f"is unavailable for {stock_id} "
                        f"on {price_date}"
                    ) from exc

                close = float(
                    market_close.close
                )

                if (
                    not isfinite(close)
                    or close <= 0.0
                ):
                    raise ParticipantMarketOverviewInvariantError(
                        "canonical market close must be "
                        "finite and positive"
                    )

                history.append(
                    ParticipantMarketPricePointRead(
                        participant_date=(
                            participant_date
                        ),
                        price_date=price_date,
                        close=close,
                    )
                )

            current_price = (
                history[-1].close
            )

            previous_visible_close = (
                None
                if len(history) < 2
                else history[-2].close
            )

            change_pct = None

            if previous_visible_close is not None:
                change_pct = (
                    (
                        current_price
                        - previous_visible_close
                    )
                    / previous_visible_close
                    * 100.0
                )

            projected_assets.append(
                ParticipantMarketAssetRead(
                    stock_id=str(stock_id),
                    display_name=participant_asset_display_name(
                        asset.stock_id
                    ),
                    short_display_name=participant_asset_short_name(
                        asset.stock_id
                    ),
                    current_price=current_price,
                    previous_visible_close=(
                        previous_visible_close
                    ),
                    change_from_previous_visible_pct=(
                        change_pct
                    ),
                    historical_price_context=(
                        historical_context
                    ),
                    price_history=history,
                )
            )

        return ParticipantMarketOverviewRead(
            session_id=trusted.session_id,
            current_date=(
                trusted.agent_world_date
            ),
            price_date=current_price_date,
            assets=projected_assets,
        )

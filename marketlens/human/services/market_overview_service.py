"""Participant-safe canonical market overview projection.

This service is read-only. It never advances the participant session,
changes a portfolio, invokes TwinMarket matching, or exposes future
canonical market state.

Price history is bounded by participant-visible experiment checkpoints,
not by every historical row present in the canonical Agent-world DB.
"""
from __future__ import annotations

from marketlens.human.participant_asset_labels import (
    participant_asset_display_name,
    participant_asset_short_name,
    validate_participant_asset_labels,
)


from math import isfinite
from typing import Mapping

from marketlens.human.orchestration import ParticipantStage
from marketlens.human.schemas import (
    ParticipantMarketAssetRead,
    ParticipantMarketOverviewRead,
    ParticipantMarketPricePointRead,
)
from marketlens.market.price_provider import PriceNotFoundError
from marketlens.market.status import TradingCalendarError


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

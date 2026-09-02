from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from marketlens.episode.contract import EPISODE_IDS
from marketlens.human.participant_asset_labels import (
    PARTICIPANT_ASSET_LABELS,
)
from marketlens.human.measurement.event_store import (
    ParticipantEventStore,
)
from marketlens.main import create_app
from marketlens.stimulus.engine import StimulusEngine
from marketlens.stimulus.material import load_material


ROOT = Path(__file__).resolve().parents[3]

FORMAL_STIMULUS = (
    ROOT
    / "data"
    / "marketlens"
    / "stimuli"
    / "stimulus_v1.formal.json"
)


class FakeProjection:
    def __init__(
        self,
        episode_id: str,
    ):
        self.episode = SimpleNamespace(
            episode_id=episode_id
        )

    def project(
        self,
        *,
        current_date: str,
    ):
        return {
            "current_date": current_date,
            "natural_news": [
                f"background-{current_date}"
            ],
            "forum_posts": [],
        }


class FakePriceProvider:
    def __init__(self):
        self.calls: list[
            tuple[str, str]
        ] = []

    def get_close(
        self,
        stock_id: str,
        trading_date,
    ):
        date_value = (
            trading_date.isoformat()
            if hasattr(
                trading_date,
                "isoformat",
            )
            else str(trading_date)
        )

        self.calls.append(
            (
                str(stock_id),
                date_value,
            )
        )

        stock_component = (
            sum(
                ord(char)
                for char in str(stock_id)
            )
            % 17
        )

        date_component = int(
            date_value[-2:]
        )

        close = (
            90.0
            + stock_component
            + date_component / 100.0
        )

        return SimpleNamespace(
            stock_id=str(stock_id),
            trading_date=date_value,
            close=close,
        )


def _runtime_app(tmp_path):
    episode_id = EPISODE_IDS[0]

    events = ParticipantEventStore(
        tmp_path
        / "participant_events.db"
    )

    engine = StimulusEngine(
        load_material(
            FORMAL_STIMULUS,
            formal=True,
        )
    )

    provider = FakePriceProvider()

    app = create_app(
        tmp_path / "human.db",
        participant_runtime_enabled=True,
        participant_event_store=events,
        background_projections={
            episode_id:
                FakeProjection(
                    episode_id
                )
        },
        journey_price_providers={
            episode_id: provider
        },
        stimulus_engine=engine,
    )

    return (
        app,
        events,
        episode_id,
        provider,
    )


def _create_and_bind(
    client: TestClient,
    episode_id: str,
) -> str:
    created = client.post(
        "/session",
        json={
            "participant_id": "P001",
            "request_id": "session-create",
        },
    )

    assert created.status_code == 201

    session_id = (
        created.json()["session_id"]
    )

    client.app.state.participant_runtime.assignments.bind(
        session_id,
        episode_id,
        assignment_method=(
            "phase15-market-overview-test"
        ),
        assignment_version=(
            "phase15-market-overview-v1"
        ),
    )

    return session_id


def test_market_overview_requires_assignment(
    tmp_path,
) -> None:
    app, events, _episode_id, _provider = (
        _runtime_app(tmp_path)
    )

    with TestClient(app) as client:
        created = client.post(
            "/session",
            json={
                "participant_id": "P001",
                "request_id": "session-create",
            },
        )

        session_id = (
            created.json()["session_id"]
        )

        response = client.get(
            f"/session/{session_id}/market-overview"
        )

        assert response.status_code == 409
        assert (
            "assignment"
            in response.json()["detail"]
        )

    events.dispose()


def test_market_overview_is_blocked_until_background_delivery(
    tmp_path,
) -> None:
    app, events, episode_id, _provider = (
        _runtime_app(tmp_path)
    )

    with TestClient(app) as client:
        session_id = _create_and_bind(
            client,
            episode_id,
        )

        response = client.get(
            f"/session/{session_id}/market-overview"
        )

        assert response.status_code == 409
        assert (
            "before current-period market information"
            in response.json()["detail"]
        )

    events.dispose()


def test_market_overview_exposes_only_current_visible_checkpoint_prices(
    tmp_path,
) -> None:
    app, events, episode_id, provider = (
        _runtime_app(tmp_path)
    )

    with TestClient(app) as client:
        session_id = _create_and_bind(
            client,
            episode_id,
        )

        delivered = client.post(
            f"/session/{session_id}/exposure/background",
            json={
                "request_id": "background-0"
            },
        )

        assert delivered.status_code == 200

        response = client.get(
            f"/session/{session_id}/market-overview"
        )

        assert response.status_code == 200

        body = response.json()

        assert {
            asset["stock_id"]:
                asset["display_name"]
            for asset in body["assets"]
        } == dict(
            PARTICIPANT_ASSET_LABELS
        )

        assert set(body) == {
            "session_id",
            "current_date",
            "price_date",
            "assets",
        }

        assert (
            body["session_id"]
            == session_id
        )

        assert (
            body["current_date"]
            == "2023-06-19"
        )

        assert (
            body["price_date"]
            == "2023-06-19"
        )

        expected_ids = list(
            client.app.state.asset_catalog.ids()
        )

        assert [
            asset["stock_id"]
            for asset in body["assets"]
        ] == expected_ids

        assert body["assets"]

        for asset in body["assets"]:
            assert set(asset) == {
                "stock_id",
                "display_name",
                "short_display_name",
                "current_price",
                "previous_visible_close",
                "change_from_previous_visible_pct",
                "historical_price_context",
                "price_history",
            }

            assert (
                asset["previous_visible_close"]
                is None
            )

            assert (
                asset[
                    "change_from_previous_visible_pct"
                ]
                is None
            )

            historical = asset[
                "historical_price_context"
            ]

            assert len(
                historical
            ) == 108

            assert historical[0][
                "price_date"
            ] == "2023-01-03"

            assert historical[-1][
                "price_date"
            ] == "2023-06-14"

            historical_dates = {
                item["price_date"]
                for item in historical
            }

            assert "2023-06-15" not in (
                historical_dates
            )

            assert "2023-06-16" not in (
                historical_dates
            )

            assert all(
                set(item)
                == {
                    "price_date",
                    "close",
                }
                for item in historical
            )

            assert len(
                asset["price_history"]
            ) == 1

            point = (
                asset["price_history"][0]
            )

            assert set(point) == {
                "participant_date",
                "price_date",
                "close",
            }

            assert (
                point["participant_date"]
                == "2023-06-19"
            )

            assert (
                point["price_date"]
                == "2023-06-19"
            )

            assert (
                point["close"]
                == asset["current_price"]
            )

        called_dates = {
            date
            for _stock_id, date
            in provider.calls
        }

        assert "2023-01-03" in (
            called_dates
        )

        assert "2023-06-14" in (
            called_dates
        )

        assert "2023-06-15" not in (
            called_dates
        )

        assert "2023-06-16" not in (
            called_dates
        )

        assert "2023-06-19" in (
            called_dates
        )

        assert max(
            called_dates
        ) == "2023-06-19"

        assert len(provider.calls) == (
            len(expected_ids)
            * 109
        )

        serialised = str(body)

        assert "episode_id" not in serialised
        assert "experiment_step" not in serialised
        assert "agent_world_date" not in serialised

        paths = client.get(
            "/openapi.json"
        ).json()["paths"]

        assert (
            "/session/{session_id}/market-overview"
            in paths
        )

    events.dispose()

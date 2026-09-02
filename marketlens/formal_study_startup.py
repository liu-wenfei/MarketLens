"""Formal-study startup composition with explicit persistent local data paths.

This module is a deployment boundary. It does not change the frozen
participant journey, feedback policy, portfolio semantics, canonical
episodes, or Agent-world behaviour.

Before authentication is implemented, the executable entrypoint is
intentionally loopback-only and must not be exposed to participants.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from fastapi import FastAPI

from marketlens.human.formal_feedback_generator import (
    create_formal_openai_feedback_generator,
)
from marketlens.participant_server import create_formal_participant_app


FORMAL_DATA_RELATIVE_DIR = Path("data/marketlens/human/formal")
FORMAL_RUNTIME_DB_FILENAME = "participant_runtime.db"
FORMAL_EVENT_DB_FILENAME = "participant_events.db"

LOCAL_PREAUTH_HOST = "127.0.0.1"
LOCAL_PREAUTH_PORT = 8000

_BLOCKING_DATABASE_ENV_VARS = (
    "MARKETLENS_DATABASE_URL",
    "MARKETLENS_DB_PATH",
)


class FormalStudyStartupConfigurationError(ValueError):
    """Raised when persistent formal-study startup would be ambiguous."""


def resolve_formal_data_paths(
    repo_root: str | Path | None = None,
) -> tuple[Path, Path, Path]:
    """Return repo root, main participant DB, and event-ledger DB paths."""

    root = (
        Path(repo_root).expanduser().resolve()
        if repo_root is not None
        else Path(__file__).resolve().parents[1]
    )

    formal_dir = root / FORMAL_DATA_RELATIVE_DIR

    return (
        root,
        formal_dir / FORMAL_RUNTIME_DB_FILENAME,
        formal_dir / FORMAL_EVENT_DB_FILENAME,
    )


def _reject_database_environment_override(
    environ: Mapping[str, str],
) -> None:
    """Fail closed if generic DB environment variables could redirect writes."""

    present = tuple(
        name
        for name in _BLOCKING_DATABASE_ENV_VARS
        if str(environ.get(name, "")).strip()
    )

    if present:
        names = ", ".join(present)
        raise FormalStudyStartupConfigurationError(
            "formal study startup requires explicit deployment-owned "
            f"database paths; unset database override(s): {names}"
        )


def create_persistent_formal_participant_app(
    *,
    repo_root: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> FastAPI:
    """Compose the existing formal runtime onto persistent formal-study DBs.

    The formal feedback provider generator is composed explicitly here.
    Creating the app does not itself request feedback from the provider.
    """

    source = os.environ if environ is None else environ
    _reject_database_environment_override(source)

    root, runtime_db_path, event_db_path = resolve_formal_data_paths(
        repo_root
    )

    runtime_db_path.parent.mkdir(parents=True, exist_ok=True)

    if environ is None:
        feedback_generator = create_formal_openai_feedback_generator()
    else:
        feedback_generator = create_formal_openai_feedback_generator(
            environ=environ
        )

    app = create_formal_participant_app(
        repo_root=root,
        db_path=runtime_db_path,
        participant_event_db_path=event_db_path,
        feedback_generator=feedback_generator,
    )

    # Deployment metadata only. These values do not alter experiment state.
    app.state.formal_study_runtime_db_path = str(runtime_db_path)
    app.state.formal_study_event_db_path = str(event_db_path)
    app.state.formal_study_startup_mode = "persistent_local_preauth"

    return app


def main() -> None:
    """Run the pre-auth formal study server on loopback only."""

    import uvicorn

    print(
        "MarketLens formal study startup: persistent DBs enabled; "
        "PRE-AUTH LOOPBACK ONLY."
    )
    print(
        "Do not expose this server publicly until Phase 16 authentication "
        "and session-ownership gates are accepted."
    )

    uvicorn.run(
        (
            "marketlens.formal_study_startup:"
            "create_persistent_formal_participant_app"
        ),
        factory=True,
        host=LOCAL_PREAUTH_HOST,
        port=LOCAL_PREAUTH_PORT,
    )


if __name__ == "__main__":
    main()

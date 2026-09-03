"""Formal-study startup with explicit persistent paths and auth gateway.

This is a deployment boundary. It composes the already-validated formal
MarketLens participant runtime; it does not change the frozen experiment
journey, feedback policy, portfolio semantics, canonical episodes, or
Agent-world behaviour.

The executable entrypoint remains loopback-only until the final formal
deployment acceptance gate is complete.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path

from fastapi import FastAPI

from marketlens.formal_auth import (
    FormalAuthStore,
    create_authenticated_formal_gateway,
)
from marketlens.human.formal_feedback_generator import (
    create_formal_openai_feedback_generator,
)
from marketlens.participant_server import (
    DEFAULT_FRONTEND_ORIGINS,
    create_formal_participant_app,
)


FORMAL_DATA_RELATIVE_DIR = Path(
    "data/marketlens/human/formal"
)
FORMAL_RUNTIME_DB_FILENAME = "participant_runtime.db"
FORMAL_EVENT_DB_FILENAME = "participant_events.db"
FORMAL_AUTH_DB_FILENAME = "participant_auth.db"

LOCAL_PREAUTH_HOST = "127.0.0.1"
LOCAL_PREAUTH_PORT = 8000

_BLOCKING_DATABASE_ENV_VARS = (
    "MARKETLENS_DATABASE_URL",
    "MARKETLENS_DB_PATH",
)


class FormalStudyStartupConfigurationError(ValueError):
    """Raised when formal-study startup would be ambiguous."""


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


def resolve_formal_auth_db_path(
    repo_root: str | Path | None = None,
) -> Path:
    root, runtime_db_path, _event_db_path = (
        resolve_formal_data_paths(repo_root)
    )
    del root
    return runtime_db_path.parent / FORMAL_AUTH_DB_FILENAME


def _enforce_private_formal_db_permissions(
    *paths: Path,
) -> None:
    # Fail closed unless each formal-study SQLite file is mode 600.

    for path in paths:
        if not path.is_file():
            raise FormalStudyStartupConfigurationError(
                "formal study database was not created as expected: "
                f"{path}"
            )

        try:
            os.chmod(path, 0o600)
        except OSError as exc:
            raise FormalStudyStartupConfigurationError(
                "cannot enforce private permissions on formal study "
                f"database: {path}"
            ) from exc

        if (path.stat().st_mode & 0o777) != 0o600:
            raise FormalStudyStartupConfigurationError(
                "formal study database permissions are not private: "
                f"{path}"
            )


def _reject_database_environment_override(
    environ: Mapping[str, str],
) -> None:
    """Fail closed if generic DB variables could redirect formal writes."""

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
    allowed_origins: Sequence[str] = (
        DEFAULT_FRONTEND_ORIGINS
    ),
) -> FastAPI:
    """Compose persistent formal runtime behind the auth gateway.

    Creating the application instantiates the frozen formal feedback
    generator configuration but does not itself make a provider request.
    """

    source = os.environ if environ is None else environ
    _reject_database_environment_override(source)

    root, runtime_db_path, event_db_path = (
        resolve_formal_data_paths(repo_root)
    )
    auth_db_path = resolve_formal_auth_db_path(root)

    runtime_db_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if environ is None:
        feedback_generator = (
            create_formal_openai_feedback_generator()
        )
    else:
        feedback_generator = (
            create_formal_openai_feedback_generator(
                environ=environ
            )
        )

    resolved_origins = tuple(
        str(origin).rstrip("/")
        for origin in allowed_origins
        if str(origin).strip()
    )

    inner_app = create_formal_participant_app(
        repo_root=root,
        db_path=runtime_db_path,
        participant_event_db_path=event_db_path,
        allowed_origins=resolved_origins,
        feedback_generator=feedback_generator,
    )

    auth_store = FormalAuthStore(
        auth_db_path
    )

    _enforce_private_formal_db_permissions(
        runtime_db_path,
        event_db_path,
        auth_db_path,
    )

    app = create_authenticated_formal_gateway(
        inner_app=inner_app,
        auth_store=auth_store,
        allowed_origins=resolved_origins,
    )

    # Deployment metadata only.
    app.state.formal_study_runtime_db_path = str(
        runtime_db_path
    )
    app.state.formal_study_event_db_path = str(
        event_db_path
    )
    app.state.formal_study_auth_db_path = str(
        auth_db_path
    )
    app.state.formal_study_startup_mode = (
        "persistent_local_authenticated"
    )

    return app


def main() -> None:
    """Run the authenticated deployment locally for acceptance testing."""

    import uvicorn

    print(
        "MarketLens formal study startup: persistent DBs + "
        "authentication enabled; LOOPBACK ACCEPTANCE MODE."
    )
    print(
        "Do not expose publicly until the final Phase 16 "
        "deployment acceptance gate is complete."
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

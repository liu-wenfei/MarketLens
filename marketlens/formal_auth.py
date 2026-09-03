"""Deployment-only authentication and session-ownership boundary.

This module protects the formal participant HTTP surface without changing
the frozen MarketLens experiment semantics. Participant credentials live
in a separate local-only SQLite database and are not research outcomes.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from marketlens.human.schemas import SessionCreate, SessionRead
from marketlens.human.services.episode_assignment_service import (
    EpisodeAssignmentConflictError,
    EpisodeAssignmentValidationError,
)
from marketlens.human.services.orchestration_service import (
    ExperimentStateConflictError,
)
from marketlens.human.services.session_service import (
    IdempotencyConflictError,
    SessionNotFoundError,
)


PASSWORD_SCRYPT_N = 2**14
PASSWORD_SCRYPT_R = 8
PASSWORD_SCRYPT_P = 1
PASSWORD_HASH_BYTES = 32
PASSWORD_SALT_BYTES = 16

AUTH_TOKEN_BYTES = 32
AUTH_TOKEN_TTL_HOURS = 24

_AUTH_SCHEMA_VERSION = "marketlens-formal-auth-v1"


class FormalAuthError(ValueError):
    """Base deployment-auth error."""


class FormalAuthProvisioningError(FormalAuthError):
    """Raised when the account register cannot be provisioned safely."""


class FormalAuthLoginCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    participant_id: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class FormalAuthLoginRead(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    session: SessionRead


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _normalise_participant_id(value: str) -> str:
    participant_id = str(value).strip().upper()

    if not participant_id or len(participant_id) > 128:
        raise FormalAuthError("invalid participant identity")

    return participant_id


def _normalise_password(value: str) -> str:
    password = str(value).strip()

    if not password or len(password) > 256:
        raise FormalAuthError("invalid password")

    return password


def _password_digest(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=PASSWORD_SCRYPT_N,
        r=PASSWORD_SCRYPT_R,
        p=PASSWORD_SCRYPT_P,
        dklen=PASSWORD_HASH_BYTES,
    )


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _bootstrap_request_id(participant_id: str) -> str:
    digest = hashlib.sha256(
        participant_id.encode("utf-8")
    ).hexdigest()

    return f"formal-auth-bootstrap-{digest}"


class FormalAuthStore:
    """Local-only credential/token store; never stores plaintext secrets."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=30.0,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialise(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS participant_accounts (
                    participant_id TEXT PRIMARY KEY,
                    password_salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL,
                    enabled INTEGER NOT NULL
                        CHECK (enabled IN (0, 1)),
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS participant_auth_tokens (
                    token_hash TEXT PRIMARY KEY,
                    participant_id TEXT NOT NULL,
                    issued_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY(participant_id)
                        REFERENCES participant_accounts(participant_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS
                    ix_participant_auth_tokens_participant
                ON participant_auth_tokens(participant_id);

                CREATE TABLE IF NOT EXISTS auth_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            connection.execute(
                """
                INSERT OR REPLACE INTO auth_metadata(key, value)
                VALUES ('schema_version', ?)
                """,
                (_AUTH_SCHEMA_VERSION,),
            )

        try:
            os.chmod(self.path, 0o600)
        except OSError as exc:
            raise FormalAuthProvisioningError(
                "cannot enforce private permissions on participant auth DB"
            ) from exc

    def account_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM participant_accounts"
            ).fetchone()
        assert row is not None
        return int(row["count"])

    def provision_account(
        self,
        *,
        participant_id: str,
        password: str,
        enabled: bool = True,
    ) -> None:
        """Create one account; existing identities are never overwritten."""

        pid = _normalise_participant_id(participant_id)
        secret = _normalise_password(password)
        salt = secrets.token_bytes(PASSWORD_SALT_BYTES)
        digest = _password_digest(secret, salt)

        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO participant_accounts(
                        participant_id,
                        password_salt,
                        password_hash,
                        enabled,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        pid,
                        salt,
                        digest,
                        1 if enabled else 0,
                        _iso(_utc_now()),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise FormalAuthProvisioningError(
                "participant account already exists"
            ) from exc

    def verify_credentials(
        self,
        *,
        participant_id: str,
        password: str,
    ) -> str | None:
        """Return canonical participant_id only for a valid enabled account."""

        try:
            pid = _normalise_participant_id(participant_id)
            secret = _normalise_password(password)
        except FormalAuthError:
            return None

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    participant_id,
                    password_salt,
                    password_hash,
                    enabled
                FROM participant_accounts
                WHERE participant_id = ?
                """,
                (pid,),
            ).fetchone()

        if row is None or int(row["enabled"]) != 1:
            return None

        candidate = _password_digest(
            secret,
            bytes(row["password_salt"]),
        )

        if not hmac.compare_digest(
            candidate,
            bytes(row["password_hash"]),
        ):
            return None

        return str(row["participant_id"])

    def issue_token(
        self,
        participant_id: str,
        *,
        now: datetime | None = None,
    ) -> tuple[str, datetime]:
        pid = _normalise_participant_id(participant_id)
        current = now or _utc_now()
        expires = current + timedelta(
            hours=AUTH_TOKEN_TTL_HOURS
        )
        token = secrets.token_urlsafe(AUTH_TOKEN_BYTES)
        digest = _token_digest(token)

        with self._connect() as connection:
            account = connection.execute(
                """
                SELECT enabled
                FROM participant_accounts
                WHERE participant_id = ?
                """,
                (pid,),
            ).fetchone()

            if account is None or int(account["enabled"]) != 1:
                raise FormalAuthError(
                    "cannot issue a token for an unavailable account"
                )

            # One active browser credential per participant. A fresh login
            # invalidates earlier bearer tokens but does not create a new
            # MarketLens experiment session.
            connection.execute(
                """
                DELETE FROM participant_auth_tokens
                WHERE participant_id = ?
                """,
                (pid,),
            )
            connection.execute(
                """
                INSERT INTO participant_auth_tokens(
                    token_hash,
                    participant_id,
                    issued_at,
                    expires_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    digest,
                    pid,
                    _iso(current),
                    _iso(expires),
                ),
            )

        return token, expires

    def resolve_token(
        self,
        token: str,
        *,
        now: datetime | None = None,
    ) -> str | None:
        raw = str(token).strip()
        if not raw:
            return None

        current = now or _utc_now()
        digest = _token_digest(raw)

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    t.participant_id,
                    t.expires_at,
                    a.enabled
                FROM participant_auth_tokens AS t
                JOIN participant_accounts AS a
                  ON a.participant_id = t.participant_id
                WHERE t.token_hash = ?
                """,
                (digest,),
            ).fetchone()

            if row is None or int(row["enabled"]) != 1:
                return None

            try:
                expires = datetime.fromisoformat(
                    str(row["expires_at"])
                )
            except ValueError:
                return None

            if expires <= current:
                connection.execute(
                    """
                    DELETE FROM participant_auth_tokens
                    WHERE token_hash = ?
                    """,
                    (digest,),
                )
                return None

            return str(row["participant_id"])


def _bearer_token(request: Request) -> str | None:
    value = request.headers.get("Authorization", "").strip()

    if not value:
        return None

    parts = value.split(None, 1)

    if (
        len(parts) != 2
        or parts[0].lower() != "bearer"
        or not parts[1].strip()
    ):
        return None

    return parts[1].strip()


def create_authenticated_formal_gateway(
    *,
    inner_app: FastAPI,
    auth_store: FormalAuthStore,
    allowed_origins: tuple[str, ...],
) -> FastAPI:
    """Wrap the frozen formal app in the public participant auth boundary."""

    if not allowed_origins:
        raise FormalAuthError(
            "formal auth gateway requires an explicit frontend origin"
        )

    runtime = getattr(
        inner_app.state,
        "participant_runtime",
        None,
    )

    if runtime is None:
        raise FormalAuthError(
            "formal auth gateway requires the participant runtime"
        )

    app = FastAPI(
        title="MarketLens Formal Study Gateway",
        version="0.3.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    app.state.formal_inner_app = inner_app
    app.state.formal_auth_store = auth_store

    # Mirror only deployment-relevant references for acceptance tests and
    # controlled shutdown. The frozen services remain owned by inner_app.
    app.state.participant_runtime = runtime
    app.state.db = inner_app.state.db
    app.state.formal_participant_event_store = getattr(
        inner_app.state,
        "formal_participant_event_store",
        None,
    )
    app.state.feedback_preparation_service = getattr(
        inner_app.state,
        "feedback_preparation_service",
        None,
    )
    app.state.formal_feedback_runtime_policy = getattr(
        inner_app.state,
        "formal_feedback_runtime_policy",
        None,
    )

    @app.post(
        "/auth/login",
        response_model=FormalAuthLoginRead,
        status_code=status.HTTP_200_OK,
    )
    def login(
        payload: FormalAuthLoginCreate,
    ) -> FormalAuthLoginRead:
        participant_id = auth_store.verify_credentials(
            participant_id=payload.participant_id,
            password=payload.password,
        )

        if participant_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid participant ID or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            session = runtime.sessions.create(
                SessionCreate(
                    participant_id=participant_id,
                    request_id=_bootstrap_request_id(
                        participant_id
                    ),
                )
            )
            runtime.assignments.allocate_balanced_random(
                session.session_id
            )
            runtime.orchestration.initialize(
                session.session_id
            )
            session = runtime.sessions.get(
                session.session_id
            )
        except (
            IdempotencyConflictError,
            EpisodeAssignmentConflictError,
            EpisodeAssignmentValidationError,
            ExperimentStateConflictError,
        ) as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Unable to initialise participant session",
            ) from exc

        if session.participant_id != participant_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Participant session identity invariant failed",
            )

        token, expires_at = auth_store.issue_token(
            participant_id
        )

        return FormalAuthLoginRead(
            access_token=token,
            expires_at=expires_at,
            session=session,
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "marketlens-formal-study-gateway",
        }

    @app.middleware("http")
    async def participant_auth_boundary(
        request: Request,
        call_next,
    ):
        path = request.url.path

        if request.method == "OPTIONS":
            return await call_next(request)

        if path in {"/health", "/auth/login"}:
            return await call_next(request)

        # Formal participants never create sessions through the inherited
        # unauthenticated bootstrap route. Login is the only public entry.
        if path == "/participant-session":
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"detail": "Not found"},
            )

        if path.startswith("/session/"):
            token = _bearer_token(request)
            participant_id = (
                auth_store.resolve_token(token)
                if token is not None
                else None
            )

            if participant_id is None:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Authentication required"},
                    headers={
                        "WWW-Authenticate": "Bearer"
                    },
                )

            pieces = path.split("/")
            session_id = (
                pieces[2].strip()
                if len(pieces) > 2
                else ""
            )

            if not session_id:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"detail": "Not found"},
                )

            try:
                session = runtime.sessions.get(
                    session_id
                )
            except SessionNotFoundError:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"detail": "Unknown session"},
                )

            if (
                session.participant_id
                != participant_id
            ):
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "detail": (
                            "Session is not owned by "
                            "the authenticated participant"
                        )
                    },
                )

            request.state.authenticated_participant_id = (
                participant_id
            )

            return await call_next(request)

        # Hide inherited development/legacy HTTP surfaces in the formal
        # authenticated deployment. The inner app remains unchanged.
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Not found"},
        )

    # Add CORS after the auth middleware so CORS is outermost and therefore
    # also decorates 401/403 responses generated by the auth boundary.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            str(origin).rstrip("/")
            for origin in allowed_origins
            if str(origin).strip()
        ],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=[
            "Authorization",
            "Content-Type",
        ],
    )

    # The inherited formal app is mounted unchanged behind the gateway.
    app.mount("/", inner_app)

    return app

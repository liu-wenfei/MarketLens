# MarketLens database portability gate

This commit is an infrastructure refactor after `phase02-participant-portfolio-v1.0`.
It does **not** change Phase 2 participant behaviour and does not add Agent,
experiment-timeline, frontend, authentication, or Azure SDK logic.

## What changes

- Persistence now uses SQLAlchemy Core instead of direct `sqlite3` calls.
- Existing local callers may still pass a SQLite file path to `create_app(...)`.
- Preferred configuration is now `MARKETLENS_DATABASE_URL`.
- PostgreSQL URLs use the normal SQLAlchemy form, for example
  `postgresql+psycopg://...`.
- Current transaction-critical stores lock the participant session row with
  `SELECT ... FOR UPDATE` on PostgreSQL. SQLAlchemy omits that clause on SQLite.
- Alembic now owns the production migration boundary.

## Local development

No behaviour change is required. By default, missing local SQLite tables are
still auto-created so the existing test/development workflow remains simple.
`MARKETLENS_DB_PATH` remains supported for backwards compatibility.

## Production / future Azure PostgreSQL

For a new production database:

1. Set `MARKETLENS_DATABASE_URL` through deployment configuration/secrets.
2. Run `alembic upgrade head` before starting the application.
3. Set `MARKETLENS_AUTO_CREATE_SCHEMA=0` so application startup does not mutate
   the production schema.

Managed Identity / Microsoft Entra token acquisition is deliberately not
implemented in this gate. That belongs to the later deployment/security gate.

## Explicitly unchanged

- Participant portfolio rules and API semantics.
- Decision / round-completion ownership.
- Read-only `data/stock_profile.csv` and `data/stock_data.csv`.
- TwinMarket `Agent.py`, `simulation.py`, `trader/`, and `util/`.
- Currency is still represented with the Phase 2 float/rounding behaviour.
  A later formal-data hardening gate may migrate currency columns to
  `NUMERIC`/`Decimal` before experiment freeze.

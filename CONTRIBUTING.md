# Contributing to skillhubserver

Thanks for contributing. This document covers local setup, tests, and conventions.

## Development environment

**Requirements**

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- Optional: PostgreSQL 16 for dual-DB tests

**Setup**

```bash
cp .env.example .env
# set SECRET_KEY in .env

make install
make migrate
```

**Run services**

```bash
# Terminal 1 — API (port 3000)
make dev-backend

# Terminal 2 — Vite (port 5173, proxies /api → 3000)
make dev-frontend
```

Open http://localhost:5173. First visit creates the admin via the bootstrap page.

## Tests

Backend tests use pytest. SQLite runs by default; PostgreSQL is optional.

```bash
# All tests (SQLite + skipped PG matrix when TEST_POSTGRESQL_URL unset)
make test

# Or from backend/
cd backend && uv run pytest -q
```

**PostgreSQL matrix**

```bash
export TEST_POSTGRESQL_URL=postgresql+psycopg://user:pass@localhost:5432/skillhub_test
uv run --directory backend pytest -q
```

**Frontend typecheck**

```bash
cd frontend && npm run lint
```

## Project layout

```
backend/app/          FastAPI app (routers → services → repositories → models)
backend/alembic/      Migrations
backend/tests/        unit/ + integration/
frontend/src/         React SPA (api/, contexts/, pages/, locales/)
docs/                 proposal, design, tasks
docker/               Dockerfile + compose
```

## Code conventions

- **Layers**: routers stay thin; business rules in `services/`; SQL in `repositories/`.
- **API envelope**: success `{ "data": ... }`, errors `{ "error": { "code", "message" } }`.
- **Auth**: session cookie + `X-CSRF-Token` on write methods; login and bootstrap/init are CSRF-exempt.
- **Dual DB**: do not hard-code SQLite-only SQL in repositories; search goes through `SearchRepository`.
- **Enums**: store as VARCHAR (`native_enum=False`).
- **i18n**: keep `frontend/src/locales/en.json` and `zh.json` keys in sync.

## Migrations

```bash
cd backend
uv run alembic revision -m "describe change"
uv run alembic upgrade head
```

Prefer dialect-branched upgrades when SQLite and PostgreSQL diverge (see `002_fts`).

## Pull requests

1. Add or update tests for the change.
2. Run `make test` and `cd frontend && npm run lint`.
3. Update `docs/tasks.md` checkboxes if you complete listed work.
4. Keep commits focused; avoid committing `.env`, `data/`, or secrets.

## Security notes

- Never commit a real `SECRET_KEY`.
- ZIP import must keep zip-slip / symlink / size guards.
- Media upload is limited to image types and `MAX_UPLOAD_SIZE`.

# Moneyball — Multi-Sport Tipping & Simulation Platform

Quant research stack for MLB, NBA, AFL, and Soccer. Read-only odds, manual
staking, no auto-bet placement. Base currency: **AUD**.

This is **Phase 1** of the build (per the agreed build order): repo scaffold,
Docker Compose, DB schema/migrations, and demo seed data. No ingestion,
simulation, or modelling logic exists yet — those land in Phases 2+.

## Stack

Next.js 14 (App Router) + TypeScript + Tailwind · FastAPI (Python 3.11) ·
PostgreSQL 16 + TimescaleDB · Redis + Celery · SQLAlchemy 2.0 + Alembic.

## Quickstart

```bash
cp .env.example .env   # edit if you already have API keys; app works with none
make up                # docker compose up -d --build
make migrate            # alembic upgrade head
make seed                # populates a demo slate for all 4 sports
```

- Web: http://localhost:3000
- API: http://localhost:8000 (docs at `/docs`)
- API health: http://localhost:8000/health, http://localhost:8000/health/db

## Database access

```bash
make db
```

opens `psql` on the running Postgres container. Direct connection string
(matches `.env.example`, adjust password if you changed it):

```
postgresql://moneyball:moneyball_dev_password@localhost:5433/moneyball
```

Note the container publishes Postgres on host port **5433** (not 5432) and
Redis on **6380**, to avoid clashing with any local instances.

## Tests

```bash
make test-api   # pytest inside the api container
make test-web   # vitest inside the web container
```

## Data sources (all free-tier / no-key by default)

See `.env.example` for the full list and rate-limit notes. The seed script
(`make seed`) populates demo fixtures/odds so the app is fully usable before
any keys are configured. The Odds API free tier (500 req/month) is the
binding constraint for live odds — see the ingestion polling design notes
once Phase 4 lands.

## Known tradeoffs from Phase 1 verification

- **Next.js pinned to 14.2.35** (latest patched release on the 14.x line the
  spec requires). `npm audit` still flags some GHSAs against the `next`
  package because the advisory ranges in the npm registry are broad; the
  real fix for several of them ships only in Next 15/16. Moving off Next 14
  is a deliberate major-version call, not something to do silently — flag it
  if/when you want to revisit.
- The `passlib[bcrypt]` + `bcrypt` combo needed `bcrypt` pinned to `4.0.1`;
  newer `bcrypt` (4.1+) dropped an attribute `passlib` 1.7.4 probes for and
  breaks all hashing. Pinned in `apps/api/requirements.txt`.
- The Alembic migration that converts `odds_snapshots` into a Timescale
  hypertable (`alembic/versions/..._odds_snapshots_hypertable.py`) was
  verified for SQL correctness but not exercised end-to-end in this
  environment (no TimescaleDB extension available outside the
  `timescale/timescaledb` Docker image). It will run automatically against
  the real Postgres container the first time you run `make migrate`.

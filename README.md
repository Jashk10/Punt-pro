# Moneyball — Multi-Sport Tipping & Simulation Platform

Quant research stack for MLB, NBA, AFL, and Soccer. Read-only odds, manual
staking, no auto-bet placement. Base currency: **AUD**.

Phases 1-3 are done, per the agreed build order: repo scaffold, AFL data
ingestion, and an AFL simulation model with a calibration/backtest harness.
NBA, Soccer, and MLB don't exist yet — AFL goes first per the build order,
and the other sports land in Phase 6.

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

## AFL ingestion (Phase 2)

`moneyball/ingestion/afl/client.py` wraps the Squiggle API (teams, games,
tips), self-throttled to 1 req/sec with the required descriptive
`User-Agent` (`SQUIGGLE_USER_AGENT` in `.env`). `moneyball/ingestion/afl/sync.py`
upserts teams and fixtures idempotently, matching fixtures by Squiggle's own
game id (stored in `fixtures.external_ids`) so re-running against an
in-progress round updates scores/status in place instead of duplicating.

Trigger a sync manually:

```bash
curl -X POST http://localhost:8000/admin/ingestion/afl/sync \
  -H "Content-Type: application/json" -d '{"year": 2026, "round": 1}'
```

This dispatches a Celery task (`moneyball.ingestion.sync_afl`) — a worker
must be running (`docker compose up` starts one). No auth gate on this
endpoint yet; RBAC lands with the admin panel in Phase 9.

## AFL model + backtest (Phase 3)

`moneyball/models/afl/` implements the `SportModel` interface
(`moneyball/models/base.py`) with a margin-of-victory Elo rating system:

- **Ratings**: standard Elo, K-factor scaled by an MOV multiplier (bigger
  margin = bigger update, dampened when the win was already expected) —
  `moneyball/models/afl/elo.py`.
- **Home ground advantage**: team-and-venue-specific, estimated via
  empirical Bayes shrinkage toward a league-wide default (a team/venue pair
  with little history leans on the prior; one with a long home record, e.g.
  Geelong at GMHBA, gets its own estimate).
- **Simulation**: Monte Carlo margin + total draws (independent Normal,
  empirical Bayes-shrunk mean/std) via `moneyball/simulation/engine.py`,
  which also reports Monte Carlo standard error on every headline
  probability per spec.
- **Not yet implemented**: the full shot-volume × accuracy decomposition
  from the original spec needs contested-possession/inside-50/clearance/xScore
  data that Squiggle's basic API doesn't provide (AFL Tables would). Margin/
  total are currently drawn independently, which is a known simplification —
  real blowouts skew the margin/total relationship. Both are documented as
  upgrade paths in `moneyball/models/afl/model.py`'s docstring, not silently
  glossed over.

**Calibration harness** (`moneyball/quant/calibration.py`, sport-agnostic):
Brier score, log loss, expected calibration error, reliability bins, and the
Green/Amber/Red `model_health` badge — all with known-answer unit tests.

**Backtest** (`moneyball/backtest/walkforward.py`): strict walk-forward —
each prediction only ever sees model state built from strictly earlier
fixtures. Two leakage tests enforce this directly: mutating a later result
must not change any earlier prediction, and truncating future fixtures must
not change any past prediction (`tests/backtest/test_walkforward.py`). No
ROI/CLV yet — that needs real historical closing odds, which is Phase 4.

Run it against ingested data:

```bash
make backtest-afl start=2022-01-01 end=2024-12-31
```

This prints a calibration report (Brier score + bootstrap 95% CI, log loss,
ECE, model_health, reliability bins) and persists it to `backtest_runs` /
`calibration_bins`.

### The actual checkpoint this build order asks for hasn't happened yet

The build order says: run the backtest, stop, and show real calibration
numbers before building more UI. **I can't do that from this environment** —
the sandbox has no network access to Squiggle (see Phase 2 tradeoffs below),
so there is no real historical AFL data to backtest against here. Everything
above is verified against known-answer unit tests and a synthetic,
Elo-shaped dataset (to confirm the walk-forward/fitting machinery actually
learns something, not that the real model is any good) — see
`tests/backtest/test_walkforward.py` and `tests/models/afl/`. I also ran the
full pipeline (DB query → backtest → calibration → persistence) once against
synthetic fixtures inserted directly into the dev database to confirm it
works end-to-end against the real schema, then deleted that data — it's not
in this repo.

**Before any AFL UI gets built, run `make backtest-afl` yourself against real
ingested seasons and look at the actual numbers.** If `model_health` comes
back red or the reliability bins are badly off the diagonal, that's the
signal to retune `apps/api/moneyball/config/afl_model.yaml` (all the Elo/HGA/
distribution constants are placeholder starting values, explicitly flagged
as such in that file) before building the fixture deep-dive UI in Phase 5.

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

## Known tradeoffs from Phase 2 verification

- This sandbox's egress policy also blocks outbound access to
  `api.squiggle.com.au` (confirmed via the proxy's policy-denial log, same
  class of restriction as the Docker registry block above — not a bug in the
  client). `SquiggleClient` and the sync logic are covered by unit tests that
  mock the HTTP layer (`respx`) and exercise the upsert logic against a real
  local Postgres, but **no live pull against the real Squiggle API has been
  done from this environment**. Run a real `POST /admin/ingestion/afl/sync`
  once you're somewhere with internet access to confirm the response shape
  matches what `client.py` assumes (documented inline in that file).

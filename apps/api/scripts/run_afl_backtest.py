"""Runs the walk-forward AFL backtest against ingested Squiggle data and
prints the calibration report — this is the "stop and show me the numbers"
checkpoint from the build order, before any AFL UI gets built.

Usage:
    python -m scripts.run_afl_backtest --start 2022-01-01 --end 2024-12-31

Requires completed AFL fixtures in the database (run the Squiggle sync
first — see README's Phase 2/AFL ingestion section).
"""
from __future__ import annotations

import argparse
from datetime import date

from moneyball.backtest.persist import get_or_create_model_version, persist_backtest_result
from moneyball.backtest.walkforward import run_walkforward_backtest
from moneyball.db.models import Fixture, Sport, Team, Venue
from moneyball.db.session import SessionLocal
from moneyball.models.afl.model import AflModel


def load_afl_fixtures(db, start_date: date, end_date: date) -> list[dict]:
    sport = db.query(Sport).filter_by(code="AFL").one()
    home_team = Team.__table__.alias("home_team")
    away_team = Team.__table__.alias("away_team")

    rows = (
        db.query(
            Fixture,
            home_team.c.name.label("home_name"),
            away_team.c.name.label("away_name"),
            Venue.name.label("venue_name"),
        )
        .join(home_team, Fixture.home_team_id == home_team.c.id)
        .join(away_team, Fixture.away_team_id == away_team.c.id)
        .outerjoin(Venue, Fixture.venue_id == Venue.id)
        .filter(
            Fixture.sport_id == sport.id,
            Fixture.status == "final",
            Fixture.scheduled_at >= start_date,
            Fixture.scheduled_at <= end_date,
        )
        .all()
    )

    return [
        {
            "id": fixture.id,
            "home_team": home_name,
            "away_team": away_name,
            "venue": venue_name,
            "scheduled_at": fixture.scheduled_at.isoformat(),
            "home_score": fixture.home_score,
            "away_score": fixture.away_score,
        }
        for fixture, home_name, away_name, venue_name in rows
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--n-sims", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--min-fit-games", type=int, default=20, help="warmup games before scoring predictions")
    args = parser.parse_args()

    start_date = date.fromisoformat(args.start)
    end_date = date.fromisoformat(args.end)

    db = SessionLocal()
    try:
        fixtures = load_afl_fixtures(db, start_date, end_date)
        if not fixtures:
            print(f"No completed AFL fixtures between {start_date} and {end_date}. Run the AFL sync first (see README).")
            return

        result = run_walkforward_backtest(
            AflModel, fixtures, n_sims=args.n_sims, seed=args.seed, min_fit_games=args.min_fit_games
        )

        model = AflModel()
        model_version = get_or_create_model_version(db, "AFL", model.version, "1", model.cfg)
        persist_backtest_result(
            db,
            model_version,
            start_date,
            end_date,
            result,
            params={"n_sims": args.n_sims, "seed": args.seed, "min_fit_games": args.min_fit_games},
        )

        print(f"AFL backtest {start_date} -> {end_date}")
        print(f"  fixtures loaded: {len(fixtures)}")
        print(f"  predictions (post-warmup, decisive games): {result.n_predictions}")
        if result.n_predictions == 0:
            print("  Not enough data past the warmup window to score — widen the date range or lower --min-fit-games.")
            return
        if result.brier_ci:
            print(f"  Brier score: {result.brier:.4f}  (95% CI: [{result.brier_ci.ci_low:.4f}, {result.brier_ci.ci_high:.4f}])")
        else:
            print(f"  Brier score: {result.brier:.4f}")
        print(f"  Log loss: {result.log_loss:.4f}")
        print(f"  ECE: {result.ece:.4f}")
        print(f"  Model health: {result.model_health.upper()}")
        print("  Reliability bins ([predicted range) n predicted vs observed):")
        for b in result.calibration_bins:
            if b.n == 0:
                continue
            print(f"    [{b.bin_lower:.1f},{b.bin_upper:.1f}) n={b.n:4d} predicted={b.mean_predicted:.3f} observed={b.mean_observed:.3f}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

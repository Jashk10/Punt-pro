from datetime import datetime, timedelta

import numpy as np
import pytest

from moneyball.backtest.walkforward import run_walkforward_backtest
from moneyball.models.afl.model import AflModel

TEAMS = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot"]
VENUES = ["Ground A", "Ground B", "Ground C"]


def make_synthetic_fixtures(n_games: int, seed: int = 0) -> list[dict]:
    """Round-robin-ish schedule with scores generated from a process the Elo
    model can plausibly recover (elo-style true strengths -> margin with
    noise), so a "reasonably calibrated" assertion is meaningful rather than
    arbitrary."""
    rng = np.random.default_rng(seed)
    true_strength = {team: rng.normal(0, 150) for team in TEAMS}

    fixtures = []
    start = datetime(2024, 3, 1)
    for i in range(n_games):
        home, away = rng.choice(TEAMS, size=2, replace=False)
        venue = rng.choice(VENUES)
        true_margin_mean = (true_strength[home] - true_strength[away]) * 0.6 + 6.0  # +6 = HGA
        margin = int(round(rng.normal(true_margin_mean, 35)))
        home_score = max(20, 90 + margin // 2 + rng.integers(-5, 5))
        away_score = home_score - margin
        away_score = max(10, away_score)

        fixtures.append(
            {
                "id": i + 1,
                "home_team": str(home),
                "away_team": str(away),
                "venue": str(venue),
                "scheduled_at": (start + timedelta(days=i * 5)).isoformat(),
                "home_score": int(home_score),
                "away_score": int(away_score),
            }
        )
    return fixtures


def test_backtest_produces_one_prediction_per_decisive_game_after_min_fit():
    fixtures = make_synthetic_fixtures(40, seed=1)
    result = run_walkforward_backtest(AflModel, fixtures, n_sims=2000, seed=0, min_fit_games=10)
    decisive_after_warmup = sum(
        1 for f in sorted(fixtures, key=lambda f: f["scheduled_at"])[10:] if f["home_score"] != f["away_score"]
    )
    assert result.n_predictions == decisive_after_warmup


def test_min_fit_games_gates_early_predictions():
    fixtures = make_synthetic_fixtures(20, seed=2)
    result = run_walkforward_backtest(AflModel, fixtures, n_sims=1000, seed=0, min_fit_games=1000)
    assert result.n_predictions == 0


def test_no_leakage_changing_a_later_result_does_not_change_earlier_predictions():
    fixtures = make_synthetic_fixtures(30, seed=3)
    fixtures_sorted = sorted(fixtures, key=lambda f: f["scheduled_at"])

    original = run_walkforward_backtest(AflModel, fixtures, n_sims=3000, seed=42, min_fit_games=5)

    mutated = [dict(f) for f in fixtures]
    last_id = fixtures_sorted[-1]["id"]
    for f in mutated:
        if f["id"] == last_id:
            # Flip the last game's result to something drastically different.
            f["home_score"], f["away_score"] = f["away_score"] + 200, f["home_score"]

    mutated_result = run_walkforward_backtest(AflModel, mutated, n_sims=3000, seed=42, min_fit_games=5)

    assert len(original.predictions) == len(mutated_result.predictions)
    # Every prediction except possibly the one for the mutated (last) fixture
    # must be bit-identical — nothing about a later result may have flowed
    # backward into an earlier prediction.
    for orig_pred, mut_pred in zip(original.predictions, mutated_result.predictions):
        if orig_pred.fixture_id == last_id:
            continue
        assert orig_pred.home_win_prob == mut_pred.home_win_prob
        assert orig_pred.fixture_id == mut_pred.fixture_id


def test_no_leakage_truncating_future_fixtures_does_not_change_past_predictions():
    fixtures = make_synthetic_fixtures(30, seed=4)
    fixtures_sorted = sorted(fixtures, key=lambda f: f["scheduled_at"])

    full_result = run_walkforward_backtest(AflModel, fixtures, n_sims=3000, seed=7, min_fit_games=5)

    truncated = [f for f in fixtures if f["scheduled_at"] <= fixtures_sorted[14]["scheduled_at"]]
    truncated_result = run_walkforward_backtest(AflModel, truncated, n_sims=3000, seed=7, min_fit_games=5)

    full_by_id = {p.fixture_id: p for p in full_result.predictions}
    for pred in truncated_result.predictions:
        assert pred.home_win_prob == full_by_id[pred.fixture_id].home_win_prob


def test_backtest_reports_calibration_metrics_and_bootstrap_ci():
    fixtures = make_synthetic_fixtures(150, seed=5)
    result = run_walkforward_backtest(AflModel, fixtures, n_sims=5000, seed=0, min_fit_games=20)

    assert result.n_predictions > 0
    assert 0.0 <= result.brier <= 1.0
    assert result.log_loss >= 0.0
    assert 0.0 <= result.ece <= 1.0
    assert result.model_health in {"green", "amber", "red"}
    assert result.brier_ci is not None
    assert result.brier_ci.ci_low <= result.brier_ci.point_estimate <= result.brier_ci.ci_high


def test_backtest_beats_random_guessing_on_a_matched_generative_process():
    # Not a claim of real-world skill — the synthetic data is generated from
    # an Elo-shaped process the model can approximate, so this only checks
    # the walk-forward + fitting machinery is actually learning something,
    # not producing noise indistinguishable from a coin flip.
    fixtures = make_synthetic_fixtures(200, seed=6)
    result = run_walkforward_backtest(AflModel, fixtures, n_sims=5000, seed=0, min_fit_games=20)
    assert result.brier < 0.25  # 0.25 is the fair-coin baseline

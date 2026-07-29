"""Strict walk-forward backtest: for each historical fixture in chronological
order, predict using only model state built from strictly earlier fixtures,
then fit on it before moving to the next. No ROI/CLV yet — that needs real
historical closing odds, which is Phase 4 (odds ingestion) — this reports
calibration quality on out-of-sample win predictions, which is the checkpoint
the build order asks for before any UI gets built.

Draws are excluded from the win-market evaluation (there is no well-defined
"home win" outcome for a draw) but still update the model's rating state.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from moneyball.models.base import FixtureInput, SportModel
from moneyball.quant.bootstrap import BootstrapCI, bootstrap_ci
from moneyball.quant.calibration import CalibrationBin, brier_score, expected_calibration_error, log_loss, model_health, reliability_bins


@dataclass
class BacktestPrediction:
    fixture_id: int | None
    scheduled_at: str
    home_win_prob: float
    home_win_prob_se: float
    actual_home_win: int


@dataclass
class BacktestResult:
    n_predictions: int
    predictions: list[BacktestPrediction] = field(default_factory=list)
    brier: float = float("nan")
    log_loss: float = float("nan")
    ece: float = float("nan")
    calibration_bins: list[CalibrationBin] = field(default_factory=list)
    model_health: str = "amber"
    brier_ci: BootstrapCI | None = None


def run_walkforward_backtest(
    model_factory: Callable[[], SportModel],
    fixtures: list[FixtureInput],
    n_sims: int = 10_000,
    seed: int = 0,
    min_fit_games: int = 0,
) -> BacktestResult:
    model = model_factory()
    fixtures_sorted = sorted(
        (f for f in fixtures if f.get("home_score") is not None and f.get("away_score") is not None),
        key=lambda f: f["scheduled_at"],
    )

    predictions: list[BacktestPrediction] = []
    fitted_count = 0

    for i, fx in enumerate(fixtures_sorted):
        actual_margin = fx["home_score"] - fx["away_score"]  # type: ignore[operator]

        if fitted_count >= min_fit_games and actual_margin != 0:
            sim = model.simulate(fx, n_sims=n_sims, seed=seed + i)
            predictions.append(
                BacktestPrediction(
                    fixture_id=fx.get("id"),
                    scheduled_at=fx["scheduled_at"],
                    home_win_prob=sim.home_win_prob,
                    home_win_prob_se=sim.home_win_prob_se,
                    actual_home_win=1 if actual_margin > 0 else 0,
                )
            )

        # Fit happens strictly after prediction for this fixture — the model
        # that produced the prediction above never saw this result.
        model.fit([fx])
        fitted_count += 1

    if not predictions:
        return BacktestResult(n_predictions=0)

    probs = np.array([p.home_win_prob for p in predictions])
    outcomes = np.array([p.actual_home_win for p in predictions])

    # bootstrap_ci resamples rows, so probs and outcomes must travel together
    # (resampling them independently would break the pairing).
    paired = np.stack([probs, outcomes], axis=1)

    def _paired_brier(sample: np.ndarray) -> float:
        return brier_score(sample[:, 0], sample[:, 1])

    return BacktestResult(
        n_predictions=len(predictions),
        predictions=predictions,
        brier=brier_score(probs, outcomes),
        log_loss=log_loss(probs, outcomes),
        ece=expected_calibration_error(probs, outcomes),
        calibration_bins=reliability_bins(probs, outcomes),
        model_health=model_health(probs, outcomes),
        brier_ci=bootstrap_ci(paired, _paired_brier, seed=seed),
    )

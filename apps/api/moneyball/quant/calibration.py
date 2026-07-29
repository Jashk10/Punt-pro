"""Calibration harness: reliability binning, Brier score, log loss, ECE, and
the model_health traffic light. Shared across sports/markets — nothing here
is AFL-specific.

Per spec section 6.6: if the model says 60% and those bets win 52%, the model
is broken and the site has to say so. This module is what makes that
statement checkable, not just a design intention.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Quality-gate thresholds for model_health. These are ops/monitoring
# thresholds, not fitted model parameters, so they live here rather than in
# a per-sport versioned config file — but they're still named constants, not
# inline magic numbers, and are meant to be revisited once real backtests
# exist to calibrate them against.
ECE_GREEN_MAX = 0.03
ECE_AMBER_MAX = 0.07
MIN_SAMPLES_FOR_HEALTH = 30  # below this, there isn't enough data to judge — treat as amber


def brier_score(probs: np.ndarray, outcomes: np.ndarray) -> float:
    """Mean squared error between predicted probability and the 0/1 outcome.
    Lower is better; 0 is perfect, 0.25 is what "always guess 50%" scores on
    a fair coin."""
    probs = np.asarray(probs, dtype=float)
    outcomes = np.asarray(outcomes, dtype=float)
    if probs.shape != outcomes.shape:
        raise ValueError("probs and outcomes must be the same shape")
    if probs.size == 0:
        raise ValueError("need at least one observation")
    return float(np.mean((probs - outcomes) ** 2))


def log_loss(probs: np.ndarray, outcomes: np.ndarray, eps: float = 1e-15) -> float:
    """Binary cross-entropy. Clips probabilities away from exactly 0/1 so a
    single confident-and-wrong prediction doesn't blow up to infinity."""
    probs = np.asarray(probs, dtype=float)
    outcomes = np.asarray(outcomes, dtype=float)
    if probs.shape != outcomes.shape:
        raise ValueError("probs and outcomes must be the same shape")
    if probs.size == 0:
        raise ValueError("need at least one observation")
    clipped = np.clip(probs, eps, 1 - eps)
    return float(-np.mean(outcomes * np.log(clipped) + (1 - outcomes) * np.log(1 - clipped)))


@dataclass
class CalibrationBin:
    bin_lower: float
    bin_upper: float
    n: int
    mean_predicted: float
    mean_observed: float
    brier: float | None


def reliability_bins(probs: np.ndarray, outcomes: np.ndarray, n_bins: int = 10) -> list[CalibrationBin]:
    """Buckets predictions into equal-width probability bins and compares
    mean predicted vs mean observed in each — the data behind a reliability
    diagram, and what gets persisted to calibration_bins."""
    probs = np.asarray(probs, dtype=float)
    outcomes = np.asarray(outcomes, dtype=float)
    if probs.shape != outcomes.shape:
        raise ValueError("probs and outcomes must be the same shape")

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bins: list[CalibrationBin] = []
    for i in range(n_bins):
        lower, upper = edges[i], edges[i + 1]
        is_last = i == n_bins - 1
        mask = (probs >= lower) & (probs < upper) if not is_last else (probs >= lower) & (probs <= upper)
        n = int(mask.sum())
        if n == 0:
            bins.append(CalibrationBin(bin_lower=lower, bin_upper=upper, n=0, mean_predicted=float("nan"), mean_observed=float("nan"), brier=None))
            continue
        bin_probs = probs[mask]
        bin_outcomes = outcomes[mask]
        bins.append(
            CalibrationBin(
                bin_lower=float(lower),
                bin_upper=float(upper),
                n=n,
                mean_predicted=float(bin_probs.mean()),
                mean_observed=float(bin_outcomes.mean()),
                brier=brier_score(bin_probs, bin_outcomes),
            )
        )
    return bins


def expected_calibration_error(probs: np.ndarray, outcomes: np.ndarray, n_bins: int = 10) -> float:
    """Sample-weighted average gap between predicted and observed probability
    across bins — a single number summarising the reliability diagram."""
    bins = reliability_bins(probs, outcomes, n_bins=n_bins)
    total_n = sum(b.n for b in bins)
    if total_n == 0:
        raise ValueError("need at least one observation")
    return float(
        sum(b.n * abs(b.mean_predicted - b.mean_observed) for b in bins if b.n > 0) / total_n
    )


def model_health(probs: np.ndarray, outcomes: np.ndarray, n_bins: int = 10) -> str:
    """Green/Amber/Red badge driven by rolling ECE. Too little data to judge
    reads as Amber, not Green — silence isn't evidence of a healthy model."""
    probs = np.asarray(probs, dtype=float)
    if probs.size < MIN_SAMPLES_FOR_HEALTH:
        return "amber"
    ece = expected_calibration_error(probs, outcomes, n_bins=n_bins)
    if ece <= ECE_GREEN_MAX:
        return "green"
    if ece <= ECE_AMBER_MAX:
        return "amber"
    return "red"

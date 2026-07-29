"""Generic bootstrap confidence interval helper.

Spec section 6.7 asks for bootstrap CIs on backtest ROI specifically, but ROI
needs real historical closing odds, which don't exist yet (odds ingestion is
Phase 4). This helper is written sport/metric-agnostic so it applies to ROI
later without changes — for now the AFL backtest uses it on Brier score.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np


@dataclass
class BootstrapCI:
    point_estimate: float
    ci_low: float
    ci_high: float
    confidence: float
    n_boot: int


def bootstrap_ci(
    values: np.ndarray,
    statistic_fn: Callable[[np.ndarray], float],
    confidence: float = 0.95,
    n_boot: int = 2000,
    seed: int = 0,
) -> BootstrapCI:
    """Percentile bootstrap: resample `values` with replacement n_boot times,
    recompute statistic_fn on each resample, and report the percentile
    interval. Report the interval, not just the point estimate — a single
    ROI number over a few hundred bets is mostly noise."""
    values = np.asarray(values)
    if values.size == 0:
        raise ValueError("need at least one observation")

    rng = np.random.default_rng(seed)
    n = values.shape[0]
    point_estimate = float(statistic_fn(values))

    boot_stats = np.empty(n_boot)
    for i in range(n_boot):
        resample = values[rng.integers(0, n, size=n)]
        boot_stats[i] = statistic_fn(resample)

    alpha = 1 - confidence
    ci_low, ci_high = np.percentile(boot_stats, [100 * alpha / 2, 100 * (1 - alpha / 2)])

    return BootstrapCI(
        point_estimate=point_estimate,
        ci_low=float(ci_low),
        ci_high=float(ci_high),
        confidence=confidence,
        n_boot=n_boot,
    )

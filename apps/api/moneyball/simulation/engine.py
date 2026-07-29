"""Generic Monte Carlo utilities shared by every sport's simulate(): seeded
RNGs (for reproducibility — same seed always reproduces the same output),
input hashing (for the model_runs audit trail), and Monte Carlo standard
error helpers (for the convergence check in spec section 5: headline
probabilities must report their MC SE, and re-run with more sims if it's
above 0.5%).
"""
from __future__ import annotations

import hashlib
import json

import numpy as np

DEFAULT_MC_SE_THRESHOLD = 0.005  # 0.5%, per spec


def make_rng(seed: int) -> np.random.Generator:
    """Seeded PCG64 generator. Reusing the same seed for a fixture reproduces
    an identical simulation run — this is what full reproducibility rests on."""
    return np.random.default_rng(seed)


def hash_inputs(payload: dict) -> str:
    """Deterministic hash of a model run's inputs, stored on model_runs so an
    admin can verify two runs used identical data."""
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def binary_prob_se(prob: float, n_sims: int) -> float:
    """MC standard error of a probability estimated from n_sims Bernoulli
    draws, e.g. P(home wins) = fraction of sims where margin > 0."""
    if n_sims <= 0:
        raise ValueError("n_sims must be positive")
    prob = min(max(prob, 0.0), 1.0)
    return float(np.sqrt(prob * (1 - prob) / n_sims))


def sample_mean_se(samples: np.ndarray) -> float:
    """MC standard error of a sample mean (e.g. mean margin) via the usual
    std/sqrt(n) estimator."""
    n = samples.shape[0]
    if n <= 1:
        raise ValueError("need at least 2 samples to estimate SE")
    return float(np.std(samples, ddof=1) / np.sqrt(n))


def needs_more_sims(se: float, threshold: float = DEFAULT_MC_SE_THRESHOLD) -> bool:
    return se > threshold


def n_sims_for_target_se(prob: float, target_se: float = DEFAULT_MC_SE_THRESHOLD) -> int:
    """How many sims are needed to bring a probability's MC SE at/under
    target_se, given the current point estimate. Used to auto-increase
    n_sims on headline markets that came in under-converged."""
    prob = min(max(prob, 1e-6), 1 - 1e-6)
    return int(np.ceil(prob * (1 - prob) / (target_se**2)))

"""Shared contract every sport's model implements.

Deliberately decoupled from the DB/ORM layer: `fit`/`simulate`/`explain` all
take and return plain dicts/dataclasses, not SQLAlchemy objects. That keeps
model code pure and unit-testable without a database, and is what lets the
backtest engine feed it historical fixtures without a live session.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, TypedDict

import numpy as np


class FixtureInput(TypedDict, total=False):
    id: int
    home_team: str
    away_team: str
    venue: str | None
    scheduled_at: str  # ISO8601
    home_score: int | None  # None for future fixtures; required for fit()
    away_score: int | None


@dataclass
class SimulationOutput:
    """Output of one Monte Carlo simulation run for a single fixture."""

    n_sims: int
    seed: int
    home_win_prob: float
    home_win_prob_se: float  # Monte Carlo standard error — see simulation/engine.py
    margin_samples: np.ndarray  # home_score - away_score per sim, shape (n_sims,)
    total_samples: np.ndarray | None = None
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class Driver:
    """One line of the explainability panel: what pushed the model's view
    away from a naive/market baseline, and by roughly how much."""

    factor: str
    detail: str
    impact: float  # signed, same units as the model's home win prob shift


class SportModel(ABC):
    version: str

    @abstractmethod
    def fit(self, fixtures: list[FixtureInput]) -> None:
        """Train/update model state from completed historical fixtures.
        Must be safe to call repeatedly with a growing fixture list (walk-forward)."""
        ...

    @abstractmethod
    def simulate(self, fixture: FixtureInput, n_sims: int, seed: int) -> SimulationOutput:
        """Monte Carlo simulate one fixture. Must be deterministic given the
        same (model state, fixture, n_sims, seed) — reproducibility is mandatory."""
        ...

    @abstractmethod
    def explain(self, fixture: FixtureInput) -> list[Driver]:
        """Top drivers behind the model's view of this fixture, in plain English."""
        ...

"""Margin-of-victory Elo with team-and-venue-specific home ground advantage.

This is the AFL rating engine underneath moneyball/models/afl/model.py. It
does not depend on advanced stats (contested possessions, inside-50s,
clearances) that aren't ingested yet — see README's Phase 3 notes — so it
only needs team names, venue, and final scores, sourced straight from
Squiggle's `games` endpoint.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from moneyball.config.loader import load_afl_config


@dataclass
class TeamVenueStat:
    n: int = 0
    margin_residual_sum: float = 0.0  # sum of (actual_margin - elo_baseline_margin)


class AflEloRatings:
    """HGA is estimated per (team, venue) via empirical Bayes shrinkage toward
    a league-wide default: a team with little history at a ground leans on
    the league prior, while a team with a long home record there (e.g.
    Geelong at GMHBA) gets an estimate closer to its own numbers.
    """

    def __init__(self, config: dict | None = None):
        self.cfg = config or load_afl_config()
        self.ratings: dict[str, float] = {}
        self.team_venue: dict[tuple[str, str], TeamVenueStat] = {}
        self.margin_residuals: list[float] = []
        self.totals: list[float] = []

    def get_rating(self, team: str) -> float:
        return self.ratings.get(team, self.cfg["elo"]["initial_rating"])

    def get_hga_points(self, team: str, venue: str | None) -> float:
        hga_cfg = self.cfg["hga"]
        default = hga_cfg["league_default_points"]
        if not venue:
            return default
        stat = self.team_venue.get((team, venue))
        if not stat or stat.n == 0:
            return default
        shrink_n = hga_cfg["shrinkage_games"]
        weight = stat.n / (stat.n + shrink_n)
        team_estimate = stat.margin_residual_sum / stat.n
        return weight * team_estimate + (1 - weight) * default

    def predicted_margin(self, home: str, away: str, venue: str | None) -> float:
        elo_cfg = self.cfg["elo"]
        elo_diff = self.get_rating(home) - self.get_rating(away)
        hga = self.get_hga_points(home, venue)
        return elo_diff * elo_cfg["margin_per_elo_point"] + hga

    def win_prob(self, home: str, away: str, venue: str | None) -> float:
        elo_cfg = self.cfg["elo"]
        elo_diff = self.get_rating(home) - self.get_rating(away)
        hga_elo_equiv = self.get_hga_points(home, venue) / elo_cfg["margin_per_elo_point"]
        return 1.0 / (1.0 + 10 ** (-(elo_diff + hga_elo_equiv) / 400.0))

    def update(self, home: str, away: str, home_score: int, away_score: int, venue: str | None) -> None:
        elo_cfg = self.cfg["elo"]
        r_home = self.get_rating(home)
        r_away = self.get_rating(away)

        pre_win_prob = self.win_prob(home, away, venue)
        actual_margin = home_score - away_score
        s_home = 1.0 if actual_margin > 0 else (0.5 if actual_margin == 0 else 0.0)

        winner_elo, loser_elo = (r_home, r_away) if actual_margin >= 0 else (r_away, r_home)
        mov_multiplier = math.log(abs(actual_margin) + 1) * (
            elo_cfg["mov_multiplier_base"]
            / ((winner_elo - loser_elo) * elo_cfg["mov_multiplier_scale"] + elo_cfg["mov_multiplier_base"])
        )

        delta = elo_cfg["k_factor"] * mov_multiplier * (s_home - pre_win_prob)
        self.ratings[home] = r_home + delta
        self.ratings[away] = r_away - delta

        if venue:
            baseline_margin = (r_home - r_away) * elo_cfg["margin_per_elo_point"]
            residual = actual_margin - baseline_margin
            stat = self.team_venue.setdefault((home, venue), TeamVenueStat())
            stat.n += 1
            stat.margin_residual_sum += residual

        predicted_margin = self.predicted_margin(home, away, venue)
        self.margin_residuals.append(actual_margin - predicted_margin)
        self.totals.append(float(home_score + away_score))

    def margin_std(self) -> float:
        cfg = self.cfg["margin_distribution"]
        n = len(self.margin_residuals)
        if n <= 1:
            return cfg["residual_std_prior"]
        sample_std = float(np.std(self.margin_residuals, ddof=1))
        shrink_n = cfg["residual_std_shrinkage_games"]
        weight = n / (n + shrink_n)
        return weight * sample_std + (1 - weight) * cfg["residual_std_prior"]

    def total_mean(self) -> float:
        cfg = self.cfg["total_distribution"]
        n = len(self.totals)
        if n == 0:
            return cfg["mean_prior"]
        sample_mean = float(np.mean(self.totals))
        weight = n / (n + cfg["shrinkage_games"])
        return weight * sample_mean + (1 - weight) * cfg["mean_prior"]

    def total_std(self) -> float:
        cfg = self.cfg["total_distribution"]
        n = len(self.totals)
        if n <= 1:
            return cfg["std_prior"]
        sample_std = float(np.std(self.totals, ddof=1))
        weight = n / (n + cfg["shrinkage_games"])
        return weight * sample_std + (1 - weight) * cfg["std_prior"]

"""AFL SportModel: Elo + margin-of-victory ratings, team-and-venue-specific
HGA, Monte Carlo margin/total simulation.

Margin and total are drawn independently (Normal, empirical Bayes-shrunk
mean/std from fit history) — real AFL blowouts skew the margin/total
relationship (routs tend to run higher-scoring), so treating them as
independent is a known simplification, not a claim of correctness. Upgrading
to a fitted bivariate normal (or the full shot-volume x accuracy simulation
from the original spec) is the natural next step once AFL Tables ingestion
provides the underlying shot data — see README.
"""
from __future__ import annotations

from moneyball.config.loader import config_hash, load_afl_config
from moneyball.models.afl.elo import AflEloRatings
from moneyball.models.base import Driver, FixtureInput, SimulationOutput, SportModel
from moneyball.simulation.engine import binary_prob_se, make_rng


class AflModel(SportModel):
    version = "afl-elo-v1"

    def __init__(self, config: dict | None = None):
        self.cfg = config or load_afl_config()
        self.config_hash = config_hash(self.cfg)
        self.ratings = AflEloRatings(config=self.cfg)
        self._fitted_fixture_ids: set[int] = set()

    def fit(self, fixtures: list[FixtureInput]) -> None:
        completed = [
            f
            for f in fixtures
            if f.get("home_score") is not None and f.get("away_score") is not None and f.get("id") not in self._fitted_fixture_ids
        ]
        completed.sort(key=lambda f: f["scheduled_at"])
        for f in completed:
            self.ratings.update(
                home=f["home_team"],
                away=f["away_team"],
                home_score=f["home_score"],  # type: ignore[arg-type]
                away_score=f["away_score"],  # type: ignore[arg-type]
                venue=f.get("venue"),
            )
            if f.get("id") is not None:
                self._fitted_fixture_ids.add(f["id"])  # type: ignore[arg-type]

    def simulate(self, fixture: FixtureInput, n_sims: int, seed: int) -> SimulationOutput:
        rng = make_rng(seed)
        home, away, venue = fixture["home_team"], fixture["away_team"], fixture.get("venue")

        mean_margin = self.ratings.predicted_margin(home, away, venue)
        margin_std = self.ratings.margin_std()
        margin_samples = rng.normal(loc=mean_margin, scale=margin_std, size=n_sims)

        total_mean = self.ratings.total_mean()
        total_std = self.ratings.total_std()
        total_samples = rng.normal(loc=total_mean, scale=total_std, size=n_sims)
        total_samples = total_samples.clip(min=0)  # a negative combined score isn't physical

        home_win_prob = float((margin_samples > 0).mean())
        se = binary_prob_se(home_win_prob, n_sims)

        home_score_samples = (total_samples + margin_samples) / 2
        away_score_samples = (total_samples - margin_samples) / 2

        return SimulationOutput(
            n_sims=n_sims,
            seed=seed,
            home_win_prob=home_win_prob,
            home_win_prob_se=se,
            margin_samples=margin_samples,
            total_samples=total_samples,
            extras={
                "mean_margin": mean_margin,
                "margin_std": margin_std,
                "total_mean": total_mean,
                "total_std": total_std,
                "home_score_samples": home_score_samples,
                "away_score_samples": away_score_samples,
                "home_rating": self.ratings.get_rating(home),
                "away_rating": self.ratings.get_rating(away),
                "hga_points": self.ratings.get_hga_points(home, venue),
            },
        )

    def explain(self, fixture: FixtureInput) -> list[Driver]:
        home, away, venue = fixture["home_team"], fixture["away_team"], fixture.get("venue")
        home_rating = self.ratings.get_rating(home)
        away_rating = self.ratings.get_rating(away)
        hga = self.ratings.get_hga_points(home, venue)
        league_default_hga = self.cfg["hga"]["league_default_points"]

        drivers = [
            Driver(
                factor="Elo rating gap",
                detail=f"{home} rates {home_rating - away_rating:+.0f} Elo points vs {away}",
                impact=home_rating - away_rating,
            ),
            Driver(
                factor="Home ground advantage",
                detail=(
                    f"{home} at {venue or 'this venue'}: {hga:+.1f}pt HGA "
                    f"({'above' if hga > league_default_hga else 'below'} the {league_default_hga:.1f}pt league default)"
                ),
                impact=hga - league_default_hga,
            ),
            Driver(
                factor="Margin uncertainty",
                detail=f"Fitted margin std of {self.ratings.margin_std():.1f} points from {len(self.ratings.margin_residuals)} rated games",
                impact=0.0,
            ),
        ]
        return sorted(drivers, key=lambda d: abs(d.impact), reverse=True)

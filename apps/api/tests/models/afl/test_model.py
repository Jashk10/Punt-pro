import numpy as np
import pytest

from moneyball.models.afl.model import AflModel

FIXTURES = [
    {
        "id": 1,
        "home_team": "Geelong",
        "away_team": "Collingwood",
        "venue": "GMHBA Stadium",
        "scheduled_at": "2024-03-01T19:00:00",
        "home_score": 100,
        "away_score": 80,
    },
    {
        "id": 2,
        "home_team": "Collingwood",
        "away_team": "Geelong",
        "venue": "MCG",
        "scheduled_at": "2024-03-08T19:00:00",
        "home_score": 90,
        "away_score": 95,
    },
]


def test_fit_is_idempotent_on_repeated_fixture_ids():
    model_a = AflModel()
    model_a.fit(FIXTURES)
    rating_after_one_fit = model_a.ratings.get_rating("Geelong")

    model_a.fit(FIXTURES)  # same fixtures again — already-fitted ids must be skipped
    assert model_a.ratings.get_rating("Geelong") == pytest.approx(rating_after_one_fit)


def test_fit_processes_fixtures_in_chronological_order_regardless_of_input_order():
    forward = AflModel()
    forward.fit(FIXTURES)

    backward = AflModel()
    backward.fit(list(reversed(FIXTURES)))

    assert forward.ratings.get_rating("Geelong") == pytest.approx(backward.ratings.get_rating("Geelong"))
    assert forward.ratings.get_rating("Collingwood") == pytest.approx(backward.ratings.get_rating("Collingwood"))


def test_simulate_is_deterministic_given_same_seed():
    model = AflModel()
    model.fit(FIXTURES)
    fixture = {"home_team": "Geelong", "away_team": "Collingwood", "venue": "GMHBA Stadium"}

    out_1 = model.simulate(fixture, n_sims=5000, seed=7)
    out_2 = model.simulate(fixture, n_sims=5000, seed=7)

    assert out_1.home_win_prob == out_2.home_win_prob
    np.testing.assert_array_equal(out_1.margin_samples, out_2.margin_samples)


def test_simulate_different_seeds_give_different_samples_but_similar_probability():
    model = AflModel()
    model.fit(FIXTURES)
    fixture = {"home_team": "Geelong", "away_team": "Collingwood", "venue": "GMHBA Stadium"}

    out_1 = model.simulate(fixture, n_sims=20000, seed=1)
    out_2 = model.simulate(fixture, n_sims=20000, seed=2)

    assert not np.array_equal(out_1.margin_samples, out_2.margin_samples)
    assert abs(out_1.home_win_prob - out_2.home_win_prob) < 0.05


def test_simulate_more_sims_reduces_mc_standard_error():
    model = AflModel()
    model.fit(FIXTURES)
    fixture = {"home_team": "Geelong", "away_team": "Collingwood", "venue": "GMHBA Stadium"}

    small = model.simulate(fixture, n_sims=500, seed=1)
    large = model.simulate(fixture, n_sims=50000, seed=1)

    assert large.home_win_prob_se < small.home_win_prob_se


def test_simulate_home_away_scores_reconstruct_margin_and_total():
    model = AflModel()
    model.fit(FIXTURES)
    fixture = {"home_team": "Geelong", "away_team": "Collingwood", "venue": "GMHBA Stadium"}
    out = model.simulate(fixture, n_sims=1000, seed=3)

    home_scores = out.extras["home_score_samples"]
    away_scores = out.extras["away_score_samples"]

    np.testing.assert_allclose(home_scores - away_scores, out.margin_samples, atol=1e-6)
    np.testing.assert_allclose(home_scores + away_scores, out.total_samples, atol=1e-6)


def test_evenly_matched_teams_with_no_history_simulate_near_fifty_fifty_before_hga():
    # No fit history at all: both teams sit at the initial rating, so the
    # only thing pushing win prob off 0.5 is HGA — sanity-check that it's a
    # small nudge, not a landslide, on default config.
    model = AflModel()
    fixture = {"home_team": "Team A", "away_team": "Team B", "venue": None}
    out = model.simulate(fixture, n_sims=50000, seed=11)
    assert 0.5 < out.home_win_prob < 0.65


def test_explain_returns_drivers_sorted_by_impact_magnitude():
    model = AflModel()
    model.fit(FIXTURES)
    drivers = model.explain({"home_team": "Geelong", "away_team": "Collingwood", "venue": "GMHBA Stadium"})
    impacts = [abs(d.impact) for d in drivers]
    assert impacts == sorted(impacts, reverse=True)
    assert any(d.factor == "Elo rating gap" for d in drivers)

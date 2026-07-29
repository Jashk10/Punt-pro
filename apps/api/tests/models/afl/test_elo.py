import pytest

from moneyball.models.afl.elo import AflEloRatings

BASE_CONFIG = {
    "elo": {
        "initial_rating": 1500.0,
        "k_factor": 32.0,
        "mov_multiplier_base": 2.2,
        "mov_multiplier_scale": 0.001,
        "margin_per_elo_point": 0.6,
    },
    "hga": {"shrinkage_games": 20, "league_default_points": 0.0},  # zeroed for clean known-answer tests
    "margin_distribution": {"residual_std_prior": 37.0, "residual_std_shrinkage_games": 30},
}


def make_ratings(**overrides) -> AflEloRatings:
    import copy

    cfg = copy.deepcopy(BASE_CONFIG)
    for section, values in overrides.items():
        cfg[section].update(values)
    return AflEloRatings(config=cfg)


def test_unrated_teams_default_to_initial_rating():
    ratings = make_ratings()
    assert ratings.get_rating("Unknown Team") == 1500.0


def test_equal_ratings_no_hga_gives_fifty_fifty():
    ratings = make_ratings()
    assert ratings.win_prob("A", "B", venue=None) == pytest.approx(0.5)


def test_higher_rated_team_favoured():
    ratings = make_ratings()
    ratings.ratings["A"] = 1600.0
    ratings.ratings["B"] = 1500.0
    prob = ratings.win_prob("A", "B", venue=None)
    assert prob > 0.5
    # closed form for standard Elo: 1 / (1 + 10^(-diff/400))
    expected = 1.0 / (1.0 + 10 ** (-100 / 400.0))
    assert prob == pytest.approx(expected)


def test_update_is_zero_sum():
    ratings = make_ratings()
    ratings.ratings["A"] = 1550.0
    ratings.ratings["B"] = 1450.0
    before_total = ratings.get_rating("A") + ratings.get_rating("B")
    ratings.update("A", "B", home_score=100, away_score=80, venue=None)
    after_total = ratings.get_rating("A") + ratings.get_rating("B")
    assert after_total == pytest.approx(before_total)


def test_win_increases_winner_rating_loss_decreases_loser_rating():
    ratings = make_ratings()
    ratings.ratings["A"] = 1500.0
    ratings.ratings["B"] = 1500.0
    ratings.update("A", "B", home_score=100, away_score=80, venue=None)
    assert ratings.get_rating("A") > 1500.0
    assert ratings.get_rating("B") < 1500.0


def test_upset_win_moves_rating_more_than_expected_win():
    # Same margin (20 points), but one is a huge underdog winning, the other
    # a big favourite winning as expected — the underdog's win should move
    # ratings by more (that's the entire point of the MOV multiplier).
    upset = make_ratings()
    upset.ratings["A"] = 1400.0
    upset.ratings["B"] = 1700.0
    upset.update("A", "B", home_score=100, away_score=80, venue=None)  # A (underdog) wins
    upset_delta = upset.get_rating("A") - 1400.0

    expected_win = make_ratings()
    expected_win.ratings["A"] = 1700.0
    expected_win.ratings["B"] = 1400.0
    expected_win.update("A", "B", home_score=100, away_score=80, venue=None)  # A (favourite) wins
    expected_delta = expected_win.get_rating("A") - 1700.0

    assert upset_delta > expected_delta > 0


def test_hga_defaults_to_league_value_with_no_venue_history():
    ratings = make_ratings(hga={"league_default_points": 6.0})
    assert ratings.get_hga_points("Geelong", "GMHBA Stadium") == pytest.approx(6.0)


def test_hga_shrinks_toward_teams_own_history_as_games_accumulate():
    # Pin k_factor near zero so ratings don't drift — isolates the HGA
    # mechanism from Elo's own rating separation, which would otherwise
    # "explain away" a consistent margin as pure team strength (unidentifiable
    # from a single, always-at-the-same-venue matchup) rather than home
    # advantage specifically.
    ratings = make_ratings(hga={"league_default_points": 0.0, "shrinkage_games": 20}, elo={"k_factor": 0.001})
    ratings.ratings["Geelong"] = 1500.0
    ratings.ratings["Opponent"] = 1500.0

    # Geelong wins by ~40 at home every time — team-specific HGA should climb
    # toward that margin and away from the (zeroed) league default.
    for _ in range(50):
        ratings.update("Geelong", "Opponent", home_score=120, away_score=80, venue="GMHBA Stadium")

    hga = ratings.get_hga_points("Geelong", "GMHBA Stadium")
    assert hga > 15.0  # well above the zeroed league default, given a consistent ~40pt margin pattern


def test_margin_std_returns_prior_with_no_history():
    ratings = make_ratings()
    assert ratings.margin_std() == pytest.approx(37.0)


def test_margin_std_shrinks_toward_observed_std_with_more_games():
    ratings = make_ratings(margin_distribution={"residual_std_prior": 37.0, "residual_std_shrinkage_games": 30})
    ratings.margin_residuals = [10.0, -10.0, 15.0, -15.0, 5.0, -5.0] * 20  # 120 residuals, sample std ~11.4
    std = ratings.margin_std()
    assert std < 37.0
    assert std > 5.0

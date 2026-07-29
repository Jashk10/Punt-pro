import math

import numpy as np
import pytest

from moneyball.quant.calibration import (
    brier_score,
    expected_calibration_error,
    log_loss,
    model_health,
    reliability_bins,
)


def test_brier_score_perfect_predictions_is_zero():
    assert brier_score(np.array([1.0, 0.0]), np.array([1, 0])) == pytest.approx(0.0)


def test_brier_score_known_value():
    probs = np.array([0.1, 0.1, 0.9, 0.9])
    outcomes = np.array([0, 0, 1, 1])
    assert brier_score(probs, outcomes) == pytest.approx(0.01)


def test_brier_score_always_fifty_fifty_on_fair_coin():
    probs = np.array([0.5] * 1000)
    rng = np.random.default_rng(0)
    outcomes = rng.integers(0, 2, size=1000)
    # not a tight bound — just checks it lands near the textbook 0.25 for a fair coin
    assert brier_score(probs, outcomes) == pytest.approx(0.25, abs=0.03)


def test_log_loss_known_value():
    probs = np.array([0.1, 0.1, 0.9, 0.9])
    outcomes = np.array([0, 0, 1, 1])
    assert log_loss(probs, outcomes) == pytest.approx(-math.log(0.9))


def test_log_loss_confident_correct_near_zero():
    probs = np.array([0.999999999])
    outcomes = np.array([1])
    assert log_loss(probs, outcomes) < 1e-6


def test_log_loss_does_not_blow_up_on_confident_wrong_prediction():
    probs = np.array([1.0])
    outcomes = np.array([0])
    loss = log_loss(probs, outcomes)
    assert math.isfinite(loss)
    assert loss > 30  # heavily penalised but finite, thanks to eps clipping


def test_reliability_bins_known_grouping():
    probs = np.array([0.1, 0.1, 0.9, 0.9])
    outcomes = np.array([0, 0, 1, 1])
    bins = reliability_bins(probs, outcomes, n_bins=10)
    assert len(bins) == 10

    low_bin = next(b for b in bins if b.bin_lower == pytest.approx(0.1))
    assert low_bin.n == 2
    assert low_bin.mean_predicted == pytest.approx(0.1)
    assert low_bin.mean_observed == pytest.approx(0.0)

    high_bin = next(b for b in bins if b.bin_lower == pytest.approx(0.9))
    assert high_bin.n == 2
    assert high_bin.mean_predicted == pytest.approx(0.9)
    assert high_bin.mean_observed == pytest.approx(1.0)

    empty_bins = [b for b in bins if b.n == 0]
    assert len(empty_bins) == 8


def test_expected_calibration_error_known_value():
    probs = np.array([0.1, 0.1, 0.9, 0.9])
    outcomes = np.array([0, 0, 1, 1])
    assert expected_calibration_error(probs, outcomes, n_bins=10) == pytest.approx(0.1)


def test_expected_calibration_error_zero_when_perfectly_calibrated():
    # Every bin's mean predicted prob exactly matches its observed rate.
    probs = np.array([0.2, 0.2, 0.2, 0.2, 0.2])
    outcomes = np.array([1, 0, 0, 0, 0])  # observed rate 0.2 in the 0.2 bin
    assert expected_calibration_error(probs, outcomes, n_bins=10) == pytest.approx(0.0, abs=1e-9)


def test_model_health_green_when_well_calibrated():
    rng = np.random.default_rng(42)
    probs = rng.uniform(0.1, 0.9, size=2000)
    outcomes = (rng.uniform(0, 1, size=2000) < probs).astype(int)  # outcomes truly drawn from probs
    assert model_health(probs, outcomes) == "green"


def test_model_health_red_when_systematically_overconfident():
    # Model says 90% every time; true win rate is only 55% — exactly the
    # "model is broken" scenario from the spec.
    probs = np.array([0.9] * 200)
    rng = np.random.default_rng(1)
    outcomes = (rng.uniform(0, 1, size=200) < 0.55).astype(int)
    assert model_health(probs, outcomes) == "red"


def test_model_health_amber_when_too_few_samples():
    probs = np.array([0.6, 0.7, 0.55])
    outcomes = np.array([1, 1, 0])
    assert model_health(probs, outcomes) == "amber"


def test_shape_mismatch_raises():
    with pytest.raises(ValueError):
        brier_score(np.array([0.5, 0.5]), np.array([1]))

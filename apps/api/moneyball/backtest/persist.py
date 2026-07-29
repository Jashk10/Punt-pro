"""Persists a walk-forward BacktestResult into backtest_runs + calibration_bins.

Kept separate from walkforward.py so the backtest engine itself stays pure
(list[FixtureInput] in, dataclasses out, no DB session) — this is the only
part of the backtest path that touches the ORM.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from moneyball.backtest.walkforward import BacktestResult
from moneyball.config.loader import config_hash
from moneyball.db.models import BacktestRun, CalibrationBin as CalibrationBinRow, JobStatus, ModelVersion, Sport
from moneyball.db.utils import get_or_create


def get_or_create_model_version(db: Session, sport_code: str, name: str, version: str, config: dict) -> ModelVersion:
    sport = db.query(Sport).filter_by(code=sport_code).one()
    mv, _ = get_or_create(
        db,
        ModelVersion,
        sport_id=sport.id,
        name=name,
        version=version,
        defaults={"config_hash": config_hash(config), "params": config, "is_active": True},
    )
    return mv


def persist_backtest_result(
    db: Session,
    model_version: ModelVersion,
    start_date: date,
    end_date: date,
    result: BacktestResult,
    params: dict,
) -> BacktestRun:
    run = BacktestRun(
        model_version_id=model_version.id,
        sport_id=model_version.sport_id,
        start_date=start_date,
        end_date=end_date,
        params=params,
        status=JobStatus.success,
        roi_point=None,  # no ROI yet — needs real historical closing odds (Phase 4)
        roi_ci_low=None,
        roi_ci_high=None,
    )
    db.add(run)
    db.flush()

    for b in result.calibration_bins:
        if b.n == 0:
            continue
        db.add(
            CalibrationBinRow(
                backtest_run_id=run.id,
                model_version_id=model_version.id,
                sport_id=model_version.sport_id,
                market="moneyline",
                bin_lower=b.bin_lower,
                bin_upper=b.bin_upper,
                n=b.n,
                mean_predicted=b.mean_predicted,
                mean_observed=b.mean_observed,
                brier=b.brier,
            )
        )

    db.commit()
    return run

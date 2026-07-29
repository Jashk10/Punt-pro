"""SQLAlchemy models mirroring the schema agreed with the user before Phase 1 began.

Timescale hypertable conversion for odds_snapshots happens in the Alembic migration
(execute_hypertable_create), not here — SQLAlchemy has no native concept of it.
"""
from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum as SAEnum

from moneyball.db.base import Base


class LineupStatus(str, enum.Enum):
    confirmed = "confirmed"
    projected = "projected"
    unknown = "unknown"


class PriceSource(str, enum.Enum):
    live = "live"
    estimated = "estimated"


class BetStatus(str, enum.Enum):
    pending = "pending"
    won = "won"
    lost = "lost"
    void = "void"
    push = "push"


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    success = "success"
    failed = "failed"


class Sport(Base):
    __tablename__ = "sports"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)


class Venue(Base):
    __tablename__ = "venues"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    city: Mapped[str | None] = mapped_column(String(128))
    country: Mapped[str | None] = mapped_column(String(128))
    lat: Mapped[float | None] = mapped_column(Numeric)
    lon: Mapped[float | None] = mapped_column(Numeric)
    altitude_m: Mapped[float | None] = mapped_column(Numeric)
    surface: Mapped[str | None] = mapped_column(String(64))
    roof_type: Mapped[str | None] = mapped_column(String(32))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    is_outdoor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    external_ids: Mapped[dict] = mapped_column(JSONB, default=dict)


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("sport_id", "name", name="uq_team_sport_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sport_id: Mapped[int] = mapped_column(ForeignKey("sports.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(32))
    home_venue_id: Mapped[int | None] = mapped_column(ForeignKey("venues.id"))
    external_ids: Mapped[dict] = mapped_column(JSONB, default=dict)


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sport_id: Mapped[int] = mapped_column(ForeignKey("sports.id"), nullable=False)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    position: Mapped[str | None] = mapped_column(String(32))
    birthdate: Mapped[date | None] = mapped_column(Date)
    debut_date: Mapped[date | None] = mapped_column(Date)
    bats_throws: Mapped[str | None] = mapped_column(String(16))
    external_ids: Mapped[dict] = mapped_column(JSONB, default=dict)


class Fixture(Base):
    __tablename__ = "fixtures"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sport_id: Mapped[int] = mapped_column(ForeignKey("sports.id"), nullable=False, index=True)
    season: Mapped[str] = mapped_column(String(16), nullable=False)
    round: Mapped[str | None] = mapped_column(String(32))
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    venue_id: Mapped[int | None] = mapped_column(ForeignKey("venues.id"))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="scheduled")
    home_score: Mapped[int | None] = mapped_column()
    away_score: Mapped[int | None] = mapped_column()
    external_ids: Mapped[dict] = mapped_column(JSONB, default=dict)


class Lineup(Base):
    __tablename__ = "lineups"
    __table_args__ = (UniqueConstraint("fixture_id", "player_id", name="uq_lineup_fixture_player"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixtures.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    status: Mapped[LineupStatus] = mapped_column(
        SAEnum(LineupStatus, name="lineup_status"), nullable=False, default=LineupStatus.unknown
    )
    role: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_debut: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_first_game_back: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Injury(Base):
    __tablename__ = "injuries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expected_return: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str | None] = mapped_column(String(64))


class WeatherSnapshot(Base):
    __tablename__ = "weather_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fixture_id: Mapped[int | None] = mapped_column(ForeignKey("fixtures.id"), index=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    temp_c: Mapped[float | None] = mapped_column(Numeric)
    wind_speed_kph: Mapped[float | None] = mapped_column(Numeric)
    wind_dir_deg: Mapped[float | None] = mapped_column(Numeric)
    precip_prob: Mapped[float | None] = mapped_column(Numeric)
    humidity_pct: Mapped[float | None] = mapped_column(Numeric)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="open-meteo")


class TeamGameStats(Base):
    __tablename__ = "team_game_stats"
    __table_args__ = (UniqueConstraint("fixture_id", "team_id", name="uq_team_game_stats"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixtures.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    stats: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source: Mapped[str | None] = mapped_column(String(64))


class PlayerGameStats(Base):
    __tablename__ = "player_game_stats"
    __table_args__ = (UniqueConstraint("fixture_id", "player_id", name="uq_player_game_stats"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixtures.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    stats: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source: Mapped[str | None] = mapped_column(String(64))


class OddsSnapshot(Base):
    """Append-only Timescale hypertable. Composite PK enforces immutability by construction."""

    __tablename__ = "odds_snapshots"

    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixtures.id"), primary_key=True)
    book: Mapped[str] = mapped_column(String(64), primary_key=True)
    market: Mapped[str] = mapped_column(String(64), primary_key=True)
    selection: Mapped[str] = mapped_column(String(128), primary_key=True)
    line: Mapped[float | None] = mapped_column(Numeric)
    price_decimal: Mapped[float] = mapped_column(Numeric, nullable=False)
    price_source: Mapped[PriceSource] = mapped_column(
        SAEnum(PriceSource, name="price_source_t"), nullable=False, default=PriceSource.live
    )


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("sport_id", "name", "version", name="uq_model_version"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sport_id: Mapped[int] = mapped_column(ForeignKey("sports.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    params: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelRun(Base):
    __tablename__ = "model_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"), nullable=False)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixtures.id"), nullable=False, index=True)
    seed: Mapped[int] = mapped_column(nullable=False)
    n_sims: Mapped[int] = mapped_column(nullable=False)
    input_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[JobStatus] = mapped_column(SAEnum(JobStatus, name="job_status"), nullable=False, default=JobStatus.queued)
    mc_se: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SimulationResult(Base):
    __tablename__ = "simulation_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    model_run_id: Mapped[int] = mapped_column(ForeignKey("model_runs.id"), nullable=False)
    result_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_path: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[dict | None] = mapped_column(JSONB)


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    model_run_id: Mapped[int] = mapped_column(ForeignKey("model_runs.id"), nullable=False)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixtures.id"), nullable=False, index=True)
    market: Mapped[str] = mapped_column(String(64), nullable=False)
    selection: Mapped[str] = mapped_column(String(128), nullable=False)
    model_prob: Mapped[float] = mapped_column(Numeric, nullable=False)
    model_prob_se: Mapped[float | None] = mapped_column(Numeric)
    market_prob: Mapped[float | None] = mapped_column(Numeric)
    fair_prob: Mapped[float | None] = mapped_column(Numeric)
    devig_method: Mapped[str | None] = mapped_column(String(32))
    edge: Mapped[float | None] = mapped_column(Numeric)
    ev_per_100: Mapped[float | None] = mapped_column(Numeric)
    kelly_fraction: Mapped[float | None] = mapped_column(Numeric)
    confidence_tier: Mapped[str | None] = mapped_column(String(16))
    price_source: Mapped[PriceSource] = mapped_column(
        SAEnum(PriceSource, name="price_source_t"), nullable=False, default=PriceSource.live
    )
    lineup_status: Mapped[LineupStatus] = mapped_column(
        SAEnum(LineupStatus, name="lineup_status"), nullable=False, default=LineupStatus.unknown
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    permissions: Mapped[dict] = mapped_column(JSONB, default=dict)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BankrollLedger(Base):
    __tablename__ = "bankroll_ledger"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    amount: Mapped[float] = mapped_column(Numeric, nullable=False)
    balance_after: Mapped[float] = mapped_column(Numeric, nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    bet_id: Mapped[int | None] = mapped_column()


class Bet(Base):
    __tablename__ = "bets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    stake: Mapped[float] = mapped_column(Numeric, nullable=False)
    odds_decimal: Mapped[float] = mapped_column(Numeric, nullable=False)
    status: Mapped[BetStatus] = mapped_column(SAEnum(BetStatus, name="bet_status"), nullable=False, default=BetStatus.pending)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closing_price: Mapped[float | None] = mapped_column(Numeric)
    clv_pct: Mapped[float | None] = mapped_column(Numeric)
    bankroll_ledger_id: Mapped[int | None] = mapped_column(ForeignKey("bankroll_ledger.id"))


class BetLeg(Base):
    __tablename__ = "bet_legs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bet_id: Mapped[int] = mapped_column(ForeignKey("bets.id"), nullable=False)
    prediction_id: Mapped[int | None] = mapped_column(ForeignKey("predictions.id"))
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixtures.id"), nullable=False)
    market: Mapped[str] = mapped_column(String(64), nullable=False)
    selection: Mapped[str] = mapped_column(String(128), nullable=False)
    leg_odds: Mapped[float] = mapped_column(Numeric, nullable=False)
    result: Mapped[str | None] = mapped_column(String(16))


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"), nullable=False)
    sport_id: Mapped[int] = mapped_column(ForeignKey("sports.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    params: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[JobStatus] = mapped_column(SAEnum(JobStatus, name="job_status"), nullable=False, default=JobStatus.queued)
    roi_point: Mapped[float | None] = mapped_column(Numeric)
    roi_ci_low: Mapped[float | None] = mapped_column(Numeric)
    roi_ci_high: Mapped[float | None] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CalibrationBin(Base):
    __tablename__ = "calibration_bins"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    backtest_run_id: Mapped[int | None] = mapped_column(ForeignKey("backtest_runs.id"))
    model_version_id: Mapped[int | None] = mapped_column(ForeignKey("model_versions.id"))
    sport_id: Mapped[int] = mapped_column(ForeignKey("sports.id"), nullable=False)
    market: Mapped[str] = mapped_column(String(64), nullable=False)
    bin_lower: Mapped[float] = mapped_column(Numeric, nullable=False)
    bin_upper: Mapped[float] = mapped_column(Numeric, nullable=False)
    n: Mapped[int] = mapped_column(nullable=False)
    mean_predicted: Mapped[float] = mapped_column(Numeric, nullable=False)
    mean_observed: Mapped[float] = mapped_column(Numeric, nullable=False)
    brier: Mapped[float | None] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    rotated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class ManualOverride(Base):
    __tablename__ = "manual_overrides"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(String(64), nullable=False)
    record_id: Mapped[str] = mapped_column(String(64), nullable=False)
    field: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    table_name: Mapped[str] = mapped_column(String(64), nullable=False)
    record_id: Mapped[str | None] = mapped_column(String(64))
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

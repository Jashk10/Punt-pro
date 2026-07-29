"""Upserts Squiggle payloads (teams, games) into the shared schema.

Idempotent: re-running against the same year/round updates existing rows
(matched by Squiggle's own game id, stashed in fixtures.external_ids) instead
of duplicating them. Safe to run on a schedule (Celery beat) for in-progress
rounds where scores/status change between polls.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from moneyball.db.models import Fixture, Sport, Team, Venue
from moneyball.db.utils import get_or_create
from moneyball.ingestion.afl.client import SquiggleClient

AFL_SPORT_CODE = "AFL"
DEFAULT_VENUE_TZ = "Australia/Melbourne"


def get_afl_sport(db: Session) -> Sport:
    sport = db.query(Sport).filter_by(code=AFL_SPORT_CODE).one_or_none()
    if sport is None:
        raise RuntimeError(f"Sport row for '{AFL_SPORT_CODE}' is missing — run migrations/seed first")
    return sport


def parse_squiggle_datetime(date_str: str | None, tz_offset: str | None) -> datetime | None:
    """Squiggle's `date` field is local kickoff time (no offset baked in); `tz`
    carries the offset separately, e.g. "+11:00" during AEDT."""
    if not date_str:
        return None
    naive = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    offset = tz_offset or "+10:00"
    sign = -1 if offset.startswith("-") else 1
    hours_str, _, minutes_str = offset.lstrip("+-").partition(":")
    delta = sign * timedelta(hours=int(hours_str), minutes=int(minutes_str or 0))
    return naive.replace(tzinfo=timezone(delta))


def _fixture_status(row: dict) -> str:
    complete = row.get("complete") or 0
    if complete >= 100:
        return "final"
    if complete > 0:
        return "live"
    return "scheduled"


def sync_teams(db: Session, client: SquiggleClient) -> int:
    sport = get_afl_sport(db)
    rows = client.get_teams()
    count = 0
    for row in rows:
        name = row.get("name")
        if not name:
            continue
        team, created = get_or_create(
            db,
            Team,
            sport_id=sport.id,
            name=name,
            defaults={"external_ids": {"squiggle_id": row.get("id")}},
        )
        if not created and row.get("id") is not None and team.external_ids.get("squiggle_id") is None:
            team.external_ids = {**team.external_ids, "squiggle_id": row.get("id")}
        count += 1
    db.flush()
    return count


def _find_fixture_by_squiggle_id(db: Session, sport_id: int, squiggle_game_id: int) -> Fixture | None:
    return (
        db.query(Fixture)
        .filter(
            Fixture.sport_id == sport_id,
            Fixture.external_ids["squiggle_id"].as_integer() == squiggle_game_id,
        )
        .one_or_none()
    )


def sync_games(db: Session, client: SquiggleClient, year: int, round_: int | None = None) -> int:
    sport = get_afl_sport(db)
    rows = client.get_games(year=year, round_=round_)
    count = 0

    for row in rows:
        squiggle_game_id = row.get("id")
        home_name = row.get("hteam")
        away_name = row.get("ateam")
        venue_name = row.get("venue")
        scheduled_at = parse_squiggle_datetime(row.get("date"), row.get("tz"))

        if not (squiggle_game_id and home_name and away_name and scheduled_at):
            continue

        venue = None
        if venue_name:
            venue, _ = get_or_create(
                db, Venue, name=venue_name, defaults={"timezone": DEFAULT_VENUE_TZ, "is_outdoor": True}
            )

        home_team, _ = get_or_create(db, Team, sport_id=sport.id, name=home_name)
        away_team, _ = get_or_create(db, Team, sport_id=sport.id, name=away_name)

        status = _fixture_status(row)
        home_score = row.get("hscore")
        away_score = row.get("ascore")
        round_label = str(row.get("round")) if row.get("round") is not None else None

        existing = _find_fixture_by_squiggle_id(db, sport.id, squiggle_game_id)
        if existing:
            existing.scheduled_at = scheduled_at
            existing.status = status
            existing.home_score = home_score
            existing.away_score = away_score
            existing.round = round_label
            if venue:
                existing.venue_id = venue.id
        else:
            db.add(
                Fixture(
                    sport_id=sport.id,
                    season=str(year),
                    round=round_label,
                    home_team_id=home_team.id,
                    away_team_id=away_team.id,
                    venue_id=venue.id if venue else None,
                    scheduled_at=scheduled_at,
                    status=status,
                    home_score=home_score,
                    away_score=away_score,
                    external_ids={"squiggle_id": squiggle_game_id},
                )
            )
        count += 1

    db.flush()
    return count


def run_full_sync(db: Session, year: int, round_: int | None = None) -> dict:
    with SquiggleClient() as client:
        teams_synced = sync_teams(db, client)
        games_synced = sync_games(db, client, year=year, round_=round_)
    db.commit()
    return {"teams_synced": teams_synced, "games_synced": games_synced, "year": year, "round": round_}

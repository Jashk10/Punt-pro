import pytest
from sqlalchemy.orm import Session as SqlaSession

from moneyball.db.models import Fixture, Sport, Team, Venue
from moneyball.db.session import engine
from moneyball.ingestion.afl.sync import parse_squiggle_datetime, sync_games, sync_teams


class FakeSquiggleClient:
    """Stand-in for SquiggleClient — sync.py only calls these three methods,
    so a duck-typed fake keeps these tests independent of the HTTP layer
    (that's covered separately in test_afl_client.py)."""

    def __init__(self, teams=None, games=None):
        self._teams = teams or []
        self._games = games or []

    def get_teams(self):
        return self._teams

    def get_games(self, year, round_=None):
        return self._games

    def get_tips(self, year, round_=None, source=None):
        return []


@pytest.fixture
def db():
    """Runs the test inside an outer transaction that is always rolled back,
    so it can't leak state into (or be broken by) whatever else is in the
    dev/demo database. sync.py's own `db.commit()` calls only release a
    SAVEPOINT here, not the outer transaction — see join_transaction_mode.
    """
    connection = engine.connect()
    outer_trans = connection.begin()
    session = SqlaSession(bind=connection, join_transaction_mode="create_savepoint")

    if session.query(Sport).filter_by(code="AFL").first() is None:
        session.add(Sport(code="AFL", name="Australian Football League"))
        session.commit()

    yield session

    session.close()
    outer_trans.rollback()
    connection.close()


def afl_sport(db) -> Sport:
    return db.query(Sport).filter_by(code="AFL").one()


def test_parse_squiggle_datetime_applies_offset():
    dt = parse_squiggle_datetime("2024-03-14 19:20:00", "+11:00")
    assert dt is not None
    assert dt.utcoffset().total_seconds() == 11 * 3600
    assert (dt.hour, dt.minute) == (19, 20)


def test_parse_squiggle_datetime_defaults_offset_when_missing():
    dt = parse_squiggle_datetime("2024-03-14 19:20:00", None)
    assert dt is not None
    assert dt.utcoffset().total_seconds() == 10 * 3600


def test_parse_squiggle_datetime_none_when_no_date():
    assert parse_squiggle_datetime(None, "+10:00") is None


def test_sync_teams_creates_and_is_idempotent(db):
    sport = afl_sport(db)
    client = FakeSquiggleClient(teams=[{"id": 3, "name": "Zzz Test Carlton"}, {"id": 14, "name": "Zzz Test Richmond"}])

    first_count = sync_teams(db, client)
    db.commit()
    assert first_count == 2
    names = ["Zzz Test Carlton", "Zzz Test Richmond"]
    assert db.query(Team).filter(Team.sport_id == sport.id, Team.name.in_(names)).count() == 2

    second_count = sync_teams(db, client)
    db.commit()
    assert second_count == 2
    assert db.query(Team).filter(Team.sport_id == sport.id, Team.name.in_(names)).count() == 2  # no duplicates

    carlton = db.query(Team).filter_by(sport_id=sport.id, name="Zzz Test Carlton").one()
    assert carlton.external_ids.get("squiggle_id") == 3


def test_sync_games_creates_fixture_with_venue(db):
    client = FakeSquiggleClient(
        games=[
            {
                "id": 900001,
                "round": 1,
                "hteam": "Zzz Test Carlton",
                "ateam": "Zzz Test Richmond",
                "hscore": 100,
                "ascore": 85,
                "venue": "Zzz Test M.C.G.",
                "date": "2024-03-14 19:20:00",
                "tz": "+11:00",
                "complete": 100,
            }
        ]
    )

    count = sync_games(db, client, year=2024, round_=1)
    db.commit()
    assert count == 1
    assert db.query(Venue).filter_by(name="Zzz Test M.C.G.").count() == 1

    fixture = db.query(Fixture).filter(Fixture.external_ids["squiggle_id"].as_integer() == 900001).one()
    assert fixture.status == "final"
    assert fixture.home_score == 100
    assert fixture.away_score == 85


def test_sync_games_updates_existing_fixture_on_rerun(db):
    live_row = {
        "id": 900002,
        "round": 5,
        "hteam": "Zzz Test Carlton",
        "ateam": "Zzz Test Richmond",
        "hscore": 40,
        "ascore": 35,
        "venue": "Zzz Test M.C.G.",
        "date": "2024-05-01 19:20:00",
        "tz": "+10:00",
        "complete": 60,
    }
    client = FakeSquiggleClient(games=[live_row])
    sync_games(db, client, year=2024, round_=5)
    db.commit()

    fixture = db.query(Fixture).filter(Fixture.external_ids["squiggle_id"].as_integer() == 900002).one()
    assert fixture.status == "live"
    assert fixture.home_score == 40

    final_row = {**live_row, "hscore": 110, "ascore": 90, "complete": 100}
    client_final = FakeSquiggleClient(games=[final_row])
    count = sync_games(db, client_final, year=2024, round_=5)
    db.commit()

    assert count == 1
    matches = db.query(Fixture).filter(Fixture.external_ids["squiggle_id"].as_integer() == 900002).all()
    assert len(matches) == 1  # updated in place, not duplicated
    assert matches[0].status == "final"
    assert matches[0].home_score == 110
    assert matches[0].away_score == 90


def test_sync_games_skips_rows_missing_required_fields(db):
    client = FakeSquiggleClient(games=[{"id": 900003, "hteam": "Zzz Test Carlton"}])  # no ateam/date
    count = sync_games(db, client, year=2024, round_=1)
    db.commit()
    assert count == 0
    assert db.query(Fixture).filter(Fixture.external_ids["squiggle_id"].as_integer() == 900003).count() == 0

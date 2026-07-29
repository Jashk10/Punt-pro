"""Populates one demo slate per sport (AFL, NBA, SOCCER, MLB) so the app is usable
on first run with zero API keys configured. Safe to re-run: it upserts by natural key
instead of blindly inserting duplicates.

Demo fixtures are dated a week out from whenever this runs and are clearly synthetic
(no live odds — they are seeded as price_source='estimated' with a manual/demo book).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from passlib.context import CryptContext
from sqlalchemy.orm import Session

from moneyball.config.settings import get_settings
from moneyball.db.models import (
    Fixture,
    OddsSnapshot,
    PriceSource,
    Role,
    Sport,
    Team,
    User,
    Venue,
)
from moneyball.db.session import SessionLocal
from moneyball.db.utils import get_or_create

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SPORTS = [
    ("AFL", "Australian Football League"),
    ("NBA", "National Basketball Association"),
    ("SOCCER", "Soccer"),
    ("MLB", "Major League Baseball"),
]

# (sport_code, home, away, venue_name, city, country, is_outdoor, tz)
DEMO_FIXTURES = [
    ("AFL", "Geelong Cats", "Collingwood Magpies", "GMHBA Stadium", "Geelong", "Australia", True, "Australia/Melbourne"),
    ("AFL", "Sydney Swans", "West Coast Eagles", "SCG", "Sydney", "Australia", True, "Australia/Sydney"),
    ("NBA", "Boston Celtics", "Denver Nuggets", "TD Garden", "Boston", "USA", False, "America/New_York"),
    ("NBA", "LA Lakers", "Golden State Warriors", "Crypto.com Arena", "Los Angeles", "USA", False, "America/Los_Angeles"),
    ("SOCCER", "Arsenal", "Manchester City", "Emirates Stadium", "London", "England", True, "Europe/London"),
    ("SOCCER", "Real Madrid", "Barcelona", "Santiago Bernabeu", "Madrid", "Spain", True, "Europe/Madrid"),
    ("MLB", "New York Yankees", "Boston Red Sox", "Yankee Stadium", "New York", "USA", True, "America/New_York"),
    ("MLB", "LA Dodgers", "San Francisco Giants", "Dodger Stadium", "Los Angeles", "USA", True, "America/Los_Angeles"),
]

# Demo decimal odds (moneyline/head-to-head), clearly synthetic.
DEMO_ODDS = {
    ("Geelong Cats", "Collingwood Magpies"): (1.65, 2.25),
    ("Sydney Swans", "West Coast Eagles"): (1.30, 3.40),
    ("Boston Celtics", "Denver Nuggets"): (1.75, 2.05),
    ("LA Lakers", "Golden State Warriors"): (2.10, 1.72),
    ("Arsenal", "Manchester City"): (2.60, 2.70),
    ("Real Madrid", "Barcelona"): (2.20, 3.10),
    ("New York Yankees", "Boston Red Sox"): (1.55, 2.45),
    ("LA Dodgers", "San Francisco Giants"): (1.40, 2.95),
}


def seed_roles_and_admin(db: Session) -> None:
    settings = get_settings()
    role_defs = {
        "admin": {"all": True},
        "analyst": {"read": True, "write_predictions": True},
        "user": {"read": True},
    }
    roles = {}
    for name, perms in role_defs.items():
        role, _ = get_or_create(db, Role, name=name, defaults={"permissions": perms})
        roles[name] = role

    existing = db.query(User).filter_by(email=settings.admin_email).one_or_none()
    if not existing:
        db.add(
            User(
                email=settings.admin_email,
                hashed_password=pwd_context.hash(settings.admin_password),
                role_id=roles["admin"].id,
                is_active=True,
            )
        )


def seed_sports(db: Session) -> dict[str, Sport]:
    sports = {}
    for code, name in SPORTS:
        sport, _ = get_or_create(db, Sport, code=code, defaults={"name": name})
        sports[code] = sport
    return sports


def seed_slate(db: Session, sports: dict[str, Sport]) -> None:
    kickoff_base = datetime.now(timezone.utc) + timedelta(days=7)

    for i, (sport_code, home, away, venue_name, city, country, is_outdoor, tz) in enumerate(DEMO_FIXTURES):
        sport = sports[sport_code]

        venue, _ = get_or_create(
            db,
            Venue,
            name=venue_name,
            defaults={"city": city, "country": country, "is_outdoor": is_outdoor, "timezone": tz},
        )

        home_team, _ = get_or_create(db, Team, sport_id=sport.id, name=home, defaults={"home_venue_id": venue.id})
        away_team, _ = get_or_create(db, Team, sport_id=sport.id, name=away)

        scheduled_at = kickoff_base + timedelta(hours=i)

        fixture = (
            db.query(Fixture)
            .filter_by(sport_id=sport.id, home_team_id=home_team.id, away_team_id=away_team.id, season="2026-demo")
            .one_or_none()
        )
        if not fixture:
            fixture = Fixture(
                sport_id=sport.id,
                season="2026-demo",
                round="Demo Slate",
                home_team_id=home_team.id,
                away_team_id=away_team.id,
                venue_id=venue.id,
                scheduled_at=scheduled_at,
                status="scheduled",
            )
            db.add(fixture)
            db.flush()

        home_price, away_price = DEMO_ODDS[(home, away)]
        for selection, price in ((home, home_price), (away, away_price)):
            exists = (
                db.query(OddsSnapshot)
                .filter_by(fixture_id=fixture.id, book="demo-manual", market="moneyline", selection=selection)
                .one_or_none()
            )
            if not exists:
                db.add(
                    OddsSnapshot(
                        ts=datetime.now(timezone.utc),
                        fixture_id=fixture.id,
                        book="demo-manual",
                        market="moneyline",
                        selection=selection,
                        price_decimal=price,
                        price_source=PriceSource.estimated,
                    )
                )


def main() -> None:
    db = SessionLocal()
    try:
        seed_roles_and_admin(db)
        sports = seed_sports(db)
        seed_slate(db, sports)
        db.commit()
        print("Seed complete: 4 sports, 8 demo fixtures, demo odds (AUD decimal), admin user ready.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

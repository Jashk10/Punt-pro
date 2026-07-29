"""odds_snapshots hypertable

Revision ID: ea8c05cb1d22
Revises: cffd2ef13b63
Create Date: 2026-07-29 06:57:34.177982

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ea8c05cb1d22'
down_revision: Union[str, None] = 'cffd2ef13b63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # timescaledb is created in infra/postgres/init.sql on container init; this is
    # belt-and-braces for environments where the migration runs before that hook.
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    op.execute(
        "SELECT create_hypertable('odds_snapshots', 'ts', if_not_exists => TRUE, "
        "migrate_data => TRUE)"
    )
    op.create_index(
        "ix_odds_snapshots_fixture_market_ts",
        "odds_snapshots",
        ["fixture_id", "market", sa.text("ts DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_odds_snapshots_fixture_market_ts", table_name="odds_snapshots")
    # Hypertables cannot be cleanly "un-converted"; downgrade is schema-destructive
    # by design for this table and is not expected to be run in production.

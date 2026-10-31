"""A Product's Usual Shelf Life in days; existing Products have none.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("products", sa.Column("shelf_life_days", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.drop_column("shelf_life_days")

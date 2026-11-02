"""The Stock History: one row per Stock Event; it starts empty, no past is made up.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-02

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stock_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("change", sa.Integer(), nullable=False),
        sa.Column("on", sa.Date(), nullable=False),
        sa.Column("expired", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_events_product_on", "stock_events", ["product_id", "on"])


def downgrade() -> None:
    op.drop_index("ix_stock_events_product_on", table_name="stock_events")
    op.drop_table("stock_events")

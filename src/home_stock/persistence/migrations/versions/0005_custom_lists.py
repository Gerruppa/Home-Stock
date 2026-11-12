"""Custom Lists and their List Lines, kept by hand beside the Shopping List (ADR-0006); they start empty.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "custom_lists",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("occasion", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "list_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("list_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("text", sa.String(), nullable=True),
        sa.Column("bought", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "(product_id IS NOT NULL AND quantity > 0 AND text IS NULL)"
            " OR (product_id IS NULL AND quantity IS NULL AND text IS NOT NULL)",
            name="ck_list_lines_product_or_text",
        ),
        sa.ForeignKeyConstraint(["list_id"], ["custom_lists.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("list_lines")
    op.drop_table("custom_lists")

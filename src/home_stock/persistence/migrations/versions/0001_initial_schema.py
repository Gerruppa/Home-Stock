"""Initial schema: Categories, Units, Products and Batches, with the starting Categories and Units (docs/spec.md).

Revision ID: 0001
Revises:
Create Date: 2026-10-27

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIES = [
    ("Spożywcze", 3),
    ("Napoje", 7),
    ("Chemia i środki czystości", 30),
    ("Higiena i kosmetyki", 30),
    ("Apteczka", 30),
    ("Zwierzęta", 7),
    ("Dom i inne", 30),
]
UNITS = [
    ("sztuka", "szt."),
    ("opakowanie", "opak."),
    ("rolka", "rol."),
    ("butelka", "but."),
    ("puszka", "pusz."),
    ("tubka", "tub."),
    ("słoik", "sł."),
    ("para", "par."),
]


def upgrade() -> None:
    categories = op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("warning_days", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    units = op.create_table(
        "units",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("short", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("name_key", sa.String(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("pack_amount", sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column("pack_measure", sa.String(), nullable=True),
        sa.Column("minimum_stock", sa.Integer(), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name_key"),
    )
    op.create_table(
        "batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("expiry", sa.Date(), nullable=True),
        sa.CheckConstraint("quantity > 0", name="ck_batches_quantity_positive"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.bulk_insert(categories, [{"name": name, "warning_days": days} for name, days in CATEGORIES])
    op.bulk_insert(units, [{"name": name, "short": short} for name, short in UNITS])


def downgrade() -> None:
    op.drop_table("batches")
    op.drop_table("products")
    op.drop_table("units")
    op.drop_table("categories")

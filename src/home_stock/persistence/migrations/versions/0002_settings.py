"""Settings: values kept as text by key, starting with the last version whose "Co nowego" was shown.

A database that already holds Products was used by 0.1.0, the version before settings existed, so it records 0.1.0
as announced, so the first start of a newer version shows its notes; an empty one counts as a fresh install.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    settings = op.create_table(
        "settings",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM products)")).scalar():
        op.bulk_insert(settings, [{"key": "last_announced_version", "value": "0.1.0"}])


def downgrade() -> None:
    op.drop_table("settings")

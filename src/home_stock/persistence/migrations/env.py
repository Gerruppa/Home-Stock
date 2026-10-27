"""Alembic environment.

The app passes its own connection (see ``db.migrate``). The ``alembic`` CLI connects to the user's REAL database
(``paths.database_path()``), so point HOME_STOCK_DATA_DIR at a scratch folder before running it by hand.
"""

from alembic import context
from sqlalchemy import Connection

from home_stock.persistence.db import open_engine
from home_stock.persistence.models import Base
from home_stock.persistence.paths import database_path


def run_migrations(connection: Connection) -> None:
    # batch mode lets ALTER-style changes work on SQLite
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


connection = context.config.attributes.get("connection")
if connection is not None:
    run_migrations(connection)
else:
    with open_engine(database_path()).begin() as cli_connection:
        run_migrations(cli_connection)

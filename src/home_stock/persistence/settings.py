"""Settings kept as text by key."""

from sqlalchemy import Engine, select
from sqlalchemy.dialects.sqlite import insert

from home_stock.persistence.models import SettingRow

# The last app version whose start was recorded, so the first start of a newer one opens its "Co nowego" once
LAST_ANNOUNCED_VERSION = "last_announced_version"


def load_setting(engine: Engine, key: str) -> str | None:
    with engine.connect() as connection:
        return connection.execute(select(SettingRow.value).where(SettingRow.key == key)).scalar_one_or_none()


def save_setting(engine: Engine, key: str, value: str) -> None:
    with engine.begin() as connection:
        connection.execute(
            insert(SettingRow)
            .values(key=key, value=value)
            .on_conflict_do_update(index_elements=[SettingRow.key], set_={"value": value})
        )

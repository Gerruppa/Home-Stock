from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import Engine

from home_stock.domain.stock import ExpiryStatus, expiry_status, is_running_low
from home_stock.persistence.catalog import list_categories
from home_stock.persistence.db import init_db
from home_stock.persistence.products import list_products
from home_stock.sources.demo_data import seed_demo_data

TODAY = date(2026, 10, 27)


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    engine = init_db(tmp_path / "db.sqlite3")
    seed_demo_data(engine, TODAY)
    return engine


def test_demo_data_fills_every_start_section_and_the_shopping_list(engine: Engine) -> None:
    warning_days = {category.id: category.warning_days for category in list_categories(engine)}
    products = list_products(engine)
    statuses = [
        expiry_status(batch, TODAY, warning_days[product.category_id])
        for product in products
        for batch in product.batches
    ]

    assert 8 <= len(products) <= 12
    assert statuses.count(ExpiryStatus.EXPIRED) >= 1
    assert statuses.count(ExpiryStatus.EXPIRING_SOON) >= 2
    assert sum(is_running_low(product) for product in products) >= 2
    assert len(list_products(engine, archived=True)) == 1


def test_demo_data_shows_the_optional_fields(engine: Engine) -> None:
    products = list_products(engine)

    assert any(product.pack_size is not None for product in products)
    assert any(product.minimum_stock is None for product in products)
    assert len({product.category_id for product in products}) >= 4

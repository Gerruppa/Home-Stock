from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import Engine

from home_stock.domain.stock import ExpiryStatus, expiry_status, is_running_low
from home_stock.persistence.catalog import list_categories
from home_stock.persistence.db import init_db
from home_stock.persistence.history import consumption_rates, list_latest_events, waste_by_period
from home_stock.persistence.products import list_products, list_shopping_list
from home_stock.sources.demo_data import ARCHIVED, PRODUCTS, seed_demo_data

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


def test_demo_data_gives_several_products_a_consumption_rate(engine: Engine) -> None:
    assert len(consumption_rates(engine, TODAY)) >= 4


def test_demo_data_puts_a_product_on_the_shopping_list_as_running_out(engine: Engine) -> None:
    running_out = [entry for entry in list_shopping_list(engine, TODAY) if entry.days_left is not None]

    assert running_out
    assert not any(is_running_low(entry.product) for entry in running_out)


def test_demo_data_gives_waste_of_two_products_one_with_expired_units(engine: Engine) -> None:
    lines = waste_by_period(engine, TODAY)[30]

    assert len(lines) >= 2
    assert any(line.expired_units > 0 for line in lines)
    assert any(line.expired_units < line.units for line in lines)


def test_demo_data_dates_the_stock_history_from_the_day_it_starts(tmp_path: Path) -> None:
    today = date(2027, 3, 15)
    engine = init_db(tmp_path / "db.sqlite3")
    seed_demo_data(engine, today)
    events = list_latest_events(engine, limit=1000)

    assert min(event.on for event in events) == today - timedelta(days=62)
    assert max(event.on for event in events) <= today
    assert len(consumption_rates(engine, today)) >= 4


def test_demo_discards_only_products_without_uses() -> None:
    # A Use takes a dated Batch first, so it would eat the Batch meant to be Discarded
    assert not [demo.name for demo in [*PRODUCTS, ARCHIVED] if demo.use_every is not None and demo.discards]

from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import Engine

from home_stock.domain.history import StockEventKind
from home_stock.domain.stock import BatchDraft, ExpiryStatus, expiry_status, is_running_low
from home_stock.persistence.catalog import list_categories
from home_stock.persistence.custom_lists import list_custom_lists, list_lines
from home_stock.persistence.db import init_db
from home_stock.persistence.history import consumption_rates, list_latest_events, waste_by_period
from home_stock.persistence.products import Purchased, list_products, list_shopping_list, purchase
from home_stock.sources import demo_data
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


def test_no_demo_purchase_adds_more_than_twelve_units(engine: Engine) -> None:
    purchases = [event for event in list_latest_events(engine, limit=1000) if event.kind is StockEventKind.PURCHASE]

    assert purchases
    assert max(event.change for event in purchases) <= 12


def test_every_purchase_of_a_product_with_dated_stock_has_an_expiry_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = init_db(tmp_path / "db.sqlite3")
    drafts: list[tuple[int, BatchDraft]] = []

    def recording_purchase(engine: Engine, product_id: int, draft: BatchDraft, on: date) -> Purchased:
        drafts.append((product_id, draft))
        return purchase(engine, product_id, draft, on)

    monkeypatch.setattr(demo_data, "purchase", recording_purchase)
    seed_demo_data(engine, TODAY)
    names = {product.id: product.name for product in [*list_products(engine), *list_products(engine, archived=True)]}
    dated = {demo.name for demo in [*PRODUCTS, ARCHIVED] if any(days is not None for _, days in demo.batches)}

    undated = [names[product_id] for product_id, draft in drafts if names[product_id] in dated and draft.expiry is None]
    assert not undated
    # Not only the stock today: the history's Purchases too
    assert len([product_id for product_id, _ in drafts if names[product_id] == "Woda mineralna"]) > 1


def test_no_product_has_more_than_half_of_the_latest_events(engine: Engine) -> None:
    [(_, most)] = Counter(event.product_id for event in list_latest_events(engine, limit=50)).most_common(1)

    assert most <= 25


def test_uses_take_only_the_history_and_leave_the_stock_today(engine: Engine) -> None:
    stock = {
        product.name: Counter((batch.quantity, batch.expiry) for batch in product.batches)
        for product in list_products(engine)
    }

    for demo in PRODUCTS:
        expected = Counter(
            (quantity, None if days is None else TODAY + timedelta(days=days)) for quantity, days in demo.batches
        )
        assert stock[demo.name] == expected, demo.name


def test_demo_discards_only_products_without_uses() -> None:
    # A Use takes a dated Batch first, so it would eat the Batch meant to be Discarded
    assert not [demo.name for demo in [*PRODUCTS, ARCHIVED] if demo.use_every is not None and demo.discards]


def test_demo_data_has_a_custom_list_for_a_dinner(engine: Engine) -> None:
    [dinner] = list_custom_lists(engine)
    lines = list_lines(engine, dinner.id)

    assert dinner.name == "Kolacja w sobotę"
    assert dinner.occasion is not None and dinner.occasion > TODAY
    assert any(line.product_id is not None for line in lines)
    assert any(line.text is not None for line in lines)

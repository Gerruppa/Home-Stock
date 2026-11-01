from datetime import date

import pytest

from home_stock.domain.stock import (
    Batch,
    BatchDraft,
    ExpiryStatus,
    Product,
    ProductDraft,
    default_expiry,
    expiry_status,
    is_running_low,
    name_key,
    suggested_purchase,
    units_to_use,
    use_order,
)


def batch(batch_id: int, quantity: int, expiry: date | None = None) -> Batch:
    return Batch(batch_id, 1, quantity, expiry)


def product(batches: tuple[Batch, ...] = (), minimum_stock: int | None = None) -> Product:
    return Product(1, "Mleko", 1, 1, None, minimum_stock, False, batches)


def test_quantity_is_the_sum_of_batches() -> None:
    assert product(batches=(batch(1, 2), batch(2, 3))).quantity == 5


def test_running_low_at_or_below_minimum() -> None:
    assert is_running_low(product(batches=(batch(1, 1),), minimum_stock=1))
    assert not is_running_low(product(batches=(batch(1, 2),), minimum_stock=1))


def test_no_minimum_stock_is_never_running_low() -> None:
    assert not is_running_low(product(batches=(), minimum_stock=None))


def test_expiry_status_boundaries() -> None:
    today = date(2026, 10, 27)
    assert expiry_status(batch(1, 1, date(2026, 10, 26)), today, 3) is ExpiryStatus.EXPIRED
    assert expiry_status(batch(1, 1, date(2026, 10, 27)), today, 3) is ExpiryStatus.EXPIRING_SOON
    assert expiry_status(batch(1, 1, date(2026, 10, 30)), today, 3) is ExpiryStatus.EXPIRING_SOON
    assert expiry_status(batch(1, 1, date(2026, 10, 31)), today, 3) is ExpiryStatus.FRESH
    assert expiry_status(batch(1, 1, None), today, 3) is None


def test_use_order_puts_nearest_expiry_first_then_undated_older_first() -> None:
    undated, late, soon, newer_undated = (
        batch(1, 1, None),
        batch(2, 1, date(2026, 11, 12)),
        batch(3, 1, date(2026, 10, 30)),
        batch(4, 1, None),
    )
    assert sorted([newer_undated, undated, late, soon], key=use_order) == [soon, late, undated, newer_undated]


def test_units_to_use_empties_each_batch_in_use_order_before_the_next() -> None:
    undated, late, soon = batch(1, 4, None), batch(2, 5, date(2026, 11, 12)), batch(3, 2, date(2026, 10, 30))
    assert units_to_use([undated, late, soon], 3) == [(soon, 2), (late, 1)]
    assert units_to_use([undated, late, soon], 9) == [(soon, 2), (late, 5), (undated, 2)]


def test_suggested_purchase() -> None:
    assert suggested_purchase(product(batches=(batch(1, 1),), minimum_stock=2)) == 2
    assert suggested_purchase(product(batches=(batch(1, 5),), minimum_stock=2)) == 1
    assert suggested_purchase(product(batches=(), minimum_stock=None)) == 1


def test_name_key_ignores_case_and_spaces() -> None:
    assert name_key("  Mleko   2% ") == name_key("mleko 2%") == "mleko 2%"


def test_drafts_validate() -> None:
    with pytest.raises(ValueError, match="Podaj nazwę produktu."):
        ProductDraft("  ", 1, 1)
    with pytest.raises(ValueError, match="ujemny"):
        ProductDraft("Cukier", 1, 1, minimum_stock=-1)
    with pytest.raises(ValueError, match="większą od zera"):
        BatchDraft(0)
    assert ProductDraft(" Cukier ", 1, 1).name == "Cukier"


@pytest.mark.parametrize("days", [0, -3, 3651])
def test_a_usual_shelf_life_outside_one_day_to_ten_years_is_refused(days: int) -> None:
    with pytest.raises(ValueError, match="od 1 do 3650"):
        ProductDraft("Mleko", 1, 1, usual_shelf_life_days=days)


def test_default_expiry_is_today_plus_the_usual_shelf_life() -> None:
    assert default_expiry(7, date(2026, 10, 27)) == date(2026, 11, 3)
    assert default_expiry(None, date(2026, 10, 27)) is None

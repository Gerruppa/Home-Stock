from datetime import date
from fractions import Fraction

import pytest

from home_stock.domain.stock import (
    Batch,
    BatchDraft,
    ExpiryStatus,
    Product,
    ProductDraft,
    ShoppingListEntry,
    default_expiry,
    expiry_status,
    is_running_low,
    is_running_out,
    name_key,
    shopping_list,
    suggested_minimum_stock,
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


def test_without_a_rate_the_purchase_gets_one_above_minimum_stock() -> None:
    assert suggested_purchase(product(batches=(batch(1, 1),), minimum_stock=2), None, 7) == 2
    assert suggested_purchase(product(batches=(batch(1, 5),), minimum_stock=2), None, 7) == 1
    assert suggested_purchase(product(batches=(), minimum_stock=None), None, 7) == 1


def test_with_a_rate_the_purchase_covers_the_buffer_above_minimum_stock() -> None:
    # Half a Unit a day over a Buffer of 7: 3.5, so 4 Units above the Minimum Stock of 2, 1 already there
    assert suggested_purchase(product(batches=(batch(1, 1),), minimum_stock=2), Fraction(1, 2), 7) == 5
    # No Minimum Stock: the Buffer alone, 2 Units for a fifth of a Unit a day
    assert suggested_purchase(product(batches=(batch(1, 1),), minimum_stock=None), Fraction(1, 5), 7) == 1
    assert suggested_purchase(product(batches=(batch(1, 20),), minimum_stock=2), Fraction(1, 2), 7) == 1


@pytest.mark.parametrize(("rate", "minimum_stock"), [(Fraction(1), None), (Fraction(2), None), (Fraction(2), 1)])
def test_buying_the_suggested_purchase_takes_the_product_off_the_shopping_list(
    rate: Fraction, minimum_stock: int | None
) -> None:
    empty = _stocked(1, 0, minimum_stock=minimum_stock)
    bought = _stocked(1, suggested_purchase(empty, rate, 7), minimum_stock=minimum_stock)

    assert shopping_list([bought], {1: rate}, 7) == []


def test_suggested_minimum_stock_is_the_rate_over_the_buffer_rounded_up() -> None:
    assert suggested_minimum_stock(Fraction(1, 2), 7) == 4
    assert suggested_minimum_stock(Fraction(2), 7) == 14
    assert suggested_minimum_stock(Fraction(1, 100), 7) == 1


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


def _stocked(product_id: int, quantity: int, minimum_stock: int | None = None) -> Product:
    return Product(product_id, f"P{product_id}", 1, 1, None, minimum_stock, False, (batch(product_id, quantity),))


def test_the_shopping_list_holds_products_running_low_or_running_out() -> None:
    low = _stocked(1, 1, minimum_stock=2)
    running_out = _stocked(2, 6, minimum_stock=2)  # 1 a day: 6 days left, within a Buffer of 7
    lasting = _stocked(3, 8, minimum_stock=2)  # 8 days left
    no_forecast = _stocked(4, 3)
    rates = {2: Fraction(1), 3: Fraction(1)}

    entries = shopping_list([low, running_out, lasting, no_forecast], rates, 7)

    assert entries == [ShoppingListEntry(low), ShoppingListEntry(running_out, days_left=6)]


def test_running_out_is_days_left_at_or_below_the_buffer() -> None:
    assert is_running_out(_stocked(1, 7), Fraction(1), 7)
    assert not is_running_out(_stocked(1, 8), Fraction(1), 7)
    assert not is_running_out(_stocked(1, 0), None, 7)


def test_a_product_both_running_low_and_out_is_listed_as_running_low() -> None:
    low = _stocked(1, 1, minimum_stock=2)

    assert shopping_list([low], {1: Fraction(1)}, 7) == [ShoppingListEntry(low)]

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import Engine

from home_stock.domain.custom_lists import CustomListDraft, ListLineDraft
from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.persistence.custom_lists import (
    CustomListInUseError,
    LineBoughtError,
    MissingCustomListError,
    MissingListLineError,
    add_line,
    buy_lines,
    change_line,
    delete_custom_list,
    delete_line,
    edit_custom_list,
    get_line,
    list_custom_lists,
    list_lines,
    make_custom_list,
    restore_custom_list,
    restore_lines,
    tick_line,
    undo_add_line,
    undo_buy_lines,
    undo_make_custom_list,
)
from home_stock.persistence.db import init_db
from home_stock.persistence.history import list_product_events
from home_stock.persistence.products import (
    MissingBatchError,
    ProductInUseError,
    ProductsInUseError,
    add_product,
    add_products,
    get_product,
    remove_new_products,
    undo_add_product,
    use_units,
)

SPOZYWCZE = 1
SZTUKA = 1
TODAY = date(2026, 11, 12)


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


def test_lists_are_ordered_by_date_undated_last_then_by_name(engine: Engine) -> None:
    make_custom_list(engine, CustomListDraft("Wyjazd"))
    make_custom_list(engine, CustomListDraft("Kolacja", date(2026, 11, 15)))
    make_custom_list(engine, CustomListDraft("Grill"))
    make_custom_list(engine, CustomListDraft("Urodziny", date(2026, 11, 14)))

    assert [(lst.name, lst.occasion) for lst in list_custom_lists(engine)] == [
        ("Urodziny", date(2026, 11, 14)),
        ("Kolacja", date(2026, 11, 15)),
        ("Grill", None),
        ("Wyjazd", None),
    ]


def test_a_list_name_is_trimmed_and_cannot_be_blank() -> None:
    assert CustomListDraft("  Kolacja   w sobotę ").name == "Kolacja w sobotę"
    with pytest.raises(ValueError, match="Podaj nazwę listy."):
        CustomListDraft("   ")


def test_product_and_free_text_lines_come_in_the_order_added(engine: Engine) -> None:
    smietana = add_product(engine, ProductDraft("Śmietana", SPOZYWCZE, SZTUKA))
    kolacja = make_custom_list(engine, CustomListDraft("Kolacja"))

    add_line(engine, kolacja, ListLineDraft.product(smietana, 2))
    add_line(engine, kolacja, ListLineDraft.note("  świeczki "))

    lines = list_lines(engine, kolacja)
    assert [(line.product_id, line.quantity, line.text, line.bought) for line in lines] == [
        (smietana, 2, None, False),
        (None, None, "świeczki", False),
    ]


def test_the_same_product_adds_to_its_line_and_undo_takes_the_quantity_back(engine: Engine) -> None:
    smietana = add_product(engine, ProductDraft("Śmietana", SPOZYWCZE, SZTUKA))
    kolacja = make_custom_list(engine, CustomListDraft("Kolacja"))
    add_line(engine, kolacja, ListLineDraft.product(smietana, 2))

    added = add_line(engine, kolacja, ListLineDraft.product(smietana, 3))

    [line] = list_lines(engine, kolacja)
    assert line.quantity == 5
    undo_add_line(engine, added)
    [line] = list_lines(engine, kolacja)
    assert line.quantity == 2


def test_undo_removes_a_new_line(engine: Engine) -> None:
    kolacja = make_custom_list(engine, CustomListDraft("Kolacja"))
    added = add_line(engine, kolacja, ListLineDraft.note("świeczki"))

    undo_add_line(engine, added)

    assert list_lines(engine, kolacja) == []
    with pytest.raises(MissingListLineError, match="Tej pozycji już nie ma."):
        undo_add_line(engine, added)


def test_the_same_product_on_another_list_gets_its_own_line(engine: Engine) -> None:
    smietana = add_product(engine, ProductDraft("Śmietana", SPOZYWCZE, SZTUKA))
    kolacja = make_custom_list(engine, CustomListDraft("Kolacja"))
    grill = make_custom_list(engine, CustomListDraft("Grill"))

    add_line(engine, kolacja, ListLineDraft.product(smietana, 2))
    add_line(engine, grill, ListLineDraft.product(smietana, 1))

    assert [line.quantity for line in list_lines(engine, kolacja)] == [2]
    assert [line.quantity for line in list_lines(engine, grill)] == [1]


@pytest.mark.parametrize("quantity", [0, -1])
def test_a_product_line_needs_a_quantity_of_at_least_one(quantity: int) -> None:
    with pytest.raises(ValueError, match="Ilość musi być liczbą całkowitą większą od zera."):
        ListLineDraft.product(1, quantity)


def test_a_free_text_line_cannot_be_blank() -> None:
    with pytest.raises(ValueError, match="Wpisz, co kupić."):
        ListLineDraft.note("  ")


def test_a_line_on_a_list_gone_meanwhile_is_refused(engine: Engine) -> None:
    kolacja = make_custom_list(engine, CustomListDraft("Kolacja"))
    undo_make_custom_list(engine, kolacja)

    with pytest.raises(MissingCustomListError, match="Tej listy już nie ma."):
        add_line(engine, kolacja, ListLineDraft.note("świeczki"))
    assert list_custom_lists(engine) == []


def test_undoing_a_new_list_is_refused_once_it_has_a_line(engine: Engine) -> None:
    kolacja = make_custom_list(engine, CustomListDraft("Kolacja"))
    add_line(engine, kolacja, ListLineDraft.note("świeczki"))

    with pytest.raises(CustomListInUseError, match="na liście są już pozycje"):
        undo_make_custom_list(engine, kolacja)
    assert [lst.id for lst in list_custom_lists(engine)] == [kolacja]


def test_a_product_named_by_a_line_is_not_removed(engine: Engine) -> None:
    smietana = add_product(engine, ProductDraft("Śmietana", SPOZYWCZE, SZTUKA))
    [chleb] = add_products(engine, [ProductDraft("Chleb", SPOZYWCZE, SZTUKA)])
    kolacja = make_custom_list(engine, CustomListDraft("Kolacja"))
    add_line(engine, kolacja, ListLineDraft.product(smietana, 1))
    add_line(engine, kolacja, ListLineDraft.product(chleb, 1))

    with pytest.raises(ProductInUseError):
        undo_add_product(engine, smietana)
    with pytest.raises(ProductsInUseError):
        remove_new_products(engine, [chleb])


def _dinner(engine: Engine) -> tuple[int, int, int]:
    """Kolacja with a Śmietana line (2) and a free-text line; returns the Product and the two line ids."""
    smietana = add_product(engine, ProductDraft("Śmietana", SPOZYWCZE, SZTUKA))
    kolacja = make_custom_list(engine, CustomListDraft("Kolacja", date(2026, 11, 15)))
    product_line = add_line(engine, kolacja, ListLineDraft.product(smietana, 2)).line_id
    note_line = add_line(engine, kolacja, ListLineDraft.note("świeczki")).line_id
    return smietana, product_line, note_line


def test_ticking_a_free_text_line_marks_it_bought_and_undo_unmarks_it(engine: Engine) -> None:
    _, _, note_line = _dinner(engine)

    bought = tick_line(engine, note_line)

    assert get_line(engine, note_line).bought
    with pytest.raises(LineBoughtError, match="Ta pozycja jest już kupiona."):
        tick_line(engine, note_line)
    undo_buy_lines(engine, bought)
    assert not get_line(engine, note_line).bought


def test_buying_a_product_line_records_a_purchase_and_marks_it_in_one_go(engine: Engine) -> None:
    smietana, product_line, _ = _dinner(engine)

    bought = buy_lines(engine, [(product_line, BatchDraft(3, date(2026, 11, 20)))], TODAY)

    assert get_line(engine, product_line).bought
    assert get_product(engine, smietana).quantity == 3
    assert [event.change for event in list_product_events(engine, smietana)] == [3]
    undo_buy_lines(engine, bought)
    assert not get_line(engine, product_line).bought
    assert get_product(engine, smietana).quantity == 0
    assert list_product_events(engine, smietana) == []


def test_buying_a_line_gone_meanwhile_records_nothing(engine: Engine) -> None:
    smietana, product_line, _ = _dinner(engine)
    delete_line(engine, product_line)

    with pytest.raises(MissingListLineError):
        buy_lines(engine, [(product_line, BatchDraft(1))], TODAY)
    assert get_product(engine, smietana).quantity == 0


def test_undoing_a_purchase_whose_batch_is_gone_changes_nothing(engine: Engine) -> None:
    smietana, product_line, _ = _dinner(engine)
    bought = buy_lines(engine, [(product_line, BatchDraft(1))], TODAY)
    use_units(engine, smietana, 1, TODAY)

    with pytest.raises(MissingBatchError):
        undo_buy_lines(engine, bought)
    assert get_line(engine, product_line).bought


def test_a_line_s_quantity_or_text_changes_and_changes_back(engine: Engine) -> None:
    smietana, product_line, note_line = _dinner(engine)

    before = change_line(engine, product_line, ListLineDraft.product(smietana, 5))
    change_line(engine, note_line, ListLineDraft.note("świece"))

    assert get_line(engine, product_line).quantity == 5
    assert get_line(engine, note_line).text == "świece"
    change_line(engine, product_line, before)
    assert get_line(engine, product_line).quantity == 2


def test_a_deleted_line_comes_back_as_it_was(engine: Engine) -> None:
    _, product_line, _ = _dinner(engine)
    original = get_line(engine, product_line)

    deleted = delete_line(engine, product_line)

    with pytest.raises(MissingListLineError):
        get_line(engine, product_line)
    restore_lines(engine, [deleted])
    assert get_line(engine, product_line) == original


def test_a_list_is_renamed_and_re_dated_and_back(engine: Engine) -> None:
    kolacja = make_custom_list(engine, CustomListDraft("Kolacja", date(2026, 11, 15)))

    before = edit_custom_list(engine, kolacja, CustomListDraft("Kolacja u mamy"))

    assert [(lst.name, lst.occasion) for lst in list_custom_lists(engine)] == [("Kolacja u mamy", None)]
    edit_custom_list(engine, kolacja, before)
    assert [(lst.name, lst.occasion) for lst in list_custom_lists(engine)] == [("Kolacja", date(2026, 11, 15))]


def test_a_deleted_list_comes_back_with_every_line_bought_or_not(engine: Engine) -> None:
    _, product_line, note_line = _dinner(engine)
    tick_line(engine, note_line)
    [kolacja] = list_custom_lists(engine)
    lines = list_lines(engine, kolacja.id)

    deleted = delete_custom_list(engine, kolacja.id)

    assert list_custom_lists(engine) == []
    with pytest.raises(MissingListLineError):
        get_line(engine, product_line)
    restore_custom_list(engine, deleted)
    assert list_custom_lists(engine) == [kolacja]
    assert list_lines(engine, kolacja.id) == lines


def test_editing_or_deleting_a_list_gone_meanwhile_is_refused(engine: Engine) -> None:
    kolacja = make_custom_list(engine, CustomListDraft("Kolacja"))
    delete_custom_list(engine, kolacja)

    with pytest.raises(MissingCustomListError):
        edit_custom_list(engine, kolacja, CustomListDraft("Grill"))
    with pytest.raises(MissingCustomListError):
        delete_custom_list(engine, kolacja)

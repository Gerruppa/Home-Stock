from datetime import date
from decimal import Decimal
from pathlib import Path

import flet as ft
import pytest
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, PackSize, ProductDraft
from home_stock.mobile.shell import Shell
from home_stock.mobile.start import StartTab
from home_stock.mobile.theme import EXPIRED, EXPIRING, TO_BUY
from home_stock.persistence.db import init_db
from home_stock.persistence.products import add_product, get_product, list_products
from mobile_ui import Screen, absent, find, select, tap, texts

SPOZYWCZE, APTECZKA = 1, 5
SZTUKA, OPAKOWANIE = 1, 2
SHOPPING_TAB = 2
TODAY = date(2026, 10, 27)


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


@pytest.fixture
def screen() -> Screen:
    return Screen()


def _add(engine: Engine, name: str, expiry: date, category: int = SPOZYWCZE, quantity: int = 1) -> int:
    return add_product(engine, ProductDraft(name, category, SZTUKA), BatchDraft(quantity, expiry))


def _shell(engine: Engine, screen: Screen) -> Shell:
    return Shell(engine, screen.present, screen.update, screen.views, screen.copy, screen.share, today=lambda: TODAY)


def _lines(section: ft.Control) -> list[list[str]]:
    """Each line of a section, top to bottom: a Product's name and detail, or "Nic tutaj." alone."""
    column = find(section, f"{section.key}-lines")
    assert isinstance(column, ft.Column)
    return [texts(line) for line in column.controls]


def _title(body: ft.Control, section: str) -> str | None:
    title = find(body, f"{section}-title")
    assert isinstance(title, ft.Text)
    return title.value


def test_the_app_opens_on_start(engine: Engine, screen: Screen) -> None:
    shell = _shell(engine, screen)

    assert shell.navigation_bar.selected_index == 0
    assert isinstance(shell.tabs[0][2], StartTab)
    assert shell.body.content is shell.tabs[0][2].control


def test_no_products_at_all_is_all_clear(engine: Engine, screen: Screen) -> None:
    body = _shell(engine, screen).body

    assert texts(body) == ["Wszystko w porządku."]


def test_expired_and_expiring_by_warning_window(engine: Engine, screen: Screen) -> None:
    _add(engine, "Jogurt", date(2026, 10, 26), quantity=2)
    _add(engine, "Ser", date(2026, 10, 30))
    _add(engine, "Mleko", date(2026, 10, 27))
    _add(engine, "Szynka", date(2026, 10, 31))
    _add(engine, "Aspiryna", date(2026, 11, 20), category=APTECZKA)

    body = _shell(engine, screen).body

    expired = find(body, "expired")
    assert _title(body, "expired") == "Przeterminowane"
    assert _lines(expired) == [["Jogurt", "2 szt., termin 26.10.2026"]]
    expiring = find(body, "expiring")
    assert _title(body, "expiring") == "Kończy się termin"
    assert {line[0] for line in _lines(expiring)} == {"Mleko", "Ser", "Aspiryna"}
    assert ["Aspiryna", "1 szt., termin 20.11.2026"] in _lines(expiring)
    assert "Szynka" not in texts(body)
    assert _lines(find(body, "running-low")) == [["Nic tutaj."]]
    assert "Wszystko w porządku." not in texts(body)


def test_expiring_lines_run_soonest_first(engine: Engine, screen: Screen) -> None:
    _add(engine, "Ser", date(2026, 10, 30))
    _add(engine, "Mleko", date(2026, 10, 27))
    _add(engine, "Aspiryna", date(2026, 11, 20), category=APTECZKA)

    body = _shell(engine, screen).body

    assert _lines(find(body, "expiring")) == [
        ["Mleko", "1 szt., termin 27.10.2026"],
        ["Ser", "1 szt., termin 30.10.2026"],
        ["Aspiryna", "1 szt., termin 20.11.2026"],
    ]


def test_do_kupienia_lists_products_running_low(engine: Engine, screen: Screen) -> None:
    kg = PackSize(Decimal(1), "kg")
    add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE, kg, minimum_stock=3), BatchDraft(3))
    add_product(engine, ProductDraft("Pieprz", SPOZYWCZE, SZTUKA))

    body = _shell(engine, screen).body

    running_low = find(body, "running-low")
    assert _title(body, "running-low") == "Do kupienia"
    assert _lines(running_low) == [["Cukier", "3 opak. (3 kg), minimum 3 opak."]]
    assert _lines(find(body, "expired")) == [["Nic tutaj."]]


def test_each_section_title_is_in_its_urgency_colour(engine: Engine, screen: Screen) -> None:
    _add(engine, "Jogurt", date(2026, 10, 26))

    body = _shell(engine, screen).body

    for key, colour in (("expired", EXPIRED), ("expiring", EXPIRING), ("running-low", TO_BUY)):
        title = find(body, f"{key}-title")
        assert isinstance(title, ft.Text)
        assert title.color == colour


def test_a_purchase_on_the_shopping_list_clears_do_kupienia(engine: Engine, screen: Screen) -> None:
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE, minimum_stock=1), BatchDraft(1))
    shell = _shell(engine, screen)
    assert ["Cukier", "1 opak., minimum 1 opak."] in _lines(find(shell.body, "running-low"))

    select(shell.navigation_bar, SHOPPING_TAB)
    tap(find(shell.body, f"bought-{cukier}"))
    tap(find(screen.top, "purchase-save"))
    select(shell.navigation_bar, 0)

    assert texts(shell.body) == ["Wszystko w porządku."]


@pytest.mark.parametrize(
    ("name", "line"),
    [("Jogurt", "start-batch-{batch}"), ("Mleko", "start-batch-{batch}"), ("Cukier", "start-low-{product}")],
)
def test_each_start_line_opens_its_products_card(engine: Engine, screen: Screen, name: str, line: str) -> None:
    _add(engine, "Jogurt", date(2026, 10, 26))
    _add(engine, "Mleko", date(2026, 10, 28))
    add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE, minimum_stock=1), BatchDraft(1))
    [product] = [p for p in list_products(engine) if p.name == name]
    key = line.format(batch=product.batches[0].id, product=product.id)
    body = _shell(engine, screen).body

    tap(find(body, key))

    assert name in texts(find(screen.top, "product-card"))


def test_discarding_the_expired_batch_from_the_card_clears_przeterminowane(engine: Engine, screen: Screen) -> None:
    jogurt = _add(engine, "Jogurt", date(2026, 10, 26))
    [batch] = get_product(engine, jogurt).batches
    # Keeps the sections on Start once Jogurt's line goes
    _add(engine, "Mleko", date(2026, 10, 28))
    body = _shell(engine, screen).body

    tap(find(body, f"start-batch-{batch.id}"))
    tap(find(screen.top, f"discard-{batch.id}"))

    assert _lines(find(body, "expired")) == [["Nic tutaj."]]
    assert absent(body, f"start-batch-{batch.id}")


def test_a_purchase_from_the_card_above_the_minimum_clears_do_kupienia(engine: Engine, screen: Screen) -> None:
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE, minimum_stock=1), BatchDraft(1))
    # Keeps the sections on Start once Cukier's line goes
    _add(engine, "Mleko", date(2026, 10, 28))
    body = _shell(engine, screen).body

    tap(find(body, f"start-low-{cukier}"))
    tap(find(screen.top, "card-purchase"))
    quantity = find(screen.top, "purchase-quantity")
    assert isinstance(quantity, ft.TextField)
    quantity.value = "2"
    tap(find(screen.top, "purchase-save"))

    assert _lines(find(body, "running-low")) == [["Nic tutaj."]]
    assert get_product(engine, cukier).quantity == 3

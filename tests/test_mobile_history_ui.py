from datetime import date
from pathlib import Path

import flet as ft
import pytest
from sqlalchemy import Engine

from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.mobile.shell import Shell
from home_stock.persistence.db import init_db
from home_stock.persistence.products import add_product, discard_batch, purchase, use_one
from mobile_ui import Screen, absent, find, select, tap, texts, walk

SPOZYWCZE = 1
SZTUKA, OPAKOWANIE = 1, 2
HISTORY_TAB = 3
MONDAY, TUESDAY = date(2026, 11, 2), date(2026, 11, 3)


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return init_db(tmp_path / "db.sqlite3")


@pytest.fixture
def screen() -> Screen:
    return Screen()


def _shell(engine: Engine, screen: Screen, today: date = TUESDAY) -> Shell:
    return Shell(
        engine,
        screen.present,
        screen.update,
        screen.views,
        screen.copy,
        screen.share,
        screen.open_url,
        today=lambda: today,
    )


def _open(engine: Engine, screen: Screen, today: date = TUESDAY) -> ft.Control:
    """The Historia tab of a fresh shell, as the user sees it after tapping its destination."""
    shell = _shell(engine, screen, today)
    select(shell.navigation_bar, HISTORY_TAB)
    return shell.body


def _lines(root: ft.Control, key: str) -> list[str]:
    """What each control with ``key`` shows, in page order."""
    return [" ".join(texts(c)) for c in walk(root) if c.key == key]


def _search(body: ft.Control, value: str) -> None:
    search = find(body, "history-search")
    search.value = value  # type: ignore[attr-defined]
    tap(search, "on_change")


def _discarded(engine: Engine, product_id: int, draft: BatchDraft, bought: date, thrown: date) -> None:
    [batch] = purchase(engine, product_id, draft, bought).batches
    discard_batch(engine, batch.id, thrown)


def test_with_no_events_the_history_says_it_is_empty(engine: Engine, screen: Screen) -> None:
    add_product(engine, ProductDraft("Pieprz", SPOZYWCZE, SZTUKA))

    body = _open(engine, screen)

    assert texts(find(body, "history-list")) == ["Historia jest pusta."]


def test_lists_the_events_of_all_products_newest_first(engine: Engine, screen: Screen) -> None:
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE))
    maka = add_product(engine, ProductDraft("Mąka", SPOZYWCZE, SZTUKA))
    purchase(engine, cukier, BatchDraft(3), MONDAY)
    purchase(engine, maka, BatchDraft(2), MONDAY)
    use_one(engine, cukier, TUESDAY)

    body = _open(engine, screen)

    assert _lines(body, "history-event") == [
        "03.11.2026 Cukier Zużycie −1 opak.",
        "02.11.2026 Mąka Zakup +2 szt.",
        "02.11.2026 Cukier Zakup +3 opak.",
    ]


def test_typing_part_of_a_name_keeps_only_that_products_events(engine: Engine, screen: Screen) -> None:
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE))
    maka = add_product(engine, ProductDraft("Mąka", SPOZYWCZE, SZTUKA))
    purchase(engine, cukier, BatchDraft(3), MONDAY)
    purchase(engine, maka, BatchDraft(2), MONDAY)
    body = _open(engine, screen)
    updates = screen.updates

    _search(body, "MĄK")

    assert _lines(body, "history-event") == ["02.11.2026 Mąka Zakup +2 szt."]
    assert screen.updates > updates


def test_a_use_elsewhere_and_its_cofnij_show_up_in_the_history(engine: Engine, screen: Screen) -> None:
    cukier = add_product(engine, ProductDraft("Cukier", SPOZYWCZE, OPAKOWANIE), BatchDraft(2))
    shell = _shell(engine, screen)
    select(shell.navigation_bar, 1)

    tap(find(shell.body, f"use-{cukier}"))
    select(shell.navigation_bar, HISTORY_TAB)
    assert _lines(shell.body, "history-event") == ["03.11.2026 Cukier Zużycie −1 opak."]

    tap(screen.presented[-1], "on_action")

    assert absent(shell.body, "history-event")
    assert texts(find(shell.body, "history-list")) == ["Historia jest pusta."]


def test_waste_lists_each_products_discarded_units_most_first_for_30_and_90_days(
    engine: Engine, screen: Screen
) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA))
    chleb = add_product(engine, ProductDraft("Chleb", SPOZYWCZE, SZTUKA))
    # 8 days ago, 12 days past its date: Expired
    _discarded(engine, mleko, BatchDraft(3, date(2026, 10, 13)), date(2026, 10, 1), date(2026, 10, 25))
    # 74 days ago: in the 90 days only
    _discarded(engine, mleko, BatchDraft(3), date(2026, 8, 1), date(2026, 8, 20))
    _discarded(engine, chleb, BatchDraft(5), date(2026, 10, 30), date(2026, 10, 31))
    # A Use is no Waste
    purchase(engine, chleb, BatchDraft(4), date(2026, 10, 30))
    use_one(engine, chleb, date(2026, 11, 1))

    body = _open(engine, screen, MONDAY)

    assert _lines(body, "history-waste-30-line") == [
        "Chleb 5 szt. (przeterminowane: 0)",
        "Mleko 3 szt. (przeterminowane: 3)",
    ]
    assert _lines(body, "history-waste-90-line") == [
        "Mleko 6 szt. (przeterminowane: 3)",
        "Chleb 5 szt. (przeterminowane: 0)",
    ]
    assert texts(find(body, "history-waste-30"))[0] == "Marnowanie: ostatnie 30 dni"


def test_with_no_discards_in_a_period_waste_says_nothing_was_thrown_away(engine: Engine, screen: Screen) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA))
    _discarded(engine, mleko, BatchDraft(2), date(2026, 8, 1), date(2026, 8, 20))
    chleb = add_product(engine, ProductDraft("Chleb", SPOZYWCZE, SZTUKA), BatchDraft(1))
    use_one(engine, chleb, MONDAY)

    body = _open(engine, screen, MONDAY)

    assert "Nic nie wyrzucono." in texts(find(body, "history-waste-30"))
    assert "Nic nie wyrzucono." not in texts(find(body, "history-waste-90"))
    assert "Mleko" in texts(find(body, "history-waste-90"))


def test_the_name_filter_leaves_waste_as_it_is(engine: Engine, screen: Screen) -> None:
    mleko = add_product(engine, ProductDraft("Mleko", SPOZYWCZE, SZTUKA))
    _discarded(engine, mleko, BatchDraft(2), date(2026, 10, 20), date(2026, 10, 25))
    body = _open(engine, screen, MONDAY)

    _search(body, "Chleb")

    assert texts(find(body, "history-list")) == ["Brak zdarzeń pasujących produktów."]
    assert "Mleko" in texts(find(body, "history-waste-30"))

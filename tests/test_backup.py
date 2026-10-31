from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from home_stock.domain.stock import BatchDraft, ProductDraft
from home_stock.persistence.backup import KEEP_BACKUPS, backup_database
from home_stock.persistence.catalog import list_categories, list_units
from home_stock.persistence.db import init_db, open_engine
from home_stock.persistence.products import add_product, list_products, purchase


def test_no_backup_before_the_database_exists(tmp_path: Path) -> None:
    backups = tmp_path / "backups"

    assert backup_database(tmp_path / "home_stock.sqlite3", backups) is None
    assert not backups.exists()


def test_backup_holds_the_products_and_batches(tmp_path: Path) -> None:
    db_path = tmp_path / "home_stock.sqlite3"
    engine = init_db(db_path)
    draft = ProductDraft("Mleko 2%", list_categories(engine)[0].id, list_units(engine)[0].id)
    product_id = add_product(engine, draft, BatchDraft(3, date(2026, 11, 5)))
    purchase(engine, product_id, BatchDraft(2))
    engine.dispose()

    backup = backup_database(db_path, tmp_path / "backups")

    assert backup is not None and backup.parent == tmp_path / "backups"
    backup_engine = open_engine(backup)
    [product] = list_products(backup_engine)
    backup_engine.dispose()
    assert product.name == "Mleko 2%"
    assert [(batch.quantity, batch.expiry) for batch in product.batches] == [(3, date(2026, 11, 5)), (2, None)]


def test_backups_in_the_same_second_get_names_that_sort_oldest_first(tmp_path: Path) -> None:
    db_path = tmp_path / "home_stock.sqlite3"
    init_db(db_path).dispose()
    moment = datetime(2026, 10, 31, 9, 15, 0, tzinfo=UTC)

    made = [backup_database(db_path, tmp_path / "backups", moment) for _ in range(3)]

    assert [path.name for path in made if path] == [
        "home_stock-20261031-091500Z.sqlite3",
        "home_stock-20261031-091500Z_01.sqlite3",
        "home_stock-20261031-091500Z_02.sqlite3",
    ]
    assert sorted((tmp_path / "backups").iterdir()) == made


def test_only_the_newest_backups_are_kept(tmp_path: Path) -> None:
    db_path = tmp_path / "home_stock.sqlite3"
    init_db(db_path).dispose()
    first = datetime(2026, 10, 1, tzinfo=UTC)

    made = [
        backup_database(db_path, tmp_path / "backups", first + timedelta(days=day)) for day in range(KEEP_BACKUPS + 1)
    ]

    assert sorted((tmp_path / "backups").iterdir()) == made[1:]


def test_a_file_the_user_put_among_the_backups_is_neither_counted_nor_removed(tmp_path: Path) -> None:
    db_path = tmp_path / "home_stock.sqlite3"
    init_db(db_path).dispose()
    backups = tmp_path / "backups"
    backups.mkdir()
    own = backups / "home_stock-before-restore.sqlite3"
    own.write_bytes(b"")
    first = datetime(2026, 10, 1, tzinfo=UTC)

    made = [backup_database(db_path, backups, first + timedelta(days=day)) for day in range(KEEP_BACKUPS)]

    assert sorted(backups.iterdir()) == sorted([own, *(path for path in made if path)])

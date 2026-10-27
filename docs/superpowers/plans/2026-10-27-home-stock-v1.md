# Home Stock v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the whole of `docs/spec.md`: Products with Batches, Use / Purchase / Discard / Archive with undo, the Shopping List, Expiry reminders and the four tabs, on a migrated SQLite database, with `--demo`.

**Architecture:** Four layers as in KAPITA: `domain/` holds frozen dataclasses and pure rules (Running Low, Expiry Status, which Batch a Use takes, Polish formatting); `persistence/` maps them to SQLite through SQLAlchemy with Alembic migrations (the first one also seeds Categories and Units); `ui/` is a NiceGUI shell with four tabs that all redraw after any change; `sources/` holds only the demo data. Every UI function takes a `Context` (engine, today, redraw, undo).

**Tech Stack:** Python 3.14, NiceGUI 3 (native window via pywebview), SQLAlchemy 2, Alembic, platformdirs, pytest + pytest-asyncio + NiceGUI `user_simulation`, mypy strict, ruff.

**Spec:** `docs/spec.md` (terms: `GLOSSARY.md`; decisions: `docs/adr/0001`, `docs/adr/0002`)

## Global Constraints

- Work on branch `feat/home-stock-v1`; one PR to `main` at the end.
- Python `>=3.14`; run everything with `.venv/Scripts/python.exe` (no activation).
- `domain/` never imports nicegui, sqlalchemy, alembic or webview (`tests/test_architecture.py`).
- UI text Polish; code, table and column names, docs English. Every error the user sees is a Polish sentence.
- Quantities and Minimum Stock are whole numbers of Units; weight/volume only as Pack Size (ADR-0001).
- Reminders only inside the app: no notifications, no background process (ADR-0002).
- Dates are shown and typed as `DD.MM.RRRR` (e.g. `30.10.2026`).
- The schema changes only through a migration in `src/home_stock/persistence/migrations/versions/`; `tests/test_database.py` fails on drift.
- The database lives in `platformdirs.user_data_dir("Home Stock", appauthor=False)`; `HOME_STOCK_DATA_DIR` overrides it. Never in the repo.
- UI tests use `nicegui.testing.user_simulation` and find elements by `.mark(...)` markers; keep markers unique per page.
- Before each commit: `.venv/Scripts/python.exe -m ruff check .`, `... -m ruff format .`, `... -m mypy` and the touched test files pass.

## Review Focus

1. Typing `1,5`, `abc`, `-1` or nothing into a Quantity or Minimum Stock field: a Polish error under the field, nothing saved (Task 1 `parse_count` tests, Task 6 form test).
2. A date like `31.02.2026` or `2026-10-30`: refused with "Podaj datę w formacie DD.MM.RRRR." (Task 1 `parse_date` tests).
3. "−1" on a Product at 0: the button is disabled and nothing changes (Task 4 `use_one` returns None, Task 5 UI test).
4. "Mleko " or "MLEKO" when "Mleko" exists, also when renaming: treated as the same name (Task 1 `name_key`, Task 4 duplicate tests including rename).
5. A Batch expiring today is Expiring Soon, not Expired; a Product without Minimum Stock at 0 is not on the Shopping List (Task 1 tests).

---

## File Structure

```
src/home_stock/
  app.py                     # parse_args, demo database, main (Task 10)
  domain/stock.py            # Category, Unit, PackSize, Product, Batch, drafts, rules (Task 1)
  domain/formatting.py       # Polish dates, counts, Pack Size, Quantity text (Task 1)
  persistence/paths.py       # data_dir, database_path (Task 2)
  persistence/db.py          # open_engine, init_db, migrate (Task 2)
  persistence/models.py      # SQLAlchemy tables (Task 2)
  persistence/migrations/    # env.py, script.py.mako, versions/0001_initial_schema.py (Task 2)
  persistence/catalog.py     # Categories and Units (Task 3)
  persistence/products.py    # Products and Batches (Task 4)
  sources/demo_data.py       # seed_demo_data (Task 10)
  ui/context.py              # Context (Task 5)
  ui/shell.py                # build_shell: tabs, undo bar, overlay (Task 5)
  ui/products.py             # Produkty tab (Task 5)
  ui/product_form.py         # add / edit Product dialog (Task 6)
  ui/purchase_dialog.py      # Purchase dialog (Task 7)
  ui/product_card.py         # Product card with Batches (Task 7)
  ui/start.py                # Start tab (Task 8)
  ui/shopping.py             # Lista zakupów tab (Task 8)
  ui/settings.py             # Ustawienia tab (Task 9)
tests/
  conftest.py, test_stock_domain.py, test_formatting.py, test_database.py, test_paths.py,
  test_catalog.py, test_products.py, test_products_ui.py, test_product_form_ui.py,
  test_product_card_ui.py, test_start_ui.py, test_shopping_ui.py, test_settings_ui.py, test_app.py
```

---

### Task 1: Domain rules and formatting

**Files:**
- Create: `src/home_stock/domain/stock.py`, `src/home_stock/domain/formatting.py`
- Create: `tests/conftest.py`, `tests/test_stock_domain.py`, `tests/test_formatting.py`

**Interfaces:**
- Produces (`domain/stock.py`):
  - `MEASURES = ("g", "kg", "ml", "l")`
  - `@dataclass(frozen=True) Category(id: int, name: str, warning_days: int)`
  - `@dataclass(frozen=True) Unit(id: int, name: str, short: str)` (`short` is used after numbers: `"opak."`)
  - `@dataclass(frozen=True) PackSize(amount: Decimal, measure: str)`
  - `@dataclass(frozen=True) Batch(id: int, product_id: int, quantity: int, expiry: date | None)`
  - `@dataclass(frozen=True) BatchDraft(quantity: int, expiry: date | None = None)`: `quantity < 1` raises `ValueError("Ilość musi być liczbą całkowitą większą od zera.")`
  - `@dataclass(frozen=True) ProductDraft(name: str, category_id: int, unit_id: int, pack_size: PackSize | None = None, minimum_stock: int | None = None)`: name is stripped (`object.__setattr__`); empty raises `ValueError("Podaj nazwę produktu.")`; `minimum_stock < 0` raises `ValueError("Stan minimalny nie może być ujemny.")`
  - `@dataclass(frozen=True) Product(id: int, name: str, category_id: int, unit_id: int, pack_size: PackSize | None, minimum_stock: int | None, archived: bool, batches: tuple[Batch, ...])` with property `quantity -> int` (sum of Batches)
  - `class ExpiryStatus(Enum): FRESH, EXPIRING_SOON, EXPIRED`
  - `name_key(name: str) -> str`: stripped, inner whitespace collapsed to one space, `casefold()`
  - `is_running_low(product: Product) -> bool`: `minimum_stock is not None and quantity <= minimum_stock`
  - `expiry_status(batch: Batch, today: date, warning_days: int) -> ExpiryStatus | None`: None without expiry; `expiry < today` EXPIRED; `expiry <= today + warning_days` EXPIRING_SOON; else FRESH
  - `batch_to_use(batches: Sequence[Batch]) -> Batch | None`: nearest expiry first, Batches without expiry last, ties by lowest id; None when empty
  - `suggested_purchase(product: Product) -> int`: `max(1, minimum_stock + 1 - quantity)`, or 1 without Minimum Stock
- Produces (`domain/formatting.py`):
  - `format_date(value: date) -> str` → `"30.10.2026"`
  - `parse_date(text: str) -> date | None`: blank → None; `D.M.RRRR` with optional leading zeros; anything else (incl. `31.02.2026`, `2026-10-30`) raises `ValueError("Podaj datę w formacie DD.MM.RRRR.")`
  - `parse_count(text: str, *, allow_blank: bool = False) -> int | None`: digits only after strip; blank → None if `allow_blank`, else error; otherwise `ValueError("Podaj liczbę całkowitą, np. 2.")`
  - `parse_pack_size(text: str) -> PackSize | None`: blank → None; `"1 kg"`, `"0,5 l"`, `"500g"`, `"1.5 L"` (comma or dot, optional space, measure case-insensitive, amount > 0); else `ValueError("Podaj rozmiar opakowania, np. 1 kg albo 500 ml.")`
  - `format_decimal(value: Decimal) -> str`: no trailing zeros, comma separator (`Decimal("1.50")` → `"1,5"`, `Decimal("2")` → `"2"`)
  - `format_pack_size(size: PackSize) -> str` → `"0,5 l"`
  - `format_quantity(quantity: int, unit: Unit, pack_size: PackSize | None) -> str` → `"2 opak. (2 kg)"`, without Pack Size `"4 rol."`

- [ ] **Step 1: Set up the environment**

Run: `py -3.14 -m venv .venv`, then `.venv/Scripts/python.exe -m pip install -e ".[dev]"`, then `.venv/Scripts/python.exe -m pre_commit install`, then `git checkout -b feat/home-stock-v1`.
Expected: `.venv/Scripts/python.exe -m pytest` → 1 passed (`test_architecture.py`).

- [ ] **Step 2: Write `tests/conftest.py`**

Copy KAPITA's `pytest_collection_modifyitems` hook (`D:\PythonProject\FinancialApp\tests\conftest.py:12-17`) that marks modules importing `user_simulation` with `pytest.mark.ui`; register the marker in `pyproject.toml` `[tool.pytest.ini_options] markers = ["ui: drives the UI through NiceGUI's user_simulation"]`.

- [ ] **Step 3: Write the failing tests**

`tests/test_stock_domain.py` (build Products with a helper `product(batches=(), minimum_stock=None)`):

```python
def test_running_low_at_or_below_minimum():
    assert is_running_low(product(batches=(batch(1, 1),), minimum_stock=1))
    assert not is_running_low(product(batches=(batch(1, 2),), minimum_stock=1))


def test_no_minimum_stock_is_never_running_low():
    assert not is_running_low(product(batches=(), minimum_stock=None))


def test_expiry_status_boundaries():
    today = date(2026, 10, 27)
    assert expiry_status(batch(1, 1, date(2026, 10, 26)), today, 3) is ExpiryStatus.EXPIRED
    assert expiry_status(batch(1, 1, date(2026, 10, 27)), today, 3) is ExpiryStatus.EXPIRING_SOON
    assert expiry_status(batch(1, 1, date(2026, 10, 30)), today, 3) is ExpiryStatus.EXPIRING_SOON
    assert expiry_status(batch(1, 1, date(2026, 10, 31)), today, 3) is ExpiryStatus.FRESH
    assert expiry_status(batch(1, 1, None), today, 3) is None


def test_batch_to_use_takes_nearest_expiry_then_undated():
    undated, late, soon = batch(1, 1, None), batch(2, 1, date(2026, 11, 12)), batch(3, 1, date(2026, 10, 30))
    assert batch_to_use([undated, late, soon]) == soon
    assert batch_to_use([undated, batch(4, 1, None)]) == undated
    assert batch_to_use([]) is None


def test_suggested_purchase():
    assert suggested_purchase(product(batches=(batch(1, 1),), minimum_stock=2)) == 2
    assert suggested_purchase(product(batches=(batch(1, 5),), minimum_stock=2)) == 1
    assert suggested_purchase(product(batches=(), minimum_stock=None)) == 1


def test_name_key_ignores_case_and_spaces():
    assert name_key("  Mleko   2% ") == name_key("mleko 2%") == "mleko 2%"


def test_drafts_validate():
    with pytest.raises(ValueError, match="Podaj nazwę produktu."):
        ProductDraft("  ", 1, 1)
    with pytest.raises(ValueError, match="ujemny"):
        ProductDraft("Cukier", 1, 1, minimum_stock=-1)
    with pytest.raises(ValueError, match="większą od zera"):
        BatchDraft(0)
    assert ProductDraft(" Cukier ", 1, 1).name == "Cukier"
```

`tests/test_formatting.py`:

```python
def test_dates():
    assert format_date(date(2026, 10, 3)) == "03.10.2026"
    assert parse_date("3.10.2026") == date(2026, 10, 3)
    assert parse_date(" ") is None
    for bad in ("31.02.2026", "2026-10-30", "jutro"):
        with pytest.raises(ValueError, match="DD.MM.RRRR"):
            parse_date(bad)


def test_counts():
    assert parse_count(" 3 ") == 3
    assert parse_count("", allow_blank=True) is None
    for bad in ("1,5", "abc", "-1", ""):
        with pytest.raises(ValueError, match="liczbę całkowitą"):
            parse_count(bad)


def test_pack_sizes():
    assert parse_pack_size("0,5 l") == PackSize(Decimal("0.5"), "l")
    assert parse_pack_size("500G") == PackSize(Decimal("500"), "g")
    assert parse_pack_size("") is None
    for bad in ("1 szklanka", "0 kg", "kg"):
        with pytest.raises(ValueError, match="rozmiar opakowania"):
            parse_pack_size(bad)


def test_format_quantity():
    opak, but = Unit(1, "opakowanie", "opak."), Unit(2, "butelka", "but.")
    assert format_quantity(2, opak, PackSize(Decimal("1"), "kg")) == "2 opak. (2 kg)"
    assert format_quantity(3, but, PackSize(Decimal("0.5"), "l")) == "3 but. (1,5 l)"
    assert format_quantity(4, opak, None) == "4 opak."
```

- [ ] **Step 4: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stock_domain.py tests/test_formatting.py`
Expected: FAIL, `ModuleNotFoundError: home_stock.domain.stock`

- [ ] **Step 5: Implement `domain/stock.py` and `domain/formatting.py`** with the interfaces above.

- [ ] **Step 6: Run to verify they pass**

Run: same command, plus `tests/test_architecture.py`. Expected: all PASS; mypy and ruff clean.

- [ ] **Step 7: Commit**: `git add -A && git commit -m "Add stock domain rules and Polish formatting"`

---

### Task 2: Database, paths and the initial migration

**Files:**
- Create: `src/home_stock/persistence/paths.py`, `db.py`, `models.py`, `migrations/env.py`, `migrations/script.py.mako`, `migrations/versions/0001_initial_schema.py`
- Modify: `pyproject.toml` (`[tool.setuptools.package-data] home_stock = ["persistence/migrations/*.py", "persistence/migrations/*.mako", "persistence/migrations/versions/*.py"]`)
- Test: `tests/test_database.py`, `tests/test_paths.py`

**Interfaces:**
- Produces:
  - `paths.DATA_DIR_ENV = "HOME_STOCK_DATA_DIR"`, `paths.data_dir() -> Path`, `paths.database_path() -> Path` (`data_dir() / "home_stock.sqlite3"`)
  - `db.open_engine(path: Path) -> Engine` (creates the folder; turns on `PRAGMA foreign_keys=ON` for each connection through an `event.listens_for(engine, "connect")` hook)
  - `db.init_db(path: Path) -> Engine`, `db.migrate(engine: Engine) -> None`: copy KAPITA's `persistence/db.py` and `migrations/env.py` (`render_as_batch=True`, connection passed in `config.attributes["connection"]`)
  - `models.Base` and tables (SQLAlchemy 2 `Mapped` style):
    - `categories(id PK, name String unique not null, warning_days Integer not null)`
    - `units(id PK, name String unique not null, short String not null)`
    - `products(id PK, name String not null, name_key String unique not null, category_id FK categories.id not null, unit_id FK units.id not null, pack_amount Numeric(10,3) null, pack_measure String null, minimum_stock Integer null, archived Boolean not null default false)`
    - `batches(id PK, product_id FK products.id ON DELETE CASCADE not null, quantity Integer not null CHECK quantity > 0, expiry Date null)`
  - Migration `0001` creates the four tables and inserts (in this order, ids 1..n) the Categories `Spożywcze 3, Napoje 7, Chemia i środki czystości 30, Higiena i kosmetyki 30, Apteczka 30, Zwierzęta 7, Dom i inne 30` and the Units `sztuka/szt., opakowanie/opak., rolka/rol., butelka/but., puszka/pusz., tubka/tub., słoik/sł., para/par.`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_database.py
def test_models_match_migrations(tmp_path):
    engine = init_db(tmp_path / "db.sqlite3")
    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []


def test_first_run_seeds_categories_and_units(tmp_path):
    engine = init_db(tmp_path / "db.sqlite3")
    with engine.connect() as c:
        assert c.execute(text("select name, warning_days from categories order by id")).all()[0] == ("Spożywcze", 3)
        assert c.execute(text("select count(*) from categories")).scalar() == 7
        assert c.execute(text("select name, short from units order by id")).all()[1] == ("opakowanie", "opak.")
        assert c.execute(text("select count(*) from products")).scalar() == 0


def test_init_db_twice_keeps_data(tmp_path): ...  # second init_db on the same file: still 7 categories


# tests/test_paths.py
def test_env_overrides_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME_STOCK_DATA_DIR", str(tmp_path))
    assert database_path() == tmp_path / "home_stock.sqlite3"
```

- [ ] **Step 2: Run to verify they fail** (`ModuleNotFoundError`)
- [ ] **Step 3: Implement** `paths.py`, `db.py`, `models.py`, `env.py`, `script.py.mako` (Alembic's default template) and `0001_initial_schema.py` (hand-written `op.create_table` plus `op.bulk_insert` for the seed rows).
- [ ] **Step 4: Run to verify they pass**: `.venv/Scripts/python.exe -m pytest tests/test_database.py tests/test_paths.py`
- [ ] **Step 5: Commit**: `git commit -m "Add SQLite schema with seeded Categories and Units"`

---

### Task 3: Categories and Units repository

**Files:**
- Create: `src/home_stock/persistence/catalog.py`
- Test: `tests/test_catalog.py`

**Interfaces:**
- Consumes: `Category`, `Unit` (Task 1); `init_db`, models (Task 2)
- Produces:
  - `class StockError(Exception)`: the message is the Polish text for the user (defined here, reused by Task 4)
  - `list_categories(engine) -> list[Category]` (by name), `add_category(engine, name: str, warning_days: int) -> int`, `update_category(engine, category_id: int, name: str, warning_days: int) -> None`, `delete_category(engine, category_id: int) -> None`
  - `list_units(engine) -> list[Unit]` (by name), `add_unit(engine, name: str, short: str) -> int`, `update_unit(engine, unit_id: int, name: str, short: str) -> None`, `delete_unit(engine, unit_id: int) -> None`
  - Errors: blank name `"Podaj nazwę."`; `warning_days < 0` `"Liczba dni nie może być ujemna."`; duplicate (by `name_key`, also on rename to another row's name) `"Kategoria o tej nazwie już istnieje."` / `"Jednostka o tej nazwie już istnieje."`; delete while any Product (archived too) uses it `"Nie można usunąć kategorii, do której należą produkty."` / `"Nie można usunąć jednostki, której używają produkty."`

- [ ] **Step 1: Write the failing tests** in `tests/test_catalog.py` with an `engine` fixture (`init_db(tmp_path / "db.sqlite3")`):
  - `test_add_rename_and_delete_unused_category`: add `"Ogród", 14`, rename to `"Ogród i balkon", 20`, delete; `list_categories` reflects each step.
  - `test_duplicate_category_name_is_refused`: `add_category(engine, "spożywcze ", 3)` raises `StockError` matching `"już istnieje"`; renaming Napoje to `"SPOŻYWCZE"` likewise.
  - `test_category_in_use_cannot_be_deleted`: insert a Product row into Spożywcze with SQL (Task 4 does not exist yet), archived = 1; `delete_category` raises matching `"należą produkty"`.
  - The same three for Units.
- [ ] **Step 2: Run to verify they fail**
- [ ] **Step 3: Implement `catalog.py`**
- [ ] **Step 4: Run to verify they pass**: `.venv/Scripts/python.exe -m pytest tests/test_catalog.py`
- [ ] **Step 5: Commit**: `git commit -m "Add Categories and Units repository"`

---

### Task 4: Products and Batches repository

**Files:**
- Create: `src/home_stock/persistence/products.py`
- Test: `tests/test_products.py`

**Interfaces:**
- Consumes: `Product`, `Batch`, `ProductDraft`, `BatchDraft`, `PackSize`, `name_key`, `batch_to_use` (Task 1); `StockError` (Task 3)
- Produces:
  - `class DuplicateProductError(StockError)` with attributes `product_id: int` and `archived: bool`; message `"Produkt o tej nazwie już istnieje."`
  - `add_product(engine, draft: ProductDraft, first_batch: BatchDraft | None = None) -> int`
  - `update_product(engine, product_id: int, draft: ProductDraft) -> None` (duplicate check skips the Product itself)
  - `get_product(engine, product_id: int) -> Product` (Batches ordered by `batch_to_use` order)
  - `list_products(engine, *, archived: bool = False) -> list[Product]` (by `name_key`)
  - `purchase(engine, product_id: int, draft: BatchDraft) -> int` (new Batch id)
  - `edit_batch(engine, batch_id: int, quantity: int, expiry: date | None) -> None`: 0 deletes the Batch; negative raises `ValueError("Ilość nie może być ujemna.")`
  - `use_one(engine, product_id: int) -> Batch | None`: takes one Unit off `batch_to_use`, deletes the Batch at 0; returns the Batch as it was before, None when the Product has no Batches
  - `discard_batch(engine, batch_id: int) -> Batch` (the deleted Batch)
  - `restore_batch(engine, batch: Batch) -> None`: puts the Batch back with its id, quantity and expiry (insert or update): the undo of `use_one` and `discard_batch`
  - `archive_product(engine, product_id: int) -> None`, `restore_product(engine, product_id: int) -> None` (restore checks no active Product took the name meanwhile)

- [ ] **Step 1: Write the failing tests** in `tests/test_products.py` (fixture `engine`; Spożywcze is category 1, opakowanie unit 2):
  - `test_add_with_first_batch_and_pack_size`: `add_product(engine, ProductDraft("Cukier", 1, 2, PackSize(Decimal("1"), "kg"), 2), BatchDraft(3))`; `get_product` has quantity 3, `pack_size == PackSize(Decimal("1"), "kg")`, `minimum_stock == 2`.
  - `test_duplicate_name_reports_existing_product`: after "Mleko", adding `" mleko "` raises `DuplicateProductError` with `product_id` of Mleko and `archived is False`; after archiving Mleko, `archived is True`.
  - `test_rename_to_existing_name_is_refused`: "Mleko" and "Kefir"; `update_product(kefir, ProductDraft("MLEKO", 1, 2))` raises `DuplicateProductError`; `update_product(kefir, ProductDraft("Kefir", 1, 1))` passes.
  - `test_use_takes_nearest_expiry_and_drops_empty_batch`: Batches `2 @ 30.10.2026`, `3 @ 12.11.2026`; two `use_one` calls leave one Batch `3 @ 12.11.2026`; the second call returned `Batch(..., quantity=1, expiry=date(2026, 10, 30))`.
  - `test_use_on_empty_product_does_nothing`: `use_one` returns None, quantity stays 0.
  - `test_undo_use_and_discard`: `restore_batch(engine, use_one(...))` and `restore_batch(engine, discard_batch(...))` each bring `get_product` back to its earlier state (same Batch ids).
  - `test_edit_batch_to_zero_removes_it_and_keeps_product`: the Product is still listed with quantity 0.
  - `test_archive_hides_and_restore_brings_back`: `list_products(engine)` excludes it, `list_products(engine, archived=True)` includes it; `restore_product` reverses; restoring while an active Product has the same name raises `DuplicateProductError`.
- [ ] **Step 2: Run to verify they fail**
- [ ] **Step 3: Implement `products.py`** (each function one `with engine.begin()` transaction)
- [ ] **Step 4: Run to verify they pass**: `.venv/Scripts/python.exe -m pytest tests/test_products.py`
- [ ] **Step 5: Commit**: `git commit -m "Add Products and Batches repository with undo"`

---

### Task 5: Shell and the Produkty tab

**Files:**
- Create: `src/home_stock/ui/context.py`, `ui/shell.py`, `ui/products.py`
- Modify: `src/home_stock/app.py` (the `index` page calls `build_shell(engine)`; full startup comes in Task 10)
- Test: `tests/test_products_ui.py`

**Interfaces:**
- Consumes: Tasks 1–4
- Produces:
  - `@dataclass Context(engine: Engine, today: Callable[[], date], overlay: ui.element, changed: Callable[[], None], undo: Callable[[str, Callable[[], None]], None])`
    - `overlay`: a shell-level element; every dialog is opened `with ctx.overlay:` so redrawing a tab never deletes an open dialog
    - `changed()`: redraws every tab (each tab registers its `refresh` with the shell)
    - `undo(message, action)`: shows a bar at the bottom (marker `undo-bar`) with the message and a `Cofnij` button (marker `undo`) for `UNDO_SECONDS = 8`; clicking runs `action()` then `changed()` and hides the bar; a new call replaces the old bar
  - `build_shell(engine: Engine, today: Callable[[], date] = date.today) -> None`: header "Home Stock", tabs `Start`, `Produkty`, `Lista zakupów`, `Ustawienia` (markers `tab-start`, `tab-products`, `tab-shopping`, `tab-settings`); Start selected. Tabs not built yet show an empty panel.
  - `class ProductsTab(ctx: Context)` with `refresh() -> None`:
    - search input (marker `search`) filters by `name_key` substring, live
    - Products grouped under their Category's name, Categories alphabetically, empty Categories hidden
    - each row (marker `product-<id>`): name (click → `open_product_card(ctx, product_id)`, Task 7; until then a no-op), `format_quantity(...)`, nearest Expiry Date if any, button `−1` (marker `use-<id>`) disabled at quantity 0; a Use calls `use_one`, then `ctx.changed()` and `ctx.undo(f"Zużyto 1 × {name}", lambda: restore_batch(engine, before))`
    - button `Dodaj produkt` (marker `add-product`) → `open_product_form(ctx)` (Task 6 adds the form and wires it; until then the button is not shown)
    - no Products at all: text `Nie masz jeszcze produktów.`

- [ ] **Step 1: Write the failing tests** in `tests/test_products_ui.py` (fixture: `init_db(tmp_path / ...)`, Products added through Task 4, `user_simulation(lambda: build_shell(engine, today=lambda: date(2026, 10, 27)))`, then `user.find(marker="tab-products").click()`):
  - `test_products_grouped_by_category_with_quantity`: Cukier (Spożywcze, opakowanie, 1 kg, 2 Batches 1+1) and Płyn do naczyń (Chemia i środki czystości); within marker `product-<cukier id>` should see `"2 opak. (2 kg)"`; should see both Category names.
  - `test_use_one_and_undo`: click `use-<id>` → should see `"1 opak."`; click `undo` → should see `"2 opak."` again.
  - `test_use_disabled_at_zero`: a Product with no Batches; `user.find(marker="use-<id>").elements` has one element with `enabled is False`.
  - `test_search_filters_by_name_ignoring_case`: type `"CUK"` into `search`; should see Cukier, should not see Płyn do naczyń.
- [ ] **Step 2: Run to verify they fail**
- [ ] **Step 3: Implement `context.py`, `shell.py`, `products.py`**
- [ ] **Step 4: Run to verify they pass**: `.venv/Scripts/python.exe -m pytest tests/test_products_ui.py`
- [ ] **Step 5: Commit**: `git commit -m "Add shell with undo bar and the Produkty tab"`

---

### Task 6: Add and edit a Product

**Files:**
- Create: `src/home_stock/ui/product_form.py`
- Modify: `src/home_stock/ui/products.py` (show the `Dodaj produkt` button)
- Test: `tests/test_product_form_ui.py`

**Interfaces:**
- Consumes: `Context` (Task 5); `add_product`, `update_product`, `purchase`, `restore_product`, `DuplicateProductError` (Task 4); `list_categories`, `list_units` (Task 3); `parse_count`, `parse_pack_size`, `parse_date` (Task 1)
- Produces: `open_product_form(ctx: Context, product: Product | None = None) -> None`
  - Fields (markers): `name`, `category` (select), `unit` (select), `pack-size` (placeholder `np. 1 kg`), `minimum-stock` (pre-filled `"1"` for a new Product; blank = no Minimum Stock), and, only for a new Product, `first-quantity` and `first-expiry` (both optional; expiry needs a quantity). Buttons `Zapisz` (marker `save`), `Anuluj`.
  - A parse or draft `ValueError` shows its message under the field (`validation` / `error` prop) and saves nothing.
  - `DuplicateProductError` replaces the form's buttons with the message plus `Dodaj partię do istniejącego` (active duplicate; saves the first Batch, if given, to it with `purchase`) or `Przywróć z archiwum` (archived duplicate; `restore_product`), marker `duplicate-action`.
  - Success closes the dialog and calls `ctx.changed()`.

- [ ] **Step 1: Write the failing tests** (open via `add-product` on the Produkty tab):
  - `test_add_product_with_first_batch`: name `Cukier`, category Spożywcze, unit opakowanie, pack size `1 kg`, minimum `2`, first quantity `3`, expiry `01.03.2027`; save; `list_products(engine)` has one Product with quantity 3, `pack_size == PackSize(Decimal("1"), "kg")`, `minimum_stock == 2`, Batch expiry `date(2027, 3, 1)`.
  - `test_minimum_stock_prefilled_and_clearable`: new form shows `minimum-stock` value `"1"`; clear it, save `Pieprz`; saved `minimum_stock is None`.
  - `test_invalid_input_shows_polish_error_and_saves_nothing`: minimum `1,5` → should see `"Podaj liczbę całkowitą"`; pack size `1 szklanka` → should see `"rozmiar opakowania"`; `list_products(engine) == []`.
  - `test_duplicate_offers_adding_a_batch`: existing Mleko; add `mleko` with first quantity 2; should see `"Produkt o tej nazwie już istnieje."`; click `duplicate-action`; Mleko's quantity grew by 2 and there is still one Product.
  - `test_duplicate_of_archived_offers_restore`: archived Mleko; click `duplicate-action`; `list_products(engine)` contains Mleko.
  - (Editing an existing Product is tested from the card in Task 7.)
- [ ] **Step 2: Run to verify they fail**
- [ ] **Step 3: Implement `product_form.py`**
- [ ] **Step 4: Run to verify they pass**: `.venv/Scripts/python.exe -m pytest tests/test_product_form_ui.py`
- [ ] **Step 5: Commit**: `git commit -m "Add the Product form with duplicate handling"`

---

### Task 7: Product card and the Purchase dialog

**Files:**
- Create: `src/home_stock/ui/product_card.py`, `src/home_stock/ui/purchase_dialog.py`
- Modify: `src/home_stock/ui/products.py` (row name opens the card)
- Test: `tests/test_product_card_ui.py`

**Interfaces:**
- Consumes: Tasks 1–6
- Produces:
  - `open_purchase_dialog(ctx: Context, product: Product) -> None`: title `Zakup: <name>`; `purchase-quantity` pre-filled with `suggested_purchase(product)`, `purchase-expiry` blank; `Dodaj` (marker `purchase-save`) calls `purchase`, closes, `ctx.changed()`
  - `open_product_card(ctx: Context, product_id: int) -> None`: name, Category, Unit, Pack Size, Minimum Stock (`brak` when None); one row per Batch with inputs `batch-quantity-<id>`, `batch-expiry-<id>`, buttons `Zapisz` (`batch-save-<id>`, calls `edit_batch`) and `Wyrzuć` (`discard-<id>`, calls `discard_batch` then `ctx.undo(f"Wyrzucono partię: {name}", ...)` with `restore_batch`); buttons `Dodaj partię` (`card-purchase` → purchase dialog), `Edytuj` (`card-edit` → `open_product_form(ctx, product)`), `Archiwizuj` (`card-archive`: `archive_product`, close, `ctx.undo(f"Zarchiwizowano: {name}", restore_product)`). The card redraws its own content after each action.

- [ ] **Step 1: Write the failing tests**:
  - `test_card_lists_batches_and_saves_an_edit`: Mleko with Batches `2 @ 30.10.2026`, `3 @ 12.11.2026`; open card by clicking `Mleko`; should see `"30.10.2026"`; set `batch-quantity-<first>` to `0`, click `batch-save-<first>`; `get_product` has one Batch.
  - `test_discard_and_undo`: click `discard-<id>` → Batch gone in `get_product`; click `undo` → back with the same id.
  - `test_purchase_suggests_quantity`: Cukier minimum 2, quantity 1; click `card-purchase`; `purchase-quantity` value is `"2"`; type expiry `01.03.2027`, click `purchase-save`; quantity becomes 3.
  - `test_archive_hides_product_and_undo_restores`: click `card-archive`; Produkty tab should not see Mleko; click `undo`; should see Mleko.
  - `test_edit_from_card_changes_minimum_stock`: click `card-edit`; the form shows `name` value `"Mleko"`; set `minimum-stock` to `5`, click `save`; `get_product(...).minimum_stock == 5` and there is still one Product (no duplicate error on its own name).
- [ ] **Step 2: Run to verify they fail**
- [ ] **Step 3: Implement `purchase_dialog.py` and `product_card.py`; wire the row name in `products.py`**
- [ ] **Step 4: Run to verify they pass**: `.venv/Scripts/python.exe -m pytest tests/test_product_card_ui.py tests/test_products_ui.py`
- [ ] **Step 5: Commit**: `git commit -m "Add the Product card and the Purchase dialog"`

---

### Task 8: Start and Lista zakupów tabs

**Files:**
- Create: `src/home_stock/ui/start.py`, `src/home_stock/ui/shopping.py`
- Modify: `src/home_stock/ui/shell.py` (register both tabs)
- Test: `tests/test_start_ui.py`, `tests/test_shopping_ui.py`

**Interfaces:**
- Consumes: `is_running_low`, `expiry_status`, `format_date`, `format_quantity` (Task 1); `list_products`, `list_categories`, `list_units`; `open_purchase_dialog` (Task 7); `ctx.today()`
- Produces:
  - `class StartTab(ctx)` with `refresh()`: three sections, markers `expired` (`Przeterminowane`), `expiring` (`Kończy się termin`), `to-buy` (`Do kupienia`). Expired / Expiring Soon list one line per Batch: `"<name>: <quantity> <unit.short>, termin <DD.MM.RRRR>"`, soonest first, using the Product's Category's `warning_days`. To-buy lists Running Low Products: `"<name>: <format_quantity>, minimum <minimum_stock>"`. An empty section shows `Nic tutaj.`; all three empty show `Wszystko w porządku.` instead.
  - `class ShoppingTab(ctx)` with `refresh()`: Running Low Products grouped by Category; each row has a checkbox-style button `Kupione` (marker `bought-<id>`) that opens `open_purchase_dialog`; empty list shows `Nic nie trzeba kupować.`

- [ ] **Step 1: Write the failing tests** (`today=lambda: date(2026, 10, 27)`):
  - `test_start_sections`: Jogurt (Spożywcze) Batch expiring `26.10.2026` → within `expired` see `"Jogurt"`; Mleko expiring `27.10.2026` and Ser `30.10.2026` → within `expiring` see both; Szynka `31.10.2026` → not in `expiring`; Aspiryna (Apteczka, 30 days) expiring `20.11.2026` → within `expiring`.
  - `test_start_to_buy_and_all_clear`: Papier toaletowy (rolka, minimum 3, quantity 3) → within `to-buy` see `"Papier toaletowy"`; Pieprz (no minimum, quantity 0) → not seen; with no Products at all → see `"Wszystko w porządku."`.
  - `test_shopping_list_purchase_removes_product`: Chusteczki minimum 2, quantity 1; on `tab-shopping` click `bought-<id>`, `purchase-quantity` shows `"2"`, click `purchase-save`; should not see `"Chusteczki"` on the list; Start's `to-buy` updated too.
- [ ] **Step 2: Run to verify they fail**
- [ ] **Step 3: Implement `start.py` and `shopping.py`; register them in `shell.py`**
- [ ] **Step 4: Run to verify they pass**
- [ ] **Step 5: Commit**: `git commit -m "Add the Start and Lista zakupów tabs"`

---

### Task 9: Ustawienia tab

**Files:**
- Create: `src/home_stock/ui/settings.py`
- Modify: `src/home_stock/ui/shell.py` (register the tab)
- Test: `tests/test_settings_ui.py`

**Interfaces:**
- Consumes: Task 3 functions and `StockError`; `list_products(engine, archived=True)`, `restore_product`, `DuplicateProductError` (Task 4)
- Produces: `class SettingsTab(ctx)` with `refresh()`, three sections:
  - `categories`: one row per Category with inputs `category-name-<id>`, `category-days-<id>`, buttons `category-save-<id>`, `category-delete-<id>`; a new row `category-new-name`, `category-new-days` (pre-filled `"7"`), `category-add`
  - `units`: likewise with `unit-name-<id>`, `unit-short-<id>`, `unit-save-<id>`, `unit-delete-<id>`, `unit-new-name`, `unit-new-short`, `unit-add`
  - `archive`: Archived Products with `Przywróć` (`restore-<id>`); empty shows `Archiwum jest puste.`
  - A `StockError` or parse error is shown with `ui.notify(message, type="negative")`; every success calls `ctx.changed()`.

- [ ] **Step 1: Write the failing tests**:
  - `test_change_warning_window_moves_batch_to_expiring`: Szynka (Spożywcze) expiring `31.10.2026`, today 27.10; set `category-days-1` to `5`, save; Start's `expiring` shows Szynka.
  - `test_add_and_delete_unused_category`: add `Ogród` / `14`; see it; delete it; not seen.
  - `test_delete_used_category_is_refused`: Product in Spożywcze; click `category-delete-1`; should see `"należą produkty"`; still listed.
  - `test_add_unit_and_use_it`: add `worek` / `wor.`; it is selectable in the Product form's `unit`.
  - `test_restore_from_archive`: archived Mleko; click `restore-<id>`; Produkty tab shows Mleko.
- [ ] **Step 2: Run to verify they fail**
- [ ] **Step 3: Implement `settings.py` and register it**
- [ ] **Step 4: Run to verify they pass**
- [ ] **Step 5: Commit**: `git commit -m "Add the Ustawienia tab"`

---

### Task 10: Startup, demo data and the PR

**Files:**
- Modify: `src/home_stock/app.py`, `README.md`, `CLAUDE.md` (Project state)
- Create: `src/home_stock/sources/__init__.py`, `src/home_stock/sources/demo_data.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `init_db`, `database_path`, `DATA_DIR_ENV`, `build_shell`, Task 4 functions
- Produces:
  - `seed_demo_data(engine: Engine, today: date) -> None`: about ten Products across Categories, chosen so every Start section and the Shopping List have entries (one Expired, two Expiring Soon, two Running Low, one with Pack Size `1 kg`, one without Minimum Stock, one Archived), dates relative to `today`
  - `parse_args(argv: Sequence[str]) -> argparse.Namespace`: `--browser`, `--demo`, `--port` (default 8080), `allow_abbrev=False`, `parse_known_args` (as KAPITA `app.py:84-92`)
  - `demo_dir() -> Path` (`tempfile.gettempdir() / "Home-Stock-demo"`), `start_demo_database() -> None` (sets `HOME_STOCK_DATA_DIR`, deletes and recreates the database, seeds it)
  - `main(argv: Sequence[str] | None = None) -> None`: `--demo` implies browser; `init_db(database_path())` once; `ui.run(root, title="Home Stock", reload=False, language="pl", ...)` with `{"port": port, "show": False}` in browser mode, else `{"native": True, "window_size": (1200, 800)}`

- [ ] **Step 1: Write the failing tests**:
  - `test_parse_args_defaults_and_flags`: `parse_args([])` → `browser is False, demo is False, port == 8080`; `parse_args(["--demo", "-x"])` → `demo is True` (unknown args ignored).
  - `test_demo_database_lives_in_temp_and_is_fresh(tmp_path, monkeypatch)`: monkeypatch `tempfile.gettempdir` to `tmp_path`; `start_demo_database()` twice; `list_products(init_db(database_path()))` has the same non-zero count both times and `database_path()` is under `tmp_path`.
  - `test_demo_data_fills_every_section`: `seed_demo_data(engine, date(2026, 10, 27))`; at least one Batch Expired, one Expiring Soon, one Product Running Low, one Archived Product.
- [ ] **Step 2: Run to verify they fail**
- [ ] **Step 3: Implement `demo_data.py` and the new `app.py`**
- [ ] **Step 4: Run the full suite and checks**

Run: `.venv/Scripts/python.exe -m pytest -n auto`, `... -m mypy`, `... -m ruff check .`
Expected: all pass, no errors.

- [ ] **Step 5: Try the app**: `.venv/Scripts/python.exe main.py --demo`, open http://127.0.0.1:8080, click through all four tabs, a Use with undo, a Purchase from the Shopping List.
- [ ] **Step 6: Update `README.md`** (`--demo` under Run) and `CLAUDE.md` Project state (v1 implemented; `--demo`; `HOME_STOCK_DATA_DIR`).
- [ ] **Step 7: Commit, push and open the PR**: `git commit -m "Add startup and demo data"`, `git push -u origin feat/home-stock-v1`, `gh pr create --base main --title "Home Stock v1"`.

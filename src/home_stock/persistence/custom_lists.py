"""Custom Lists and their List Lines (ADR-0006)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import Connection, Engine, Row, delete, insert, select, update

from home_stock.domain.custom_lists import CustomList, CustomListDraft, ListLine, ListLineDraft, custom_list_order
from home_stock.domain.stock import BatchDraft
from home_stock.persistence.catalog import StockError
from home_stock.persistence.models import CustomListRow, ListLineRow, ProductRow
from home_stock.persistence.products import Purchased, record_purchases, remove_purchases


class MissingCustomListError(StockError):
    """The Custom List was deleted meanwhile."""

    def __init__(self) -> None:
        super().__init__("Tej listy już nie ma.")


class CustomListInUseError(StockError):
    """The undo of make_custom_list when the list has List Lines by then."""

    def __init__(self) -> None:
        super().__init__("Nie można cofnąć: na liście są już pozycje.")


class MissingListLineError(StockError):
    """The List Line was deleted meanwhile."""

    def __init__(self) -> None:
        super().__init__("Tej pozycji już nie ma.")


def make_custom_list(engine: Engine, draft: CustomListDraft) -> int:
    """Save a new, empty Custom List; returns its id."""
    with engine.begin() as connection:
        list_id: int = connection.execute(
            insert(CustomListRow).values(name=draft.name, occasion=draft.occasion).returning(CustomListRow.id)
        ).scalar_one()
    return list_id


def undo_make_custom_list(engine: Engine, list_id: int) -> None:
    """Remove a Custom List make_custom_list saved: CustomListInUseError, with nothing removed, once it has a List
    Line; nothing to do when it is gone."""
    with engine.begin() as connection:
        if connection.execute(select(ListLineRow.id).where(ListLineRow.list_id == list_id)).first() is not None:
            raise CustomListInUseError()
        connection.execute(delete(CustomListRow).where(CustomListRow.id == list_id))


def list_custom_lists(engine: Engine) -> list[CustomList]:
    """Every Custom List by date of the occasion, undated last, then by name."""
    with engine.connect() as connection:
        rows = connection.execute(select(CustomListRow)).all()
    return sorted((CustomList(row.id, row.name, row.occasion) for row in rows), key=custom_list_order)


def list_lines(engine: Engine, list_id: int) -> list[ListLine]:
    """The List Lines of a Custom List, in the order added."""
    with engine.connect() as connection:
        rows = connection.execute(
            select(ListLineRow).where(ListLineRow.list_id == list_id).order_by(ListLineRow.id)
        ).all()
    return [_line(row) for row in rows]


@dataclass(frozen=True)
class AddedLine:
    """What add_line did, for undo_add_line: a new line, or the Quantity added to the Product's line."""

    line_id: int
    new: bool
    quantity: int | None


def add_line(engine: Engine, list_id: int, draft: ListLineDraft) -> AddedLine:
    """Write a List Line on the Custom List; a Product already on it, not yet bought, gets the Quantity added to its
    line instead. MissingCustomListError when the list is gone."""
    with engine.begin() as connection:
        _refuse_missing_list(connection, list_id)
        if draft.product_id is not None:
            existing = connection.execute(
                select(ListLineRow.id).where(
                    ListLineRow.list_id == list_id,
                    ListLineRow.product_id == draft.product_id,
                    ListLineRow.bought.is_(False),
                )
            ).scalar_one_or_none()
            if existing is not None:
                connection.execute(
                    update(ListLineRow)
                    .where(ListLineRow.id == existing)
                    .values(quantity=ListLineRow.quantity + draft.quantity)
                )
                return AddedLine(existing, False, draft.quantity)
        line_id: int = connection.execute(
            insert(ListLineRow)
            .values(
                list_id=list_id, product_id=draft.product_id, quantity=draft.quantity, text=draft.text, bought=False
            )
            .returning(ListLineRow.id)
        ).scalar_one()
    return AddedLine(line_id, True, draft.quantity)


def undo_add_line(engine: Engine, added: AddedLine) -> None:
    """Take back what add_line did: remove the new line, or the Quantity it added. MissingListLineError, with nothing
    changed, when the line is gone or its Quantity no longer holds what was added."""
    with engine.begin() as connection:
        quantity = connection.execute(select(ListLineRow.quantity).where(ListLineRow.id == added.line_id)).one_or_none()
        if quantity is None:
            raise MissingListLineError()
        if added.new:
            connection.execute(delete(ListLineRow).where(ListLineRow.id == added.line_id))
            return
        assert added.quantity is not None
        if quantity[0] is None or quantity[0] <= added.quantity:
            raise MissingListLineError()
        connection.execute(
            update(ListLineRow).where(ListLineRow.id == added.line_id).values(quantity=quantity[0] - added.quantity)
        )


class LineBoughtError(StockError):
    """The List Line was ticked meanwhile."""

    def __init__(self) -> None:
        super().__init__("Ta pozycja jest już kupiona.")


@dataclass(frozen=True)
class BoughtLines:
    """What tick_line, buy_lines or unpack_list did, for undo_buy_lines: the lines ticked and the Purchases
    recorded with them."""

    line_ids: tuple[int, ...]
    purchased: Purchased


def tick_line(engine: Engine, line_id: int) -> BoughtLines:
    """Mark a free-text List Line bought; MissingListLineError when it is gone, LineBoughtError when ticked already."""
    with engine.begin() as connection:
        products = _refuse_unbought_missing(connection, [line_id])
        assert products[line_id] is None, "a Product line is bought through buy_lines"
        _set_bought(connection, [line_id], True)
    return BoughtLines((line_id,), Purchased((), ()))


def buy_lines(engine: Engine, purchases: Sequence[tuple[int, BatchDraft]], on: date) -> BoughtLines:
    """Record a Purchase of each (Product line id, draft), dated ``on``, and mark those lines bought, in one
    transaction; MissingListLineError when a line is gone, LineBoughtError when one is ticked already."""
    return unpack_list(engine, [((line_id,), draft) for line_id, draft in purchases], [], on)


@dataclass(frozen=True)
class LinesToUnpack:
    """A Product's lines to buy on a Custom List, Unpacked as one row: their ids and Quantities added up."""

    line_ids: tuple[int, ...]
    quantity: int


def lines_to_unpack(engine: Engine, list_id: int) -> dict[int, LinesToUnpack]:
    """What Unpacking a Custom List offers, by Product id in the order added: its Product lines to buy of active
    Products; a Product on two lines, as after a deleted line came back, has both."""
    with engine.connect() as connection:
        rows = connection.execute(
            select(ListLineRow.id, ListLineRow.product_id, ListLineRow.quantity)
            .join(ProductRow, ProductRow.id == ListLineRow.product_id)
            .where(ListLineRow.list_id == list_id, ListLineRow.bought.is_(False), ProductRow.archived.is_(False))
            .order_by(ListLineRow.id)
        ).all()
    found: dict[int, LinesToUnpack] = {}
    for row in rows:
        before = found.get(row.product_id, LinesToUnpack((), 0))
        found[row.product_id] = LinesToUnpack((*before.line_ids, row.id), before.quantity + row.quantity)
    return found


def unpack_list(
    engine: Engine,
    lines: Sequence[tuple[Sequence[int], BatchDraft]],
    off_list: Sequence[tuple[int, BatchDraft]],
    on: date,
) -> BoughtLines:
    """Unpacking a Custom List, in one transaction: a Purchase dated ``on`` of each (Product lines, draft), the lines
    all of one Product and all marked bought, and of each (Product id, draft) bought off the list.
    MissingListLineError when a line is gone, LineBoughtError when one is ticked already."""
    line_ids = [line_id for ids, _ in lines for line_id in ids]
    with engine.begin() as connection:
        products = _refuse_unbought_missing(connection, line_ids)
        purchases = []
        for ids, draft in lines:
            product_id = products[ids[0]]
            assert product_id is not None, "a free-text line is ticked, not bought"
            assert all(products[line_id] == product_id for line_id in ids), "one Purchase is of one Product"
            purchases.append((product_id, draft))
        purchased = record_purchases(connection, [*purchases, *off_list], on)
        _set_bought(connection, line_ids, True)
    return BoughtLines(tuple(line_ids), purchased)


def undo_buy_lines(engine: Engine, bought: BoughtLines) -> None:
    """Take back tick_line, buy_lines or unpack_list, all or none: the lines unticked, the Batches and their Stock
    Events removed; MissingBatchError or MissingListLineError, with nothing changed, when one is gone."""
    with engine.begin() as connection:
        found = connection.execute(select(ListLineRow.id).where(ListLineRow.id.in_(bought.line_ids))).scalars().all()
        if len(found) < len(bought.line_ids):
            raise MissingListLineError()
        remove_purchases(connection, bought.purchased)
        _set_bought(connection, bought.line_ids, False)


def get_line(engine: Engine, line_id: int) -> ListLine:
    """One List Line; MissingListLineError when it is gone."""
    with engine.connect() as connection:
        row = connection.execute(select(ListLineRow).where(ListLineRow.id == line_id)).one_or_none()
    if row is None:
        raise MissingListLineError()
    return _line(row)


def change_line(engine: Engine, line_id: int, draft: ListLineDraft) -> ListLineDraft:
    """Set a List Line's Quantity, or its text, from ``draft`` (of the same kind); returns the line as it was, for
    the undo, which is change_line with it. MissingListLineError when the line is gone."""
    with engine.begin() as connection:
        row = connection.execute(select(ListLineRow).where(ListLineRow.id == line_id)).one_or_none()
        if row is None:
            raise MissingListLineError()
        assert row.product_id == draft.product_id, "a line keeps its Product, or stays free text"
        connection.execute(
            update(ListLineRow).where(ListLineRow.id == line_id).values(quantity=draft.quantity, text=draft.text)
        )
    return ListLineDraft(row.product_id, row.quantity, row.text)


def delete_line(engine: Engine, line_id: int) -> ListLine:
    """Remove a List Line; returns it, for restore_lines. MissingListLineError when it is gone."""
    line = get_line(engine, line_id)
    with engine.begin() as connection:
        connection.execute(delete(ListLineRow).where(ListLineRow.id == line_id))
    return line


def restore_lines(engine: Engine, lines: Sequence[ListLine]) -> None:
    """Put deleted List Lines back as they were, ids and all: the undo of delete_line. MissingCustomListError when
    their list is gone."""
    with engine.begin() as connection:
        _insert_lines(connection, lines)


def edit_custom_list(engine: Engine, list_id: int, draft: CustomListDraft) -> CustomListDraft:
    """Rename or re-date a Custom List; returns it as it was, for the undo, which is edit_custom_list with it.
    MissingCustomListError when it is gone."""
    with engine.begin() as connection:
        row = connection.execute(select(CustomListRow).where(CustomListRow.id == list_id)).one_or_none()
        if row is None:
            raise MissingCustomListError()
        connection.execute(
            update(CustomListRow).where(CustomListRow.id == list_id).values(name=draft.name, occasion=draft.occasion)
        )
    return CustomListDraft(row.name, row.occasion)


@dataclass(frozen=True)
class DeletedCustomList:
    """What delete_custom_list removed, for restore_custom_list: the list and every line on it."""

    custom_list: CustomList
    lines: tuple[ListLine, ...]


def delete_custom_list(engine: Engine, list_id: int) -> DeletedCustomList:
    """Remove a Custom List with its lines, bought or not; MissingCustomListError when it is gone."""
    with engine.begin() as connection:
        row = connection.execute(select(CustomListRow).where(CustomListRow.id == list_id)).one_or_none()
        if row is None:
            raise MissingCustomListError()
        lines = connection.execute(
            select(ListLineRow).where(ListLineRow.list_id == list_id).order_by(ListLineRow.id)
        ).all()
        connection.execute(delete(CustomListRow).where(CustomListRow.id == list_id))
    return DeletedCustomList(CustomList(row.id, row.name, row.occasion), tuple(_line(line) for line in lines))


def restore_custom_list(engine: Engine, deleted: DeletedCustomList) -> None:
    """Put a deleted Custom List back as it was, ids and lines and all: the undo of delete_custom_list."""
    lst = deleted.custom_list
    with engine.begin() as connection:
        connection.execute(insert(CustomListRow).values(id=lst.id, name=lst.name, occasion=lst.occasion))
        _insert_lines(connection, deleted.lines)


def _insert_lines(connection: Connection, lines: Sequence[ListLine]) -> None:
    for line in lines:
        _refuse_missing_list(connection, line.list_id)
        connection.execute(
            insert(ListLineRow).values(
                id=line.id,
                list_id=line.list_id,
                product_id=line.product_id,
                quantity=line.quantity,
                text=line.text,
                bought=line.bought,
            )
        )


def _line(row: Row[Any]) -> ListLine:
    return ListLine(row.id, row.list_id, row.product_id, row.quantity, row.text, row.bought)


def _refuse_unbought_missing(connection: Connection, line_ids: Sequence[int]) -> dict[int, int | None]:
    """The Product of each line by id; MissingListLineError when one is gone, LineBoughtError when one is bought."""
    rows = connection.execute(
        select(ListLineRow.id, ListLineRow.product_id, ListLineRow.bought).where(ListLineRow.id.in_(line_ids))
    ).all()
    if len(rows) < len(set(line_ids)):
        raise MissingListLineError()
    if any(row.bought for row in rows):
        raise LineBoughtError()
    return {row.id: row.product_id for row in rows}


def _set_bought(connection: Connection, line_ids: Sequence[int], bought: bool) -> None:
    connection.execute(update(ListLineRow).where(ListLineRow.id.in_(line_ids)).values(bought=bought))


def _refuse_missing_list(connection: Connection, list_id: int) -> None:
    if connection.execute(select(CustomListRow.id).where(CustomListRow.id == list_id)).first() is None:
        raise MissingCustomListError()

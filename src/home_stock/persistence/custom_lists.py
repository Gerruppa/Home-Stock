"""Custom Lists and their List Lines (ADR-0006)."""

from dataclasses import dataclass

from sqlalchemy import Connection, Engine, delete, insert, select, update

from home_stock.domain.custom_lists import CustomList, CustomListDraft, ListLine, ListLineDraft, custom_list_order
from home_stock.persistence.catalog import StockError
from home_stock.persistence.models import CustomListRow, ListLineRow


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
    return [ListLine(row.id, row.list_id, row.product_id, row.quantity, row.text, row.bought) for row in rows]


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


def _refuse_missing_list(connection: Connection, list_id: int) -> None:
    if connection.execute(select(CustomListRow.id).where(CustomListRow.id == list_id)).first() is None:
        raise MissingCustomListError()

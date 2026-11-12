"""The database tables; the schema changes only through a migration (tests/test_database.py checks)."""

from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CategoryRow(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    warning_days: Mapped[int]


class UnitRow(Base):
    __tablename__ = "units"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    short: Mapped[str] = mapped_column(String)


class ProductRow(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    # The name as domain.stock.name_key compares it, so "Mleko" and " mleko " cannot both exist
    name_key: Mapped[str] = mapped_column(String, unique=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"))
    pack_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    pack_measure: Mapped[str | None] = mapped_column(String)
    minimum_stock: Mapped[int | None]
    usual_shelf_life_days: Mapped[int | None]
    archived: Mapped[bool] = mapped_column(default=False)


class BatchRow(Base):
    __tablename__ = "batches"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_batches_quantity_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    quantity: Mapped[int]
    expiry: Mapped[date | None] = mapped_column(Date)


class StockEventRow(Base):
    __tablename__ = "stock_events"
    __table_args__ = (Index("ix_stock_events_product_on", "product_id", "on"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String)
    change: Mapped[int]
    on: Mapped[date] = mapped_column(Date)
    expired: Mapped[bool] = mapped_column(default=False)


class CustomListRow(Base):
    __tablename__ = "custom_lists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    occasion: Mapped[date | None] = mapped_column(Date)


class ListLineRow(Base):
    """A List Line, in the order added (by id)."""

    __tablename__ = "list_lines"
    __table_args__ = (
        # A Product with a Quantity, or free text without one
        CheckConstraint(
            "(product_id IS NOT NULL AND quantity > 0 AND text IS NULL)"
            " OR (product_id IS NULL AND quantity IS NULL AND text IS NOT NULL)",
            name="ck_list_lines_product_or_text",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("custom_lists.id", ondelete="CASCADE"))
    # No cascade: a Product is not removed while a line names it
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int | None]
    text: Mapped[str | None] = mapped_column(String)
    bought: Mapped[bool] = mapped_column(default=False)


class SettingRow(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String)

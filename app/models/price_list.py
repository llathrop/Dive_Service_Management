"""Price list models for standard service pricing.

The price list is organised into categories, each containing service
items with associated pricing.  Price list items can optionally link
to inventory parts that are automatically deducted when the service
is applied to an order (Phase 3).

Models:
    PriceListCategory -- top-level grouping (e.g. "Regulator Service")
    PriceListItem     -- an individual service/product with pricing
    PriceListItemPart -- links a PriceListItem to an InventoryItem
"""

from decimal import Decimal

from app.extensions import db
from app.models.mixins import TimestampMixin


# ---------------------------------------------------------------------------
# PriceListCategory
# ---------------------------------------------------------------------------

class PriceListCategory(db.Model):
    """A grouping category for price list items."""

    __tablename__ = "price_list_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(500), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # Timestamps (inline, not full mixin -- only need created/updated)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=db.func.now(),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
        onupdate=db.func.now(),
    )

    # --- Relationships ---
    items = db.relationship(
        "PriceListItem",
        back_populates="category",
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<PriceListCategory {self.id} {self.name!r}>"


# ---------------------------------------------------------------------------
# PriceListItem
# ---------------------------------------------------------------------------

class PriceListItem(TimestampMixin, db.Model):
    """A priced service or product on the price list."""

    __tablename__ = "price_list_items"

    id = db.Column(db.Integer, primary_key=True)

    # --- Category link ---
    category_id = db.Column(
        db.Integer,
        db.ForeignKey("price_list_categories.id"),
        nullable=False,
    )

    # --- Identification ---
    code = db.Column(db.String(30), unique=True, nullable=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # --- Pricing ---
    price = db.Column(db.Numeric(10, 2), nullable=False)
    cost = db.Column(db.Numeric(10, 2), nullable=True)
    price_tier = db.Column(db.String(50), nullable=True)

    # --- Unit configuration ---
    is_per_unit = db.Column(db.Boolean, nullable=False, default=True)
    default_quantity = db.Column(
        db.Numeric(10, 2), nullable=False, default=1
    )
    unit_label = db.Column(db.String(50), nullable=False, default="each")

    # --- Auto-deduction ---
    auto_deduct_parts = db.Column(db.Boolean, nullable=False, default=False)

    # --- Tax ---
    is_taxable = db.Column(db.Boolean, nullable=False, default=True)

    # --- Ordering & status ---
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # --- Internal ---
    internal_notes = db.Column(db.Text, nullable=True)
    updated_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )

    # --- Relationships ---
    category = db.relationship(
        "PriceListCategory",
        back_populates="items",
    )
    linked_parts = db.relationship(
        "PriceListItemPart",
        back_populates="price_list_item",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def margin_percent(self):
        """Compute profit margin as a percentage of the price.

        Returns ((price - cost) / price) * 100, or None if cost or
        price is not set or price is zero.
        """
        if (
            self.cost is not None
            and self.price is not None
            and self.price > 0
        ):
            price = Decimal(str(self.price))
            cost = Decimal(str(self.cost))
            return ((price - cost) / price) * Decimal("100")
        return None

    def __repr__(self):
        return f"<PriceListItem {self.id} {self.name!r}>"


# ---------------------------------------------------------------------------
# PriceListItemPart
# ---------------------------------------------------------------------------

class PriceListItemPart(db.Model):
    """Links a PriceListItem to an InventoryItem with a quantity.

    When a service is applied and ``auto_deduct_parts`` is True on the
    parent PriceListItem, these linked parts define which inventory
    items to deduct and in what quantity.
    """

    __tablename__ = "price_list_item_parts"

    id = db.Column(db.Integer, primary_key=True)

    # --- Foreign keys ---
    price_list_item_id = db.Column(
        db.Integer,
        db.ForeignKey("price_list_items.id"),
        nullable=False,
    )
    inventory_item_id = db.Column(
        db.Integer,
        db.ForeignKey("inventory_items.id"),
        nullable=False,
    )

    # --- Quantity ---
    quantity = db.Column(db.Numeric(10, 2), nullable=False, default=1)

    # --- Notes ---
    notes = db.Column(db.String(255), nullable=True)

    # --- Timestamp ---
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=db.func.now(),
    )

    # --- Relationships ---
    price_list_item = db.relationship(
        "PriceListItem",
        back_populates="linked_parts",
    )
    inventory_item = db.relationship(
        "InventoryItem",
    )

    def __repr__(self):
        return (
            f"<PriceListItemPart item={self.price_list_item_id} "
            f"inv={self.inventory_item_id}>"
        )

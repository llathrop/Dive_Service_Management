"""InventoryItem model for parts, consumables, and resale stock.

Tracks quantities, reorder levels, pricing, and supplier details for
all physical items the shop keeps on hand.  Includes soft-delete and
audit trail support.
"""

from decimal import Decimal

from sqlalchemy import Index

from app.extensions import db
from app.models.mixins import AuditMixin, SoftDeleteMixin, TimestampMixin


class InventoryItem(TimestampMixin, SoftDeleteMixin, AuditMixin, db.Model):
    """A physical inventory item (part, consumable, or resale product)."""

    __tablename__ = "inventory_items"

    id = db.Column(db.Integer, primary_key=True)

    # --- Identification ---
    sku = db.Column(db.String(50), unique=True, nullable=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # --- Categorisation ---
    category = db.Column(db.String(100), nullable=False)
    subcategory = db.Column(db.String(100), nullable=True)

    # --- Manufacturer ---
    manufacturer = db.Column(db.String(100), nullable=True)
    manufacturer_part_number = db.Column(db.String(100), nullable=True)

    # --- Pricing ---
    purchase_cost = db.Column(db.Numeric(10, 2), nullable=True)
    resale_price = db.Column(db.Numeric(10, 2), nullable=True)
    markup_percent = db.Column(db.Numeric(5, 2), nullable=True)

    # --- Stock ---
    quantity_in_stock = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    reorder_level = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    reorder_quantity = db.Column(db.Integer, nullable=True)
    unit_of_measure = db.Column(
        db.String(50), nullable=False, default="each"
    )
    storage_location = db.Column(db.String(100), nullable=True)

    # --- Status flags ---
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_for_resale = db.Column(db.Boolean, nullable=False, default=False)

    # --- Supplier ---
    preferred_supplier = db.Column(db.String(255), nullable=True)
    supplier_url = db.Column(db.String(500), nullable=True)
    minimum_order_quantity = db.Column(db.Integer, nullable=True)
    supplier_lead_time_days = db.Column(db.Integer, nullable=True)

    # --- Expiration ---
    expiration_date = db.Column(db.Date, nullable=True)

    # --- Notes ---
    notes = db.Column(db.Text, nullable=True)

    # --- Custom fields (JSON) ---
    custom_fields = db.Column(db.JSON, nullable=True)

    # --- Table indexes ---
    __table_args__ = (
        Index("ix_inventory_category_sub", "category", "subcategory"),
        Index("ix_inventory_stock_reorder", "quantity_in_stock", "reorder_level"),
        Index("ix_inventory_is_active", "is_active"),
    )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_low_stock(self):
        """Return True if quantity is at or below the reorder level.

        Only considers stock 'low' when a reorder_level > 0 has been
        explicitly configured.
        """
        return (
            self.reorder_level is not None
            and self.reorder_level > 0
            and self.quantity_in_stock <= self.reorder_level
        )

    @property
    def computed_markup_percent(self):
        """Compute markup percentage from purchase_cost and resale_price.

        Returns the percentage markup, or None if either value is missing
        or purchase_cost is zero.
        """
        if (
            self.purchase_cost is not None
            and self.resale_price is not None
            and self.purchase_cost > 0
        ):
            cost = Decimal(str(self.purchase_cost))
            price = Decimal(str(self.resale_price))
            return ((price - cost) / cost) * Decimal("100")
        return None

    def __repr__(self):
        return f"<InventoryItem {self.id} {self.name!r}>"

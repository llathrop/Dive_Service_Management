"""PartUsed model for tracking inventory parts consumed during service.

Records which inventory items were used on a service order item, the
quantity consumed, and the cost/price at the time of use.  Parts can
be manually added or automatically deducted when an AppliedService
with linked parts is applied.
"""

from sqlalchemy import Index

from app.extensions import db
from app.models.mixins import TimestampMixin


class PartUsed(TimestampMixin, db.Model):
    """An inventory part consumed during service of an order item."""

    __tablename__ = "parts_used"

    id = db.Column(db.Integer, primary_key=True)

    # --- Service order item link ---
    service_order_item_id = db.Column(
        db.Integer,
        db.ForeignKey("service_order_items.id"),
        nullable=False,
    )

    # --- Inventory item link ---
    inventory_item_id = db.Column(
        db.Integer,
        db.ForeignKey("inventory_items.id"),
        nullable=False,
    )

    # --- Applied service link (optional) ---
    applied_service_id = db.Column(
        db.Integer,
        db.ForeignKey("applied_services.id"),
        nullable=True,
    )

    # --- Auto-deduction flag ---
    is_auto_deducted = db.Column(db.Boolean, nullable=False, default=False)

    # --- Quantity & pricing ---
    quantity = db.Column(db.Numeric(10, 2), nullable=False, default=1)
    unit_cost_at_use = db.Column(db.Numeric(10, 2), nullable=False)
    unit_price_at_use = db.Column(db.Numeric(10, 2), nullable=False)

    # --- Notes ---
    notes = db.Column(db.String(500), nullable=True)

    # --- Who added ---
    added_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )

    # --- Relationships ---
    order_item = db.relationship(
        "ServiceOrderItem",
        back_populates="parts_used",
    )
    inventory_item = db.relationship(
        "InventoryItem",
        backref=db.backref("parts_used", lazy="dynamic"),
    )
    added_by_user = db.relationship(
        "User",
        foreign_keys=[added_by],
    )

    # --- Table indexes ---
    __table_args__ = (
        Index("ix_parts_used_order_item_id", "service_order_item_id"),
        Index("ix_parts_used_inventory_item_id", "inventory_item_id"),
    )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def line_total(self):
        """Return the total price for this part usage (quantity * unit_price_at_use)."""
        if self.quantity is not None and self.unit_price_at_use is not None:
            return self.quantity * self.unit_price_at_use
        return None

    def __repr__(self):
        return (
            f"<PartUsed {self.id} item={self.service_order_item_id} "
            f"inv={self.inventory_item_id}>"
        )

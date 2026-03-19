"""ServiceOrderItem model for individual equipment items within a service order.

Each service order item represents a single piece of equipment (ServiceItem)
being serviced as part of a ServiceOrder.  It tracks the item's status,
condition, warranty information, and links to related notes, parts, labor,
and applied services.
"""

from sqlalchemy import UniqueConstraint

from app.extensions import db
from app.models.mixins import TimestampMixin


# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

VALID_STATUSES = [
    "pending",
    "in_progress",
    "completed",
    "cancelled",
    "returned_unserviceable",
]

VALID_WARRANTY_TYPES = ["none", "standard", "extended", "manufacturer"]


class ServiceOrderItem(TimestampMixin, db.Model):
    """An individual equipment item within a service order."""

    __tablename__ = "service_order_items"

    id = db.Column(db.Integer, primary_key=True)

    # --- Order link ---
    order_id = db.Column(
        db.Integer,
        db.ForeignKey("service_orders.id"),
        nullable=False,
    )

    # --- Equipment link ---
    service_item_id = db.Column(
        db.Integer,
        db.ForeignKey("service_items.id"),
        nullable=False,
    )

    # --- Work details ---
    work_description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="pending")
    condition_at_receipt = db.Column(db.Text, nullable=True)
    customer_approved = db.Column(db.Boolean, nullable=False, default=False)
    diagnosis = db.Column(db.Text, nullable=True)

    # --- Warranty ---
    warranty_type = db.Column(db.String(20), nullable=False, default="none")
    warranty_start_date = db.Column(db.Date, nullable=True)
    warranty_end_date = db.Column(db.Date, nullable=True)
    warranty_notes = db.Column(db.String(500), nullable=True)

    # --- Completion ---
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )

    # --- Relationships ---
    order = db.relationship(
        "ServiceOrder",
        back_populates="order_items",
    )
    service_item = db.relationship(
        "ServiceItem",
        backref=db.backref("order_items", lazy="dynamic"),
    )
    completed_by_user = db.relationship(
        "User",
        foreign_keys=[completed_by],
    )
    notes = db.relationship(
        "ServiceNote",
        back_populates="order_item",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    parts_used = db.relationship(
        "PartUsed",
        back_populates="order_item",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    labor_entries = db.relationship(
        "LaborEntry",
        back_populates="order_item",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    applied_services = db.relationship(
        "AppliedService",
        back_populates="order_item",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    # --- Table constraints & indexes ---
    __table_args__ = (
        UniqueConstraint("order_id", "service_item_id", name="uq_order_service_item"),
    )

    def __repr__(self):
        return (
            f"<ServiceOrderItem {self.id} order={self.order_id} "
            f"item={self.service_item_id}>"
        )

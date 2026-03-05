"""ServiceOrder model for tracking customer service work orders.

A service order represents a complete job for a customer, from intake
through completion and pickup.  Each order contains one or more
ServiceOrderItems (individual pieces of equipment being serviced).

Includes soft-delete support, audit trail, and status tracking with
priority levels.
"""

from datetime import date

from sqlalchemy import Index

from app.extensions import db
from app.models.mixins import AuditMixin, SoftDeleteMixin, TimestampMixin


# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

VALID_STATUSES = [
    "intake",
    "assessment",
    "awaiting_approval",
    "in_progress",
    "awaiting_parts",
    "completed",
    "ready_for_pickup",
    "picked_up",
    "cancelled",
]

VALID_PRIORITIES = ["low", "normal", "high", "rush"]

COMPLETED_STATUSES = ["completed", "ready_for_pickup", "picked_up"]


class ServiceOrder(TimestampMixin, SoftDeleteMixin, AuditMixin, db.Model):
    """A service work order for a customer."""

    __tablename__ = "service_orders"

    id = db.Column(db.Integer, primary_key=True)

    # --- Order identification ---
    order_number = db.Column(db.String(20), unique=True, nullable=False)

    # --- Customer link ---
    customer_id = db.Column(
        db.Integer,
        db.ForeignKey("customers.id"),
        nullable=False,
    )

    # --- Status & priority ---
    status = db.Column(db.String(30), nullable=False, default="intake")
    priority = db.Column(db.String(10), nullable=False, default="normal")

    # --- Assignment ---
    assigned_tech_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )

    # --- Key dates ---
    date_received = db.Column(db.Date, nullable=False)
    date_promised = db.Column(db.Date, nullable=True)
    date_completed = db.Column(db.Date, nullable=True)
    date_picked_up = db.Column(db.Date, nullable=True)

    # --- Description & notes ---
    description = db.Column(db.Text, nullable=True)
    internal_notes = db.Column(db.Text, nullable=True)

    # --- Financial ---
    estimated_total = db.Column(db.Numeric(10, 2), nullable=True)
    rush_fee = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    discount_percent = db.Column(db.Numeric(5, 2), nullable=False, default=0.00)
    discount_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    actual_total = db.Column(db.Numeric(10, 2), nullable=True)

    # --- Approval ---
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    approved_by_name = db.Column(db.String(200), nullable=True)
    approval_method = db.Column(db.String(20), nullable=True)

    # --- Pickup ---
    picked_up_by_name = db.Column(db.String(200), nullable=True)
    pickup_notes = db.Column(db.String(500), nullable=True)

    # --- Relationships ---
    customer = db.relationship(
        "Customer",
        backref=db.backref("orders", lazy="dynamic"),
    )
    assigned_tech = db.relationship(
        "User",
        foreign_keys=[assigned_tech_id],
    )
    order_items = db.relationship(
        "ServiceOrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    # --- Table indexes ---
    __table_args__ = (
        Index("ix_service_orders_status", "status"),
        Index("ix_service_orders_customer_id", "customer_id"),
        Index("ix_service_orders_date_received", "date_received"),
        Index("ix_service_orders_assigned_tech_id", "assigned_tech_id"),
    )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def display_status(self):
        """Return the status with underscores replaced by spaces, title-cased."""
        return self.status.replace("_", " ").title() if self.status else ""

    @property
    def is_overdue(self):
        """Return True if the order is past the promised date and not completed.

        An order is considered overdue when ``date_promised`` is set and in
        the past and the current status is not one of the completed states.
        """
        if self.date_promised is None:
            return False
        if self.status in COMPLETED_STATUSES:
            return False
        return date.today() > self.date_promised

    def __repr__(self):
        return f"<ServiceOrder {self.id} {self.order_number!r}>"

"""LaborEntry model for tracking technician labor on service order items.

Each entry records the technician, hours worked, hourly rate, and a
description of the work performed on a specific date.  Labor entries
are linked to individual ServiceOrderItems for granular cost tracking.
"""

from sqlalchemy import Index

from app.extensions import db
from app.models.mixins import TimestampMixin


class LaborEntry(TimestampMixin, db.Model):
    """A labor time entry for work on a service order item."""

    __tablename__ = "labor_entries"

    id = db.Column(db.Integer, primary_key=True)

    # --- Service order item link ---
    service_order_item_id = db.Column(
        db.Integer,
        db.ForeignKey("service_order_items.id"),
        nullable=False,
    )

    # --- Technician ---
    tech_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
    )

    # --- Time & rate ---
    hours = db.Column(db.Numeric(5, 2), nullable=False)
    hourly_rate = db.Column(db.Numeric(8, 2), nullable=False)

    # --- Work details ---
    description = db.Column(db.String(500), nullable=True)
    work_date = db.Column(db.Date, nullable=False)

    # --- Relationships ---
    order_item = db.relationship(
        "ServiceOrderItem",
        back_populates="labor_entries",
    )
    tech = db.relationship(
        "User",
        foreign_keys=[tech_id],
    )

    # --- Table indexes ---
    __table_args__ = (
        Index("ix_labor_entries_order_item_id", "service_order_item_id"),
        Index("ix_labor_entries_tech_id", "tech_id"),
        Index("ix_labor_entries_work_date", "work_date"),
    )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def line_total(self):
        """Return the total cost for this labor entry (hours * hourly_rate)."""
        if self.hours is not None and self.hourly_rate is not None:
            return self.hours * self.hourly_rate
        return None

    def __repr__(self):
        return (
            f"<LaborEntry {self.id} item={self.service_order_item_id} "
            f"tech={self.tech_id}>"
        )

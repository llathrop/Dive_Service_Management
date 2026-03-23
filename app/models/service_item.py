"""ServiceItem model for tracking customer equipment.

A service item represents a piece of dive equipment that can be brought
in for service.  Each item belongs to a customer and may have
a one-to-one DrysuitDetails extension for drysuit-specific fields.
"""

from sqlalchemy import Index

from app.extensions import db
from app.models.mixins import AuditMixin, SoftDeleteMixin, TimestampMixin


class ServiceItem(TimestampMixin, SoftDeleteMixin, AuditMixin, db.Model):
    """A piece of dive equipment tracked for service."""

    __tablename__ = "service_items"

    id = db.Column(db.Integer, primary_key=True)

    # --- Identification ---
    serial_number = db.Column(db.String(100), nullable=True, unique=True)
    name = db.Column(db.String(255), nullable=False)
    item_category = db.Column(db.String(100), nullable=True)

    # --- Serviceability ---
    serviceability = db.Column(
        db.String(30), nullable=False, default="serviceable"
    )
    serviceability_notes = db.Column(db.Text, nullable=True)

    # --- Equipment details ---
    brand = db.Column(db.String(100), nullable=True)
    model = db.Column(db.String(100), nullable=True)
    year_manufactured = db.Column(db.SmallInteger, nullable=True)

    # --- Notes ---
    notes = db.Column(db.Text, nullable=True)

    # --- Service history ---
    last_service_date = db.Column(db.Date, nullable=True)

    # --- Customer relationship ---
    customer_id = db.Column(
        db.Integer,
        db.ForeignKey("customers.id"),
        nullable=False,
    )

    # --- Custom fields (JSON) ---
    custom_fields = db.Column(db.JSON, nullable=True)

    # --- Relationships ---
    customer = db.relationship(
        "Customer",
        back_populates="service_items",
    )
    drysuit_details = db.relationship(
        "DrysuitDetails",
        back_populates="service_item",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # --- Table indexes ---
    __table_args__ = (
        Index("ix_service_items_serial_number", "serial_number"),
    )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_drysuit(self):
        """Return True if this item is categorised as a Drysuit."""
        return self.item_category == "Drysuit"

    def __repr__(self):
        return f"<ServiceItem {self.id} {self.name!r}>"

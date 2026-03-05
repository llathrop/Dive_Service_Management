"""ServiceNote model for technician and service notes.

Notes are attached to individual ServiceOrderItems and track diagnostic
findings, repair actions, testing results, and customer communications.
Each note records the author and timestamp for full traceability.
"""

from sqlalchemy import Index

from app.extensions import db
from app.models.mixins import TimestampMixin


# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

VALID_NOTE_TYPES = [
    "diagnostic",
    "repair",
    "testing",
    "general",
    "customer_communication",
]


class ServiceNote(TimestampMixin, db.Model):
    """A note attached to a service order item."""

    __tablename__ = "service_notes"

    id = db.Column(db.Integer, primary_key=True)

    # --- Service order item link ---
    service_order_item_id = db.Column(
        db.Integer,
        db.ForeignKey("service_order_items.id"),
        nullable=False,
    )

    # --- Note content ---
    note_text = db.Column(db.Text, nullable=False)
    note_type = db.Column(db.String(30), nullable=False, default="general")

    # --- Author ---
    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
    )

    # --- Relationships ---
    order_item = db.relationship(
        "ServiceOrderItem",
        back_populates="notes",
    )
    author = db.relationship(
        "User",
        foreign_keys=[created_by],
    )

    # --- Table indexes ---
    __table_args__ = (
        Index("ix_service_notes_order_item_id", "service_order_item_id"),
    )

    def __repr__(self):
        return f"<ServiceNote {self.id} type={self.note_type!r}>"

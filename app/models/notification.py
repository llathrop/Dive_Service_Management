"""Notification model for in-app notifications.

Supports user-targeted and broadcast notifications with severity levels,
entity linking for context navigation, and read/unread tracking.
"""

from sqlalchemy import Index

from app.extensions import db
from app.models.mixins import TimestampMixin


# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

VALID_SEVERITIES = ["info", "warning", "critical"]

VALID_NOTIFICATION_TYPES = [
    "low_stock",
    "critical_stock",
    "overdue_invoice",
    "order_status_change",
    "order_approaching_due",
    "order_overdue",
    "order_assigned",
    "serviceability_change",
    "payment_received",
    "service_reminder",
    "system",
]


class Notification(TimestampMixin, db.Model):
    """An in-app notification for a user or broadcast to all users."""

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)

    # --- Target user (null = broadcast to all) ---
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )

    # --- Notification content ---
    notification_type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)

    # --- Entity link (for navigation context) ---
    entity_type = db.Column(db.String(50), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)

    # --- Read tracking ---
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    read_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # --- Severity ---
    severity = db.Column(db.String(20), nullable=False, default="info")

    # --- Relationships ---
    user = db.relationship(
        "User",
        backref=db.backref("notifications", lazy="dynamic"),
    )

    # --- Table indexes ---
    __table_args__ = (
        Index("ix_notifications_user_read", "user_id", "is_read"),
        Index("ix_notifications_type", "notification_type"),
        Index("ix_notifications_created_at", "created_at"),
    )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def display_severity(self):
        """Return the severity with title-case formatting."""
        return self.severity.title() if self.severity else ""

    def __repr__(self):
        return f"<Notification {self.id} type={self.notification_type!r}>"

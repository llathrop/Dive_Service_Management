"""Service reminder delivery ledger.

Tracks per-recipient reminder sends so the recurring reminder task can
claim a deterministic slot before creating a notification.  This keeps
overlapping task executions from double-sending the same reminder.
"""

from datetime import datetime, timezone

from app.extensions import db


class ServiceReminderDelivery(db.Model):
    """Per-user reminder delivery ledger row."""

    __tablename__ = "service_reminder_deliveries"

    id = db.Column(db.Integer, primary_key=True)
    service_item_id = db.Column(
        db.Integer,
        db.ForeignKey("service_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    delivery_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        db.UniqueConstraint(
            "service_item_id",
            "user_id",
            "delivery_date",
            name="uq_service_reminder_delivery",
        ),
    )

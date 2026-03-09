"""Notification read-tracking for per-user broadcast state.

Broadcast notifications (where notification.user_id is NULL) are visible to
all users.  Rather than flipping a single ``is_read`` flag on the shared
notification row, each user gets their own NotificationRead record when they
dismiss / read the broadcast.
"""

from app.extensions import db


class NotificationRead(db.Model):
    """Per-user read receipt for broadcast notifications."""

    __tablename__ = "notification_reads"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    notification_id = db.Column(
        db.Integer,
        db.ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    read_at = db.Column(db.DateTime(timezone=True), nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            "notification_id", "user_id", name="uq_notification_user_read"
        ),
    )

    notification = db.relationship("Notification", backref="reads")

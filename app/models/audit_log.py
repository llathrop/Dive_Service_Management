"""AuditLog model for tracking data changes with user attribution.

Stores immutable records of all significant data changes, user actions,
and system events.  Each entry captures who did what, to which entity,
and the before/after values for field-level changes.
"""

from app.extensions import db


class AuditLog(db.Model):
    """An immutable audit trail entry."""

    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)

    # Who performed the action (null for system actions)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True
    )

    # What happened
    action = db.Column(db.String(50), nullable=False)  # create, update, delete, restore, login, logout, export, status_change

    # Which entity was affected
    entity_type = db.Column(db.String(50), nullable=False)  # customer, service_order, etc.
    entity_id = db.Column(db.Integer, nullable=False)

    # Field-level change tracking
    field_name = db.Column(db.String(100), nullable=True)
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)

    # Request metadata
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)

    # Arbitrary extra data (JSON string)
    additional_data = db.Column(db.Text, nullable=True)

    # Immutable timestamp — no updated_at since audit records are never modified
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
    )

    # Relationships
    user = db.relationship("User", backref="audit_logs")

    __table_args__ = (
        db.Index("ix_audit_log_entity", "entity_type", "entity_id"),
        db.Index("ix_audit_log_user_id", "user_id"),
        db.Index("ix_audit_log_created_at", "created_at"),
        db.Index("ix_audit_log_action", "action"),
    )

    def __repr__(self):
        return (
            f"<AuditLog {self.action} {self.entity_type}#{self.entity_id}>"
        )

"""SystemConfig model for database-stored application settings.

Stores key-value configuration entries organized by category, with type
coercion support and environment variable override tracking.  Settings
controlled by environment variables are shown as read-only in the admin UI.
"""

import json

from app.extensions import db
from app.models.mixins import TimestampMixin


VALID_CONFIG_TYPES = ["string", "integer", "float", "boolean", "json"]

VALID_CATEGORIES = [
    "company",
    "email",
    "invoice",
    "tax",
    "service",
    "notification",
    "display",
    "security",
]


class SystemConfig(TimestampMixin, db.Model):
    """A single configuration key-value entry."""

    __tablename__ = "system_config"

    id = db.Column(db.Integer, primary_key=True)

    config_key = db.Column(db.String(100), unique=True, nullable=False)
    config_value = db.Column(db.Text, nullable=True)
    config_type = db.Column(
        db.String(20), nullable=False, default="string"
    )
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    is_sensitive = db.Column(db.Boolean, default=False, nullable=False)

    updated_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )

    __table_args__ = (
        db.Index("ix_system_config_category", "category"),
    )

    # ------------------------------------------------------------------
    # Type coercion
    # ------------------------------------------------------------------

    @property
    def typed_value(self):
        """Return config_value coerced to the declared config_type."""
        if self.config_value is None:
            return None
        return _coerce_value(self.config_value, self.config_type)

    @typed_value.setter
    def typed_value(self, value):
        """Set config_value from a Python value, serialising as needed."""
        if value is None:
            self.config_value = None
        elif self.config_type == "json":
            self.config_value = json.dumps(value)
        elif self.config_type == "boolean":
            self.config_value = "true" if value else "false"
        else:
            self.config_value = str(value)

    def __repr__(self):
        return f"<SystemConfig {self.config_key!r}={self.config_value!r}>"


def _coerce_value(raw, config_type):
    """Coerce a string value to the given config_type."""
    if config_type == "integer":
        return int(raw)
    if config_type == "float":
        return float(raw)
    if config_type == "boolean":
        return raw.lower() in ("true", "1", "yes")
    if config_type == "json":
        return json.loads(raw)
    return raw  # string

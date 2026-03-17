"""SavedSearch model for per-user saved filter configurations.

Allows users to save and reload their search/filter criteria on entity
list pages (customers, orders, inventory, invoices).  Each user can mark
one saved search per entity type as their default, which auto-applies on
page load.
"""

import json

from app.extensions import db
from app.models.mixins import TimestampMixin


VALID_SEARCH_TYPES = ["customer", "order", "inventory", "invoice"]


class SavedSearch(TimestampMixin, db.Model):
    """A named saved search / filter configuration."""

    __tablename__ = "saved_searches"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    name = db.Column(db.String(100), nullable=False)
    search_type = db.Column(db.String(50), nullable=False)
    filters_json = db.Column(db.Text, nullable=False)
    is_default = db.Column(db.Boolean, default=False, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "name", "search_type", name="uq_saved_search_user_name_type"),
        db.Index("ix_saved_search_user_type", "user_id", "search_type"),
    )

    @property
    def filters(self):
        """Return the deserialized filter criteria dict."""
        if self.filters_json:
            return json.loads(self.filters_json)
        return {}

    @filters.setter
    def filters(self, value):
        """Serialize filter criteria to JSON."""
        self.filters_json = json.dumps(value)

    def __repr__(self):
        return f"<SavedSearch {self.id} '{self.name}' ({self.search_type})>"

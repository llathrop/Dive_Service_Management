from app.extensions import db
from app.models.mixins import TimestampMixin, AuditMixin

class LookupValue(db.Model, TimestampMixin, AuditMixin):
    """Generic table for user-extensible dropdown values."""
    __tablename__ = 'lookup_values'

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False, index=True)  # e.g., 'material_type', 'seal_type'
    value = db.Column(db.String(100), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)

    __table_args__ = (
        db.UniqueConstraint('category', 'value', name='_category_value_uc'),
    )

    def __repr__(self):
        return f"<LookupValue category={self.category} value={self.value}>"

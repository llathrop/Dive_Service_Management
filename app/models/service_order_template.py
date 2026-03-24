"""ServiceOrderTemplate model for reusable service order configurations.

Allows technicians and admins to save common service configurations as
templates that pre-populate when creating new orders.  Templates can be
private (visible only to the creator) or shared with all users.
"""

from app.extensions import db
from app.models.mixins import TimestampMixin


class ServiceOrderTemplate(TimestampMixin, db.Model):
    """A reusable template for service order configurations."""

    __tablename__ = "service_order_templates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    is_shared = db.Column(db.Boolean, default=False, nullable=False)

    # JSON blob storing template configuration:
    # {
    #   "priority": "normal",
    #   "rush_fee": "0.00",
    #   "discount_percent": "0",
    #   "services": [{"price_list_item_id": 1, "quantity": 1, "override_price": null}],
    #   "parts": [{"inventory_item_id": 5, "quantity": 2}],
    #   "estimated_labor_hours": "2.0",
    #   "notes": "Standard annual service procedure"
    # }
    template_data = db.Column(db.JSON, nullable=False, default=dict)

    # Relationships
    created_by = db.relationship("User", backref="order_templates")

    def __repr__(self):
        return f"<ServiceOrderTemplate {self.id} '{self.name}'>"

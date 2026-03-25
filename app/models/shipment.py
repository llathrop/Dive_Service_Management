"""Shipment model for tracking shipping details on service orders.

Stores package dimensions, weight, shipping cost, carrier, tracking
information, and shipment status for each service order.
"""

from app.extensions import db
from app.models.mixins import AuditMixin, TimestampMixin


# Valid shipment statuses
VALID_STATUSES = ["pending", "shipped", "in_transit", "delivered", "cancelled"]


class Shipment(TimestampMixin, AuditMixin, db.Model):
    """A shipment associated with a service order."""

    __tablename__ = "shipments"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer, db.ForeignKey("service_orders.id"), nullable=False
    )

    # Package dimensions
    weight_lbs = db.Column(db.Numeric(8, 2), nullable=True)
    length_in = db.Column(db.Numeric(8, 2), nullable=True)
    width_in = db.Column(db.Numeric(8, 2), nullable=True)
    height_in = db.Column(db.Numeric(8, 2), nullable=True)

    # Shipping details
    provider_code = db.Column(db.String(50), nullable=True)
    shipping_method = db.Column(db.String(100), nullable=True)
    shipping_cost = db.Column(db.Numeric(10, 2), nullable=True)
    quote_metadata = db.Column(db.JSON, nullable=True, default=dict)
    tracking_number = db.Column(db.String(255), nullable=True)
    carrier = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(50), default="pending", nullable=False)
    notes = db.Column(db.Text, nullable=True)

    # Relationships
    order = db.relationship(
        "ServiceOrder",
        backref=db.backref("shipments", lazy="dynamic"),
    )

    def __repr__(self):
        return f"<Shipment id={self.id} order_id={self.order_id} status={self.status}>"

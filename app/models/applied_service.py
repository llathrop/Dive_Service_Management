"""AppliedService model for services applied to a service order item.

An applied service represents a specific service (from the price list or
custom/ad-hoc) that has been applied to a piece of equipment on a work
order.  It tracks pricing, discounts, tax status, and links to any
inventory parts that were consumed as part of the service.
"""

from decimal import Decimal

from sqlalchemy import Index

from app.extensions import db
from app.models.mixins import TimestampMixin


class AppliedService(TimestampMixin, db.Model):
    """A service applied to a service order item."""

    __tablename__ = "applied_services"

    id = db.Column(db.Integer, primary_key=True)

    # --- Service order item link ---
    service_order_item_id = db.Column(
        db.Integer,
        db.ForeignKey("service_order_items.id"),
        nullable=False,
    )

    # --- Price list link (NULL = custom/ad-hoc service) ---
    price_list_item_id = db.Column(
        db.Integer,
        db.ForeignKey("price_list_items.id"),
        nullable=True,
    )

    # --- Service details ---
    service_name = db.Column(db.String(255), nullable=False)
    service_description = db.Column(db.Text, nullable=True)

    # --- Pricing ---
    quantity = db.Column(db.Numeric(10, 2), nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    discount_percent = db.Column(db.Numeric(5, 2), nullable=False, default=0.00)
    line_total = db.Column(db.Numeric(10, 2), nullable=False)

    # --- Flags ---
    is_taxable = db.Column(db.Boolean, nullable=False, default=True)
    price_overridden = db.Column(db.Boolean, nullable=False, default=False)
    customer_approved = db.Column(db.Boolean, nullable=False, default=False)

    # --- Notes ---
    notes = db.Column(db.String(500), nullable=True)

    # --- Who added ---
    added_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )

    # --- Relationships ---
    order_item = db.relationship(
        "ServiceOrderItem",
        back_populates="applied_services",
    )
    price_list_item = db.relationship(
        "PriceListItem",
        backref=db.backref("applied_services", lazy="dynamic"),
    )
    added_by_user = db.relationship(
        "User",
        foreign_keys=[added_by],
    )
    parts_used = db.relationship(
        "PartUsed",
        backref="applied_service",
        lazy="dynamic",
    )

    # --- Table indexes ---
    __table_args__ = (
        Index("ix_applied_services_order_item_id", "service_order_item_id"),
        Index("ix_applied_services_price_list_item_id", "price_list_item_id"),
    )

    # ------------------------------------------------------------------
    # Methods
    # ------------------------------------------------------------------

    def calculate_line_total(self):
        """Compute and set line_total from quantity, unit_price, and discount.

        Calculates: (quantity * unit_price) * (1 - discount_percent / 100)
        """
        qty = Decimal(str(self.quantity)) if self.quantity is not None else Decimal("0")
        price = Decimal(str(self.unit_price)) if self.unit_price is not None else Decimal("0")
        discount = Decimal(str(self.discount_percent)) if self.discount_percent is not None else Decimal("0")
        self.line_total = (qty * price) * (Decimal("1") - discount / Decimal("100"))

    def __repr__(self):
        return f"<AppliedService {self.id} {self.service_name!r}>"

"""Payment model for tracking payments against invoices and service orders.

A payment records a financial transaction -- a payment received, a deposit
collected, or a refund issued.  Payments can be linked to a specific
invoice, a service order, or both.  Deposits and prepayments may exist
without an invoice link.
"""

from sqlalchemy import Index

from app.extensions import db
from app.models.mixins import TimestampMixin


# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

VALID_PAYMENT_TYPES = ["payment", "deposit", "refund"]

VALID_PAYMENT_METHODS = [
    "cash",
    "check",
    "credit_card",
    "debit_card",
    "bank_transfer",
    "other",
]


class Payment(TimestampMixin, db.Model):
    """A payment, deposit, or refund recorded against an invoice or order."""

    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)

    # --- Invoice link (nullable for deposits/prepayments) ---
    invoice_id = db.Column(
        db.Integer,
        db.ForeignKey("invoices.id"),
        nullable=True,
    )

    # --- Service order link ---
    service_order_id = db.Column(
        db.Integer,
        db.ForeignKey("service_orders.id"),
        nullable=True,
    )

    # --- Payment details ---
    payment_type = db.Column(db.String(20), nullable=False, default="payment")
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    reference_number = db.Column(db.String(255), nullable=True)

    # --- External system integration ---
    external_id = db.Column(db.String(255), nullable=True)
    external_system = db.Column(db.String(50), nullable=True)

    # --- Notes ---
    notes = db.Column(db.String(500), nullable=True)

    # --- Who recorded ---
    recorded_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )

    # --- Relationships ---
    invoice = db.relationship(
        "Invoice",
        back_populates="payments",
    )
    service_order = db.relationship(
        "ServiceOrder",
        backref=db.backref("payments", lazy="dynamic"),
    )
    recorded_by_user = db.relationship(
        "User",
        foreign_keys=[recorded_by],
    )

    # --- Table indexes ---
    __table_args__ = (
        Index("ix_payments_invoice_id", "invoice_id"),
        Index("ix_payments_service_order_id", "service_order_id"),
        Index("ix_payments_payment_date", "payment_date"),
        Index("ix_payments_payment_type", "payment_type"),
    )

    def __repr__(self):
        return (
            f"<Payment {self.id} type={self.payment_type!r} "
            f"amount={self.amount}>"
        )

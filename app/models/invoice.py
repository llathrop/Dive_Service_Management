"""Invoice and InvoiceLineItem models for customer billing.

An invoice represents a bill sent to a customer for services rendered.
Each invoice contains one or more line items detailing the charges, and
can be linked to one or more service orders via the invoice_orders
association table.

Invoices use status tracking (not soft-delete) since financial records
should be voided rather than deleted.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import Index, UniqueConstraint

from app.extensions import db
from app.models.mixins import AuditMixin, TimestampMixin


# ---------------------------------------------------------------------------
# Association table for Invoice <-> ServiceOrder many-to-many link
# ---------------------------------------------------------------------------

invoice_orders = db.Table(
    "invoice_orders",
    db.Column("id", db.Integer, primary_key=True, autoincrement=True),
    db.Column(
        "invoice_id",
        db.Integer,
        db.ForeignKey("invoices.id"),
        nullable=False,
    ),
    db.Column(
        "order_id",
        db.Integer,
        db.ForeignKey("service_orders.id"),
        nullable=False,
    ),
    db.Column(
        "created_at",
        db.DateTime(timezone=True),
        nullable=True,
    ),
    UniqueConstraint("invoice_id", "order_id", name="uq_invoice_orders_invoice_order"),
)


# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

VALID_STATUSES = [
    "draft",
    "sent",
    "viewed",
    "partially_paid",
    "paid",
    "overdue",
    "void",
    "refunded",
]

TERMINAL_STATUSES = ["paid", "void", "refunded"]


# ---------------------------------------------------------------------------
# Invoice model
# ---------------------------------------------------------------------------

class Invoice(TimestampMixin, AuditMixin, db.Model):
    """A billing invoice for a customer."""

    __tablename__ = "invoices"

    id = db.Column(db.Integer, primary_key=True)

    # --- Invoice identification ---
    invoice_number = db.Column(db.String(20), unique=True, nullable=False)

    # --- Customer link ---
    customer_id = db.Column(
        db.Integer,
        db.ForeignKey("customers.id"),
        nullable=False,
    )

    # --- Status ---
    status = db.Column(db.String(20), nullable=False, default="draft")

    # --- Key dates ---
    issue_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    paid_date = db.Column(db.Date, nullable=True)

    # --- Financial ---
    subtotal = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    tax_rate = db.Column(db.Numeric(5, 4), default=0.0000)
    tax_amount = db.Column(db.Numeric(10, 2), default=0.00)
    discount_amount = db.Column(db.Numeric(10, 2), default=0.00)
    total = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    amount_paid = db.Column(db.Numeric(10, 2), default=0.00)
    balance_due = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)

    # --- Payment info ---
    payment_method = db.Column(db.String(50), nullable=True)
    payment_reference = db.Column(db.String(255), nullable=True)

    # --- External system integration ---
    external_id = db.Column(db.String(255), nullable=True)
    external_system = db.Column(db.String(50), nullable=True)
    external_sync_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # --- Notes ---
    notes = db.Column(db.Text, nullable=True)
    customer_notes = db.Column(db.Text, nullable=True)
    terms = db.Column(db.Text, nullable=True)

    # --- Relationships ---
    customer = db.relationship(
        "Customer",
        backref=db.backref("invoices", lazy="dynamic"),
    )
    line_items = db.relationship(
        "InvoiceLineItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    payments = db.relationship(
        "Payment",
        back_populates="invoice",
        lazy="dynamic",
    )
    orders = db.relationship(
        "ServiceOrder",
        secondary="invoice_orders",
        backref=db.backref("invoices", lazy="dynamic"),
    )

    # --- Table indexes ---
    __table_args__ = (
        Index("ix_invoices_status", "status"),
        Index("ix_invoices_customer_id", "customer_id"),
        Index("ix_invoices_issue_date", "issue_date"),
        Index("ix_invoices_due_date", "due_date"),
    )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_overdue(self):
        """Return True if the invoice is past due and not in a terminal status.

        An invoice is considered overdue when ``due_date`` is set and in
        the past and the current status is not one of the terminal states
        (paid, void, refunded).
        """
        if self.due_date is None:
            return False
        if self.status in TERMINAL_STATUSES:
            return False
        return date.today() > self.due_date

    @property
    def display_status(self):
        """Return the status with underscores replaced by spaces, title-cased."""
        return self.status.replace("_", " ").title() if self.status else ""

    # ------------------------------------------------------------------
    # Methods
    # ------------------------------------------------------------------

    def recalculate_totals(self):
        """Recompute subtotal, tax_amount, total, and balance_due from line items.

        Sums all line item ``line_total`` values to derive ``subtotal``,
        applies ``tax_rate`` to compute ``tax_amount``, then calculates
        ``total`` and ``balance_due``.
        """
        items = self.line_items.all()
        raw_subtotal = sum(
            (Decimal(str(item.line_total)) for item in items if item.line_total is not None),
            Decimal("0"),
        )
        self.subtotal = raw_subtotal

        rate = Decimal(str(self.tax_rate)) if self.tax_rate is not None else Decimal("0")
        self.tax_amount = raw_subtotal * rate

        discount = Decimal(str(self.discount_amount)) if self.discount_amount is not None else Decimal("0")
        self.total = raw_subtotal + self.tax_amount - discount

        paid = Decimal(str(self.amount_paid)) if self.amount_paid is not None else Decimal("0")
        self.balance_due = self.total - paid

    def __repr__(self):
        return f"<Invoice {self.id} {self.invoice_number!r}>"


# ---------------------------------------------------------------------------
# InvoiceLineItem model
# ---------------------------------------------------------------------------

VALID_LINE_TYPES = [
    "service",
    "labor",
    "part",
    "fee",
    "discount",
    "other",
]


class InvoiceLineItem(TimestampMixin, db.Model):
    """A single line item on an invoice."""

    __tablename__ = "invoice_line_items"

    id = db.Column(db.Integer, primary_key=True)

    # --- Invoice link ---
    invoice_id = db.Column(
        db.Integer,
        db.ForeignKey("invoices.id"),
        nullable=False,
    )

    # --- Line item details ---
    line_type = db.Column(db.String(20), nullable=False)
    description = db.Column(db.String(500), nullable=False)

    # --- Quantity & pricing ---
    quantity = db.Column(db.Numeric(10, 2), nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    line_total = db.Column(db.Numeric(10, 2), nullable=False)

    # --- Source links (optional, for traceability) ---
    applied_service_id = db.Column(
        db.Integer,
        db.ForeignKey("applied_services.id"),
        nullable=True,
    )
    labor_entry_id = db.Column(
        db.Integer,
        db.ForeignKey("labor_entries.id"),
        nullable=True,
    )
    parts_used_id = db.Column(
        db.Integer,
        db.ForeignKey("parts_used.id"),
        nullable=True,
    )

    # --- Ordering ---
    sort_order = db.Column(db.Integer, default=0)

    # --- Relationships ---
    invoice = db.relationship(
        "Invoice",
        back_populates="line_items",
    )

    # --- Table indexes ---
    __table_args__ = (
        Index("ix_invoice_line_items_invoice_id", "invoice_id"),
    )

    def __repr__(self):
        return f"<InvoiceLineItem {self.id} invoice={self.invoice_id}>"

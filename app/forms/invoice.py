"""Invoice forms for billing workflow.

WTForms form classes for creating, editing, and searching invoices,
managing invoice line items, and recording payments.  ``InvoiceForm``
handles the full invoice lifecycle with status tracking and financial
fields.  ``InvoiceSearchForm`` is a lightweight GET-based form (CSRF
disabled) for filtering invoice lists.  ``InvoiceLineItemForm`` handles
individual line item entries, and ``PaymentForm`` handles payment
recording.
"""

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    DecimalField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError

from app.forms.order import coerce_int_or_none


# Valid status choices for invoices.
VALID_STATUSES = [
    ("draft", "Draft"),
    ("sent", "Sent"),
    ("viewed", "Viewed"),
    ("partially_paid", "Partially Paid"),
    ("paid", "Paid"),
    ("overdue", "Overdue"),
    ("void", "Void"),
    ("refunded", "Refunded"),
]


class InvoiceForm(FlaskForm):
    """Form for creating and editing an invoice.

    The ``customer_id`` choices must be populated dynamically in the route
    from the current set of customers.
    """

    customer_id = SelectField(
        "Customer",
        coerce=coerce_int_or_none,
        validators=[DataRequired()],
        choices=[("", "-- Select --")],
    )
    status = SelectField(
        "Status",
        choices=VALID_STATUSES,
        default="draft",
    )
    issue_date = DateField(
        "Issue Date",
        validators=[DataRequired()],
        format="%Y-%m-%d",
    )
    due_date = DateField(
        "Due Date",
        validators=[Optional()],
    )
    tax_rate = DecimalField(
        "Tax Rate",
        places=4,
        default=0.0000,
        validators=[Optional(), NumberRange(min=0, max=1)],
    )
    discount_amount = DecimalField(
        "Discount Amount",
        places=2,
        default=0.00,
        validators=[Optional(), NumberRange(min=0)],
    )
    notes = TextAreaField(
        "Internal Notes",
        validators=[Optional(), Length(max=5000)],
    )
    customer_notes = TextAreaField(
        "Customer Notes",
        validators=[Optional(), Length(max=5000)],
    )
    terms = TextAreaField(
        "Terms",
        validators=[Optional(), Length(max=5000)],
    )
    submit = SubmitField("Save Invoice")


class InvoiceSearchForm(FlaskForm):
    """GET-based search / filter form for the invoice list.

    CSRF is disabled because this form is submitted via GET query parameters.
    """

    class Meta:
        csrf = False

    q = StringField("Search", validators=[Optional()])
    status = SelectField(
        "Status",
        choices=[("", "All Statuses")] + VALID_STATUSES,
        default="",
    )
    date_from = DateField(
        "Date From",
        validators=[Optional()],
    )
    date_to = DateField(
        "Date To",
        validators=[Optional()],
    )
    overdue_only = BooleanField(
        "Overdue Only",
        default=False,
    )
    submit = SubmitField("Search")


class InvoiceLineItemForm(FlaskForm):
    """Form for adding or editing an invoice line item."""

    line_type = SelectField(
        "Line Type",
        choices=[
            ("service", "Service"),
            ("labor", "Labor"),
            ("part", "Part"),
            ("fee", "Fee"),
            ("discount", "Discount"),
            ("other", "Other"),
        ],
    )
    description = StringField(
        "Description",
        validators=[DataRequired(), Length(max=500)],
    )
    quantity = DecimalField(
        "Quantity",
        places=2,
        default=1,
        validators=[DataRequired(), NumberRange(min=0.01)],
    )
    unit_price = DecimalField(
        "Unit Price",
        places=2,
        validators=[DataRequired()],
    )
    submit = SubmitField("Add Line Item")

    def validate_unit_price(self, field):
        """Only discount lines may have negative unit price."""
        if field.data is not None and field.data < 0:
            line_type = self.line_type.data if hasattr(self, "line_type") and self.line_type else None
            if line_type != "discount":
                raise ValidationError("Unit price must be non-negative for non-discount line items.")


class PaymentForm(FlaskForm):
    """Form for recording a payment against an invoice."""

    payment_type = SelectField(
        "Payment Type",
        choices=[
            ("payment", "Payment"),
            ("deposit", "Deposit"),
            ("refund", "Refund"),
        ],
    )
    amount = DecimalField(
        "Amount",
        places=2,
        validators=[DataRequired(), NumberRange(min=0.01)],
    )
    payment_date = DateField(
        "Payment Date",
        validators=[DataRequired()],
        format="%Y-%m-%d",
    )
    payment_method = SelectField(
        "Payment Method",
        choices=[
            ("cash", "Cash"),
            ("check", "Check"),
            ("credit_card", "Credit Card"),
            ("debit_card", "Debit Card"),
            ("bank_transfer", "Bank Transfer"),
            ("other", "Other"),
        ],
    )
    reference_number = StringField(
        "Reference Number",
        validators=[Optional(), Length(max=255)],
    )
    notes = StringField(
        "Notes",
        validators=[Optional(), Length(max=500)],
    )
    submit = SubmitField("Record Payment")

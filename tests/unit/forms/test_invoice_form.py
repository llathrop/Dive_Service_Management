"""Unit tests for invoice forms.

Tests cover field validation, default values, and the search form's
CSRF-disabled behaviour for ``InvoiceForm``, ``InvoiceSearchForm``,
``InvoiceLineItemForm``, and ``PaymentForm``.
"""

from datetime import date

import pytest
from werkzeug.datastructures import MultiDict

from app.forms.invoice import (
    InvoiceForm,
    InvoiceLineItemForm,
    InvoiceSearchForm,
    PaymentForm,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# InvoiceForm -- valid data
# ---------------------------------------------------------------------------


class TestInvoiceFormValid:
    """Scenarios where the InvoiceForm should pass validation."""

    def test_valid_invoice_form(self, app, db_session):
        """A form with all required fields passes validation."""
        with app.test_request_context():
            form = InvoiceForm(
                formdata=MultiDict([
                    ("customer_id", "1"),
                    ("status", "draft"),
                    ("issue_date", date.today().isoformat()),
                ])
            )
            form.customer_id.choices = [("", "-- Select --"), (1, "Test Customer")]
            assert form.validate(), form.errors

    def test_valid_invoice_form_all_statuses(self, app, db_session):
        """All valid status values are accepted."""
        statuses = [
            "draft", "sent", "viewed", "partially_paid",
            "paid", "overdue", "void", "refunded",
        ]
        for status in statuses:
            with app.test_request_context():
                form = InvoiceForm(
                    formdata=MultiDict([
                        ("customer_id", "1"),
                        ("status", status),
                        ("issue_date", date.today().isoformat()),
                    ])
                )
                form.customer_id.choices = [("", "-- Select --"), (1, "Test Customer")]
                assert form.validate(), (
                    f"Status '{status}' should be valid: {form.errors}"
                )

    def test_valid_invoice_form_with_optional_fields(self, app, db_session):
        """Optional fields like notes and tax_rate are accepted."""
        with app.test_request_context():
            form = InvoiceForm(
                formdata=MultiDict([
                    ("customer_id", "1"),
                    ("status", "draft"),
                    ("issue_date", date.today().isoformat()),
                    ("due_date", "2026-04-01"),
                    ("tax_rate", "0.0800"),
                    ("discount_amount", "10.00"),
                    ("notes", "Internal note"),
                    ("customer_notes", "Note for customer"),
                    ("terms", "Net 30"),
                ])
            )
            form.customer_id.choices = [("", "-- Select --"), (1, "Test Customer")]
            assert form.validate(), form.errors


# ---------------------------------------------------------------------------
# InvoiceForm -- invalid data
# ---------------------------------------------------------------------------


class TestInvoiceFormInvalid:
    """Scenarios where the InvoiceForm should fail validation."""

    def test_invoice_form_missing_customer(self, app, db_session):
        """Invoice form without a customer_id should fail validation."""
        with app.test_request_context():
            form = InvoiceForm(
                formdata=MultiDict([
                    ("customer_id", ""),
                    ("status", "draft"),
                    ("issue_date", date.today().isoformat()),
                ])
            )
            form.customer_id.choices = [("", "-- Select --"), (1, "Test Customer")]
            assert not form.validate()
            assert "customer_id" in form.errors

    def test_invoice_form_missing_issue_date(self, app, db_session):
        """Invoice form without issue_date should fail validation."""
        with app.test_request_context():
            form = InvoiceForm(
                formdata=MultiDict([
                    ("customer_id", "1"),
                    ("status", "draft"),
                    ("issue_date", ""),
                ])
            )
            form.customer_id.choices = [("", "-- Select --"), (1, "Test Customer")]
            assert not form.validate()
            assert "issue_date" in form.errors

    def test_invoice_form_negative_discount(self, app, db_session):
        """Negative discount_amount should fail validation."""
        with app.test_request_context():
            form = InvoiceForm(
                formdata=MultiDict([
                    ("customer_id", "1"),
                    ("status", "draft"),
                    ("issue_date", date.today().isoformat()),
                    ("discount_amount", "-10.00"),
                ])
            )
            form.customer_id.choices = [("", "-- Select --"), (1, "Test Customer")]
            assert not form.validate()
            assert "discount_amount" in form.errors

    def test_invoice_form_tax_rate_over_one(self, app, db_session):
        """Tax rate above 1 (100%) should fail validation."""
        with app.test_request_context():
            form = InvoiceForm(
                formdata=MultiDict([
                    ("customer_id", "1"),
                    ("status", "draft"),
                    ("issue_date", date.today().isoformat()),
                    ("tax_rate", "1.5000"),
                ])
            )
            form.customer_id.choices = [("", "-- Select --"), (1, "Test Customer")]
            assert not form.validate()
            assert "tax_rate" in form.errors


# ---------------------------------------------------------------------------
# InvoiceForm -- defaults
# ---------------------------------------------------------------------------


class TestInvoiceFormDefaults:
    """Verify that field defaults are applied correctly."""

    def test_defaults_applied(self, app):
        with app.test_request_context():
            form = InvoiceForm()
            assert form.status.data == "draft"
            assert form.tax_rate.data == 0.0000
            assert form.discount_amount.data == 0.00


# ---------------------------------------------------------------------------
# InvoiceSearchForm
# ---------------------------------------------------------------------------


class TestInvoiceSearchForm:
    """Tests for the GET-based invoice search form."""

    def test_csrf_disabled(self, app):
        """Search form should not require a CSRF token."""
        with app.test_request_context():
            form = InvoiceSearchForm()
            assert form.meta.csrf is False

    def test_empty_search_is_valid(self, app):
        """An empty search form is valid (all filters optional)."""
        with app.test_request_context():
            form = InvoiceSearchForm(formdata=MultiDict())
            assert form.validate(), form.errors

    def test_search_with_query(self, app):
        """Search form accepts a query string."""
        with app.test_request_context():
            form = InvoiceSearchForm(
                formdata=MultiDict([("q", "INV-2026")])
            )
            assert form.validate(), form.errors

    def test_search_with_status_filter(self, app):
        """Search form accepts a status filter."""
        with app.test_request_context():
            form = InvoiceSearchForm(
                formdata=MultiDict([("status", "draft")])
            )
            assert form.validate(), form.errors

    def test_search_with_date_range(self, app):
        """Search form accepts date_from and date_to filters."""
        with app.test_request_context():
            form = InvoiceSearchForm(
                formdata=MultiDict([
                    ("date_from", "2026-01-01"),
                    ("date_to", "2026-12-31"),
                ])
            )
            assert form.validate(), form.errors

    def test_search_with_overdue_only(self, app):
        """Search form accepts overdue_only checkbox."""
        with app.test_request_context():
            form = InvoiceSearchForm(
                formdata=MultiDict([("overdue_only", "y")])
            )
            assert form.validate(), form.errors


# ---------------------------------------------------------------------------
# InvoiceLineItemForm
# ---------------------------------------------------------------------------


class TestInvoiceLineItemForm:
    """Tests for the InvoiceLineItemForm."""

    def test_valid_line_item_form(self, app):
        """A form with all required fields passes validation."""
        with app.test_request_context():
            form = InvoiceLineItemForm(
                formdata=MultiDict([
                    ("line_type", "service"),
                    ("description", "Annual Service"),
                    ("quantity", "1.00"),
                    ("unit_price", "150.00"),
                ])
            )
            assert form.validate(), form.errors

    def test_line_item_form_missing_description(self, app):
        """Line item form without description should fail validation."""
        with app.test_request_context():
            form = InvoiceLineItemForm(
                formdata=MultiDict([
                    ("line_type", "service"),
                    ("description", ""),
                    ("quantity", "1.00"),
                    ("unit_price", "150.00"),
                ])
            )
            assert not form.validate()
            assert "description" in form.errors

    def test_line_item_form_missing_unit_price(self, app):
        """Line item form without unit_price should fail validation."""
        with app.test_request_context():
            form = InvoiceLineItemForm(
                formdata=MultiDict([
                    ("line_type", "service"),
                    ("description", "Test"),
                    ("quantity", "1.00"),
                    ("unit_price", ""),
                ])
            )
            assert not form.validate()
            assert "unit_price" in form.errors

    def test_line_item_form_zero_quantity(self, app):
        """Line item form with zero quantity should fail validation."""
        with app.test_request_context():
            form = InvoiceLineItemForm(
                formdata=MultiDict([
                    ("line_type", "service"),
                    ("description", "Test"),
                    ("quantity", "0.00"),
                    ("unit_price", "50.00"),
                ])
            )
            assert not form.validate()
            assert "quantity" in form.errors

    def test_line_item_form_all_line_types(self, app):
        """All valid line_type values are accepted."""
        line_types = ["service", "labor", "part", "fee", "discount", "other"]
        for lt in line_types:
            with app.test_request_context():
                form = InvoiceLineItemForm(
                    formdata=MultiDict([
                        ("line_type", lt),
                        ("description", "Test"),
                        ("quantity", "1.00"),
                        ("unit_price", "50.00"),
                    ])
                )
                assert form.validate(), (
                    f"Line type '{lt}' should be valid: {form.errors}"
                )

    def test_line_item_form_default_quantity(self, app):
        """Line item form defaults quantity to 1."""
        with app.test_request_context():
            form = InvoiceLineItemForm()
            assert form.quantity.data == 1


# ---------------------------------------------------------------------------
# PaymentForm
# ---------------------------------------------------------------------------


class TestPaymentForm:
    """Tests for the PaymentForm."""

    def test_valid_payment_form(self, app):
        """A form with all required fields passes validation."""
        with app.test_request_context():
            form = PaymentForm(
                formdata=MultiDict([
                    ("payment_type", "payment"),
                    ("amount", "100.00"),
                    ("payment_date", date.today().isoformat()),
                    ("payment_method", "cash"),
                ])
            )
            assert form.validate(), form.errors

    def test_payment_form_missing_amount(self, app):
        """Payment form without amount should fail validation."""
        with app.test_request_context():
            form = PaymentForm(
                formdata=MultiDict([
                    ("payment_type", "payment"),
                    ("amount", ""),
                    ("payment_date", date.today().isoformat()),
                    ("payment_method", "cash"),
                ])
            )
            assert not form.validate()
            assert "amount" in form.errors

    def test_payment_form_missing_payment_date(self, app):
        """Payment form without payment_date should fail validation."""
        with app.test_request_context():
            form = PaymentForm(
                formdata=MultiDict([
                    ("payment_type", "payment"),
                    ("amount", "50.00"),
                    ("payment_date", ""),
                    ("payment_method", "cash"),
                ])
            )
            assert not form.validate()
            assert "payment_date" in form.errors

    def test_payment_form_zero_amount(self, app):
        """Payment form with zero amount should fail validation."""
        with app.test_request_context():
            form = PaymentForm(
                formdata=MultiDict([
                    ("payment_type", "payment"),
                    ("amount", "0.00"),
                    ("payment_date", date.today().isoformat()),
                    ("payment_method", "cash"),
                ])
            )
            assert not form.validate()
            assert "amount" in form.errors

    def test_payment_form_all_payment_types(self, app):
        """All valid payment_type values are accepted."""
        for pt in ["payment", "deposit", "refund"]:
            with app.test_request_context():
                form = PaymentForm(
                    formdata=MultiDict([
                        ("payment_type", pt),
                        ("amount", "50.00"),
                        ("payment_date", date.today().isoformat()),
                        ("payment_method", "cash"),
                    ])
                )
                assert form.validate(), (
                    f"Payment type '{pt}' should be valid: {form.errors}"
                )

    def test_payment_form_all_payment_methods(self, app):
        """All valid payment_method values are accepted."""
        methods = [
            "cash", "check", "credit_card",
            "debit_card", "bank_transfer", "other",
        ]
        for method in methods:
            with app.test_request_context():
                form = PaymentForm(
                    formdata=MultiDict([
                        ("payment_type", "payment"),
                        ("amount", "50.00"),
                        ("payment_date", date.today().isoformat()),
                        ("payment_method", method),
                    ])
                )
                assert form.validate(), (
                    f"Payment method '{method}' should be valid: {form.errors}"
                )

    def test_payment_form_with_optional_fields(self, app):
        """Optional fields like reference_number and notes are accepted."""
        with app.test_request_context():
            form = PaymentForm(
                formdata=MultiDict([
                    ("payment_type", "payment"),
                    ("amount", "100.00"),
                    ("payment_date", date.today().isoformat()),
                    ("payment_method", "check"),
                    ("reference_number", "CHK-12345"),
                    ("notes", "Monthly payment"),
                ])
            )
            assert form.validate(), form.errors


# ---------------------------------------------------------------------------
# InvoiceLineItemForm -- negative unit_price validation (P1-6)
# ---------------------------------------------------------------------------


class TestLineItemFormNegativePrice:
    """Tests for the unit_price sign constraint on InvoiceLineItemForm."""

    def test_line_item_form_rejects_negative_for_service(self, app):
        """Form validation fails when unit_price is negative for a service line."""
        with app.test_request_context():
            form = InvoiceLineItemForm(
                formdata=MultiDict([
                    ("line_type", "service"),
                    ("description", "Negative service"),
                    ("quantity", "1.00"),
                    ("unit_price", "-50.00"),
                ])
            )
            assert not form.validate()
            assert "unit_price" in form.errors

    def test_line_item_form_allows_negative_for_discount(self, app):
        """Form validation passes when unit_price is negative for a discount line."""
        with app.test_request_context():
            form = InvoiceLineItemForm(
                formdata=MultiDict([
                    ("line_type", "discount"),
                    ("description", "Coupon discount"),
                    ("quantity", "1.00"),
                    ("unit_price", "-25.00"),
                ])
            )
            assert form.validate(), form.errors

    def test_line_item_form_rejects_negative_for_labor(self, app):
        """Form validation fails when unit_price is negative for a labor line."""
        with app.test_request_context():
            form = InvoiceLineItemForm(
                formdata=MultiDict([
                    ("line_type", "labor"),
                    ("description", "Negative labor"),
                    ("quantity", "1.00"),
                    ("unit_price", "-10.00"),
                ])
            )
            assert not form.validate()
            assert "unit_price" in form.errors

    def test_line_item_form_rejects_negative_for_part(self, app):
        """Form validation fails when unit_price is negative for a part line."""
        with app.test_request_context():
            form = InvoiceLineItemForm(
                formdata=MultiDict([
                    ("line_type", "part"),
                    ("description", "Negative part"),
                    ("quantity", "1.00"),
                    ("unit_price", "-5.00"),
                ])
            )
            assert not form.validate()
            assert "unit_price" in form.errors

    def test_line_item_form_rejects_negative_for_fee(self, app):
        """Form validation fails when unit_price is negative for a fee line."""
        with app.test_request_context():
            form = InvoiceLineItemForm(
                formdata=MultiDict([
                    ("line_type", "fee"),
                    ("description", "Negative fee"),
                    ("quantity", "1.00"),
                    ("unit_price", "-15.00"),
                ])
            )
            assert not form.validate()
            assert "unit_price" in form.errors

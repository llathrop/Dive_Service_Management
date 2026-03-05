"""Unit tests for customer forms.

Tests cover field validation, default values, and the custom
individual-vs-business cross-field validation on ``CustomerForm``.
"""

import pytest
from werkzeug.datastructures import MultiDict

from app.forms.customer import CustomerForm, CustomerSearchForm

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# CustomerForm — valid data
# ---------------------------------------------------------------------------


class TestCustomerFormValid:
    """Scenarios where the form should pass validation."""

    def test_valid_individual_customer(self, app):
        with app.test_request_context():
            form = CustomerForm(
                formdata=MultiDict([
                    ("customer_type", "individual"),
                    ("first_name", "Jane"),
                    ("last_name", "Doe"),
                    ("email", "jane@example.com"),
                ])
            )
            assert form.validate(), form.errors

    def test_valid_business_customer(self, app):
        with app.test_request_context():
            form = CustomerForm(
                formdata=MultiDict([
                    ("customer_type", "business"),
                    ("business_name", "Acme Dive Shop"),
                    ("email", "info@acmedive.com"),
                ])
            )
            assert form.validate(), form.errors

    def test_valid_individual_all_fields(self, app):
        with app.test_request_context():
            form = CustomerForm(
                formdata=MultiDict([
                    ("customer_type", "individual"),
                    ("first_name", "John"),
                    ("last_name", "Smith"),
                    ("email", "john@example.com"),
                    ("phone_primary", "555-1234"),
                    ("phone_secondary", "555-5678"),
                    ("address_line1", "123 Main St"),
                    ("address_line2", "Apt 4"),
                    ("city", "Portland"),
                    ("state_province", "OR"),
                    ("postal_code", "97201"),
                    ("country", "US"),
                    ("preferred_contact", "phone"),
                    ("tax_id", ""),
                    ("payment_terms", "Net 30"),
                    ("credit_limit", "1000.00"),
                    ("notes", "VIP customer"),
                    ("referral_source", "Google"),
                ])
            )
            assert form.validate(), form.errors


# ---------------------------------------------------------------------------
# CustomerForm — required-field and custom-validation failures
# ---------------------------------------------------------------------------


class TestCustomerFormInvalid:
    """Scenarios where the form should fail validation."""

    def test_individual_missing_first_name(self, app):
        with app.test_request_context():
            form = CustomerForm(
                formdata=MultiDict([
                    ("customer_type", "individual"),
                    ("first_name", ""),
                    ("last_name", "Doe"),
                ])
            )
            assert not form.validate()
            assert "first_name" in form.errors

    def test_individual_missing_last_name(self, app):
        with app.test_request_context():
            form = CustomerForm(
                formdata=MultiDict([
                    ("customer_type", "individual"),
                    ("first_name", "Jane"),
                    ("last_name", ""),
                ])
            )
            assert not form.validate()
            assert "last_name" in form.errors

    def test_individual_missing_both_names(self, app):
        with app.test_request_context():
            form = CustomerForm(
                formdata=MultiDict([
                    ("customer_type", "individual"),
                    ("first_name", ""),
                    ("last_name", ""),
                ])
            )
            assert not form.validate()
            assert "first_name" in form.errors
            assert "last_name" in form.errors

    def test_business_missing_business_name(self, app):
        with app.test_request_context():
            form = CustomerForm(
                formdata=MultiDict([
                    ("customer_type", "business"),
                    ("business_name", ""),
                ])
            )
            assert not form.validate()
            assert "business_name" in form.errors

    def test_invalid_email(self, app):
        with app.test_request_context():
            form = CustomerForm(
                formdata=MultiDict([
                    ("customer_type", "individual"),
                    ("first_name", "Jane"),
                    ("last_name", "Doe"),
                    ("email", "not-an-email"),
                ])
            )
            assert not form.validate()
            assert "email" in form.errors


# ---------------------------------------------------------------------------
# CustomerForm — defaults
# ---------------------------------------------------------------------------


class TestCustomerFormDefaults:
    """Verify that field defaults are applied correctly."""

    def test_defaults_applied(self, app):
        with app.test_request_context():
            form = CustomerForm()
            assert form.customer_type.data == "individual"
            assert form.country.data == "US"
            assert form.preferred_contact.data == "email"
            assert form.tax_exempt.data is False


# ---------------------------------------------------------------------------
# CustomerSearchForm
# ---------------------------------------------------------------------------


class TestCustomerSearchForm:
    """Tests for the GET-based customer search form."""

    def test_valid_search(self, app):
        with app.test_request_context():
            form = CustomerSearchForm(
                formdata=MultiDict([("q", "dive")])
            )
            assert form.validate(), form.errors

    def test_empty_search_is_valid(self, app):
        """An empty search form is valid (all filters optional)."""
        with app.test_request_context():
            form = CustomerSearchForm(formdata=MultiDict())
            assert form.validate(), form.errors

    def test_csrf_disabled(self, app):
        """Search form should not require a CSRF token."""
        with app.test_request_context():
            form = CustomerSearchForm()
            assert form.meta.csrf is False

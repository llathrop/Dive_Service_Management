"""Unit tests for service order forms.

Tests cover field validation, default values, and the search form's
CSRF-disabled behaviour for ``ServiceOrderForm`` and ``OrderSearchForm``.
"""

from datetime import date

import pytest
from werkzeug.datastructures import MultiDict

from app.forms.order import OrderSearchForm, ServiceOrderForm

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# ServiceOrderForm -- valid data
# ---------------------------------------------------------------------------


class TestServiceOrderFormValid:
    """Scenarios where the form should pass validation."""

    def test_valid_order_form(self, app, db_session):
        """A form with all required fields passes validation."""
        with app.test_request_context():
            form = ServiceOrderForm(
                formdata=MultiDict([
                    ("customer_id", "1"),
                    ("status", "intake"),
                    ("priority", "normal"),
                    ("date_received", date.today().isoformat()),
                ])
            )
            # Populate choices so customer_id=1 is valid
            form.customer_id.choices = [("", "-- Select --"), (1, "Test Customer")]
            form.assigned_tech_id.choices = [("", "-- Select --")]
            assert form.validate(), form.errors

    def test_valid_order_form_all_priorities(self, app, db_session):
        """All valid priority values are accepted."""
        for priority in ["low", "normal", "high", "rush"]:
            with app.test_request_context():
                form = ServiceOrderForm(
                    formdata=MultiDict([
                        ("customer_id", "1"),
                        ("status", "intake"),
                        ("priority", priority),
                        ("date_received", date.today().isoformat()),
                    ])
                )
                form.customer_id.choices = [("", "-- Select --"), (1, "Test Customer")]
                form.assigned_tech_id.choices = [("", "-- Select --")]
                assert form.validate(), (
                    f"Priority '{priority}' should be valid: {form.errors}"
                )

    def test_valid_order_form_with_optional_fields(self, app, db_session):
        """Optional fields like description and estimated_total are accepted."""
        with app.test_request_context():
            form = ServiceOrderForm(
                formdata=MultiDict([
                    ("customer_id", "1"),
                    ("status", "intake"),
                    ("priority", "normal"),
                    ("date_received", date.today().isoformat()),
                    ("description", "Annual regulator service"),
                    ("estimated_total", "250.00"),
                    ("rush_fee", "50.00"),
                    ("discount_percent", "10.00"),
                    ("discount_amount", "5.00"),
                ])
            )
            form.customer_id.choices = [("", "-- Select --"), (1, "Test Customer")]
            form.assigned_tech_id.choices = [("", "-- Select --")]
            assert form.validate(), form.errors


# ---------------------------------------------------------------------------
# ServiceOrderForm -- invalid data
# ---------------------------------------------------------------------------


class TestServiceOrderFormInvalid:
    """Scenarios where the form should fail validation."""

    def test_order_form_missing_customer(self, app, db_session):
        """Order form without a customer_id should fail validation."""
        with app.test_request_context():
            form = ServiceOrderForm(
                formdata=MultiDict([
                    ("customer_id", ""),
                    ("status", "intake"),
                    ("priority", "normal"),
                    ("date_received", date.today().isoformat()),
                ])
            )
            form.customer_id.choices = [("", "-- Select --"), (1, "Test Customer")]
            form.assigned_tech_id.choices = [("", "-- Select --")]
            assert not form.validate()
            assert "customer_id" in form.errors

    def test_order_form_missing_date_received(self, app, db_session):
        """Order form without date_received should fail validation."""
        with app.test_request_context():
            form = ServiceOrderForm(
                formdata=MultiDict([
                    ("customer_id", "1"),
                    ("status", "intake"),
                    ("priority", "normal"),
                    ("date_received", ""),
                ])
            )
            form.customer_id.choices = [("", "-- Select --"), (1, "Test Customer")]
            form.assigned_tech_id.choices = [("", "-- Select --")]
            assert not form.validate()
            assert "date_received" in form.errors

    def test_order_form_negative_estimated_total(self, app, db_session):
        """Negative estimated_total should fail validation."""
        with app.test_request_context():
            form = ServiceOrderForm(
                formdata=MultiDict([
                    ("customer_id", "1"),
                    ("status", "intake"),
                    ("priority", "normal"),
                    ("date_received", date.today().isoformat()),
                    ("estimated_total", "-100.00"),
                ])
            )
            form.customer_id.choices = [("", "-- Select --"), (1, "Test Customer")]
            form.assigned_tech_id.choices = [("", "-- Select --")]
            assert not form.validate()
            assert "estimated_total" in form.errors


# ---------------------------------------------------------------------------
# ServiceOrderForm -- defaults
# ---------------------------------------------------------------------------


class TestServiceOrderFormDefaults:
    """Verify that field defaults are applied correctly."""

    def test_defaults_applied(self, app):
        with app.test_request_context():
            form = ServiceOrderForm()
            assert form.status.data == "intake"
            assert form.priority.data == "normal"
            assert form.rush_fee.data == 0.00
            assert form.discount_percent.data == 0.00
            assert form.discount_amount.data == 0.00


# ---------------------------------------------------------------------------
# OrderSearchForm
# ---------------------------------------------------------------------------


class TestOrderSearchForm:
    """Tests for the GET-based order search form."""

    def test_csrf_disabled(self, app):
        """Search form should not require a CSRF token."""
        with app.test_request_context():
            form = OrderSearchForm()
            assert form.meta.csrf is False

    def test_empty_search_is_valid(self, app):
        """An empty search form is valid (all filters optional)."""
        with app.test_request_context():
            form = OrderSearchForm(formdata=MultiDict())
            form.assigned_tech_id.choices = [("", "All Technicians")]
            assert form.validate(), form.errors

    def test_search_with_query(self, app):
        """Search form accepts a query string."""
        with app.test_request_context():
            form = OrderSearchForm(
                formdata=MultiDict([("q", "SO-2026")])
            )
            form.assigned_tech_id.choices = [("", "All Technicians")]
            assert form.validate(), form.errors

    def test_search_with_status_filter(self, app):
        """Search form accepts a status filter."""
        with app.test_request_context():
            form = OrderSearchForm(
                formdata=MultiDict([("status", "intake")])
            )
            form.assigned_tech_id.choices = [("", "All Technicians")]
            assert form.validate(), form.errors

    def test_search_with_priority_filter(self, app):
        """Search form accepts a priority filter."""
        with app.test_request_context():
            form = OrderSearchForm(
                formdata=MultiDict([("priority", "rush")])
            )
            form.assigned_tech_id.choices = [("", "All Technicians")]
            assert form.validate(), form.errors

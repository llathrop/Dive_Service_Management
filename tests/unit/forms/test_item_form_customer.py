"""Unit tests for ServiceItemForm customer_id requirement."""

import pytest
from werkzeug.datastructures import MultiDict

from app.forms.item import ServiceItemForm

pytestmark = pytest.mark.unit


class TestItemFormCustomerRequired:
    """Verify customer_id is required on the service item form."""

    def test_item_form_customer_id_required(self, app):
        """Form should be invalid without customer_id."""
        with app.test_request_context():
            form = ServiceItemForm(
                formdata=MultiDict([
                    ("name", "Test Regulator"),
                    ("item_category", "Regulator"),
                ])
            )
            # Need to set choices for SelectField validation
            form.customer_id.choices = [(1, "Test Customer")]
            assert not form.validate()
            assert "customer_id" in form.errors

    def test_item_form_customer_id_valid(self, app):
        """Form should be valid with customer_id provided."""
        with app.test_request_context():
            form = ServiceItemForm(
                formdata=MultiDict([
                    ("name", "Test Regulator"),
                    ("item_category", "Regulator"),
                    ("customer_id", "1"),
                ])
            )
            form.customer_id.choices = [(1, "Test Customer")]
            assert form.validate(), form.errors

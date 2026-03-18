"""Test that the invoice create form includes the quick-create customer option."""

import pytest

from tests.factories import BaseFactory, CustomerFactory


@pytest.fixture(autouse=True)
def _bind_factories(db_session):
    """Bind Factory Boy factories to the test database session."""
    BaseFactory._meta.sqlalchemy_session = db_session
    CustomerFactory._meta.sqlalchemy_session = db_session


class TestInvoiceCustomerDropdown:
    """Verify the invoice create form includes the Create New Customer option."""

    def test_invoice_form_has_create_new_customer_option(self, admin_client):
        """The customer dropdown on invoice create has '+ Create New Customer'."""
        resp = admin_client.get("/invoices/new")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Create New Customer" in html

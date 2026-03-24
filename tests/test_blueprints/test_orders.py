"""Tests for quick-create-customer route on the orders blueprint."""

import pytest

from app.models.customer import Customer

pytestmark = pytest.mark.blueprint


QUICK_CREATE_URL = "/orders/quick-create-customer"


class TestQuickCreateCustomerSuccess:
    """POST /orders/quick-create-customer creates a customer and returns JSON."""

    def test_quick_create_customer_success(self, admin_client, app):
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "customer_type": "individual",
            "first_name": "Jane",
            "last_name": "Diver",
            "email": "jane@example.com",
            "phone_primary": "555-0101",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert "id" in data
        assert data["display_name"] == "Jane Diver"

        # Verify the customer was actually persisted
        with app.app_context():
            customer = Customer.query.get(data["id"])
            assert customer is not None
            assert customer.email == "jane@example.com"
            assert customer.phone_primary == "555-0101"

    def test_quick_create_customer_technician(self, logged_in_client):
        """Technician role can also quick-create customers."""
        resp = logged_in_client.post(QUICK_CREATE_URL, data={
            "customer_type": "individual",
            "first_name": "Bob",
            "last_name": "Tech",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["display_name"] == "Bob Tech"


class TestQuickCreateCustomerAuth:
    """Authentication and authorization checks."""

    def test_quick_create_customer_requires_auth(self, client):
        resp = client.post(QUICK_CREATE_URL, data={
            "customer_type": "individual",
            "first_name": "No",
            "last_name": "Auth",
        })
        # Unauthenticated users get redirected to login or get 403
        assert resp.status_code in (302, 403)

    def test_quick_create_customer_requires_role(self, viewer_client):
        resp = viewer_client.post(QUICK_CREATE_URL, data={
            "customer_type": "individual",
            "first_name": "No",
            "last_name": "Role",
        })
        assert resp.status_code == 403


class TestQuickCreateCustomerValidation:
    """Validation error cases."""

    def test_quick_create_customer_missing_name(self, admin_client):
        """Individual type without first+last name returns 400."""
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "customer_type": "individual",
            "first_name": "OnlyFirst",
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert "last name" in data["error"].lower()

    def test_quick_create_customer_missing_business_name(self, admin_client):
        """Business type without business_name returns 400."""
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "customer_type": "business",
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert "business name" in data["error"].lower()

    def test_quick_create_customer_duplicate_email(self, admin_client, app, db_session):
        """Duplicate email is handled gracefully.

        The Customer model does not enforce a unique constraint on email,
        so duplicates are allowed.  If a unique constraint *were* added in
        the future, the route returns 409 with an error message instead of
        crashing.  We test both the current (no constraint) and the
        IntegrityError guard by verifying the route doesn't 500.
        """
        # Create first customer
        resp1 = admin_client.post(QUICK_CREATE_URL, data={
            "customer_type": "individual",
            "first_name": "First",
            "last_name": "Customer",
            "email": "dupe@example.com",
        })
        assert resp1.status_code == 201

        # Second with same email -- succeeds because no unique constraint
        resp2 = admin_client.post(QUICK_CREATE_URL, data={
            "customer_type": "individual",
            "first_name": "Second",
            "last_name": "Customer",
            "email": "dupe@example.com",
        })
        # Should be 201 (no constraint) or 409 (if constraint added)
        assert resp2.status_code in (201, 409)
        data = resp2.get_json()
        if resp2.status_code == 409:
            assert "error" in data
        else:
            assert "id" in data


class TestQuickCreateCustomerBusiness:
    """Business customer type tests."""

    def test_quick_create_customer_business_type(self, admin_client, app):
        resp = admin_client.post(QUICK_CREATE_URL, data={
            "customer_type": "business",
            "business_name": "Acme Dive Shop",
            "email": "info@acmedive.com",
            "phone_primary": "555-0202",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["display_name"] == "Acme Dive Shop"

        with app.app_context():
            customer = Customer.query.get(data["id"])
            assert customer.customer_type == "business"
            assert customer.business_name == "Acme Dive Shop"

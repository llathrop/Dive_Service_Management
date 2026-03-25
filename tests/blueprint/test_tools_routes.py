"""Blueprint tests for tools routes.

Tests the tools hub and individual tool pages, verifying
authenticated access returns 200 and unauthenticated access redirects
to login.
"""

import pytest

pytestmark = pytest.mark.blueprint


# ---------------------------------------------------------------------------
# Anonymous access (should redirect to login)
# ---------------------------------------------------------------------------


class TestUnauthenticated:
    """Anonymous users are redirected to the login page."""

    def test_hub_unauthenticated_redirects(self, client):
        response = client.get("/tools/")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_seal_calculator_unauthenticated_redirects(self, client):
        response = client.get("/tools/seal-calculator")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_material_estimator_unauthenticated_redirects(self, client):
        response = client.get("/tools/material-estimator")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_pricing_calculator_unauthenticated_redirects(self, client):
        response = client.get("/tools/pricing-calculator")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_leak_test_log_unauthenticated_redirects(self, client):
        response = client.get("/tools/leak-test-log")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_valve_reference_unauthenticated_redirects(self, client):
        response = client.get("/tools/valve-reference")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_converter_unauthenticated_redirects(self, client):
        response = client.get("/tools/converter")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_shipping_calculator_unauthenticated_redirects(self, client):
        response = client.get("/tools/shipping-calculator")
        assert response.status_code == 302
        assert "/login" in response.location


# ---------------------------------------------------------------------------
# Authenticated access
# ---------------------------------------------------------------------------


class TestAuthenticatedAccess:
    """Authenticated users can access all tool endpoints."""

    def test_hub_authenticated(self, logged_in_client, app, db_session):
        response = logged_in_client.get("/tools/")
        assert response.status_code == 200

    def test_seal_calculator(self, logged_in_client, app, db_session):
        response = logged_in_client.get("/tools/seal-calculator")
        assert response.status_code == 200

    def test_material_estimator(self, logged_in_client, app, db_session):
        response = logged_in_client.get("/tools/material-estimator")
        assert response.status_code == 200

    def test_pricing_calculator(self, logged_in_client, app, db_session):
        response = logged_in_client.get("/tools/pricing-calculator")
        assert response.status_code == 200

    def test_leak_test_log(self, logged_in_client, app, db_session):
        response = logged_in_client.get("/tools/leak-test-log")
        assert response.status_code == 200

    def test_valve_reference(self, logged_in_client, app, db_session):
        response = logged_in_client.get("/tools/valve-reference")
        assert response.status_code == 200

    def test_converter(self, logged_in_client, app, db_session):
        response = logged_in_client.get("/tools/converter")
        assert response.status_code == 200

    def test_shipping_calculator(self, logged_in_client, app, db_session):
        response = logged_in_client.get("/tools/shipping-calculator")
        assert response.status_code == 200
        assert b"Shipping Calculator" in response.data
        assert b"Local pickup stays at $0.00" in response.data

    def test_shipping_calculator_estimate(self, logged_in_client, app, db_session):
        response = logged_in_client.get(
            "/tools/shipping-calculator/estimate?provider_code=fedex&shipping_method=fedex_ground&weight_lbs=8&destination_postal_code=90210&destination_country=US"
        )
        assert response.status_code == 200
        assert b"FedEx" in response.data
        assert b"90210" in response.data

    def test_shipping_calculator_invalid_provider_shows_error(self, logged_in_client, app, db_session):
        response = logged_in_client.get(
            f"/tools/shipping-calculator/estimate?provider_code={'x' * 51}"
        )
        assert response.status_code == 200
        assert b"Provider Code must be 50 characters or fewer." in response.data

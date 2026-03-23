"""Tests for CSRF protection on admin import forms."""

import io

import pytest
from flask_security import hash_password

from app import create_app
from app.config import TestingConfig
from app.extensions import db as _db


CUSTOMER_CSV = (
    "Type,First Name,Last Name,Business Name,Contact Person,Email,Phone,"
    "Address,City,State,Postal Code,Country,Preferred Contact,Tax Exempt,Notes\n"
    "individual,John,Doe,,,,555-1234,123 Main St,Portland,OR,97201,US,email,No,Test\n"
)


class CsrfTestingConfig(TestingConfig):
    """TestingConfig with CSRF enforcement enabled."""

    WTF_CSRF_ENABLED = True


@pytest.fixture()
def csrf_app():
    """Create a Flask app with CSRF protection enabled."""
    app = create_app(CsrfTestingConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def csrf_admin_client(csrf_app):
    """Admin client on the CSRF-enabled app."""
    with csrf_app.app_context():
        user_datastore = csrf_app.extensions["security"].datastore
        admin_role = user_datastore.find_or_create_role(
            name="admin", description="Full system access"
        )
        user = user_datastore.create_user(
            username="csrfadmin",
            email="csrfadmin@example.com",
            password=hash_password("password"),
            first_name="Csrf",
            last_name="Admin",
        )
        user_datastore.add_role_to_user(user, admin_role)
        _db.session.commit()

    client = csrf_app.test_client()
    # Login — CSRF is enforced, but Flask-Security login form generates its own token
    # Use GET to obtain the CSRF token first
    resp = client.get("/login")
    assert resp.status_code == 200
    html = resp.data.decode()
    # Extract csrf_token from the login form
    import re
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    assert match, "Could not find csrf_token on login page"
    token = match.group(1)

    resp = client.post(
        "/login",
        data={"email": "csrfadmin@example.com", "password": "password", "csrf_token": token},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/dashboard" in resp.location

    with client:
        yield client


def _get_csrf_token(client, url):
    """Fetch a page and extract the csrf_token hidden input value."""
    import re
    resp = client.get(url)
    assert resp.status_code == 200
    html = resp.data.decode()
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    assert match, f"No csrf_token found on {url}"
    return match.group(1)


class TestCsrfTokenPresent:
    """Verify that import form templates include CSRF tokens."""

    def test_import_form_contains_csrf_token(self, admin_client):
        """The import form page should include a csrf_token hidden input."""
        resp = admin_client.get("/admin/data/import?type=customers")
        assert resp.status_code == 200
        assert b'name="csrf_token"' in resp.data

    def test_import_preview_contains_csrf_token(self, admin_client):
        """The import preview page should include a csrf_token hidden input."""
        data = {
            "action": "preview",
            "entity_type": "customers",
            "csv_file": (io.BytesIO(CUSTOMER_CSV.encode()), "customers.csv"),
        }
        resp = admin_client.post(
            "/admin/data/import?type=customers",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        assert b'name="csrf_token"' in resp.data


class TestCsrfEnforcement:
    """Verify CSRF enforcement when WTF_CSRF_ENABLED=True."""

    def test_import_post_without_csrf_rejected(self, csrf_admin_client):
        """POST to import without CSRF token should be rejected (400)."""
        data = {
            "action": "preview",
            "entity_type": "customers",
            "csv_file": (io.BytesIO(CUSTOMER_CSV.encode()), "customers.csv"),
        }
        resp = csrf_admin_client.post(
            "/admin/data/import?type=customers",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_import_post_with_csrf_accepted(self, csrf_admin_client):
        """POST to import with valid CSRF token should be accepted."""
        token = _get_csrf_token(csrf_admin_client, "/admin/data/import?type=customers")
        data = {
            "action": "preview",
            "entity_type": "customers",
            "csv_file": (io.BytesIO(CUSTOMER_CSV.encode()), "customers.csv"),
            "csrf_token": token,
        }
        resp = csrf_admin_client.post(
            "/admin/data/import?type=customers",
            data=data,
            content_type="multipart/form-data",
        )
        # Should get 200 (preview page), not 400 (CSRF error)
        assert resp.status_code == 200
        assert b"Preview" in resp.data

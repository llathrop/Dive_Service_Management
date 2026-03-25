"""Blueprint tests for portal authentication routes."""

import pytest

from app.models.portal_user import PortalAccessToken, PortalUser
from tests.factories import CustomerFactory


pytestmark = pytest.mark.blueprint


def _set_session(db_session):
    CustomerFactory._meta.sqlalchemy_session = db_session


def _create_portal_user(db_session, customer, email="portal@example.com", password="portal-pass"):
    user = PortalUser(customer_id=customer.id, email=email)
    user.set_password(password)
    user.active = True
    db_session.add(user)
    db_session.commit()
    return user


def test_portal_root_redirects_to_login(client):
    """Anonymous GET /portal/ redirects to the portal login page."""
    response = client.get("/portal/")
    assert response.status_code == 302
    assert "/portal/login" in response.location


def test_portal_login_page_renders(client):
    """GET /portal/login renders the customer portal sign-in page."""
    response = client.get("/portal/login")
    assert response.status_code == 200
    html = response.data.decode().lower()
    assert "sign in" in html
    assert "email" in html


def test_portal_login_failure_stays_on_page(app, db_session, client):
    """Wrong portal credentials should not authenticate the session."""
    _set_session(db_session)
    customer = CustomerFactory(first_name="Login", last_name="Failure")
    _create_portal_user(db_session, customer, password="correct-pass")

    response = client.post(
        "/portal/login",
        data={"email": "portal@example.com", "password": "wrong-pass"},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert response.location is None
    assert b"Invalid email or password." in response.data


def test_portal_activation_flow_creates_user_and_logs_in(app, db_session, client):
    """Valid activation token creates a portal account and logs the user in."""
    _set_session(db_session)
    customer = CustomerFactory(first_name="Activation", last_name="Target")
    token_row, raw_token = PortalAccessToken.issue_activation(
        customer=customer,
        email="activation@example.com",
    )
    db_session.commit()

    response = client.get(f"/portal/activate/{raw_token}")
    assert response.status_code == 200
    assert b"Set your portal password" in response.data

    response = client.post(
        f"/portal/activate/{raw_token}",
        data={"password": "portal-pass", "confirm_password": "portal-pass"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/portal/dashboard" in response.location

    created_user = PortalUser.query.filter_by(email="activation@example.com").one()
    assert created_user.active is True
    assert created_user.customer_id == customer.id
    assert token_row.used_at is not None

    portal_response = client.get("/portal/dashboard")
    assert portal_response.status_code == 200, portal_response.location
    assert b"Welcome" in portal_response.data


def test_portal_activation_rejects_stale_token_after_reissue(app, db_session, client):
    """An older token should be rejected after a newer one has been issued and used."""
    _set_session(db_session)
    customer = CustomerFactory(first_name="Stale", last_name="Target")
    old_token, old_raw = PortalAccessToken.issue_activation(
        customer=customer,
        email="stale@example.com",
    )
    db_session.commit()

    new_token, new_raw = PortalAccessToken.issue_activation(
        customer=customer,
        email="stale@example.com",
    )
    db_session.commit()

    response = client.post(
        f"/portal/activate/{new_raw}",
        data={"password": "portal-pass", "confirm_password": "portal-pass"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/portal/dashboard" in response.location

    db_session.refresh(old_token)
    db_session.refresh(new_token)

    stale_response = client.get(f"/portal/activate/{old_raw}", follow_redirects=False)
    assert stale_response.status_code == 404

    created_user = PortalUser.query.filter_by(email="stale@example.com").one()
    assert created_user.active is True
    assert new_token.portal_user_id == created_user.id
    assert old_token.used_at is not None


def test_portal_used_token_rejected_after_activation(app, db_session, client):
    """A token cannot be reused once it has already activated the account."""
    _set_session(db_session)
    customer = CustomerFactory(first_name="Used", last_name="Target")
    token, raw_token = PortalAccessToken.issue_activation(
        customer=customer,
        email="used@example.com",
    )
    db_session.commit()

    response = client.post(
        f"/portal/activate/{raw_token}",
        data={"password": "portal-pass", "confirm_password": "portal-pass"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    db_session.refresh(token)

    reused_get = client.get(f"/portal/activate/{raw_token}", follow_redirects=False)
    assert reused_get.status_code == 404

    reused_post = client.post(
        f"/portal/activate/{raw_token}",
        data={"password": "portal-pass-2", "confirm_password": "portal-pass-2"},
        follow_redirects=False,
    )
    assert reused_post.status_code == 404
    assert token.used_at is not None


def test_portal_login_does_not_authenticate_internal_dashboard(app, db_session, client):
    """Logging into the portal should not grant Flask-Security staff access."""
    _set_session(db_session)
    customer = CustomerFactory(first_name="Separate", last_name="Session")
    _create_portal_user(db_session, customer)

    response = client.post(
        "/portal/login",
        data={"email": "portal@example.com", "password": "portal-pass"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/portal/dashboard" in response.location

    internal_response = client.get("/dashboard/", follow_redirects=False)
    assert internal_response.status_code == 302
    assert "/login" in internal_response.location


def test_portal_logout_is_post_only(app, db_session, client):
    """Portal logout should be a POST-only action and sign the user out."""
    _set_session(db_session)
    customer = CustomerFactory(first_name="Logout", last_name="Target")
    _create_portal_user(db_session, customer)

    response = client.post(
        "/portal/login",
        data={"email": "portal@example.com", "password": "portal-pass"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/portal/dashboard" in response.location

    logout_get = client.get("/portal/logout", follow_redirects=False)
    assert logout_get.status_code == 405

    logout_post = client.post("/portal/logout", follow_redirects=False)
    assert logout_post.status_code == 302
    assert "/portal/login" in logout_post.location

    dashboard_response = client.get("/portal/dashboard", follow_redirects=False)
    assert dashboard_response.status_code == 302
    assert "/portal/login" in dashboard_response.location

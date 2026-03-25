"""Blueprint tests for customer portal invites."""

import pytest

from app.models.portal_user import PortalAccessToken
from tests.factories import BaseFactory, CustomerFactory


pytestmark = pytest.mark.blueprint


@pytest.fixture(autouse=True)
def _bind_factories(db_session):
    for factory in (BaseFactory, CustomerFactory):
        factory._meta.sqlalchemy_session = db_session


def test_admin_can_send_portal_invite(admin_client, db_session, monkeypatch):
    """Admins can issue portal invites from the customer detail page."""
    customer = CustomerFactory(
        first_name="Invite",
        last_name="Target",
        email="invite@example.com",
    )
    captured = {}

    def fake_send_email(to_address, subject, html_body, text_body=None):
        captured["to_address"] = to_address
        captured["subject"] = subject
        captured["html_body"] = html_body
        captured["text_body"] = text_body
        return True

    monkeypatch.setattr("app.blueprints.customers.email_service.send_email", fake_send_email)

    response = admin_client.post(
        f"/customers/{customer.id}/portal-invite",
        data={"email": "portal@example.com"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert f"/customers/{customer.id}" in response.location

    token = PortalAccessToken.query.filter_by(customer_id=customer.id).one()
    assert token.email == "portal@example.com"
    assert captured["to_address"] == "portal@example.com"
    assert "portal invite" in captured["subject"].lower()
    assert "Activate your account" in captured["html_body"]


def test_customer_detail_shows_portal_management_card(admin_client, db_session):
    """Customer detail should surface portal invite management for admins."""
    customer = CustomerFactory(
        first_name="Portal",
        last_name="Customer",
        email="portal-customer@example.com",
    )
    PortalAccessToken.issue_activation(customer, "portal-customer@example.com")
    db_session.commit()

    response = admin_client.get(f"/customers/{customer.id}")
    assert response.status_code == 200
    html = response.data.decode()
    assert "Customer Portal" in html
    assert "Send Invite" in html
    assert "Invite History" in html

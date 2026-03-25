"""Unit tests for the portal auth models."""

from datetime import timedelta

import pytest

from app.models.portal_user import PortalAccessToken, PortalUser
from tests.factories import CustomerFactory


pytestmark = pytest.mark.unit


def _set_session(db_session):
    CustomerFactory._meta.sqlalchemy_session = db_session


def test_portal_user_creation_and_relationship(app, db_session):
    """Portal users persist separately from internal users and link to customers."""
    _set_session(db_session)
    customer = CustomerFactory(first_name="Portal", last_name="Customer")

    user = PortalUser(customer_id=customer.id, email="Portal@Example.com")
    user.set_password("portal-password")
    db_session.add(user)
    db_session.commit()

    fetched = db_session.get(PortalUser, user.id)
    assert fetched is not None
    assert fetched.email == "portal@example.com"
    assert fetched.check_password("portal-password") is True
    assert fetched.customer.id == customer.id
    assert fetched.display_name == customer.display_name
    assert fetched.is_authenticated is True
    assert fetched.is_anonymous is False
    assert fetched.is_active is False
    assert customer.portal_users.count() == 1


def test_portal_activation_token_issue_and_lookup(app, db_session):
    """Activation tokens are hashed at rest and can be looked up by raw token."""
    _set_session(db_session)
    customer = CustomerFactory(first_name="Invite", last_name="Target")

    token, raw_token = PortalAccessToken.issue_activation(
        customer=customer,
        email="invite@example.com",
        expires_in=timedelta(hours=1),
    )
    db_session.commit()

    assert token.token_hash != raw_token
    assert len(token.token_hash) == 64
    assert PortalAccessToken.lookup_valid_token(raw_token) == token
    assert token.is_valid is True


def test_portal_activation_token_reissue_revokes_older_token_and_reuses_user(
    app, db_session
):
    """Reissuing an invite revokes the previous unused token and reuses the account."""
    _set_session(db_session)
    customer = CustomerFactory(first_name="Reuse", last_name="Target")

    first_token, first_raw = PortalAccessToken.issue_activation(
        customer=customer,
        email="reuse@example.com",
        expires_in=timedelta(hours=1),
    )
    db_session.commit()

    existing_user = PortalUser(customer_id=customer.id, email="reuse@example.com")
    existing_user.set_password("portal-password")
    existing_user.active = True
    db_session.add(existing_user)
    db_session.commit()

    second_token, second_raw = PortalAccessToken.issue_activation(
        customer=customer,
        email="reuse@example.com",
        expires_in=timedelta(hours=1),
    )
    db_session.commit()

    db_session.refresh(first_token)
    db_session.refresh(second_token)

    assert first_token.used_at is not None
    assert PortalAccessToken.lookup_valid_token(first_raw) is None
    assert second_token.portal_user_id == existing_user.id
    assert PortalAccessToken.lookup_valid_token(second_raw) == second_token
    assert customer.portal_users.count() == 1


def test_portal_activation_token_expiry_and_consumption(app, db_session):
    """Expired or used tokens are no longer valid."""
    _set_session(db_session)
    customer = CustomerFactory(first_name="Expire", last_name="Target")
    token, raw_token = PortalAccessToken.issue_activation(
        customer=customer,
        email="expire@example.com",
        expires_in=timedelta(minutes=5),
    )
    db_session.commit()

    token.used_at = token.expires_at
    db_session.commit()
    assert token.is_used is True
    assert PortalAccessToken.lookup_valid_token(raw_token) is None

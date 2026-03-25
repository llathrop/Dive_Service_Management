"""Blueprint tests for the customer portal dashboard and order tracking."""

from datetime import date

import pytest

from app.models.portal_user import PortalUser
from app.services import order_service
from tests.factories import (
    BaseFactory,
    CustomerFactory,
    ServiceItemFactory,
    ServiceNoteFactory,
    ServiceOrderFactory,
    ServiceOrderItemFactory,
    UserFactory,
)


pytestmark = pytest.mark.blueprint


@pytest.fixture(autouse=True)
def _bind_factories(db_session):
    for factory in (
        BaseFactory,
        CustomerFactory,
        ServiceItemFactory,
        ServiceOrderFactory,
        ServiceOrderItemFactory,
        ServiceNoteFactory,
        UserFactory,
    ):
        factory._meta.sqlalchemy_session = db_session


def _create_portal_user(db_session, customer, email="portal@example.com", password="portal-pass"):
    user = PortalUser(customer_id=customer.id, email=email)
    user.set_password(password)
    user.active = True
    db_session.add(user)
    db_session.commit()
    return user


def _login_portal(client, email="portal@example.com", password="portal-pass"):
    response = client.post(
        "/portal/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/portal/dashboard" in response.location


def test_dashboard_shows_only_customer_orders(app, db_session, client):
    """Dashboard content must be scoped to the signed-in portal customer."""
    customer = CustomerFactory(first_name="Portal", last_name="Owner")
    other_customer = CustomerFactory(first_name="Other", last_name="Owner")
    _create_portal_user(db_session, customer)

    own_order = ServiceOrderFactory(
        customer=customer,
        status="in_progress",
        date_received=date(2026, 3, 3),
        description="Own order",
    )
    other_order = ServiceOrderFactory(
        customer=other_customer,
        status="intake",
        date_received=date(2026, 3, 4),
        description="Other order",
    )
    db_session.commit()

    _login_portal(client)

    response = client.get("/portal/dashboard")
    assert response.status_code == 200
    html = response.data.decode()
    assert own_order.order_number in html
    assert other_order.order_number not in html


def test_order_detail_shows_safe_tracking_and_hides_internal_notes(app, db_session, client):
    """Order tracking should expose only customer-safe detail for the signed-in customer."""
    customer = CustomerFactory(first_name="Portal", last_name="Owner")
    other_customer = CustomerFactory(first_name="Other", last_name="Owner")
    _create_portal_user(db_session, customer)

    item = ServiceItemFactory(customer=customer, name="Drysuit", serial_number="DS-777")
    order = ServiceOrderFactory(
        customer=customer,
        description="Service the zipper and seals",
        date_received=date(2026, 3, 1),
        date_promised=date(2026, 3, 10),
    )
    order_item = ServiceOrderItemFactory(
        order=order,
        service_item=item,
        work_description="Replace the zipper",
        condition_at_receipt="Minor abrasion on the leg panel.",
    )
    user = UserFactory()
    ServiceNoteFactory(
        order_item=order_item,
        note_type="customer_communication",
        note_text="We found a leak near the zipper and will update you after testing.",
        created_by=user.id,
    )
    ServiceNoteFactory(
        order_item=order_item,
        note_type="testing",
        note_text="Internal pressure test log.",
        created_by=user.id,
    )
    other_order = ServiceOrderFactory(customer=other_customer)
    db_session.commit()

    order_service.change_status(order.id, "assessment", user_id=user.id)
    db_session.commit()

    _login_portal(client)

    response = client.get(f"/portal/orders/{order.id}")
    assert response.status_code == 200
    html = response.data.decode()
    assert order.order_number in html
    assert "Replace the zipper" in html
    assert "Internal pressure test log." not in html
    assert "We found a leak near the zipper" in html
    assert "Intake" in html and "Assessment" in html
    assert "Estimated total" in html

    forbidden = client.get(f"/portal/orders/{other_order.id}")
    assert forbidden.status_code == 404


def test_dashboard_links_to_order_detail(app, db_session, client):
    """Dashboard cards should link to the portal order detail page."""
    customer = CustomerFactory(first_name="Portal", last_name="Owner")
    _create_portal_user(db_session, customer)
    order = ServiceOrderFactory(customer=customer, status="completed")
    db_session.commit()

    _login_portal(client)

    response = client.get("/portal/dashboard")
    html = response.data.decode()
    assert f"/portal/orders/{order.id}" in html

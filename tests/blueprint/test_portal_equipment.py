"""Blueprint tests for portal equipment routes."""

import pytest

from app.models.portal_user import PortalUser
from tests.factories import (
    AttachmentFactory,
    BaseFactory,
    CustomerFactory,
    ServiceItemFactory,
    ServiceOrderFactory,
    ServiceOrderItemFactory,
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
        AttachmentFactory,
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


def test_portal_equipment_list_shows_only_owned_items(client, db_session):
    """Portal equipment list should only show the signed-in customer's items."""
    customer = CustomerFactory(first_name="Portal", last_name="Owner")
    owned_item = ServiceItemFactory(customer=customer, name="Owned Suit")
    other_customer = CustomerFactory()
    ServiceItemFactory(customer=other_customer, name="Other Regulator")
    _create_portal_user(db_session, customer)

    _login_portal(client)
    response = client.get("/portal/equipment")
    assert response.status_code == 200
    html = response.data.decode()
    assert "Owned Suit" in html
    assert "Other Regulator" not in html


def test_portal_equipment_detail_shows_history_and_safe_media(client, db_session):
    """Portal equipment detail should show customer-safe history and attachments."""
    customer = CustomerFactory(first_name="Portal", last_name="History")
    item = ServiceItemFactory(customer=customer, name="Serviceable Drysuit")
    completed_order = ServiceOrderFactory(customer=customer, status="completed")
    completed_order_item = ServiceOrderItemFactory(
        order=completed_order,
        service_item=item,
        work_description="Replace neck seal",
    )
    AttachmentFactory(
        attachable_type="service_order_item",
        attachable_id=completed_order_item.id,
        filename="service.jpg",
    )
    AttachmentFactory(
        attachable_type="service_order_item",
        attachable_id=completed_order_item.id,
        filename="service-report.pdf",
        stored_filename="service-report.pdf",
        file_path="attachments/service_order_item/2026/03/service-report.pdf",
        mime_type="application/pdf",
    )
    open_order = ServiceOrderFactory(customer=customer, status="in_progress")
    open_order_item = ServiceOrderItemFactory(order=open_order, service_item=item)
    AttachmentFactory(
        attachable_type="service_order_item",
        attachable_id=open_order_item.id,
        filename="hidden.jpg",
    )
    _create_portal_user(db_session, customer)

    _login_portal(client)
    response = client.get(f"/portal/equipment/{item.id}")
    assert response.status_code == 200
    html = response.data.decode()
    assert "Serviceable Drysuit" in html
    assert completed_order.order_number in html
    assert "Replace neck seal" in html
    assert "direct.jpg" not in html
    assert "service.jpg" in html
    assert "service-report.pdf" not in html
    assert "hidden.jpg" not in html


def test_portal_equipment_media_route_blocks_other_customers(client, db_session):
    """Media routes must enforce customer ownership."""
    customer = CustomerFactory(first_name="Portal", last_name="Media")
    item = ServiceItemFactory(customer=customer, name="Owned Item")
    direct_attachment = AttachmentFactory(
        attachable_type="service_item",
        attachable_id=item.id,
        filename="direct.jpg",
    )
    _create_portal_user(db_session, customer)

    _login_portal(client)
    response = client.get(
        f"/portal/equipment/{item.id}/media/{direct_attachment.id}",
        follow_redirects=False,
    )
    assert response.status_code == 404


def test_portal_equipment_media_route_blocks_non_image_files(client, db_session):
    """Portal equipment media routes must not expose non-image attachments."""
    customer = CustomerFactory(first_name="Portal", last_name="Media")
    item = ServiceItemFactory(customer=customer, name="Owned Item")
    completed_order = ServiceOrderFactory(customer=customer, status="completed")
    completed_order_item = ServiceOrderItemFactory(
        order=completed_order,
        service_item=item,
    )
    pdf_attachment = AttachmentFactory(
        attachable_type="service_order_item",
        attachable_id=completed_order_item.id,
        filename="service-report.pdf",
        stored_filename="service-report.pdf",
        file_path="attachments/service_order_item/2026/03/service-report.pdf",
        mime_type="application/pdf",
    )
    _create_portal_user(db_session, customer)

    _login_portal(client)
    response = client.get(
        f"/portal/equipment/{item.id}/media/{pdf_attachment.id}",
        follow_redirects=False,
    )
    assert response.status_code == 404

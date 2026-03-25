"""Unit tests for portal service helpers."""

from datetime import date

import pytest
from werkzeug.exceptions import NotFound

from app.models.portal_user import PortalAccessToken, PortalUser
from app.services import order_service, portal_service
from tests.factories import (
    AttachmentFactory,
    AuditLogFactory,
    BaseFactory,
    CustomerFactory,
    ServiceItemFactory,
    ServiceNoteFactory,
    ServiceOrderFactory,
    ServiceOrderItemFactory,
    UserFactory,
)


pytestmark = pytest.mark.unit


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
        AuditLogFactory,
        AttachmentFactory,
    ):
        factory._meta.sqlalchemy_session = db_session


def test_get_customer_dashboard_scopes_orders(app, db_session):
    """The portal dashboard should only include the customer's own orders."""
    customer = CustomerFactory(first_name="Portal", last_name="Owner")
    other_customer = CustomerFactory(first_name="Other", last_name="Owner")

    active_order = ServiceOrderFactory(
        customer=customer,
        status="ready_for_pickup",
        date_received=date(2026, 3, 1),
    )
    recent_order = ServiceOrderFactory(
        customer=customer,
        status="completed",
        date_received=date(2026, 2, 28),
    )
    ServiceOrderFactory(
        customer=other_customer,
        status="intake",
        date_received=date(2026, 3, 2),
    )
    db_session.commit()

    dashboard = portal_service.get_customer_dashboard(customer.id)

    assert dashboard["active_count"] == 1
    assert dashboard["recent_count"] == 2
    assert [order["id"] for order in dashboard["active_orders"]] == [active_order.id]
    assert [order["id"] for order in dashboard["recent_orders"]] == [
        active_order.id,
        recent_order.id,
    ]


def test_get_customer_order_rejects_other_customer_order(app, db_session):
    """Portal reads must not cross customer boundaries."""
    customer = CustomerFactory(first_name="Portal", last_name="Owner")
    other_customer = CustomerFactory(first_name="Other", last_name="Owner")
    order = ServiceOrderFactory(customer=other_customer)
    db_session.commit()

    with pytest.raises(NotFound):
        portal_service.get_customer_order(customer.id, order.id)


def test_get_customer_order_detail_includes_only_public_notes_and_history(
    app, db_session
):
    """Portal order detail should expose only customer-safe notes and status history."""
    customer = CustomerFactory(first_name="Portal", last_name="Owner")
    other_customer = CustomerFactory(first_name="Other", last_name="Owner")
    item = ServiceItemFactory(customer=customer, name="Drysuit", serial_number="DS-123")
    leaked_item = ServiceItemFactory(
        customer=other_customer,
        name="Do Not Leak",
        serial_number="LEAK-123",
        brand="Leaky Brand",
        model="Leaky Model",
    )
    order = ServiceOrderFactory(customer=customer, description="Repair the zipper")
    order_item = ServiceOrderItemFactory(
        order=order,
        service_item=item,
        work_description="Replace zipper",
        condition_at_receipt="Small tear near the ankle.",
    )
    ServiceOrderItemFactory(
        order=order,
        service_item=leaked_item,
        work_description="Mismatched item",
        condition_at_receipt="Should not appear in portal.",
    )
    user = UserFactory()
    ServiceNoteFactory(
        order_item=order_item,
        note_type="customer_communication",
        note_text="We found a zipper leak and will proceed after approval.",
        created_by=user.id,
    )
    ServiceNoteFactory(
        order_item=order_item,
        note_type="diagnostic",
        note_text="Internal pressure test details.",
        created_by=user.id,
    )
    order_service.change_status(order.id, "assessment", user_id=user.id)
    db_session.commit()

    detail = portal_service.get_customer_order_detail(customer.id, order.id)

    assert detail["order"].id == order.id
    assert detail["summary"]["estimated_total"] is not None
    assert len(detail["items"]) == 1
    assert detail["items"][0]["notes"][0]["note_text"].startswith(
        "We found a zipper leak"
    )
    assert "Do Not Leak" not in str(detail)
    assert "LEAK-123" not in str(detail)
    assert detail["status_history"][0]["new_value"] == "assessment"
    assert len(detail["status_history"]) == 1


def test_create_portal_invite_reuses_existing_user_and_revokes_old_token(
    app, db_session
):
    """Reissuing a portal invite should reuse the account and revoke the old token."""
    customer = CustomerFactory(email="customer@example.com")
    portal_user = PortalUser(customer_id=customer.id, email="portal@example.com")
    portal_user.set_password("portal-password")
    portal_user.active = True
    db_session.add(portal_user)
    db_session.commit()

    first_token, first_raw = portal_service.create_portal_invite(
        customer.id,
        email="portal@example.com",
    )
    second_token, second_raw = portal_service.create_portal_invite(
        customer.id,
        email="portal@example.com",
    )

    db_session.refresh(first_token)
    db_session.refresh(second_token)

    assert first_token.used_at is not None
    assert first_token.portal_user_id == portal_user.id
    assert second_token.portal_user_id == portal_user.id
    assert PortalAccessToken.lookup_valid_token(first_raw) is None
    assert PortalAccessToken.lookup_valid_token(second_raw) == second_token


def test_get_customer_portal_media_filters_nonmatching_orders(app, db_session):
    """Only safe service-visit media for the customer-owned item should be returned."""
    customer = CustomerFactory()
    item = ServiceItemFactory(customer=customer)

    completed_order = ServiceOrderFactory(customer=customer, status="completed")
    completed_order_item = ServiceOrderItemFactory(order=completed_order, service_item=item)
    direct_attachment = AttachmentFactory(
        attachable_type="service_item",
        attachable_id=item.id,
        filename="direct.jpg",
    )
    completed_attachment = AttachmentFactory(
        attachable_type="service_order_item",
        attachable_id=completed_order_item.id,
        filename="completed.jpg",
    )

    open_order = ServiceOrderFactory(customer=customer, status="in_progress")
    open_order_item = ServiceOrderItemFactory(order=open_order, service_item=item)
    hidden_attachment = AttachmentFactory(
        attachable_type="service_order_item",
        attachable_id=open_order_item.id,
        filename="hidden.jpg",
    )

    other_customer = CustomerFactory()
    other_item = ServiceItemFactory(customer=other_customer)
    other_order = ServiceOrderFactory(customer=other_customer, status="completed")
    other_order_item = ServiceOrderItemFactory(order=other_order, service_item=other_item)
    other_attachment = AttachmentFactory(
        attachable_type="service_order_item",
        attachable_id=other_order_item.id,
        filename="other.jpg",
    )

    direct_media, service_media = portal_service.get_customer_portal_media(
        customer.id,
        item.id,
    )

    assert direct_media == []
    assert len(service_media) == 1
    assert service_media[0]["order"].id == completed_order.id
<<<<<<< HEAD
    assert [att.id for att in service_media[0]["attachments"]] == [
        completed_attachment.id
    ]
    assert hidden_attachment.id not in [
        att.id for group in service_media for att in group["attachments"]
    ]
    assert other_attachment.id not in [
        att.id for group in service_media for att in group["attachments"]
    ]
    assert direct_attachment.id not in [
        att.id for group in service_media for att in group["attachments"]
    ]


def test_get_portal_attachment_rejects_direct_item_attachments(app, db_session):
=======
    assert [att.id for att in service_media[0]["attachments"]] == [completed_attachment.id]
    assert hidden_attachment.id not in [att.id for group in service_media for att in group["attachments"]]
    assert other_attachment.id not in [att.id for group in service_media for att in group["attachments"]]
    assert direct_attachment.id not in [att.id for group in service_media for att in group["attachments"]]


def test_get_portal_attachment_rejects_cross_customer_attachment(app, db_session):
>>>>>>> ad9356b (Harden portal equipment media exposure)
    """Raw service-item attachments must not be served through the portal."""
    customer = CustomerFactory()
    item = ServiceItemFactory(customer=customer)
    direct_attachment = AttachmentFactory(
        attachable_type="service_item",
        attachable_id=item.id,
        filename="direct.jpg",
    )

    with pytest.raises(NotFound):
        portal_service.get_portal_attachment(
            customer.id,
            item.id,
            direct_attachment.id,
        )

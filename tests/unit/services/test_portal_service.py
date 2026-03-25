"""Unit tests for portal_service."""

from datetime import date

import pytest
from werkzeug.exceptions import NotFound

from app.services import order_service, portal_service
from tests.factories import (
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
    ):
        factory._meta.sqlalchemy_session = db_session


def test_get_customer_dashboard_scopes_orders(app, db_session):
    """The portal dashboard should only include the customer's own orders."""
    customer = CustomerFactory(first_name="Portal", last_name="Owner")
    other_customer = CustomerFactory(first_name="Other", last_name="Owner")

    active_order = ServiceOrderFactory(customer=customer, status="in_progress", date_received=date(2026, 3, 1))
    recent_order = ServiceOrderFactory(customer=customer, status="completed", date_received=date(2026, 2, 28))
    ServiceOrderFactory(customer=other_customer, status="intake", date_received=date(2026, 3, 2))
    db_session.commit()

    dashboard = portal_service.get_customer_dashboard(customer.id)

    assert dashboard["active_count"] == 1
    assert dashboard["recent_count"] == 2
    assert [order["id"] for order in dashboard["active_orders"]] == [active_order.id]
    assert [order["id"] for order in dashboard["recent_orders"]] == [active_order.id, recent_order.id]


def test_get_customer_order_rejects_other_customer_order(app, db_session):
    """Portal reads must not cross customer boundaries."""
    customer = CustomerFactory(first_name="Portal", last_name="Owner")
    other_customer = CustomerFactory(first_name="Other", last_name="Owner")
    order = ServiceOrderFactory(customer=other_customer)
    db_session.commit()

    with pytest.raises(NotFound):
        portal_service.get_customer_order(customer.id, order.id)


def test_get_customer_order_detail_includes_only_public_notes_and_history(app, db_session):
    """Portal order detail should expose only customer-safe notes and status history."""
    customer = CustomerFactory(first_name="Portal", last_name="Owner")
    item = ServiceItemFactory(customer=customer, name="Drysuit", serial_number="DS-123")
    order = ServiceOrderFactory(customer=customer, description="Repair the zipper")
    order_item = ServiceOrderItemFactory(
        order=order,
        service_item=item,
        work_description="Replace zipper",
        condition_at_receipt="Small tear near the ankle.",
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
    assert detail["items"][0]["notes"][0]["note_text"].startswith("We found a zipper leak")
    assert detail["status_history"][0]["new_value"] == "assessment"
    assert len(detail["status_history"]) == 1

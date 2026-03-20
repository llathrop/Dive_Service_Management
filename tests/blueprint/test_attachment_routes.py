"""Blueprint tests for attachment routes including unified gallery."""

import pytest

from tests.factories import (
    AttachmentFactory,
    CustomerFactory,
    ServiceItemFactory,
    ServiceOrderFactory,
    ServiceOrderItemFactory,
)

pytestmark = pytest.mark.blueprint


def _set_session(db_session):
    """Configure all factories to use the test DB session."""
    for factory_cls in (
        AttachmentFactory,
        CustomerFactory,
        ServiceItemFactory,
        ServiceOrderFactory,
        ServiceOrderItemFactory,
    ):
        factory_cls._meta.sqlalchemy_session = db_session


class TestUnifiedGalleryEndpoint:
    """Tests for GET /attachments/gallery/unified/<service_item_id>."""

    def test_returns_html(self, app, db_session, logged_in_client):
        """Authenticated request returns 200 with HTML content."""
        _set_session(db_session)
        item = ServiceItemFactory()
        AttachmentFactory(attachable_type="service_item", attachable_id=item.id)

        resp = logged_in_client.get(
            f"/attachments/gallery/unified/{item.id}"
        )

        assert resp.status_code == 200
        assert b"Item Photos" in resp.data

    def test_requires_login(self, app, client):
        """Unauthenticated request redirects to login."""
        resp = client.get("/attachments/gallery/unified/1")

        assert resp.status_code == 302
        assert "/login" in resp.location

    def test_shows_service_visit_section(self, app, db_session, logged_in_client):
        """Response includes service visit photos section."""
        _set_session(db_session)
        item = ServiceItemFactory()
        oi = ServiceOrderItemFactory(service_item=item)
        AttachmentFactory(
            attachable_type="service_order_item", attachable_id=oi.id
        )

        resp = logged_in_client.get(
            f"/attachments/gallery/unified/{item.id}"
        )

        assert resp.status_code == 200
        assert b"Service Visit Photos" in resp.data
        assert oi.order.order_number.encode() in resp.data

    def test_empty_item(self, app, db_session, logged_in_client):
        """Item with no attachments shows empty state messages."""
        _set_session(db_session)
        item = ServiceItemFactory()

        resp = logged_in_client.get(
            f"/attachments/gallery/unified/{item.id}"
        )

        assert resp.status_code == 200
        assert b"No item photos" in resp.data
        assert b"No service visit photos" in resp.data

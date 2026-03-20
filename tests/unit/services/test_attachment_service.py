"""Unit tests for attachment service unified gallery function."""

import pytest

from app.services import attachment_service
from tests.factories import (
    AttachmentFactory,
    CustomerFactory,
    ServiceItemFactory,
    ServiceOrderFactory,
    ServiceOrderItemFactory,
)

pytestmark = pytest.mark.unit


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


class TestGetUnifiedAttachments:
    """Tests for get_unified_attachments()."""

    def test_direct_only(self, app, db_session):
        """Item with direct photos but no service order history."""
        _set_session(db_session)
        item = ServiceItemFactory()
        AttachmentFactory(attachable_type="service_item", attachable_id=item.id)
        AttachmentFactory(attachable_type="service_item", attachable_id=item.id)

        direct, order_atts = attachment_service.get_unified_attachments(item.id)

        assert len(direct) == 2
        assert len(order_atts) == 0

    def test_from_orders_only(self, app, db_session):
        """Item with order photos but no direct photos."""
        _set_session(db_session)
        item = ServiceItemFactory()
        oi = ServiceOrderItemFactory(service_item=item)
        AttachmentFactory(attachable_type="service_order_item", attachable_id=oi.id)

        direct, order_atts = attachment_service.get_unified_attachments(item.id)

        assert len(direct) == 0
        assert len(order_atts) == 1
        assert len(order_atts[0]["attachments"]) == 1
        assert order_atts[0]["order_item"] == oi

    def test_combined(self, app, db_session):
        """Item with both direct and order photos."""
        _set_session(db_session)
        item = ServiceItemFactory()
        AttachmentFactory(attachable_type="service_item", attachable_id=item.id)

        oi1 = ServiceOrderItemFactory(service_item=item)
        oi2 = ServiceOrderItemFactory(service_item=item)
        AttachmentFactory(attachable_type="service_order_item", attachable_id=oi1.id)
        AttachmentFactory(attachable_type="service_order_item", attachable_id=oi2.id)
        AttachmentFactory(attachable_type="service_order_item", attachable_id=oi2.id)

        direct, order_atts = attachment_service.get_unified_attachments(item.id)

        assert len(direct) == 1
        assert len(order_atts) == 2
        # Find the group for oi2 — it should have 2 attachments
        oi2_group = [g for g in order_atts if g["order_item"].id == oi2.id][0]
        assert len(oi2_group["attachments"]) == 2

    def test_excludes_other_items(self, app, db_session):
        """Attachments from unrelated items are not included."""
        _set_session(db_session)
        item = ServiceItemFactory()
        other_item = ServiceItemFactory()
        AttachmentFactory(attachable_type="service_item", attachable_id=item.id)
        AttachmentFactory(attachable_type="service_item", attachable_id=other_item.id)

        direct, order_atts = attachment_service.get_unified_attachments(item.id)

        assert len(direct) == 1
        assert len(order_atts) == 0

    def test_empty_results(self, app, db_session):
        """Item with no attachments at all."""
        _set_session(db_session)
        item = ServiceItemFactory()

        direct, order_atts = attachment_service.get_unified_attachments(item.id)

        assert len(direct) == 0
        assert len(order_atts) == 0

    def test_order_items_without_attachments_excluded(self, app, db_session):
        """Order items with no attachments don't appear in results."""
        _set_session(db_session)
        item = ServiceItemFactory()
        # Create an order item but no attachments for it
        ServiceOrderItemFactory(service_item=item)

        direct, order_atts = attachment_service.get_unified_attachments(item.id)

        assert len(order_atts) == 0

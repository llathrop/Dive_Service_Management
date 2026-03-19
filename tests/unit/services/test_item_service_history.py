"""Unit tests for item_service.get_service_history()."""

import pytest

from app.services import item_service
from tests.factories import (
    BaseFactory,
    CustomerFactory,
    ServiceItemFactory,
    ServiceOrderFactory,
    ServiceOrderItemFactory,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _bind_factories(db_session):
    for f in (BaseFactory, CustomerFactory, ServiceItemFactory,
              ServiceOrderFactory, ServiceOrderItemFactory):
        f._meta.sqlalchemy_session = db_session


class TestGetServiceHistory:
    """Tests for get_service_history()."""

    def test_get_service_history_returns_orders(self, app, db_session):
        """Service history returns order items for an item."""
        customer = CustomerFactory()
        item = ServiceItemFactory(customer=customer)
        order = ServiceOrderFactory(customer=customer)
        oi = ServiceOrderItemFactory(order=order, service_item=item,
                                     work_description="Annual service")
        db_session.commit()

        history = item_service.get_service_history(item.id)
        assert len(history) == 1
        assert history[0].id == oi.id
        assert history[0].order.order_number == order.order_number

    def test_get_service_history_excludes_deleted(self, app, db_session):
        """Deleted orders should not appear in service history."""
        customer = CustomerFactory()
        item = ServiceItemFactory(customer=customer)
        order = ServiceOrderFactory(customer=customer)
        ServiceOrderItemFactory(order=order, service_item=item)
        order.soft_delete()
        db_session.commit()

        history = item_service.get_service_history(item.id)
        assert len(history) == 0

    def test_get_service_history_empty(self, app, db_session):
        """An item with no orders returns an empty list."""
        customer = CustomerFactory()
        item = ServiceItemFactory(customer=customer)
        db_session.commit()

        history = item_service.get_service_history(item.id)
        assert history == []

"""Unit tests for the AppliedService model.

Tests cover creation, the calculate_line_total method with and without
discounts, and relationships to order items and price list items.
"""

from decimal import Decimal

import pytest

from app.extensions import db
from app.models.applied_service import AppliedService
from tests.factories import (
    AppliedServiceFactory,
    CustomerFactory,
    InventoryItemFactory,
    PriceListCategoryFactory,
    PriceListItemFactory,
    ServiceItemFactory,
    ServiceOrderFactory,
    ServiceOrderItemFactory,
)

pytestmark = pytest.mark.unit


def _set_session(db_session):
    """Configure all factories to use the given session."""
    AppliedServiceFactory._meta.sqlalchemy_session = db_session
    ServiceOrderFactory._meta.sqlalchemy_session = db_session
    ServiceOrderItemFactory._meta.sqlalchemy_session = db_session
    CustomerFactory._meta.sqlalchemy_session = db_session
    ServiceItemFactory._meta.sqlalchemy_session = db_session
    InventoryItemFactory._meta.sqlalchemy_session = db_session
    PriceListItemFactory._meta.sqlalchemy_session = db_session
    PriceListCategoryFactory._meta.sqlalchemy_session = db_session


class TestAppliedServiceCreation:
    """Tests for basic AppliedService creation and persistence."""

    def test_create_applied_service(self, app, db_session):
        """An AppliedService persists all fields correctly."""
        _set_session(db_session)
        svc = AppliedServiceFactory(
            service_name="Full Regulator Service",
            quantity=Decimal("1.00"),
            unit_price=Decimal("150.00"),
            line_total=Decimal("150.00"),
        )

        fetched = db_session.get(AppliedService, svc.id)
        assert fetched is not None
        assert fetched.service_name == "Full Regulator Service"
        assert fetched.quantity == Decimal("1.00")
        assert fetched.unit_price == Decimal("150.00")
        assert fetched.line_total == Decimal("150.00")

    def test_defaults(self, app, db_session):
        """Default values are applied correctly."""
        _set_session(db_session)
        svc = AppliedServiceFactory()

        assert svc.is_taxable is True
        assert svc.price_overridden is False
        assert svc.customer_approved is False
        assert svc.discount_percent == Decimal("0.00")


class TestAppliedServiceCalculation:
    """Tests for the calculate_line_total method."""

    def test_calculate_line_total(self, app, db_session):
        """calculate_line_total computes quantity * unit_price with no discount."""
        _set_session(db_session)
        svc = AppliedServiceFactory(
            quantity=Decimal("2.00"),
            unit_price=Decimal("100.00"),
            discount_percent=Decimal("0.00"),
            line_total=Decimal("0"),
        )
        svc.calculate_line_total()

        assert svc.line_total == Decimal("200.00")

    def test_calculate_line_total_with_discount(self, app, db_session):
        """calculate_line_total applies discount_percent correctly."""
        _set_session(db_session)
        svc = AppliedServiceFactory(
            quantity=Decimal("1.00"),
            unit_price=Decimal("200.00"),
            discount_percent=Decimal("10.00"),
            line_total=Decimal("0"),
        )
        svc.calculate_line_total()

        # 200 * (1 - 10/100) = 200 * 0.90 = 180.00
        assert svc.line_total == Decimal("180.00")

    def test_calculate_line_total_with_quantity_and_discount(self, app, db_session):
        """calculate_line_total handles both quantity and discount."""
        _set_session(db_session)
        svc = AppliedServiceFactory(
            quantity=Decimal("3.00"),
            unit_price=Decimal("50.00"),
            discount_percent=Decimal("20.00"),
            line_total=Decimal("0"),
        )
        svc.calculate_line_total()

        # (3 * 50) * (1 - 20/100) = 150 * 0.80 = 120.00
        assert svc.line_total == Decimal("120.00")


class TestAppliedServiceRelationships:
    """Tests for model relationships."""

    def test_order_item_relationship(self, app, db_session):
        """An AppliedService links to its parent order item."""
        _set_session(db_session)
        item = ServiceOrderItemFactory()
        svc = AppliedServiceFactory(order_item=item)

        assert svc.order_item.id == item.id

    def test_price_list_item_relationship(self, app, db_session):
        """An AppliedService can link to a price list item."""
        _set_session(db_session)
        pli = PriceListItemFactory(name="Standard Service", price=Decimal("99.00"))
        svc = AppliedServiceFactory(
            price_list_item=pli,
            service_name="Standard Service",
        )

        assert svc.price_list_item is not None
        assert svc.price_list_item.id == pli.id
        assert svc.price_list_item.name == "Standard Service"

    def test_no_price_list_item(self, app, db_session):
        """An AppliedService can have no price list item (custom service)."""
        _set_session(db_session)
        svc = AppliedServiceFactory(price_list_item=None)

        assert svc.price_list_item_id is None
        assert svc.price_list_item is None


class TestAppliedServiceRepr:
    """Tests for __repr__."""

    def test_repr(self, app, db_session):
        """__repr__ includes id and service_name."""
        _set_session(db_session)
        svc = AppliedServiceFactory(service_name="Valve Rebuild")
        expected = f"<AppliedService {svc.id} 'Valve Rebuild'>"
        assert repr(svc) == expected

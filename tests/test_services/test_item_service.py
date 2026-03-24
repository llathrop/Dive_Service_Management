"""Tests for the item service layer."""

import pytest
from werkzeug.exceptions import NotFound

from app.services import item_service
from tests.factories import BaseFactory, CustomerFactory, ServiceItemFactory

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _bind_factories(db_session):
    BaseFactory._meta.sqlalchemy_session = db_session
    CustomerFactory._meta.sqlalchemy_session = db_session
    ServiceItemFactory._meta.sqlalchemy_session = db_session


class TestGetItems:
    """Tests for item_service.get_items()."""

    def test_returns_paginated_results(self, app, db_session):
        ServiceItemFactory.create_batch(3)

        result = item_service.get_items(page=1, per_page=25)
        assert result.total == 3

    def test_search_filters_by_name(self, app, db_session):
        ServiceItemFactory(name="Scubapro MK25")
        ServiceItemFactory(name="Aqualung Legend")

        result = item_service.get_items(search="Scubapro")
        assert result.total == 1
        assert result.items[0].name == "Scubapro MK25"

    def test_search_filters_by_serial(self, app, db_session):
        ServiceItemFactory(serial_number="SN-UNIQUE-123")
        ServiceItemFactory(serial_number="SN-OTHER-456")

        result = item_service.get_items(search="UNIQUE")
        assert result.total == 1

    def test_excludes_soft_deleted(self, app, db_session):
        item = ServiceItemFactory()
        item.soft_delete()
        db_session.commit()

        result = item_service.get_items()
        assert result.total == 0

    def test_sorting(self, app, db_session):
        ServiceItemFactory(name="Zebra Reg")
        ServiceItemFactory(name="Alpha BCD")

        result = item_service.get_items(sort="name", order="asc")
        names = [i.name for i in result.items]
        assert names == ["Alpha BCD", "Zebra Reg"]


class TestGetItem:
    """Tests for item_service.get_item()."""

    def test_returns_item_by_id(self, app, db_session):
        item = ServiceItemFactory()

        result = item_service.get_item(item.id)
        assert result.id == item.id

    def test_raises_404_for_nonexistent(self, app, db_session):
        with pytest.raises(NotFound):
            item_service.get_item(9999)

    def test_raises_404_for_soft_deleted(self, app, db_session):
        item = ServiceItemFactory()
        item.soft_delete()
        db_session.commit()

        with pytest.raises(NotFound):
            item_service.get_item(item.id)


class TestCreateItem:
    """Tests for item_service.create_item()."""

    def test_creates_basic_item(self, app, db_session):
        customer = CustomerFactory()
        data = {
            "name": "Test Regulator",
            "item_category": "Regulator",
            "serviceability": "serviceable",
            "customer_id": customer.id,
        }
        item = item_service.create_item(data, created_by=1)
        assert item.id is not None
        assert item.name == "Test Regulator"
        assert item.created_by == 1

    def test_creates_item_with_drysuit_details(self, app, db_session):
        customer = CustomerFactory()
        data = {
            "name": "My Drysuit",
            "item_category": "Drysuit",
            "customer_id": customer.id,
        }
        drysuit_data = {
            "size": "L",
            "material_type": "Trilaminate",
            "neck_seal_type": "Latex",
        }
        item = item_service.create_item(data, drysuit_data=drysuit_data)
        assert item.drysuit_details is not None
        assert item.drysuit_details.size == "L"
        assert item.drysuit_details.material_type == "Trilaminate"

    def test_creates_item_with_customer(self, app, db_session):
        customer = CustomerFactory()

        data = {
            "name": "Customer BCD",
            "customer_id": customer.id,
        }
        item = item_service.create_item(data)
        assert item.customer_id == customer.id

    def test_empty_serial_stored_as_none(self, app, db_session):
        customer = CustomerFactory()
        data = {"name": "No Serial", "serial_number": "", "customer_id": customer.id}
        item = item_service.create_item(data)
        assert item.serial_number is None


class TestUpdateItem:
    """Tests for item_service.update_item()."""

    def test_updates_fields(self, app, db_session):
        item = ServiceItemFactory(name="Old Name")

        result = item_service.update_item(item.id, {"name": "New Name"})
        assert result.name == "New Name"

    def test_clears_empty_serial(self, app, db_session):
        item = ServiceItemFactory(serial_number="SN-123")

        result = item_service.update_item(
            item.id, {"serial_number": "", "name": item.name}
        )
        assert result.serial_number is None

    def test_raises_404_for_nonexistent(self, app, db_session):
        with pytest.raises(NotFound):
            item_service.update_item(9999, {"name": "Test"})


class TestDeleteItem:
    """Tests for item_service.delete_item()."""

    def test_soft_deletes_item(self, app, db_session):
        item = ServiceItemFactory()

        result = item_service.delete_item(item.id)
        assert result.is_deleted is True

    def test_raises_404_for_nonexistent(self, app, db_session):
        with pytest.raises(NotFound):
            item_service.delete_item(9999)


class TestLookupBySerial:
    """Tests for item_service.lookup_by_serial()."""

    def test_finds_item_by_serial(self, app, db_session):
        ServiceItemFactory(serial_number="LOOKUP-SN-001")

        result = item_service.lookup_by_serial("LOOKUP-SN-001")
        assert result is not None
        assert result.serial_number == "LOOKUP-SN-001"

    def test_returns_none_for_no_match(self, app, db_session):
        result = item_service.lookup_by_serial("NONEXISTENT-SN")
        assert result is None

    def test_returns_none_for_empty_serial(self, app, db_session):
        result = item_service.lookup_by_serial("")
        assert result is None

    def test_excludes_soft_deleted(self, app, db_session):
        item = ServiceItemFactory(serial_number="DELETED-SN")
        item.soft_delete()
        db_session.commit()

        result = item_service.lookup_by_serial("DELETED-SN")
        assert result is None

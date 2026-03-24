"""Tests for the price list service layer."""

from decimal import Decimal

import pytest
from werkzeug.exceptions import NotFound

from app.services import price_list_service
from tests.factories import PriceListCategoryFactory, PriceListItemFactory

pytestmark = pytest.mark.unit


class TestGetCategories:
    """Tests for price_list_service.get_categories()."""

    def test_returns_active_categories(self, app, db_session):
        PriceListCategoryFactory._meta.sqlalchemy_session = db_session
        PriceListCategoryFactory(is_active=True, name="Active Cat")
        PriceListCategoryFactory(is_active=False, name="Inactive Cat")

        result = price_list_service.get_categories(active_only=True)
        assert len(result) == 1
        assert result[0].name == "Active Cat"

    def test_returns_all_categories(self, app, db_session):
        PriceListCategoryFactory._meta.sqlalchemy_session = db_session
        PriceListCategoryFactory(is_active=True)
        PriceListCategoryFactory(is_active=False)

        result = price_list_service.get_categories(active_only=False)
        assert len(result) == 2

    def test_ordered_by_sort_order(self, app, db_session):
        PriceListCategoryFactory._meta.sqlalchemy_session = db_session
        PriceListCategoryFactory(sort_order=2, name="Second")
        PriceListCategoryFactory(sort_order=1, name="First")

        result = price_list_service.get_categories()
        assert result[0].name == "First"
        assert result[1].name == "Second"


class TestGetCategory:
    """Tests for price_list_service.get_category()."""

    def test_returns_category_by_id(self, app, db_session):
        PriceListCategoryFactory._meta.sqlalchemy_session = db_session
        cat = PriceListCategoryFactory()

        result = price_list_service.get_category(cat.id)
        assert result.id == cat.id

    def test_raises_404_for_nonexistent(self, app, db_session):
        with pytest.raises(NotFound):
            price_list_service.get_category(9999)


class TestCreateCategory:
    """Tests for price_list_service.create_category()."""

    def test_creates_category(self, app, db_session):
        data = {"name": "New Category", "sort_order": 5}
        result = price_list_service.create_category(data)
        assert result.id is not None
        assert result.name == "New Category"
        assert result.sort_order == 5

    def test_defaults(self, app, db_session):
        data = {"name": "Minimal"}
        result = price_list_service.create_category(data)
        assert result.sort_order == 0
        assert result.is_active is True


class TestUpdateCategory:
    """Tests for price_list_service.update_category()."""

    def test_updates_fields(self, app, db_session):
        PriceListCategoryFactory._meta.sqlalchemy_session = db_session
        cat = PriceListCategoryFactory(name="Old Name")

        result = price_list_service.update_category(cat.id, {"name": "New Name"})
        assert result.name == "New Name"

    def test_raises_404_for_nonexistent(self, app, db_session):
        with pytest.raises(NotFound):
            price_list_service.update_category(9999, {"name": "Test"})


class TestGetPriceListItems:
    """Tests for price_list_service.get_price_list_items()."""

    def test_returns_items(self, app, db_session):
        PriceListCategoryFactory._meta.sqlalchemy_session = db_session
        PriceListItemFactory._meta.sqlalchemy_session = db_session
        cat = PriceListCategoryFactory()
        PriceListItemFactory(category=cat)

        result = price_list_service.get_price_list_items()
        assert len(result) >= 1

    def test_filters_by_category(self, app, db_session):
        PriceListCategoryFactory._meta.sqlalchemy_session = db_session
        PriceListItemFactory._meta.sqlalchemy_session = db_session
        cat1 = PriceListCategoryFactory(name="Cat 1")
        cat2 = PriceListCategoryFactory(name="Cat 2")
        PriceListItemFactory(category=cat1, name="Item in Cat 1")
        PriceListItemFactory(category=cat2, name="Item in Cat 2")

        result = price_list_service.get_price_list_items(category_id=cat1.id)
        assert len(result) == 1
        assert result[0].name == "Item in Cat 1"

    def test_filters_active_only(self, app, db_session):
        PriceListCategoryFactory._meta.sqlalchemy_session = db_session
        PriceListItemFactory._meta.sqlalchemy_session = db_session
        cat = PriceListCategoryFactory()
        PriceListItemFactory(category=cat, is_active=True, name="Active")
        PriceListItemFactory(category=cat, is_active=False, name="Inactive")

        result = price_list_service.get_price_list_items(active_only=True)
        names = [i.name for i in result]
        assert "Active" in names
        assert "Inactive" not in names

    def test_search(self, app, db_session):
        PriceListCategoryFactory._meta.sqlalchemy_session = db_session
        PriceListItemFactory._meta.sqlalchemy_session = db_session
        cat = PriceListCategoryFactory()
        PriceListItemFactory(category=cat, name="Regulator Service")
        PriceListItemFactory(category=cat, name="Tank Inspection")

        result = price_list_service.get_price_list_items(search="Regulator")
        assert len(result) == 1
        assert result[0].name == "Regulator Service"


class TestGetPriceListItem:
    """Tests for price_list_service.get_price_list_item()."""

    def test_returns_item_by_id(self, app, db_session):
        PriceListCategoryFactory._meta.sqlalchemy_session = db_session
        PriceListItemFactory._meta.sqlalchemy_session = db_session
        item = PriceListItemFactory()

        result = price_list_service.get_price_list_item(item.id)
        assert result.id == item.id

    def test_raises_404_for_nonexistent(self, app, db_session):
        with pytest.raises(NotFound):
            price_list_service.get_price_list_item(9999)


class TestCreatePriceListItem:
    """Tests for price_list_service.create_price_list_item()."""

    def test_creates_item(self, app, db_session):
        PriceListCategoryFactory._meta.sqlalchemy_session = db_session
        cat = PriceListCategoryFactory()

        data = {
            "category_id": cat.id,
            "name": "New Service",
            "price": Decimal("99.99"),
        }
        item = price_list_service.create_price_list_item(data, updated_by=1)
        assert item.id is not None
        assert item.name == "New Service"
        assert item.updated_by == 1


class TestUpdatePriceListItem:
    """Tests for price_list_service.update_price_list_item()."""

    def test_updates_fields(self, app, db_session):
        PriceListCategoryFactory._meta.sqlalchemy_session = db_session
        PriceListItemFactory._meta.sqlalchemy_session = db_session
        item = PriceListItemFactory(name="Old Service")

        result = price_list_service.update_price_list_item(
            item.id, {"name": "Updated Service"}, updated_by=1
        )
        assert result.name == "Updated Service"
        assert result.updated_by == 1

    def test_raises_404_for_nonexistent(self, app, db_session):
        with pytest.raises(NotFound):
            price_list_service.update_price_list_item(9999, {"name": "Test"})


class TestDuplicatePriceListItem:
    """Tests for price_list_service.duplicate_price_list_item()."""

    def test_duplicates_item(self, app, db_session):
        PriceListCategoryFactory._meta.sqlalchemy_session = db_session
        PriceListItemFactory._meta.sqlalchemy_session = db_session
        original = PriceListItemFactory(name="Original Service")

        dup = price_list_service.duplicate_price_list_item(original.id)
        assert dup.id != original.id
        assert dup.name == "Original Service (Copy)"
        assert dup.code is None
        assert dup.price == original.price
        assert dup.category_id == original.category_id

    def test_raises_404_for_nonexistent(self, app, db_session):
        with pytest.raises(NotFound):
            price_list_service.duplicate_price_list_item(9999)

"""Tests for part linking UI on price list items.

Covers the HTMX endpoints for linking and unlinking inventory parts
to price list items, including role-based access control.
"""

import pytest

from tests.factories import (
    BaseFactory,
    InventoryItemFactory,
    PriceListCategoryFactory,
    PriceListItemFactory,
)


@pytest.fixture()
def _set_session(db_session):
    """Inject db_session into all factories."""
    BaseFactory._meta.sqlalchemy_session = db_session
    PriceListCategoryFactory._meta.sqlalchemy_session = db_session
    PriceListItemFactory._meta.sqlalchemy_session = db_session
    InventoryItemFactory._meta.sqlalchemy_session = db_session


@pytest.fixture()
def price_list_item(app, _set_session, db_session):
    """Create a price list item for testing."""
    item = PriceListItemFactory()
    db_session.flush()
    return item


@pytest.fixture()
def inventory_item(app, _set_session, db_session):
    """Create an inventory item for testing."""
    item = InventoryItemFactory()
    db_session.flush()
    return item


class TestLinkPart:
    """Tests for the link-part endpoint."""

    def test_admin_can_link_part(
        self, admin_client, price_list_item, inventory_item, db_session
    ):
        """Admin user can link an inventory item to a price list item."""
        resp = admin_client.post(
            f"/price-list/item/{price_list_item.id}/link-part",
            data={
                "inventory_item_id": inventory_item.id,
                "quantity": 2,
            },
        )
        assert resp.status_code == 200
        # The linked part should appear in the returned partial
        assert inventory_item.name.encode() in resp.data
        assert b'id="linked-parts-section"' in resp.data

    def test_technician_can_link_part(
        self, logged_in_client, price_list_item, inventory_item, db_session
    ):
        """Technician user can link an inventory item to a price list item."""
        resp = logged_in_client.post(
            f"/price-list/item/{price_list_item.id}/link-part",
            data={
                "inventory_item_id": inventory_item.id,
                "quantity": 1,
            },
        )
        assert resp.status_code == 200
        assert inventory_item.name.encode() in resp.data

    def test_viewer_cannot_link_part(
        self, viewer_client, price_list_item, inventory_item
    ):
        """Viewer role is forbidden from linking parts."""
        resp = viewer_client.post(
            f"/price-list/item/{price_list_item.id}/link-part",
            data={
                "inventory_item_id": inventory_item.id,
                "quantity": 1,
            },
        )
        assert resp.status_code == 403

    def test_link_returns_updated_partial(
        self, admin_client, price_list_item, inventory_item, db_session
    ):
        """Link response contains the parts table with a Remove button."""
        resp = admin_client.post(
            f"/price-list/item/{price_list_item.id}/link-part",
            data={
                "inventory_item_id": inventory_item.id,
                "quantity": 3,
            },
        )
        assert resp.status_code == 200
        assert b'id="linked-parts-section"' in resp.data
        assert b"Remove" in resp.data

    def test_link_invalid_inventory_item(
        self, admin_client, price_list_item
    ):
        """Linking a nonexistent inventory item returns error in partial."""
        resp = admin_client.post(
            f"/price-list/item/{price_list_item.id}/link-part",
            data={
                "inventory_item_id": 99999,
                "quantity": 1,
            },
        )
        assert resp.status_code == 200
        # Still returns the partial (no new parts added)
        assert b'id="linked-parts-section"' in resp.data

    def test_link_missing_inventory_item_id(
        self, admin_client, price_list_item
    ):
        """Linking without an inventory_item_id returns the partial."""
        resp = admin_client.post(
            f"/price-list/item/{price_list_item.id}/link-part",
            data={"quantity": 1},
        )
        assert resp.status_code == 200
        assert b'id="linked-parts-section"' in resp.data


class TestUnlinkPart:
    """Tests for the unlink-part endpoint."""

    def test_admin_can_unlink_part(
        self, admin_client, price_list_item, inventory_item, db_session
    ):
        """Admin user can unlink a previously linked part."""
        from app.services.price_list_service import link_part

        link = link_part(price_list_item.id, inventory_item.id, quantity=1)
        part_id = link.id

        resp = admin_client.post(
            f"/price-list/item/{price_list_item.id}/unlink-part/{part_id}",
        )
        assert resp.status_code == 200
        assert b'id="linked-parts-section"' in resp.data
        # The parts table body should not contain the inventory item link
        # (it may still appear in the add-part dropdown)
        assert b"No parts linked" in resp.data

    def test_viewer_cannot_unlink_part(
        self, viewer_client, price_list_item, inventory_item, db_session
    ):
        """Viewer role is forbidden from unlinking parts."""
        from app.services.price_list_service import link_part

        link = link_part(price_list_item.id, inventory_item.id, quantity=1)
        part_id = link.id

        resp = viewer_client.post(
            f"/price-list/item/{price_list_item.id}/unlink-part/{part_id}",
        )
        assert resp.status_code == 403

    def test_unlink_nonexistent_part(self, admin_client, price_list_item):
        """Unlinking a nonexistent part returns 404."""
        resp = admin_client.post(
            f"/price-list/item/{price_list_item.id}/unlink-part/99999",
        )
        assert resp.status_code == 404

    def test_unlink_part_wrong_item_id(
        self, admin_client, price_list_item, inventory_item, db_session, _set_session
    ):
        """Unlinking a part via wrong item_id returns 404 (IDOR prevention)."""
        from app.services.price_list_service import link_part

        link = link_part(price_list_item.id, inventory_item.id, quantity=1)
        part_id = link.id

        # Create a second price list item to use as the wrong item_id
        other_item = PriceListItemFactory()
        db_session.flush()

        resp = admin_client.post(
            f"/price-list/item/{other_item.id}/unlink-part/{part_id}",
        )
        assert resp.status_code == 404


class TestDuplicatePartLink:
    """Tests for duplicate part link prevention."""

    def test_duplicate_link_shows_warning(
        self, admin_client, price_list_item, inventory_item, db_session
    ):
        """Linking the same part twice shows a warning and creates no duplicate."""
        from app.models.price_list import PriceListItemPart

        # First link succeeds
        resp = admin_client.post(
            f"/price-list/item/{price_list_item.id}/link-part",
            data={
                "inventory_item_id": inventory_item.id,
                "quantity": 2,
            },
        )
        assert resp.status_code == 200
        assert b"Part linked successfully" in resp.data

        # Second link with same part returns warning
        resp = admin_client.post(
            f"/price-list/item/{price_list_item.id}/link-part",
            data={
                "inventory_item_id": inventory_item.id,
                "quantity": 3,
            },
        )
        assert resp.status_code == 200
        assert b"already linked" in resp.data

        # Only one link should exist
        count = PriceListItemPart.query.filter_by(
            price_list_item_id=price_list_item.id,
            inventory_item_id=inventory_item.id,
        ).count()
        assert count == 1

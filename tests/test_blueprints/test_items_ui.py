"""Tests for service items list view add-button visibility by role."""

import pytest

from tests.factories import ServiceItemFactory

pytestmark = pytest.mark.blueprint


ITEMS_LIST_URL = "/items/"


def _set_session(db_session, *factories):
    for f in factories:
        f._meta.sqlalchemy_session = db_session


@pytest.mark.blueprint
class TestAddButtonVisibilityWithItems:
    """When items exist, only admin/technician see the header Add Item button."""

    def test_admin_sees_add_button(self, admin_client, db_session):
        _set_session(db_session, ServiceItemFactory)
        ServiceItemFactory(name="Test Regulator")
        db_session.commit()

        resp = admin_client.get(ITEMS_LIST_URL)
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Add Item" in html

    def test_technician_sees_add_button(self, logged_in_client, db_session):
        _set_session(db_session, ServiceItemFactory)
        ServiceItemFactory(name="Test BCD")
        db_session.commit()

        resp = logged_in_client.get(ITEMS_LIST_URL)
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Add Item" in html

    def test_viewer_does_not_see_add_button(self, viewer_client, db_session):
        _set_session(db_session, ServiceItemFactory)
        ServiceItemFactory(name="Test Tank")
        db_session.commit()

        resp = viewer_client.get(ITEMS_LIST_URL)
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Add Item" not in html


@pytest.mark.blueprint
class TestAddButtonVisibilityEmpty:
    """When no items exist, the empty state add button respects role checks."""

    def test_admin_sees_add_button_empty_state(self, admin_client):
        resp = admin_client.get(ITEMS_LIST_URL)
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Add Item" in html
        assert "No service items found." in html

    def test_technician_sees_add_button_empty_state(self, logged_in_client):
        resp = logged_in_client.get(ITEMS_LIST_URL)
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Add Item" in html
        assert "No service items found." in html

    def test_viewer_no_add_button_empty_state(self, viewer_client):
        resp = viewer_client.get(ITEMS_LIST_URL)
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Add Item" not in html
        assert "No service items found." in html

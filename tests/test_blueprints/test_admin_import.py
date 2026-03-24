"""Tests for admin CSV import routes."""

import io

import pytest

pytestmark = pytest.mark.blueprint


CUSTOMER_CSV = (
    "Type,First Name,Last Name,Business Name,Contact Person,Email,Phone,"
    "Address,City,State,Postal Code,Country,Preferred Contact,Tax Exempt,Notes\n"
    "individual,John,Doe,,,,555-1234,123 Main St,Portland,OR,97201,US,email,No,Test\n"
)

INVENTORY_CSV = (
    "SKU,Name,Category,Subcategory,Manufacturer,Purchase Cost,Resale Price,"
    "Quantity,Reorder Level,Unit,Location,Notes\n"
    "SEAL-001,Latex Neck Seal,Seals,Neck,DUI,5.00,15.00,10,5,each,A,\n"
)


class TestImportPage:
    """Tests for GET /admin/data/import."""

    def test_requires_admin(self, logged_in_client):
        resp = logged_in_client.get("/admin/data/import")
        assert resp.status_code == 403

    def test_renders_for_admin(self, admin_client):
        resp = admin_client.get("/admin/data/import")
        assert resp.status_code == 200
        assert b"Import" in resp.data

    def test_customer_tab(self, admin_client):
        resp = admin_client.get("/admin/data/import?type=customers")
        assert resp.status_code == 200
        assert b"Customers" in resp.data

    def test_inventory_tab(self, admin_client):
        resp = admin_client.get("/admin/data/import?type=inventory")
        assert resp.status_code == 200
        assert b"Inventory" in resp.data


class TestImportPreview:
    """Tests for POST /admin/data/import (preview action)."""

    def test_preview_customers(self, admin_client):
        data = {
            "action": "preview",
            "entity_type": "customers",
            "csv_file": (io.BytesIO(CUSTOMER_CSV.encode()), "customers.csv"),
        }
        resp = admin_client.post(
            "/admin/data/import?type=customers",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        assert b"Preview" in resp.data
        assert b"John" in resp.data

    def test_preview_inventory(self, admin_client):
        data = {
            "action": "preview",
            "entity_type": "inventory",
            "csv_file": (io.BytesIO(INVENTORY_CSV.encode()), "inventory.csv"),
        }
        resp = admin_client.post(
            "/admin/data/import?type=inventory",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        assert b"Latex Neck Seal" in resp.data

    def test_preview_no_file(self, admin_client):
        resp = admin_client.post(
            "/admin/data/import?type=customers",
            data={"action": "preview", "entity_type": "customers"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"select a CSV" in resp.data


class TestImportConfirm:
    """Tests for POST /admin/data/import (confirm action)."""

    def test_confirm_customer_import(self, admin_client, app):
        resp = admin_client.post(
            "/admin/data/import?type=customers",
            data={
                "action": "confirm",
                "entity_type": "customers",
                "csv_content": CUSTOMER_CSV,
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Import complete" in resp.data
        assert b"1 imported" in resp.data

    def test_confirm_inventory_import(self, admin_client, app):
        resp = admin_client.post(
            "/admin/data/import?type=inventory",
            data={
                "action": "confirm",
                "entity_type": "inventory",
                "csv_content": INVENTORY_CSV,
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Import complete" in resp.data

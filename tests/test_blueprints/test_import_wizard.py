"""Tests for admin import wizard (column mapping) routes."""

import io
import base64

import pytest

pytestmark = pytest.mark.blueprint


CUSTOMER_CSV = (
    "Type,First Name,Last Name,Business Name,Email\n"
    "individual,John,Doe,,john@test.com\n"
)

INVENTORY_CSV = (
    "SKU,Name,Category,Purchase Cost\n"
    "TST-001,Test Item,Parts,10.00\n"
)


def _make_xlsx_bytes(headers, rows):
    """Create XLSX bytes from headers and row data."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestImportWizardPage:
    """Tests for GET /admin/import/wizard."""

    def test_requires_admin(self, logged_in_client):
        resp = logged_in_client.get("/admin/import/wizard")
        assert resp.status_code == 403

    def test_renders_for_admin(self, admin_client):
        resp = admin_client.get("/admin/import/wizard")
        assert resp.status_code == 200
        assert b"Import Wizard" in resp.data
        assert b"Upload" in resp.data


class TestImportWizardUpload:
    """Tests for POST /admin/import/upload."""

    def test_upload_csv(self, admin_client):
        data = {
            "entity_type": "customers",
            "import_file": (io.BytesIO(CUSTOMER_CSV.encode()), "customers.csv"),
        }
        resp = admin_client.post(
            "/admin/import/upload",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        assert b"Map Columns" in resp.data
        assert b"First Name" in resp.data

    def test_upload_xlsx(self, admin_client):
        xlsx_bytes = _make_xlsx_bytes(
            ["Name", "Category", "Price"],
            [["Widget", "Parts", "10.00"]],
        )
        data = {
            "entity_type": "inventory",
            "import_file": (io.BytesIO(xlsx_bytes), "inventory.xlsx"),
        }
        resp = admin_client.post(
            "/admin/import/upload",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        assert b"Map Columns" in resp.data
        assert b"Name" in resp.data

    def test_upload_no_file(self, admin_client):
        resp = admin_client.post(
            "/admin/import/upload",
            data={"entity_type": "customers"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"select a file" in resp.data

    def test_upload_invalid_file_type(self, admin_client):
        data = {
            "entity_type": "customers",
            "import_file": (io.BytesIO(b"not a csv"), "file.txt"),
        }
        resp = admin_client.post(
            "/admin/import/upload",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Invalid file type" in resp.data

    def test_upload_requires_admin(self, logged_in_client):
        data = {
            "entity_type": "customers",
            "import_file": (io.BytesIO(CUSTOMER_CSV.encode()), "customers.csv"),
        }
        resp = logged_in_client.post(
            "/admin/import/upload",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 403


class TestImportWizardPreview:
    """Tests for POST /admin/import/preview."""

    def test_preview_returns_mapped_data(self, admin_client):
        csv_bytes = CUSTOMER_CSV.encode("utf-8")
        b64 = base64.b64encode(csv_bytes).decode("ascii")
        data = {
            "entity_type": "customers",
            "file_content": b64,
            "file_type": "csv",
            "source_col_0": "Type",
            "mapping_0": "type",
            "source_col_1": "First Name",
            "mapping_1": "first_name",
            "source_col_2": "Last Name",
            "mapping_2": "last_name",
            "source_col_3": "Business Name",
            "mapping_3": "",
            "source_col_4": "Email",
            "mapping_4": "email",
        }
        resp = admin_client.post("/admin/import/preview", data=data)
        assert resp.status_code == 200
        assert b"Preview" in resp.data
        assert b"John" in resp.data

    def test_preview_missing_file_content(self, admin_client):
        resp = admin_client.post(
            "/admin/import/preview",
            data={"entity_type": "customers", "file_content": "", "file_type": "csv"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"missing" in resp.data.lower() or b"Upload" in resp.data


class TestImportWizardExecute:
    """Tests for POST /admin/import/execute."""

    def test_execute_creates_records(self, admin_client, app):
        csv_bytes = INVENTORY_CSV.encode("utf-8")
        b64 = base64.b64encode(csv_bytes).decode("ascii")
        data = {
            "entity_type": "inventory",
            "file_content": b64,
            "file_type": "csv",
            "map_source[]": ["SKU", "Name", "Category", "Purchase Cost"],
            "map_target[]": ["sku", "name", "category", "purchase_cost"],
        }
        resp = admin_client.post("/admin/import/execute", data=data)
        assert resp.status_code == 200
        assert b"1" in resp.data  # 1 imported
        assert b"Imported" in resp.data or b"imported" in resp.data

    def test_execute_requires_admin(self, logged_in_client):
        resp = logged_in_client.post("/admin/import/execute", data={})
        assert resp.status_code == 403

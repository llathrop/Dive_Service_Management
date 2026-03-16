"""Tests for import_service column mapping and XLSX support."""

import io
import pytest
from decimal import Decimal

from app.models.customer import Customer
from app.models.inventory import InventoryItem
from app.services import import_service


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

CUSTOMER_CSV = (
    "Type,First Name,Last Name,Business Name,Contact Person,Email,Phone,"
    "Address,City,State,Postal Code,Country,Preferred Contact,Tax Exempt,Notes\n"
    "individual,John,Doe,,,,555-1234,123 Main St,Portland,OR,97201,US,email,No,Test\n"
    "business,,,Acme Diving,Jane Smith,biz@example.com,,456 Oak Ave,Seattle,WA,98101,US,phone,Yes,Business\n"
)

INVENTORY_CSV = (
    "SKU,Name,Category,Subcategory,Manufacturer,Purchase Cost,Resale Price,"
    "Quantity,Reorder Level,Unit,Location,Notes\n"
    "SEAL-001,Latex Neck Seal,Seals,Neck Seals,DUI,5.00,15.00,10,5,each,Shelf A,Test\n"
    ",Aquaseal,Adhesive,,McNett,8.50,12.00,20,10,each,Shelf B,\n"
)

# CSV with non-standard column names for mapping tests
CUSTOM_CSV = (
    "cust_type,fname,lname,company,contact,email_addr,telephone\n"
    "individual,Alice,Jones,,,,555-9999\n"
)

INVENTORY_CUSTOM_CSV = (
    "item_sku,item_name,item_category,cost,price,qty\n"
    "TST-001,Test Item,Parts,10.00,25.00,50\n"
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


# ---------------------------------------------------------------------------
# Column detection
# ---------------------------------------------------------------------------

class TestDetectColumns:
    """Tests for detect_columns()."""

    def test_detect_csv_columns(self):
        columns = import_service.detect_columns(CUSTOMER_CSV, "csv")
        assert "Type" in columns
        assert "First Name" in columns
        assert "Email" in columns
        assert len(columns) == 15

    def test_detect_csv_columns_from_bytes(self):
        columns = import_service.detect_columns(CUSTOMER_CSV.encode("utf-8"), "csv")
        assert "Type" in columns

    def test_detect_csv_with_bom(self):
        csv_bom = "\ufeff" + CUSTOMER_CSV
        columns = import_service.detect_columns(csv_bom, "csv")
        assert len(columns) == 15

    def test_detect_empty_csv(self):
        columns = import_service.detect_columns("", "csv")
        assert columns == []

    def test_detect_xlsx_columns(self):
        xlsx_bytes = _make_xlsx_bytes(
            ["Name", "Category", "Price"],
            [["Widget", "Parts", "10.00"]],
        )
        columns = import_service.detect_columns(xlsx_bytes, "xlsx")
        assert columns == ["Name", "Category", "Price"]

    def test_detect_xlsx_empty(self):
        xlsx_bytes = _make_xlsx_bytes([], [])
        columns = import_service.detect_columns(xlsx_bytes, "xlsx")
        assert columns == []


# ---------------------------------------------------------------------------
# Target fields
# ---------------------------------------------------------------------------

class TestGetTargetFields:
    """Tests for get_target_fields()."""

    def test_customer_fields(self):
        fields = import_service.get_target_fields("customers")
        keys = [f["key"] for f in fields]
        assert "first_name" in keys
        assert "last_name" in keys
        assert "email" in keys
        assert len(fields) == 15

    def test_inventory_fields(self):
        fields = import_service.get_target_fields("inventory")
        keys = [f["key"] for f in fields]
        assert "name" in keys
        assert "category" in keys
        assert "sku" in keys
        # Check required flags
        name_field = next(f for f in fields if f["key"] == "name")
        assert name_field["required"] is True
        category_field = next(f for f in fields if f["key"] == "category")
        assert category_field["required"] is True

    def test_unknown_entity_type(self):
        fields = import_service.get_target_fields("unknown")
        assert fields == []


# ---------------------------------------------------------------------------
# Auto-detect mapping
# ---------------------------------------------------------------------------

class TestAutoDetectMapping:
    """Tests for auto_detect_mapping()."""

    def test_exact_match_customer_columns(self):
        """Standard export columns should map perfectly."""
        source = ["Type", "First Name", "Last Name", "Email", "Phone"]
        mapping = import_service.auto_detect_mapping(source, "customers")
        assert mapping["Type"] == "type"
        assert mapping["First Name"] == "first_name"
        assert mapping["Last Name"] == "last_name"
        assert mapping["Email"] == "email"
        assert mapping["Phone"] == "phone"

    def test_fuzzy_match(self):
        """Columns with slightly different names should still match."""
        source = ["First Name", "Last Name", "E-mail", "Postal Code"]
        mapping = import_service.auto_detect_mapping(source, "customers")
        assert mapping["First Name"] == "first_name"
        assert mapping["Last Name"] == "last_name"
        assert mapping["Postal Code"] == "postal_code"

    def test_no_match_for_garbage(self):
        """Completely unrelated column names should map to None."""
        source = ["zzz_garbage_col", "another_random"]
        mapping = import_service.auto_detect_mapping(source, "customers")
        assert mapping["zzz_garbage_col"] is None
        assert mapping["another_random"] is None

    def test_inventory_auto_detect(self):
        source = ["SKU", "Name", "Category", "Purchase Cost", "Quantity"]
        mapping = import_service.auto_detect_mapping(source, "inventory")
        assert mapping["SKU"] == "sku"
        assert mapping["Name"] == "name"
        assert mapping["Category"] == "category"
        assert mapping["Purchase Cost"] == "purchase_cost"
        assert mapping["Quantity"] == "quantity"


# ---------------------------------------------------------------------------
# Map and validate
# ---------------------------------------------------------------------------

class TestMapAndValidate:
    """Tests for map_and_validate()."""

    def test_valid_customer_mapping(self):
        mapping = {
            "Type": "type", "First Name": "first_name",
            "Last Name": "last_name", "Email": "email",
            "Phone": "phone",
        }
        csv = "Type,First Name,Last Name,Email,Phone\nindividual,John,Doe,john@test.com,555\n"
        result = import_service.map_and_validate(csv, mapping, "customers")
        assert result["total"] == 1
        assert result["valid"] == 1
        assert len(result["errors"]) == 0
        assert result["rows"][0]["first_name"] == "John"

    def test_missing_required_inventory_fields(self):
        """Missing name/category should produce errors."""
        mapping = {"SKU": "sku", "Price": "resale_price"}
        csv = "SKU,Price\nTEST,10.00\n"
        result = import_service.map_and_validate(csv, mapping, "inventory")
        assert len(result["errors"]) >= 1
        error_msgs = " ".join(e["message"] for e in result["errors"])
        assert "Name is required" in error_msgs

    def test_skip_columns(self):
        """Columns mapped to None should be skipped."""
        mapping = {"First Name": "first_name", "Last Name": "last_name", "Junk": None}
        csv = "First Name,Last Name,Junk\nAlice,Smith,garbage\n"
        result = import_service.map_and_validate(csv, mapping, "customers")
        assert "Junk" not in result["rows"][0]
        assert result["rows"][0]["first_name"] == "Alice"

    def test_xlsx_map_and_validate(self):
        xlsx_bytes = _make_xlsx_bytes(
            ["Item Name", "Item Category", "Cost"],
            [["Widget", "Parts", "10.00"]],
        )
        mapping = {"Item Name": "name", "Item Category": "category", "Cost": "purchase_cost"}
        result = import_service.map_and_validate(xlsx_bytes, mapping, "inventory", "xlsx")
        assert result["total"] == 1
        assert result["valid"] == 1
        assert result["rows"][0]["name"] == "Widget"

    def test_invalid_decimal_in_validation(self):
        mapping = {"Name": "name", "Category": "category", "Purchase Cost": "purchase_cost"}
        csv = "Name,Category,Purchase Cost\nItem,Parts,not-a-number\n"
        result = import_service.map_and_validate(csv, mapping, "inventory")
        assert len(result["errors"]) == 1
        assert "purchase cost" in result["errors"][0]["message"].lower()


# ---------------------------------------------------------------------------
# Execute mapped import
# ---------------------------------------------------------------------------

class TestExecuteMappedImport:
    """Tests for execute_mapped_import()."""

    def test_import_customers(self, app, db_session):
        mapping = {
            "Type": "type", "First Name": "first_name",
            "Last Name": "last_name", "Email": "email",
        }
        csv = "Type,First Name,Last Name,Email\nindividual,Jane,Doe,jane@test.com\n"
        with app.app_context():
            outcome = import_service.execute_mapped_import(csv, mapping, "customers")
            assert outcome["imported"] == 1
            assert outcome["skipped"] == 0
            assert Customer.query.count() == 1
            c = Customer.query.first()
            assert c.first_name == "Jane"
            assert c.email == "jane@test.com"

    def test_import_inventory(self, app, db_session):
        mapping = {
            "SKU": "sku", "Name": "name", "Category": "category",
            "Cost": "purchase_cost", "Qty": "quantity",
        }
        csv = "SKU,Name,Category,Cost,Qty\nTST-001,Test Part,Parts,10.00,50\n"
        with app.app_context():
            outcome = import_service.execute_mapped_import(csv, mapping, "inventory")
            assert outcome["imported"] == 1
            item = InventoryItem.query.first()
            assert item.name == "Test Part"
            assert item.purchase_cost == Decimal("10.00")
            assert item.quantity_in_stock == Decimal("50")

    def test_import_skips_duplicate_email(self, app, db_session):
        mapping = {"First Name": "first_name", "Last Name": "last_name", "Email": "email"}
        csv = "First Name,Last Name,Email\nJohn,Doe,dupe@test.com\n"
        with app.app_context():
            import_service.execute_mapped_import(csv, mapping, "customers")
            outcome = import_service.execute_mapped_import(csv, mapping, "customers")
            assert outcome["skipped"] == 1
            assert outcome["imported"] == 0

    def test_import_handles_errors_gracefully(self, app, db_session):
        """Import with missing required fields should report errors, not crash."""
        mapping = {"SKU": "sku"}  # Missing name and category
        csv = "SKU\nTST-X\n"
        with app.app_context():
            outcome = import_service.execute_mapped_import(csv, mapping, "inventory")
            assert outcome["imported"] == 0
            assert len(outcome["errors"]) >= 1

    def test_import_xlsx(self, app, db_session):
        xlsx_bytes = _make_xlsx_bytes(
            ["Name", "Category", "Purchase Cost"],
            [["XLSX Item", "Parts", "15.00"]],
        )
        mapping = {"Name": "name", "Category": "category", "Purchase Cost": "purchase_cost"}
        with app.app_context():
            outcome = import_service.execute_mapped_import(
                xlsx_bytes, mapping, "inventory", "xlsx"
            )
            assert outcome["imported"] == 1
            item = InventoryItem.query.first()
            assert item.name == "XLSX Item"

    def test_import_unknown_entity_type(self, app, db_session):
        with app.app_context():
            outcome = import_service.execute_mapped_import("", {}, "widgets")
            assert outcome["imported"] == 0
            assert len(outcome["errors"]) > 0

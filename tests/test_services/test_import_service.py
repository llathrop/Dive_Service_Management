"""Tests for the import_service module."""

import pytest
from decimal import Decimal

from app.models.customer import Customer
from app.models.inventory import InventoryItem
from app.services import import_service


CUSTOMER_CSV = (
    "Type,First Name,Last Name,Business Name,Contact Person,Email,Phone,"
    "Address,City,State,Postal Code,Country,Preferred Contact,Tax Exempt,Notes\n"
    "individual,John,Doe,,,,555-1234,123 Main St,Portland,OR,97201,US,email,No,Test customer\n"
    "business,,,Acme Diving,Jane Smith,biz@example.com,,456 Oak Ave,Seattle,WA,98101,US,phone,Yes,Business note\n"
)

INVENTORY_CSV = (
    "SKU,Name,Category,Subcategory,Manufacturer,Purchase Cost,Resale Price,"
    "Quantity,Reorder Level,Unit,Location,Notes\n"
    "SEAL-001,Latex Neck Seal,Seals,Neck Seals,DUI,5.00,15.00,10,5,each,Shelf A,Test item\n"
    ",Aquaseal,Adhesive,,McNett,8.50,12.00,20,10,each,Shelf B,\n"
)


class TestParseCsv:
    """Tests for parse_csv()."""

    def test_parse_customer_csv(self):
        result = import_service.parse_csv(CUSTOMER_CSV, "customers")
        assert len(result["rows"]) == 2
        assert len(result["errors"]) == 0
        assert len(result["headers"]) == 15

    def test_parse_inventory_csv(self):
        result = import_service.parse_csv(INVENTORY_CSV, "inventory")
        assert len(result["rows"]) == 2
        assert len(result["errors"]) == 0

    def test_parse_with_bom(self):
        csv_with_bom = "\ufeff" + CUSTOMER_CSV
        result = import_service.parse_csv(csv_with_bom, "customers")
        assert len(result["rows"]) == 2

    def test_parse_empty_csv(self):
        result = import_service.parse_csv("", "customers")
        assert len(result["errors"]) > 0

    def test_preview_limit(self):
        # Build CSV with 20 rows
        lines = ["Name,Category\n"]
        for i in range(20):
            lines.append(f"Item {i},Cat\n")
        result = import_service.parse_csv("".join(lines), "inventory")
        assert len(result["preview"]) == 10

    def test_customer_validation_missing_name(self):
        csv = "Type,First Name,Last Name\nindividual,,\n"
        result = import_service.parse_csv(csv, "customers")
        assert len(result["errors"]) == 1
        assert "first or last name" in result["errors"][0]["message"].lower()

    def test_business_validation_missing_business_name(self):
        csv = "Type,First Name,Last Name,Business Name\nbusiness,,,\n"
        result = import_service.parse_csv(csv, "customers")
        assert len(result["errors"]) == 1
        assert "business name" in result["errors"][0]["message"].lower()

    def test_inventory_validation_missing_name(self):
        csv = "Name,Category\n,Seals\n"
        result = import_service.parse_csv(csv, "inventory")
        assert any("Name" in e["message"] for e in result["errors"])

    def test_inventory_validation_missing_category(self):
        csv = "Name,Category\nSeal,\n"
        result = import_service.parse_csv(csv, "inventory")
        assert any("Category" in e["message"] for e in result["errors"])

    def test_inventory_validation_invalid_cost(self):
        csv = "Name,Category,Purchase Cost\nSeal,Seals,not-a-number\n"
        result = import_service.parse_csv(csv, "inventory")
        assert any("cost" in e["message"].lower() for e in result["errors"])


class TestImportCustomers:
    """Tests for import_customers()."""

    def test_import_basic_customers(self, app, db_session):
        with app.app_context():
            result = import_service.parse_csv(CUSTOMER_CSV, "customers")
            outcome = import_service.import_customers(result["rows"])
            assert outcome["imported"] == 2
            assert outcome["skipped"] == 0
            assert Customer.query.count() == 2

    def test_import_skips_duplicate_email(self, app, db_session):
        with app.app_context():
            result = import_service.parse_csv(CUSTOMER_CSV, "customers")
            import_service.import_customers(result["rows"])
            # Import again
            result2 = import_service.parse_csv(CUSTOMER_CSV, "customers")
            outcome2 = import_service.import_customers(result2["rows"])
            # The one with email should be skipped; the one without imported again
            assert outcome2["skipped"] >= 1


class TestImportInventory:
    """Tests for import_inventory()."""

    def test_import_basic_inventory(self, app, db_session):
        with app.app_context():
            result = import_service.parse_csv(INVENTORY_CSV, "inventory")
            outcome = import_service.import_inventory(result["rows"])
            assert outcome["imported"] == 2
            assert outcome["skipped"] == 0
            items = InventoryItem.query.all()
            assert len(items) == 2
            seal = InventoryItem.query.filter_by(sku="SEAL-001").first()
            assert seal.purchase_cost == Decimal("5.00")

    def test_import_skips_duplicate_sku(self, app, db_session):
        with app.app_context():
            result = import_service.parse_csv(INVENTORY_CSV, "inventory")
            import_service.import_inventory(result["rows"])
            result2 = import_service.parse_csv(INVENTORY_CSV, "inventory")
            outcome2 = import_service.import_inventory(result2["rows"])
            assert outcome2["skipped"] >= 1

"""Import service — CSV import for customers and inventory.

Supports the fixed column format matching the export service output.
Import workflow: parse CSV → validate rows → preview → commit.
"""

import csv
import io
from decimal import Decimal, InvalidOperation

from app.extensions import db
from app.models.customer import Customer
from app.models.inventory import InventoryItem


# Expected column headers (case-insensitive, order matters for mapping)
CUSTOMER_COLUMNS = [
    "type", "first_name", "last_name", "business_name",
    "contact_person", "email", "phone", "address", "city",
    "state", "postal_code", "country", "preferred_contact",
    "tax_exempt", "notes",
]

INVENTORY_COLUMNS = [
    "sku", "name", "category", "subcategory",
    "manufacturer", "purchase_cost", "resale_price",
    "quantity", "reorder_level", "unit", "location",
    "notes",
]


def parse_csv(file_content, entity_type):
    """Parse a CSV string and return structured rows with validation.

    Args:
        file_content: CSV string content (may include BOM).
        entity_type: "customers" or "inventory".

    Returns:
        dict with keys:
          - "headers": list of detected column headers
          - "rows": list of dicts (one per data row)
          - "errors": list of {"row": N, "message": str}
          - "preview": first 10 rows as dicts
    """
    # Strip BOM if present
    if file_content.startswith("\ufeff"):
        file_content = file_content[1:]

    reader = csv.DictReader(io.StringIO(file_content))
    if not reader.fieldnames:
        return {"headers": [], "rows": [], "errors": [{"row": 0, "message": "Empty or invalid CSV file"}], "preview": []}

    headers = list(reader.fieldnames)
    rows = []
    errors = []

    for i, row in enumerate(reader, start=2):  # Row 2 = first data row
        rows.append(row)

    # Validate
    if entity_type == "customers":
        errors = _validate_customer_rows(rows)
    elif entity_type == "inventory":
        errors = _validate_inventory_rows(rows)

    return {
        "headers": headers,
        "rows": rows,
        "errors": errors,
        "preview": rows[:10],
    }


def import_customers(rows):
    """Import validated customer rows into the database.

    Args:
        rows: list of dicts from parse_csv.

    Returns:
        dict: {"imported": N, "skipped": N, "errors": [...]}
    """
    imported = 0
    skipped = 0
    errors = []

    for i, row in enumerate(rows, start=2):
        try:
            # Skip rows with existing email (if email provided)
            email = _get(row, "Email", "email")
            if email:
                existing = Customer.query.filter_by(email=email).first()
                if existing:
                    skipped += 1
                    continue

            customer = Customer(
                customer_type=_get(row, "Type", "type") or "individual",
                first_name=_get(row, "First Name", "first_name") or "",
                last_name=_get(row, "Last Name", "last_name") or "",
                business_name=_get(row, "Business Name", "business_name"),
                contact_person=_get(row, "Contact Person", "contact_person"),
                email=email,
                phone_primary=_get(row, "Phone", "phone"),
                address_line1=_get(row, "Address", "address"),
                city=_get(row, "City", "city"),
                state_province=_get(row, "State", "state"),
                postal_code=_get(row, "Postal Code", "postal_code"),
                country=_get(row, "Country", "country") or "US",
                preferred_contact=_get(row, "Preferred Contact", "preferred_contact") or "email",
                tax_exempt=_parse_bool(_get(row, "Tax Exempt", "tax_exempt")),
                notes=_get(row, "Notes", "notes"),
            )
            db.session.add(customer)
            imported += 1
        except Exception as e:
            errors.append({"row": i, "message": str(e)})

    if imported > 0:
        db.session.commit()

    return {"imported": imported, "skipped": skipped, "errors": errors}


def import_inventory(rows):
    """Import validated inventory rows into the database.

    Args:
        rows: list of dicts from parse_csv.

    Returns:
        dict: {"imported": N, "skipped": N, "errors": [...]}
    """
    imported = 0
    skipped = 0
    errors = []

    for i, row in enumerate(rows, start=2):
        try:
            sku = _get(row, "SKU", "sku")
            if sku:
                existing = InventoryItem.query.filter_by(sku=sku).first()
                if existing:
                    skipped += 1
                    continue

            name = _get(row, "Name", "name")
            if not name:
                errors.append({"row": i, "message": "Name is required"})
                continue

            category = _get(row, "Category", "category")
            if not category:
                errors.append({"row": i, "message": "Category is required"})
                continue

            item = InventoryItem(
                sku=sku or None,  # None for empty to avoid unique constraint on ''
                name=name,
                category=category,
                subcategory=_get(row, "Subcategory", "subcategory"),
                manufacturer=_get(row, "Manufacturer", "manufacturer"),
                purchase_cost=_parse_decimal(_get(row, "Purchase Cost", "purchase_cost")),
                resale_price=_parse_decimal(_get(row, "Resale Price", "resale_price")),
                quantity_in_stock=_parse_decimal(_get(row, "Quantity", "quantity")) or Decimal("0"),
                reorder_level=_parse_decimal(_get(row, "Reorder Level", "reorder_level")) or Decimal("0"),
                unit_of_measure=_get(row, "Unit", "unit") or "each",
                storage_location=_get(row, "Location", "location"),
                notes=_get(row, "Notes", "notes"),
            )
            db.session.add(item)
            imported += 1
        except Exception as e:
            errors.append({"row": i, "message": str(e)})

    if imported > 0:
        db.session.commit()

    return {"imported": imported, "skipped": skipped, "errors": errors}


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_customer_rows(rows):
    """Validate customer rows and return a list of errors."""
    errors = []
    for i, row in enumerate(rows, start=2):
        ctype = _get(row, "Type", "type") or "individual"
        if ctype == "individual":
            if not _get(row, "First Name", "first_name") and not _get(row, "Last Name", "last_name"):
                errors.append({"row": i, "message": "Individual customers require first or last name"})
        elif ctype == "business":
            if not _get(row, "Business Name", "business_name"):
                errors.append({"row": i, "message": "Business customers require a business name"})
    return errors


def _validate_inventory_rows(rows):
    """Validate inventory rows and return a list of errors."""
    errors = []
    for i, row in enumerate(rows, start=2):
        if not _get(row, "Name", "name"):
            errors.append({"row": i, "message": "Name is required"})
        if not _get(row, "Category", "category"):
            errors.append({"row": i, "message": "Category is required"})
        cost = _get(row, "Purchase Cost", "purchase_cost")
        if cost:
            try:
                Decimal(cost)
            except InvalidOperation:
                errors.append({"row": i, "message": f"Invalid purchase cost: {cost}"})
    return errors


# ---------------------------------------------------------------------------
# Value parsing helpers
# ---------------------------------------------------------------------------

def _get(row, *keys):
    """Get a value from a row dict, trying multiple key names."""
    for key in keys:
        val = row.get(key, "").strip() if row.get(key) else ""
        if val:
            return val
    return ""


def _parse_bool(val):
    """Parse a boolean value from string."""
    if not val:
        return False
    return val.lower() in ("true", "yes", "1", "y")


def _parse_decimal(val):
    """Parse a decimal value from string, returning None for empty/invalid."""
    if not val:
        return None
    try:
        return Decimal(val)
    except InvalidOperation:
        return None

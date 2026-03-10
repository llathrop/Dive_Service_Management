"""Unit tests for inventory forms.

Tests cover ``InventoryItemForm``, ``InventorySearchForm``, and
``StockAdjustmentForm`` — including required fields, defaults, and
the CSRF-disabled search form.
"""

import pytest
from werkzeug.datastructures import MultiDict

from app.forms.inventory import (
    InventoryItemForm,
    InventorySearchForm,
    StockAdjustmentForm,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# InventoryItemForm — valid data
# ---------------------------------------------------------------------------


class TestInventoryItemFormValid:
    """Scenarios where the form should pass validation."""

    def test_valid_minimal(self, app):
        with app.test_request_context():
            form = InventoryItemForm(
                formdata=MultiDict([
                    ("name", "O-Ring Kit"),
                    ("category", "Parts"),
                    ("unit_of_measure", "each"),
                ])
            )
            assert form.validate(), form.errors

    def test_valid_all_fields(self, app):
        with app.test_request_context():
            form = InventoryItemForm(
                formdata=MultiDict([
                    ("sku", "ORK-001"),
                    ("name", "O-Ring Kit - Regulator"),
                    ("description", "Assorted Viton o-rings for regulator service"),
                    ("category", "Parts"),
                    ("subcategory", "O-Rings"),
                    ("manufacturer", "Trident"),
                    ("manufacturer_part_number", "TRD-ORK-100"),
                    ("purchase_cost", "12.50"),
                    ("resale_price", "25.00"),
                    ("markup_percent", "100.00"),
                    ("quantity_in_stock", "50"),
                    ("reorder_level", "10"),
                    ("reorder_quantity", "25"),
                    ("unit_of_measure", "set"),
                    ("storage_location", "Shelf A3"),
                    ("is_active", "y"),
                    ("is_for_resale", "y"),
                    ("preferred_supplier", "DGX"),
                    ("supplier_url", "https://www.dgx.com/oring-kit"),
                    ("minimum_order_quantity", "5"),
                    ("supplier_lead_time_days", "7"),
                    ("expiration_date", "2027-12-31"),
                    ("notes", "Restock quarterly"),
                ])
            )
            assert form.validate(), form.errors

    def test_valid_decimal_quantities(self, app):
        """Decimal values accepted for quantity_in_stock and reorder_level."""
        with app.test_request_context():
            form = InventoryItemForm(
                formdata=MultiDict([
                    ("name", "Neoprene Tape"),
                    ("category", "Adhesives"),
                    ("unit_of_measure", "ft"),
                    ("quantity_in_stock", "12.50"),
                    ("reorder_level", "3.25"),
                ])
            )
            assert form.validate(), form.errors
            from decimal import Decimal
            assert form.quantity_in_stock.data == Decimal("12.50")
            assert form.reorder_level.data == Decimal("3.25")

    def test_negative_quantity_rejected(self, app):
        """Negative quantity_in_stock should fail validation."""
        with app.test_request_context():
            form = InventoryItemForm(
                formdata=MultiDict([
                    ("name", "Bad Item"),
                    ("category", "Parts"),
                    ("unit_of_measure", "each"),
                    ("quantity_in_stock", "-5"),
                ])
            )
            assert not form.validate()
            assert "quantity_in_stock" in form.errors


# ---------------------------------------------------------------------------
# InventoryItemForm — invalid data
# ---------------------------------------------------------------------------


class TestInventoryItemFormInvalid:
    """Scenarios where the form should fail validation."""

    def test_missing_name(self, app):
        with app.test_request_context():
            form = InventoryItemForm(
                formdata=MultiDict([
                    ("name", ""),
                    ("category", "Parts"),
                    ("unit_of_measure", "each"),
                ])
            )
            assert not form.validate()
            assert "name" in form.errors

    def test_missing_category(self, app):
        with app.test_request_context():
            form = InventoryItemForm(
                formdata=MultiDict([
                    ("name", "O-Ring Kit"),
                    ("category", ""),
                    ("unit_of_measure", "each"),
                ])
            )
            assert not form.validate()
            assert "category" in form.errors

    def test_missing_both_required(self, app):
        with app.test_request_context():
            form = InventoryItemForm(
                formdata=MultiDict([
                    ("name", ""),
                    ("category", ""),
                    ("unit_of_measure", "each"),
                ])
            )
            assert not form.validate()
            assert "name" in form.errors
            assert "category" in form.errors


# ---------------------------------------------------------------------------
# InventoryItemForm — defaults
# ---------------------------------------------------------------------------


class TestInventoryItemFormDefaults:
    """Verify that field defaults are applied correctly."""

    def test_defaults_applied(self, app):
        with app.test_request_context():
            form = InventoryItemForm()
            assert form.quantity_in_stock.data == 0
            assert form.reorder_level.data == 0
            assert form.is_active.data is True
            assert form.is_for_resale.data is False


# ---------------------------------------------------------------------------
# InventorySearchForm
# ---------------------------------------------------------------------------


class TestInventorySearchForm:
    """Tests for the GET-based inventory search form."""

    def test_valid_search(self, app):
        with app.test_request_context():
            form = InventorySearchForm(
                formdata=MultiDict([("q", "o-ring")])
            )
            assert form.validate(), form.errors

    def test_empty_search_is_valid(self, app):
        with app.test_request_context():
            form = InventorySearchForm(formdata=MultiDict())
            assert form.validate(), form.errors

    def test_csrf_disabled(self, app):
        with app.test_request_context():
            form = InventorySearchForm()
            assert form.meta.csrf is False

    def test_filter_by_status(self, app):
        with app.test_request_context():
            form = InventorySearchForm(
                formdata=MultiDict([("is_active", "1")])
            )
            assert form.validate(), form.errors
            assert form.is_active.data == "1"


# ---------------------------------------------------------------------------
# StockAdjustmentForm
# ---------------------------------------------------------------------------


class TestStockAdjustmentForm:
    """Tests for the stock adjustment form."""

    def test_valid_positive_adjustment(self, app):
        with app.test_request_context():
            form = StockAdjustmentForm(
                formdata=MultiDict([
                    ("adjustment", "10"),
                    ("reason", "Received shipment"),
                ])
            )
            assert form.validate(), form.errors

    def test_valid_negative_adjustment(self, app):
        with app.test_request_context():
            form = StockAdjustmentForm(
                formdata=MultiDict([
                    ("adjustment", "-5"),
                    ("reason", "Used in repair"),
                ])
            )
            assert form.validate(), form.errors

    def test_valid_decimal_adjustment(self, app):
        """Decimal adjustments are accepted (e.g., 2.5 ft of tape)."""
        with app.test_request_context():
            form = StockAdjustmentForm(
                formdata=MultiDict([
                    ("adjustment", "2.5"),
                    ("reason", "Partial roll received"),
                ])
            )
            assert form.validate(), form.errors

    def test_valid_negative_decimal_adjustment(self, app):
        """Negative decimal adjustments are accepted."""
        with app.test_request_context():
            form = StockAdjustmentForm(
                formdata=MultiDict([
                    ("adjustment", "-0.75"),
                    ("reason", "Used partial unit"),
                ])
            )
            assert form.validate(), form.errors

    def test_missing_adjustment(self, app):
        with app.test_request_context():
            form = StockAdjustmentForm(
                formdata=MultiDict([
                    ("adjustment", ""),
                    ("reason", "Oops"),
                ])
            )
            assert not form.validate()
            assert "adjustment" in form.errors

    def test_missing_reason(self, app):
        with app.test_request_context():
            form = StockAdjustmentForm(
                formdata=MultiDict([
                    ("adjustment", "5"),
                    ("reason", ""),
                ])
            )
            assert not form.validate()
            assert "reason" in form.errors

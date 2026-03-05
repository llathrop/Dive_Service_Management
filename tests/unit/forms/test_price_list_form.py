"""Unit tests for price-list forms.

Tests cover ``PriceListCategoryForm`` and ``PriceListItemForm``
including required fields, defaults, and numeric-range validation.
"""

import pytest
from werkzeug.datastructures import MultiDict

from app.forms.price_list import PriceListCategoryForm, PriceListItemForm

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# PriceListCategoryForm — valid data
# ---------------------------------------------------------------------------


class TestPriceListCategoryFormValid:
    """Scenarios where the category form should pass validation."""

    def test_valid_minimal(self, app):
        with app.test_request_context():
            form = PriceListCategoryForm(
                formdata=MultiDict([("name", "Drysuit Repairs")])
            )
            assert form.validate(), form.errors

    def test_valid_all_fields(self, app):
        with app.test_request_context():
            form = PriceListCategoryForm(
                formdata=MultiDict([
                    ("name", "Regulator Service"),
                    ("description", "Standard and advanced regulator services"),
                    ("sort_order", "10"),
                    ("is_active", "y"),
                ])
            )
            assert form.validate(), form.errors


# ---------------------------------------------------------------------------
# PriceListCategoryForm — invalid data
# ---------------------------------------------------------------------------


class TestPriceListCategoryFormInvalid:
    """Scenarios where the category form should fail validation."""

    def test_missing_name(self, app):
        with app.test_request_context():
            form = PriceListCategoryForm(
                formdata=MultiDict([("name", "")])
            )
            assert not form.validate()
            assert "name" in form.errors


# ---------------------------------------------------------------------------
# PriceListCategoryForm — defaults
# ---------------------------------------------------------------------------


class TestPriceListCategoryFormDefaults:
    """Verify that field defaults are applied correctly."""

    def test_defaults_applied(self, app):
        with app.test_request_context():
            form = PriceListCategoryForm()
            assert form.sort_order.data == 0
            assert form.is_active.data is True


# ---------------------------------------------------------------------------
# PriceListItemForm — valid data
# ---------------------------------------------------------------------------


class TestPriceListItemFormValid:
    """Scenarios where the item form should pass validation."""

    def test_valid_minimal(self, app):
        with app.test_request_context():
            form = PriceListItemForm(
                formdata=MultiDict([
                    ("category_id", "1"),
                    ("name", "Neck Seal Replacement"),
                    ("price", "45.00"),
                ])
            )
            # Populate choices dynamically as a route would
            form.category_id.choices = [(1, "Drysuit Repairs")]
            assert form.validate(), form.errors

    def test_valid_all_fields(self, app):
        with app.test_request_context():
            form = PriceListItemForm(
                formdata=MultiDict([
                    ("category_id", "2"),
                    ("code", "REG-SVC-01"),
                    ("name", "First Stage Annual Service"),
                    ("description", "Complete first stage service and rebuild"),
                    ("price", "85.00"),
                    ("cost", "25.00"),
                    ("price_tier", "standard"),
                    ("is_per_unit", "y"),
                    ("default_quantity", "1.00"),
                    ("unit_label", "each"),
                    ("auto_deduct_parts", "y"),
                    ("is_taxable", "y"),
                    ("sort_order", "5"),
                    ("is_active", "y"),
                    ("internal_notes", "Includes o-ring kit"),
                ])
            )
            form.category_id.choices = [
                (1, "Drysuit Repairs"),
                (2, "Regulator Service"),
            ]
            assert form.validate(), form.errors


# ---------------------------------------------------------------------------
# PriceListItemForm — invalid data
# ---------------------------------------------------------------------------


class TestPriceListItemFormInvalid:
    """Scenarios where the item form should fail validation."""

    def test_missing_name(self, app):
        with app.test_request_context():
            form = PriceListItemForm(
                formdata=MultiDict([
                    ("category_id", "1"),
                    ("name", ""),
                    ("price", "45.00"),
                ])
            )
            form.category_id.choices = [(1, "Drysuit Repairs")]
            assert not form.validate()
            assert "name" in form.errors

    def test_missing_price(self, app):
        with app.test_request_context():
            form = PriceListItemForm(
                formdata=MultiDict([
                    ("category_id", "1"),
                    ("name", "Seal Replace"),
                    ("price", ""),
                ])
            )
            form.category_id.choices = [(1, "Drysuit Repairs")]
            assert not form.validate()
            assert "price" in form.errors

    def test_negative_price(self, app):
        with app.test_request_context():
            form = PriceListItemForm(
                formdata=MultiDict([
                    ("category_id", "1"),
                    ("name", "Seal Replace"),
                    ("price", "-10.00"),
                ])
            )
            form.category_id.choices = [(1, "Drysuit Repairs")]
            assert not form.validate()
            assert "price" in form.errors

    def test_missing_category(self, app):
        with app.test_request_context():
            form = PriceListItemForm(
                formdata=MultiDict([
                    ("category_id", ""),
                    ("name", "Seal Replace"),
                    ("price", "45.00"),
                ])
            )
            form.category_id.choices = [(1, "Drysuit Repairs")]
            assert not form.validate()
            assert "category_id" in form.errors


# ---------------------------------------------------------------------------
# PriceListItemForm — defaults
# ---------------------------------------------------------------------------


class TestPriceListItemFormDefaults:
    """Verify that field defaults are applied correctly."""

    def test_defaults_applied(self, app):
        with app.test_request_context():
            form = PriceListItemForm()
            assert form.is_per_unit.data is True
            assert form.default_quantity.data == 1
            assert form.unit_label.data == "each"
            assert form.auto_deduct_parts.data is False
            assert form.is_taxable.data is True
            assert form.sort_order.data == 0
            assert form.is_active.data is True

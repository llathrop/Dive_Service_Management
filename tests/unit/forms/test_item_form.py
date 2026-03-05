"""Unit tests for service-item and drysuit-details forms.

Tests cover required-field validation, optional-field behaviour,
and defaults for ``ServiceItemForm`` and ``DrysuitDetailsForm``.
"""

import pytest
from werkzeug.datastructures import MultiDict

from app.forms.item import DrysuitDetailsForm, ServiceItemForm

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# ServiceItemForm — valid data
# ---------------------------------------------------------------------------


class TestServiceItemFormValid:
    """Scenarios where the form should pass validation."""

    def test_valid_minimal(self, app):
        with app.test_request_context():
            form = ServiceItemForm(
                formdata=MultiDict([
                    ("name", "My Regulator"),
                    ("item_category", "Regulator"),
                ])
            )
            assert form.validate(), form.errors

    def test_valid_with_empty_category(self, app):
        """Selecting the blank '-- Select --' option is allowed."""
        with app.test_request_context():
            form = ServiceItemForm(
                formdata=MultiDict([
                    ("name", "Mystery Item"),
                    ("item_category", ""),
                ])
            )
            assert form.validate(), form.errors

    def test_valid_all_fields(self, app):
        with app.test_request_context():
            form = ServiceItemForm(
                formdata=MultiDict([
                    ("serial_number", "REG-2024-001"),
                    ("name", "Apeks XTX50"),
                    ("item_category", "Regulator"),
                    ("serviceability", "serviceable"),
                    ("serviceability_notes", "Good condition"),
                    ("brand", "Apeks"),
                    ("model", "XTX50"),
                    ("year_manufactured", "2022"),
                    ("notes", "Customer's primary reg set"),
                    ("customer_id", "42"),
                ])
            )
            assert form.validate(), form.errors


# ---------------------------------------------------------------------------
# ServiceItemForm — invalid data
# ---------------------------------------------------------------------------


class TestServiceItemFormInvalid:
    """Scenarios where the form should fail validation."""

    def test_missing_name(self, app):
        with app.test_request_context():
            form = ServiceItemForm(
                formdata=MultiDict([
                    ("name", ""),
                    ("item_category", "Regulator"),
                ])
            )
            assert not form.validate()
            assert "name" in form.errors

    def test_year_too_low(self, app):
        with app.test_request_context():
            form = ServiceItemForm(
                formdata=MultiDict([
                    ("name", "Old Suit"),
                    ("item_category", "Drysuit"),
                    ("year_manufactured", "1800"),
                ])
            )
            assert not form.validate()
            assert "year_manufactured" in form.errors

    def test_year_too_high(self, app):
        with app.test_request_context():
            form = ServiceItemForm(
                formdata=MultiDict([
                    ("name", "Future Suit"),
                    ("item_category", "Drysuit"),
                    ("year_manufactured", "2200"),
                ])
            )
            assert not form.validate()
            assert "year_manufactured" in form.errors


# ---------------------------------------------------------------------------
# ServiceItemForm — defaults
# ---------------------------------------------------------------------------


class TestServiceItemFormDefaults:
    """Verify that field defaults are applied correctly."""

    def test_defaults_applied(self, app):
        with app.test_request_context():
            form = ServiceItemForm()
            assert form.serviceability.data == "serviceable"


# ---------------------------------------------------------------------------
# DrysuitDetailsForm — valid data
# ---------------------------------------------------------------------------


class TestDrysuitDetailsFormValid:
    """Scenarios where the drysuit form should pass validation."""

    def test_valid_empty(self, app):
        """All fields are optional so an empty form is valid."""
        with app.test_request_context():
            form = DrysuitDetailsForm(formdata=MultiDict())
            assert form.validate(), form.errors

    def test_valid_all_fields(self, app):
        with app.test_request_context():
            form = DrysuitDetailsForm(
                formdata=MultiDict([
                    ("size", "Large"),
                    ("material_type", "Trilaminate"),
                    ("material_thickness", "4mm"),
                    ("color", "Black/Red"),
                    ("suit_entry_type", "Back-entry"),
                    ("neck_seal_type", "Silicone"),
                    ("neck_seal_system", "SiTech QCS"),
                    ("wrist_seal_type", "Silicone"),
                    ("wrist_seal_system", "SiTech QCS"),
                    ("zipper_type", "YKK Aquaseal"),
                    ("zipper_length", "28in"),
                    ("zipper_orientation", "Back"),
                    ("inflate_valve_brand", "SI Tech"),
                    ("inflate_valve_model", "Standard"),
                    ("inflate_valve_position", "Chest"),
                    ("dump_valve_brand", "SI Tech"),
                    ("dump_valve_model", "Auto"),
                    ("dump_valve_type", "Shoulder"),
                    ("boot_type", "Integrated Rock Boot"),
                    ("boot_size", "10"),
                ])
            )
            assert form.validate(), form.errors

    def test_partial_data_valid(self, app):
        """Filling only a few fields should still validate."""
        with app.test_request_context():
            form = DrysuitDetailsForm(
                formdata=MultiDict([
                    ("material_type", "Neoprene"),
                    ("boot_type", "Integrated Sock"),
                ])
            )
            assert form.validate(), form.errors

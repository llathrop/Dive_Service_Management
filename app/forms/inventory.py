"""Inventory forms.

WTForms form classes for managing shop inventory items (parts, supplies,
consumables), adjusting stock levels, and searching the inventory list.
"""

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    DecimalField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class InventoryItemForm(FlaskForm):
    """Form for creating and editing an inventory (stock) item."""

    sku = StringField(
        "SKU",
        validators=[Optional(), Length(max=50)],
    )
    name = StringField(
        "Name",
        validators=[DataRequired(), Length(max=255)],
    )
    description = TextAreaField("Description", validators=[Optional()])
    category = StringField(
        "Category",
        validators=[DataRequired(), Length(max=100)],
    )
    subcategory = StringField(
        "Subcategory",
        validators=[Optional(), Length(max=100)],
    )
    manufacturer = StringField(
        "Manufacturer",
        validators=[Optional(), Length(max=100)],
    )
    manufacturer_part_number = StringField(
        "Manufacturer Part Number",
        validators=[Optional(), Length(max=100)],
    )
    purchase_cost = DecimalField(
        "Purchase Cost",
        places=2,
        validators=[Optional()],
    )
    resale_price = DecimalField(
        "Resale Price",
        places=2,
        validators=[Optional()],
    )
    markup_percent = DecimalField(
        "Markup %",
        places=2,
        validators=[Optional()],
    )
    quantity_in_stock = IntegerField(
        "Quantity in Stock",
        default=0,
        validators=[Optional()],
    )
    reorder_level = IntegerField(
        "Reorder Level",
        default=0,
        validators=[Optional()],
    )
    reorder_quantity = IntegerField(
        "Reorder Quantity",
        validators=[Optional()],
    )
    unit_of_measure = SelectField(
        "Unit of Measure",
        choices=[
            ("each", "Each"),
            ("ft", "Feet"),
            ("ml", "Milliliters"),
            ("oz", "Ounces"),
            ("pair", "Pair"),
            ("set", "Set"),
        ],
    )
    storage_location = StringField(
        "Storage Location",
        validators=[Optional(), Length(max=100)],
    )
    is_active = BooleanField("Active", default=True)
    is_for_resale = BooleanField("For Resale", default=False)
    preferred_supplier = StringField(
        "Preferred Supplier",
        validators=[Optional(), Length(max=255)],
    )
    supplier_url = StringField(
        "Supplier URL",
        validators=[Optional(), Length(max=500)],
    )
    minimum_order_quantity = IntegerField(
        "Minimum Order Quantity",
        validators=[Optional()],
    )
    supplier_lead_time_days = IntegerField(
        "Supplier Lead Time (days)",
        validators=[Optional()],
    )
    expiration_date = DateField(
        "Expiration Date",
        validators=[Optional()],
    )
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save Item")


class InventorySearchForm(FlaskForm):
    """GET-based search / filter form for inventory items.

    CSRF is disabled because this form is submitted via GET query parameters.
    The ``category`` choices should be populated dynamically in the route.
    """

    class Meta:
        csrf = False

    q = StringField("Search", validators=[Optional()])
    category = SelectField(
        "Category",
        choices=[("", "All")],
        default="",
    )
    low_stock_only = BooleanField("Low Stock Only", default=False)
    is_active = SelectField(
        "Status",
        choices=[("", "All"), ("1", "Active"), ("0", "Inactive")],
        default="",
    )
    submit = SubmitField("Search")


class StockAdjustmentForm(FlaskForm):
    """Form for adjusting the stock level of an inventory item.

    The ``adjustment`` value can be positive (stock in) or negative
    (stock out / correction).
    """

    adjustment = IntegerField(
        "Adjustment (+/-)",
        validators=[DataRequired()],
    )
    reason = StringField(
        "Reason",
        validators=[DataRequired(), Length(max=255)],
    )
    submit = SubmitField("Adjust Stock")

"""Price list forms.

WTForms form classes for managing service price-list categories and
their individual line items.  These drive the shop's standard pricing
for repairs, inspections, and other services.
"""

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DecimalField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class PriceListCategoryForm(FlaskForm):
    """Form for creating and editing a price-list category.

    Categories group related services (e.g. "Drysuit Repairs",
    "Regulator Service") for presentation and filtering.
    """

    name = StringField(
        "Category Name",
        validators=[DataRequired(), Length(max=100)],
    )
    description = TextAreaField(
        "Description",
        validators=[Optional(), Length(max=500)],
    )
    sort_order = IntegerField(
        "Sort Order",
        default=0,
        validators=[Optional()],
    )
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Save Category")


class PriceListItemForm(FlaskForm):
    """Form for creating and editing a price-list service item.

    The ``category_id`` choices must be populated dynamically in the
    route from the current set of active ``PriceListCategory`` rows.
    """

    category_id = SelectField(
        "Category",
        coerce=int,
        validators=[DataRequired()],
    )
    code = StringField(
        "Code",
        validators=[Optional(), Length(max=30)],
    )
    name = StringField(
        "Service Name",
        validators=[DataRequired(), Length(max=255)],
    )
    description = TextAreaField("Description", validators=[Optional()])
    price = DecimalField(
        "Price",
        places=2,
        validators=[DataRequired(), NumberRange(min=0)],
    )
    cost = DecimalField(
        "Cost",
        places=2,
        validators=[Optional()],
    )
    price_tier = StringField(
        "Price Tier",
        validators=[Optional(), Length(max=50)],
    )
    is_per_unit = BooleanField("Per Unit", default=True)
    default_quantity = DecimalField(
        "Default Quantity",
        places=2,
        default=1,
        validators=[Optional()],
    )
    unit_label = StringField(
        "Unit Label",
        default="each",
        validators=[Optional(), Length(max=50)],
    )
    auto_deduct_parts = BooleanField("Auto-Deduct Parts", default=False)
    is_taxable = BooleanField("Taxable", default=True)
    sort_order = IntegerField(
        "Sort Order",
        default=0,
        validators=[Optional()],
    )
    is_active = BooleanField("Active", default=True)
    internal_notes = TextAreaField("Internal Notes", validators=[Optional()])
    submit = SubmitField("Save Item")

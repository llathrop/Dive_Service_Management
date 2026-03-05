"""Applied service forms.

WTForms form class for adding a service from the price list (or a
custom ad-hoc service) to a service order item.  Supports both
price-list-driven entries and free-form custom services with
per-line discounts and taxability.
"""

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DecimalField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional


def coerce_int_or_none(value):
    """Coerce a SelectField value to int, treating empty strings as None."""
    if value == "" or value is None:
        return None
    return int(value)


class AppliedServiceForm(FlaskForm):
    """Form for adding a service to a service order item.

    The ``price_list_item_id`` choices should be populated dynamically
    in the route from the active price list items.  When set to the
    blank option, the service is treated as a custom (ad-hoc) entry
    and the ``service_name`` / ``unit_price`` fields must be filled
    manually.
    """

    price_list_item_id = SelectField(
        "Price List Item",
        coerce=coerce_int_or_none,
        validators=[Optional()],
        choices=[("", "-- Select (or leave blank for custom) --")],
    )
    service_name = StringField(
        "Service Name",
        validators=[DataRequired(), Length(max=255)],
    )
    service_description = TextAreaField(
        "Service Description",
        validators=[Optional(), Length(max=5000)],
    )
    quantity = DecimalField(
        "Quantity",
        places=2,
        default=1,
        validators=[DataRequired(), NumberRange(min=0.01)],
    )
    unit_price = DecimalField(
        "Unit Price",
        places=2,
        validators=[DataRequired(), NumberRange(min=0)],
    )
    discount_percent = DecimalField(
        "Discount %",
        places=2,
        default=0.00,
        validators=[Optional(), NumberRange(min=0, max=100)],
    )
    is_taxable = BooleanField("Taxable", default=True)
    notes = StringField(
        "Notes",
        validators=[Optional(), Length(max=500)],
    )
    submit = SubmitField("Add Service")

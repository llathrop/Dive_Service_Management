"""Parts used forms.

WTForms form class for recording a part (inventory item) consumed
during a service order item's repair or maintenance.  Captures the
quantity used and the unit price at the time of use for accurate
invoicing even if inventory prices change later.
"""

from flask_wtf import FlaskForm
from wtforms import (
    DecimalField,
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.forms.order import coerce_int_or_none


class PartUsedForm(FlaskForm):
    """Form for adding a part to a service order item.

    The ``inventory_item_id`` choices must be populated dynamically in
    the route from the current active inventory items.
    """

    inventory_item_id = SelectField(
        "Inventory Item",
        coerce=coerce_int_or_none,
        validators=[DataRequired()],
        choices=[("", "-- Select --")],
    )
    quantity = DecimalField(
        "Quantity",
        places=2,
        default=1,
        validators=[DataRequired(), NumberRange(min=0.01)],
    )
    unit_price_at_use = DecimalField(
        "Unit Price",
        places=2,
        validators=[DataRequired(), NumberRange(min=0)],
    )
    notes = StringField(
        "Notes",
        validators=[Optional(), Length(max=500)],
    )
    submit = SubmitField("Add Part")

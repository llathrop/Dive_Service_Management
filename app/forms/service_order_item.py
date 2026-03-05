"""Service order item forms.

WTForms form class for adding a customer-owned service item to an
existing service order.  The ``service_item_id`` choices must be
populated dynamically in the route from the customer's equipment list.
"""

from flask_wtf import FlaskForm
from wtforms import (
    SelectField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, Optional

from app.forms.order import coerce_int_or_none


class ServiceOrderItemForm(FlaskForm):
    """Form for adding a service item to a service order.

    The ``service_item_id`` choices should be populated dynamically in
    the route from the customer's service items (regulators, BCDs,
    drysuits, etc.).
    """

    service_item_id = SelectField(
        "Service Item",
        coerce=coerce_int_or_none,
        validators=[DataRequired()],
        choices=[("", "-- Select --")],
    )
    work_description = TextAreaField(
        "Work Description",
        validators=[Optional(), Length(max=5000)],
    )
    condition_at_receipt = TextAreaField(
        "Condition at Receipt",
        validators=[Optional(), Length(max=5000)],
    )
    submit = SubmitField("Add Item")

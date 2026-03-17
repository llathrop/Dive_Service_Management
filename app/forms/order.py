"""Service order forms.

WTForms form classes for creating, editing, and searching service orders.
The ``ServiceOrderForm`` handles the full order lifecycle with status
tracking, technician assignment, and pricing fields.  ``OrderSearchForm``
is a lightweight GET-based form (CSRF disabled) for filtering order lists.
"""

from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    DecimalField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional


def coerce_int_or_none(value):
    """Coerce a SelectField value to int, treating empty strings as None.

    Passes through non-numeric sentinel strings (e.g. '__new__') so they
    can be used as placeholder option values in dropdowns.
    """
    if value == "" or value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return value


# Valid status choices for service orders.
VALID_STATUSES = [
    ("intake", "Intake"),
    ("assessment", "Assessment"),
    ("awaiting_approval", "Awaiting Approval"),
    ("in_progress", "In Progress"),
    ("awaiting_parts", "Awaiting Parts"),
    ("completed", "Completed"),
    ("ready_for_pickup", "Ready for Pickup"),
    ("picked_up", "Picked Up"),
    ("cancelled", "Cancelled"),
]

# Valid priority choices for service orders.
VALID_PRIORITIES = [
    ("low", "Low"),
    ("normal", "Normal"),
    ("high", "High"),
    ("rush", "Rush"),
]


class ServiceOrderForm(FlaskForm):
    """Form for creating and editing a service order.

    The ``customer_id`` and ``assigned_tech_id`` choices must be populated
    dynamically in the route from the current set of customers and
    technician-role users respectively.
    """

    customer_id = SelectField(
        "Customer",
        coerce=coerce_int_or_none,
        validators=[DataRequired()],
        choices=[("", "-- Select --")],
    )
    status = SelectField(
        "Status",
        choices=[("", "-- Select --")] + VALID_STATUSES,
        validators=[DataRequired()],
        default="intake",
    )
    priority = SelectField(
        "Priority",
        choices=[("", "-- Select --")] + VALID_PRIORITIES,
        validators=[DataRequired()],
        default="normal",
    )
    assigned_tech_id = SelectField(
        "Assigned Technician",
        coerce=coerce_int_or_none,
        validators=[Optional()],
        choices=[("", "-- Select --")],
    )
    date_received = DateField(
        "Date Received",
        validators=[DataRequired()],
        format="%Y-%m-%d",
    )
    date_promised = DateField(
        "Date Promised",
        validators=[Optional()],
    )
    description = TextAreaField(
        "Description",
        validators=[Optional(), Length(max=5000)],
    )
    internal_notes = TextAreaField(
        "Internal Notes",
        validators=[Optional(), Length(max=5000)],
    )
    estimated_total = DecimalField(
        "Estimated Total",
        places=2,
        validators=[Optional(), NumberRange(min=0)],
    )
    rush_fee = DecimalField(
        "Rush Fee",
        places=2,
        default=0.00,
        validators=[Optional(), NumberRange(min=0)],
    )
    discount_percent = DecimalField(
        "Discount %",
        places=2,
        default=0.00,
        validators=[Optional(), NumberRange(min=0, max=100)],
    )
    discount_amount = DecimalField(
        "Discount Amount",
        places=2,
        default=0.00,
        validators=[Optional(), NumberRange(min=0)],
    )
    submit = SubmitField("Save Order")


class OrderSearchForm(FlaskForm):
    """GET-based search / filter form for the service order list.

    CSRF is disabled because this form is submitted via GET query parameters.
    The ``assigned_tech_id`` choices should be populated dynamically in the
    route from technician-role users.
    """

    class Meta:
        csrf = False

    q = StringField("Search", validators=[Optional()])
    status = SelectField(
        "Status",
        choices=[("", "All Statuses")] + VALID_STATUSES,
        default="",
    )
    priority = SelectField(
        "Priority",
        choices=[("", "All Priorities")] + VALID_PRIORITIES,
        default="",
    )
    assigned_tech_id = SelectField(
        "Assigned Technician",
        coerce=coerce_int_or_none,
        choices=[("", "All Technicians")],
        default="",
    )
    date_from = DateField(
        "Date From",
        validators=[Optional()],
    )
    date_to = DateField(
        "Date To",
        validators=[Optional()],
    )
    submit = SubmitField("Search")

"""Labor entry forms.

WTForms form class for recording labor time against a service order
item.  Each entry captures the technician, hours worked, hourly rate,
and a brief description of the work performed.
"""

from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    DecimalField,
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.forms.order import coerce_int_or_none


class LaborEntryForm(FlaskForm):
    """Form for adding a labor entry to a service order item.

    The ``tech_id`` choices must be populated dynamically in the route
    from users with the technician role.
    """

    tech_id = SelectField(
        "Technician",
        coerce=coerce_int_or_none,
        validators=[DataRequired()],
        choices=[("", "-- Select --")],
    )
    hours = DecimalField(
        "Hours",
        places=2,
        validators=[DataRequired(), NumberRange(min=0.1, max=24)],
    )
    hourly_rate = DecimalField(
        "Hourly Rate",
        places=2,
        validators=[DataRequired(), NumberRange(min=0)],
    )
    description = StringField(
        "Description",
        validators=[Optional(), Length(max=500)],
    )
    work_date = DateField(
        "Work Date",
        validators=[DataRequired()],
        format="%Y-%m-%d",
    )
    submit = SubmitField("Add Labor")

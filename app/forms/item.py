"""Service item forms.

WTForms form classes for managing customer-owned service items
(regulators, BCDs, drysuits, etc.) and drysuit-specific detail fields.
"""

from flask_wtf import FlaskForm
from wtforms import (
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, Optional


class ServiceItemForm(FlaskForm):
    """Form for creating and editing a customer's service item.

    The ``customer_id`` hidden field is populated by the route so the
    item is correctly linked to its owner.
    """

    serial_number = StringField(
        "Serial Number",
        validators=[Optional(), Length(max=100)],
    )
    name = StringField(
        "Item Name",
        validators=[DataRequired(), Length(max=255)],
    )
    item_category = SelectField(
        "Category",
        choices=[
            ("", "-- Select --"),
            ("Drysuit", "Drysuit"),
            ("BCD", "BCD"),
            ("Regulator", "Regulator"),
            ("Wetsuit", "Wetsuit"),
            ("Other", "Other"),
        ],
    )
    serviceability = SelectField(
        "Serviceability",
        choices=[
            ("serviceable", "Serviceable"),
            ("non_serviceable", "Non-Serviceable"),
            ("conditional", "Conditional"),
            ("retired", "Retired"),
        ],
        default="serviceable",
    )
    serviceability_notes = TextAreaField(
        "Serviceability Notes",
        validators=[Optional()],
    )
    brand = StringField(
        "Brand",
        validators=[Optional(), Length(max=100)],
    )
    model = StringField(
        "Model",
        validators=[Optional(), Length(max=100)],
    )
    year_manufactured = IntegerField(
        "Year Manufactured",
        validators=[Optional(), NumberRange(min=1900, max=2100)],
    )
    notes = TextAreaField("Notes", validators=[Optional()])
    service_interval_days = IntegerField(
        "Service Interval (days)",
        validators=[Optional(), NumberRange(min=1, max=9999)],
    )
    customer_id = SelectField(
        "Customer",
        coerce=int,
        validators=[InputRequired()],
    )
    submit = SubmitField("Save Item")


from app.models.lookup import LookupValue

def get_lookup_choices(category):
    """Fetch choices for a SelectField from the lookup_values table."""
    try:
        lookups = LookupValue.query.filter_by(category=category, is_active=True).order_by(LookupValue.sort_order, LookupValue.display_name).all()
        return [("", "")] + [(l.value, l.display_name) for l in lookups]
    except Exception:
        # Fallback if DB is not ready or table doesn't exist yet
        return [("", "")]

class DrysuitDetailsForm(FlaskForm):
    """Extended detail fields for drysuit service items.

    All fields are optional.  This form is typically rendered alongside
    (or embedded within) the ``ServiceItemForm`` when the selected
    category is *Drysuit*.
    """

    def __init__(self, *args, **kwargs):
        super(DrysuitDetailsForm, self).__init__(*args, **kwargs)
        self.material_type.choices = get_lookup_choices('material_type')
        self.suit_entry_type.choices = get_lookup_choices('suit_entry_type')
        self.neck_seal_type.choices = get_lookup_choices('neck_seal_type')
        self.wrist_seal_type.choices = get_lookup_choices('wrist_seal_type')
        self.zipper_orientation.choices = get_lookup_choices('zipper_orientation')
        self.dump_valve_type.choices = get_lookup_choices('dump_valve_type')
        self.boot_type.choices = get_lookup_choices('boot_type')

    size = StringField(
        "Size",
        validators=[Optional(), Length(max=50)],
    )
    material_type = SelectField(
        "Material Type",
        choices=[],
        validators=[Optional()],
    )
    material_thickness = StringField(
        "Material Thickness",
        validators=[Optional(), Length(max=50)],
    )
    color = StringField(
        "Color",
        validators=[Optional(), Length(max=100)],
    )
    suit_entry_type = SelectField(
        "Suit Entry Type",
        choices=[],
        validators=[Optional()],
    )

    # --- Seals ---
    neck_seal_type = SelectField(
        "Neck Seal Type",
        choices=[],
        validators=[Optional()],
    )
    neck_seal_system = StringField(
        "Neck Seal System",
        validators=[Optional(), Length(max=100)],
    )
    wrist_seal_type = SelectField(
        "Wrist Seal Type",
        choices=[],
        validators=[Optional()],
    )
    wrist_seal_system = StringField(
        "Wrist Seal System",
        validators=[Optional(), Length(max=100)],
    )

    # --- Zipper ---
    zipper_type = StringField(
        "Zipper Type",
        validators=[Optional(), Length(max=100)],
    )
    zipper_length = StringField(
        "Zipper Length",
        validators=[Optional(), Length(max=50)],
    )
    zipper_orientation = SelectField(
        "Zipper Orientation",
        choices=[],
        validators=[Optional()],
    )

    # --- Valves ---
    inflate_valve_brand = StringField(
        "Inflate Valve Brand",
        validators=[Optional(), Length(max=100)],
    )
    inflate_valve_model = StringField(
        "Inflate Valve Model",
        validators=[Optional(), Length(max=100)],
    )
    inflate_valve_position = StringField(
        "Inflate Valve Position",
        validators=[Optional(), Length(max=50)],
    )
    dump_valve_brand = StringField(
        "Dump Valve Brand",
        validators=[Optional(), Length(max=100)],
    )
    dump_valve_model = StringField(
        "Dump Valve Model",
        validators=[Optional(), Length(max=100)],
    )
    dump_valve_type = SelectField(
        "Dump Valve Type",
        choices=[],
        validators=[Optional()],
    )

    # --- Boots ---
    boot_type = SelectField(
        "Boot Type",
        choices=[],
        validators=[Optional()],
    )
    boot_size = StringField(
        "Boot Size",
        validators=[Optional(), Length(max=20)],
    )

"""Customer forms.

WTForms form classes for creating, editing, and searching customers.
The ``CustomerForm`` handles both individual and business customers
with custom cross-field validation.  ``CustomerSearchForm`` is a
lightweight GET-based form (CSRF disabled) for filtering customer lists.
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
from wtforms.validators import Email, Length, Optional


class CustomerForm(FlaskForm):
    """Form for creating and editing a customer record.

    Supports two customer types — *individual* (requires first + last name)
    and *business* (requires business name).  The ``validate`` override
    enforces this rule automatically.
    """

    customer_type = SelectField(
        "Customer Type",
        choices=[("individual", "Individual"), ("business", "Business")],
        default="individual",
    )
    first_name = StringField(
        "First Name",
        validators=[Optional(), Length(max=100)],
    )
    last_name = StringField(
        "Last Name",
        validators=[Optional(), Length(max=100)],
    )
    business_name = StringField(
        "Business Name",
        validators=[Optional(), Length(max=255)],
    )
    contact_person = StringField(
        "Contact Person",
        validators=[Optional(), Length(max=200)],
    )
    email = StringField(
        "Email",
        validators=[Optional(), Email(), Length(max=255)],
    )
    phone_primary = StringField(
        "Primary Phone",
        validators=[Optional(), Length(max=20)],
    )
    phone_secondary = StringField(
        "Secondary Phone",
        validators=[Optional(), Length(max=20)],
    )
    address_line1 = StringField(
        "Address Line 1",
        validators=[Optional(), Length(max=255)],
    )
    address_line2 = StringField(
        "Address Line 2",
        validators=[Optional(), Length(max=255)],
    )
    city = StringField(
        "City",
        validators=[Optional(), Length(max=100)],
    )
    state_province = StringField(
        "State / Province",
        validators=[Optional(), Length(max=100)],
    )
    postal_code = StringField(
        "Postal Code",
        validators=[Optional(), Length(max=20)],
    )
    country = StringField(
        "Country",
        default="US",
        validators=[Optional(), Length(max=100)],
    )
    preferred_contact = SelectField(
        "Preferred Contact Method",
        choices=[
            ("email", "Email"),
            ("phone", "Phone"),
            ("text", "Text"),
            ("none", "None"),
        ],
        default="email",
    )
    tax_exempt = BooleanField("Tax Exempt", default=False)
    tax_id = StringField(
        "Tax ID",
        validators=[Optional(), Length(max=50)],
    )
    payment_terms = StringField(
        "Payment Terms",
        validators=[Optional(), Length(max=100)],
    )
    credit_limit = DecimalField(
        "Credit Limit",
        places=2,
        validators=[Optional()],
    )
    notes = TextAreaField("Notes", validators=[Optional()])
    referral_source = StringField(
        "Referral Source",
        validators=[Optional(), Length(max=100)],
    )
    submit = SubmitField("Save Customer")

    def validate(self, extra_validators=None):
        """Run standard validators then enforce name requirements.

        * Individual customers must have both ``first_name`` and ``last_name``.
        * Business customers must have ``business_name``.
        """
        if not super().validate(extra_validators=extra_validators):
            return False

        valid = True

        if self.customer_type.data == "individual":
            if not self.first_name.data or not self.first_name.data.strip():
                self.first_name.errors.append(
                    "First name is required for individual customers."
                )
                valid = False
            if not self.last_name.data or not self.last_name.data.strip():
                self.last_name.errors.append(
                    "Last name is required for individual customers."
                )
                valid = False
        elif self.customer_type.data == "business":
            if not self.business_name.data or not self.business_name.data.strip():
                self.business_name.errors.append(
                    "Business name is required for business customers."
                )
                valid = False

        return valid


class CustomerSearchForm(FlaskForm):
    """GET-based search / filter form for the customer list.

    CSRF is disabled because this form is submitted via GET query parameters.
    """

    class Meta:
        csrf = False

    q = StringField("Search", validators=[Optional()])
    customer_type = SelectField(
        "Customer Type",
        choices=[("", "All"), ("individual", "Individual"), ("business", "Business")],
        default="",
    )
    has_open_orders = BooleanField("Has Open Orders", default=False)
    has_balance = BooleanField("Has Balance", default=False)
    submit = SubmitField("Search")

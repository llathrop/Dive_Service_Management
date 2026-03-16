"""Settings forms for admin configuration pages.

One form per settings category, dynamically populated from SystemConfig
rows.  ENV-locked fields are rendered as read-only in the template.
"""

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import DecimalField, IntegerField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class CompanySettingsForm(FlaskForm):
    """Company information settings."""

    company_name = StringField(
        "Company Name",
        validators=[DataRequired(), Length(max=255)],
    )
    company_address = TextAreaField(
        "Address",
        validators=[Optional(), Length(max=500)],
    )
    company_phone = StringField(
        "Phone",
        validators=[Optional(), Length(max=50)],
    )
    company_email = StringField(
        "Email",
        validators=[Optional(), Length(max=255)],
    )
    company_website = StringField(
        "Website",
        validators=[Optional(), Length(max=500)],
    )
    logo_upload = FileField(
        "Header Logo",
        validators=[
            FileAllowed(["jpg", "jpeg", "png"], "Images only (JPG, PNG)"),
        ],
    )
    invoice_logo_upload = FileField(
        "Invoice Logo (optional)",
        validators=[
            FileAllowed(["jpg", "jpeg", "png"], "Images only (JPG, PNG)"),
        ],
    )


class ServiceSettingsForm(FlaskForm):
    """Service order settings."""

    order_prefix = StringField(
        "Order Number Prefix",
        validators=[DataRequired(), Length(max=10)],
    )
    default_labor_rate = DecimalField(
        "Default Labor Rate ($)",
        places=2,
        validators=[DataRequired(), NumberRange(min=0)],
    )
    rush_fee_default = DecimalField(
        "Default Rush Fee ($)",
        places=2,
        validators=[DataRequired(), NumberRange(min=0)],
    )


class InvoiceTaxSettingsForm(FlaskForm):
    """Invoice and tax settings."""

    invoice_prefix = StringField(
        "Invoice Number Prefix",
        validators=[DataRequired(), Length(max=10)],
    )
    default_terms = StringField(
        "Default Payment Terms",
        validators=[Optional(), Length(max=255)],
    )
    default_due_days = IntegerField(
        "Default Due Days",
        validators=[DataRequired(), NumberRange(min=1, max=365)],
    )
    footer_text = TextAreaField(
        "Invoice Footer Text",
        validators=[Optional(), Length(max=1000)],
    )
    tax_rate = DecimalField(
        "Default Tax Rate",
        places=4,
        validators=[DataRequired(), NumberRange(min=0, max=1)],
        description="Enter as decimal (e.g. 0.0825 for 8.25%)",
    )
    tax_label = StringField(
        "Tax Label",
        validators=[DataRequired(), Length(max=100)],
    )


class DisplaySettingsForm(FlaskForm):
    """Display and formatting settings."""

    date_format = StringField(
        "Date Format",
        validators=[DataRequired(), Length(max=50)],
        description="Python strftime format (e.g. %Y-%m-%d)",
    )
    currency_symbol = StringField(
        "Currency Symbol",
        validators=[DataRequired(), Length(max=10)],
    )
    currency_code = StringField(
        "Currency Code",
        validators=[DataRequired(), Length(max=10)],
        description="ISO 4217 code (e.g. USD)",
    )
    pagination_size = IntegerField(
        "Rows Per Page",
        validators=[DataRequired(), NumberRange(min=5, max=200)],
    )


class NotificationSettingsForm(FlaskForm):
    """Notification settings."""

    low_stock_check_hours = IntegerField(
        "Low Stock Check Interval (hours)",
        validators=[DataRequired(), NumberRange(min=1, max=168)],
    )
    overdue_check_time = StringField(
        "Overdue Invoice Check Time",
        validators=[DataRequired(), Length(max=10)],
        description="24-hour format (e.g. 08:00)",
    )
    retention_days = IntegerField(
        "Notification Retention (days)",
        validators=[DataRequired(), NumberRange(min=1, max=365)],
    )
    order_due_warning_days = IntegerField(
        "Order Due Warning (days before)",
        validators=[DataRequired(), NumberRange(min=1, max=30)],
    )


class SecuritySettingsForm(FlaskForm):
    """Security settings."""

    password_min_length = IntegerField(
        "Minimum Password Length",
        validators=[DataRequired(), NumberRange(min=6, max=128)],
    )
    lockout_attempts = IntegerField(
        "Failed Login Attempts Before Lockout",
        validators=[DataRequired(), NumberRange(min=1, max=20)],
    )
    lockout_duration_minutes = IntegerField(
        "Lockout Duration (minutes)",
        validators=[DataRequired(), NumberRange(min=1, max=1440)],
    )
    session_lifetime_hours = IntegerField(
        "Session Lifetime (hours)",
        validators=[DataRequired(), NumberRange(min=1, max=720)],
    )

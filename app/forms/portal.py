"""Portal authentication forms."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length


class PortalLoginForm(FlaskForm):
    """Separate login form for customer portal users."""

    email = StringField(
        "Email Address",
        validators=[DataRequired(), Email(), Length(max=255)],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(max=255)],
    )
    remember = BooleanField("Remember me", default=False)
    submit = SubmitField("Sign In")


class PortalActivationForm(FlaskForm):
    """Initial password setup for an invited portal user."""

    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=8, max=255)],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(),
            EqualTo("password", message="Passwords must match."),
        ],
    )
    submit = SubmitField("Activate Account")

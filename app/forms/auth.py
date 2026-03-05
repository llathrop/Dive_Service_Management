"""Custom authentication forms.

Flask-Security-Too provides fully-functional ``LoginForm`` and
``RegisterForm`` classes out of the box.  This module extends them
only where the application needs custom fields or validation (e.g.
adding a ``username`` field to registration, or customising the login
form's look-and-feel).

For Phase 1, registration is disabled (``SECURITY_REGISTERABLE=False``)
so only the login form customization is relevant.
"""

from flask_security.forms import LoginForm
from wtforms import StringField
from wtforms.validators import DataRequired


class ExtendedLoginForm(LoginForm):
    """Login form that accepts an email address.

    Flask-Security's default ``LoginForm`` already handles email + password
    login.  This subclass exists as a convenient extension point if we
    later want to add "remember me" styling, CAPTCHA, or a username field.

    To activate, pass ``login_form=ExtendedLoginForm`` to the Security
    extension init in the app factory.
    """

    # Example: override the email field's label or add a placeholder
    # email = StringField("Email", validators=[DataRequired()])
    pass

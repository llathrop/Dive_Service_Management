"""Custom authentication forms.

Flask-Security-Too provides fully-functional ``LoginForm`` and
``RegisterForm`` classes out of the box.  This module extends them
only where the application needs custom fields or validation (e.g.
adding a ``username`` field to registration, or customising the login
form's look-and-feel).

Registration is disabled (``SECURITY_REGISTERABLE=False``), so only the
login form customization is relevant.
"""

from flask_security.forms import LoginForm


class ExtendedLoginForm(LoginForm):
    """Extended login form registered with Flask-Security.

    Inherits email, password, remember, and submit fields from
    Flask-Security's ``LoginForm``.  This subclass serves as the
    application's login form extension point for any future custom
    fields or validation (e.g. CAPTCHA, username field).

    Registered via ``login_form=ExtendedLoginForm`` in the app factory's
    ``_init_extensions()`` call to ``security.init_app()``.
    """

    # The parent LoginForm already provides a ``remember`` BooleanField.
    # Add custom fields below as needed.

"""Authentication blueprint.

Flask-Security-Too automatically registers its own routes for login,
logout, register, etc. at the ``SECURITY_URL_PREFIX`` (default ``/``).
This blueprint adds any *custom* auth-related routes that live outside
Flask-Security's scope.

Key auto-registered routes (provided by Flask-Security):
    GET/POST  /login
    GET/POST  /logout
    GET/POST  /register   (disabled via SECURITY_REGISTERABLE=False)
    GET/POST  /change     (password change, if SECURITY_CHANGEABLE=True)
"""

from flask import Blueprint, redirect, url_for
from flask_security import current_user

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def index():
    """Root URL -- redirect to dashboard if logged in, otherwise to login."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    return redirect(url_for("security.login"))

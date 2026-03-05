"""Flask extension instances.

Extensions are created here in an uninitialized state, then bound to the
application via ``init_app()`` calls inside the ``create_app`` factory in
``app/__init__.py``.  Importing from this module is the canonical way to
reference the global extension objects throughout the codebase.
"""

from flask_migrate import Migrate
from flask_security import Security
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

# Database ORM
db = SQLAlchemy()

# Schema migrations (Alembic)
migrate = Migrate()

# Authentication & authorization (Flask-Security-Too)
security = Security()

# CSRF protection (initialized separately in factory so it can be
# selectively disabled during testing)
csrf = CSRFProtect()

# Mail support — placeholder for future password-reset / notification emails.
# Flask-Mail is an optional dependency; if not installed we create a small
# stand-in so that importing this module never fails.
try:
    from flask_mail import Mail

    mail = Mail()
except ImportError:  # pragma: no cover
    mail = None  # type: ignore[assignment]

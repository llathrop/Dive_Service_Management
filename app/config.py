"""Application configuration classes.

Configuration hierarchy: ENV vars > instance/config.py > DB system_config > app defaults.
All sensitive values are loaded from environment variables with sensible defaults
for development only.
"""

import os

from dotenv import load_dotenv

# Load .env file if it exists (no-op in production where real env vars are set)
load_dotenv()


class Config:
    """Base configuration with shared defaults."""

    # --- Flask Core ---
    SECRET_KEY = os.environ.get("DSM_SECRET_KEY", "change-me-in-production")

    # --- Database ---
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DSM_DATABASE_URL",
        "mysql+mysqldb://dsm_user:dsm_pass@localhost:3306/dive_service_mgmt?charset=utf8mb4",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 280,
        "pool_pre_ping": True,
    }

    # --- Flask-Security-Too ---
    SECURITY_PASSWORD_SALT = os.environ.get(
        "DSM_SECURITY_PASSWORD_SALT", "change-me-salt-in-production"
    )
    SECURITY_PASSWORD_HASH = "argon2"
    SECURITY_REGISTERABLE = False
    SECURITY_SEND_REGISTER_EMAIL = False
    SECURITY_TOKEN_AUTHENTICATION_HEADER = None  # Session-based auth only
    SECURITY_TRACKABLE = True  # Enable login tracking fields
    SECURITY_CHANGEABLE = True  # Allow password changes
    SECURITY_RECOVERABLE = False  # Disable password recovery (no email configured yet)
    SECURITY_POST_LOGIN_VIEW = "/dashboard"
    SECURITY_POST_LOGOUT_VIEW = "/login"
    # When None, Flask-Security returns 403 for authenticated users who lack
    # the required role; unauthenticated users are still redirected to login
    # via @login_required.
    SECURITY_UNAUTHORIZED_VIEW = None
    # Suppress Flask-Security's default flash messages category prefix
    SECURITY_MSG_UNAUTHORIZED = ("You do not have permission to access this page.", "warning")

    # --- CSRF ---
    WTF_CSRF_ENABLED = True

    # --- File Uploads ---
    MAX_CONTENT_LENGTH = int(
        os.environ.get("DSM_MAX_CONTENT_LENGTH", 16 * 1024 * 1024)
    )  # Default 16 MB
    UPLOAD_FOLDER = os.environ.get(
        "DSM_UPLOAD_FOLDER",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads"),
    )

    # --- Celery ---
    CELERY_BROKER_URL = os.environ.get(
        "DSM_CELERY_BROKER_URL", "redis://localhost:6379/0"
    )
    CELERY_RESULT_BACKEND = os.environ.get(
        "DSM_CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
    )

    # --- Redis ---
    REDIS_URL = os.environ.get("DSM_REDIS_URL", "redis://localhost:6379/0")

    # --- Mail (placeholder for future use) ---
    MAIL_SERVER = os.environ.get("DSM_MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.environ.get("DSM_MAIL_PORT", 25))
    MAIL_USE_TLS = os.environ.get("DSM_MAIL_USE_TLS", "false").lower() == "true"
    MAIL_USERNAME = os.environ.get("DSM_MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("DSM_MAIL_PASSWORD")


class DevelopmentConfig(Config):
    """Development configuration with debug mode enabled."""

    DEBUG = True


class ProductionConfig(Config):
    """Production configuration with debug mode disabled."""

    DEBUG = False
    # In production, SECRET_KEY and SECURITY_PASSWORD_SALT MUST be set via env vars.
    # The defaults in Config are only for development convenience.

    @classmethod
    def init_app(cls, app):
        """Validate production configuration at startup."""
        dangerous_defaults = {
            "SECRET_KEY": "change-me-in-production",
            "SECURITY_PASSWORD_SALT": "change-me-salt-in-production",
        }
        for key, dangerous_value in dangerous_defaults.items():
            if app.config.get(key) == dangerous_value:
                raise RuntimeError(
                    f"SECURITY ERROR: {key} is still set to the default value. "
                    f"Set the DSM_{key} environment variable before running in production."
                )


class TestingConfig(Config):
    """Testing configuration with in-memory SQLite and optimizations."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SECURITY_PASSWORD_HASH = "plaintext"
    # Disable CSRF for easier test client usage
    SERVER_NAME = "localhost"


# Map environment names to config classes for the app factory
config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}

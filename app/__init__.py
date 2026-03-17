"""Dive Service Management -- Application Factory.

This module contains ``create_app()``, the single entry-point for
bootstrapping the Flask application.  It follows the *app factory*
pattern so that multiple instances can coexist (e.g. in tests) and
configuration can be injected cleanly.

Typical usage::

    from app import create_app
    app = create_app()           # uses DSM_ENV or defaults to development
    app = create_app(TestingConfig)  # explicit config for test suite
"""

import os

from dotenv import load_dotenv
from flask import Flask, render_template, send_from_directory
from flask_login import login_required
from flask_security import SQLAlchemyUserDatastore

from app.config import config_by_name
from app.extensions import csrf, db, mail, migrate, security


def create_app(config_class=None):
    """Create and configure the Flask application.

    Args:
        config_class: A configuration class (e.g. ``TestingConfig``).
            If *None*, the class is selected based on the ``DSM_ENV``
            environment variable (default: ``"development"``).

    Returns:
        A fully-configured Flask application instance.
    """
    # Load .env early so DSM_ENV (and everything else) is available
    load_dotenv()

    # Resolve configuration class
    if config_class is None:
        # Check DSM_ENV first, fall back to FLASK_ENV for compatibility
        env_name = os.environ.get("DSM_ENV") or os.environ.get("FLASK_ENV", "development")
        config_class = config_by_name.get(env_name)
        if config_class is None:
            raise ValueError(
                f"Unknown environment value: {env_name!r}. "
                f"Expected one of: {', '.join(config_by_name)}"
            )

    # Create the Flask application
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    # Run config-class-specific validation (e.g. ProductionConfig checks secrets)
    if hasattr(config_class, 'init_app'):
        config_class.init_app(app)

    # Ensure the instance folder exists (Flask doesn't create it automatically)
    os.makedirs(app.instance_path, exist_ok=True)

    # Optionally load instance/config.py for local overrides (silent if absent)
    app.config.from_pyfile("config.py", silent=True)

    # ------------------------------------------------------------------
    # Initialise extensions
    # ------------------------------------------------------------------
    _init_extensions(app)

    # ------------------------------------------------------------------
    # Register blueprints
    # ------------------------------------------------------------------
    _register_blueprints(app)

    # ------------------------------------------------------------------
    # Register error handlers
    # ------------------------------------------------------------------
    _register_error_handlers(app)

    # ------------------------------------------------------------------
    # Register CLI commands
    # ------------------------------------------------------------------
    _register_cli(app)

    # ------------------------------------------------------------------
    # Register upload serving route
    # ------------------------------------------------------------------
    _register_upload_route(app)

    # ------------------------------------------------------------------
    # Register context processors
    # ------------------------------------------------------------------
    _register_context_processors(app)

    return app


# ======================================================================
# Private helper functions
# ======================================================================


def _init_extensions(app):
    """Bind all Flask extensions to the application."""
    # SQLAlchemy & Migrate
    db.init_app(app)
    migrate.init_app(app, db)

    # CSRF protection
    csrf.init_app(app)

    # Flask-Mail (if available)
    if mail is not None:
        mail.init_app(app)

    # Flask-Security-Too
    # Must be initialised AFTER db so the user datastore can reference
    # the User and Role models.
    from app.forms.auth import ExtendedLoginForm
    from app.models.user import Role, User

    user_datastore = SQLAlchemyUserDatastore(db, User, Role)
    security.init_app(app, user_datastore, login_form=ExtendedLoginForm)


def _register_blueprints(app):
    """Register all application blueprints."""
    from app.blueprints.admin import admin_bp
    from app.blueprints.attachments import attachments_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.customers import customers_bp
    from app.blueprints.dashboard import dashboard_bp
    from app.blueprints.docs import docs_bp
    from app.blueprints.export import export_bp
    from app.blueprints.health import health_bp
    from app.blueprints.inventory import inventory_bp
    from app.blueprints.invoices import invoices_bp
    from app.blueprints.items import items_bp
    from app.blueprints.notifications import notifications_bp
    from app.blueprints.orders import orders_bp
    from app.blueprints.price_list import price_list_bp
    from app.blueprints.reports import reports_bp
    from app.blueprints.search import search_bp
    from app.blueprints.tools import tools_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(attachments_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(invoices_bp)
    app.register_blueprint(items_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(price_list_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(tools_bp)


def _register_error_handlers(app):
    """Register custom error-page handlers."""

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        return render_template("errors/500.html"), 500


def _register_upload_route(app):
    """Serve uploaded files from the UPLOAD_FOLDER."""

    @app.route("/uploads/<path:filename>")
    @login_required
    def uploaded_file(filename):
        upload_folder = app.config.get("UPLOAD_FOLDER", "uploads")
        response = send_from_directory(upload_folder, filename)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response


def _register_context_processors(app):
    """Register template context processors."""

    @app.context_processor
    def inject_company_branding():
        """Make company_name, company_logo_url, and company_invoice_logo_url
        available in all templates."""
        try:
            from app.services import config_service

            company_name = config_service.get_config("company.name") or "Dive Service Management"

            company_logo_url = _resolve_logo_url(app, "company.logo_path")
            company_invoice_logo_url = _resolve_logo_url(app, "company.invoice_logo_path")
        except Exception:
            # During app startup or if DB isn't ready yet
            company_name = "Dive Service Management"
            company_logo_url = None
            company_invoice_logo_url = None

        return {
            "company_name": company_name,
            "company_logo_url": company_logo_url,
            "company_invoice_logo_url": company_invoice_logo_url,
        }


def _resolve_logo_url(app, config_key):
    """Return a URL path for a logo config key, or None if not configured."""
    from app.services import config_service

    rel_path = config_service.get_config(config_key)
    if not rel_path or ".." in rel_path or rel_path.startswith("/"):
        return None
    upload_folder = app.config.get("UPLOAD_FOLDER", "")
    abs_path = os.path.join(upload_folder, rel_path)
    if os.path.isfile(abs_path):
        return f"/uploads/{rel_path}"
    return None


def _register_cli(app):
    """Register custom Flask CLI commands."""
    from app.cli import register_cli_commands

    register_cli_commands(app)

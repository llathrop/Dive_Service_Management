"""Seed database with default data.

Usage::

    flask seed-db
"""

import click
from flask import current_app
from flask.cli import with_appcontext
from flask_security import SQLAlchemyUserDatastore, hash_password

from app.extensions import db
from app.models.price_list import PriceListCategory
from app.models.user import Role, User


# Default roles for the application
DEFAULT_ROLES = [
    {
        "name": "admin",
        "description": "Full system access",
    },
    {
        "name": "technician",
        "description": "Create/edit data, manage orders",
    },
    {
        "name": "viewer",
        "description": "Read-only access",
    },
]


@click.command("seed-db")
@with_appcontext
def seed_db():
    """Seed the database with default roles and configuration.

    This command is idempotent -- running it multiple times will not
    create duplicate records.
    """
    click.echo("Seeding database...")

    _seed_roles()
    _seed_price_list_categories()
    _seed_demo_users()
    _seed_system_config()

    click.echo("Database seeding complete.")


def _seed_roles():
    """Create default roles if they do not already exist."""
    created_count = 0

    for role_data in DEFAULT_ROLES:
        existing = Role.query.filter_by(name=role_data["name"]).first()
        if existing is None:
            role = Role(**role_data)
            db.session.add(role)
            created_count += 1
            click.echo(f"  Created role: {role_data['name']}")
        else:
            click.echo(f"  Role already exists: {role_data['name']} (skipped)")

    if created_count > 0:
        db.session.commit()
        click.echo(f"  {created_count} role(s) created.")
    else:
        click.echo("  All roles already exist. Nothing to do.")


def _seed_price_list_categories():
    """Create default price list categories if they do not already exist."""
    default_categories = [
        {"name": "Drysuit Repairs", "sort_order": 1},
        {"name": "Seal Replacement", "sort_order": 2},
        {"name": "Zipper Service", "sort_order": 3},
        {"name": "Valve Service", "sort_order": 4},
        {"name": "Testing & Inspection", "sort_order": 5},
        {"name": "General Service", "sort_order": 10},
    ]

    created_count = 0
    for cat_data in default_categories:
        existing = PriceListCategory.query.filter_by(name=cat_data["name"]).first()
        if existing is None:
            category = PriceListCategory(**cat_data)
            db.session.add(category)
            created_count += 1
            click.echo(f"  Created price list category: {cat_data['name']}")
        else:
            click.echo(f"  Price list category already exists: {cat_data['name']} (skipped)")

    if created_count > 0:
        db.session.commit()
        click.echo(f"  {created_count} price list category(ies) created.")
    else:
        click.echo("  All price list categories already exist. Nothing to do.")


def _seed_demo_users():
    """Create demo users with known passwords if they do not already exist."""
    if not current_app.config.get("DEBUG") and not current_app.config.get("TESTING"):
        click.echo("  Skipping demo users (not in DEBUG or TESTING mode).")
        click.echo("  Use 'flask create-admin' to create an admin account.")
        return

    user_datastore = SQLAlchemyUserDatastore(db, User, Role)

    demo_users = [
        {
            "email": "admin@example.com",
            "password": "admin123",
            "first_name": "Admin",
            "last_name": "User",
            "role": "admin",
        },
        {
            "email": "tech@example.com",
            "password": "tech123",
            "first_name": "Jane",
            "last_name": "Technician",
            "role": "technician",
        },
        {
            "email": "viewer@example.com",
            "password": "viewer123",
            "first_name": "View",
            "last_name": "Only",
            "role": "viewer",
        },
    ]

    created_count = 0
    for user_data in demo_users:
        existing = User.query.filter_by(email=user_data["email"]).first()
        if existing is None:
            user = user_datastore.create_user(
                email=user_data["email"],
                password=hash_password(user_data["password"]),
                first_name=user_data["first_name"],
                last_name=user_data["last_name"],
            )
            user_datastore.add_role_to_user(user, user_data["role"])
            created_count += 1
            click.echo(f"  Created demo user: {user_data['email']} ({user_data['role']})")
        else:
            click.echo(f"  Demo user already exists: {user_data['email']} (skipped)")

    if created_count > 0:
        db.session.commit()
        click.echo(f"  {created_count} demo user(s) created.")
    else:
        click.echo("  All demo users already exist. Nothing to do.")


def _seed_system_config():
    """Seed default system_config entries.

    Creates one row per config key if it does not already exist.
    Existing rows are never overwritten so that admin edits persist.
    """
    from app.models.system_config import SystemConfig

    defaults = [
        # --- Company ---
        ("company.name", "Dive Service Management", "string", "company", "Company name displayed in header and invoices"),
        ("company.address", "", "string", "company", "Company street address"),
        ("company.phone", "", "string", "company", "Company phone number"),
        ("company.email", "", "string", "company", "Company contact email"),
        ("company.logo_path", "", "string", "company", "Path to uploaded header logo file"),
        ("company.invoice_logo_path", "", "string", "company", "Path to uploaded invoice logo file (falls back to header logo)"),
        ("company.website", "", "string", "company", "Company website URL"),
        # --- Invoice ---
        ("invoice.prefix", "INV", "string", "invoice", "Invoice number prefix"),
        ("invoice.next_number", "1", "integer", "invoice", "Next invoice sequential number"),
        ("invoice.default_terms", "Net 30", "string", "invoice", "Default payment terms text"),
        ("invoice.default_due_days", "30", "integer", "invoice", "Days until invoice is due"),
        ("invoice.footer_text", "", "string", "invoice", "Text printed at bottom of invoices"),
        # --- Tax ---
        ("tax.default_rate", "0.0000", "float", "tax", "Default tax rate as decimal (e.g. 0.0825 = 8.25%)"),
        ("tax.label", "Sales Tax", "string", "tax", "Tax label on invoices"),
        # --- Service ---
        ("service.order_prefix", "SO", "string", "service", "Order number prefix"),
        ("service.next_order_number", "1", "integer", "service", "Next order sequential number"),
        ("service.default_labor_rate", "75.00", "float", "service", "Default hourly labor rate"),
        ("service.rush_fee_default", "50.00", "float", "service", "Default rush fee"),
        # --- Notification ---
        ("notification.low_stock_check_hours", "6", "integer", "notification", "Hours between low stock checks"),
        ("notification.overdue_check_time", "08:00", "string", "notification", "Time of day for overdue invoice checks"),
        ("notification.retention_days", "90", "integer", "notification", "Days to keep notifications before cleanup"),
        ("notification.order_due_warning_days", "2", "integer", "notification", "Days before due date to warn"),
        # --- Email ---
        ("email.enabled", "false", "boolean", "email", "Master toggle for email notifications"),
        ("email.smtp_server", "", "string", "email", "SMTP server hostname"),
        ("email.smtp_port", "587", "integer", "email", "SMTP server port"),
        ("email.smtp_use_tls", "true", "boolean", "email", "Use TLS for SMTP connection"),
        ("email.smtp_username", "", "string", "email", "SMTP authentication username"),
        ("email.smtp_password", "", "string", "email", "SMTP authentication password"),
        ("email.from_address", "", "string", "email", "Sender email address"),
        ("email.from_name", "", "string", "email", "Sender display name"),
        # --- Display ---
        ("display.date_format", "%Y-%m-%d", "string", "display", "Date display format"),
        ("display.currency_symbol", "$", "string", "display", "Currency symbol"),
        ("display.currency_code", "USD", "string", "display", "ISO currency code"),
        ("display.pagination_size", "25", "integer", "display", "Default rows per page"),
        # --- Security ---
        ("security.password_min_length", "8", "integer", "security", "Minimum password length"),
        ("security.lockout_attempts", "5", "integer", "security", "Failed login attempts before lockout"),
        ("security.lockout_duration_minutes", "15", "integer", "security", "Account lockout duration in minutes"),
        ("security.session_lifetime_hours", "24", "integer", "security", "Session lifetime in hours"),
    ]

    created_count = 0
    for key, value, config_type, category, description in defaults:
        existing = SystemConfig.query.filter_by(config_key=key).first()
        if existing is None:
            entry = SystemConfig(
                config_key=key,
                config_value=value,
                config_type=config_type,
                category=category,
                description=description,
            )
            db.session.add(entry)
            created_count += 1

    if created_count > 0:
        db.session.commit()
        click.echo(f"  {created_count} system config entries created.")
    else:
        click.echo("  All system config entries already exist. Nothing to do.")

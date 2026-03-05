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

    The SystemConfig model does not exist yet (Phase 2+).  For now this
    is a placeholder that simply prints a message.
    """
    click.echo("  System config seeding: skipped (SystemConfig model not yet implemented).")

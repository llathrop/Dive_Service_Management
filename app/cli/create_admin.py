"""Create an admin user from the command line.

Usage::

    flask create-admin --username admin --email admin@example.com --password secret

All options can also be entered interactively if omitted.
"""

import click
from flask import current_app
from flask.cli import with_appcontext
from flask_security import SQLAlchemyUserDatastore, hash_password

from app.extensions import db
from app.models.user import Role, User


@click.command("create-admin")
@click.option("--username", prompt=True, help="Admin username")
@click.option("--email", prompt=True, help="Admin email address")
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help="Admin password",
)
@click.option("--first-name", default="Admin", help="First name (default: Admin)")
@click.option("--last-name", default="User", help="Last name (default: User)")
@with_appcontext
def create_admin(username, email, password, first_name, last_name):
    """Create a user with the admin role.

    If a user with the given username or email already exists, the command
    prints a warning and exits without changes.  If the 'admin' role does
    not exist, it is created automatically.
    """
    # Check for existing user
    existing = User.query.filter(
        (User.username == username) | (User.email == email)
    ).first()

    if existing is not None:
        click.echo(
            f"A user with username '{existing.username}' or email "
            f"'{existing.email}' already exists. Skipping."
        )
        return

    # Ensure admin role exists
    admin_role = Role.query.filter_by(name="admin").first()
    if admin_role is None:
        admin_role = Role(name="admin", description="Full system access")
        db.session.add(admin_role)
        db.session.flush()
        click.echo("Created 'admin' role.")

    # Use Flask-Security's datastore to create the user so that password
    # hashing and fs_uniquifier generation are handled properly.
    user_datastore = current_app.extensions["security"].datastore

    user = user_datastore.create_user(
        username=username,
        email=email,
        password=hash_password(password),
        first_name=first_name,
        last_name=last_name,
    )
    user_datastore.add_role_to_user(user, admin_role)
    db.session.commit()

    click.echo(f"Admin user '{username}' ({email}) created successfully.")

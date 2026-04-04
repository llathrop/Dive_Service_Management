"""CLI commands package.

Registers all custom Flask CLI commands with the application.
Call ``register_cli_commands(app)`` from the application factory.
"""

from app.cli.create_admin import create_admin
from app.cli.seed import seed_db
from app.cli.seed_lookups import seed_lookups_command
from app.cli.test_email import test_email


def register_cli_commands(app):
    """Register all custom CLI commands with the Flask application.

    Args:
        app: The Flask application instance.
    """
    app.cli.add_command(seed_db)
    app.cli.add_command(seed_lookups_command)
    app.cli.add_command(create_admin)
    app.cli.add_command(test_email)

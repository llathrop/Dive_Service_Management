"""CLI command to send a test email using current SMTP configuration."""

import click
from flask.cli import with_appcontext

from app.services import email_service


@click.command("test-email")
@click.argument("recipient")
@with_appcontext
def test_email(recipient):
    """Send a test email to RECIPIENT using current SMTP settings.

    Example: flask test-email admin@example.com
    """
    click.echo(f"Sending test email to {recipient}...")

    html_body = (
        "<h2>Test Email</h2>"
        "<p>This is a test email from Dive Service Management.</p>"
        "<p>If you received this, your SMTP configuration is working correctly.</p>"
    )
    text_body = (
        "Test Email\n\n"
        "This is a test email from Dive Service Management.\n"
        "If you received this, your SMTP configuration is working correctly."
    )

    success = email_service.send_email(
        to_address=recipient,
        subject="[DSM] Test Email",
        html_body=html_body,
        text_body=text_body,
    )

    if success:
        click.echo("Test email sent successfully.")
    else:
        click.echo("Failed to send test email. Check SMTP configuration and logs.", err=True)

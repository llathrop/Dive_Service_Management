"""Email service layer — send notification emails via SMTP.

Reads SMTP configuration from SystemConfig at send-time so that admin
changes take effect immediately without restarting the application.
Falls back gracefully when email is disabled or misconfigured.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app, render_template

from app.services import config_service

logger = logging.getLogger(__name__)


def _get_smtp_config():
    """Read current email settings from SystemConfig.

    Returns a dict with all SMTP connection parameters, or None if
    email is disabled.
    """
    enabled = config_service.get_config("email.enabled", False)
    if not enabled:
        return None

    server = config_service.get_config("email.smtp_server", "")
    if not server:
        return None

    return {
        "server": server,
        "port": config_service.get_config("email.smtp_port", 587),
        "use_tls": config_service.get_config("email.smtp_use_tls", True),
        "username": config_service.get_config("email.smtp_username", ""),
        "password": config_service.get_config("email.smtp_password", ""),
        "from_address": config_service.get_config("email.from_address", ""),
        "from_name": config_service.get_config("email.from_name", ""),
    }


def send_email(to_address, subject, html_body, text_body=None):
    """Send an email using the current SMTP configuration.

    Args:
        to_address: Recipient email address.
        subject: Email subject line.
        html_body: HTML content of the email.
        text_body: Optional plain-text fallback.

    Returns:
        True if the email was sent successfully, False otherwise.
    """
    config = _get_smtp_config()
    if config is None:
        logger.debug("Email sending skipped — email is disabled or not configured.")
        return False

    from_addr = config["from_address"]
    if not from_addr:
        logger.warning("Email sending skipped — no from_address configured.")
        return False

    from_name = config["from_name"] or "Dive Service Management"
    sender = f"{from_name} <{from_addr}>"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_address

    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        if config["use_tls"]:
            server = smtplib.SMTP(config["server"], config["port"], timeout=30)
            server.starttls()
        else:
            server = smtplib.SMTP(config["server"], config["port"], timeout=30)

        if config["username"] and config["password"]:
            server.login(config["username"], config["password"])

        server.sendmail(from_addr, [to_address], msg.as_string())
        server.quit()
        logger.info("Email sent to %s: %s", to_address, subject)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("Failed to send email to %s: %s", to_address, exc)
        return False


def send_notification_email(user, notification):
    """Send an email for a notification to a user.

    Args:
        user: User model instance (must have .email attribute).
        notification: Notification model instance.

    Returns:
        True if sent, False otherwise.
    """
    if not user.email:
        return False

    config = _get_smtp_config()
    if config is None:
        return False

    subject = f"[DSM] {notification.title}"

    try:
        html_body = render_template(
            "email/notification.html",
            notification=notification,
            user=user,
        )
    except Exception:
        # Fallback if template is missing or broken
        html_body = (
            f"<h2>{notification.title}</h2>"
            f"<p>{notification.message}</p>"
        )

    text_body = f"{notification.title}\n\n{notification.message}"

    return send_email(user.email, subject, html_body, text_body)

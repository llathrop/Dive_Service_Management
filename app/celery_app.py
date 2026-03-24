"""Celery application factory.

Creates a Celery instance that shares Flask's application context.
Used by the worker and beat containers.

Usage::

    celery -A app.celery_app worker --loglevel=info
    celery -A app.celery_app beat --loglevel=info
"""

from celery import Celery

from app import create_app


def make_celery(app=None):
    """Create a Celery app bound to the Flask application context."""
    if app is None:
        app = create_app()

    celery = Celery(
        app.import_name,
        broker=app.config.get("CELERY_BROKER_URL", "redis://localhost:6379/1"),
        backend=app.config.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/2"),
    )
    # Copy the Flask config without the legacy CELERY_* keys.  Celery 5 rejects
    # mixed old/new setting names when the app is finalized.
    celery.conf.update(
        {k: v for k, v in app.config.items() if not k.startswith("CELERY_")}
    )

    class ContextTask(celery.Task):
        """Wrap task execution inside the Flask app context."""

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask

    # Periodic task schedule (Celery beat)
    celery.conf.beat_schedule = {
        "check-service-reminders-daily": {
            "task": "app.tasks.reminder_tasks.check_service_reminders",
            "schedule": 86400.0,  # every 24 hours
        },
    }

    return celery


# Module-level instance so Celery CLI can discover it
celery = make_celery()

# Import task modules explicitly so worker/beat registration does not depend on
# side effects from unrelated imports in the web app.
from app.tasks import email_tasks as _email_tasks  # noqa: F401,E402
from app.tasks import reminder_tasks as _reminder_tasks  # noqa: F401,E402

_reminder_tasks.register_tasks(celery)

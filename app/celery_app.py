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
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        """Wrap task execution inside the Flask app context."""

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery


# Module-level instance so Celery CLI can discover it
celery = make_celery()

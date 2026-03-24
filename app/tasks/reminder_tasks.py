"""Recurring service reminder task registration.

The business logic lives in ``app.services.service_reminder_service`` so the
pytest suite can execute it without importing the module-level Celery app.
This module only exposes the Celery registration hook.
"""

from app.services.service_reminder_service import check_service_reminders

TASK_NAME = "app.tasks.reminder_tasks.check_service_reminders"

_celery_task = None


def register_tasks(celery):
    """Register reminder tasks against a Celery app instance."""
    global _celery_task
    _celery_task = celery.task(name=TASK_NAME)(check_service_reminders)
    return _celery_task


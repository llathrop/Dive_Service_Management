"""Audit service layer — record and query audit log entries.

Provides functions to create audit trail entries for data changes and
to query the audit log with filtering and pagination.
"""

from datetime import datetime

from sqlalchemy import and_

from app.extensions import db
from app.models.audit_log import AuditLog


AUDIT_USER_AGENT_MAX_LENGTH = 500


def log_action(
    action,
    entity_type,
    entity_id,
    user_id=None,
    field_name=None,
    old_value=None,
    new_value=None,
    ip_address=None,
    user_agent=None,
    additional_data=None,
):
    """Record an audit log entry.

    Parameters
    ----------
    action : str
        The action performed (create, update, delete, restore, login,
        logout, export, status_change).
    entity_type : str
        The type of entity affected (customer, service_order, etc.).
    entity_id : int
        The primary key of the affected entity.
    user_id : int, optional
        The user who performed the action.  None for system actions.
    field_name : str, optional
        The specific field that changed (for update actions).
    old_value : str, optional
        The previous value (as string).
    new_value : str, optional
        The new value (as string).
    ip_address : str, optional
        The IP address of the request.
    user_agent : str, optional
        The User-Agent header of the request.
    additional_data : str, optional
        Arbitrary JSON string with extra context.

    Returns
    -------
    AuditLog
        The newly created audit log entry.
    """
    if user_agent:
        user_agent = user_agent[:AUDIT_USER_AGENT_MAX_LENGTH]

    entry = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
        user_agent=user_agent,
        additional_data=additional_data,
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def get_audit_logs(
    entity_type=None,
    entity_id=None,
    user_id=None,
    action=None,
    date_from=None,
    date_to=None,
    page=1,
    per_page=50,
):
    """Query audit logs with optional filters.

    Parameters
    ----------
    entity_type : str, optional
        Filter by entity type.
    entity_id : int, optional
        Filter by entity ID.
    user_id : int, optional
        Filter by user ID.
    action : str, optional
        Filter by action type.
    date_from : datetime, optional
        Filter entries created on or after this datetime.
    date_to : datetime, optional
        Filter entries created on or before this datetime.
    page : int
        Page number (1-based).
    per_page : int
        Number of entries per page.

    Returns
    -------
    Pagination
        A SQLAlchemy pagination object with .items, .total, .pages, etc.
    """
    query = AuditLog.query

    filters = []
    if entity_type:
        filters.append(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        filters.append(AuditLog.entity_id == entity_id)
    if user_id is not None:
        filters.append(AuditLog.user_id == user_id)
    if action:
        filters.append(AuditLog.action == action)
    if date_from:
        filters.append(AuditLog.created_at >= date_from)
    if date_to:
        filters.append(AuditLog.created_at <= date_to)

    if filters:
        query = query.filter(and_(*filters))

    query = query.order_by(AuditLog.created_at.desc())

    return query.paginate(page=page, per_page=per_page, error_out=False)


def get_recent_activity(limit=20):
    """Get the most recent audit log entries.

    Parameters
    ----------
    limit : int
        Maximum number of entries to return.

    Returns
    -------
    list[AuditLog]
        The most recent audit log entries, newest first.
    """
    return (
        AuditLog.query
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )

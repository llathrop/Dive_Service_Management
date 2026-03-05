"""Reusable model mixins for common column patterns.

These mixins are designed to be composed via multiple inheritance on any
SQLAlchemy model that needs timestamps, soft-delete, or simple audit trails.

Usage::

    class Customer(TimestampMixin, SoftDeleteMixin, AuditMixin, db.Model):
        __tablename__ = "customers"
        id = db.Column(db.Integer, primary_key=True)
        ...
"""

from datetime import datetime, timezone

from app.extensions import db


def _utcnow():
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# TimestampMixin
# ---------------------------------------------------------------------------

class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` columns.

    ``created_at`` is set once on INSERT; ``updated_at`` is refreshed on
    every UPDATE.
    """

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
        onupdate=_utcnow,
    )


# ---------------------------------------------------------------------------
# SoftDeleteMixin
# ---------------------------------------------------------------------------

class SoftDeleteMixin:
    """Adds ``is_deleted`` flag and ``deleted_at`` timestamp.

    Provides a convenience class method ``not_deleted()`` that returns a
    base query filtered to non-deleted rows, and a ``soft_delete()``
    instance method to mark a record as deleted.

    Note: For production use, consider adding a default query filter or
    using SQLAlchemy events to automatically exclude soft-deleted records.
    """

    is_deleted = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    deleted_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    def soft_delete(self):
        """Mark this record as soft-deleted."""
        self.is_deleted = True
        self.deleted_at = _utcnow()

    def restore(self):
        """Restore a soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None

    @classmethod
    def not_deleted(cls):
        """Return a query filtered to non-deleted records.

        Usage::

            customers = Customer.not_deleted().filter_by(city="Portland").all()
        """
        return cls.query.filter_by(is_deleted=False)


# ---------------------------------------------------------------------------
# AuditMixin
# ---------------------------------------------------------------------------

class AuditMixin:
    """Adds a ``created_by`` foreign key pointing to ``users.id``.

    This records *who* created the row.  It uses a simple FK rather than
    attempting to auto-detect the current user (which would couple the
    model layer to the request context).  The calling code is responsible
    for setting ``created_by`` at creation time.
    """

    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )

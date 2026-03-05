"""Unit tests for model mixins (TimestampMixin, SoftDeleteMixin, AuditMixin)."""

import pytest

from app.extensions import db as _db
from app.models.mixins import AuditMixin, SoftDeleteMixin, TimestampMixin


pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Temporary test model that uses all three mixins.
# This model is only created in the test database for mixin testing.
# ---------------------------------------------------------------------------

class MixinTestModel(TimestampMixin, SoftDeleteMixin, AuditMixin, _db.Model):
    """Temporary model for testing mixins."""

    __tablename__ = "mixin_test"

    id = _db.Column(_db.Integer, primary_key=True)
    name = _db.Column(_db.String(100), nullable=False)


@pytest.fixture(autouse=True)
def create_mixin_table(app):
    """Ensure the mixin_test table exists for these tests."""
    with app.app_context():
        MixinTestModel.__table__.create(_db.engine, checkfirst=True)
    yield
    with app.app_context():
        MixinTestModel.__table__.drop(_db.engine, checkfirst=True)


def test_timestamp_mixin_created_at(app, db_session):
    """TimestampMixin sets created_at on record creation."""
    with app.app_context():
        obj = MixinTestModel(name="timestamp_test")
        db_session.add(obj)
        db_session.commit()

        assert obj.created_at is not None


def test_soft_delete_mixin(app, db_session):
    """SoftDeleteMixin.soft_delete() sets is_deleted=True and deleted_at."""
    with app.app_context():
        obj = MixinTestModel(name="soft_delete_test")
        db_session.add(obj)
        db_session.commit()

        assert obj.is_deleted is False
        assert obj.deleted_at is None

        obj.soft_delete()
        db_session.commit()

        assert obj.is_deleted is True
        assert obj.deleted_at is not None


def test_soft_delete_restore(app, db_session):
    """SoftDeleteMixin.restore() clears is_deleted and deleted_at."""
    with app.app_context():
        obj = MixinTestModel(name="restore_test")
        db_session.add(obj)
        db_session.commit()

        obj.soft_delete()
        db_session.commit()
        assert obj.is_deleted is True

        obj.restore()
        db_session.commit()
        assert obj.is_deleted is False
        assert obj.deleted_at is None


def test_not_deleted_query(app, db_session):
    """SoftDeleteMixin.not_deleted() filters out soft-deleted records."""
    with app.app_context():
        active = MixinTestModel(name="active_record")
        deleted = MixinTestModel(name="deleted_record")
        db_session.add_all([active, deleted])
        db_session.commit()

        deleted.soft_delete()
        db_session.commit()

        results = MixinTestModel.not_deleted().all()
        names = [r.name for r in results]

        assert "active_record" in names
        assert "deleted_record" not in names


def test_audit_mixin_created_by(app, db_session):
    """AuditMixin provides a created_by field that can be set."""
    with app.app_context():
        obj = MixinTestModel(name="audit_test", created_by=1)
        db_session.add(obj)
        db_session.commit()

        assert obj.created_by == 1

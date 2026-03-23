"""Tests for P2 security hardening changes.

Covers:
- Upload route path traversal defense-in-depth
- Backup download audit logging
- Data management service table stats allowlist
"""

import pytest

from app.extensions import db
from app.models.audit_log import AuditLog


class TestUploadPathTraversal:
    """Verify that the upload route rejects path traversal attempts."""

    def test_rejects_dot_dot_traversal(self, admin_client):
        """Path traversal via ../../etc/passwd should be blocked."""
        resp = admin_client.get("/uploads/../../etc/passwd")
        # Flask may normalize the path and return 404, or our guard returns 403
        assert resp.status_code in (403, 404)

    def test_rejects_encoded_traversal(self, admin_client):
        """Encoded path traversal should also be blocked."""
        resp = admin_client.get("/uploads/..%2F..%2Fetc%2Fpasswd")
        assert resp.status_code in (403, 404)

    def test_normal_filename_not_blocked(self, admin_client):
        """A normal filename should not trigger the traversal guard.

        It will 404 because the file doesn't exist, but should NOT be 403.
        """
        resp = admin_client.get("/uploads/nonexistent-photo.jpg")
        assert resp.status_code == 404


class TestBackupAuditLog:
    """Verify that downloading a backup creates an audit log entry."""

    def test_backup_creates_audit_entry(self, admin_client):
        """GET /admin/data/backup should log a download_backup action."""
        # Clear any existing audit logs
        AuditLog.query.delete()
        db.session.commit()

        resp = admin_client.get("/admin/data/backup")
        assert resp.status_code == 200

        # Verify audit log was created
        log = AuditLog.query.filter_by(action="download_backup").first()
        assert log is not None
        assert log.entity_type == "system"
        assert log.entity_id == 0


class TestTableStatsAllowlist:
    """Verify that table stats only query allowlisted tables."""

    def test_table_stats_returns_known_tables(self, app):
        """Table stats should only include tables from SQLAlchemy metadata."""
        from app.services import data_management_service

        with app.app_context():
            stats = data_management_service.get_table_stats()

        allowed = set(db.metadata.tables.keys())
        returned_tables = {s["table"] for s in stats}

        # Every returned table must be in the allowlist
        assert returned_tables.issubset(allowed), (
            f"Tables not in allowlist: {returned_tables - allowed}"
        )

    def test_table_stats_excludes_internal_tables(self, app):
        """Internal SQLite tables (sqlite_*, alembic_version) should be excluded."""
        from app.services import data_management_service

        with app.app_context():
            stats = data_management_service.get_table_stats()

        table_names = [s["table"] for s in stats]
        for name in table_names:
            assert not name.startswith("sqlite_"), f"Internal table {name} should be excluded"
            assert name != "alembic_version", "alembic_version should be excluded"

    def test_table_stats_returns_valid_counts(self, app):
        """Each table should have a non-negative row count."""
        from app.services import data_management_service

        with app.app_context():
            stats = data_management_service.get_table_stats()

        assert len(stats) > 0, "Should return at least one table"
        for entry in stats:
            assert "table" in entry
            assert "rows" in entry
            assert entry["rows"] >= 0

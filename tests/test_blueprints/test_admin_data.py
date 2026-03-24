"""Tests for admin data management routes."""

import pytest

pytestmark = pytest.mark.blueprint


class TestDataManagementPage:
    """Tests for GET /admin/data."""

    def test_requires_admin(self, logged_in_client):
        resp = logged_in_client.get("/admin/data")
        assert resp.status_code == 403

    def test_renders_for_admin(self, admin_client):
        resp = admin_client.get("/admin/data")
        assert resp.status_code == 200
        assert b"Data Management" in resp.data

    def test_shows_db_version(self, admin_client):
        resp = admin_client.get("/admin/data")
        assert resp.status_code == 200
        assert b"SQLite" in resp.data  # TestingConfig uses SQLite

    def test_shows_table_stats(self, admin_client):
        resp = admin_client.get("/admin/data")
        assert resp.status_code == 200
        assert b"users" in resp.data
        assert b"Table Statistics" in resp.data

    def test_shows_migration_status(self, admin_client):
        resp = admin_client.get("/admin/data")
        assert resp.status_code == 200
        assert b"Migration" in resp.data

    def test_shows_export_links(self, admin_client):
        resp = admin_client.get("/admin/data")
        assert resp.status_code == 200
        assert b"Export" in resp.data
        assert b"CSV" in resp.data
        assert b"XLSX" in resp.data

    def test_shows_backup_button(self, admin_client):
        resp = admin_client.get("/admin/data")
        assert resp.status_code == 200
        assert b"Download Backup" in resp.data


class TestBackupDownload:
    """Tests for GET /admin/data/backup."""

    def test_requires_admin(self, logged_in_client):
        resp = logged_in_client.get("/admin/data/backup")
        assert resp.status_code == 403

    def test_download_backup_sqlite(self, admin_client):
        """Backup download works with SQLite (test environment)."""
        resp = admin_client.get("/admin/data/backup")
        assert resp.status_code == 200
        assert "application/sql" in resp.content_type
        assert "attachment" in resp.headers.get("Content-Disposition", "")
        assert b"CREATE TABLE" in resp.data or b"BEGIN" in resp.data

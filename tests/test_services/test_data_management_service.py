"""Tests for the data_management_service module."""

import pytest

from app.services import data_management_service

pytestmark = pytest.mark.unit


class TestGetTableStats:
    """Tests for get_table_stats()."""

    def test_returns_list(self, app):
        with app.app_context():
            stats = data_management_service.get_table_stats()
            assert isinstance(stats, list)

    def test_contains_known_tables(self, app):
        with app.app_context():
            stats = data_management_service.get_table_stats()
            table_names = {s["table"] for s in stats}
            assert "users" in table_names
            assert "roles" in table_names

    def test_each_entry_has_table_and_rows(self, app):
        with app.app_context():
            stats = data_management_service.get_table_stats()
            for entry in stats:
                assert "table" in entry
                assert "rows" in entry
                assert isinstance(entry["rows"], int)


class TestGetDbVersion:
    """Tests for get_db_version()."""

    def test_returns_string(self, app):
        with app.app_context():
            version = data_management_service.get_db_version()
            assert isinstance(version, str)
            assert len(version) > 0

    def test_sqlite_version_format(self, app):
        with app.app_context():
            version = data_management_service.get_db_version()
            # TestingConfig uses SQLite
            assert "SQLite" in version


class TestGetDbSize:
    """Tests for get_db_size()."""

    def test_returns_none_for_sqlite(self, app):
        with app.app_context():
            size = data_management_service.get_db_size()
            # SQLite doesn't support size queries
            assert size is None


class TestGetMigrationStatus:
    """Tests for get_migration_status()."""

    def test_returns_dict(self, app):
        with app.app_context():
            status = data_management_service.get_migration_status()
            assert isinstance(status, dict)
            assert "current" in status


class TestCreateBackupSql:
    """Tests for create_backup_sql()."""

    def test_sqlite_backup_returns_sql(self, app):
        """SQLite in-memory backup should return valid SQL text."""
        with app.app_context():
            sql = data_management_service.create_backup_sql()
            assert isinstance(sql, str)
            assert "CREATE TABLE" in sql or "BEGIN" in sql

    def test_sqlite_backup_contains_table_definitions(self, app):
        with app.app_context():
            sql = data_management_service.create_backup_sql()
            # Should contain at least the users table
            assert "users" in sql.lower()

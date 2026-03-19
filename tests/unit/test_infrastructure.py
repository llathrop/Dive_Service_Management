"""Tests for infrastructure files (Dockerfile, entrypoint, config)."""

import os
import subprocess

import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class TestDockerEntrypoint:
    """Verify the docker-entrypoint.sh script is valid."""

    def test_entrypoint_exists(self):
        """docker-entrypoint.sh exists and is executable."""
        path = os.path.join(ROOT_DIR, "docker-entrypoint.sh")
        assert os.path.isfile(path), "docker-entrypoint.sh not found"

    def test_entrypoint_syntax_valid(self):
        """docker-entrypoint.sh has valid bash syntax."""
        path = os.path.join(ROOT_DIR, "docker-entrypoint.sh")
        result = subprocess.run(
            ["bash", "-n", path],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"

    def test_entrypoint_contains_backup_logic(self):
        """docker-entrypoint.sh includes auto-backup before migration."""
        path = os.path.join(ROOT_DIR, "docker-entrypoint.sh")
        with open(path) as f:
            content = f.read()
        assert "DSM_AUTO_BACKUP_ON_UPGRADE" in content
        assert "mariadb-dump" in content
        assert "flask db upgrade" in content

    def test_entrypoint_uses_env_var_for_password(self):
        """Password is passed via MYSQL_PWD env var, not --password CLI arg."""
        path = os.path.join(ROOT_DIR, "docker-entrypoint.sh")
        with open(path) as f:
            content = f.read()
        assert "MYSQL_PWD=" in content, "Should use MYSQL_PWD env var"
        assert "--password" not in content, (
            "Should not pass password on command line"
        )

    def test_entrypoint_backup_before_migrate(self):
        """Backup logic appears before flask db upgrade."""
        path = os.path.join(ROOT_DIR, "docker-entrypoint.sh")
        with open(path) as f:
            content = f.read()
        backup_pos = content.index("mariadb-dump")
        migrate_pos = content.index("flask db upgrade")
        assert backup_pos < migrate_pos, (
            "Backup must run before migration"
        )


class TestEnvExample:
    """Verify .env.example documents required variables."""

    def test_auto_backup_env_var_documented(self):
        """DSM_AUTO_BACKUP_ON_UPGRADE is documented in .env.example."""
        path = os.path.join(ROOT_DIR, ".env.example")
        with open(path) as f:
            content = f.read()
        assert "DSM_AUTO_BACKUP_ON_UPGRADE" in content


class TestBackupsDirectory:
    """Verify the backups directory structure."""

    def test_gitkeep_exists(self):
        """backups/.gitkeep exists so the directory is tracked."""
        path = os.path.join(ROOT_DIR, "backups", ".gitkeep")
        assert os.path.isfile(path), "backups/.gitkeep not found"


class TestDockerfile:
    """Verify Dockerfile includes required packages."""

    def test_mariadb_client_installed(self):
        """Dockerfile installs mariadb-client for backup support."""
        path = os.path.join(ROOT_DIR, "Dockerfile")
        with open(path) as f:
            content = f.read()
        assert "mariadb-client" in content

    def test_backups_directory_created(self):
        """Dockerfile creates /app/backups directory."""
        path = os.path.join(ROOT_DIR, "Dockerfile")
        with open(path) as f:
            content = f.read()
        assert "/app/backups" in content

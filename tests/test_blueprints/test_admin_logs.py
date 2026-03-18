"""Tests for the admin log viewer routes."""

import os

import pytest


class TestLogsPage:
    """Tests for GET /admin/logs."""

    def test_requires_admin_role(self, viewer_client):
        resp = viewer_client.get("/admin/logs")
        assert resp.status_code == 403

    def test_requires_login(self, client):
        resp = client.get("/admin/logs")
        # Unauthenticated users get 403 (Flask-Security with UNAUTHORIZED_VIEW=None)
        assert resp.status_code == 403

    def test_renders_for_admin(self, admin_client):
        resp = admin_client.get("/admin/logs")
        assert resp.status_code == 200
        assert b"Log Viewer" in resp.data

    def test_select_log_param(self, admin_client):
        resp = admin_client.get("/admin/logs?log=app")
        assert resp.status_code == 200
        assert b"app.log" in resp.data

    def test_select_auth_log(self, admin_client):
        resp = admin_client.get("/admin/logs?log=auth")
        assert resp.status_code == 200
        assert b"auth.log" in resp.data

    def test_invalid_log_name_handled(self, admin_client):
        resp = admin_client.get("/admin/logs?log=../../etc/passwd")
        assert resp.status_code == 200
        assert b"Invalid log name" in resp.data

    def test_line_count_param(self, admin_client):
        resp = admin_client.get("/admin/logs?log=app&lines=100")
        assert resp.status_code == 200

    def test_with_log_content(self, app, admin_client, tmp_path):
        """When a log file exists, its content is displayed."""
        log_dir = str(tmp_path)
        app.config["LOG_DIR"] = log_dir
        log_file = os.path.join(log_dir, "app.log")
        with open(log_file, "w") as f:
            f.write("2026-03-17 Test log entry\n")

        resp = admin_client.get("/admin/logs?log=app")
        assert resp.status_code == 200
        assert b"Test log entry" in resp.data


class TestLogsTail:
    """Tests for GET /admin/logs/tail (HTMX endpoint)."""

    def test_requires_admin_role(self, viewer_client):
        resp = viewer_client.get("/admin/logs/tail")
        assert resp.status_code == 403

    def test_returns_content_partial(self, admin_client):
        resp = admin_client.get("/admin/logs/tail?log=app")
        assert resp.status_code == 200
        # Should be a partial (no full HTML page structure)
        assert b"<!DOCTYPE html>" not in resp.data

    def test_invalid_log_returns_error(self, admin_client):
        resp = admin_client.get("/admin/logs/tail?log=invalid")
        assert resp.status_code == 200
        assert b"Invalid log name" in resp.data

    def test_with_content(self, app, admin_client, tmp_path):
        log_dir = str(tmp_path)
        app.config["LOG_DIR"] = log_dir
        log_file = os.path.join(log_dir, "app.log")
        with open(log_file, "w") as f:
            f.write("Tail content line\n")

        resp = admin_client.get("/admin/logs/tail?log=app")
        assert resp.status_code == 200
        assert b"Tail content line" in resp.data

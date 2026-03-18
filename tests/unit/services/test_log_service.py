"""Tests for the log service."""

import os

import pytest


class TestGetAvailableLogs:
    """Tests for get_available_logs()."""

    def test_returns_log_entries(self, app):
        from app.services import log_service

        logs = log_service.get_available_logs()
        assert isinstance(logs, list)
        assert len(logs) >= 2
        names = [entry["name"] for entry in logs]
        assert "app" in names
        assert "auth" in names

    def test_existing_log_file(self, app, tmp_path):
        """When a log file exists, metadata is populated."""
        from app.services import log_service

        # Create a temporary log directory with a file
        log_dir = str(tmp_path)
        app.config["LOG_DIR"] = log_dir
        log_file = os.path.join(log_dir, "app.log")
        with open(log_file, "w") as f:
            f.write("test log line\n")

        logs = log_service.get_available_logs()
        app_log = next(l for l in logs if l["name"] == "app")
        assert app_log["exists"] is True
        assert app_log["size"] > 0
        assert app_log["modified"] is not None

    def test_missing_log_directory(self, app):
        """When the log directory does not exist, logs show as not found."""
        from app.services import log_service

        app.config["LOG_DIR"] = "/nonexistent/path/to/logs"
        logs = log_service.get_available_logs()
        for entry in logs:
            assert entry["exists"] is False
            assert entry["size"] == 0


class TestReadLog:
    """Tests for read_log()."""

    def test_read_valid_log(self, app, tmp_path):
        from app.services import log_service

        log_dir = str(tmp_path)
        app.config["LOG_DIR"] = log_dir
        log_file = os.path.join(log_dir, "app.log")
        with open(log_file, "w") as f:
            for i in range(10):
                f.write(f"Line {i}\n")

        result = log_service.read_log("app", lines=5)
        assert result["error"] is None
        assert result["log_name"] == "app"
        assert result["total_lines"] == 10
        assert len(result["lines"]) == 5
        # Should return the last 5 lines
        assert result["lines"][0] == "Line 5"
        assert result["lines"][-1] == "Line 9"

    def test_read_empty_file(self, app, tmp_path):
        from app.services import log_service

        log_dir = str(tmp_path)
        app.config["LOG_DIR"] = log_dir
        log_file = os.path.join(log_dir, "app.log")
        with open(log_file, "w") as f:
            pass  # empty file

        result = log_service.read_log("app", lines=200)
        assert result["error"] is None
        assert result["lines"] == []
        assert result["total_lines"] == 0

    def test_line_limit_capped_at_1000(self, app, tmp_path):
        from app.services import log_service

        log_dir = str(tmp_path)
        app.config["LOG_DIR"] = log_dir
        log_file = os.path.join(log_dir, "app.log")
        with open(log_file, "w") as f:
            for i in range(1500):
                f.write(f"Line {i}\n")

        result = log_service.read_log("app", lines=2000)
        assert len(result["lines"]) == 1000
        assert result["total_lines"] == 1500

    def test_path_traversal_dotdot(self, app):
        from app.services import log_service

        result = log_service.read_log("../etc/passwd")
        assert result["error"] is not None
        assert "Invalid log name" in result["error"]

    def test_path_traversal_slash(self, app):
        from app.services import log_service

        result = log_service.read_log("/etc/passwd")
        assert result["error"] is not None
        assert "Invalid log name" in result["error"]

    def test_path_traversal_backslash(self, app):
        from app.services import log_service

        result = log_service.read_log("..\\etc\\passwd")
        assert result["error"] is not None
        assert "Invalid log name" in result["error"]

    def test_invalid_log_name(self, app):
        from app.services import log_service

        result = log_service.read_log("nonexistent")
        assert result["error"] is not None
        assert "Invalid log name" in result["error"]

    def test_missing_file_no_error(self, app):
        """A valid log name with no file on disk returns empty, no error."""
        from app.services import log_service

        app.config["LOG_DIR"] = "/nonexistent/path"
        result = log_service.read_log("app")
        assert result["error"] is None
        assert result["lines"] == []

    def test_read_with_offset(self, app, tmp_path):
        from app.services import log_service

        log_dir = str(tmp_path)
        app.config["LOG_DIR"] = log_dir
        log_file = os.path.join(log_dir, "app.log")
        with open(log_file, "w") as f:
            for i in range(20):
                f.write(f"Line {i}\n")

        result = log_service.read_log("app", lines=5, offset=5)
        assert result["error"] is None
        assert len(result["lines"]) == 5
        # Offset 5 from end means skip last 5, then take 5
        assert result["lines"][0] == "Line 10"
        assert result["lines"][-1] == "Line 14"


class TestValidateLogName:
    """Tests for _validate_log_name()."""

    def test_valid_names(self, app):
        from app.services.log_service import _validate_log_name

        assert _validate_log_name("app") is True
        assert _validate_log_name("auth") is True

    def test_invalid_names(self, app):
        from app.services.log_service import _validate_log_name

        assert _validate_log_name("") is False
        assert _validate_log_name(None) is False
        assert _validate_log_name("../secret") is False
        assert _validate_log_name("foo/bar") is False
        assert _validate_log_name("unknown") is False

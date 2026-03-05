"""Smoke tests for the /health endpoint."""

from unittest.mock import patch

import pytest
from sqlalchemy.exc import OperationalError, SQLAlchemyError


@pytest.mark.smoke
class TestHealthEndpoint:
    """Tests for the health check endpoint used by Docker."""

    def test_health_returns_200(self, client):
        """GET /health returns 200 with JSON status."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_json(self, client):
        """GET /health returns JSON with status field."""
        response = client.get("/health")
        data = response.get_json()
        assert data is not None
        assert "status" in data
        assert data["status"] == "ok"

    def test_health_includes_db_check(self, client):
        """GET /health includes a database check."""
        response = client.get("/health")
        data = response.get_json()
        assert "checks" in data
        assert "database" in data["checks"]
        assert data["checks"]["database"] == "ok"

    def test_health_returns_503_when_db_unreachable(self, client):
        """GET /health returns 503 when DB connection fails (OperationalError)."""
        with patch("app.blueprints.health.db") as mock_db:
            mock_db.session.execute.side_effect = OperationalError(
                "SELECT 1", {}, Exception("Connection refused")
            )
            mock_db.text = lambda x: x
            response = client.get("/health")

        assert response.status_code == 503
        data = response.get_json()
        assert data["status"] == "degraded"
        assert data["checks"]["database"] == "unreachable"

    def test_health_returns_503_when_db_error(self, client):
        """GET /health returns 503 when DB has a SQLAlchemy error."""
        with patch("app.blueprints.health.db") as mock_db:
            mock_db.session.execute.side_effect = SQLAlchemyError("DB error")
            mock_db.text = lambda x: x
            response = client.get("/health")

        assert response.status_code == 503
        data = response.get_json()
        assert data["status"] == "degraded"
        assert data["checks"]["database"] == "error"

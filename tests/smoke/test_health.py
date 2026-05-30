"""Smoke tests for the /health endpoint."""

from unittest.mock import patch

import pytest
from sqlalchemy.exc import OperationalError, SQLAlchemyError

pytestmark = pytest.mark.smoke


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

    def test_liveness_probe_always_returns_200(self, client):
        """GET /health/live liveness probe always returns 200 OK."""
        response = client.get("/health/live")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "alive"

    def test_readiness_probe_returns_200_when_healthy(self, client):
        """GET /health/ready readiness probe returns 200 OK when DB and Redis are healthy."""
        # Mock Redis ping to ensure it passes even if Redis is slow in test container
        with patch("redis.Redis.ping") as mock_ping:
            mock_ping.return_value = True
            response = client.get("/health/ready")
            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "ready"
            assert data["db"] == "ok"
            assert data["redis"] == "ok"

    def test_readiness_probe_fails_on_db_error(self, client):
        """GET /health/ready returns 503 when DB connection fails."""
        with patch("app.blueprints.health.db") as mock_db, patch("redis.Redis.ping") as mock_ping:
            mock_ping.return_value = True
            mock_db.session.execute.side_effect = OperationalError(
                "SELECT 1", {}, Exception("DB down")
            )
            mock_db.text = lambda x: x
            response = client.get("/health/ready")
            
        assert response.status_code == 503
        data = response.get_json()
        assert data["status"] == "not_ready"
        assert data["db"] == "error"
        assert data["redis"] == "ok"

    def test_readiness_probe_fails_on_redis_error(self, client):
        """GET /health/ready returns 503 when Redis connection fails."""
        with patch("redis.Redis.ping") as mock_ping:
            mock_ping.side_effect = Exception("Redis connection failed")
            response = client.get("/health/ready")

        assert response.status_code == 503
        data = response.get_json()
        assert data["status"] == "not_ready"
        assert data["db"] == "ok"
        assert data["redis"] == "error"

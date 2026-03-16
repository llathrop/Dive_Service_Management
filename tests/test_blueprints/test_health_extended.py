"""Tests for the extended health check endpoints.

Covers /health, /health/ready, and /health/live endpoints including
success paths and failure scenarios for DB and Redis connectivity.
"""

import pytest
from unittest.mock import patch, MagicMock

from sqlalchemy.exc import OperationalError


class TestHealthEndpoint:
    """Tests for the existing /health endpoint."""

    def test_health_returns_200(self, client):
        """GET /health returns 200 when database is reachable."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["checks"]["database"] == "ok"

    def test_health_returns_503_when_db_down(self, client, app):
        """GET /health returns 503 when database is unreachable."""
        with patch("app.blueprints.health.db") as mock_db:
            mock_db.text = MagicMock(return_value="SELECT 1")
            mock_db.session.execute.side_effect = OperationalError(
                "conn", "params", Exception("connection refused")
            )
            response = client.get("/health")
        assert response.status_code == 503
        data = response.get_json()
        assert data["status"] == "degraded"
        assert data["checks"]["database"] == "unreachable"


class TestLivenessEndpoint:
    """Tests for the /health/live liveness probe."""

    def test_liveness_returns_200(self, client):
        """GET /health/live always returns 200."""
        response = client.get("/health/live")
        assert response.status_code == 200

    def test_liveness_json_structure(self, client):
        """GET /health/live returns correct JSON structure."""
        response = client.get("/health/live")
        data = response.get_json()
        assert data == {"status": "alive"}

    def test_liveness_content_type(self, client):
        """GET /health/live returns application/json."""
        response = client.get("/health/live")
        assert response.content_type == "application/json"


class TestReadinessEndpoint:
    """Tests for the /health/ready readiness probe."""

    def test_readiness_returns_200_when_all_up(self, client):
        """GET /health/ready returns 200 when DB and Redis are reachable."""
        with patch("app.blueprints.health.redis") as mock_redis_mod:
            mock_conn = MagicMock()
            mock_redis_mod.from_url.return_value = mock_conn
            mock_conn.ping.return_value = True
            response = client.get("/health/ready")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ready"
        assert data["db"] == "ok"
        assert data["redis"] == "ok"

    def test_readiness_json_structure(self, client):
        """GET /health/ready response has required keys."""
        with patch("app.blueprints.health.redis") as mock_redis_mod:
            mock_conn = MagicMock()
            mock_redis_mod.from_url.return_value = mock_conn
            response = client.get("/health/ready")
        data = response.get_json()
        assert "status" in data
        assert "db" in data
        assert "redis" in data

    def test_readiness_503_when_db_down(self, client):
        """GET /health/ready returns 503 when DB is unreachable."""
        with patch("app.blueprints.health.db") as mock_db, \
             patch("app.blueprints.health.redis") as mock_redis_mod:
            mock_db.text = MagicMock(return_value="SELECT 1")
            mock_db.session.execute.side_effect = OperationalError(
                "conn", "params", Exception("connection refused")
            )
            mock_conn = MagicMock()
            mock_redis_mod.from_url.return_value = mock_conn
            mock_conn.ping.return_value = True
            response = client.get("/health/ready")
        assert response.status_code == 503
        data = response.get_json()
        assert data["status"] == "not_ready"
        assert data["db"] == "error"
        assert data["redis"] == "ok"

    def test_readiness_503_when_redis_down(self, client):
        """GET /health/ready returns 503 when Redis is unreachable."""
        with patch("app.blueprints.health.redis") as mock_redis_mod:
            mock_conn = MagicMock()
            mock_redis_mod.from_url.return_value = mock_conn
            mock_conn.ping.side_effect = ConnectionError("Redis down")
            response = client.get("/health/ready")
        assert response.status_code == 503
        data = response.get_json()
        assert data["status"] == "not_ready"
        assert data["db"] == "ok"
        assert data["redis"] == "error"

    def test_readiness_503_when_both_down(self, client):
        """GET /health/ready returns 503 when both DB and Redis are down."""
        with patch("app.blueprints.health.db") as mock_db, \
             patch("app.blueprints.health.redis") as mock_redis_mod:
            mock_db.text = MagicMock(return_value="SELECT 1")
            mock_db.session.execute.side_effect = OperationalError(
                "conn", "params", Exception("connection refused")
            )
            mock_conn = MagicMock()
            mock_redis_mod.from_url.return_value = mock_conn
            mock_conn.ping.side_effect = ConnectionError("Redis down")
            response = client.get("/health/ready")
        assert response.status_code == 503
        data = response.get_json()
        assert data["status"] == "not_ready"
        assert data["db"] == "error"
        assert data["redis"] == "error"

    def test_readiness_content_type(self, client):
        """GET /health/ready returns application/json."""
        with patch("app.blueprints.health.redis") as mock_redis_mod:
            mock_conn = MagicMock()
            mock_redis_mod.from_url.return_value = mock_conn
            response = client.get("/health/ready")
        assert response.content_type == "application/json"

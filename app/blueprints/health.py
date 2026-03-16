"""Health check blueprint.

Provides health, readiness, and liveness endpoints used by Docker health
checks, Kubernetes probes, and monitoring tools.

Endpoints:
    GET /health       — DB connectivity check (legacy, kept for compatibility)
    GET /health/ready — Readiness probe: checks DB and Redis
    GET /health/live  — Liveness probe: always returns 200
"""

import redis
from flask import Blueprint, current_app, jsonify
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.extensions import db

health_bp = Blueprint("health", __name__)


@health_bp.route("/health")
def health():
    """Return application health status.

    Checks database connectivity and returns a JSON response.
    Used by Docker HEALTHCHECK and load balancers.
    """
    status = {"status": "ok", "checks": {}}

    # Database connectivity check
    try:
        db.session.execute(db.text("SELECT 1"))
        status["checks"]["database"] = "ok"
    except OperationalError:
        status["checks"]["database"] = "unreachable"
        status["status"] = "degraded"
    except SQLAlchemyError:
        status["checks"]["database"] = "error"
        status["status"] = "degraded"

    http_status = 200 if status["status"] == "ok" else 503
    return jsonify(status), http_status


@health_bp.route("/health/ready")
def readiness():
    """Readiness probe for Kubernetes and cloud load balancers.

    Checks both database and Redis connectivity. Returns 200 when all
    dependencies are reachable, 503 otherwise.
    """
    result = {"status": "ready", "db": "ok", "redis": "ok"}
    is_ready = True

    # Database check
    try:
        db.session.execute(db.text("SELECT 1"))
    except (OperationalError, SQLAlchemyError):
        result["db"] = "error"
        is_ready = False

    # Redis check
    try:
        redis_url = current_app.config.get("REDIS_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
        r.ping()
    except Exception:
        result["redis"] = "error"
        is_ready = False

    if not is_ready:
        result["status"] = "not_ready"

    http_status = 200 if is_ready else 503
    return jsonify(result), http_status


@health_bp.route("/health/live")
def liveness():
    """Liveness probe for Kubernetes and cloud orchestrators.

    Always returns 200 to indicate the process is alive. No dependency
    checks — if this endpoint stops responding, the process is hung and
    should be restarted.
    """
    return jsonify({"status": "alive"}), 200

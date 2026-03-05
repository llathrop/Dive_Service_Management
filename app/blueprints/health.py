"""Health check blueprint.

Provides a simple ``/health`` endpoint used by Docker health checks
and monitoring tools.
"""

from flask import Blueprint, jsonify
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

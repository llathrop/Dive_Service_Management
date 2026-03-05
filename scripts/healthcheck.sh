#!/usr/bin/env bash
# =============================================================================
# Dive Service Management - Container Health Check
# =============================================================================
# Called by Docker HEALTHCHECK to verify the application is responding.
# Returns exit code 0 if healthy, 1 otherwise.
# =============================================================================

set -euo pipefail

PORT="${DSM_PORT:-8080}"
URL="http://localhost:${PORT}/health"
TIMEOUT=5

if curl -sf --max-time "${TIMEOUT}" "${URL}" > /dev/null 2>&1; then
    exit 0
else
    echo "Health check failed: ${URL}" >&2
    exit 1
fi

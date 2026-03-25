#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

"${ROOT_DIR}/scripts/test-compose.sh" -f docker-compose.test.yml run --build --rm test python -m pytest \
  tests/smoke/ \
  tests/test_blueprints/test_health_extended.py \
  tests/validation/test_full_workflow.py \
  -x -v

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

docker compose -f docker-compose.test.yml run --rm test python -m pytest \
  tests/smoke/ \
  tests/test_blueprints/test_health_extended.py \
  tests/validation/test_full_workflow.py \
  -x -v

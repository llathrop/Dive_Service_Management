#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/docker/test-resources.env"

if [[ ! -f "${ENV_FILE}" ]]; then
    "${ROOT_DIR}/scripts/configure_test_resources.sh"
fi

exec env \
    -u DSM_TEST_DOCKER_CPUS \
    -u DSM_TEST_DOCKER_MEMORY \
    -u DSM_TEST_DOCKER_PIDS_LIMIT \
    docker compose --env-file "${ENV_FILE}" "$@"

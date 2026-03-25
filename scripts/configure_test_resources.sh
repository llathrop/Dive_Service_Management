#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_FILE="${ROOT_DIR}/docker/test-resources.env"

detect_cpu_count() {
    if command -v nproc >/dev/null 2>&1; then
        nproc
        return
    fi

    if command -v sysctl >/dev/null 2>&1; then
        sysctl -n hw.ncpu
        return
    fi

    echo 2
}

detect_total_mem_mb() {
    if [[ -r /proc/meminfo ]]; then
        awk '/MemTotal/ {printf "%d\n", $2 / 1024}' /proc/meminfo
        return
    fi

    if command -v sysctl >/dev/null 2>&1; then
        sysctl -n hw.memsize | awk '{printf "%d\n", $1 / 1024 / 1024}'
        return
    fi

    echo 4096
}

TOTAL_CPUS="$(detect_cpu_count)"
TOTAL_MEM_MB="$(detect_total_mem_mb)"

CPU_LIMIT=$(( TOTAL_CPUS / 2 ))
if (( CPU_LIMIT < 1 )); then
    CPU_LIMIT=1
fi

MEMORY_LIMIT_MB=$(( TOTAL_MEM_MB / 4 ))
if (( MEMORY_LIMIT_MB < 2048 )); then
    MEMORY_LIMIT_MB=2048
fi
if (( MEMORY_LIMIT_MB > 6144 )); then
    MEMORY_LIMIT_MB=6144
fi

cat > "${OUTPUT_FILE}" <<EOF
# Docker test-container resource caps.
# Regenerate these defaults from the current host with:
#   ./scripts/configure_test_resources.sh
#
# Manual edits are safe. Docker Compose reads this file via:
#   --env-file docker/test-resources.env

DSM_TEST_DOCKER_CPUS=${CPU_LIMIT}
DSM_TEST_DOCKER_MEMORY=${MEMORY_LIMIT_MB}m
DSM_TEST_DOCKER_PIDS_LIMIT=512
EOF

printf 'Wrote %s\n' "${OUTPUT_FILE}"
printf '  CPUs: %s (host=%s)\n' "${CPU_LIMIT}" "${TOTAL_CPUS}"
printf '  Memory: %sm (host=%s MB)\n' "${MEMORY_LIMIT_MB}" "${TOTAL_MEM_MB}"
printf '  PIDs: %s\n' "512"

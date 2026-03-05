#!/usr/bin/env bash
# =============================================================================
# Dive Service Management - Database Backup
# =============================================================================
# Creates a compressed MariaDB dump in the backups/ directory.
#
# Usage:
#   ./scripts/backup.sh                  # Timestamped backup
#   ./scripts/backup.sh custom_name      # Named backup
#
# Output: backups/dsm_YYYYMMDD_HHMMSS.sql.gz (or custom name)
# =============================================================================

set -euo pipefail

# Resolve project root (one level up from scripts/)
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${PROJECT_DIR}/backups"

# Load environment variables
if [[ -f "${PROJECT_DIR}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${PROJECT_DIR}/.env"
    set +a
fi

# Database credentials from environment (with defaults matching .env.example)
DB_NAME="${MARIADB_DATABASE:-dsm}"
DB_USER="${MARIADB_USER:-dsm}"
DB_PASSWORD="${MARIADB_PASSWORD:-}"
DB_CONTAINER="dsm-db"

# Backup filename
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
if [[ -n "${1:-}" ]]; then
    BACKUP_FILE="${BACKUP_DIR}/${1}.sql.gz"
else
    BACKUP_FILE="${BACKUP_DIR}/dsm_${TIMESTAMP}.sql.gz"
fi

# Ensure backup directory exists
mkdir -p "${BACKUP_DIR}"

echo "=== Dive Service Management - Database Backup ==="
echo "Database:   ${DB_NAME}"
echo "Container:  ${DB_CONTAINER}"
echo "Output:     ${BACKUP_FILE}"
echo ""

# Verify the database container is running
if ! docker compose -f "${PROJECT_DIR}/docker-compose.yml" ps --status running "${DB_CONTAINER}" 2>/dev/null | grep -q "${DB_CONTAINER}"; then
    # Try without container name filter (older docker compose versions)
    if ! docker ps --filter "name=${DB_CONTAINER}" --filter "status=running" -q | grep -q .; then
        echo "ERROR: Database container '${DB_CONTAINER}' is not running." >&2
        echo "Start it with: docker compose up -d db" >&2
        exit 1
    fi
fi

# Run mysqldump inside the container and compress
echo "Starting backup..."
docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T db \
    mysqldump \
        --user="${DB_USER}" \
        --password="${DB_PASSWORD}" \
        --single-transaction \
        --routines \
        --triggers \
        --quick \
        --lock-tables=false \
        "${DB_NAME}" \
    | gzip > "${BACKUP_FILE}"

# Verify the backup file was created and has content
if [[ -s "${BACKUP_FILE}" ]]; then
    FILESIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    echo ""
    echo "Backup completed successfully."
    echo "File: ${BACKUP_FILE} (${FILESIZE})"

    # Clean up old backups (keep last 10)
    BACKUP_COUNT=$(find "${BACKUP_DIR}" -name "dsm_*.sql.gz" -type f | wc -l)
    if [[ "${BACKUP_COUNT}" -gt 10 ]]; then
        echo ""
        echo "Cleaning old backups (keeping last 10)..."
        find "${BACKUP_DIR}" -name "dsm_*.sql.gz" -type f | sort | head -n -10 | xargs rm -f
        echo "Done."
    fi
else
    echo "ERROR: Backup file is empty or was not created." >&2
    rm -f "${BACKUP_FILE}"
    exit 1
fi

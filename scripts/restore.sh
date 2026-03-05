#!/usr/bin/env bash
# =============================================================================
# Dive Service Management - Database Restore
# =============================================================================
# Restores a MariaDB dump from a backup file.
#
# Usage:
#   ./scripts/restore.sh backups/dsm_20260303_120000.sql.gz
#   ./scripts/restore.sh backups/custom_name.sql.gz
#
# WARNING: This will DROP and recreate the database!
# =============================================================================

set -euo pipefail

# Resolve project root (one level up from scripts/)
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Load environment variables
if [[ -f "${PROJECT_DIR}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${PROJECT_DIR}/.env"
    set +a
fi

# Database credentials from environment
DB_NAME="${MARIADB_DATABASE:-dsm}"
DB_USER="${MARIADB_USER:-dsm}"
DB_PASSWORD="${MARIADB_PASSWORD:-}"
DB_ROOT_PASSWORD="${MARIADB_ROOT_PASSWORD:-}"
DB_CONTAINER="dsm-db"

# Validate arguments
BACKUP_FILE="${1:-}"
if [[ -z "${BACKUP_FILE}" ]]; then
    echo "Usage: $0 <backup-file>" >&2
    echo "" >&2
    echo "Available backups:" >&2
    if [[ -d "${PROJECT_DIR}/backups" ]]; then
        ls -lh "${PROJECT_DIR}/backups/"*.sql.gz 2>/dev/null || echo "  (no backups found)" >&2
    else
        echo "  (backups/ directory does not exist)" >&2
    fi
    exit 1
fi

# Resolve relative paths
if [[ "${BACKUP_FILE}" != /* ]]; then
    BACKUP_FILE="${PROJECT_DIR}/${BACKUP_FILE}"
fi

# Verify backup file exists
if [[ ! -f "${BACKUP_FILE}" ]]; then
    echo "ERROR: Backup file not found: ${BACKUP_FILE}" >&2
    exit 1
fi

echo "=== Dive Service Management - Database Restore ==="
echo "Database:   ${DB_NAME}"
echo "Container:  ${DB_CONTAINER}"
echo "Backup:     ${BACKUP_FILE}"
echo ""

# Confirm (unless running non-interactively)
if [[ -t 0 ]]; then
    echo "WARNING: This will DROP the '${DB_NAME}' database and replace it with"
    echo "the contents of the backup file. This action cannot be undone."
    echo ""
    read -r -p "Are you sure you want to continue? (yes/no): " CONFIRM
    if [[ "${CONFIRM}" != "yes" ]]; then
        echo "Restore cancelled."
        exit 0
    fi
fi

# Verify the database container is running
if ! docker ps --filter "name=${DB_CONTAINER}" --filter "status=running" -q | grep -q .; then
    echo "ERROR: Database container '${DB_CONTAINER}' is not running." >&2
    echo "Start it with: docker compose up -d db" >&2
    exit 1
fi

echo ""
echo "Step 1/3: Dropping and recreating database..."
docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T db \
    mysql \
        --user=root \
        --password="${DB_ROOT_PASSWORD}" \
        -e "DROP DATABASE IF EXISTS \`${DB_NAME}\`; CREATE DATABASE \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'%'; FLUSH PRIVILEGES;"

echo "Step 2/3: Restoring from backup..."
if [[ "${BACKUP_FILE}" == *.gz ]]; then
    gunzip -c "${BACKUP_FILE}" | docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T db \
        mysql \
            --user="${DB_USER}" \
            --password="${DB_PASSWORD}" \
            "${DB_NAME}"
else
    docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T db \
        mysql \
            --user="${DB_USER}" \
            --password="${DB_PASSWORD}" \
            "${DB_NAME}" < "${BACKUP_FILE}"
fi

echo "Step 3/3: Verifying restore..."
TABLE_COUNT=$(docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T db \
    mysql \
        --user="${DB_USER}" \
        --password="${DB_PASSWORD}" \
        --skip-column-names \
        -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${DB_NAME}';" \
    2>/dev/null | tr -d '[:space:]')

echo ""
echo "Restore completed successfully."
echo "Tables in database: ${TABLE_COUNT}"
echo ""
echo "NOTE: You may want to run migrations to ensure the schema is up to date:"
echo "  docker compose exec web flask db upgrade"

#!/bin/bash
set -e

# Only run migrations and seeding for the web/gunicorn process,
# not for celery workers or beat schedulers.
if [[ "$1" == "gunicorn" ]]; then

    # Auto-backup before migration (if enabled and migrations pending)
    if [[ "${DSM_AUTO_BACKUP_ON_UPGRADE:-true}" == "true" ]]; then
        CURRENT=$(flask db current 2>/dev/null | head -1 | awk '{print $1}')
        HEAD=$(flask db heads 2>/dev/null | head -1 | awk '{print $1}')
        if [[ -n "$CURRENT" && -n "$HEAD" && "$CURRENT" != "$HEAD" ]]; then
            TIMESTAMP=$(date +%Y%m%d_%H%M%S)
            BACKUP_FILE="/app/backups/dsm_pre_migrate_${TIMESTAMP}.sql.gz"
            echo "Pending migrations detected. Creating backup: ${BACKUP_FILE}"
            if MYSQL_PWD="${MARIADB_PASSWORD}" mariadb-dump \
                --host="${MARIADB_HOST:-db}" --user="${MARIADB_USER}" \
                --single-transaction --routines --triggers "${MARIADB_DATABASE:-dsm}" \
                2>/dev/null | gzip > "${BACKUP_FILE}"; then
                echo "Backup created successfully: ${BACKUP_FILE}"
            else
                echo "WARNING: Pre-migration backup failed. Continuing with upgrade..."
                rm -f "${BACKUP_FILE}"
            fi
        else
            echo "No pending migrations. Skipping backup."
        fi
    fi

    echo "Running database migrations..."
    if ! flask db upgrade 2>&1; then
        if [[ "$DSM_ENV" == "production" ]]; then
            echo "FATAL: Database migration failed in production. Refusing to start."
            exit 1
        else
            echo "WARNING: Database migration failed. The app may not work correctly."
            echo "Check the migration history and database state."
        fi
    fi

    echo "Seeding database defaults..."
    if ! flask seed-db 2>&1; then
        if [[ "$DSM_ENV" == "production" ]]; then
            echo "FATAL: Database seeding failed in production. Refusing to start."
            exit 1
        else
            echo "WARNING: Database seeding failed. Roles or defaults may be missing."
        fi
    fi
fi

echo "Starting: $@"
exec "$@"

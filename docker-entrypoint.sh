#!/bin/bash
set -e

# Only run migrations and seeding for the web/gunicorn process,
# not for celery workers or beat schedulers.
if [[ "$1" == "gunicorn" ]]; then
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

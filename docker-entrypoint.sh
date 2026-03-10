#!/bin/bash
set -e

# Only run migrations and seeding for the web/gunicorn process,
# not for celery workers or beat schedulers.
if [[ "$1" == "gunicorn" ]]; then
    echo "Running database migrations..."
    flask db upgrade 2>&1 || {
        echo "WARNING: Database migration failed. The app may not work correctly."
        echo "Check the migration history and database state."
    }

    echo "Seeding database defaults..."
    flask seed-db 2>&1 || {
        echo "WARNING: Database seeding failed. Roles or defaults may be missing."
    }
fi

echo "Starting: $@"
exec "$@"

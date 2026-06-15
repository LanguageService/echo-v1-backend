#!/bin/sh

# Exit immediately if a command exits with a non-zero status
set -e

# Wait for PostgreSQL to start up if we are using it
if [ -n "$DATABASE_HOST" ]; then
    echo "Waiting for database at $DATABASE_HOST:$DATABASE_PORT..."
    until pg_isready -h "$DATABASE_HOST" -p "${DATABASE_PORT:-5432}" -U "${DATABASE_USER:-postgres}"; do
        echo "Database is unavailable - sleeping"
        sleep 1
    done
    echo "Database is up - continuing"
fi

# Run Django database migrations
echo "Running migrations..."
python manage.py migrate --noinput

# Seed pricing data
echo "Seeding pricing data..."
python manage.py seed_pricing || echo "Seed pricing failed, continuing..."

# Populate language and cloud configs
echo "Populating languages..."
python manage.py populate_languages || echo "Populate languages failed, continuing..."

echo "Populating cloud configs..."
python manage.py populate_cloud_configs || echo "Populate cloud configs failed, continuing..."

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Execute the command passed to the script (e.g. Daphne, celery worker, etc.)
exec "$@"

#!/bin/bash
# entrypoint.sh

# Exit the script if any command fails
set -e

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate --noinput

# Start Gunicorn server
echo "Starting Gunicorn server..."
exec gunicorn core.wsgi:application --bind 0.0.0.0:8000
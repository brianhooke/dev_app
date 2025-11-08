#!/bin/bash
set -e

echo "Running migrations..."
python manage.py migrate --noinput || echo "Migrations failed, continuing..."

echo "Starting gunicorn..."
exec gunicorn dev_app.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120 --log-level debug

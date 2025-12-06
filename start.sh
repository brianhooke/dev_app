#!/bin/bash
set -e

echo "=== Starting Django Application ==="
echo "DJANGO_SETTINGS_MODULE: ${DJANGO_SETTINGS_MODULE:-NOT SET}"
echo "RDS_HOSTNAME: ${RDS_HOSTNAME:-NOT SET}"
echo "AWS_STORAGE_BUCKET_NAME: ${AWS_STORAGE_BUCKET_NAME:-NOT SET}"
echo "AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID:+SET}"
echo "AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY:+SET}"
echo "===================================="

echo "Collecting static files to S3..."
python manage.py collectstatic --noinput || echo "Collectstatic failed, continuing..."

echo "Running migrations..."
python manage.py migrate --noinput || echo "Migrations failed, continuing..."

echo "Creating admin superuser..."
python manage.py create_admin || echo "Admin creation failed, continuing..."

echo "Importing Xero data from environment..."
python manage.py import_xero_from_env || echo "Xero import failed, continuing..."

echo "Starting gunicorn on port 80..."
exec gunicorn dev_app.wsgi:application --bind 0.0.0.0:80 --workers 3 --timeout 120 --access-logfile - --error-logfile - --log-level info

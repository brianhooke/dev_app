#!/bin/bash
set -e

# Force production settings in AWS deployment
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-dev_app.settings.production_aws}"

echo "=== Starting Django Application ==="
echo "DJANGO_SETTINGS_MODULE: ${DJANGO_SETTINGS_MODULE}"
echo "RDS_HOSTNAME: ${RDS_HOSTNAME:-NOT SET}"
echo "AWS_STORAGE_BUCKET_NAME: ${AWS_STORAGE_BUCKET_NAME:-NOT SET}"
echo "AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID:+SET}"
echo "AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY:+SET}"
echo "===================================="

echo "Collecting static files to S3..."
python manage.py collectstatic --noinput || echo "Collectstatic failed, continuing..."

echo "Creating pre-migration database backup..."
BACKUP_FILE="/tmp/db_backup_$(date +%Y%m%d_%H%M%S).json"
python manage.py dumpdata core --natural-foreign --natural-primary -o "$BACKUP_FILE" && \
    echo "Backup created: $BACKUP_FILE" && \
    aws s3 cp "$BACKUP_FILE" "s3://${AWS_STORAGE_BUCKET_NAME}/backups/$(basename $BACKUP_FILE)" && \
    echo "Backup uploaded to S3" || \
    echo "Backup failed, continuing anyway..."

echo "Running migrations..."
python manage.py migrate --noinput || echo "Migrations failed, continuing..."

echo "Seeding public holidays..."
python manage.py seed_public_holidays || echo "Public holidays seeding failed, continuing..."

echo "Creating admin superuser..."
python manage.py create_admin || echo "Admin creation failed, continuing..."

echo "Starting gunicorn on port 80..."
exec gunicorn dev_app.wsgi:application --bind 0.0.0.0:80 --workers 3 --timeout 120 --access-logfile - --error-logfile - --log-level info

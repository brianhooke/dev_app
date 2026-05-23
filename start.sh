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

echo "Collecting static files..."
# Static collection is non-fatal: a corrupted asset shouldn't take the site
# down. Logs surface failures so they can be triaged.
python manage.py collectstatic --noinput || echo "Collectstatic failed; serving with stale staticfiles."

echo "Creating pre-migration database backup..."
BACKUP_FILE="/tmp/db_backup_$(date +%Y%m%d_%H%M%S).json"
# Backup is best-effort: a backup failure shouldn't prevent rollout. If you
# need stricter guarantees move this to a scheduled job that runs against
# RDS rather than during container start.
if python manage.py dumpdata core --natural-foreign --natural-primary -o "$BACKUP_FILE"; then
    if [ -n "${AWS_STORAGE_BUCKET_NAME:-}" ]; then
        aws s3 cp "$BACKUP_FILE" "s3://${AWS_STORAGE_BUCKET_NAME}/backups/$(basename $BACKUP_FILE)" \
            && echo "Backup uploaded to S3" \
            || echo "S3 upload failed; backup remains in /tmp."
    fi
else
    echo "Backup dump failed; continuing without one."
fi

# Migrations are FATAL: a deploy with broken migrations is worse than a
# rolled-back deploy. Let the container fail and EB will not promote.
echo "Running migrations..."
python manage.py migrate --noinput

echo "Seeding public holidays..."
python manage.py seed_public_holidays || echo "Public holidays seeding failed; continuing."

# Idempotent: only creates the superuser if it doesn't exist. Won't reset
# passwords on every deploy. See core/management/commands/create_admin.py.
echo "Bootstrapping admin superuser if needed..."
python manage.py create_admin || echo "create_admin failed; continuing."

echo "Starting gunicorn on port 80..."
exec gunicorn dev_app.wsgi:application --bind 0.0.0.0:80 --workers 3 --timeout 120 --access-logfile - --error-logfile - --log-level info

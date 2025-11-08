#!/bin/bash
set -e

echo "=== Environment Check ==="
echo "DJANGO_SETTINGS_MODULE: $DJANGO_SETTINGS_MODULE"
echo "RDS_HOSTNAME: $RDS_HOSTNAME"
echo "AWS_STORAGE_BUCKET_NAME: $AWS_STORAGE_BUCKET_NAME"
echo "SECRET_KEY present: $([ -n "$SECRET_KEY" ] && echo "YES" || echo "NO")"
echo "========================"

echo "Testing Django import..."
python -c "import django; print('Django version:', django.get_version())" || echo "Django import failed"

echo "Testing settings import..."
python -c "from django.conf import settings; print('Settings loaded:', settings.DATABASES['default']['HOST'])" || echo "Settings import failed"

echo "Starting gunicorn..."
exec gunicorn dev_app.wsgi:application --bind 0.0.0.0:8000 --workers 1 --timeout 120 --access-logfile - --error-logfile - --log-level debug

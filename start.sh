#!/bin/bash
set -e

echo "Starting gunicorn..."
exec gunicorn dev_app.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120 --access-logfile - --error-logfile -

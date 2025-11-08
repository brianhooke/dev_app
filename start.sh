#!/bin/bash

echo "=== Container Started ==="
echo "DJANGO_SETTINGS_MODULE: ${DJANGO_SETTINGS_MODULE:-NOT SET}"
echo "RDS_HOSTNAME: ${RDS_HOSTNAME:-NOT SET}"
echo "AWS_STORAGE_BUCKET_NAME: ${AWS_STORAGE_BUCKET_NAME:-NOT SET}"
echo "========================"

# Start a simple HTTP server on port 8000 to test if container networking works
echo "Starting test HTTP server on port 8000..."
python3 -m http.server 8000

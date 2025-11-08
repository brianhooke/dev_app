# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq-dev \
    gcc \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Create startup script
COPY <<EOF /app/start.sh
#!/bin/bash
set -e
echo "Running migrations..."
python manage.py migrate --noinput || echo "Migrations failed, continuing..."
echo "Starting gunicorn..."
exec gunicorn dev_app.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120 --log-level debug
EOF

RUN chmod +x /app/start.sh

# Run startup script
CMD ["/bin/bash", "/app/start.sh"]

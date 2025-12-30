#!/bin/bash
# Create .env file from EB environment variables for docker-compose
# This script runs before docker-compose up

set -e

echo "=== Creating .env file from EB environment variables ==="

# EB stores environment variables in this file
EB_ENV_FILE="/opt/elasticbeanstalk/deployment/env"

# Target .env file in the application directory
APP_ENV_FILE="/var/app/staging/.env"

if [ -f "$EB_ENV_FILE" ]; then
    echo "Found EB environment file at $EB_ENV_FILE"
    
    # Copy the EB env file to the app directory as .env
    cp "$EB_ENV_FILE" "$APP_ENV_FILE"
    
    # Make it readable
    chmod 644 "$APP_ENV_FILE"
    
    echo "Created $APP_ENV_FILE with EB environment variables"
    
    # Debug: show which variables are set (without values for security)
    echo "Environment variables available:"
    grep -oE '^[^=]+' "$APP_ENV_FILE" | head -20 || echo "Could not list variables"
else
    echo "WARNING: EB environment file not found at $EB_ENV_FILE"
    echo "Checking alternative locations..."
    
    # Try alternative location
    if [ -f "/opt/elasticbeanstalk/deployment/custom_env_var" ]; then
        cp "/opt/elasticbeanstalk/deployment/custom_env_var" "$APP_ENV_FILE"
        chmod 644 "$APP_ENV_FILE"
        echo "Used alternative env file"
    else
        echo "No environment file found - container will use default values"
    fi
fi

echo "=== Done creating .env file ==="

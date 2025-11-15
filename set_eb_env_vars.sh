#!/bin/bash
# Script to set Elastic Beanstalk environment variables
# Run this after getting the RDS endpoint

# Get RDS endpoint
RDS_ENDPOINT=$(aws rds describe-db-instances --db-instance-identifier dev-app-db --query "DBInstances[0].Endpoint.Address" --output text --region ap-southeast-2)

echo "Setting environment variables for dev-app-production..."
echo "RDS Endpoint: $RDS_ENDPOINT"

# Set all environment variables
eb setenv \
  RDS_DB_NAME=devappdb \
  RDS_USERNAME=dbadmin \
  RDS_PASSWORD=DevApp2024SecurePass! \
  RDS_HOSTNAME=$RDS_ENDPOINT \
  RDS_PORT=5432 \
  AWS_STORAGE_BUCKET_NAME=dev-app-mason-bucket \
  AWS_S3_REGION_NAME=ap-southeast-2 \
  AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
  DJANGO_SETTINGS_MODULE=dev_app.settings.production_aws \
  PROJECT_NAME="Mason Build Dev App" \
  LETTERHEAD_PATH=media/letterhead/letterhead.pdf \
  BACKGROUND_IMAGE_PATH=media/backgrounds/bg.jpg

echo "Environment variables set successfully!"
echo ""
echo "Next steps:"
echo "1. Add your email and Xero credentials with: eb setenv EMAIL_HOST_USER=... EMAIL_HOST_PASSWORD=..."
echo "2. Deploy your application with: eb deploy"

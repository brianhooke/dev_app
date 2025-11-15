#!/bin/bash
# Script to set RDS PostgreSQL environment variables in AWS Elastic Beanstalk
# Run this after RDS instance is created

# Get RDS endpoint
RDS_ENDPOINT=$(aws rds describe-db-instances --db-instance-identifier dev-app-postgres --region us-east-1 --query "DBInstances[0].Endpoint.Address" --output text)

echo "RDS Endpoint: $RDS_ENDPOINT"

# Set environment variables in Elastic Beanstalk
aws elasticbeanstalk update-environment \
  --environment-name dev-app-prod \
  --region us-east-1 \
  --option-settings \
    Namespace=aws:elasticbeanstalk:application:environment,OptionName=RDS_HOSTNAME,Value=$RDS_ENDPOINT \
    Namespace=aws:elasticbeanstalk:application:environment,OptionName=RDS_DB_NAME,Value=devappdb \
    Namespace=aws:elasticbeanstalk:application:environment,OptionName=RDS_USERNAME,Value=devappmaster \
    Namespace=aws:elasticbeanstalk:application:environment,OptionName=RDS_PASSWORD,Value=U1wPqDKuRZVZ6hwRrLkrpnNp \
    Namespace=aws:elasticbeanstalk:application:environment,OptionName=RDS_PORT,Value=5432

echo "Environment variables set successfully!"
echo "The environment will restart automatically to apply changes."

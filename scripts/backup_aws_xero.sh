#!/bin/bash
# Script to backup Xero data from AWS and update the XERO_DATA environment variable
# 
# Usage:
#   ./scripts/backup_aws_xero.sh
#
# This script:
# 1. SSHs into the AWS EC2 instance
# 2. Exports Xero instances to JSON
# 3. Downloads the JSON file
# 4. Base64 encodes it
# 5. Updates the AWS EB environment variable

set -e

echo "=== AWS Xero Data Backup Script ==="
echo ""

# Get the EC2 instance ID
echo "Getting EC2 instance ID..."
INSTANCE_ID=$(aws ec2 describe-instances \
    --filters "Name=tag:elasticbeanstalk:environment-name,Values=dev-app-prod" "Name=instance-state-name,Values=running" \
    --query 'Reservations[0].Instances[0].InstanceId' \
    --output text)

if [ "$INSTANCE_ID" == "None" ] || [ -z "$INSTANCE_ID" ]; then
    echo "ERROR: Could not find running EC2 instance for dev-app-prod"
    exit 1
fi

echo "Found instance: $INSTANCE_ID"
echo ""

# Use SSM to run the export command
echo "Exporting Xero data from AWS..."
COMMAND_ID=$(aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters 'commands=["cd /var/app/current && source /var/app/venv/*/bin/activate && python manage.py export_xero_instances --output /tmp/xero_export.json && cat /tmp/xero_export.json"]' \
    --query 'Command.CommandId' \
    --output text)

echo "Waiting for command to complete..."
sleep 5

# Get the output
OUTPUT=$(aws ssm get-command-invocation \
    --command-id "$COMMAND_ID" \
    --instance-id "$INSTANCE_ID" \
    --query 'StandardOutputContent' \
    --output text)

# Extract just the JSON part (after the success message)
JSON_DATA=$(echo "$OUTPUT" | grep -A 1000 '^\[' | head -n -1)

if [ -z "$JSON_DATA" ]; then
    echo "ERROR: Could not extract Xero data from output"
    echo "Raw output:"
    echo "$OUTPUT"
    exit 1
fi

# Save to local file
echo "$JSON_DATA" > xero_aws_backup.json
echo "Saved to xero_aws_backup.json"

# Base64 encode
XERO_DATA_B64=$(echo "$JSON_DATA" | base64)

echo ""
echo "=== XERO_DATA Environment Variable ==="
echo ""
echo "Run this command to update the AWS environment variable:"
echo ""
echo "aws elasticbeanstalk update-environment \\"
echo "    --environment-name dev-app-prod \\"
echo "    --option-settings Namespace=aws:elasticbeanstalk:application:environment,OptionName=XERO_DATA,Value='$XERO_DATA_B64'"
echo ""
echo "Or copy this value to set manually in AWS Console:"
echo ""
echo "$XERO_DATA_B64"
echo ""
echo "=== Done ==="

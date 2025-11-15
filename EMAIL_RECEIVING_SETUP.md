# Email Receiving Setup Guide

## Overview

This system receives emails at `bills@app.mason.build` and `test@app.mason.build`, processes them via AWS Lambda, and stores them in PostgreSQL with attachments in S3.

**Architecture:** Incoming Email → SES → S3 → Lambda → Django API → PostgreSQL

---

## Phase 1: Database Migration (Already Done ✅)

The models are already added to `core/models.py`. Just need to run migrations:

```bash
# Local
python3 manage.py makemigrations
python3 manage.py migrate

# AWS (will run automatically on deploy via start.sh)
```

---

## Phase 2: AWS SES Setup

### Step 1: Verify Domain in SES

```bash
# Verify mason.build domain in SES
aws ses verify-domain-identity --domain mason.build --region us-east-1
```

This will return DKIM tokens. You need to add these DNS records in your domain provider (Route53/Cloudflare/etc.):

### Step 2: Add DNS Records

**For Route53:**
```bash
# Get verification token
TOKEN=$(aws ses verify-domain-identity --domain mason.build --region us-east-1 --query VerificationToken --output text)

# Add TXT record for domain verification
aws route53 change-resource-record-sets --hosted-zone-id YOUR_ZONE_ID --change-batch '{
  "Changes": [{
    "Action": "CREATE",
    "ResourceRecordSet": {
      "Name": "_amazonses.mason.build",
      "Type": "TXT",
      "TTL": 1800,
      "ResourceRecords": [{"Value": "\"'$TOKEN'\""}]
    }
  }]
}'

# Add MX record to receive emails
aws route53 change-resource-record-sets --hosted-zone-id YOUR_ZONE_ID --change-batch '{
  "Changes": [{
    "Action": "CREATE",
    "ResourceRecordSet": {
      "Name": "app.mason.build",
      "Type": "MX",
      "TTL": 1800,
      "ResourceRecords": [{"Value": "10 inbound-smtp.us-east-1.amazonaws.com"}]
    }
  }]
}'
```

**Or manually in Route53 console:**
1. Go to Route53 → Hosted Zones → mason.build
2. Add TXT record: `_amazonses.mason.build` with value from SES
3. Add MX record: `app.mason.build` pointing to `10 inbound-smtp.us-east-1.amazonaws.com`

### Step 3: Create SES Receipt Rule

```bash
# Create receipt rule set (if doesn't exist)
aws ses create-receipt-rule-set --rule-set-name email-receiving-rules --region us-east-1

# Set as active
aws ses set-active-receipt-rule-set --rule-set-name email-receiving-rules --region us-east-1

# Create rule to save emails to S3
aws ses create-receipt-rule \
  --rule-set-name email-receiving-rules \
  --rule '{
    "Name": "save-to-s3",
    "Enabled": true,
    "TlsPolicy": "Optional",
    "Recipients": [
      "bills@app.mason.build",
      "test@app.mason.build"
    ],
    "Actions": [{
      "S3Action": {
        "BucketName": "dev-app-emails",
        "ObjectKeyPrefix": "inbox/"
      }
    }]
  }' \
  --region us-east-1
```

---

## Phase 3: Lambda Function Deployment

### Step 1: Create Lambda Deployment Package

```bash
cd /tmp
mkdir lambda-email-processor
cd lambda-email-processor

# Copy Lambda function
cp "/Users/brianhooke/Library/Mobile Documents/com~apple~CloudDocs/Coding/dev_app/lambda_email_processor.py" lambda_function.py

# Install dependencies
pip3 install --target . requests

# Create deployment package
zip -r lambda-email-processor.zip .
```

### Step 2: Create IAM Role for Lambda

```bash
# Create trust policy
cat > /tmp/lambda-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "lambda.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

# Create role
aws iam create-role \
  --role-name lambda-email-processor-role \
  --assume-role-policy-document file:///tmp/lambda-trust-policy.json

# Attach basic execution policy
aws iam attach-role-policy \
  --role-name lambda-email-processor-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Create S3 access policy
cat > /tmp/lambda-s3-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "s3:GetObject",
      "s3:PutObject"
    ],
    "Resource": "arn:aws:s3:::dev-app-emails/*"
  }]
}
EOF

# Attach S3 policy
aws iam put-role-policy \
  --role-name lambda-email-processor-role \
  --policy-name s3-access \
  --policy-document file:///tmp/lambda-s3-policy.json
```

### Step 3: Create Lambda Function

```bash
# Generate a strong API key
API_KEY=$(openssl rand -base64 32)
echo "Save this API key: $API_KEY"

# Create Lambda function
aws lambda create-function \
  --function-name email-processor \
  --runtime python3.11 \
  --role arn:aws:iam::629256540295:role/lambda-email-processor-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb:///tmp/lambda-email-processor/lambda-email-processor.zip \
  --timeout 60 \
  --memory-size 256 \
  --environment "Variables={
    DJANGO_API_URL=https://app.mason.build/core/api/receive_email/,
    API_SECRET_KEY=$API_KEY
  }" \
  --region us-east-1
```

### Step 4: Add S3 Trigger to Lambda

```bash
# Allow S3 to invoke Lambda
aws lambda add-permission \
  --function-name email-processor \
  --statement-id s3-trigger \
  --action lambda:InvokeFunction \
  --principal s3.amazonaws.com \
  --source-arn arn:aws:s3:::dev-app-emails \
  --region us-east-1

# Add S3 notification to trigger Lambda
aws s3api put-bucket-notification-configuration \
  --bucket dev-app-emails \
  --notification-configuration '{
    "LambdaFunctionConfigurations": [{
      "LambdaFunctionArn": "arn:aws:lambda:us-east-1:629256540295:function:email-processor",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {
        "Key": {
          "FilterRules": [{
            "Name": "prefix",
            "Value": "inbox/"
          }]
        }
      }
    }]
  }'
```

---

## Phase 4: Django Configuration

### Step 1: Add API Key to AWS EB Environment

```bash
# Use the API key generated above
aws elasticbeanstalk update-environment \
  --environment-name dev-app-prod \
  --region us-east-1 \
  --option-settings \
    Namespace=aws:elasticbeanstalk:application:environment,OptionName=EMAIL_API_SECRET_KEY,Value=YOUR_API_KEY_HERE
```

### Step 2: Deploy Updated Code

The code is already updated with:
- ✅ Models added to `core/models.py`
- ✅ API endpoint at `/core/api/receive_email/`
- ✅ Admin interface registered
- ✅ Settings configured

Just need to deploy:

```bash
# Run migrations locally first
python3 manage.py makemigrations
python3 manage.py migrate

# Commit and deploy
git add -A
git commit -m "v43: Add email receiving system (SES → Lambda → Django)"
# Deploy via normal process
```

---

## Phase 5: Testing

### Test 1: Send Test Email

```bash
# Send test email to test@app.mason.build
# Use your personal email or:
aws ses send-email \
  --from your-verified-email@example.com \
  --destination "ToAddresses=test@app.mason.build" \
  --message "Subject={Data='Test Email'},Body={Text={Data='This is a test email with body text.'}}" \
  --region us-east-1
```

### Test 2: Check S3

```bash
# Check if email arrived in S3
aws s3 ls s3://dev-app-emails/inbox/ --recursive
```

### Test 3: Check Lambda Logs

```bash
# View Lambda logs
aws logs tail /aws/lambda/email-processor --follow --region us-east-1
```

### Test 4: Check Django

```bash
# Check Django received the email
curl https://app.mason.build/core/api/emails/ \
  -u admin:your-password
```

Or visit Django admin:
```
https://app.mason.build/admin/core/receivedemail/
```

---

## Email Addresses

### Production: `bills@app.mason.build`
- For receiving bills, invoices, receipts
- Stored in PostgreSQL with full history
- Attachments saved to S3

### Testing: `test@app.mason.build`
- For testing the email system
- Same processing as production
- Can be filtered/deleted easily

---

## Troubleshooting

### Email not arriving in S3
1. Check DNS records are correct (`dig MX app.mason.build`)
2. Verify domain in SES (`aws ses get-identity-verification-attributes --identities mason.build --region us-east-1`)
3. Check SES receipt rule is active

### Lambda not triggering
1. Check S3 notification configuration
2. Check Lambda permissions
3. View CloudWatch logs

### Django API returning error
1. Check API key matches in Lambda and Django
2. Check Django logs
3. Test API manually: `curl -X POST https://app.mason.build/core/api/receive_email/ -H "X-API-Secret: YOUR_KEY" -d '{}'`

---

## Security Notes

1. **API Key:** Keep `EMAIL_API_SECRET_KEY` secret and rotate periodically
2. **S3 Bucket:** Only Lambda and SES can write, Django can read
3. **Lambda:** Only has S3 access, no database access
4. **Attachments:** Generate presigned URLs for downloading (expire in 1 hour)

---

## Cost Estimate

- **SES:** $0.10 per 1,000 emails
- **S3:** $0.023 per GB/month
- **Lambda:** $0.20 per 1M requests + $0.0000166667 per GB-second
- **Total:** ~$1-5/month for typical usage

---

## Next Steps

After setup is complete, you can:
1. Add email processing logic to auto-categorize bills
2. Extract invoice numbers/amounts automatically
3. Create notifications when bills arrive
4. Build UI to view/manage received emails
5. Add OCR for scanned PDFs
6. Auto-create records from email content

# Local Email Testing Setup

## Option A: Test with Real Emails via ngrok

### 1. Install ngrok (if not already installed)
```bash
brew install ngrok
# OR download from https://ngrok.com/download
```

### 2. Start your local Django server
```bash
python manage.py runserver 8000
```

### 3. In a new terminal, start ngrok
```bash
ngrok http 8000
```

This gives you a public URL like: `https://abc123.ngrok.io`

### 4. Update Lambda to point to your ngrok URL
```bash
# Get the ngrok URL from step 3, then:
aws lambda update-function-configuration \
  --function-name email-processor \
  --environment "Variables={DJANGO_API_URL=https://YOUR-NGROK-URL.ngrok.io/core/api/receive_email/,API_SECRET_KEY=05817a8c12b4f2d5b173953b3a0ab58a70a2f18b84ceaed32326e7e87cf6ed0e}" \
  --region us-east-1
```

### 5. Add test@mail.mason.build to SES rules
```bash
aws ses update-receipt-rule \
  --rule-set-name email-receiving-rules \
  --rule '{
    "Name": "save-to-s3-test",
    "Enabled": true,
    "TlsPolicy": "Optional",
    "Recipients": [
      "test@mail.mason.build"
    ],
    "Actions": [{
      "S3Action": {
        "BucketName": "dev-app-emails",
        "ObjectKeyPrefix": "test-inbox/"
      }
    }]
  }' \
  --region us-east-1
```

### 6. Send test email to test@mail.mason.build
It will now route to your local server!

### 7. When done testing
Restore Lambda to production URL:
```bash
aws lambda update-function-configuration \
  --function-name email-processor \
  --environment "Variables={DJANGO_API_URL=https://app.mason.build/core/api/receive_email/,API_SECRET_KEY=05817a8c12b4f2d5b173953b3a0ab58a70a2f18b84ceaed32326e7e87cf6ed0e}" \
  --region us-east-1
```

---

## Option B: Manual Local Testing (Simpler)

Test without real emails using the provided script:

### 1. Start local server
```bash
python manage.py runserver 8000
```

### 2. Run the test script
```bash
python test_email_locally.py
```

This simulates Lambda calling your local API with sample email data.

---

## Quick Test Command

Test your local API directly:
```bash
curl -X POST http://localhost:8000/core/api/receive_email/ \
  -H "Content-Type: application/json" \
  -H "X-API-Secret: 05817a8c12b4f2d5b173953b3a0ab58a70a2f18b84ceaed32326e7e87cf6ed0e" \
  -d '{
    "message_id": "test-'$(date +%s)'",
    "from_address": "sender@example.com",
    "to_address": "test@mail.mason.build",
    "subject": "Test Invoice",
    "body_text": "This is a test email body",
    "body_html": "",
    "received_at": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'",
    "s3_bucket": "dev-app-emails",
    "s3_key": "test/sample",
    "attachments": [
      {
        "filename": "invoice.pdf",
        "content_type": "application/pdf",
        "size_bytes": 12345,
        "s3_bucket": "dev-app-emails",
        "s3_key": "attachments/test-invoice.pdf"
      }
    ]
  }'
```

You should see the email and invoice created in your local database!

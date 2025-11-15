# Email Receiving - Quick Start

## 🎯 What's Been Done

✅ Django models created (`ReceivedEmail`, `EmailAttachment`)  
✅ API endpoint created (`/core/api/receive_email/`)  
✅ Admin interface configured  
✅ S3 bucket created (`dev-app-emails`)  
✅ Lambda function code ready (`lambda_email_processor.py`)  
✅ Migration created and applied locally  

## 📧 Email Addresses

- **Production:** `bills@app.mason.build`  
- **Testing:** `test@app.mason.build`  

## ⚙️ Setup Required (Do Once)

### 1. Verify Domain in SES
```bash
aws ses verify-domain-identity --domain mason.build --region us-east-1
```
→ Add DNS records (see EMAIL_RECEIVING_SETUP.md)

### 2. Deploy Lambda Function
```bash
# See Phase 3 in EMAIL_RECEIVING_SETUP.md
# Takes ~10 minutes
```

### 3. Configure SES Receipt Rule
```bash
# See Phase 2 Step 3 in EMAIL_RECEIVING_SETUP.md
# Takes ~2 minutes
```

### 4. Set API Key in AWS EB
```bash
# Generate key
API_KEY=$(openssl rand -base64 32)
echo $API_KEY

# Add to EB
aws elasticbeanstalk update-environment \
  --environment-name dev-app-prod \
  --region us-east-1 \
  --option-settings \
    Namespace=aws:elasticbeanstalk:application:environment,OptionName=EMAIL_API_SECRET_KEY,Value=$API_KEY
```

### 5. Deploy Django Code
```bash
# Deploy v43 (includes email models + API)
# Migrations will run automatically
```

## 🧪 Testing

1. **Send test email:**
   ```
   Send email to: test@app.mason.build
   ```

2. **Check it arrived:**
   ```
   https://app.mason.build/admin/core/receivedemail/
   ```

3. **View attachments:**
   - Click on email in admin
   - See attachments listed with download links

## 📂 Files Created/Modified

- `core/models.py` - Added `ReceivedEmail` and `EmailAttachment` models
- `core/views/email_receiver.py` - API endpoint for Lambda
- `core/urls.py` - Added `/api/receive_email/` route
- `core/admin.py` - Admin interface for emails
- `dev_app/settings/base.py` - Added `EMAIL_API_SECRET_KEY` setting
- `lambda_email_processor.py` - Lambda function (deploy separately)
- `core/migrations/0010_receivedemail_emailattachment.py` - Database migration

## 🔍 How It Works

```
1. Email sent to bills@app.mason.build
   ↓
2. AWS SES receives it
   ↓
3. SES stores raw email in S3 (dev-app-emails/inbox/)
   ↓
4. S3 triggers Lambda function
   ↓
5. Lambda parses email, extracts attachments
   ↓
6. Lambda stores attachments in S3 (dev-app-emails/attachments/)
   ↓
7. Lambda calls Django API with processed data
   ↓
8. Django stores in PostgreSQL (ReceivedEmail + EmailAttachment)
   ↓
9. View in admin: https://app.mason.build/admin/core/receivedemail/
```

## 💡 Next Steps

After emails are being received:

1. **Auto-categorize bills** - Add logic in `email_receiver.py`
2. **Extract invoice data** - Parse PDFs, extract amounts
3. **Notifications** - Email/SMS when bill arrives
4. **Build UI** - Create page to view received emails
5. **Workflows** - Auto-create records from emails

## 📊 View Emails

- **Admin:** `https://app.mason.build/admin/core/receivedemail/`
- **API:** `https://app.mason.build/core/api/emails/` (requires auth)

## 🚨 Troubleshooting

| Problem | Solution |
|---------|----------|
| Email not arriving | Check DNS MX records |
| Lambda not triggering | Check S3 notification config |
| API error | Check API key matches in Lambda & Django |
| Can't download attachment | Check S3 permissions |

For detailed troubleshooting, see `EMAIL_RECEIVING_SETUP.md`.

## 💰 Cost

~$1-5/month for typical usage:
- SES: $0.10 per 1,000 emails
- S3: $0.023 per GB/month
- Lambda: ~$0.20 per 1M requests

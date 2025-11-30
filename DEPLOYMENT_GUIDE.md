# AWS Deployment Guide - Environment Variables

## Overview
Your Django app uses AWS Elastic Beanstalk and reads configuration from environment variables via `os.getenv()`. This guide covers secure methods to set these variables.

---

## Required Environment Variables

Based on your `production_aws.py`, you need:

### **Django Core**
- `SECRET_KEY` - Django secret key (generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)

### **Database (RDS)**
- `RDS_DB_NAME` - Database name
- `RDS_USERNAME` - Database user
- `RDS_PASSWORD` - Database password ⚠️ **SENSITIVE**
- `RDS_HOSTNAME` - RDS endpoint (e.g., `mydb.abc123.us-east-1.rds.amazonaws.com`)
- `RDS_PORT` - Database port (default: `5432`)

### **AWS S3**
- `AWS_STORAGE_BUCKET_NAME` - S3 bucket for static/media files
- `AWS_S3_REGION_NAME` - AWS region (e.g., `us-east-1`)
- `AWS_ACCESS_KEY_ID` - AWS access key ⚠️ **SENSITIVE**
- `AWS_SECRET_ACCESS_KEY` - AWS secret key ⚠️ **SENSITIVE**

### **Email (Office 365)**
- `EMAIL_HOST_USER` - Email address (e.g., `purchase_orders@mason.build`)
- `EMAIL_HOST_PASSWORD` - Email password ⚠️ **SENSITIVE**
- `DEFAULT_FROM_EMAIL` - Default from address
- `EMAIL_CC` - CC email address

### **Xero API**
- `XERO_CLIENT_ID` - Xero OAuth client ID ⚠️ **SENSITIVE**
- `XERO_CLIENT_SECRET` - Xero OAuth secret ⚠️ **SENSITIVE**
- `XERO_PROJECT_ID` - Xero project ID
- `MB_XERO_CLIENT_ID` - Mason Build Xero client ID
- `MB_XERO_CLIENT_SECRET` - Mason Build Xero secret ⚠️ **SENSITIVE**
- `MDG_XERO_CLIENT_ID` - MDG Xero client ID
- `MDG_XERO_CLIENT_SECRET` - MDG Xero secret ⚠️ **SENSITIVE**

### **Project Specific**
- `PROJECT_NAME` - Your project name
- `LETTERHEAD_PATH` - Path to letterhead file
- `BACKGROUND_IMAGE_PATH` - Path to background image (optional)

---

## Method 1: AWS Console (Recommended for Most Users)

### Steps:
1. **Go to Elastic Beanstalk Console**
   - Navigate to: https://console.aws.amazon.com/elasticbeanstalk
   - Select your application
   - Select your environment

2. **Access Configuration**
   - Left sidebar → **Configuration**
   - Find **Software** category → Click **Edit**

3. **Add Environment Properties**
   - Scroll down to "Environment properties" section
   - Click **Add environment property**
   - Add each key-value pair from the list above

4. **Apply Changes**
   - Click **Apply** at bottom
   - EB will restart your environment (takes 2-5 minutes)

### ✅ **Pros:**
- Simple GUI
- Changes tracked in EB configuration history
- No CLI tools required

### ❌ **Cons:**
- Manual entry (tedious for many variables)
- Easy to make typos

---

## Method 2: EB CLI (Best for Developers)

### Prerequisites:
```bash
# Install EB CLI
pip install awsebcli

# Initialize (one-time)
eb init
```

### Set Variables:
```bash
# Option A: Set variables one by one
eb setenv SECRET_KEY=your-secret-key \
         EMAIL_HOST_USER=purchase_orders@mason.build \
         EMAIL_HOST_PASSWORD=your-password

# Option B: From a file (recommended)
# 1. Create .env.production file (DON'T COMMIT THIS!)
cat > .env.production << 'EOF'
SECRET_KEY=your-secret-key-here
RDS_DB_NAME=devappdb
RDS_USERNAME=devappuser
RDS_PASSWORD=your-db-password
RDS_HOSTNAME=your-rds.abc123.us-east-1.rds.amazonaws.com
RDS_PORT=5432
AWS_STORAGE_BUCKET_NAME=your-bucket-name
AWS_S3_REGION_NAME=us-east-1
EMAIL_HOST_USER=purchase_orders@mason.build
EMAIL_HOST_PASSWORD=your-email-password
DEFAULT_FROM_EMAIL=purchase_orders@mason.build
EMAIL_CC=brian.hooke@mason.build
XERO_CLIENT_ID=your-xero-client-id
XERO_CLIENT_SECRET=your-xero-secret
PROJECT_NAME=Mason Project Management
LETTERHEAD_PATH=path/to/letterhead.png
EOF

# 2. Deploy from file
eb setenv $(cat .env.production | xargs)

# 3. Delete .env.production after deployment!
rm .env.production
```

### View Current Variables:
```bash
eb printenv
```

### ✅ **Pros:**
- Fast bulk updates
- Scriptable/automatable
- Can use local .env file as source

### ❌ **Cons:**
- Requires EB CLI installation
- Must be careful not to commit .env.production

---

## Method 3: AWS Secrets Manager (Most Secure)

For highly sensitive credentials (passwords, API keys), use AWS Secrets Manager.

### Setup:

1. **Store secrets in Secrets Manager:**
```bash
# Store email password
aws secretsmanager create-secret \
  --name dev-app/email-password \
  --secret-string "your-actual-password" \
  --region us-east-1

# Store Xero credentials as JSON
aws secretsmanager create-secret \
  --name dev-app/xero-credentials \
  --secret-string '{
    "client_id": "your-client-id",
    "client_secret": "your-client-secret"
  }' \
  --region us-east-1

# Store RDS password
aws secretsmanager create-secret \
  --name dev-app/rds-password \
  --secret-string "your-db-password" \
  --region us-east-1
```

2. **Grant EB IAM role permissions:**
   - Go to IAM Console → Roles
   - Find your EB instance profile role (e.g., `aws-elasticbeanstalk-ec2-role`)
   - Attach policy: `SecretsManagerReadWrite` or create custom policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:*:secret:dev-app/*"
    }
  ]
}
```

3. **Update `production_aws.py`** to use Secrets Manager:
```python
# At top of file
from dev_app.aws_secrets import get_secret
import json

# Replace sensitive variables:
EMAIL_HOST_PASSWORD = get_secret('dev-app/email-password')
RDS_PASSWORD = get_secret('dev-app/rds-password')

# For JSON secrets:
xero_creds = json.loads(get_secret('dev-app/xero-credentials'))
XERO_CLIENT_ID = xero_creds['client_id']
XERO_CLIENT_SECRET = xero_creds['client_secret']
```

### ✅ **Pros:**
- Secrets encrypted at rest
- Automatic rotation available
- Audit trail of secret access
- Best practice for production

### ❌ **Cons:**
- More complex setup
- Additional AWS service costs (~$0.40/month per secret)
- Slight performance overhead (first request only, then cached)

---

## Method 4: .ebextensions Config (For Non-Sensitive Values)

For **non-sensitive** configuration only (like feature flags):

Create `.ebextensions/environment.config`:
```yaml
option_settings:
  aws:elasticbeanstalk:application:environment:
    PROJECT_NAME: "Mason Project Management"
    LETTERHEAD_PATH: "media/letterhead.png"
    AWS_S3_REGION_NAME: "us-east-1"
```

⚠️ **WARNING:** This file is committed to Git, so **NEVER** put passwords or API keys here!

---

## Security Best Practices

### ✅ **DO:**
- Use Secrets Manager for passwords and API keys
- Rotate secrets regularly
- Use principle of least privilege for IAM roles
- Keep `.env` files in `.gitignore`
- Use different secrets for dev/staging/production
- Enable MFA on AWS accounts with production access

### ❌ **DON'T:**
- Commit `.env` or `.env.production` to Git
- Share secrets via Slack/email
- Use the same secrets across environments
- Put secrets in `.ebextensions` files
- Copy-paste secrets in plain text documents

---

## Deployment Workflow

### Initial Setup (One-Time):
```bash
# 1. Set all environment variables via AWS Console or EB CLI
eb setenv $(cat .env.production | xargs)

# 2. Deploy application
eb deploy

# 3. Run migrations
eb ssh
cd /var/app/current
source /var/app/venv/*/bin/activate
python manage.py migrate
exit
```

### Subsequent Deployments:
```bash
# Deploy code changes
eb deploy

# If there are new migrations:
eb ssh
cd /var/app/current
source /var/app/venv/*/bin/activate
python manage.py migrate
exit
```

### Update Environment Variables:
```bash
# Update a single variable
eb setenv EMAIL_HOST_USER=new-email@mason.build

# Update from file
eb setenv $(cat .env.production | xargs)
```

---

## Troubleshooting

### Check current environment variables:
```bash
eb printenv
```

### View application logs:
```bash
eb logs
```

### SSH into instance to debug:
```bash
eb ssh
# Then check environment:
env | grep -E 'RDS|EMAIL|XERO'
```

### Common Issues:

**Issue:** "No DATABASE_URL environment variable set"
- **Fix:** Set all `RDS_*` variables in EB environment

**Issue:** Email not sending
- **Fix:** Verify `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` are set correctly

**Issue:** S3 media files not loading
- **Fix:** Check `AWS_STORAGE_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

---

## Recommended Approach

For your project, I recommend:

1. **Use EB CLI (Method 2)** for initial setup - fast bulk import
2. **Migrate sensitive secrets to Secrets Manager (Method 3)** over time
3. **Use AWS Console (Method 1)** for occasional updates

This balances ease of use with security best practices.

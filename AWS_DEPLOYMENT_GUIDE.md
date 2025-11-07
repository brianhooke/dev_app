# AWS Elastic Beanstalk Deployment Guide

## Overview

This guide covers deploying the dev_app Django application to AWS Elastic Beanstalk with:
- **Elastic Beanstalk**: Application hosting
- **RDS PostgreSQL**: Database
- **S3**: Static and media file storage
- **Environment Variables**: Secure configuration management

---

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured
3. **EB CLI** (Elastic Beanstalk CLI) installed
4. **Git** repository initialized

### Install AWS CLI
```bash
# macOS
brew install awscli

# Configure with your credentials
aws configure
```

### Install EB CLI
```bash
pip install awsebcli
```

---

## Step 1: Initialize Elastic Beanstalk

```bash
# From project root
eb init

# Follow prompts:
# - Select region (e.g., us-east-1)
# - Create new application: dev-app
# - Select Python 3.11 (or your version)
# - Do not set up SSH at this time (optional)
```

---

## Step 2: Create S3 Bucket for Static/Media Files

```bash
# Create S3 bucket (replace with your bucket name)
aws s3 mb s3://your-project-bucket --region us-east-1

# Configure bucket for public read access (for static files)
aws s3api put-bucket-policy --bucket your-project-bucket --policy '{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::your-project-bucket/static/*"
    }
  ]
}'
```

---

## Step 3: Create RDS PostgreSQL Database

### Option A: Via AWS Console
1. Go to RDS → Create Database
2. Choose PostgreSQL
3. Select appropriate instance size (e.g., db.t3.micro for dev)
4. Set database name, username, password
5. Note the endpoint URL

### Option B: Via AWS CLI
```bash
aws rds create-db-instance \
    --db-instance-identifier dev-app-db \
    --db-instance-class db.t3.micro \
    --engine postgres \
    --master-username dbadmin \
    --master-user-password YOUR_SECURE_PASSWORD \
    --allocated-storage 20 \
    --vpc-security-group-ids sg-xxxxx \
    --db-name devappdb
```

---

## Step 4: Create Elastic Beanstalk Environment

```bash
# Create environment
eb create dev-app-production \
    --instance-type t3.small \
    --platform python-3.11 \
    --region us-east-1

# This will:
# - Create EC2 instances
# - Set up load balancer
# - Configure auto-scaling
# - Deploy your application
```

---

## Step 5: Configure Environment Variables

Set all required environment variables in Elastic Beanstalk:

```bash
# Database Configuration
eb setenv RDS_DB_NAME=devappdb
eb setenv RDS_USERNAME=dbadmin
eb setenv RDS_PASSWORD=your_secure_password
eb setenv RDS_HOSTNAME=your-db-instance.xxxxx.us-east-1.rds.amazonaws.com
eb setenv RDS_PORT=5432

# AWS S3 Configuration
eb setenv AWS_STORAGE_BUCKET_NAME=your-project-bucket
eb setenv AWS_S3_REGION_NAME=us-east-1
eb setenv AWS_ACCESS_KEY_ID=your_access_key
eb setenv AWS_SECRET_ACCESS_KEY=your_secret_key

# Django Configuration
eb setenv DJANGO_SETTINGS_MODULE=dev_app.settings.production_aws
eb setenv SECRET_KEY=your_django_secret_key

# Project Configuration
eb setenv PROJECT_NAME="Your Project Name"
eb setenv LETTERHEAD_PATH=media/letterhead/letterhead.pdf
eb setenv BACKGROUND_IMAGE_PATH=media/backgrounds/bg.jpg

# Email Configuration
eb setenv EMAIL_HOST_USER=invoices@yourdomain.com
eb setenv EMAIL_HOST_PASSWORD=your_email_password
eb setenv DEFAULT_FROM_EMAIL=invoices@yourdomain.com
eb setenv EMAIL_CC=cc@yourdomain.com

# Xero API Configuration
eb setenv XERO_CLIENT_ID=your_xero_client_id
eb setenv XERO_CLIENT_SECRET=your_xero_client_secret
eb setenv XERO_PROJECT_ID=your_project_id
eb setenv MB_XERO_CLIENT_ID=your_mb_client_id
eb setenv MB_XERO_CLIENT_SECRET=your_mb_secret
eb setenv MDG_XERO_CLIENT_ID=your_mdg_client_id
eb setenv MDG_XERO_CLIENT_SECRET=your_mdg_secret
```

---

## Step 6: Update ALLOWED_HOSTS

After deployment, get your Elastic Beanstalk URL:

```bash
eb status
# Note the CNAME (e.g., dev-app-production.us-east-1.elasticbeanstalk.com)
```

Update `production_aws.py`:
```python
ALLOWED_HOSTS = [
    '.elasticbeanstalk.com',
    'dev-app-production.us-east-1.elasticbeanstalk.com',  # Your specific URL
    # Add custom domain if you have one
]
```

---

## Step 7: Deploy Application

```bash
# Deploy current code
eb deploy

# Monitor deployment
eb logs --stream
```

---

## Step 8: Run Database Migrations

Migrations run automatically via `.ebextensions/01_django.config`, but you can also run manually:

```bash
# SSH into instance
eb ssh

# Activate virtual environment and run migrations
source /var/app/venv/*/bin/activate
cd /var/app/current
python manage.py migrate
python manage.py collectstatic --noinput
```

---

## Step 9: Create Superuser

```bash
# SSH into instance
eb ssh

# Create superuser
source /var/app/venv/*/bin/activate
cd /var/app/current
python manage.py createsuperuser
```

---

## Step 10: Configure Custom Domain (Optional)

### Add Custom Domain to Elastic Beanstalk
1. Go to Elastic Beanstalk Console → Your Environment
2. Configuration → Load Balancer
3. Add listener on port 443 (HTTPS)
4. Add SSL certificate (from AWS Certificate Manager)

### Update DNS
Point your domain to the Elastic Beanstalk CNAME:
```
CNAME: www.yourdomain.com → dev-app-production.us-east-1.elasticbeanstalk.com
```

### Update ALLOWED_HOSTS
```python
ALLOWED_HOSTS = [
    '.elasticbeanstalk.com',
    'yourdomain.com',
    'www.yourdomain.com',
]
```

---

## Ongoing Deployment

### Deploy New Changes
```bash
# Commit your changes
git add .
git commit -m "Your changes"

# Deploy to AWS
eb deploy

# Monitor logs
eb logs --stream
```

### View Application Logs
```bash
# Tail logs in real-time
eb logs --stream

# Download all logs
eb logs --all
```

### Check Application Status
```bash
eb status
eb health
```

---

## Environment Management

### Create Additional Environments
```bash
# Staging environment
eb create dev-app-staging --instance-type t3.micro

# Production environment
eb create dev-app-production --instance-type t3.medium
```

### Switch Between Environments
```bash
eb use dev-app-staging
eb deploy

eb use dev-app-production
eb deploy
```

### Terminate Environment
```bash
eb terminate dev-app-staging
```

---

## Troubleshooting

### View Recent Logs
```bash
eb logs
```

### SSH into Instance
```bash
eb ssh
```

### Check Environment Health
```bash
eb health --refresh
```

### Common Issues

**Issue: Static files not loading**
- Verify S3 bucket permissions
- Check `AWS_STORAGE_BUCKET_NAME` environment variable
- Run `python manage.py collectstatic` manually

**Issue: Database connection errors**
- Verify RDS security group allows connections from EB instances
- Check RDS endpoint and credentials in environment variables
- Ensure RDS and EB are in same VPC

**Issue: Application not starting**
- Check logs: `eb logs`
- Verify `DJANGO_SETTINGS_MODULE` is set correctly
- Ensure all required environment variables are set

---

## Cost Optimization

### Development/Testing
- Use `t3.micro` or `t3.small` instances
- Use RDS `db.t3.micro` instance
- Single instance (no load balancer)

### Production
- Use `t3.medium` or larger instances
- Use RDS `db.t3.small` or larger
- Enable auto-scaling (2-4 instances)
- Use load balancer for high availability

### Monitoring Costs
```bash
# View estimated costs
aws ce get-cost-and-usage \
    --time-period Start=2024-01-01,End=2024-01-31 \
    --granularity MONTHLY \
    --metrics BlendedCost
```

---

## Security Best Practices

1. **Never commit secrets** - Use environment variables
2. **Enable HTTPS** - Use AWS Certificate Manager for SSL
3. **Restrict database access** - Configure RDS security groups
4. **Use IAM roles** - For S3 access instead of access keys
5. **Enable CloudWatch** - For monitoring and alerts
6. **Regular backups** - Enable automated RDS backups
7. **Update dependencies** - Keep Python packages up to date

---

## Comparison: Heroku vs AWS Elastic Beanstalk

| Feature | Heroku (production.py) | AWS EB (production_aws.py) |
|---------|------------------------|----------------------------|
| Deployment | `git push heroku main` | `eb deploy` |
| Database | Heroku Postgres addon | AWS RDS PostgreSQL |
| Static Files | Heroku + S3 | AWS S3 |
| Configuration | Heroku config vars | EB environment variables |
| Cost | Higher (simpler) | Lower (more complex) |
| Scaling | Automatic | Configurable auto-scaling |
| Control | Limited | Full AWS control |

---

## Next Steps

1. ✅ Created `production_aws.py` settings file
2. ✅ Created `.ebextensions` configuration
3. ⏸️ Initialize EB application (`eb init`)
4. ⏸️ Create S3 bucket for static/media files
5. ⏸️ Create RDS PostgreSQL database
6. ⏸️ Create EB environment (`eb create`)
7. ⏸️ Set environment variables (`eb setenv`)
8. ⏸️ Deploy application (`eb deploy`)
9. ⏸️ Run migrations and create superuser
10. ⏸️ Configure custom domain (optional)

---

## Resources

- [AWS Elastic Beanstalk Documentation](https://docs.aws.amazon.com/elasticbeanstalk/)
- [Django on Elastic Beanstalk](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/create-deploy-python-django.html)
- [AWS RDS Documentation](https://docs.aws.amazon.com/rds/)
- [AWS S3 Documentation](https://docs.aws.amazon.com/s3/)

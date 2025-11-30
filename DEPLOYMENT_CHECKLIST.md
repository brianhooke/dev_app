# AWS Deployment Checklist

## Pre-Deployment

### 1. Environment Variables Ready
- [ ] Have all required credentials documented (see DEPLOYMENT_GUIDE.md)
- [ ] Create `.env.production` file locally (temporary, will be deleted)
- [ ] Add all variables from `.env.example` with production values
- [ ] Generate new `SECRET_KEY` for production (never reuse dev key)
- [ ] Verify RDS endpoint and credentials
- [ ] Verify S3 bucket name and region
- [ ] Verify email credentials (test Office 365 login)
- [ ] Verify Xero OAuth credentials

### 2. Code Preparation
- [ ] All migrations created (`python manage.py makemigrations`)
- [ ] Migrations tested locally
- [ ] Static files collected (`python manage.py collectstatic`)
- [ ] No debug code or print statements in production code
- [ ] `DEBUG = False` in production_aws.py
- [ ] `ALLOWED_HOSTS` configured correctly
- [ ] All dependencies in `requirements.txt`

### 3. Database
- [ ] RDS instance created and running
- [ ] Security group allows EB instance access
- [ ] Database initialized (if first deployment)
- [ ] Backup strategy in place

### 4. S3 Bucket
- [ ] S3 bucket created
- [ ] CORS configuration set (if needed)
- [ ] IAM user/role has S3 access
- [ ] Bucket policy configured

---

## Deployment Steps

### 1. Set Environment Variables

**Option A: Using EB CLI (Recommended)**
```bash
# From project root
eb setenv $(cat .env.production | xargs)

# Verify
eb printenv

# Delete the temp file immediately!
rm .env.production
```

**Option B: Using AWS Console**
1. Go to Elastic Beanstalk → Your Environment
2. Configuration → Software → Edit
3. Add all environment properties manually
4. Click Apply

### 2. Deploy Application
```bash
# Make sure you're on the right branch
git status

# Deploy
eb deploy

# Monitor deployment
eb status
```

### 3. Run Migrations
```bash
# SSH into instance
eb ssh

# Navigate to app directory
cd /var/app/current

# Activate virtual environment
source /var/app/venv/*/bin/activate

# Run migrations
python manage.py migrate

# Create superuser (if needed)
python manage.py createsuperuser

# Exit SSH
exit
```

### 4. Verify Deployment
```bash
# Check application logs
eb logs

# Open application in browser
eb open

# Test key functionality:
```
- [ ] Homepage loads
- [ ] Admin login works
- [ ] Database reads/writes work
- [ ] Media files upload to S3
- [ ] Static files load correctly
- [ ] Emails send successfully
- [ ] Xero integration works

---

## Post-Deployment

### Security Hardening
- [ ] Update `ALLOWED_HOSTS` to specific domains (remove `'*'`)
- [ ] Enable HTTPS certificate (AWS Certificate Manager)
- [ ] Set `CSRF_COOKIE_SECURE = True`
- [ ] Set `SESSION_COOKIE_SECURE = True`
- [ ] Set `SECURE_SSL_REDIRECT = True`
- [ ] Review IAM role permissions (principle of least privilege)
- [ ] Enable MFA on AWS root account
- [ ] Set up CloudWatch alarms for errors

### Monitoring Setup
- [ ] Configure CloudWatch logs
- [ ] Set up error alerting
- [ ] Monitor RDS performance metrics
- [ ] Monitor S3 bucket usage
- [ ] Set up cost alerts

### Backup Strategy
- [ ] Enable automated RDS backups
- [ ] Configure S3 versioning for media files
- [ ] Document restore procedure
- [ ] Test restore process

---

## Common Post-Deployment Issues

### Static Files Not Loading
```bash
# Collect static files
python manage.py collectstatic --noinput

# Check S3 bucket permissions
aws s3 ls s3://your-bucket-name/static/
```

### Database Connection Errors
```bash
# Verify environment variables
eb printenv | grep RDS

# Check RDS security group
# Ensure EB security group is allowed

# Test connection from EB instance
eb ssh
telnet $RDS_HOSTNAME $RDS_PORT
```

### Email Not Sending
```bash
# Verify email credentials
eb printenv | grep EMAIL

# Test Office 365 login manually
# Check if 2FA/app passwords required
```

### Migrations Fail
```bash
# SSH into instance
eb ssh

# Check migration status
cd /var/app/current
source /var/app/venv/*/bin/activate
python manage.py showmigrations

# If needed, fake migrations
python manage.py migrate --fake <app_name> <migration_number>
```

---

## Rollback Procedure

If deployment fails:

```bash
# List previous versions
eb appversion

# Restore previous version
eb deploy --version <version-label>

# Or use AWS Console:
# EB → Application Versions → Deploy previous version
```

---

## Environment Variable Updates

To update a single variable without redeploying code:

```bash
# Update variable
eb setenv EMAIL_HOST_PASSWORD=new-password

# Verify change
eb printenv | grep EMAIL_HOST_PASSWORD
```

The environment will automatically restart.

---

## Migration to Secrets Manager (Optional - Enhanced Security)

After initial deployment, migrate sensitive variables:

```bash
# 1. Store secret in Secrets Manager
aws secretsmanager create-secret \
  --name dev-app/email-password \
  --secret-string "your-password" \
  --region us-east-1

# 2. Update production_aws.py to read from Secrets Manager
# (See DEPLOYMENT_GUIDE.md for code examples)

# 3. Remove from EB environment variables
eb setenv EMAIL_HOST_PASSWORD=""

# 4. Redeploy
eb deploy
```

---

## Useful Commands Reference

```bash
# View environment status
eb status

# View recent logs
eb logs

# View logs in real-time
eb logs --stream

# SSH into instance
eb ssh

# List environment variables
eb printenv

# Set environment variable
eb setenv KEY=VALUE

# Deploy application
eb deploy

# Open app in browser
eb open

# Terminate environment (careful!)
eb terminate

# Restart application
eb restart
```

---

## Emergency Contacts & Resources

- **AWS Support:** Console → Support → Create Case
- **Elastic Beanstalk Docs:** https://docs.aws.amazon.com/elasticbeanstalk/
- **Django Deployment Checklist:** https://docs.djangoproject.com/en/stable/howto/deployment/checklist/
- **Your RDS Endpoint:** [Document here]
- **Your S3 Bucket:** [Document here]
- **On-call Engineer:** [Contact info]

---

## Version History

| Date | Version | Changes | Deployed By |
|------|---------|---------|-------------|
| 2024-12-01 | 1.0.0 | Initial deployment | [Your Name] |
| | | Added Units management | |
| | | Converted Costing.unit to FK | |

---

**Last Updated:** 2024-12-01
**Next Review:** [Set date]

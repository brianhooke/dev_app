"""
AWS Elastic Beanstalk Production Settings

This configuration is for AWS deployment using:
- Elastic Beanstalk for application hosting
- RDS for PostgreSQL database
- S3 for static and media files
- Environment variables for sensitive configuration
"""

import os
from django.core.exceptions import ImproperlyConfigured
from .base import *

DEBUG = False


def _required_env(name):
    """Return os.environ[name] or raise a startup error.

    Used to refuse to boot in production when a secret env var is missing
    rather than silently fall back to a baked-in default.
    """
    value = os.environ.get(name)
    if not value:
        raise ImproperlyConfigured(
            f"Production setting requires env var {name!r} to be set "
            f"(see DEPLOYMENT_GUIDE.md / SECRET_ROTATION_RUNBOOK.md)."
        )
    return value


# Hard-required production secrets. Any missing value blocks startup.
SECRET_KEY = _required_env('SECRET_KEY')
XERO_ENCRYPTION_KEY = _required_env('XERO_ENCRYPTION_KEY')
EMAIL_API_SECRET_KEY = _required_env('EMAIL_API_SECRET_KEY')

# Security Settings
# ELB health checks are handled by CanonicalHostRedirectMiddleware
ALLOWED_HOSTS = [
    'app.mason.build',  # Production domain
    '.elasticbeanstalk.com',  # AWS Elastic Beanstalk domain
    '.us-east-1.elb.amazonaws.com',  # ELB domain
    'localhost',
    '127.0.0.1',
]

# Security settings - HTTPS enabled via ALB
CSRF_COOKIE_SECURE = True  # Secure cookies over HTTPS
SESSION_COOKIE_SECURE = True  # Secure cookies over HTTPS
SECURE_SSL_REDIRECT = False  # ALB handles HTTPS redirect, not Django
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')  # Trust ALB's X-Forwarded-Proto
X_FRAME_OPTIONS = 'DENY'

# HSTS - tell browsers to talk HTTPS only. Start with a 1-day window so a
# misconfiguration is recoverable, then bump to a year + preload once you're
# confident HTTPS is working everywhere (including any subdomains).
SECURE_HSTS_SECONDS = 86400  # 1 day; raise to 31536000 (1 yr) when stable
SECURE_HSTS_INCLUDE_SUBDOMAINS = False  # flip to True after testing subdomains
SECURE_HSTS_PRELOAD = False  # flip to True only when ready for hstspreload.org

# Session Configuration for OAuth flows
SESSION_ENGINE = 'django.contrib.sessions.backends.db'  # Database-backed sessions
SESSION_COOKIE_AGE = 3600  # 1 hour (enough for OAuth flow)
SESSION_SAVE_EVERY_REQUEST = True  # Ensure session is saved on every request
SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to session cookie
SESSION_COOKIE_SAMESITE = 'Lax'  # Allow OAuth redirects to work

# Database - AWS RDS PostgreSQL
# Configure via environment variables in Elastic Beanstalk
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('RDS_DB_NAME'),
        'USER': os.getenv('RDS_USERNAME'),
        'PASSWORD': os.getenv('RDS_PASSWORD'),
        'HOST': os.getenv('RDS_HOSTNAME'),
        'PORT': os.getenv('RDS_PORT', '5432'),
    }
}

# AWS S3 Settings for Static and Media Files
AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'us-east-1')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')

# S3 Configuration
AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
AWS_DEFAULT_ACL = None
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',  # 1 day cache
}

# Static Files (CSS, JavaScript, Images)
# Serve from local filesystem (baked into Docker image) - more reliable than S3
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = '/static/'

# WhiteNoise + content-hash filenames so cache-busting is automatic on every
# deploy. `CompressedManifestStaticFilesStorage` writes a manifest mapping
# logical name -> hashed name and rejects {% static %} references that don't
# resolve, which catches stale references at deploy time instead of in the
# browser. Run `manage.py collectstatic` during container start (start.sh).
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
# Don't 500 the whole page if a single asset is missing from the manifest;
# log a warning instead. (Production still rejects writes outside STATIC_ROOT.)
WHITENOISE_MANIFEST_STRICT = False

# Media Files (User Uploads)
AWS_MEDIA_LOCATION = 'media'
MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/{AWS_MEDIA_LOCATION}/'
DEFAULT_FILE_STORAGE = 'dev_app.storagebackends.MyS3Boto3Storage'

# Project-specific paths
PROJECT_NAME = os.getenv('PROJECT_NAME')
LETTERHEAD_PATH = os.getenv('LETTERHEAD_PATH')
BACKGROUND_IMAGE_PATH = os.getenv('BACKGROUND_IMAGE_PATH', '')

# Email Configuration (Office 365)
EMAIL_BACKEND = 'dev_app.email_backends.CustomEmailBackend'
EMAIL_HOST = 'smtp.office365.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL')
EMAIL_CC = os.getenv('EMAIL_CC')

# Xero API Configuration
XERO_CLIENT_ID = os.getenv('XERO_CLIENT_ID')
XERO_CLIENT_SECRET = os.getenv('XERO_CLIENT_SECRET')
XERO_PROJECT_ID = os.getenv('XERO_PROJECT_ID')

# Mason Build Xero Credentials
MB_XERO_CLIENT_ID = os.getenv('MB_XERO_CLIENT_ID')
MB_XERO_CLIENT_SECRET = os.getenv('MB_XERO_CLIENT_SECRET')

# MDG Xero Credentials
MDG_XERO_CLIENT_ID = os.getenv('MDG_XERO_CLIENT_ID')
MDG_XERO_CLIENT_SECRET = os.getenv('MDG_XERO_CLIENT_SECRET')

# Logging Configuration for AWS
# File logging is configured in .ebextensions to create /var/log/django directory
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# File logging will be added by Elastic Beanstalk after directory creation
# Uncomment after deployment when /var/log/django exists:
# LOGGING['handlers']['file'] = {
#     'class': 'logging.handlers.RotatingFileHandler',
#     'filename': '/var/log/django/app.log',
#     'maxBytes': 1024 * 1024 * 10,  # 10 MB
#     'backupCount': 5,
#     'formatter': 'verbose',
# }
# LOGGING['root']['handlers'].append('file')
# LOGGING['loggers']['django']['handlers'].append('file')

# AWS Elastic Beanstalk Health Check
# Add this to your urls.py if needed:
# path('health/', lambda request: HttpResponse('OK'), name='health_check')

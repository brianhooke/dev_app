"""
AWS Elastic Beanstalk Production Settings

This configuration is for AWS deployment using:
- Elastic Beanstalk for application hosting
- RDS for PostgreSQL database
- S3 for static and media files
- Environment variables for sensitive configuration
"""

import os
from .base import *

DEBUG = False

# Override SECRET_KEY from base.py
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-z5h6c!k&m&6stz@jml@d@v19=!c0)zfeej2^p9!t+lf+!x6ut7')

# Security Settings
ALLOWED_HOSTS = [
    '.elasticbeanstalk.com',  # AWS Elastic Beanstalk domain
    '*',  # Temporary for initial deployment
]

# Security settings - temporarily relaxed for initial deployment
CSRF_COOKIE_SECURE = False  # Set to True after HTTPS is configured
SESSION_COOKIE_SECURE = False  # Set to True after HTTPS is configured
SECURE_SSL_REDIRECT = False  # Set to True after HTTPS is configured
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

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
AWS_STATIC_LOCATION = 'static'
STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/{AWS_STATIC_LOCATION}/'
STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

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

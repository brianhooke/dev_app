import os
from .base import *

DEBUG = False

# # AWS S3 Settingss
AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME') #Media_root is this + location in storage backends
# AWS_STORAGE_BUCKET_NAME = 'devappbucket2' #Media_root is this + location in storage backends
# AWS_STORAGE_BUCKET_NAME = '41accoladedevbucket' #Media_root is this + location in storage backends
# AWS_STORAGE_BUCKET_NAME = 'spitfirebucket' #Media_root is this + location in storage backends
# AWS_STORAGE_BUCKET_NAME = 'tareebucket' #Media_root is this + location in storage backends
# AWS_STORAGE_BUCKET_NAME = 'tinnulabucket' #Media_root is this + location in storage backends

AWS_S3_CUSTOM_DOMAIN = os.getenv('AWS_S3_CUSTOM_DOMAIN')
# AWS_S3_CUSTOM_DOMAIN = f'devappbucket2.s3.amazonaws.com'
# AWS_S3_CUSTOM_DOMAIN = f'41accoladedevbucket.s3.amazonaws.com'
# AWS_S3_CUSTOM_DOMAIN = f'spitfirebucket.s3.amazonaws.com'
# AWS_S3_CUSTOM_DOMAIN = f'tareebucket.s3.amazonaws.com'
# AWS_S3_CUSTOM_DOMAIN = f'tinnulabucket.s3.amazonaws.com'

STATIC_URL = os.getenv('STATIC_URL')
# STATIC_URL = f'https://devappbucket2.s3.amazonaws.com/static/'
# STATIC_URL = f'https://41accoladedevbucket.s3.amazonaws.com/static/'
# STATIC_URL = f'https://spitfirebucket.s3.amazonaws.com/static/'
# STATIC_URL = f'https://tareebucket.s3.amazonaws.com/static/'
# STATIC_URL = f'https://tinnulabucket.s3.amazonaws.com/static/'


AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_DEFAULT_ACL = None
AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}
AWS_STATIC_LOCATION = 'static'
PROJECT_NAME = os.getenv('PROJECT_NAME')
STATIC_ROOT = os.getenv('STATIC_ROOT')
STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
DEFAULT_FILE_STORAGE = 'dev_app.storagebackends.MyS3Boto3Storage'
MEDIA_URL = f'https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/'
MEDIA_ROOT = os.getenv('MEDIA_ROOT')
AWS_S3_REGION_NAME = 'us-east-1'
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
# AWS_PUBLIC_MEDIA_LOCATION = ''

EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
LETTERHEAD_PATH = os.getenv('LETTERHEAD_PATH')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL')
EMAIL_CC = os.getenv('EMAIL_CC')

XERO_CLIENT_ID=os.getenv('XERO_CLIENT_ID') #can delete when MB_ and MDG_ same are integrated
XERO_CLIENT_SECRET=os.getenv('XERO_CLIENT_SECRET') #can delete when MB_ and MDG_ same are integrated
XERO_PROJECT_ID=os.getenv('XERO_PROJECT_ID')

MB_XERO_CLIENT_ID=os.getenv('MB_XERO_CLIENT_ID')
MB_XERO_CLIENT_SECRET=os.getenv('MB_XERO_CLIENT_SECRET')

MDG_XERO_CLIENT_ID=os.getenv('MDG_XERO_CLIENT_ID')
MDG_XERO_CLIENT_SECRET=os.getenv('MDG_XERO_CLIENT_SECRET')
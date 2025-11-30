from .base import *
import environ

# Read .env file (if it exists)
env = environ.Env()
env_file = os.path.join(BASE_DIR, '.env')
if os.path.exists(env_file):
    environ.Env.read_env(env_file)

DEBUG = True

# Database - PostgreSQL if RDS credentials are set, otherwise SQLite
if os.environ.get('RDS_HOSTNAME'):
    # Use PostgreSQL (AWS RDS)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('RDS_DB_NAME', 'devappdb'),
            'USER': os.environ.get('RDS_USERNAME', 'devappmaster'),
            'PASSWORD': os.environ.get('RDS_PASSWORD'),
            'HOST': os.environ.get('RDS_HOSTNAME'),
            'PORT': os.environ.get('RDS_PORT', '5432'),
            'CONN_MAX_AGE': 600,  # Connection pooling
            'OPTIONS': {
                'connect_timeout': 10,
            }
        }
    }
else:
    # Use SQLite (local development)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        }
    }

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = '/static/'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'
PROJECT_NAME = '123 Fake Street'
LETTERHEAD_PATH = os.path.join(MEDIA_ROOT, 'letterhead/letterhead.pdf')
BACKGROUND_IMAGE_PATH = os.path.join(MEDIA_ROOT, 'backgrounds', 'my_bg.jpg')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# Email Configuration - Read from environment variables or .env file
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'purchase_orders@mason.build')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')  # MUST be set in .env file
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'purchase_orders@mason.build')
EMAIL_CC = os.environ.get('EMAIL_CC', 'brian.hooke@mason.build')

# fake xero settings
XERO_CLIENT_ID=''
XERO_CLIENT_SECRET=''
XERO_PROJECT_ID='9_tinnula' #for Mason Build tracking category
# XERO_MDG_ACCOUNT_ID=4 #for MDG account to put invoices in, eg Loan-Taree

MB_XERO_CLIENT_ID= ''
MB_XERO_CLIENT_SECRET= ''

MDG_XERO_CLIENT_ID=''
MDG_XERO_CLIENT_SECRET=''
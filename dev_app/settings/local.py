from .base import *
# import environ

# env = environ.Env()
# environ.Env.read_env()

DEBUG = True

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

EMAIL_HOST_USER = 'invoices@mason.build'
# EMAIL_HOST_PASSWORD = 'password'
DEFAULT_FROM_EMAIL = 'invoices@mason.build'

# fake xero settings
XERO_CLIENT_ID=''
XERO_CLIENT_SECRET=''
XERO_PROJECT_ID='9_tinnula' #for Mason Build tracking category
# XERO_MDG_ACCOUNT_ID=4 #for MDG account to put invoices in, eg Loan-Taree

MB_XERO_CLIENT_ID= ''
MB_XERO_CLIENT_SECRET= ''

MDG_XERO_CLIENT_ID=''
MDG_XERO_CLIENT_SECRET=''
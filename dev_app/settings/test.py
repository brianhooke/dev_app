"""
Test settings for Playwright E2E tests.
Uses a separate SQLite database to avoid modifying production data.
"""

from .local import *

# Use separate test database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db_test.sqlite3'),
    }
}

# Disable debug toolbar and other dev tools during tests
DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': lambda request: False,
}

# Speed up password hashing for tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Use console email backend for tests
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Test-specific media root
MEDIA_ROOT = os.path.join(BASE_DIR, 'media_test')

# Logging - show errors but reduce noise
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
        'level': 'WARNING',  # Only show warnings and errors
    },
}

print("=" * 60)
print("🧪 RUNNING IN TEST MODE")
print(f"📁 Test Database: {DATABASES['default']['NAME']}")
print(f"📁 Test Media: {MEDIA_ROOT}")
print("=" * 60)

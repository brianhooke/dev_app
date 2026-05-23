"""
Test settings for Playwright E2E tests + Django unit tests.
Uses a separate SQLite database to avoid modifying production data.

Audit note (F.Q-C-05): Django's normal test runner cannot build a fresh
test DB by replaying migrations because the historical migration set has
ordering-vs-current-models mismatches (the squash & db_table cleanup is
the eventual fix). Until then we sidestep the test runner's migrate step
by setting ``MIGRATION_MODULES`` to ``None`` for every app, which makes
``manage.py test --keepdb`` create tables straight from the current model
state via ``syncdb``. The on-disk ``db_test.sqlite3`` is still used as
the connection target so contributors can inspect post-test state, but
the schema served to tests is always derived from ``models.py``.
"""

from .local import *

# Use separate test database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db_test.sqlite3'),
    }
}


class _DisableMigrations:
    """Make every ``MIGRATION_MODULES[app]`` lookup return ``None``.

    Django interprets ``None`` as "no migration module for this app", so
    ``migrate --run-syncdb`` (which the test runner triggers under the
    hood for ``--keepdb``) creates tables from current model state.
    """

    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = _DisableMigrations()

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

# Use same media folder as local environment (not separate media_test)
# MEDIA_ROOT and MEDIA_URL are inherited from local.py

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
print(f"📁 Media Folder: {MEDIA_ROOT}")
print("=" * 60)

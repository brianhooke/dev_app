"""
Bootstrap an admin superuser on first deploy.

Usage: python manage.py create_admin

Reads DJANGO_SUPERUSER_USERNAME / _EMAIL / _PASSWORD from env. Only creates
the user when the username doesn't exist yet — this command will NOT reset
the password on subsequent runs. To rotate the password, do it via the
Django admin or `manage.py changepassword`.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
import os


class Command(BaseCommand):
    help = 'Create an admin superuser only if it does not already exist (idempotent)'

    def handle(self, *args, **options):
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', '').strip()
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '').strip()
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')

        if not username or not password:
            self.stdout.write(self.style.WARNING(
                'DJANGO_SUPERUSER_USERNAME or DJANGO_SUPERUSER_PASSWORD not set; skipping bootstrap.'
            ))
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.NOTICE(
                f'Superuser "{username}" already exists; not touching it.'
            ))
            return

        User.objects.create_superuser(
            username=username,
            email=email or f'{username}@example.invalid',
            password=password,
        )
        self.stdout.write(self.style.SUCCESS(f'Superuser "{username}" created.'))

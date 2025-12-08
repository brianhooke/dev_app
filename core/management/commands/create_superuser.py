from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os


class Command(BaseCommand):
    help = 'Create a superuser from environment variables'

    def handle(self, *args, **options):
        User = get_user_model()
        
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'bh')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@mason.build')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        
        if not password:
            self.stderr.write(self.style.ERROR('DJANGO_SUPERUSER_PASSWORD environment variable is required'))
            return
        
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'User "{username}" already exists. Updating password...'))
            user = User.objects.get(username=username)
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Password updated for user "{username}"'))
        else:
            User.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f'Superuser "{username}" created successfully'))

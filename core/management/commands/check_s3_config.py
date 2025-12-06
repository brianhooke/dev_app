"""
Management command to diagnose S3 media storage configuration.
Run with: python manage.py check_s3_config
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import os


class Command(BaseCommand):
    help = 'Check S3 media storage configuration and test upload/download'

    def handle(self, *args, **options):
        self.stdout.write("=" * 60)
        self.stdout.write("S3 MEDIA STORAGE DIAGNOSTIC")
        self.stdout.write("=" * 60)
        
        # Check environment
        self.stdout.write("\n--- Environment ---")
        self.stdout.write(f"Running in Docker (/app exists): {os.path.exists('/app')}")
        self.stdout.write(f"AWS_STORAGE_BUCKET_NAME env: {os.environ.get('AWS_STORAGE_BUCKET_NAME', 'NOT SET')}")
        self.stdout.write(f"AWS_ACCESS_KEY_ID env: {'SET' if os.environ.get('AWS_ACCESS_KEY_ID') else 'NOT SET'}")
        self.stdout.write(f"AWS_SECRET_ACCESS_KEY env: {'SET' if os.environ.get('AWS_SECRET_ACCESS_KEY') else 'NOT SET'}")
        
        # Check Django settings
        self.stdout.write("\n--- Django Settings ---")
        self.stdout.write(f"DEFAULT_FILE_STORAGE: {getattr(settings, 'DEFAULT_FILE_STORAGE', 'NOT SET (using default)')}")
        self.stdout.write(f"MEDIA_URL: {settings.MEDIA_URL}")
        self.stdout.write(f"MEDIA_ROOT: {settings.MEDIA_ROOT or '(empty - using S3)'}")
        self.stdout.write(f"AWS_STORAGE_BUCKET_NAME: {getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'NOT SET')}")
        self.stdout.write(f"AWS_S3_REGION_NAME: {getattr(settings, 'AWS_S3_REGION_NAME', 'NOT SET')}")
        self.stdout.write(f"AWS_S3_CUSTOM_DOMAIN: {getattr(settings, 'AWS_S3_CUSTOM_DOMAIN', 'NOT SET')}")
        self.stdout.write(f"AWS_MEDIA_LOCATION: {getattr(settings, 'AWS_MEDIA_LOCATION', 'NOT SET')}")
        
        # Check storage backend
        self.stdout.write("\n--- Storage Backend ---")
        storage = default_storage
        self.stdout.write(f"Storage class: {storage.__class__.__name__}")
        self.stdout.write(f"Storage module: {storage.__class__.__module__}")
        
        if hasattr(storage, 'bucket_name'):
            self.stdout.write(f"Bucket name: {storage.bucket_name}")
        if hasattr(storage, 'location'):
            self.stdout.write(f"Location prefix: {storage.location}")
        if hasattr(storage, 'base_url'):
            self.stdout.write(f"Base URL: {storage.base_url}")
        
        # Test upload
        self.stdout.write("\n--- Test Upload ---")
        test_filename = 'test_s3_diagnostic.txt'
        test_content = f'S3 diagnostic test file - {os.environ.get("HOSTNAME", "unknown")}'
        
        try:
            # Save test file
            path = default_storage.save(test_filename, ContentFile(test_content.encode()))
            self.stdout.write(self.style.SUCCESS(f"✓ Upload successful: {path}"))
            
            # Get URL
            url = default_storage.url(path)
            self.stdout.write(f"  URL: {url}")
            
            # Check if file exists
            exists = default_storage.exists(path)
            self.stdout.write(f"  Exists check: {exists}")
            
            # Read back
            try:
                with default_storage.open(path, 'r') as f:
                    content = f.read()
                self.stdout.write(self.style.SUCCESS(f"✓ Read successful: {content[:50]}..."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Read failed: {e}"))
            
            # Clean up
            try:
                default_storage.delete(path)
                self.stdout.write(self.style.SUCCESS("✓ Delete successful"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"⚠ Delete failed: {e}"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Upload failed: {e}"))
            import traceback
            self.stdout.write(traceback.format_exc())
        
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("DIAGNOSTIC COMPLETE")
        self.stdout.write("=" * 60)

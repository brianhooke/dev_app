"""
Management command to migrate existing local media files to S3.
Run this BEFORE deploying to preserve uploaded files.

Usage:
    # SSH into AWS instance
    docker exec $(docker ps -q) python manage.py migrate_media_to_s3
    
    # Or with dry run first
    docker exec $(docker ps -q) python manage.py migrate_media_to_s3 --dry-run
"""

import os
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db.models import Q
import boto3
from botocore.exceptions import ClientError


class Command(BaseCommand):
    help = 'Migrate local media files to S3 and update database paths'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without actually doing it',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Check S3 configuration
        bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None)
        if not bucket_name:
            self.stderr.write(self.style.ERROR('AWS_STORAGE_BUCKET_NAME not configured'))
            return
        
        aws_access_key = getattr(settings, 'AWS_ACCESS_KEY_ID', None)
        aws_secret_key = getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
        aws_region = getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
        media_location = getattr(settings, 'AWS_MEDIA_LOCATION', 'media')
        
        if not aws_access_key or not aws_secret_key:
            self.stderr.write(self.style.ERROR('AWS credentials not configured'))
            return
        
        # Initialize S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region
        )
        
        self.stdout.write(f'S3 Bucket: {bucket_name}')
        self.stdout.write(f'Media Location: {media_location}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Find and migrate files from various models
        migrated = 0
        errors = 0
        
        # Import models that have file fields
        from core.models import Bills, Quotes, Po_orders
        
        # Migrate Invoice PDFs
        self.stdout.write('\n--- Migrating Invoice PDFs ---')
        for invoice in Bills.objects.exclude(Q(attachment_url__isnull=True) | Q(attachment_url='')):
            url = invoice.attachment_url
            if url and url.startswith('/media/') or (url and 'pdfs/' in url and not url.startswith('http')):
                result = self.migrate_file(s3_client, bucket_name, media_location, url, dry_run)
                if result:
                    if not dry_run:
                        invoice.attachment_url = result
                        invoice.save(update_fields=['attachment_url'])
                    migrated += 1
                else:
                    errors += 1
        
        # Migrate Quote PDFs
        self.stdout.write('\n--- Migrating Quote PDFs ---')
        for quote in Quotes.objects.exclude(Q(pdf_url__isnull=True) | Q(pdf_url='')):
            url = quote.pdf_url
            if url and url.startswith('/media/') or (url and 'pdfs/' in url and not url.startswith('http')):
                result = self.migrate_file(s3_client, bucket_name, media_location, url, dry_run)
                if result:
                    if not dry_run:
                        quote.pdf_url = result
                        quote.save(update_fields=['pdf_url'])
                    migrated += 1
                else:
                    errors += 1
        
        # Summary
        self.stdout.write('\n--- Migration Summary ---')
        self.stdout.write(f'Files migrated: {migrated}')
        self.stdout.write(f'Errors: {errors}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nThis was a dry run. Run without --dry-run to actually migrate.'))
        else:
            self.stdout.write(self.style.SUCCESS('\nMigration complete!'))

    def migrate_file(self, s3_client, bucket_name, media_location, url, dry_run):
        """Upload a local file to S3 and return the new URL."""
        # Extract local file path
        if url.startswith('/media/'):
            local_path = url.replace('/media/', '')
        else:
            local_path = url
        
        # Build full local path
        local_file = os.path.join('/app/media', local_path)
        
        # Check if local file exists
        if not os.path.exists(local_file):
            self.stdout.write(f'  SKIP (not found): {local_file}')
            return None
        
        # S3 key
        s3_key = f'{media_location}/{local_path}'
        
        # New URL
        new_url = f'https://{bucket_name}.s3.amazonaws.com/{s3_key}'
        
        self.stdout.write(f'  {url}')
        self.stdout.write(f'    -> {new_url}')
        
        if dry_run:
            return new_url
        
        # Upload to S3
        try:
            s3_client.upload_file(
                local_file,
                bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': 'application/pdf',
                    'CacheControl': 'max-age=86400'
                }
            )
            return new_url
        except ClientError as e:
            self.stderr.write(f'    ERROR: {e}')
            return None

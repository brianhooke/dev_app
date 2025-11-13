from django.core.management.base import BaseCommand
from core.models import XeroInstances
from django.utils import timezone
import json
import base64


class Command(BaseCommand):
    help = 'Import Xero instances from JSON file (with encrypted credentials)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--input',
            type=str,
            default='xero_instances_export.json',
            help='Input JSON file path'
        )
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update existing instances instead of creating new ones'
        )

    def handle(self, *args, **options):
        input_file = options['input']
        update_existing = options['update']
        
        try:
            with open(input_file, 'r') as f:
                import_data = json.load(f)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'File not found: {input_file}'))
            return
        except json.JSONDecodeError:
            self.stdout.write(self.style.ERROR(f'Invalid JSON in file: {input_file}'))
            return
        
        if not import_data:
            self.stdout.write(self.style.WARNING('No data to import'))
            return
        
        imported_count = 0
        updated_count = 0
        
        for data in import_data:
            # Check if instance already exists
            existing = XeroInstances.objects.filter(xero_instance_pk=data['xero_instance_pk']).first()
            
            if existing and not update_existing:
                self.stdout.write(self.style.WARNING(f"Instance '{data['xero_name']}' (ID: {data['xero_instance_pk']}) already exists. Use --update to overwrite."))
                continue
            
            # Decode base64 encrypted fields
            xero_client_secret_encrypted = base64.b64decode(data['xero_client_secret_encrypted']) if data['xero_client_secret_encrypted'] else None
            oauth_access_token_encrypted = base64.b64decode(data['oauth_access_token_encrypted']) if data['oauth_access_token_encrypted'] else None
            oauth_refresh_token_encrypted = base64.b64decode(data['oauth_refresh_token_encrypted']) if data['oauth_refresh_token_encrypted'] else None
            oauth_token_expires_at = timezone.datetime.fromisoformat(data['oauth_token_expires_at']) if data['oauth_token_expires_at'] else None
            
            if existing:
                # Update existing instance
                existing.xero_name = data['xero_name']
                existing.xero_client_id = data['xero_client_id']
                existing.xero_client_secret_encrypted = xero_client_secret_encrypted
                existing.oauth_access_token_encrypted = oauth_access_token_encrypted
                existing.oauth_refresh_token_encrypted = oauth_refresh_token_encrypted
                existing.oauth_token_expires_at = oauth_token_expires_at
                existing.oauth_tenant_id = data['oauth_tenant_id']
                existing.save()
                updated_count += 1
                self.stdout.write(self.style.SUCCESS(f"Updated: {data['xero_name']} (ID: {data['xero_instance_pk']})"))
            else:
                # Create new instance
                instance = XeroInstances(
                    xero_instance_pk=data['xero_instance_pk'],
                    xero_name=data['xero_name'],
                    xero_client_id=data['xero_client_id'],
                    xero_client_secret_encrypted=xero_client_secret_encrypted,
                    oauth_access_token_encrypted=oauth_access_token_encrypted,
                    oauth_refresh_token_encrypted=oauth_refresh_token_encrypted,
                    oauth_token_expires_at=oauth_token_expires_at,
                    oauth_tenant_id=data['oauth_tenant_id'],
                )
                instance.save()
                imported_count += 1
                self.stdout.write(self.style.SUCCESS(f"Imported: {data['xero_name']} (ID: {data['xero_instance_pk']})"))
        
        if imported_count > 0:
            self.stdout.write(self.style.SUCCESS(f'\nSuccessfully imported {imported_count} new Xero instance(s)'))
        if updated_count > 0:
            self.stdout.write(self.style.SUCCESS(f'Successfully updated {updated_count} existing Xero instance(s)'))

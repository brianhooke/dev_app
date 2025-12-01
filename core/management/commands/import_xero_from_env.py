from django.core.management.base import BaseCommand
from core.models import XeroInstances
from django.utils import timezone
import json
import base64
import os


class Command(BaseCommand):
    help = 'Import Xero instances from XERO_DATA environment variable'

    def handle(self, *args, **options):
        xero_data_b64 = os.environ.get('XERO_DATA')
        
        if not xero_data_b64:
            self.stdout.write(self.style.WARNING('XERO_DATA environment variable not set - skipping Xero import'))
            return
        
        try:
            # Decode base64 to get JSON string
            xero_data_json = base64.b64decode(xero_data_b64).decode('utf-8')
            import_data = json.loads(xero_data_json)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to decode XERO_DATA: {e}'))
            return
        
        if not import_data:
            self.stdout.write(self.style.WARNING('No Xero data to import'))
            return
        
        imported_count = 0
        updated_count = 0
        
        for data in import_data:
            # Check if instance already exists
            existing = XeroInstances.objects.filter(xero_instance_pk=data['xero_instance_pk']).first()
            
            # Decode base64 encrypted fields
            xero_client_secret_encrypted = base64.b64decode(data['xero_client_secret_encrypted']) if data.get('xero_client_secret_encrypted') else None
            oauth_access_token_encrypted = base64.b64decode(data['oauth_access_token_encrypted']) if data.get('oauth_access_token_encrypted') else None
            oauth_refresh_token_encrypted = base64.b64decode(data['oauth_refresh_token_encrypted']) if data.get('oauth_refresh_token_encrypted') else None
            oauth_token_expires_at = timezone.datetime.fromisoformat(data['oauth_token_expires_at']) if data.get('oauth_token_expires_at') else None
            
            if existing:
                # Update existing instance
                existing.xero_name = data['xero_name']
                existing.xero_client_id = data['xero_client_id']
                existing.xero_client_secret_encrypted = xero_client_secret_encrypted
                existing.oauth_access_token_encrypted = oauth_access_token_encrypted
                existing.oauth_refresh_token_encrypted = oauth_refresh_token_encrypted
                existing.oauth_token_expires_at = oauth_token_expires_at
                existing.oauth_tenant_id = data.get('oauth_tenant_id')
                existing.save()
                updated_count += 1
                self.stdout.write(f"Updated: {data['xero_name']} (ID: {data['xero_instance_pk']})")
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
                    oauth_tenant_id=data.get('oauth_tenant_id'),
                )
                instance.save()
                imported_count += 1
                self.stdout.write(f"Imported: {data['xero_name']} (ID: {data['xero_instance_pk']})")
        
        if imported_count > 0:
            self.stdout.write(self.style.SUCCESS(f'Imported {imported_count} new Xero instance(s)'))
        if updated_count > 0:
            self.stdout.write(self.style.SUCCESS(f'Updated {updated_count} existing Xero instance(s)'))
        if imported_count == 0 and updated_count == 0:
            self.stdout.write(self.style.SUCCESS('Xero instances already up to date'))

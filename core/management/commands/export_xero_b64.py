from django.core.management.base import BaseCommand
from core.models import XeroInstances
import json
import base64


class Command(BaseCommand):
    help = 'Export Xero instances as base64-encoded JSON (for XERO_DATA env var)'

    def handle(self, *args, **options):
        instances = XeroInstances.objects.all()
        
        if not instances.exists():
            self.stderr.write('No Xero instances found')
            return
        
        export_data = []
        
        for instance in instances:
            data = {
                'xero_instance_pk': instance.xero_instance_pk,
                'xero_name': instance.xero_name,
                'xero_client_id': instance.xero_client_id,
                'xero_client_secret_encrypted': base64.b64encode(instance.xero_client_secret_encrypted).decode('utf-8') if instance.xero_client_secret_encrypted else None,
                'oauth_access_token_encrypted': base64.b64encode(instance.oauth_access_token_encrypted).decode('utf-8') if instance.oauth_access_token_encrypted else None,
                'oauth_refresh_token_encrypted': base64.b64encode(instance.oauth_refresh_token_encrypted).decode('utf-8') if instance.oauth_refresh_token_encrypted else None,
                'oauth_token_expires_at': instance.oauth_token_expires_at.isoformat() if instance.oauth_token_expires_at else None,
                'oauth_tenant_id': instance.oauth_tenant_id,
            }
            export_data.append(data)
        
        # Convert to JSON and base64 encode
        json_str = json.dumps(export_data)
        b64_str = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
        
        # Output just the base64 string (for easy copy/paste)
        self.stdout.write(b64_str)

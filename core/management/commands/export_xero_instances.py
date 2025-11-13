from django.core.management.base import BaseCommand
from core.models import XeroInstances
import json
import base64


class Command(BaseCommand):
    help = 'Export Xero instances to JSON file (with encrypted credentials)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='xero_instances_export.json',
            help='Output JSON file path'
        )

    def handle(self, *args, **options):
        output_file = options['output']
        
        instances = XeroInstances.objects.all()
        
        if not instances.exists():
            self.stdout.write(self.style.WARNING('No Xero instances found to export'))
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
        
        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        self.stdout.write(self.style.SUCCESS(f'Successfully exported {len(export_data)} Xero instance(s) to {output_file}'))
        for instance in export_data:
            self.stdout.write(f"  - {instance['xero_name']} (ID: {instance['xero_instance_pk']})")

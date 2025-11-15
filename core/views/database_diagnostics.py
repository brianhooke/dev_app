"""
Database diagnostics to verify PostgreSQL connection.
"""
from django.http import JsonResponse
from django.db import connection
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def database_diagnostics(request):
    """
    Show current database configuration and connection status.
    """
    try:
        # Get database engine
        db_engine = connection.settings_dict['ENGINE']
        db_name = connection.settings_dict['NAME']
        db_host = connection.settings_dict.get('HOST', 'N/A')
        db_port = connection.settings_dict.get('PORT', 'N/A')
        db_user = connection.settings_dict.get('USER', 'N/A')
        
        # Test connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT version()" if 'postgresql' in db_engine else "SELECT sqlite_version()")
            version = cursor.fetchone()[0]
        
        # Count users to verify data
        from django.contrib.auth.models import User
        user_count = User.objects.count()
        
        # Count Xero instances
        from core.models import XeroInstances
        xero_count = XeroInstances.objects.count()
        
        return JsonResponse({
            'status': 'success',
            'database': {
                'engine': db_engine,
                'name': db_name,
                'host': db_host,
                'port': db_port,
                'user': db_user,
                'version': version,
            },
            'data': {
                'user_count': user_count,
                'xero_instances_count': xero_count,
            },
            'message': f'Connected to {"PostgreSQL" if "postgresql" in db_engine else "SQLite"}'
        }, json_dumps_params={'indent': 2})
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500, json_dumps_params={'indent': 2})

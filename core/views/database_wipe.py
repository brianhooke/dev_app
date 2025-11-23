"""
Database Wipe Functionality

DANGER: This module contains functionality to completely wipe all database tables.
Use with extreme caution - this operation is irreversible.
"""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import connection
import logging

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def wipe_database(request):
    """
    DANGER: Wipes all data from all tables except auth/admin tables.
    
    This is an irreversible operation. All project data, quotes, bills,
    contacts, and other records will be permanently deleted.
    
    Preserves:
    - Auth tables (users, permissions, groups, sessions)
    - Django admin tables (content types, migrations)
    """
    try:
        logger.warning("Database wipe requested!")
        
        # Get all table names
        with connection.cursor() as cursor:
            # Get list of all tables
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' 
                AND name NOT LIKE 'sqlite_%'
                AND name NOT LIKE 'auth_%'
                AND name NOT LIKE 'django_%'
                ORDER BY name;
            """)
            
            tables = [row[0] for row in cursor.fetchall()]
            
            logger.info(f"Tables to be wiped: {tables}")
            
            # Disable foreign key checks temporarily
            cursor.execute("PRAGMA foreign_keys = OFF;")
            
            # Delete all data from each table
            deleted_counts = {}
            for table in tables:
                try:
                    cursor.execute(f"DELETE FROM {table};")
                    deleted_counts[table] = cursor.rowcount
                    logger.info(f"Deleted {cursor.rowcount} rows from {table}")
                except Exception as e:
                    logger.error(f"Error deleting from {table}: {str(e)}")
                    deleted_counts[table] = f"Error: {str(e)}"
            
            # Re-enable foreign key checks
            cursor.execute("PRAGMA foreign_keys = ON;")
            
            # Vacuum to reclaim space
            cursor.execute("VACUUM;")
        
        logger.warning(f"Database wipe completed. Deleted from {len(deleted_counts)} tables.")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Database wiped successfully',
            'tables_wiped': len(deleted_counts),
            'details': deleted_counts
        })
        
    except Exception as e:
        logger.error(f"Error wiping database: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error wiping database: {str(e)}'
        }, status=500)

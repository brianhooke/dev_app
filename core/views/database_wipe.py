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
    
    Supports both SQLite and PostgreSQL databases.
    """
    try:
        logger.warning("Database wipe requested!")
        
        # Detect database engine
        db_engine = connection.settings_dict['ENGINE']
        is_postgres = 'postgresql' in db_engine
        is_sqlite = 'sqlite' in db_engine
        
        logger.info(f"Database engine: {db_engine}")
        
        # Get all table names
        with connection.cursor() as cursor:
            if is_postgres:
                # PostgreSQL query to get all tables
                cursor.execute("""
                    SELECT tablename FROM pg_tables 
                    WHERE schemaname = 'public'
                    AND tablename NOT LIKE 'auth_%'
                    AND tablename NOT LIKE 'django_%'
                    ORDER BY tablename;
                """)
            elif is_sqlite:
                # SQLite query to get all tables
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' 
                    AND name NOT LIKE 'sqlite_%'
                    AND name NOT LIKE 'auth_%'
                    AND name NOT LIKE 'django_%'
                    ORDER BY name;
                """)
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Unsupported database engine: {db_engine}'
                }, status=400)
            
            tables = [row[0] for row in cursor.fetchall()]
            
            logger.info(f"Tables to be wiped: {tables}")
            
            # Disable foreign key checks
            if is_postgres:
                # PostgreSQL doesn't need FK disabling for DELETE
                pass
            elif is_sqlite:
                cursor.execute("PRAGMA foreign_keys = OFF;")
            
            # Delete all data from each table
            deleted_counts = {}
            for table in tables:
                try:
                    if is_postgres:
                        # PostgreSQL - use TRUNCATE for better performance
                        cursor.execute(f"TRUNCATE TABLE {table} CASCADE;")
                        deleted_counts[table] = "Truncated"
                        logger.info(f"Truncated table {table}")
                    else:
                        # SQLite - use DELETE
                        cursor.execute(f"DELETE FROM {table};")
                        deleted_counts[table] = cursor.rowcount
                        logger.info(f"Deleted {cursor.rowcount} rows from {table}")
                except Exception as e:
                    logger.error(f"Error clearing {table}: {str(e)}")
                    deleted_counts[table] = f"Error: {str(e)}"
            
            # Re-enable foreign key checks
            if is_sqlite:
                cursor.execute("PRAGMA foreign_keys = ON;")
            
            # Vacuum to reclaim space (SQLite only)
            if is_sqlite:
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

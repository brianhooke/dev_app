from django.http import JsonResponse
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def debug_settings(request):
    """Simple endpoint to check current settings"""
    try:
        info = {
            'DJANGO_SETTINGS_MODULE': getattr(settings, 'DJANGO_SETTINGS_MODULE', 'NOT SET'),
            'DEBUG': getattr(settings, 'DEBUG', 'NOT SET'),
            'MEDIA_URL': getattr(settings, 'MEDIA_URL', 'NOT SET'),
            'DEFAULT_FILE_STORAGE': getattr(settings, 'DEFAULT_FILE_STORAGE', 'NOT SET'),
            'AWS_STORAGE_BUCKET_NAME': getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'NOT SET'),
        }
        
        logger.info(f"=== SETTINGS DEBUG ===")
        for key, value in info.items():
            logger.info(f"{key}: {value}")
        logger.info(f"=== END DEBUG ===")
        
        return JsonResponse(info)
    except Exception as e:
        logger.error(f"Error in debug_settings: {e}")
        return JsonResponse({'error': str(e)}, status=500)

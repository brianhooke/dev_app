from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings
import mimetypes

class MyS3Boto3Storage(S3Boto3Storage):
    location = getattr(settings, 'AWS_MEDIA_LOCATION', 'media')
    file_overwrite = False
    
    def get_object_parameters(self, name):
        """
        Set Content-Disposition to inline for PDFs and images so they display
        in browser instead of downloading.
        """
        params = {}
        content_type, _ = mimetypes.guess_type(name)
        
        if content_type:
            params['ContentType'] = content_type
            # Force inline display for PDFs and images
            if content_type in ['application/pdf', 'image/jpeg', 'image/png', 'image/gif', 'image/webp']:
                params['ContentDisposition'] = 'inline'
        
        return params
    
    @property
    def object_parameters(self):
        return {}
    
class StaticStorage(S3Boto3Storage):
    location = 'static'
    default_acl = 'public-read'

class PublicMediaStorage(S3Boto3Storage):
    location = '' #ie builderappbucket/media is the location we upload to.
    default_acl = 'public-read'
    file_overwrite = False

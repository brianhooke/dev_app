from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class MyS3Boto3Storage(S3Boto3Storage):
    location = getattr(settings, 'AWS_MEDIA_LOCATION', 'media')
    file_overwrite = False
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info(f"MyS3Boto3Storage initialized - bucket: {self.bucket_name}, location: {self.location}")
    
    @property
    def object_parameters(self):
        return {}
    
    def _save(self, name, content):
        logger.info(f"S3 _save called: name={name}, content_type={getattr(content, 'content_type', 'unknown')}")
        try:
            result = super()._save(name, content)
            logger.info(f"S3 _save successful: {result}")
            return result
        except Exception as e:
            logger.error(f"S3 _save FAILED: {e}")
            raise
    
    def url(self, name):
        result = super().url(name)
        logger.debug(f"S3 url: {name} -> {result}")
        return result
    
class StaticStorage(S3Boto3Storage):
    location = 'static'
    default_acl = 'public-read'

class PublicMediaStorage(S3Boto3Storage):
    location = '' #ie builderappbucket/media is the location we upload to.
    default_acl = 'public-read'
    file_overwrite = False

"""
Cloud Storage Service

Handles file uploads to various cloud storage providers (S3, Google Cloud Storage)
with configurable settings and proper folder structure.
"""

import os
import uuid
import logging
from datetime import datetime
from typing import Optional, Tuple
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
# from .models import CloudStorageConfig
from decouple import config
import cloudinary
import cloudinary.uploader
import cloudinary.api

logger = logging.getLogger(__name__)


class CloudStorageService:
    """Service for handling cloud storage operations"""
    
    def __init__(self):
        self.config = None
        self.client = None
        # Deferred initialization to allow importing without Django setup
    
    def _get_active_config(self):
        """Get the active cloud storage configuration"""
        try:
            from .models import CloudStorageConfig
            return CloudStorageConfig.objects.filter(is_active=True).first()
        except Exception as e:
            logger.error(f"Failed to get cloud storage config: {e}")
            return None
    
    def _initialize_client(self):
        """Initialize the appropriate cloud storage client using environment variables"""
        if not self.config:
            return
            
        try:
            prefix = self.config.credentials_env_prefix
            
            if self.config.provider == 's3':
                import boto3
               

                # Get S3 credentials from environment
                access_key = config(f'{prefix}_ACCESS_KEY')
                secret_key = config(f'{prefix}_SECRET_KEY')
                
                if not access_key or not secret_key:
                    logger.error(f"Missing S3 credentials. Expected: {prefix}_ACCESS_KEY and {prefix}_SECRET_KEY")
                    return
                
                self.client = boto3.client(
                    's3',
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    region_name=self.config.region,
                    endpoint_url=self.config.endpoint_url if self.config.endpoint_url else None
                )
                
            elif self.config.provider == 'gcs':
                from google.cloud import storage
                
                # Get GCS service account JSON from environment
                service_account_json = config(f'{prefix}_SERVICE_ACCOUNT_JSON')
                
                if service_account_json:
                    import json
                    import tempfile
                    try:
                        # Validate JSON
                        json.loads(service_account_json)
                        # Write service account key to temp file
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                            f.write(service_account_json)
                            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = f.name
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON in {prefix}_SERVICE_ACCOUNT_JSON environment variable")
                        return
                else:
                    logger.warning(f"No service account JSON found in {prefix}_SERVICE_ACCOUNT_JSON. Using default credentials.")
                
                self.client = storage.Client()

            elif self.config.provider == 'cloudinary':
                 # Get Cloudinary credentials from environment
                cloud_name = config(f'{prefix}_CLOUD_NAME')
                api_key = config(f'{prefix}_API_KEY')
                api_secret = config(f'{prefix}_API_SECRET')
                
                if not cloud_name or not api_key or not api_secret:
                    logger.error(f"Missing Cloudinary credentials. Expected: {prefix}_CLOUD_NAME, {prefix}_API_KEY, {prefix}_API_SECRET")
                    return

                # Configure Cloudinary globally or specifically for this instance if needed
                # Since cloudinary library uses global config, we set it here
                cloudinary.config(
                    cloud_name=cloud_name,
                    api_key=api_key,
                    api_secret=api_secret
                )
                self.client = cloudinary  # Mark client as initialized
                
        except Exception as e:
            logger.error(f"Failed to initialize {self.config.provider} client: {e}")
            self.client = None
    
    def is_available(self) -> bool:
        """Check if cloud storage is properly configured and available"""
        if self.config is None:
            self.config = self._get_active_config()
            if self.config:
                self._initialize_client()
        return self.config is not None and self.client is not None
    
    def get_bucket_name(self) -> str:
        """Get the bucket name from provider-specific environment variable or config"""
        if not self.config:
            return 'translation'
        
        # Try provider-specific environment variable first
        if self.config.provider == 's3':
            bucket_name = config('S3_BUCKET_NAME')
        elif self.config.provider == 'gcs':
            bucket_name = config('GCS_BUCKET_NAME')
        else:
            bucket_name = None
            
        if bucket_name:
            return bucket_name
        
        # Fall back to config bucket name
        if self.config.bucket_name:
            return self.config.bucket_name
        
        # Default fallback
        return 'translation'
    
    def upload_voice_input_file(self, file: UploadedFile, language: str, user_id: str) -> Optional[str]:
        """
        Upload voice input file to cloud storage
        Path: translation/voice/input/{language}/{user_id}_{timestamp}_{uuid}.{ext}
        """
        if not self.is_available():
            logger.warning("Cloud storage not available")
            return None
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_extension = file.name.split('.')[-1] if '.' in file.name else 'audio'
        filename = f"{user_id}_{timestamp}_{uuid.uuid4().hex[:8]}.{file_extension}"
        folder_path = f"translation/voice/input/{language}/{filename}"
        
        return self._upload_file(file, folder_path)
    
    def upload_voice_output_file(self, file_content: bytes, language: str, user_id: str, file_format: str = 'wav') -> Optional[str]:
        """
        Upload voice output file to cloud storage
        Path: voice/output/{language}/{user_id}_{timestamp}_{uuid}.{ext}
        """
        if not self.is_available():
            logger.warning("Cloud storage not available")
            return None
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{user_id}_{timestamp}_{uuid.uuid4().hex[:8]}.{file_format}"
        folder_path = f"voice/output/{language}/{filename}"
        
        return self._upload_bytes(file_content, folder_path)
    
    def upload_image_input_file(self, file: UploadedFile, language: str, user_id: str) -> Optional[str]:
        """
        Upload image input file to cloud storage
        Path: translation/image/input/{language}/{user_id}_{timestamp}_{uuid}.{ext}
        """
        if not self.is_available():
            logger.warning("Cloud storage not available")
            return None
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_extension = file.name.split('.')[-1] if '.' in file.name else 'jpg'
        filename = f"{user_id}_{timestamp}_{uuid.uuid4().hex[:8]}.{file_extension}"
        folder_path = f"translation/image/input/{language}/{filename}"
        
        return self._upload_file(file, folder_path)
    
    def upload_document_input_file(self, file: UploadedFile, language: str, user_id: str) -> Optional[str]:
        """
        Upload document input file to cloud storage
        Path: translation/document/input/{language}/{user_id}_{timestamp}_{uuid}.{ext}
        """
        if not self.is_available():
            logger.warning("Cloud storage not available")
            return None
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_extension = file.name.split('.')[-1] if '.' in file.name else 'doc'
        filename = f"{user_id}_{timestamp}_{uuid.uuid4().hex[:8]}.{file_extension}"
        folder_path = f"translation/document/input/{language}/{filename}"
        
        return self._upload_file(file, folder_path)

    def upload_document_output_file(self, file_path: str, language: str, user_id: str, file_format: str) -> Optional[str]:
        """
        Upload document output file to cloud storage
        Path: translation/document/output/{language}/{user_id}_{timestamp}_{uuid}.{ext}
        """
        if not self.is_available():
            logger.warning("Cloud storage not available")
            return None
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{user_id}_{timestamp}_{uuid.uuid4().hex[:8]}.{file_format}"
        folder_path = f"translation/document/output/{language}/{filename}"
        
        with open(file_path, 'rb') as f:
            from django.core.files.base import ContentFile
            content_file = ContentFile(f.read(), name=filename)
            # Determine content type
            content_type = 'application/pdf' if file_format.lower() == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            content_file.content_type = content_type
            return self._upload_file(content_file, folder_path)
    
    def _upload_file(self, file: UploadedFile, folder_path: str) -> Optional[str]:
        """Upload a Django UploadedFile to cloud storage"""
        try:
            bucket_name = self.get_bucket_name()
            if self.config.provider == 's3':
                self.client.upload_fileobj(
                    file,
                    bucket_name,
                    folder_path,
                    ExtraArgs={'ContentType': file.content_type or 'application/octet-stream'}
                )
                return f"https://{bucket_name}.s3.{self.config.region}.amazonaws.com/{folder_path}"
                
            elif self.config.provider == 'gcs':
                bucket = self.client.bucket(bucket_name)
                blob = bucket.blob(folder_path)
                blob.upload_from_file(file, content_type=file.content_type)
                return f"https://storage.googleapis.com/{bucket_name}/{folder_path}"
            
            elif self.config.provider == 'cloudinary':
                 # Cloudinary handles buckets via cloud_name, folder structure via public_id
                # but we can optionally use folders
                response = cloudinary.uploader.upload(
                    file, 
                    public_id=folder_path, # Using path as public ID for structure
                    resource_type="auto"
                )
                return response.get('secure_url')
                 
                
        except Exception as e:
            logger.error(f"Failed to upload file to {self.config.provider}: {e}")
            return None
    
    def _upload_bytes(self, file_content: bytes, folder_path: str, content_type: str = 'audio/wav') -> Optional[str]:
        """Upload bytes content to cloud storage"""
        try:
            bucket_name = self.get_bucket_name()
            if self.config.provider == 's3':
                self.client.put_object(
                    Bucket=bucket_name,
                    Key=folder_path,
                    Body=file_content,
                    ContentType=content_type
                )
                return f"https://{bucket_name}.s3.{self.config.region}.amazonaws.com/{folder_path}"
                
            elif self.config.provider == 'gcs':
                bucket = self.client.bucket(bucket_name)
                blob = bucket.blob(folder_path)
                blob.upload_from_string(file_content, content_type=content_type)
                return f"https://storage.googleapis.com/{bucket_name}/{folder_path}"
                
            elif self.config.provider == 'cloudinary':
                import io
                # Explicitly handle bytes for Cloudinary
                file_obj = io.BytesIO(file_content)
                # Set a filename so Cloudinary can detect mime type if needed, 
                # although public_id usually suffices. Use the basename of folder_path.
                file_obj.name = folder_path.split('/')[-1]
                
                logger.info(f"Uploading {len(file_content)} bytes to Cloudinary as {folder_path}")

                # Cloudinary may add extension to URL, so strip it from public_id to avoid double extension
                public_id = folder_path
                if public_id.lower().endswith('.wav'):
                    public_id = public_id[:-4]
                
                response = cloudinary.uploader.upload(
                    file_obj, 
                    public_id=public_id,
                    resource_type="video" # Audio is treated as video in Cloudinary
                )
                return response.get('secure_url')
                
        except Exception as e:
            logger.error(f"Failed to upload bytes to {self.config.provider}: {e}")
            return None
    
    def delete_file(self, file_url: str) -> bool:
        """Delete a file from cloud storage using its URL"""
        if not self.is_available() or not file_url:
            return False
            
        try:
            bucket_name = self.get_bucket_name()
            # Extract the file path from the URL
            if self.config.provider == 's3':
                # URL format: https://bucket.s3.region.amazonaws.com/path
                path_start = file_url.find(f"/{bucket_name}/")
                if path_start == -1:
                    path_start = file_url.find(f".amazonaws.com/")
                    if path_start == -1:
                        return False
                    file_path = file_url[path_start + len(".amazonaws.com/"):]
                else:
                    file_path = file_url[path_start + len(f"/{bucket_name}/"):]
                
                self.client.delete_object(Bucket=bucket_name, Key=file_path)
                return True
                
            elif self.config.provider == 'gcs':
                # URL format: https://storage.googleapis.com/bucket/path
                path_start = file_url.find(f"/{bucket_name}/")
                if path_start == -1:
                    return False
                file_path = file_url[path_start + len(f"/{bucket_name}/"):]
                
                bucket = self.client.bucket(bucket_name)
                blob = bucket.blob(file_path)
                blob.delete()
                return True
            
            elif self.config.provider == 'cloudinary':
                 # Extract public ID from URL
                # Cloudinary URLs: https://res.cloudinary.com/cloud_name/resource_type/type/v12345/public_id.ext
                # We stored public_id as the folder path
                
                # Simple heuristic: if we used the folder path as public_id, checking if it ends with that
                # But a safer way for Cloudinary is to use search or just try to delete if we know the public_id
                # Since we returned secure_url which structure is complex, we need parsing or assume consistent structure.
                
                # If we assume we stored it with public_id = folder_path (which we did), 
                # we can re-derive it if we knew the original structure.
                # But here we only have the URL.
                
                # Let's try to extract parts after version number or upload/
                try:
                    # Typical URL: https://res.cloudinary.com/<cloud_name>/<type>/upload/v<version>/<public_id>.<ext>
                    parts = file_url.split('/')
                    # find 'upload' index
                    if 'upload' in parts:
                        idx = parts.index('upload')
                        # public_id starts after version (vXXXX) usually at idx+2
                        # but sometimes version is omitted.
                        # public_id is everything after that until the end, minus extension
                        
                        potential_public_id_parts = parts[idx+1:]
                        if potential_public_id_parts[0].startswith('v'): # version
                             potential_public_id_parts = potential_public_id_parts[1:]
                        
                        full_path = "/".join(potential_public_id_parts)
                        # remove extension
                        public_id = ".".join(full_path.split('.')[:-1])
                        
                        cloudinary.uploader.destroy(public_id)
                        return True
                except Exception:
                    logger.warning(f"Could not parse public_id from Cloudinary URL: {file_url}")
                    return False
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete file from {self.config.provider}: {e}")
            return False
    
    def get_bucket_info(self) -> dict:
        """Get information about the current bucket configuration"""
        if not self.config:
            return {"status": "not_configured", "message": "No cloud storage configured"}
        
        bucket_name = self.get_bucket_name()
        
        # Determine bucket source
        bucket_source = "config"
        if self.config.provider == 's3' and config('S3_BUCKET_NAME'):
            bucket_source = "S3_BUCKET_NAME"
        elif self.config.provider == 'gcs' and config('GCS_BUCKET_NAME'):
            bucket_source = "GCS_BUCKET_NAME"
        elif self.config.provider == 'cloudinary':
            bucket_source = "Cloud Name"
            bucket_name = config(f'{self.config.credentials_env_prefix}_CLOUD_NAME')
        
        return {
            "status": "configured" if self.is_available() else "error",
            "provider": self.config.provider,
            "bucket_name": bucket_name,
            "config_bucket_name": self.config.bucket_name,  # Show both for reference
            "region": self.config.region,
            "name": self.config.name,
            "bucket_source": bucket_source,
            "expected_bucket_env_var": f"{self.config.provider.upper()}_BUCKET_NAME"
        }


# Global instance
cloud_storage = CloudStorageService()

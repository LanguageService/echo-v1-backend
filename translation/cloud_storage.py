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


class StorageConfigMock:
    """Mock storage configuration when database access fails during bootstrap"""
    def __init__(self, name, provider, bucket_name, region, credentials_env_prefix, endpoint_url=None):
        self.name = name
        self.provider = provider
        self.bucket_name = bucket_name
        self.region = region
        self.credentials_env_prefix = credentials_env_prefix
        self.endpoint_url = endpoint_url


class CloudStorageService:
    """Service for handling cloud storage operations"""
    
    def __init__(self):
        self.config = None
        self.client = None
        # Deferred initialization to allow importing without Django setup
    
    def _get_active_config(self):
        """Get the active cloud storage configuration based on ENV_MODE"""
        env_mode = config("ENV_MODE", default="prod")
        try:
            from .models import CloudStorageConfig
            
            if env_mode == "prod":
                cfg = CloudStorageConfig.objects.filter(provider="s3").first()
                if not cfg:
                    cfg = CloudStorageConfig(
                        name="Amazon S3 (Auto)",
                        provider="s3",
                        bucket_name=config("S3_BUCKET_NAME", default="echo-translation-bucket"),
                        region=config("AWS_REGION", default="us-east-1"),
                        credentials_env_prefix="AWS"
                    )
                return cfg
            else:
                cfg = CloudStorageConfig.objects.filter(provider="cloudinary").first()
                if not cfg:
                    cfg = CloudStorageConfig(
                        name="Cloudinary (Auto)",
                        provider="cloudinary",
                        bucket_name="cloudinary",
                        region="global",
                        credentials_env_prefix="CLOUDINARY"
                    )
                return cfg
        except Exception as e:
            logger.warning(f"Failed to get cloud storage config from database: {e}. Using mock configuration.")
            if env_mode == "prod":
                return StorageConfigMock(
                    name="Amazon S3",
                    provider="s3",
                    bucket_name=config("S3_BUCKET_NAME", default="echo-translation-bucket"),
                    region=config("AWS_REGION", default="us-east-1"),
                    credentials_env_prefix="AWS"
                )
            else:
                return StorageConfigMock(
                    name="Cloudinary",
                    provider="cloudinary",
                    bucket_name="cloudinary",
                    region="global",
                    credentials_env_prefix="CLOUDINARY"
                )
    
    def _initialize_client(self):
        """Initialize the appropriate cloud storage client using environment variables"""
        if not self.config:
            return
            
        try:
            prefix = self.config.credentials_env_prefix
            
            if self.config.provider == 's3':
                import boto3
                
                # Get S3 credentials (try custom prefix first, fallback to standard AWS environment variables)
                access_key = (
                    config(f'{prefix}_ACCESS_KEY', default=None)
                    or config('AWS_ACCESS_KEY_ID', default=None)
                    or config('AWS_ACCESS_KEY', default=None)
                )
                secret_key = (
                    config(f'{prefix}_SECRET_KEY', default=None)
                    or config('AWS_SECRET_ACCESS_KEY', default=None)
                    or config('AWS_SECRET_KEY', default=None)
                )
                
                if not access_key or not secret_key:
                    logger.info(f"No explicit S3 credentials found. Relying on IAM roles or default boto3 credential chain.")
                
                boto_kwargs = {
                    'region_name': self.config.region,
                }
                if self.config.endpoint_url:
                    boto_kwargs['endpoint_url'] = self.config.endpoint_url
                    
                if access_key and secret_key:
                    boto_kwargs['aws_access_key_id'] = access_key
                    boto_kwargs['aws_secret_access_key'] = secret_key
                    
                self.client = boto3.client('s3', **boto_kwargs)
                
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
                cloud_name = config(f'{prefix}_CLOUD_NAME', default=None) or config('CLOUDINARY_CLOUD_NAME', default=None)
                api_key = config(f'{prefix}_API_KEY', default=None) or config('CLOUDINARY_API_KEY', default=None)
                api_secret = config(f'{prefix}_API_SECRET', default=None) or config('CLOUDINARY_API_SECRET', default=None)
                
                if not cloud_name or not api_key or not api_secret:
                    logger.error("Missing Cloudinary credentials.")
                    return

                # Configure Cloudinary globally
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
            bucket_name = config('S3_BUCKET_NAME', default=None) or config('AWS_STORAGE_BUCKET_NAME', default=None)
        elif self.config.provider == 'gcs':
            bucket_name = config('GCS_BUCKET_NAME', default=None)
        else:
            bucket_name = None
            
        if bucket_name:
            return bucket_name
        
        # Fall back to config bucket name
        if hasattr(self.config, 'bucket_name') and self.config.bucket_name:
            return self.config.bucket_name
        
        # Default fallback
        return 'translation'
    
    def _get_user_hex(self, user_id: str) -> str:
        """Convert user_id to its hexadecimal representation if it's a UUID or integer"""
        if not user_id or user_id == "anonymous":
            return "anonymous"
        
        try:
            # Handle UUID string (with or without dashes)
            import uuid
            return uuid.UUID(user_id).hex
        except (ValueError, AttributeError):
            try:
                # Handle integer string
                return hex(int(user_id))[2:]
            except (ValueError, TypeError):
                # Fallback to simple string cleanup or hash if needed
                return user_id.replace('-', '')
    
    def _local_store(self, file_name: str, file_content: bytes, sub_path: str) -> Optional[str]:
        """
        Store a file locally under MEDIA_ROOT when ENV_MODE=local.
        Returns the full URL using MEDIA_URL.
        """
        import shutil
        from django.conf import settings

        rel_path = os.path.join('cloud_local', sub_path, file_name)
        abs_path = os.path.join(settings.MEDIA_ROOT, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        with open(abs_path, 'wb') as f:
            f.write(file_content)

        # Build a full URL that works in local dev
        base = config('LOCAL_BASE_URL', default='http://localhost:8000')
        media_url = getattr(settings, 'MEDIA_URL', '/media/')
        url = f"{base.rstrip('/')}{media_url}{rel_path}"
        logger.info(f"[local] Stored file at {abs_path} → {url}")
        return url

    def upload_voice_input_file(self, file: UploadedFile, language: str, user_id: str) -> Optional[str]:
        """
        Upload voice input file to cloud storage
        Path: translation/voice/input/{language}/{user_id}_{timestamp}_{uuid}.{ext}
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_extension = file.name.split('.')[-1] if '.' in file.name else 'audio'
        filename = f"{user_id}_{timestamp}_{uuid.uuid4().hex[:8]}.{file_extension}"

        if not self.is_available():
            logger.warning("Cloud storage not available - falling back to local storage")
            content = file.read() if hasattr(file, 'read') else b''
            return self._local_store(filename, content, 'speech/input')

        user_hex = self._get_user_hex(user_id)
        folder_path = f"translation/{user_hex}/speech/{filename}"
        return self._upload_file(file, folder_path, resource_type="video")
    
    def upload_voice_output_file(self, file_content: bytes, language: str, user_id: str, file_format: str = 'wav') -> Optional[str]:
        """
        Upload voice output file to cloud storage
        Path: voice/output/{language}/{user_id}_{timestamp}_{uuid}.{ext}
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{user_id}_{timestamp}_{uuid.uuid4().hex[:8]}.{file_format}"

        if not self.is_available():
            logger.warning("Cloud storage not available - falling back to local storage")
            return self._local_store(filename, file_content, 'speech/output')

        user_hex = self._get_user_hex(user_id)
        folder_path = f"translation/{user_hex}/speech/{filename}"
        return self._upload_bytes(file_content, folder_path)
    
    def upload_image_input_file(self, file: UploadedFile, language: str, user_id: str) -> Optional[str]:
        """
        Upload image input file to cloud storage
        Path: translation/image/input/{language}/{user_id}_{timestamp}_{uuid}.{ext}
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_extension = file.name.split('.')[-1] if '.' in file.name else 'jpg'
        filename = f"{user_id}_{timestamp}_{uuid.uuid4().hex[:8]}.{file_extension}"

        if not self.is_available():
            logger.warning("Cloud storage not available - falling back to local storage")
            content = file.read() if hasattr(file, 'read') else b''
            return self._local_store(filename, content, 'image/input')

        user_hex = self._get_user_hex(user_id)
        folder_path = f"translation/{user_hex}/image/{filename}"
        return self._upload_file(file, folder_path, resource_type="image")
    
    def upload_document_input_file(self, file: UploadedFile, language: str, user_id: str) -> Optional[str]:
        """
        Upload document input file to cloud storage
        Path: translation/document/input/{language}/{user_id}_{timestamp}_{uuid}.{ext}
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_extension = file.name.split('.')[-1] if '.' in file.name else 'doc'
        filename = f"{user_id}_{timestamp}_{uuid.uuid4().hex[:8]}.{file_extension}"

        if not self.is_available():
            logger.warning("Cloud storage not available - falling back to local storage")
            content = file.read() if hasattr(file, 'read') else b''
            return self._local_store(filename, content, 'text/input')

        user_hex = self._get_user_hex(user_id)
        folder_path = f"translation/{user_hex}/text/{filename}"
        return self._upload_file(file, folder_path, resource_type="raw")

    def upload_document_output_file(self, file_path: str, language: str, user_id: str, file_format: str) -> Optional[str]:
        """
        Upload document output file to cloud storage
        Path: translation/document/output/{language}/{user_id}_{timestamp}_{uuid}.{ext}
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{user_id}_{timestamp}_{uuid.uuid4().hex[:8]}.{file_format}"

        if not self.is_available():
            logger.warning("Cloud storage not available - falling back to local storage")
            with open(file_path, 'rb') as f:
                content = f.read()
            return self._local_store(filename, content, 'text/output')

        user_hex = self._get_user_hex(user_id)
        folder_path = f"translation/{user_hex}/text/{filename}"

        with open(file_path, 'rb') as f:
            from django.core.files.base import ContentFile
            content_file = ContentFile(f.read(), name=filename)
            content_type = {
                'pdf': 'application/pdf',
                'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'doc': 'application/msword',
                'csv': 'text/csv',
                'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'xls': 'application/vnd.ms-excel',
            }.get(file_format.lower(), 'application/octet-stream')
            content_file.content_type = content_type
            return self._upload_file(content_file, folder_path, resource_type="raw")
    
    def _upload_file(self, file: UploadedFile, folder_path: str, resource_type: str = "auto") -> Optional[str]:
        """Upload a Django UploadedFile to cloud storage"""
        try:
            bucket_name = self.get_bucket_name()
            if self.config.provider == 's3':
                extra_args = {'ContentType': file.content_type or 'application/octet-stream'}
                if resource_type == 'raw' and 'pdf' not in (file.content_type or '').lower():
                    # Only force attachment for non-PDF raw files if needed, 
                    # but actually let's just allow inline for everything to enable previews
                    pass
                self.client.upload_fileobj(
                    file,
                    bucket_name,
                    folder_path,
                    ExtraArgs=extra_args
                )
                return f"https://{bucket_name}.s3.{self.config.region}.amazonaws.com/{folder_path}"
                
            elif self.config.provider == 'gcs':
                bucket = self.client.bucket(bucket_name)
                blob = bucket.blob(folder_path)
                blob.upload_from_file(file, content_type=file.content_type)
                return f"https://storage.googleapis.com/{bucket_name}/{folder_path}"
            
            elif self.config.provider == 'cloudinary':
                # Cloudinary handles buckets via cloud_name, folder structure via public_id.
                # Cloudinary appends the format extension to the URL automatically, so we must
                # strip the extension from public_id to avoid double extensions like .pdf.pdf
                public_id = folder_path
                if resource_type != 'raw' and '.' in public_id.split('/')[-1]:
                    public_id = public_id.rsplit('.', 1)[0]

                response = cloudinary.uploader.upload(
                    file,
                    public_id=public_id,
                    resource_type=resource_type,
                    type="authenticated"
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
            
    def private_download_url(self, file_url: str) -> str:
        """
        Generate a fresh, signed URL for an authenticated resource.
        Useful when returning URLs to the frontend.
        """
        if not self.config:
            self.config = self._get_active_config()
            self._initialize_client()
            
        if not self.config or not file_url:
            return file_url
            
        if self.config.provider == 'cloudinary' and 'cloudinary.com' in file_url:
            # We always want to sign URLs, even if they were uploaded as 'upload' but migrated, 
            # or if they are PDFs which are blocked by default.
            try:
                # Extract parts
                parts = file_url.split('/')
                # Find version index or upload/authenticated
                type_idx = -1
                version_idx = -1
                for i, p in enumerate(parts):
                    if p in ['upload', 'authenticated']:
                        type_idx = i
                    elif p.startswith('v') and p[1:].isdigit():
                        version_idx = i
                        break
                        
                if type_idx >= 0 and version_idx > type_idx:
                    public_id_with_ext = '/'.join(parts[version_idx+1:])
                    version_str = parts[version_idx][1:] # e.g. '1783280115' from 'v1783280115'
                    
                    resource_type = 'raw'
                    if '/image/' in file_url: resource_type = 'image'
                    elif '/video/' in file_url: resource_type = 'video'
                    
                    import cloudinary.utils
                    
                    fmt = ''
                    public_id = public_id_with_ext
                    if '.' in public_id_with_ext and resource_type != 'raw':
                        fmt = public_id_with_ext.rsplit('.', 1)[-1]
                        public_id = public_id_with_ext.rsplit('.', 1)[0]

                    # Generate a signed CDN URL
                    kwargs = {
                        "resource_type": resource_type,
                        "type": "authenticated",
                        "version": version_str,
                        "sign_url": True,
                        "secure": True
                    }
                    if fmt:
                        kwargs["format"] = fmt

                    fresh_url = cloudinary.utils.private_download_url(
                        public_id,
                        fmt,
                        **kwargs
                    )
                    return fresh_url
            except Exception as e:
                logger.error(f"Error generating Cloudinary signed URL: {e}")
        return file_url
            
    def download_file(self, file_url: str, local_path: str) -> bool:
        """Download a file from cloud storage using its URL securely via the provider client"""
        if not self.is_available() or not file_url:
            # Fallback to standard HTTP requests if cloud storage is off
            import requests
            try:
                response = requests.get(file_url, stream=True)
                if response.status_code == 200:
                    with open(local_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    return True
            except Exception as e:
                logger.error(f"HTTP download fallback failed: {e}")
            return False
            
        try:
            bucket_name = self.get_bucket_name()
            if self.config.provider == 's3':
                path_start = file_url.find(f"/{bucket_name}/")
                if path_start == -1:
                    path_start = file_url.find(".amazonaws.com/")
                    if path_start == -1:
                        return False
                    file_path = file_url[path_start + len(".amazonaws.com/"):]
                else:
                    file_path = file_url[path_start + len(f"/{bucket_name}/"):]
                
                self.client.download_file(bucket_name, file_path, local_path)
                return True
                
            elif self.config.provider == 'gcs':
                path_start = file_url.find(f"/{bucket_name}/")
                if path_start == -1:
                    return False
                file_path = file_url[path_start + len(f"/{bucket_name}/"):]
                bucket = self.client.bucket(bucket_name)
                blob = bucket.blob(file_path)
                blob.download_to_filename(local_path)
                return True
            
            elif self.config.provider == 'cloudinary':
                import requests
                
                # Cloudinary's secure_url from upload response often has invalid signatures for authenticated raw files.
                # Regenerate the signed URL if it's an authenticated resource.
                if '/authenticated/' in file_url:
                    parts = file_url.split('/authenticated/')
                    if len(parts) > 1:
                        sub_parts = parts[1].split('/')
                        start_idx = 0
                        if sub_parts[start_idx].startswith('s--'):
                            start_idx += 1
                        if start_idx < len(sub_parts) and sub_parts[start_idx].startswith('v') and sub_parts[start_idx][1:].isdigit():
                            start_idx += 1
                            
                        public_id_with_ext = '/'.join(sub_parts[start_idx:])
                        
                        resource_type = 'raw'
                        if '/image/' in file_url: resource_type = 'image'
                        elif '/video/' in file_url: resource_type = 'video'
                        
                        import cloudinary.utils
                        
                        # Handle the case where public_id has an extension
                        fmt = ''
                        public_id = public_id_with_ext
                        if '.' in public_id_with_ext and resource_type != 'raw':
                            fmt = public_id_with_ext.rsplit('.', 1)[-1]
                            public_id = public_id_with_ext.rsplit('.', 1)[0]
                            
                        # Use private_download_url which works for blocked file types like authenticated PDFs
                        kwargs = {
                            "resource_type": resource_type,
                            "type": "authenticated",
                            "attachment": True
                        }
                            
                        fresh_url = cloudinary.utils.private_download_url(
                            public_id,
                            fmt,
                            **kwargs
                        )
                        file_url = fresh_url

                response = requests.get(file_url, stream=True)
                if response.status_code == 200:
                    with open(local_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    return True
                else:
                    logger.error(f"Cloudinary download failed with {response.status_code} for URL: {file_url}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to download file from {self.config.provider}: {e}")
            return False
    
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
    
    def generate_presigned_url(self, file_name: str, file_type: str, user_id: str, content_type: str = None) -> Optional[dict]:
        """Generate a presigned URL for direct cloud upload from the frontend"""
        if not self.is_available():
            logger.warning("Cloud storage not available")
            return None
            
        user_hex = self._get_user_hex(user_id)
        # The user requested folder structure: user or business/file_type/file
        # We will use: user_hex/file_type/filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        import re
        file_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', file_name)
        unique_filename = f"{timestamp}_{uuid.uuid4().hex[:8]}_{file_name}"
        folder_path = f"{user_hex}/{file_type}/{unique_filename}"
        bucket_name = self.get_bucket_name()
        
        try:
            if self.config.provider == 's3':
                params = {
                    'Bucket': bucket_name,
                    'Key': folder_path
                }
                if content_type:
                    params['ContentType'] = content_type
                    
                url = self.client.generate_presigned_url(
                    'put_object',
                    Params=params,
                    ExpiresIn=3600
                )
                return {
                    "provider": "s3",
                    "upload_method": "PUT",
                    "fields": {},
                    "upload_url": url,
                    "s3_key": folder_path,
                    "bucket": bucket_name,
                    "file_url": f"https://{bucket_name}.s3.{self.config.region}.amazonaws.com/{folder_path}"
                }
            elif self.config.provider == 'cloudinary':
                import time
                import cloudinary.utils
                from decouple import config
                
                unix_timestamp = int(time.time())
                public_id = folder_path
                if '.' in public_id.split('/')[-1]:
                    public_id = public_id.rsplit('.', 1)[0]
                    
                params_to_sign = {
                    "timestamp": unix_timestamp,
                    "public_id": public_id,
                    "type": "authenticated"
                }
                
                api_secret = config('CLOUDINARY_API_SECRET', default='')
                api_key = config('CLOUDINARY_API_KEY', default='')
                cloud_name = config('CLOUDINARY_CLOUD_NAME', default='')
                
                signature = cloudinary.utils.api_sign_request(params_to_sign, api_secret)
                
                ext = file_name.rsplit('.', 1)[-1] if '.' in file_name else ''
                cloudinary.config(cloud_name=cloud_name, api_key=api_key, api_secret=api_secret)
                signed_delivery_url, _ = cloudinary.utils.cloudinary_url(
                    public_id,
                    resource_type="raw",
                    type="authenticated",
                    sign_url=True,
                    format=ext
                )
                if signed_delivery_url.startswith('http://'):
                    signed_delivery_url = signed_delivery_url.replace('http://', 'https://', 1)
                
                return {
                    "provider": "cloudinary",
                    "upload_method": "POST",
                    "upload_url": f"https://api.cloudinary.com/v1_1/{cloud_name}/raw/upload",
                    "fields": {
                        "api_key": api_key,
                        "timestamp": unix_timestamp,
                        "signature": signature,
                        "public_id": public_id,
                        "type": "authenticated"
                    },
                    "s3_key": folder_path,
                    "bucket": cloud_name,
                    "file_url": signed_delivery_url
                }
            else:
                logger.warning(f"Unsupported provider for presigned URL: {self.config.provider}")
                return None
        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            return None


# Global instance
cloud_storage = CloudStorageService()

import cloudinary
import cloudinary.uploader
import cloudinary.api


from decouple import config


cloudinary.config(
    cloud_name = config('CLOUDINARY_CLOUD_NAME'),
    api_key = config('CLOUDINARY_API_KEY'),
    api_secret = config('CLOUDINARY_API_SECRET')
)



CLOUDINARY_STORAGE = {
    'CLOUD_NAME': config('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': config('CLOUDINARY_API_KEY'),
    'API_SECRET': config('CLOUDINARY_API_SECRET'),
}


# Set DEFAULT_FILE_STORAGE to Cloudinary in non-production environments (dev/local/etc.)
# This ensures all model FileFields and ImageFields automatically save to Cloudinary.
if config('ENV_MODE', default='prod') != 'prod':
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'


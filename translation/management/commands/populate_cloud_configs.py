from django.core.management.base import BaseCommand
from translation.models import CloudStorageConfig

class Command(BaseCommand):
    help = 'Populates the database with default cloud storage configurations'

    def handle(self, *args, **kwargs):
        configs = [
            {
                'name': 'Amazon S3',
                'provider': 's3',
                'is_active': False,
                'credentials_env_prefix': 'AWS',
                'bucket_name': 'echo-translation-bucket',
                'region': 'us-east-1'
            },
            {
                'name': 'Google Cloud Storage',
                'provider': 'gcs',
                'is_active': False,
                'credentials_env_prefix': 'GCP',
                'bucket_name': 'echo-translation-bucket',
                'region': 'us-central1'
            },
            {
                'name': 'Cloudinary',
                'provider': 'cloudinary',
                'is_active': True,
                'credentials_env_prefix': 'CLOUDINARY',
                'bucket_name': 'echo-translation-bucket',
                'region': 'global'
            }
        ]

        created_count = 0
        updated_count = 0

        for config_data in configs:
            config, created = CloudStorageConfig.objects.get_or_create(
                name=config_data['name'],
                defaults=config_data
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created config: {config.name}"))
                created_count += 1
            else:
                self.stdout.write(self.style.WARNING(f"Config already exists: {config.name}"))
                # Optional: Update existing config if needed, but for now we just skip
                # for key, value in config_data.items():
                #     setattr(config, key, value)
                # config.save()
                # updated_count += 1

        self.stdout.write(self.style.SUCCESS(f"Finished. Created: {created_count}, Existing: {len(configs) - created_count}"))

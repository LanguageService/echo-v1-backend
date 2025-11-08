from pathlib import Path
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Database configuration based on environment mode
ENV_MODE = config('ENV_MODE', 'dev').lower()

if ENV_MODE == 'local':
    # Use SQLite for local development
    # Use a persistent directory for the SQLite database
    DB_DIR = BASE_DIR / "database"
    DB_DIR.mkdir(parents=True, exist_ok=True)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': DB_DIR / 'db.sqlite3',
        }
    }
else:
    # Use PostgreSQL for dev/prod environments
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('PGDATABASE'),
            'USER': os.getenv('PGUSER'),
            'PASSWORD': os.getenv('PGPASSWORD'),
            'HOST': os.getenv('PGHOST'),
            'PORT': os.getenv('PGPORT'),
            'OPTIONS': {
                'sslmode': 'require',
            },
        }
    }

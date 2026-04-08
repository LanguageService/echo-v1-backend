import os
from pathlib import Path
from decouple import config
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


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
            'NAME': config('PGDATABASE', default=config('DATABASE_NAME', default='')),
            'USER': config('PGUSER', default=config('DATABASE_USER', default='')),
            'PASSWORD': config('PGPASSWORD', default=config('DATABASE_PASSWORD', default='')),
            'HOST': config('PGHOST', default=config('DATABASE_HOST', default='')),
            'PORT': config('PGPORT', default=config('DATABASE_PORT', default='5432')),
            'OPTIONS': {
                'sslmode': 'require',
            },
        }
    }

# This will override the above if DATABASE_URL is set in .env or environment
db_url = config('DATABASE_URL', default=None)
if db_url:
    DATABASES['default'] = dj_database_url.config(default=db_url)


from decouple import config


DEBUG = False
ALLOWED_HOSTS = ["api.letusecho.com", "52.212.205.193"]


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DATABASE_NAME", default=""),
        "USER": config("DATABASE_USER", default=""),
        "PASSWORD": config("DATABASE_PASSWORD", default=""),
        "HOST": config("DATABASE_HOST", default=""),  # Use 'localhost' if running locally
        "PORT": config("DATABASE_PORT", default="5432"),  # Default PostgreSQL port
    }
}


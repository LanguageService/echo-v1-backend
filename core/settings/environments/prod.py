from decouple import config


DEBUG = False
ALLOWED_HOSTS = ["https://api.smartscribbl.com","https://app.smartscribbl.com","http://localhost:4200","api.smartscribbl.com"]


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DATABASE_NAME"),
        "USER": config("DATABASE_USER"),
        "PASSWORD": config("DATABASE_PASSWORD"),
        "HOST": config("DATABASE_HOST"),  # Use 'localhost' if running locally
        "PORT": config("DATABASE_PORT"),  # Default PostgreSQL port
    }
}


from decouple import config

DEBUG = True
ALLOWED_HOSTS = ["*"]


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

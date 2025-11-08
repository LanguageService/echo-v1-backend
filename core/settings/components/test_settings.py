from split_settings.tools import include

# Settings for testing

# First, include the base settings
include("__init__.py")

# Overwrite redis to use fakeredis (in memory)
# Turns out this was tricky to get working
# So, we gave up and let the tests run against the real redis.

# CACHES = {
#     "default": {
#         "BACKEND": "django_redis.cache.RedisCache",
#         "LOCATION": "redis://redis:6379/0",
#         "OPTIONS": {
#             "CLIENT_CLASS": "django_redis.client.DefaultClient",
#             "REDIS_CLIENT_CLASS": "fakeredis.FakeStrictRedis",
#         },
#     },
# }


# Use a sqlite database for testing
import os
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "test_db.sqlite3"),
    }
}

"""
This is a django-split-settings main file.
For more information, read this:
https://github.com/sobolevn/django-split-settings

To change settings file:
'DJANGO_ENV=production python manage.py runserver
"""

from split_settings.tools import include, optional
from decouple import config


class ENV_ENUM:
    PRODUCTION = "prod"
    DEV = "dev"
    LOCAL = "local"


ENV = config("ENV_MODE", ENV_ENUM.PRODUCTION)

print(ENV)
base_settings = [
    "components/common.py",  # standard django settings
    "components/db.py",
    "components/email.py",
    "components/logger.py",
    "components/config_urls.py",
    "components/celery.py",
    optional("environments/%s.py" % ENV),
]

include(*base_settings)

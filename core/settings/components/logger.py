# import google.cloud.logging
import sentry_sdk
from decouple import config
from sentry_sdk.integrations.django import DjangoIntegration
from django.conf import settings

SENTRY_DSN = config("SENTRY_DSN")
# from google.cloud.logging.handlers import CloudLoggingHandler
ENV_ENUM = settings.ENV_ENUM

# if settings.ENV != ENV_ENUM.LOCAL:
#     sentry_sdk.init(
#         dsn=SENTRY_DSN,
#         integrations=[DjangoIntegration()],
#         # Set traces_sample_rate to 1.0 to capture 100%
#         # of transactions for performance monitoring.
#         # We recommend adjusting this value in production.
#         traces_sample_rate=1.0,
#         # If you wish to associate users to errors (assuming you are using
#         # django.contrib.auth) you may enable sending PII data.
#         send_default_pii=True,
#         environment=settings.ENV,
#     )

LOGGING_CONFIG = None

ADMINS = [("Sunday", "sunnexajayi@gmail.com")]

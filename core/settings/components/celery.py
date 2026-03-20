from decouple import config

# Celery Configuration Options
# ------------------------------------------------------------------------------
# https://docs.celeryq.dev/en/stable/userguide/configuration.html

CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default="redis://localhost:6379/0")

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std-setting-task_time_limit
# CELERY_TASK_TIME_LIMIT = 5 * 60
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std-setting-task_soft_time_limit
# CELERY_TASK_SOFT_TIME_LIMIT = 60

CELERY_TIMEZONE = "UTC"
CELERY_TASK_TRACK_STARTED = True

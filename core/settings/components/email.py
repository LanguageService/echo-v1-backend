from decouple import config


EMAIL_USE_TLS = True
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = config("SMTP_HOST")
EMAIL_PORT = config("SMTP_PORT")
EMAIL_HOST_USER = config("SMTP_USERNAME")
EMAIL_HOST_PASSWORD = config("SMTP_PASSWORD")
EMAIL_FROM = config("EMAIL_FROM", "noreply@suavesystems.com")

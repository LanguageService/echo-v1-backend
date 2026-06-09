from decouple import config

# ── Email Settings (Resend SMTP Configuration) ───────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.resend.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'resend'
EMAIL_HOST_PASSWORD = config('RESEND_API_KEY', '')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', 'LetUsEcho<no-reply@letusecho.com>')
SUPPORT_EMAIL = config('SUPPORT_EMAIL', 'support@letusecho.com')

"""
Global Constants and Choices

Centralized configuration for all global variables, choices, and constants
used throughout the Django OCR and voice translation system.
"""

from django.db import models
from django.utils import timezone



# AI Model choices for user preferences
AI_MODEL_CHOICES = [
    ('gemini-2.5-flash', 'G25F (Fast)'),
    ('gemini-2.5-pro', 'G25P (High Quality)'),
    ('gpt-5', 'OA5 (High Quality)'),
    ('claude-sonnet-4-20250514', 'CS4 (High Quality)'),
    ('auto', 'Automatic (Service Default)'),
]

# Translation service provider choices
TRANSLATION_SERVICE_CHOICES = [
    ('gemini', 'Google Gemini'),
    ('openai', 'OpenAI GPT'),
    ('anthropic', 'Anthropic Claude'),
    ('auto', 'Automatic (Best Available)'),
]

# Supported image formats for OCR
SUPPORTED_IMAGE_FORMATS = [
    'JPEG', 'PNG', 'JPG', 'BMP', 'TIFF', 'WEBP', 'HEIC', 'AVIF'
]

# Audio formats for voice translation
SUPPORTED_AUDIO_FORMATS = [
    'WAV', 'MP3', 'MP4', 'WebM', 'OPUS'
]

# File size limits (in bytes)
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10MB

# Language support
AFRICAN_LANGUAGES = [
    ('rw', 'Kinyarwanda'),
    ('sw', 'Swahili'),
    ('yo', 'Yoruba'),
    ('ha', 'Hausa'),
    ('ig', 'Igbo'),
    ('zu', 'Zulu'),
    ('xh', 'Xhosa'),
    ('af', 'Afrikaans'),
    ('so', 'Somali'),
    ('am', 'Amharic'),
]

# OTP configuration
OTP_EXPIRY_MINUTES = 10
OTP_LENGTH = 6

# Email verification purposes
EMAIL_OTP_PURPOSES = [
    ('verification', 'Email Verification'),
    ('password_reset', 'Password Reset'),
    ('login', 'Login Verification'),
]

# Cloud storage providers
CLOUD_STORAGE_PROVIDERS = [
    ('s3', 'Amazon S3'),
    ('gcs', 'Google Cloud Storage'),
    ('azure', 'Azure Blob Storage'),
]

# API rate limits
DEFAULT_RATE_LIMIT_PER_MINUTE = 60
DEFAULT_RATE_LIMIT_PER_HOUR = 1000
DEFAULT_RATE_LIMIT_PER_DAY = 10000

# Processing timeouts (in seconds)
OCR_PROCESSING_TIMEOUT = 30
VOICE_PROCESSING_TIMEOUT = 60
TRANSLATION_TIMEOUT = 15

# Confidence score ranges
MIN_CONFIDENCE_SCORE = 0.0
MAX_CONFIDENCE_SCORE = 100.0
DEFAULT_CONFIDENCE_THRESHOLD = 70.0

# Error type choices for failure logging
ERROR_TYPE_CHOICES = [
    ('api_error', 'API Error'),
    ('timeout', 'Request Timeout'),
    ('auth_error', 'Authentication Error'),
    ('quota_exceeded', 'Quota Exceeded'),
    ('invalid_input', 'Invalid Input'),
    ('network_error', 'Network Error'),
    ('unknown', 'Unknown Error'),
]

# Extended translation service choices (including legacy providers)
EXTENDED_TRANSLATION_SERVICE_CHOICES = [
    ('gemini', 'Google Gemini'),
    ('openai', 'OpenAI GPT'),
    ('anthropic', 'Anthropic Claude'),
    ('gemini_legacy', 'Gemini Legacy'),
    ('auto', 'Automatic Selection'),
]

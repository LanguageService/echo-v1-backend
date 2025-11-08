"""
ASGI config for core project.
"""

import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

# Import after Django setup
from realtime import consumers
from realtime.middleware import JWTAuthMiddleware

websocket_urlpatterns = [
    path('ws/ocr/', consumers.OCRConsumer.as_asgi()),
    path('ws/voice/', consumers.VoiceConsumer.as_asgi()),
    path('ws/processing/', consumers.ProcessingConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": JWTAuthMiddleware(
        URLRouter(websocket_urlpatterns)
    ),
})

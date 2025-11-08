"""
WebSocket URL routing for real-time communication
"""

from django.urls import path
from realtime import consumers

websocket_urlpatterns = [
    path('ws/ocr/', consumers.OCRConsumer.as_asgi()),
    path('ws/voice/', consumers.VoiceConsumer.as_asgi()),
    path('ws/processing/', consumers.ProcessingConsumer.as_asgi()),
]
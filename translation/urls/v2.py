from django.urls import path, include
from rest_framework.routers import DefaultRouter
from ..views.v2 import TextTranslationV2ViewSet, SpeechTranslationV2ViewSet

router = DefaultRouter()
router.register(r'text', TextTranslationV2ViewSet, basename='v2-text-translation')
router.register(r'speech', SpeechTranslationV2ViewSet, basename='v2-speech-translation')

urlpatterns = [
    path('', include(router.urls)),
]

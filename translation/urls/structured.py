from django.urls import path, include
from rest_framework.routers import DefaultRouter
from ..views.structured import TextTranslationViewSet, SpeechTranslationViewSet, ImageTranslationViewSet



router = DefaultRouter()
router.register(r'text', TextTranslationViewSet, basename='text-translation')
router.register(r'speech', SpeechTranslationViewSet, basename='speech-translation')
router.register(r'image', ImageTranslationViewSet, basename='image-translation')

urlpatterns = [
    path('', include(router.urls)),
]

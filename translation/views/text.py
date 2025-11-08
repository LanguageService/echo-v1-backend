"""
Text Translation API Views

REST API endpoints for the Speak Africa voice translation application.
"""

import logging
import uuid
import time
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import models
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from django.conf import settings
from langdetect import detect
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

from ..models import Translation, UserSettings, LanguageSupport
from ..serializers import (
    TranslationSerializer, UserSettingsSerializer, LanguageSupportSerializer,
    VoiceTranslationRequestSerializer, VoiceTranslationResponseSerializer, TranslationHistorySerializer,
    TextTranslationRequestSerializer, TextTranslationResponseSerializer
)
from ..services import VoiceTranslationService, AsyncVoiceTranslationService, TranslationService
from utils.error_handler import ErrorHandler

logger = logging.getLogger(__name__)


class TextTranslationViewSet(ModelViewSet):
    """
    API ViewSet for Text-to-Text Translation.

    Provides endpoints for creating new text translations and viewing history.
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        This method is required for the swagger documentation to infer the serializer.
        It filters translations to only include those of type 'TEXT_TRANSLATION'.
        """
        return Translation.objects.filter(
            user=self.request.user,
            feature_type='TEXT_TRANSLATION'
        )

    @extend_schema(
        tags=['Text Translation'],
        summary='Translate Text',
        description='Translate text from a source language to a target language.',
        request=TextTranslationRequestSerializer,
        responses={
            201: TranslationSerializer,
            400: OpenApiResponse(description='Invalid request data'),
            500: OpenApiResponse(description='Internal server error')
        }
    )
    def create(self, request):
        """
        Create a new text translation.
        """
        serializer = TextTranslationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return ErrorHandler.handle_validation_error(serializer.errors)

        validated_data = serializer.validated_data
        text_to_translate = validated_data['text']
        target_language = validated_data['target_language']
        source_language = validated_data.get('source_language', 'auto')

        start_time = time.time()
        translation_service = TranslationService()

        detected_language = source_language
        if source_language == 'auto':
            try:
                detected_language = detect(text_to_translate)
            except Exception:
                detected_language = 'en'  # Fallback

        translation_result = translation_service.translate_text(
            text=text_to_translate,
            source_lang=detected_language,
            target_lang=target_language
        )

        processing_time = time.time() - start_time

        if not translation_result['success']:
            return ErrorHandler.format_error_response(
                "Translation failed",
                translation_result.get('error', 'An unknown error occurred.'),
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        translation_record = Translation.objects.create(
            user=request.user,
            original_text=text_to_translate,
            translated_text=translation_result['translated_text'],
            original_language=detected_language,
            target_language=target_language,
            total_processing_time=processing_time,
            feature_type='TEXT_TRANSLATION'
        )

        response_serializer = TranslationSerializer(translation_record, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=['Text Translation'],
        summary='List Text Translations',
        description='Get a list of your past text translations.',
        responses={200: TranslationSerializer(many=True)}
    )
    def list(self, request):
        """
        Return a list of all text translations for the current user.
        """
        queryset = self.get_queryset().order_by('-date_created')
        serializer = TranslationSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @extend_schema(
        tags=['Text Translation'],
        summary='Retrieve a Text Translation',
        description='Get the details of a specific text translation.',
        responses={
            200: TranslationSerializer,
            404: OpenApiResponse(description='Not Found')
        }
    )

    def retrieve(self, request, pk=None):
        """
        Return a single text translation instance.
        """
        queryset = self.get_queryset()
        translation = get_object_or_404(queryset, pk=pk)
        serializer = TranslationSerializer(translation, context={'request': request})
        return Response(serializer.data)
    

    @extend_schema(
        tags=['Text Translation'],
        summary='Update a Text Translation',
        description='Update the details of a specific text translation.'
        )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        tags=['Text Translation'],
        summary='Update a Text Translation',
        description='Update the details of a specific text translation.'
        )   
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)
    
    @extend_schema(
        tags=['Text Translation'],
        summary='Delete a Text Translation',
        description='Delete a specific text translation.'
        )  
    
    def destroy(self, request, *args, **kwargs):
        """
        Delete a specific text translation.
        """
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)



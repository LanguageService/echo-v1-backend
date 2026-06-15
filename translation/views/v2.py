import time
from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema

from .structured import BaseTranslationViewSet
from ..models import TextTranslation, SpeechTranslation
from ..serializers import (
    TextTranslationSerializer, SpeechTranslationSerializer,
    TextShortRequestSerializer, SpeechShortRequestSerializer,
    STTRequestSerializer, TTSRequestSerializer,
    TextTranslationTitleSerializer, SpeechTranslationTitleSerializer
)
from ..orchestrator_v2 import TranslationOrchestratorV2
from ..choices import TranslationMode

@extend_schema(tags=["Text Translation V2"])
class TextTranslationV2ViewSet(BaseTranslationViewSet):
    queryset = TextTranslation.objects.all()
    serializer_class = TextTranslationSerializer
    patch_serializer_class = TextTranslationTitleSerializer

    @extend_schema(
        request=TextShortRequestSerializer,
        responses={201: TextTranslationSerializer}
    )
    @action(detail=False, methods=['post'], url_path='base')
    def base(self, request):
        """Short sentence translation (V2 Custom Models)"""
        serializer = TextShortRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        target_lang = serializer.validated_data['target_language']
        source_lang = serializer.validated_data.get('source_language', 'auto')
        
        if target_lang not in ['en', 'rw'] or (source_lang not in ['en', 'rw', 'auto']):
            return Response({"error": "V2 only supports English and Kinyarwanda"}, status=status.HTTP_400_BAD_REQUEST)
        
        orchestrator = TranslationOrchestratorV2()
        result = orchestrator.translate_text(
            user=request.user,
            text=serializer.validated_data['text'],
            target_lang=target_lang,
            source_lang=source_lang,
            is_sms=serializer.validated_data.get('is_sms', False),
            mode=TranslationMode.SHORT,
            title=request.data.get('title')
        )
        return Response(result, status=status.HTTP_201_CREATED if result.get('success') else status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=["Speech Translation V2"])
class SpeechTranslationV2ViewSet(BaseTranslationViewSet):
    queryset = SpeechTranslation.objects.all()
    serializer_class = SpeechTranslationSerializer
    patch_serializer_class = SpeechTranslationTitleSerializer
    parser_classes = (MultiPartParser, FormParser)

    @extend_schema(
        request=SpeechShortRequestSerializer,
        responses={201: SpeechTranslationSerializer}
    )
    @action(detail=False, methods=['post'], url_path='base')
    def base(self, request):
        """Short speech translation STS (V2 Custom Models)"""
        serializer = SpeechShortRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        target_lang = serializer.validated_data['target_language']
        source_lang = serializer.validated_data.get('source_language', 'auto')
        
        if target_lang not in ['en', 'rw'] or (source_lang not in ['en', 'rw', 'auto']):
            return Response({"error": "V2 only supports English and Kinyarwanda"}, status=status.HTTP_400_BAD_REQUEST)

        orchestrator = TranslationOrchestratorV2()
        result = orchestrator.translate_speech(
            user=request.user,
            audio_file=serializer.validated_data.get('audio_file'),
            target_lang=target_lang,
            source_lang=source_lang,
            mode=TranslationMode.SHORT,
            original_file_url=serializer.validated_data.get('original_file_url'),
            title=request.data.get('title')
        )
        return Response(result, status=status.HTTP_201_CREATED if result.get('success') else status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        request=STTRequestSerializer,
        responses={201: SpeechTranslationSerializer}
    )
    @action(detail=False, methods=['post'], parser_classes=(MultiPartParser, FormParser))
    def stt(self, request):
        """Speech to Text Translation (V2 Custom Models)"""
        serializer = STTRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        source_lang = serializer.validated_data.get('source_language') or serializer.validated_data.get('language', 'auto')
        target_lang = serializer.validated_data.get('target_language') or serializer.validated_data.get('language', 'auto')
        
        if target_lang not in ['en', 'rw'] or (source_lang not in ['en', 'rw', 'auto']):
            return Response({"error": "V2 only supports English and Kinyarwanda"}, status=status.HTTP_400_BAD_REQUEST)

        orchestrator = TranslationOrchestratorV2()
        result = orchestrator.speech_to_text(
            user=request.user,
            audio_file=serializer.validated_data.get('audio_file'),
            source_language=source_lang,
            target_language=target_lang,
            mode=TranslationMode.SHORT,
            session_id=serializer.validated_data.get('session_id'),
            original_file_url=serializer.validated_data.get('original_file_url'),
            title=request.data.get('title')
        )
        return Response(result, status=status.HTTP_201_CREATED if result.get('success') else status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        request=TTSRequestSerializer,
        responses={201: SpeechTranslationSerializer}
    )
    @action(detail=False, methods=['post'])
    def tts(self, request):
        """Text to Speech Translation (V2 Custom Models)"""
        serializer = TTSRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        source_lang = serializer.validated_data.get('source_language') or serializer.validated_data.get('language', 'en')
        target_lang = serializer.validated_data.get('target_language') or serializer.validated_data.get('language', 'en')
        
        if target_lang not in ['en', 'rw'] or (source_lang not in ['en', 'rw']):
            return Response({"error": "V2 only supports English and Kinyarwanda"}, status=status.HTTP_400_BAD_REQUEST)

        orchestrator = TranslationOrchestratorV2()
        result = orchestrator.text_to_speech(
            user=request.user,
            text=serializer.validated_data['text'],
            source_language=source_lang,
            target_language=target_lang,
            voice=serializer.validated_data.get('voice'),
            mode=TranslationMode.SHORT,
            session_id=serializer.validated_data.get('session_id'),
            title=request.data.get('title')
        )
        return Response(result, status=status.HTTP_201_CREATED if result.get('success') else status.HTTP_400_BAD_REQUEST)

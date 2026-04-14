import time
from rest_framework import viewsets, status, permissions, mixins
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from ..models import TextTranslation, SpeechTranslation, ImageTranslation
from ..serializers import (
    TextTranslationSerializer, SpeechTranslationSerializer, ImageTranslationSerializer,
    TextShortRequestSerializer, TextLargeRequestSerializer,
    SpeechShortRequestSerializer, SpeechLargeRequestSerializer,
    ImageTranslationRequestSerializer,
    TextTranslationTitleSerializer, SpeechTranslationTitleSerializer, ImageTranslationTitleSerializer,
    STTRequestSerializer, TTSRequestSerializer
)
from ..orchestrator import TranslationOrchestrator
from ..choices import TranslationMode, TranslationStatus, SpeechServiceType
from ..tasks import async_ebook_translation_task, async_voice_translation_task, async_stt_task, async_tts_task



class BaseTranslationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet
):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action in ['partial_update', 'update']:
            return self.patch_serializer_class
        return self.serializer_class

    def update(self, request, *args, **kwargs):
        # PATCH is allowed, but PUT is not recommended if it's not restricted
        # However, for simplicity and to follow user request "PATCH should only be title",
        # let's restrict updates to title only.
        if self.action == 'update':
            return Response(
                {"error": "Full updates (PUT) are not allowed. Use PATCH to update the title."}, 
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )
        return super().update(request, *args, **kwargs)


@extend_schema(tags=["Text Translation"])
class TextTranslationViewSet(BaseTranslationViewSet):
    queryset = TextTranslation.objects.all()
    serializer_class = TextTranslationSerializer
    patch_serializer_class = TextTranslationTitleSerializer
    filterset_fields = ['is_sms', 'mode', 'date_created', 'target_language', 'original_language', 'title', 'status']

    @extend_schema(
        request=TextShortRequestSerializer,
        responses={201: TextTranslationSerializer}
    )
    @action(detail=False, methods=['post'], url_path='base')
    def base(self, request):
        """Short sentence translation"""
        serializer = TextShortRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        orchestrator = TranslationOrchestrator()
        result = orchestrator.translate_text(
            user=request.user,
            text=serializer.validated_data['text'],
            target_lang=serializer.validated_data['target_language'],
            source_lang=serializer.validated_data.get('source_language', 'auto'),
            is_sms=serializer.validated_data.get('is_sms', False),
            mode=TranslationMode.SHORT,
            title=request.data.get('title')
        )
        return Response(result, status=status.HTTP_201_CREATED if result.get('success') else status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        request=TextLargeRequestSerializer,
        responses={202: OpenApiResponse(description="Accepted for background processing")}
    )
    @action(detail=False, methods=['post'], url_path='document', parser_classes=(MultiPartParser, FormParser))
    def document(self, request):
        """Document/Large text translation"""
        serializer = TextLargeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Determine original text if provided, otherwise it's file-based
        original_text = ""
        # Not handling 'text' in TextLargeRequestSerializer as per user "only show items needed"
        # If it's a file, the task handler will process it.
        
        translation = TextTranslation.objects.create(
            user=request.user,
            title=serializer.validated_data.get('title') or f"Text Document {int(time.time())}",
            original_language=serializer.validated_data.get('source_language', 'auto'),
            target_language=serializer.validated_data['target_language'],
            original_file_url=serializer.validated_data.get('original_file_url'),
            mode=TranslationMode.LARGE,
            status=TranslationStatus.PENDING
        )
        
        local_file_path = None
        if serializer.validated_data.get('file'):
            # Save the file to translation instance if it's there
            translation.original_file = serializer.validated_data['file']
            translation.save()
            # The async task will handle the rest.
        
        async_ebook_translation_task.delay(str(translation.id))
        return Response({
            "success": True,
            "translation_id": str(translation.id),
            "status": "Accepted for background processing"
        }, status=status.HTTP_202_ACCEPTED)



@extend_schema(tags=["Speech Translation"])
class SpeechTranslationViewSet(BaseTranslationViewSet):
    queryset = SpeechTranslation.objects.all()
    serializer_class = SpeechTranslationSerializer
    patch_serializer_class = SpeechTranslationTitleSerializer
    parser_classes = (MultiPartParser, FormParser)
    filterset_fields = ['speech_service', 'target_language', 'original_language', 'mode', 'date_created', 'title', 'status']

    @extend_schema(
        request=SpeechShortRequestSerializer,
        responses={201: SpeechTranslationSerializer}
    )
    @action(detail=False, methods=['post'], url_path='base')
    def base(self, request):
        """Short speech translation (STS)"""
        serializer = SpeechShortRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        orchestrator = TranslationOrchestrator()
        result = orchestrator.translate_speech(
            user=request.user,
            audio_file=serializer.validated_data.get('audio_file'),
            target_lang=serializer.validated_data['target_language'],
            source_lang=serializer.validated_data.get('source_language', 'auto'),
            mode=TranslationMode.SHORT,
            original_file_url=serializer.validated_data.get('original_file_url'),
            title=request.data.get('title')
        )
        return Response(result, status=status.HTTP_201_CREATED if result.get('success') else status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        request=SpeechLargeRequestSerializer,
        responses={202: OpenApiResponse(description="Accepted for background processing")}
    )
    @action(detail=False, methods=['post'], url_path='document', parser_classes=(MultiPartParser, FormParser))
    def document(self, request):
        """Large speech translation (STS)"""
        serializer = SpeechLargeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        from ..choices import SpeechServiceType
        translation = SpeechTranslation.objects.create(
            user=request.user,
            title=serializer.validated_data.get('title') or f"Speech Document {int(time.time())}",
            original_language=serializer.validated_data.get('source_language', 'auto'),
            target_language=serializer.validated_data['target_language'],
            mode=TranslationMode.LARGE,
            original_audio_url=serializer.validated_data.get('original_file_url'),
            status=TranslationStatus.PENDING,
            speech_service=serializer.validated_data.get('speech_service', SpeechServiceType.STS)
        )
        
        if serializer.validated_data.get('audio_file'):
            translation.original_audio.save(
                f"large_input_{translation.id}.wav", 
                serializer.validated_data['audio_file']
            )
        
        async_voice_translation_task.delay(str(translation.id))
        return Response({
            "success": True,
            "translation_id": str(translation.id),
            "status": "Accepted for background processing"
        }, status=status.HTTP_202_ACCEPTED)


    @extend_schema(
        request=STTRequestSerializer,
        responses={201: SpeechTranslationSerializer, 202: OpenApiResponse(description="Accepted for background processing")}
    )
    @action(detail=False, methods=['post'], parser_classes=(MultiPartParser, FormParser))
    def stt(self, request):
        """
        Speech to Text Translation
        """
        serializer = STTRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        mode = serializer.validated_data.get('mode', TranslationMode.SHORT)
        
        if mode == TranslationMode.SHORT:
            orchestrator = TranslationOrchestrator()
            
            # Use source/target or fall back to legacy 'language'
            source_lang = serializer.validated_data.get('source_language') or serializer.validated_data.get('language', 'auto')
            target_lang = serializer.validated_data.get('target_language') or serializer.validated_data.get('language', 'auto')
            
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
        else:
            # LARGE mode - Async
            source_lang = serializer.validated_data.get('source_language') or serializer.validated_data.get('language', 'auto')
            target_lang = serializer.validated_data.get('target_language') or serializer.validated_data.get('language', 'auto')
            
            translation = SpeechTranslation.objects.create(
                user=request.user,
                title=request.data.get('title') or f"STT Large {int(time.time())}",
                original_language=source_lang,
                target_language=target_lang,
                mode=TranslationMode.LARGE,
                session_id=serializer.validated_data.get('session_id'),
                original_audio_url=serializer.validated_data.get('original_file_url'),
                status=TranslationStatus.PENDING,
                speech_service=SpeechServiceType.STT
            )
            
            if serializer.validated_data.get('audio_file'):
                translation.original_audio.save(
                    f"stt_large_input_{translation.id}.wav", 
                    serializer.validated_data['audio_file']
                )
            
            async_stt_task.delay(
                user_id=request.user.id,
                audio_file_path=None, # It's in the translation record
                translation_id=str(translation.id),
                source_language=translation.original_language,
                target_language=translation.target_language,
                mode=TranslationMode.LARGE,
                session_id=translation.session_id,
                original_file_url=translation.original_audio_url
            )
            return Response({
                "success": True,
                "translation_id": str(translation.id),
                "status": "Accepted for background processing"
            }, status=status.HTTP_202_ACCEPTED)

    @extend_schema(
        request=TTSRequestSerializer,
        responses={201: SpeechTranslationSerializer, 202: OpenApiResponse(description="Accepted for background processing")}
    )
    @action(detail=False, methods=['post'])
    def tts(self, request):
        """
        Text to Speech Translation
        """
        serializer = TTSRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        mode = serializer.validated_data.get('mode', TranslationMode.SHORT)
        
        if mode == TranslationMode.SHORT:
            orchestrator = TranslationOrchestrator()
            
            source_lang = serializer.validated_data.get('source_language') or serializer.validated_data.get('language', 'en')
            target_lang = serializer.validated_data.get('target_language') or serializer.validated_data.get('language', 'en')
            
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
        else:
            # LARGE mode - Async
            source_lang = serializer.validated_data.get('source_language') or serializer.validated_data.get('language', 'en')
            target_lang = serializer.validated_data.get('target_language') or serializer.validated_data.get('language', 'en')
            
            translation = SpeechTranslation.objects.create(
                user=request.user,
                title=request.data.get('title') or f"TTS Large {int(time.time())}",
                original_text=serializer.validated_data['text'],
                original_language=source_lang,
                target_language=target_lang,
                mode=TranslationMode.LARGE,
                session_id=serializer.validated_data.get('session_id'),
                status=TranslationStatus.PENDING,
                speech_service=SpeechServiceType.TTS
            )
            
            async_tts_task.delay(
                user_id=request.user.id,
                text=translation.original_text,
                source_language=translation.original_language,
                target_language=translation.target_language,
                translation_id=str(translation.id),
                voice=serializer.validated_data.get('voice'),
                mode=TranslationMode.LARGE,
                session_id=translation.session_id
            )
            return Response({
                "success": True,
                "translation_id": str(translation.id),
                "status": "Accepted for background processing",
                "original_text": translation.original_text,
                "translated_text": translation.translated_text
            }, status=status.HTTP_202_ACCEPTED)



@extend_schema(tags=["Image Translation"])
class ImageTranslationViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet
):
    queryset = ImageTranslation.objects.all()
    serializer_class = ImageTranslationSerializer
    patch_serializer_class = ImageTranslationTitleSerializer
    parser_classes = (MultiPartParser, FormParser)

    def create(self, request, *args, **kwargs):
        """Image OCR & Translation"""
        serializer = ImageTranslationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        orchestrator = TranslationOrchestrator()
        result = orchestrator.translate_image(
            user=request.user,
            image_file=serializer.validated_data['image'],
            target_lang=serializer.validated_data['target_language'],
            source_lang=serializer.validated_data.get('source_language', 'auto'),
            title=request.data.get('title')
        )
        return Response(result, status=status.HTTP_201_CREATED if result.get('success') else status.HTTP_400_BAD_REQUEST)


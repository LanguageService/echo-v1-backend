import time
from django.db import transaction
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
from ..models import AnonymousTrial

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')

def check_and_increment_trial(request):
    if getattr(request.user, 'is_authenticated', False):
        return None  # Authenticated users have no trial limit here
    
    ip_address = get_client_ip(request)
    trial, created = AnonymousTrial.objects.get_or_create(ip_address=ip_address)
    
    if trial.attempts >= 3:
        return Response({"error": "TRIAL_LIMIT_REACHED", "message": "You have reached the maximum number of free trials. Please sign up to continue."}, status=status.HTTP_403_FORBIDDEN)
    
    trial.attempts += 1
    trial.save()
    return None



from billing.permissions import HasTranslationQuota

class BaseTranslationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet
):
    permission_classes = [permissions.AllowAny, HasTranslationQuota]
    filter_backends = [DjangoFilterBackend]

    @action(detail=False, methods=['post'], url_path='presigned-url')
    def presigned_url(self, request):
        """Generate a presigned URL for direct S3 uploads"""
        if not getattr(request.user, 'is_authenticated', False):
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
            
        file_name = request.data.get('file_name')
        file_type = request.data.get('file_type') # e.g., 'audio', 'document'
        content_type = request.data.get('content_type')
        
        if not file_name or not file_type:
            return Response({"error": "file_name and file_type are required"}, status=status.HTTP_400_BAD_REQUEST)
            
        from ..cloud_storage import cloud_storage
        url_data = cloud_storage.generate_presigned_url(
            file_name=file_name,
            file_type=file_type,
            user_id=str(request.user.id),
            content_type=content_type
        )
        
        if not url_data:
            return Response({"error": "Cloud storage not configured or failed to generate URL"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        return Response(url_data)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user if getattr(self.request.user, 'is_authenticated', False) else None)

    def get_queryset(self):
        if getattr(self.request.user, 'is_authenticated', False):
            return self.queryset.filter(user=self.request.user)
        return self.queryset.none()

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
        trial_response = check_and_increment_trial(request)
        if trial_response: return trial_response

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
        trial_response = check_and_increment_trial(request)
        if trial_response: return trial_response

        import os
        import tempfile

        serializer = TextLargeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        translation = TextTranslation.objects.create(
            user=request.user,
            title=serializer.validated_data.get('title') or f"Text Document {int(time.time())}",
            original_language=serializer.validated_data.get('source_language', 'auto'),
            target_language=serializer.validated_data['target_language'],
            original_file_url=serializer.validated_data.get('original_file_url') or None,
            mode=TranslationMode.LARGE,
            status=TranslationStatus.PENDING
        )
        
        local_file_path = None
        uploaded_file = serializer.validated_data.get('file')
        if uploaded_file:
            # TextTranslation has no FileField — write to a temp file and pass path to the task
            suffix = os.path.splitext(uploaded_file.name)[-1] if uploaded_file.name else ''
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            for chunk in uploaded_file.chunks():
                tmp_file.write(chunk)
            tmp_file.flush()
            tmp_file.close()
            local_file_path = tmp_file.name
        
        _tid = str(translation.id)
        _path = local_file_path
        transaction.on_commit(lambda: async_ebook_translation_task.delay(_tid, _path))
        return Response({
            "success": True,
            "translation_id": str(translation.id),
            "status": "Accepted for background processing"
        }, status=status.HTTP_202_ACCEPTED)

    @extend_schema(
        request=TextLargeRequestSerializer,
        responses={200: TextTranslationSerializer}
    )
    @action(detail=False, methods=['post'], url_path='document-direct', parser_classes=(MultiPartParser, FormParser))
    def document_direct(self, request):
        """Direct/Synchronous Document translation (blocks until finished)"""
        trial_response = check_and_increment_trial(request)
        if trial_response: return trial_response

        import os
        import tempfile

        serializer = TextLargeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        translation = TextTranslation.objects.create(
            user=request.user,
            title=serializer.validated_data.get('title') or f"Text Document {int(time.time())}",
            original_language=serializer.validated_data.get('source_language', 'auto'),
            target_language=serializer.validated_data['target_language'],
            original_file_url=serializer.validated_data.get('original_file_url') or None,
            mode=TranslationMode.LARGE,
            status=TranslationStatus.PENDING
        )
        
        local_file_path = None
        tmp_file = None
        uploaded_file = serializer.validated_data.get('file')
        if uploaded_file:
            # InMemoryUploadedFile has no .path — write to a named temp file first
            # TextTranslation has no FileField, so we only need the temp path for the service
            suffix = os.path.splitext(uploaded_file.name)[-1] if uploaded_file.name else ''
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            for chunk in uploaded_file.chunks():
                tmp_file.write(chunk)
            tmp_file.flush()
            tmp_file.close()
            local_file_path = tmp_file.name
        
        try:
            from ..services import DocumentTranslationService
            service = DocumentTranslationService()
            result = service.process_document_translation(str(translation.id), local_file_path)
        finally:
            # Always clean up the temp file
            if tmp_file and os.path.exists(tmp_file.name):
                os.unlink(tmp_file.name)
        
        translation.refresh_from_db()
        serializer_response = TextTranslationSerializer(translation, context={'request': request})
        
        if result.get('success'):
            return Response(serializer_response.data, status=status.HTTP_200_OK)
        else:
            return Response({
                "success": False,
                "error": result.get('error', 'Translation failed'),
                "translation": serializer_response.data
            }, status=status.HTTP_400_BAD_REQUEST)



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
        trial_response = check_and_increment_trial(request)
        if trial_response: return trial_response

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

    # ------------------------------------------------------------------
    # Demo endpoint — unauthenticated, IP-based 3-attempt trial limit
    # ------------------------------------------------------------------
    DEMO_TRIAL_LIMIT = 3

    @extend_schema(
        tags=["Demo"],
        summary="Demo Speech Translation (unauthenticated)",
        description=(
            "Public speech-to-speech translation endpoint for the landing-page demo. "
            "No authentication required. Limited to 3 attempts per IP address, tracked "
            "in the AnonymousTrial table. Returns trial progress in every response."
        ),
        request=SpeechShortRequestSerializer,
        responses={
            200: SpeechTranslationSerializer,
            403: OpenApiResponse(description="Trial limit reached"),
            400: OpenApiResponse(description="Validation error"),
        },
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="demo",
        permission_classes=[],           # AllowAny — no auth required
        parser_classes=(MultiPartParser, FormParser),
    )
    def demo(self, request):
        """
        Dedicated demo endpoint for unauthenticated visitors.

        - Accepts an audio file and language pair.
        - Enforces a hard limit of 3 attempts per IP address.
        - Returns trial_attempts_used and trial_attempts_remaining in the response
          so the frontend can keep its counter in sync.
        - Uses the full TranslationOrchestrator pipeline (same quality as paid).
        """
        LIMIT = self.DEMO_TRIAL_LIMIT
        ip_address = get_client_ip(request)

        # Fetch or create the trial record for this IP
        trial, _ = AnonymousTrial.objects.get_or_create(ip_address=ip_address)

        # Enforce limit BEFORE running translation (don't waste AI credits)
        if trial.attempts >= LIMIT:
            return Response(
                {
                    "error": "TRIAL_LIMIT_REACHED",
                    "message": (
                        "You have used all 3 free demo attempts. "
                        "Create a free account to continue translating."
                    ),
                    "trial_attempts_used": trial.attempts,
                    "trial_attempts_remaining": 0,
                    "trial_limit": LIMIT,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Validate request data
        serializer = SpeechShortRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "Invalid request", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Run the full STS pipeline (same as /speech/base/)
        orchestrator = TranslationOrchestrator()
        result = orchestrator.translate_speech(
            user=None,              # anonymous — no user object
            audio_file=serializer.validated_data.get("audio_file"),
            target_lang=serializer.validated_data["target_language"],
            source_lang=serializer.validated_data.get("source_language", "auto"),
            mode=TranslationMode.SHORT,
            original_file_url=serializer.validated_data.get("original_file_url"),
            title="Demo Translation",
        )

        if not result.get("success"):
            # Translation failed — do NOT consume a trial attempt
            return Response(
                {
                    "error": result.get("error", "Translation failed"),
                    "trial_attempts_used": trial.attempts,
                    "trial_attempts_remaining": LIMIT - trial.attempts,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Success — increment the attempt counter
        trial.attempts += 1
        trial.save(update_fields=["attempts", "last_used"])

        attempts_used = trial.attempts
        attempts_remaining = max(0, LIMIT - attempts_used)

        return Response(
            {
                **result,
                "trial_attempts_used": attempts_used,
                "trial_attempts_remaining": attempts_remaining,
                "trial_limit": LIMIT,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=SpeechLargeRequestSerializer,
        responses={202: OpenApiResponse(description="Accepted for background processing")}
    )
    @action(detail=False, methods=['post'], url_path='document', parser_classes=(MultiPartParser, FormParser))
    def document(self, request):
        """Large speech translation (STS)"""
        trial_response = check_and_increment_trial(request)
        if trial_response: return trial_response

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
            from ..cloud_storage import cloud_storage
            if cloud_storage.is_available():
                url = cloud_storage.upload_voice_input_file(
                    file=serializer.validated_data['audio_file'],
                    language=serializer.validated_data.get('source_language', 'auto'),
                    user_id=str(request.user.id if request.user.is_authenticated else 'anonymous')
                )
                if url:
                    translation.original_audio_url = url
                    translation.original_audio.name = None
                    translation.save()
            else:
                translation.original_audio.save(
                    f"large_input_{translation.id}.wav", 
                    serializer.validated_data['audio_file']
                )
        
        _tid = str(translation.id)
        transaction.on_commit(lambda: async_voice_translation_task.delay(_tid))
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
        trial_response = check_and_increment_trial(request)
        if trial_response: return trial_response

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
                from ..cloud_storage import cloud_storage
                if cloud_storage.is_available():
                    url = cloud_storage.upload_voice_input_file(
                        file=serializer.validated_data['audio_file'],
                        language=serializer.validated_data.get('source_language', 'auto'),
                        user_id=str(request.user.id if request.user.is_authenticated else 'anonymous')
                    )
                    if url:
                        translation.original_audio_url = url
                        translation.original_audio.name = None
                        translation.save()
                else:
                    translation.original_audio.save(
                        f"stt_large_input_{translation.id}.wav", 
                        serializer.validated_data['audio_file']
                    )
            
            _stt_kwargs = dict(
                user_id=request.user.id,
                audio_file_path=None,  # It's in the translation record
                translation_id=str(translation.id),
                source_language=translation.original_language,
                target_language=translation.target_language,
                mode=TranslationMode.LARGE,
                session_id=translation.session_id,
                original_file_url=translation.original_audio_url
            )
            transaction.on_commit(lambda: async_stt_task.delay(**_stt_kwargs))
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
        trial_response = check_and_increment_trial(request)
        if trial_response: return trial_response

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
            
            _tts_kwargs = dict(
                user_id=request.user.id,
                text=translation.original_text,
                source_language=translation.original_language,
                target_language=translation.target_language,
                translation_id=str(translation.id),
                voice=serializer.validated_data.get('voice'),
                mode=TranslationMode.LARGE,
                session_id=translation.session_id
            )
            transaction.on_commit(lambda: async_tts_task.delay(**_tts_kwargs))
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


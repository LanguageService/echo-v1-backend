from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, OpenApiResponse

from translation.models import TextTranslation, SpeechTranslation, ImageTranslation
from translation.serializers import UnifiedTranslationSerializer
import logging

logger = logging.getLogger(__name__)

@extend_schema(tags=["Translation History"])
class GeneralTranslationHistoryAPIView(APIView):
    """Endpoint for retrieving all translation history (Voice and Text)"""
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary='Get All Translation History',
        description='Get a list of all recent translations (Voice and Text) with their feature type.',
        parameters=[
            OpenApiParameter(name='limit', description='Number of results to return', type=int),
            OpenApiParameter(name='offset', description='Pagination offset', type=int),
        ],
        responses={
            200: UnifiedTranslationSerializer(many=True),
            400: OpenApiResponse(description='Invalid query parameters'),
            401: OpenApiResponse(description='Authentication required'),
            500: OpenApiResponse(description='Internal server error')
        }
    )
    def get(self, request, *args, **kwargs):
        """Get all translation history"""
        try:
            # Validate query parameters
            limit = int(request.query_params.get('limit', 20))
            offset = int(request.query_params.get('offset', 0))
            
            from itertools import chain
            
            # Build querysets for authenticated user across all translation types
            text_qs = TextTranslation.objects.filter(user=request.user)
            speech_qs = SpeechTranslation.objects.filter(user=request.user)
            image_qs = ImageTranslation.objects.filter(user=request.user)
            
            # Combine and sort by date_created (reverse)
            # Note: For large datasets, we might want a different approach (like a union or separate endpoints),
            # but for history this combined list is what's expected.
            all_translations = sorted(
                chain(text_qs, speech_qs, image_qs),
                key=lambda x: x.date_created,
                reverse=True
            )
            
            total_count = len(all_translations)
            translations = all_translations[offset:offset + limit]
            
            # Serialize results using the Unified serializer
            serializer = UnifiedTranslationSerializer(translations, many=True, context={'request': request})
            
            return Response({
                'count': total_count,
                'offset': offset,
                'limit': limit,
                'results': serializer.data
            }, status=status.HTTP_200_OK)
            
        except ValueError:
             return Response({
                'error': 'Invalid query parameters. Limit and offset must be integers.'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error retrieving general translation history: {str(e)}")
            return Response({
                'error': f'Failed to retrieve history: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

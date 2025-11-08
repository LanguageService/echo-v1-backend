"""
Statistics Views

API views for user and system statistics tracking.
"""

from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema

from users.services import UserStatsService


@extend_schema(tags=["Statistics"])
class StatsViewSet(ViewSet):
    """
    A ViewSet for user and system statistics.
    """

    @action(detail=False, methods=['get'], permission_classes=[AllowAny], url_path='info')
    def info(self, request):
        """Statistics API information endpoint."""
        data = {
            'api_name': 'OCR & Voice Translation Statistics API',
            'version': '1.0.0',
            'description': 'Comprehensive user and system statistics tracking',
            'endpoints': {
                'personal_stats': '/statistics/user/',
                'admin_stats': '/statistics/admin/',
                'health': '/statistics/health/',
            },
            'features': [
                'Personal usage statistics',
                'OCR processing metrics',
                'Voice translation analytics',
                'Admin system-wide statistics',
                'Success/failure rate tracking',
                'Language usage analytics',
                'Processing time metrics'
            ],
            'authentication': 'JWT Bearer Token',
            'documentation': '/api/schema/swagger-ui/'
        }
        return Response(data)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny], url_path='health')
    def health_check(self, request):
        """Statistics health check endpoint."""
        data = {
            'status': 'healthy',
            'service': 'statistics',
            'version': '1.0.0'
        }
        return Response(data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated], url_path='user')
    def personal_stats(self, request):
        """
        Get personal user statistics including OCR and voice translation usage.
        Requires authentication.
        """
        try:
            user = request.user
            stats = UserStatsService.get_user_statistics(user=user)
            return Response({
                'status': 'success',
                'user_id': str(user.id),
                'stats': stats
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'Failed to retrieve user statistics',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser], url_path='admin')
    def admin_stats(self, request):
        """
        Get system-wide statistics for administrators.
        Requires admin permissions.
        """
        try:
            stats = UserStatsService.get_user_statistics()
            return Response({
                'status': 'success',
                'admin_stats': stats
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'Failed to retrieve admin statistics',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

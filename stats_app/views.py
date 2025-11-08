"""
Statistics Views

API views for user and system statistics tracking.
"""

from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status

from users.services import UserStatsService


@api_view(['GET'])
@permission_classes([])
def stats_api_info(request):
    """Statistics API information endpoint."""
    return JsonResponse({
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
    })


@api_view(['GET'])
@permission_classes([])
def stats_health_check(request):
    """Statistics health check endpoint."""
    return JsonResponse({
        'status': 'healthy',
        'service': 'statistics',
        'version': '1.0.0'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def personal_stats_view(request):
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



@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_stats_view(request):
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

from django.urls import path
from . import views

urlpatterns = [
    # API Information
    path('', views.api_info, name='api_info'),
    path('health/', views.health_check, name='health_check'),
    
    # OCR Processing
    path('process/', views.process_image, name='process_image'),
    
    # Results Management
    path('results/', views.list_results, name='list_results'),
    path('results/<int:result_id>/', views.get_result, name='get_result'),
    path('results/<int:result_id>/delete/', views.delete_result, name='delete_result'),
    
    # Translation Services
    path('translation-services/', views.translation_services_status, name='translation_services_status'),
]

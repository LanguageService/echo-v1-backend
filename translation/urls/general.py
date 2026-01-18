from django.urls import path
from .. import views

urlpatterns = [
    path('', views.GeneralTranslationHistoryAPIView.as_view(), name='general_translation_history'),
]

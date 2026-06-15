from django.urls import path
from translation import views

urlpatterns = [
    path('', views.GeneralTranslationHistoryAPIView.as_view(), name='general_translation_history'),
    path('<uuid:pk>/favorite/', views.ToggleFavoriteAPIView.as_view(), name='toggle_favorite'),
]

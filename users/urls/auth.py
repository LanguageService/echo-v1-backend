from django.urls import path
from rest_framework.routers import DefaultRouter

from users.views import AuthViewSet, CustomTokenObtainPairView, CustomTokenRefreshView

router = DefaultRouter()
router.register("", AuthViewSet, "auth")


urlpatterns = router.urls

urlpatterns += [
    path("login/", CustomTokenObtainPairView.as_view(), name="login"),
    path("token/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
]

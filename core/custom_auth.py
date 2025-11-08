from rest_framework.authentication import BasicAuthentication
from django.contrib.auth import authenticate
from django.conf import settings


class CustomBasicAuthentication(BasicAuthentication):
    def authenticate_credentials(self, email, password, request=None):
        if email not in settings.API_DOCUMENTATION_ALLOWED_EMAILS:
            return None

        user = authenticate(request=request, email=email, password=password)
        if user is None:
            return None
        return (user, None)

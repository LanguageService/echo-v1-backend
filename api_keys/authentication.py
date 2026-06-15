from rest_framework import authentication
from rest_framework import exceptions
from .models import DeveloperApp

class DeveloperTokenAuthentication(authentication.BaseAuthentication):
    """
    Authenticates requests from Developer APIs using client_id and client_secret.
    Typically passed in headers:
    X-Client-Id: ...
    X-Client-Secret: ...
    """
    def authenticate(self, request):
        client_id = request.headers.get('X-Client-Id')
        client_secret = request.headers.get('X-Client-Secret')

        if not client_id or not client_secret:
            return None

        try:
            app = DeveloperApp.objects.get(client_id=client_id, client_secret=client_secret)
        except DeveloperApp.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid Client Credentials')

        if not app.is_active:
            raise exceptions.AuthenticationFailed('Developer App is inactive')

        # Attach channel to the request so downstream logic knows it's an API request
        request.channel = 'API'
        
        # Attach the app user to the request
        return (app.user, None)

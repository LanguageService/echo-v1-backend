from django.urls import path, include
from django.conf import settings

urlpatterns = [
    # New structured API (Text, Speech, Image)
    path('', include('translation.urls.structured')),
    
    # Base/Infrastructure endpoints (Languages, Settings, Health)
    path('base/', include('translation.urls.base')),
    
    # Translation History
    path('history/', include('translation.urls.general')),
]

if getattr(settings, 'CUSTOM_MODEL', False):
    urlpatterns.append(
        # V2 API endpoints (Custom Models)
        path('v2/', include('translation.urls.v2')),
    )


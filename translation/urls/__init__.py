from django.urls import path, include

urlpatterns = [
    # New structured API (Text, Speech, Image)
    path('', include('translation.urls.structured')),
    
    # Base/Infrastructure endpoints (Languages, Settings, Health)
    path('base/', include('translation.urls.base')),
    
    # Translation History
    path('history/', include('translation.urls.general')),
]


from django.contrib import admin
from .models import DeveloperApp, WebhookEndpoint

@admin.register(DeveloperApp)
class DeveloperAppAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'client_id', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'client_id', 'user__email')

@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = ('developer_app', 'url', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('url', 'developer_app__name')

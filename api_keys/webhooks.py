import json
import hmac
import hashlib
import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def generate_signature(payload: str, secret: str) -> str:
    """Generate an HMAC SHA-512 signature for webhook payloads."""
    return hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha512
    ).hexdigest()

def dispatch_webhook(event_type: str, data: dict, app) -> None:
    """
    Dispatch a webhook event to the developer's registered endpoints.
    Should ideally be called asynchronously via Celery.
    """
    endpoints = app.webhooks.filter(is_active=True)
    if not endpoints.exists():
        return
        
    payload_dict = {
        "event": event_type,
        "data": data,
    }
    payload_str = json.dumps(payload_dict)
    
    # Sign with client_secret
    signature = generate_signature(payload_str, app.client_secret)
    
    headers = {
        "Content-Type": "application/json",
        "X-Echo-Signature": signature,
    }
    
    for endpoint in endpoints:
        try:
            # We enforce a timeout so bad endpoints don't hang our workers
            response = requests.post(endpoint.url, data=payload_str, headers=headers, timeout=5.0)
            logger.info(f"Dispatched {event_type} to {endpoint.url}. Status: {response.status_code}")
        except Exception as e:
            logger.error(f"Failed to dispatch webhook {event_type} to {endpoint.url}: {str(e)}")


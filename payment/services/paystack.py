import json
import logging
import requests
from django.conf import settings
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class PaystackService:
    BASE_URL = "https://api.paystack.co"

    def __init__(self):
        self.secret_key = settings.PAYSTACK_SECRET_KEY
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=self.headers, params=data)
            else:
                response = requests.request(method, url, headers=self.headers, json=data)
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Paystack API Error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Paystack API Response: {e.response.text}")
                try:
                    return e.response.json()
                except ValueError:
                    return {"status": False, "message": "Invalid response from Paystack"}
            return {"status": False, "message": str(e)}

    def initialize_transaction(self, email: str, amount: int, reference: str, callback_url: Optional[str] = None, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Initialize a Paystack transaction. Amount must be in kobo/cents.
        """
        payload = {
            "email": email,
            "amount": amount,
            "reference": reference,
        }
        if callback_url:
            payload["callback_url"] = callback_url
        if metadata:
            payload["metadata"] = metadata

        return self._make_request("POST", "/transaction/initialize", payload)

    def verify_transaction(self, reference: str) -> Dict[str, Any]:
        """
        Verify a transaction given its reference.
        """
        return self._make_request("GET", f"/transaction/verify/{reference}")

    def create_customer(self, email: str, first_name: str, last_name: str) -> Dict[str, Any]:
        """
        Create a Paystack customer for subscriptions
        """
        payload = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name
        }
        return self._make_request("POST", "/customer", payload)

    def verify_webhook_data(self, request) -> Optional[Dict[str, Any]]:
        """
        Verifies the webhook signature using HMAC SHA512.
        """
        import hmac
        import hashlib
        
        payload = request.body
        hash_str = hmac.new(
            self.secret_key.encode("utf-8"),
            payload,
            digestmod=hashlib.sha512,
        ).hexdigest()

        signature = request.headers.get("x-paystack-signature")
        if not signature or hash_str != signature:
            logger.warning("Invalid Paystack webhook signature")
            return None

        try:
            request_body = payload.decode("utf-8")
            request_data = json.loads(request_body)
            return request_data
        except (ValueError, UnicodeDecodeError) as e:
            logger.error(f"Failed to decode Paystack webhook payload: {e}")
            return None

paystack_service = PaystackService()

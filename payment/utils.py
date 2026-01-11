import hashlib
import hmac
import json
import requests
import base64
import uuid
import os
from typing import Dict, Optional


from django.conf import settings
from loguru import logger

from wallet.models import Wallet
from decouple import config

class StripeIntegration:
    def __init__(self):
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.STRIPE_SECRET_KEY}",
        }
        self.base_url = "https://api.paystack.co"

    def initialize_transaction(self, user, amount, callback_url, tx_ref, channels=None):
        """
        https://paystack.com/docs/api/transaction/#initialize

        channels options - ["card", "bank", "apple_pay", "ussd", "qr", "mobile_money", "bank_transfer", "eft"]

        {
            "status": true,
            "message": "Authorization URL created",
            "data": {
                "authorization_url": "https://checkout.paystack.com/3ni8kdavz62431k",
                "access_code": "3ni8kdavz62431k",
                "reference": "re4lyvq3s3"
            }
        }
        """

        payload = {
            "email": user.email,
            "amount": float(amount * 100),
            "reference": tx_ref,
            "callback_url": callback_url,
        }
        if channels:
            payload["channels"] = channels

        res = requests.post(
            f"{self.base_url}/transaction/initialize",
            json=payload,
            headers=self.headers,
        )

        logger.info(
            f"Initialize transaction data: {res.json()} with status {res.status_code}"
        )

        if res.status_code == 200:
            return res.json()
        return None

    def verify_transaction(self, txn_ref):
        """
        https://paystack.com/docs/api/transaction/#verify

        {
            "status": true,
            "message": "Verification successful",
            "data": {
                "id": 4099260516,
                "domain": "test",
                "status": "success",
                "reference": "re4lyvq3s3",
                "receipt_number": null,
                "amount": 40333,
                "message": null,
                "gateway_response": "Successful",
                "paid_at": "2024-08-22T09:15:02.000Z",
                "created_at": "2024-08-22T09:14:24.000Z",
                "channel": "card",
                "currency": "NGN",
                "ip_address": "197.210.54.33",
                "metadata": "",
                "log": {
                    "start_time": 1724318098,
                    "time_spent": 4,
                    "attempts": 1,
                    "errors": 0,
                    "success": true,
                    "mobile": false,
                    "input": [],
                    "history": [
                        {
                            "type": "action",
                            "message": "Attempted to pay with card",
                            "time": 3
                        },
                        {
                            "type": "success",
                            "message": "Successfully paid with card",
                            "time": 4
                        }
                    ]
                },
                "fees": 10283,
                "fees_split": null,
                "authorization": {
                    "authorization_code": "AUTH_uh8bcl3zbn",
                    "bin": "408408",
                    "last4": "4081",
                    "exp_month": "12",
                    "exp_year": "2030",
                    "channel": "card",
                    "card_type": "visa ",
                    "bank": "TEST BANK",
                    "country_code": "NG",
                    "brand": "visa",
                    "reusable": true,
                    "signature": "SIG_yEXu7dLBeqG0kU7g95Ke",
                    "account_name": null
                },
                "customer": {
                    "id": 181873746,
                    "first_name": null,
                    "last_name": null,
                    "email": "demo@test.com",
                    "customer_code": "CUS_1rkzaqsv4rrhqo6",
                    "phone": null,
                    "metadata": null,
                    "risk_action": "default",
                    "international_format_phone": null
                },
                "plan": null,
                "split": {},
                "order_id": null,
                "paidAt": "2024-08-22T09:15:02.000Z",
                "createdAt": "2024-08-22T09:14:24.000Z",
                "requested_amount": 30050,
                "pos_transaction_data": null,
                "source": null,
                "fees_breakdown": null,
                "connect": null,
                "transaction_date": "2024-08-22T09:14:24.000Z",
                "plan_object": {},
                "subaccount": {}
            }
        }
        """

        res = requests.get(
            f"{self.base_url}/transaction/verify/{txn_ref}",
            headers=self.headers,
        )

        logger.info(
            f"Verify transaction data: {res.json()} with status {res.status_code}"
        )

        if res.status_code == 200:
            return res.json()
        return None

    def charge_authorization(self, user, amount, tx_ref):
        """
        https://paystack.com/docs/api/transaction/#charge-authorization
        """

        wallet = Wallet.fetch_for_user(user)
        if not wallet.authorization_code:
            return None

        payload = {
            "email": user.email,
            "amount": float(amount * 100),
            "reference": tx_ref,
            "authorization_code": wallet.authorization_code,
        }

        res = requests.post(
            f"{self.base_url}/transaction/charge_authorization",
            json=payload,
            headers=self.headers,
        )

        logger.info(
            f"Charge authorization data: {res.json()} with status {res.status_code}"
        )

        if res.status_code == 200:
            return res.json()
        return None

    def verify_webhook_data(self, request):
        payload = request.body
        hash = hmac.new(
            settings.STRIPE_SECRET_KEY.encode("utf-8"),
            payload,
            digestmod=hashlib.sha512,
        ).hexdigest()

        if "x-paystack-signature" not in request.headers:
            return None

        if hash != request.headers["x-paystack-signature"]:
            return None

        request_body = payload.decode("utf-8")
        request_data = json.loads(request_body)

        logger.info(f"Webhook data: {request_data}")
        return request_data

    def update_authorization(self, user, authorization_data):
        reusable = authorization_data.get("reusable", False)
        if reusable:
            wallet = Wallet.fetch_for_user(user)
            wallet.authorization_code = authorization_data["authorization_code"]
            wallet.save()




class MTNMomoIntegration:
    """
    MTN MoMo Collections API Client (Rwanda)
    """

    SANDBOX_BASE_URL = "https://sandbox.momodeveloper.mtn.com"
    PRODUCTION_BASE_URL = "https://momodeveloper.mtn.com"

    def __init__(
        self,
        api_user: Optional[str] = None,
        api_key: Optional[str] = None,
        subscription_key: Optional[str] = None,
        environment: Optional[str] = None,
        timeout: int = 30,
    ):
        self.api_user = api_user or config("MOMO_API_USER")
        self.api_key = api_key or config("MOMO_API_KEY")
        self.subscription_key = subscription_key or config("MOMO_SUBSCRIPTION_KEY")
        self.environment = environment or config("MOMO_ENV", "sandbox")
        self.timeout = timeout

        if not all([self.api_user, self.api_key, self.subscription_key]):
            raise ValueError("Missing required MTN MoMo credentials")

        self.base_url = (
            self.SANDBOX_BASE_URL
            if self.environment == "sandbox"
            else self.PRODUCTION_BASE_URL
        )

        self._access_token: Optional[str] = None

    # -----------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------

    def _basic_auth_header(self) -> str:
        raw = f"{self.api_user}:{self.api_key}"
        encoded = base64.b64encode(raw.encode()).decode()
        return f"Basic {encoded}"

    def _headers(self, extra: dict | None = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "X-Target-Environment": self.environment,
            "Content-Type": "application/json",
        }
        if extra:
            headers.update(extra)
        return headers

    # -----------------------------------------------------
    # Public API methods
    # -----------------------------------------------------

    def get_access_token(self) -> str:
        """
        Generate access token
        """
        url = f"{self.base_url}/collection/token/"

        headers = {
            "Authorization": self._basic_auth_header(),
            "Ocp-Apim-Subscription-Key": self.subscription_key,
        }

        response = requests.post(url, headers=headers, timeout=self.timeout)
        response.raise_for_status()

        data = response.json()
        self._access_token = data["access_token"]
        return self._access_token

    def request_to_pay(
        self,
        amount: str,
        phone_number: str,
        external_id: str,
        payer_message: str = "Payment request",
        payee_note: str = "Thank you",
        currency: str = "RWF",
    ) -> str:
        """
        Initiate MoMo payment request

        Returns: reference_id
        """
        if not self._access_token:
            self.get_access_token()

        reference_id = str(uuid.uuid4())

        url = f"{self.base_url}/collection/v1_0/requesttopay"

        payload = {
            "amount": amount,
            "currency": currency,
            "externalId": external_id,
            "payer": {
                "partyIdType": "MSISDN",
                "partyId": phone_number,
            },
            "payerMessage": payer_message,
            "payeeNote": payee_note,
        }

        headers = self._headers(
            {
                "X-Reference-Id": reference_id,
            }
        )

        response = requests.post(
            url, json=payload, headers=headers, timeout=self.timeout
        )

        # 202 Accepted = success initiation
        if response.status_code != 202:
            raise RuntimeError(
                f"MoMo request failed: {response.status_code} - {response.text}"
            )

        return reference_id

    def get_payment_status(self, reference_id: str) -> dict:
        """
        Check payment status
        """
        if not self._access_token:
            self.get_access_token()

        url = f"{self.base_url}/collection/v1_0/requesttopay/{reference_id}"

        response = requests.get(
            url, headers=self._headers(), timeout=self.timeout
        )
        response.raise_for_status()

        return response.json()




class KPayClient:
    """
    Python client for K-Pay API (kpay.africa)
    """

    BASE_URL = "https://pay.esicia.com/"

    def __init__(
        self,
        api_key: Optional[str] = None,
        retailer_id: Optional[str] = None,
        timeout: int = 30,
    ):
        self.api_key = api_key or os.getenv("KPAY_API_KEY")
        self.retailer_id = retailer_id or os.getenv("KPAY_RETAILER_ID")
        self.timeout = timeout

        if not self.api_key:
            raise ValueError("KPay API key is required")
        if not self.retailer_id:
            raise ValueError("KPay retailer id is required")

    def _headers(self) -> dict:
        """
        Common headers for KPay requests
        """
        return {
            "secret_key": self.api_key,
            "Content-Type": "application/json",
        }

    def initiate_payment(
        self,
        amount: int,
        phone_number: str,
        email: str,
        customer_name: str,
        customer_number: str,
        return_url: str,
        redirect_url: str,
        currency: str = "RWF",
        details: str = "Payment",
        payment_method: str = "momo",
        refid: Optional[str] = None,
    ) -> Dict:
        """
        Initiate a KPay payment

        Returns:
            JSON response with payment status and checkout URL
        """

        # Unique payment reference if not provided
        refid = refid or str(uuid.uuid4())
        payload = {
            "action": "pay",
            "msisdn": phone_number,
            "email": email,
            "details": details,
            "refid": refid,
            "amount": amount,
            "currency": currency,
            "cname": customer_name,
            "cnumber": customer_number,
            "pmethod": payment_method,
            "retailerid": self.retailer_id,
            "returl": return_url,
            "redirecturl": redirect_url,
        }

        response = requests.post(
            self.BASE_URL, json=payload, headers=self._headers(), timeout=self.timeout
        )

        # Raise if HTTP error
        response.raise_for_status()
        data = response.json()

        if data.get("success") != 1:
            raise RuntimeError(f"KPay Error: {data}")

        return data

    def check_payment_status(self, refid: str) -> Dict:
        """
        Check status of a KPay payment
        """

        payload = {
            "action": "checkstatus",
            "refid": refid,
        }

        response = requests.post(
            self.BASE_URL, json=payload, headers=self._headers(), timeout=self.timeout
        )
        response.raise_for_status()
        return response.json() 

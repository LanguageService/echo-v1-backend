import hashlib
import hmac
import json

import requests
from django.conf import settings
from loguru import logger

from wallet.models import Wallet


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

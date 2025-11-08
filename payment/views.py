from django.db import transaction
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from drf_spectacular.utils import extend_schema

from core.utils import error_400, error_404, serializer_errors
from users.models.users import User
from wallet.models import Wallet
from .models.payment import Payment
from .utils import StripeIntegration
from . import choices, serializers



@extend_schema(tags=["Payment"])
class PaymentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    queryset = Payment.objects.all()
    serializer_class = serializers.PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()

        user = self.request.user
        if user.user_type != User.ADMIN:
            qs = qs.filter(user=user)

        return qs

    @action(
        detail=False,
        methods=["POST"],
        serializer_class=serializers.TopUpSerializer,
        url_path="topup",
    )
    def topup(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            amount = serializer.validated_data["amount"]
            tx_ref = Payment.generate_reference(choices.PaymentType.WALLET_TOPUP)

            res = PaystackIntegration().initialize_transaction(
                request.user,
                amount,
                serializer.validated_data["callback_url"],
                tx_ref,
            )
            if not res:
                return error_400("Unable to complete payment, Contact Admin.")

            Payment.objects.create(
                user=request.user,
                amount=amount,
                reference=tx_ref,
                status=choices.PaymentStatus.PENDING,
                payment_type=choices.PaymentType.WALLET_TOPUP,
            )

            return Response(
                {
                    "code": 200,
                    "status": "success",
                    "authorization_url": res["data"]["authorization_url"],
                },
                status=status.HTTP_200_OK,
            )

        default_errors = serializer.errors
        error_message = serializer_errors(default_errors)
        return error_400(error_message)


    @action(
        detail=False,
        methods=["PATCH"],
        serializer_class=None,
        url_path="verify/(?P<reference>[^/.]+)",
    )
    @transaction.atomic
    def verify(self, request, reference, pk=None):
        payment = Payment.objects.filter(reference=reference).first()
        if not payment:
            return error_404("Transaction with reference not found.")

        if payment.status != choices.PaymentStatus.PENDING:
            return Response(
                {
                    "code": 200,
                    "message": f"Transaction already verified as {payment.status}",
                },
                status=status.HTTP_200_OK,
            )

        integration = PaystackIntegration()
        res = integration.verify_transaction(reference)
        if not res:
            return error_400("Unable to verify payment, Contact Admin.")

        paystack_status = res.get("data").get("status")
        if paystack_status:
            self.fulfill_payment(payment, paystack_status)

        integration.update_authorization(payment.user, res.get("authorization", {}))

        return Response(
            {
                "code": 200,
                "message": f"Transaction verified as {paystack_status}",
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["POST"],
        serializer_class=None,
        url_path="webhook",
    )
    @transaction.atomic
    def webhook(self, request):
        integration = PaystackIntegration()
        request_data = integration.verify_webhook_data(request)
        if not request_data:
            return error_400("Unable to verify webhook")

        event = request_data["event"]
        if event == "charge.success":
            reference = request_data.get("data").get("reference")
            payment = Payment.objects.filter(reference=reference).first()
            if not payment:
                return error_404("Transaction with reference not found.")

            if payment.status != choices.PaymentStatus.PENDING:
                return Response(
                    {
                        "code": 200,
                        "message": f"Transaction already verified as {payment.status}",
                    },
                    status=status.HTTP_200_OK,
                )

            paystack_status = request_data.get("data").get("status")
            if paystack_status:
                self.fulfill_payment(payment, paystack_status)

            integration.update_authorization(payment.user, res.get("authorization", {}))

            return Response(
                {
                    "code": 200,
                    "message": "Transaction processed successfully",
                },
                status=status.HTTP_200_OK,
            )
        return error_400("Unexpected event")

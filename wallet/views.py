from datetime import timedelta

from django.utils import timezone
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from users.models.users import User
from . import models, serializers


class WalletViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    queryset = models.Wallet.objects.all()
    serializer_class = serializers.WalletSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["GET"], url_path="me")
    def me(self, request, *args, **kwargs):
        obj = models.Wallet.fetch_for_user(request.user)
        return Response(
            {"code": status.HTTP_200_OK, "data": self.get_serializer(obj).data},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["GET"], url_path="balance")
    def balance(self, request, *args, **kwargs):
        wallet = models.Wallet.fetch_for_user(request.user)
        transactions = wallet.transactions.select_related("created_by").order_by("-created")[:20]

        tx_data = [
            {
                "id": t.id,
                "amount": str(t.amount),
                "type": t.type,
                "flow": t.flow,
                "notes": t.notes,
                "initiated_by_admin": t.initiated_by_admin,
                "created_by_email": t.created_by.email if t.created_by else None,
                "created": t.created.isoformat() if t.created else None,
            }
            for t in transactions
        ]

        return Response(
            {
                "balance": str(wallet.balance),
                "currency": "CREDITS",
                "transactions": tx_data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["GET"], url_path="usage-summary")
    def usage_summary(self, request, *args, **kwargs):
        """Return translation usage counts for the current user."""
        from translation.models import TextTranslation, SpeechTranslation

        user = request.user
        now = timezone.now()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        speech_qs = SpeechTranslation.objects.filter(user=user)
        text_qs = TextTranslation.objects.filter(user=user)

        total_speech = speech_qs.count()
        total_text = text_qs.count()
        total = total_speech + total_text

        # Billing cost deducted across both types
        from django.db.models import Sum
        cost_speech = speech_qs.aggregate(c=Sum("billing_cost_deducted"))["c"] or 0
        cost_text = text_qs.aggregate(c=Sum("billing_cost_deducted"))["c"] or 0
        total_cost = float(cost_speech) + float(cost_text)

        return Response(
            {
                "total_translations": total,
                "voice_translations": total_speech,
                "text_translations": total_text,
                "this_month": (
                    speech_qs.filter(date_created__gte=month_ago).count()
                    + text_qs.filter(date_created__gte=month_ago).count()
                ),
                "this_week": (
                    speech_qs.filter(date_created__gte=week_ago).count()
                    + text_qs.filter(date_created__gte=week_ago).count()
                ),
                "today": (
                    speech_qs.filter(date_created__date=now.date()).count()
                    + text_qs.filter(date_created__date=now.date()).count()
                ),
                "total_credits_used": round(total_cost, 4),
            },
            status=status.HTTP_200_OK,
        )


class TransactionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    queryset = models.Transaction.objects.all()
    serializer_class = serializers.TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.user_type != User.ADMIN:
            qs = qs.filter(wallet__user=user)
        return qs

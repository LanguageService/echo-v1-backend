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

    @action(
        detail=False,
        methods=["GET"],
        url_path="me",
    )
    def me(self, request, *args, **kwargs):
        obj = models.Wallet.fetch_for_user(request.user)
        return Response(
            {
                "code": status.HTTP_200_OK,
                "data": self.get_serializer(obj).data,
            },
            status=status.HTTP_200_OK,
        )


class TransactionViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet
):
    queryset = models.Transaction.objects.all()
    serializer_class = serializers.TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.user_type != User.ADMIN:
            qs = qs.filter(wallet__user=user)

        return qs

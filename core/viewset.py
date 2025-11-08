from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework import status


class BaseViewSet(ModelViewSet):
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.archive()
        return Response(status=status.HTTP_204_NO_CONTENT)

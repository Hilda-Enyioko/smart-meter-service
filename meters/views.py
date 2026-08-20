from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Meter
from .serializers import MeterRegisterSerializer, MeterSerializer


class RegisterMeterView(APIView):
    """Link a meter (by serial number) to the currently authenticated user."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = MeterRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        meter, _created = Meter.objects.get_or_create(serial_number=data['serial_number'])
        meter.user = request.user
        meter.nickname = data.get('nickname', meter.nickname)
        meter.location = data.get('location', meter.location)
        meter.linked_at = timezone.now()
        meter.save()

        return Response(MeterSerializer(meter).data, status=status.HTTP_201_CREATED)


class MyMetersListView(generics.ListAPIView):
    """List all meters linked to the current user."""
    serializer_class = MeterSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Meter.objects.filter(user=self.request.user).order_by('-linked_at')


class MeterDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View/update a specific meter owned by the current user.
    DELETE unlinks the meter (does not delete the hardware record) instead of destroying it.
    """
    serializer_class = MeterSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Meter.objects.filter(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        meter = self.get_object()
        meter.user = None
        meter.linked_at = None
        meter.nickname = ''
        meter.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

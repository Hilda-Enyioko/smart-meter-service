from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Meter, TelemetryReading
from .serializers import MeterRegisterSerializer, MeterSerializer, TelemetryInSerializer
from .permissions import DeviceKeyAuthenticated


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


class DeviceTelemetryView(APIView):
    """
    ESP32 POSTs a reading here every N seconds.
    Body: { serial_number, device_key, voltage, current, power, energy, relay_state }
    """
    permission_classes = [DeviceKeyAuthenticated]

    def post(self, request):
        serializer = TelemetryInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        meter = request.meter  # attached by DeviceKeyAuthenticated

        # Simple credit depletion for POC: subtract energy * a flat rate
        RATE_PER_KWH = 0.15
        if meter.credit_balance > 0:
            deduction = data['energy'] * RATE_PER_KWH
            meter.credit_balance = max(0, meter.credit_balance - deduction)

        meter.last_voltage = data['voltage']
        meter.last_current = data['current']
        meter.last_power = data['power']
        meter.last_energy = data['energy']
        meter.relay_state = data['relay_state']
        meter.status = Meter.Status.ONLINE
        meter.last_seen_at = timezone.now()

        # Auto cut-off when credit hits zero
        if meter.credit_balance <= 0:
            meter.desired_relay_state = False

        meter.save()

        TelemetryReading.objects.create(
            meter=meter,
            voltage=data['voltage'],
            current=data['current'],
            power=data['power'],
            energy=data['energy'],
            relay_state=data['relay_state'],
        )

        return Response({
            'received': True,
            'credit_balance': meter.credit_balance,
            'relay_command': 'ON' if meter.desired_relay_state else 'OFF',
        }, status=status.HTTP_200_OK)


class DeviceCommandView(APIView):
    """
    ESP32 polls this to check what the relay SHOULD be doing.
    Query params: ?serial_number=X&device_key=Y
    """
    permission_classes = [DeviceKeyAuthenticated]

    def get(self, request):
        meter = request.meter
        return Response({
            'relay_command': 'ON' if meter.desired_relay_state else 'OFF',
            'credit_balance': meter.credit_balance,
        })

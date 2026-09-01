from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg, Sum
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from django.utils import timezone
from rest_framework.exceptions import ParseError
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from notifications.services import notify
from notifications.models import Notification

from .models import Meter, TelemetryReading
from .serializers import (
    MeterRegisterSerializer,
    MeterSerializer,
    TelemetryInSerializer,
    MeterDashboardSerializer,
    ConsumptionBucketSerializer,
    CreditUsageAnalysisSerializer,
    RuntimeEstimateSerializer,
    TelemetryHistorySerializer,
    AddCreditSerializer,
    LowCreditThresholdSerializer,
    RelayCommandSerializer,
)
from .permissions import DeviceKeyAuthenticated, IsMeterOwnerOrAdmin
from users.permissions import IsAdminRole
from django.shortcuts import get_object_or_404
from django.conf import settings


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
    permission_classes = [DeviceKeyAuthenticated]

    def post(self, request):
        serializer = TelemetryInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        meter = request.meter

        was_low_credit = meter.is_low_credit
        was_relay_on = meter.desired_relay_state

        RATE_PER_KWH = settings.CREDIT_RATE_PER_KWH
        if meter.credit_balance > 0:
            deduction = data['energy'] * RATE_PER_KWH
            meter.credit_balance = max(0, meter.credit_balance - deduction)

        meter.last_voltage = data['voltage']
        meter.last_current = data['current']
        meter.last_power = data['power']
        meter.last_energy = data['energy']
        meter.relay_state = data['relay_state']
        meter.status = Meter.Status.ONLINE
        meter.offline_alert_sent = False
        meter.last_seen_at = timezone.now()

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

        # --- Notification triggers, fire only on state TRANSITIONS, not every reading ---
        if meter.user:
            if meter.is_low_credit and not was_low_credit:
                notify(
                    meter.user,
                    Notification.Type.LOW_CREDIT,
                    f"Your credit balance for {meter.nickname or meter.serial_number} "
                    f"has dropped to {meter.credit_balance}, at or below your alert "
                    f"threshold of {meter.low_credit_threshold}.",
                    meter=meter,
                )

            if was_relay_on and not meter.desired_relay_state:
                notify(
                    meter.user,
                    Notification.Type.POWER_DISCONNECTION,
                    f"Power to {meter.nickname or meter.serial_number} has been "
                    f"automatically disconnected due to insufficient credit.",
                    meter=meter,
                )

        return Response({
            'received': True,
            'credit_balance': meter.credit_balance,
            'is_low_credit': meter.is_low_credit,
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


class MeterDashboardView(APIView):
    """
    Single-meter dashboard: credit balance, online status, relay state,
    voltage, current, power, energy, last communication timestamp.
    Only accessible by the user who owns/linked the meter.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        meter = get_object_or_404(Meter, pk=pk, user=request.user)
        serializer = MeterDashboardSerializer(meter)
        return Response(serializer.data, status=status.HTTP_200_OK)


def _get_owned_meter_or_404(request, pk):
    return get_object_or_404(Meter, pk=pk, user=request.user)


def _parse_date_range(request, default_days=30):
    """Reads ?start=YYYY-MM-DD&end=YYYY-MM-DD from query params, with a sane default."""
    end = timezone.now()
    start = end - timedelta(days=default_days)

    start_param = request.query_params.get('start')
    end_param = request.query_params.get('end')

    if start_param:
        parsed = timezone.datetime.fromisoformat(start_param)
        start = timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
    if end_param:
        parsed = timezone.datetime.fromisoformat(end_param)
        end = timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed

    if start >= end:
        raise ParseError("`start` must be before `end`.")

    return start, end


class MeterHistoryView(APIView):
    """
    Raw historical telemetry readings for a meter.
    GET /meters/<id>/analytics/history/?start=2026-08-01&end=2026-08-25&limit=200
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        meter = _get_owned_meter_or_404(request, pk)
        start, end = _parse_date_range(request, default_days=7)
        limit = min(int(request.query_params.get('limit', 500)), 2000)

        readings = (
            meter.readings
            .filter(created_at__gte=start, created_at__lte=end)
            .order_by('-created_at')[:limit]
        )
        serializer = TelemetryHistorySerializer(readings, many=True)
        return Response({
            'meter_id': meter.id,
            'start': start,
            'end': end,
            'count': len(serializer.data),
            'results': serializer.data,
        })


class MeterConsumptionView(APIView):
    """
    Aggregated consumption trends for graphs.
    GET /meters/<id>/analytics/consumption/?period=daily|weekly|monthly&start=&end=
    Defaults: period=daily, last 30 days.
    """
    permission_classes = [permissions.IsAuthenticated]

    TRUNC_MAP = {
        'daily': TruncDay,
        'weekly': TruncWeek,
        'monthly': TruncMonth,
    }

    def get(self, request, pk):
        meter = _get_owned_meter_or_404(request, pk)
        period = request.query_params.get('period', 'daily')
        if period not in self.TRUNC_MAP:
            raise ParseError("`period` must be one of: daily, weekly, monthly.")

        default_days = {'daily': 30, 'weekly': 90, 'monthly': 365}[period]
        start, end = _parse_date_range(request, default_days=default_days)

        trunc_fn = self.TRUNC_MAP[period]

        buckets = (
            meter.readings
            .filter(created_at__gte=start, created_at__lte=end)
            .annotate(period_start=trunc_fn('created_at'))
            .values('period_start')
            .annotate(
                total_energy_kwh=Sum('energy'),
                reading_count=Sum(1),
                avg_power=Avg('power'),
            )
            .order_by('period_start')
        )

        results = []
        for b in buckets:
            total_energy = b['total_energy_kwh'] or 0
            results.append({
                'period_start': b['period_start'],
                'total_energy_kwh': round(total_energy, 4),
                'total_cost': round(total_energy * settings.CREDIT_RATE_PER_KWH, 2),
                'reading_count': b['reading_count'],
                'avg_power': round(b['avg_power'], 2) if b['avg_power'] is not None else None,
            })

        serializer = ConsumptionBucketSerializer(results, many=True)
        return Response({
            'meter_id': meter.id,
            'period': period,
            'start': start,
            'end': end,
            'results': serializer.data,
        })


class MeterCreditUsageView(APIView):
    """
    Credit usage analysis over a period.
    GET /meters/<id>/analytics/credit-usage/?start=&end=
    Default: last 30 days.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        meter = _get_owned_meter_or_404(request, pk)
        start, end = _parse_date_range(request, default_days=30)

        agg = meter.readings.filter(created_at__gte=start, created_at__lte=end).aggregate(
            total_energy=Sum('energy')
        )
        total_energy = agg['total_energy'] or 0
        total_cost = total_energy * settings.CREDIT_RATE_PER_KWH

        days_in_period = max((end - start).total_seconds() / 86400, 1)

        data = {
            'current_credit_balance': meter.credit_balance,
            'total_energy_kwh_period': round(total_energy, 4),
            'total_cost_period': round(total_cost, 2),
            'average_daily_cost': round(total_cost / days_in_period, 2),
            'average_daily_energy_kwh': round(total_energy / days_in_period, 4),
            'days_in_period': int(days_in_period),
        }
        serializer = CreditUsageAnalysisSerializer(data)
        return Response(serializer.data)


class MeterRuntimeEstimateView(APIView):
    """
    Estimates remaining runtime based on recent average consumption rate.
    GET /meters/<id>/analytics/runtime-estimate/?window_hours=24
    Uses the last `window_hours` of readings to compute an hourly burn rate,
    falling back to a 7-day window if there's not enough recent data.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        meter = _get_owned_meter_or_404(request, pk)
        window_hours = int(request.query_params.get('window_hours', 24))

        cutoff = timezone.now() - timedelta(hours=window_hours)
        recent = meter.readings.filter(created_at__gte=cutoff)
        basis = f"last {window_hours}h"

        agg = recent.aggregate(total_energy=Sum('energy'), count=Sum(1))
        total_energy = agg['total_energy'] or 0
        count = agg['count'] or 0

        # Fall back to a 7-day window if too little recent data to be meaningful
        if count < 3:
            cutoff = timezone.now() - timedelta(days=7)
            recent = meter.readings.filter(created_at__gte=cutoff)
            agg = recent.aggregate(total_energy=Sum('energy'), count=Sum(1))
            total_energy = agg['total_energy'] or 0
            count = agg['count'] or 0
            basis = "last 7 days (insufficient recent data)"

        if count == 0:
            data = {
                'current_credit_balance': meter.credit_balance,
                'average_hourly_cost': None,
                'average_hourly_energy_kwh': None,
                'estimated_hours_remaining': None,
                'estimated_days_remaining': None,
                'basis': 'no telemetry data available',
            }
            return Response(RuntimeEstimateSerializer(data).data)

        hours_span = max((timezone.now() - cutoff).total_seconds() / 3600, 1)
        avg_hourly_energy = total_energy / hours_span
        avg_hourly_cost = avg_hourly_energy * settings.CREDIT_RATE_PER_KWH

        estimated_hours = (
            float(meter.credit_balance) / avg_hourly_cost if avg_hourly_cost > 0 else None
        )

        data = {
            'current_credit_balance': meter.credit_balance,
            'average_hourly_cost': round(avg_hourly_cost, 4),
            'average_hourly_energy_kwh': round(avg_hourly_energy, 5),
            'estimated_hours_remaining': round(estimated_hours, 1) if estimated_hours is not None else None,
            'estimated_days_remaining': round(estimated_hours / 24, 2) if estimated_hours is not None else None,
            'basis': basis,
        }
        serializer = RuntimeEstimateSerializer(data)
        return Response(serializer.data)


class LowCreditThresholdView(generics.RetrieveUpdateAPIView):
    """
    Configure the low-credit alert threshold for a meter.
    GET/PATCH /meters/<id>/threshold/
    """
    serializer_class = LowCreditThresholdSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Meter.objects.filter(user=self.request.user)


class RelayControlView(APIView):
    """
    Manual relay control, authorized to the meter's owner or an admin.
    POST /meters/<id>/relay/   body: { "desired_state": true|false }
    Sets desired_relay_state; the ESP32 picks this up on its next telemetry
    POST response or its next /device/command/ poll (within ~10s).
    Turning ON is blocked server-side if credit_balance <= 0.
    """
    permission_classes = [permissions.IsAuthenticated, IsMeterOwnerOrAdmin]

    def post(self, request, pk):
        meter = get_object_or_404(Meter, pk=pk)
        self.check_object_permissions(request, meter)

        serializer = RelayCommandSerializer(data=request.data, context={'meter': meter})
        serializer.is_valid(raise_exception=True)

        meter.desired_relay_state = serializer.validated_data['desired_state']
        meter.save()

        return Response({
            'meter_id': meter.id,
            'desired_relay_state': meter.desired_relay_state,
            'note': 'Command queued — the meter will apply this on its next check-in.',
        })


class AdminAddCreditView(APIView):
    """
    TEMPORARY / admin-only: manually add credit to a meter.
    POST /meters/<id>/admin-add-credit/   body: { "amount": 10.00 }
    Exists to let you test the full depletion -> disconnect -> recharge -> 
    restore cycle before the real payment/recharge endpoints are built.
    Remove or restrict further once the payments app exists.
    """
    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        meter = get_object_or_404(Meter, pk=pk)
        serializer = AddCreditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        meter.apply_credit(serializer.validated_data['amount'])

        return Response({
            'meter_id': meter.id,
            'credit_balance': meter.credit_balance,
            'desired_relay_state': meter.desired_relay_state,
        })

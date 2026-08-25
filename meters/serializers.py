from rest_framework import serializers
from .models import Meter, TelemetryReading


class MeterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meter
        fields = (
            'id', 'serial_number', 'device_key', 'nickname', 'location',
            'relay_state', 'credit_balance', 'status',
            'last_seen_at', 'linked_at', 'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'serial_number', 'device_key', 'relay_state', 'credit_balance',
            'status', 'last_seen_at', 'linked_at', 'created_at', 'updated_at',
        )


class MeterRegisterSerializer(serializers.Serializer):
    serial_number = serializers.CharField(max_length=64)
    nickname = serializers.CharField(max_length=100, required=False, allow_blank=True)
    location = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate_serial_number(self, value):
        try:
            meter = Meter.objects.get(serial_number=value)
        except Meter.DoesNotExist:
            return value

        if meter.user is not None:
            raise serializers.ValidationError("This meter is already linked to another account.")
        return value


class TelemetryInSerializer(serializers.Serializer):
    """What the ESP32 sends."""
    voltage = serializers.FloatField()
    current = serializers.FloatField()
    power = serializers.FloatField()
    energy = serializers.FloatField()
    relay_state = serializers.BooleanField()


class TelemetryReadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelemetryReading
        fields = ('voltage', 'current', 'power', 'energy', 'relay_state', 'created_at')


class MeterDashboardSerializer(serializers.ModelSerializer):
    """Everything needed for the single-meter dashboard view."""
    is_online = serializers.SerializerMethodField()

    class Meta:
        model = Meter
        fields = (
            'id',
            'serial_number',
            'nickname',
            'credit_balance',
            'status',
            'is_online',
            'relay_state',
            'last_voltage',
            'last_current',
            'last_power',
            'last_energy',
            'last_seen_at',
        )

    def get_is_online(self, obj):
        return obj.status == Meter.Status.ONLINE


class TelemetryHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TelemetryReading
        fields = ('voltage', 'current', 'power', 'energy', 'relay_state', 'created_at')


class ConsumptionBucketSerializer(serializers.Serializer):
    """One row of aggregated consumption for a given day/week/month."""
    period_start = serializers.DateTimeField()
    total_energy_kwh = serializers.FloatField()
    total_cost = serializers.FloatField()
    reading_count = serializers.IntegerField()
    avg_power = serializers.FloatField(allow_null=True)


class CreditUsageAnalysisSerializer(serializers.Serializer):
    current_credit_balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_energy_kwh_period = serializers.FloatField()
    total_cost_period = serializers.FloatField()
    average_daily_cost = serializers.FloatField()
    average_daily_energy_kwh = serializers.FloatField()
    days_in_period = serializers.IntegerField()


class RuntimeEstimateSerializer(serializers.Serializer):
    current_credit_balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    average_hourly_cost = serializers.FloatField(allow_null=True)
    average_hourly_energy_kwh = serializers.FloatField(allow_null=True)
    estimated_hours_remaining = serializers.FloatField(allow_null=True)
    estimated_days_remaining = serializers.FloatField(allow_null=True)
    basis = serializers.CharField()

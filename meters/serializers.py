from rest_framework import serializers

from .models import Meter


class MeterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meter
        fields = (
            'id', 'serial_number', 'nickname', 'location',
            'relay_state', 'credit_balance', 'status',
            'last_seen_at', 'linked_at', 'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'serial_number', 'relay_state', 'credit_balance',
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
            # POC behavior: unknown serial numbers are auto-provisioned on first link.
            return value

        if meter.user is not None:
            raise serializers.ValidationError("This meter is already linked to another account.")
        return value

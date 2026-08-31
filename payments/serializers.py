from rest_framework import serializers

from meters.models import Meter
from .models import Transaction, TransactionAuditLog


class InitializeCheckoutSerializer(serializers.Serializer):
    meter_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=100)  # min ₦100, adjust as needed

    def validate_meter_id(self, value):
        request = self.context['request']
        if not Meter.objects.filter(id=value, user=request.user).exists():
            raise serializers.ValidationError("Meter not found or not linked to your account.")
        return value


class VerifyTransactionSerializer(serializers.Serializer):
    txn_ref = serializers.CharField(max_length=64)


class TransactionSerializer(serializers.ModelSerializer):
    meter_serial_number = serializers.CharField(source='meter.serial_number', read_only=True)

    class Meta:
        model = Transaction
        fields = (
            'id', 'txn_ref', 'meter', 'meter_serial_number', 'amount',
            'currency_code', 'status', 'created_at', 'verified_at',
        )
        read_only_fields = fields


class TransactionAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionAuditLog
        fields = ('event', 'detail', 'created_at')


class TransactionSerializer(serializers.ModelSerializer):
    meter_serial_number = serializers.CharField(source='meter.serial_number', read_only=True)

    class Meta:
        model = Transaction
        fields = (
            'id', 'txn_ref', 'meter', 'meter_serial_number', 'amount', 'currency_code',
            'status', 'fulfillment_status', 'payment_method', 'payment_method_detail',
            'created_at', 'verified_at', 'fulfilled_at',
        )
        read_only_fields = fields


class TransactionDetailSerializer(TransactionSerializer):
    """Adds the full audit trail — used only for the single-transaction detail view."""
    audit_logs = TransactionAuditLogSerializer(many=True, read_only=True)

    class Meta(TransactionSerializer.Meta):
        fields = TransactionSerializer.Meta.fields + ('audit_logs',)

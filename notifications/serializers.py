from rest_framework import serializers
from .models import Notification,NotificationPreference

class NotificationSerializer(serializers.ModelSerializer):
    meter_serial_number = serializers.CharField(source='meter.serial_number', read_only=True, default=None)

    class Meta:
        model = Notification
        fields = (
            'id', 'type', 'title', 'message', 'meter', 'meter_serial_number',
            'email_sent', 'is_read', 'created_at',
        )
        read_only_fields = fields


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = (
            'low_credit_alerts', 'recharge_confirmation',
            'power_disconnection_alerts', 'power_restoration_alerts',
            'meter_offline_alerts', 'failed_payment_alerts',
            'email_enabled', 'sms_enabled', 'push_enabled', 'updated_at',
        )
        read_only_fields = ('updated_at',)

from rest_framework import serializers
from .models import NotificationPreference


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

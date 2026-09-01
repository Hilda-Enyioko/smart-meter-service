from django.conf import settings
from django.db import models

class Notification(models.Model):
    class Type(models.TextChoices):
        LOW_CREDIT = 'low_credit', 'Low Credit'
        RECHARGE_CONFIRMATION = 'recharge_confirmation', 'Recharge Confirmation'
        POWER_DISCONNECTION = 'power_disconnection', 'Power Disconnection'
        POWER_RESTORATION = 'power_restoration', 'Power Restoration'
        METER_OFFLINE = 'meter_offline', 'Meter Offline'
        FAILED_PAYMENT = 'failed_payment', 'Failed Payment'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    meter = models.ForeignKey('meters.Meter', on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')

    type = models.CharField(max_length=30, choices=Type.choices)
    title = models.CharField(max_length=150)
    message = models.TextField()

    email_sent = models.BooleanField(default=False)
    email_error = models.TextField(blank=True)

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.type} -> {self.user.username} @ {self.created_at}"


class NotificationPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences',
    )

    low_credit_alerts = models.BooleanField(default=True)
    recharge_confirmation = models.BooleanField(default=True)
    power_disconnection_alerts = models.BooleanField(default=True)
    power_restoration_alerts = models.BooleanField(default=True)
    meter_offline_alerts = models.BooleanField(default=True)
    failed_payment_alerts = models.BooleanField(default=True)

    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    push_enabled = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preferences for {self.user.username}"

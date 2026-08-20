from django.conf import settings
from django.db import models


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

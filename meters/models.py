import secrets
from django.conf import settings
from django.db import models
from decimal import Decimal
from notifications.services import notify
from notifications.models import Notification



def generate_device_key():
    return secrets.token_hex(20)


class Meter(models.Model):
    class Status(models.TextChoices):
        ONLINE = 'online', 'Online'
        OFFLINE = 'offline', 'Offline'

    serial_number = models.CharField(max_length=64, unique=True)
    device_key = models.CharField(max_length=64, unique=True, default=generate_device_key)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='meters',
    )
    nickname = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=255, blank=True)

    relay_state = models.BooleanField(default=True)
    desired_relay_state = models.BooleanField(default=True)
    credit_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OFFLINE)

    last_voltage = models.FloatField(null=True, blank=True)
    last_current = models.FloatField(null=True, blank=True)
    last_power = models.FloatField(null=True, blank=True)
    last_energy = models.FloatField(null=True, blank=True)

    last_seen_at = models.DateTimeField(null=True, blank=True)
    linked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    low_credit_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=5.00)
    offline_alert_sent = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.serial_number} ({'linked' if self.user else 'unlinked'})"
    
    @property
    def is_low_credit(self):
        return self.credit_balance <= self.low_credit_threshold

    def apply_credit(self, amount):
        amount = Decimal(str(amount))
        was_depleted = self.credit_balance <= 0
        self.credit_balance += amount

        restored = False
        if was_depleted and self.credit_balance > 0:
            self.desired_relay_state = True
            restored = True

        self.save()

        if self.user and restored:
            notify(
                self.user,
                Notification.Type.POWER_RESTORATION,
                f"Power to {self.nickname or self.serial_number} has been restored "
                f"following a successful recharge.",
                meter=self,
            )

        return self


class TelemetryReading(models.Model):
    """Historical log of every reading sent by the meter — for analytics/graphs later."""
    meter = models.ForeignKey(Meter, on_delete=models.CASCADE, related_name='readings')
    voltage = models.FloatField()
    current = models.FloatField()
    power = models.FloatField()
    energy = models.FloatField()
    relay_state = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

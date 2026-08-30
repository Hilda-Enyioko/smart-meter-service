import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

from meters.models import Meter


class Transaction(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions')
    meter = models.ForeignKey(Meter, on_delete=models.CASCADE, related_name='transactions')

    txn_ref = models.CharField(max_length=64, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # major units, e.g. Naira
    currency_code = models.CharField(max_length=10, default='566')

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    provider_response = models.JSONField(null=True, blank=True)  # raw requery response, for audit

    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.txn_ref} - {self.status} - {self.amount}"

    @staticmethod
    def generate_txn_ref():
        return f"SEM-{uuid.uuid4().hex[:20]}"

    @property
    def amount_minor_units(self):
        """Interswitch expects amount in kobo (minor units) — major * 100."""
        return int((self.amount * 100).to_integral_value())

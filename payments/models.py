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

    class FulfillmentStatus(models.TextChoices):
        NOT_APPLICABLE = 'not_applicable', 'Not Applicable'
        PENDING = 'pending', 'Pending'
        FULFILLED = 'fulfilled', 'Fulfilled'
        FAILED = 'failed', 'Failed'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions')
    meter = models.ForeignKey(Meter, on_delete=models.CASCADE, related_name='transactions')

    txn_ref = models.CharField(max_length=64, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency_code = models.CharField(max_length=10, default='NGN')

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    fulfillment_status = models.CharField(
        max_length=20, choices=FulfillmentStatus.choices, default=FulfillmentStatus.NOT_APPLICABLE
    )
    payment_method = models.CharField(max_length=30, blank=True)
    payment_method_detail = models.CharField(max_length=100, blank=True)

    provider_response = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.txn_ref} - {self.status} - {self.amount}"

    @staticmethod
    def generate_txn_ref():
        return f"SEM-{uuid.uuid4().hex[:20]}"

    @property
    def amount_minor_units(self):
        return int((self.amount * 100).to_integral_value())


class TransactionAuditLog(models.Model):
    """
    Append-only audit trail. One row per meaningful event in a transaction's
    lifecycle — initialization, each verification attempt (success or failure),
    fulfillment, webhook receipt, etc. Never updated or deleted.
    """
    class Event(models.TextChoices):
        INITIALIZED = 'initialized', 'Checkout Initialized'
        VERIFY_ATTEMPTED = 'verify_attempted', 'Verification Attempted'
        VERIFY_SUCCEEDED = 'verify_succeeded', 'Verification Succeeded'
        VERIFY_FAILED = 'verify_failed', 'Verification Failed'
        WEBHOOK_RECEIVED = 'webhook_received', 'Webhook Received'
        WEBHOOK_REJECTED = 'webhook_rejected', 'Webhook Rejected (Bad Signature)'
        CREDIT_FULFILLED = 'credit_fulfilled', 'Credit Applied to Meter'
        FULFILLMENT_FAILED = 'fulfillment_failed', 'Credit Application Failed'
        DUPLICATE_IGNORED = 'duplicate_ignored', 'Duplicate Event Ignored (Idempotency)'

    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='audit_logs')
    event = models.CharField(max_length=30, choices=Event.choices)
    detail = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.transaction.txn_ref} - {self.event} @ {self.created_at}"

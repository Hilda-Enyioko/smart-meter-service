import logging
import hashlib
import hmac

from django.conf import settings
from django.db import transaction as db_transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from meters.models import Meter
from notifications.models import Notification
from notifications.services import notify
from .paystack import verify_transaction, PaystackVerificationError
from .models import Transaction, TransactionAuditLog
from .serializers import (
    InitializeCheckoutSerializer,
    TransactionSerializer,
    VerifyTransactionSerializer,
    TransactionDetailSerializer,
)
from notifications.services import notify
from notifications.models import Notification

logger = logging.getLogger(__name__)


class InitializeCheckoutView(APIView):
    """
    POST /api/payments/initialize/   body: { meter_id, amount }
    Creates a pending Transaction with a unique txn_ref, and returns everything
    the frontend needs to open Paystack's Inline Popup.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = InitializeCheckoutSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        meter = get_object_or_404(Meter, id=data['meter_id'], user=request.user)

        txn = Transaction.objects.create(
            user=request.user,
            meter=meter,
            txn_ref=Transaction.generate_txn_ref(),
            amount=data['amount'],
            currency_code='NGN',
            status=Transaction.Status.PENDING,
        )
        
        TransactionAuditLog.objects.create(
            transaction=txn,
            event=TransactionAuditLog.Event.INITIALIZED,
            detail={'amount': str(txn.amount), 'meter_id': meter.id},
        )

        return Response({
            'txn_ref': txn.txn_ref,
            'checkout_config': {
                'key': settings.PAYSTACK_PUBLIC_KEY,
                'email': request.user.email,
                'amount': txn.amount_minor_units,  # kobo
                'ref': txn.txn_ref,
                'currency': 'NGN',
                'callback_url': settings.PAYSTACK_CALLBACK_URL,
                'metadata': {
                    'meter_id': meter.id,
                    'meter_serial_number': meter.serial_number,
                    'user_id': request.user.id,
                },
            }
        }, status=status.HTTP_201_CREATED)


def _verify_and_fulfill(txn_ref, source='verify'):
    """
    source: 'verify' (client-triggered) or 'webhook', just for audit context.
    """
    try:
        txn = Transaction.objects.select_for_update().get(txn_ref=txn_ref)
    except Transaction.DoesNotExist:
        return None, False

    if txn.status == Transaction.Status.SUCCESS:
        TransactionAuditLog.objects.create(
            transaction=txn,
            event=TransactionAuditLog.Event.DUPLICATE_IGNORED,
            detail={'source': source},
        )
        return txn, True

    TransactionAuditLog.objects.create(
        transaction=txn,
        event=TransactionAuditLog.Event.VERIFY_ATTEMPTED,
        detail={'source': source},
    )

    try:
        result = verify_transaction(txn_ref, txn.amount_minor_units)
    except PaystackVerificationError as e:
        logger.error("Paystack verify failed for %s: %s", txn_ref, e)
        TransactionAuditLog.objects.create(
            transaction=txn,
            event=TransactionAuditLog.Event.VERIFY_FAILED,
            detail={'error': str(e), 'source': source},
        )
        return txn, False

    txn.provider_response = result['raw']

    # Capture payment method from Paystack's response for the audit trail
    data = result['raw'].get('data', {})
    txn.payment_method = data.get('channel', '')  # 'card', 'bank', 'ussd', 'qr', 'mobile_money'
    authorization = data.get('authorization', {}) or {}
    if txn.payment_method == 'card':
        brand = authorization.get('card_type', '')
        last4 = authorization.get('last4', '')
        txn.payment_method_detail = f"{brand} ending {last4}".strip()
    elif authorization.get('bank'):
        txn.payment_method_detail = authorization.get('bank', '')

    if result['is_successful']:
        from django.utils import timezone
        txn.status = Transaction.Status.SUCCESS
        txn.verified_at = timezone.now()
        txn.fulfillment_status = Transaction.FulfillmentStatus.PENDING
        txn.save()

        TransactionAuditLog.objects.create(
            transaction=txn,
            event=TransactionAuditLog.Event.VERIFY_SUCCEEDED,
            detail={'payment_method': txn.payment_method, 'source': source},
        )

        try:
            txn.meter.apply_credit(txn.amount)
            txn.fulfillment_status = Transaction.FulfillmentStatus.FULFILLED
            txn.fulfilled_at = timezone.now()
            txn.save()

            TransactionAuditLog.objects.create(
                transaction=txn,
                event=TransactionAuditLog.Event.CREDIT_FULFILLED,
                detail={'amount': str(txn.amount), 'new_balance': str(txn.meter.credit_balance)},
            )
            if txn.user:
                notify(
                    txn.user,
                    Notification.Type.RECHARGE_CONFIRMATION,
                    f"Your recharge of {txn.amount} {txn.currency_code} for "
                    f"{txn.meter.nickname or txn.meter.serial_number} was successful. "
                    f"New credit balance: {txn.meter.credit_balance}.",
                    meter=txn.meter,
            )
        except Exception as e:
            # Payment succeeded but crediting failed — this must NOT be silently
            # lost. Flag it distinctly so it can be manually reconciled.
            logger.error("Fulfillment failed for %s after successful payment: %s", txn_ref, e)
            txn.fulfillment_status = Transaction.FulfillmentStatus.FAILED
            txn.save()
            TransactionAuditLog.objects.create(
                transaction=txn,
                event=TransactionAuditLog.Event.FULFILLMENT_FAILED,
                detail={'error': str(e)},
            )
    else:
        txn.status = Transaction.Status.FAILED
        txn.save()
        TransactionAuditLog.objects.create(
            transaction=txn,
            event=TransactionAuditLog.Event.VERIFY_FAILED,
            detail={'paystack_status': result.get('paystack_status'), 'source': source},
        )
        if txn.user:
            notify(
                txn.user,
                Notification.Type.FAILED_PAYMENT,
                f"Your payment of {txn.amount} {txn.currency_code} for "
                f"{txn.meter.nickname or txn.meter.serial_number} could not be "
                f"confirmed. Reference: {txn.txn_ref}.",
                meter=txn.meter,
            )

    return txn, False

class VerifyTransactionView(APIView):
    """
    POST /api/payments/verify/   body: { txn_ref }
    Called by the frontend right after the Inline Checkout onComplete callback fires.
    Per Interswitch docs, the callback's own resp/desc must NOT be trusted — this
    endpoint performs the mandatory server-side requery before crediting anything.
    Safe to call multiple times (idempotent).
    """
    permission_classes = [permissions.IsAuthenticated]

    @db_transaction.atomic
    def post(self, request):
        serializer = VerifyTransactionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        txn_ref = serializer.validated_data['txn_ref']

        txn = Transaction.objects.select_for_update().filter(
            txn_ref=txn_ref, user=request.user
        ).first()
        if not txn:
            return Response({'detail': 'Transaction not found.'}, status=status.HTTP_404_NOT_FOUND)

        txn, _already = _verify_and_fulfill(txn_ref, source='verify')

        return Response({
            'txn_ref': txn.txn_ref,
            'status': txn.status,
            'amount': txn.amount,
            'credit_balance': txn.meter.credit_balance,
            'verified_at': txn.verified_at,
        })


class PaystackWebhookView(APIView):
    """
    POST /api/payments/webhook/paystack/
    Public endpoint — Paystack's servers call this, not the browser.

    Paystack signs every webhook with an HMAC-SHA512 hash of the raw request
    body, using your secret key, sent in the X-Paystack-Signature header.
    This IS validated below (unlike the earlier Interswitch draft, where the
    signature scheme wasn't documented) — requests that fail this check are
    rejected outright and never touch verification or credit logic.
    """
    permission_classes = [permissions.AllowAny]

    @db_transaction.atomic
    def post(self, request):
        signature = request.headers.get('X-Paystack-Signature', '')
        computed_signature = hmac.new(
            key=settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
            msg=request.body,
            digestmod=hashlib.sha512,
        ).hexdigest()

        if not hmac.compare_digest(computed_signature, signature):
            logger.warning("Rejected Paystack webhook with invalid signature.")
            # Not tied to a specific transaction (we haven't looked one up yet
            # and don't want to trust the payload before the signature checks
            # out), so this is logged via the application logger only, not
            # a TransactionAuditLog row.
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        event = request.data
        event_type = event.get('event')

        if event_type == 'charge.success':
            reference = event.get('data', {}).get('reference')
            if reference:
                txn = Transaction.objects.filter(txn_ref=reference).first()
                if txn:
                    TransactionAuditLog.objects.create(
                        transaction=txn,
                        event=TransactionAuditLog.Event.WEBHOOK_RECEIVED,
                        detail={'event_type': event_type},
                    )
                _verify_and_fulfill(reference, source='webhook')

        return Response({'received': True})


class TransactionListView(generics.ListAPIView):
    """GET /api/payments/transactions/ — current user's recharge history."""
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user).order_by('-created_at')


class TransactionDetailView(generics.RetrieveAPIView):
    """
    GET /payments/transactions/<id>/
    Full detail for a single transaction, including its complete audit trail —
    every verification attempt, webhook receipt, and fulfillment event, in order.
    """
    serializer_class = TransactionDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)

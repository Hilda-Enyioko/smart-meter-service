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
from .paystack import verify_transaction, PaystackVerificationError
from .models import Transaction
from .serializers import (
    InitializeCheckoutSerializer,
    TransactionSerializer,
    VerifyTransactionSerializer,
)

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


def _verify_and_fulfill(txn_ref):
    """
    Shared verification logic used by both the client-triggered verify endpoint
    AND the webhook endpoint, so both paths are equally idempotent.
    Returns (transaction, already_processed: bool)
    """
    try:
        txn = Transaction.objects.select_for_update().get(txn_ref=txn_ref)
    except Transaction.DoesNotExist:
        return None, False

    if txn.status == Transaction.Status.SUCCESS:
        return txn, True

    try:
        result = verify_transaction(txn_ref, txn.amount_minor_units)
    except PaystackVerificationError as e:
        logger.error("Paystack verify failed for %s: %s", txn_ref, e)
        return txn, False

    txn.provider_response = result['raw']

    if result['is_successful']:
        txn.status = Transaction.Status.SUCCESS
        from django.utils import timezone
        txn.verified_at = timezone.now()
        txn.save()
        txn.meter.apply_credit(txn.amount)
    else:
        txn.status = Transaction.Status.FAILED
        txn.save()

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

        txn, _already = _verify_and_fulfill(txn_ref)

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
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        event = request.data
        event_type = event.get('event')

        # Only act on successful charge events — ignore everything else.
        if event_type == 'charge.success':
            reference = event.get('data', {}).get('reference')
            if reference:
                _verify_and_fulfill(reference)

        # Always return 200 quickly so Paystack doesn't retry unnecessarily,
        # even for event types we don't act on.
        return Response({'received': True})


class TransactionListView(generics.ListAPIView):
    """GET /api/payments/transactions/ — current user's recharge history."""
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user).order_by('-created_at')

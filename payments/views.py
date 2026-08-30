import logging

from django.conf import settings
from django.db import transaction as db_transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from meters.models import Meter
from .interswitch import InterswitchVerificationError, requery_transaction
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
    the frontend needs to call window.webpayCheckout(...) for Inline Checkout.
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
            currency_code=str(settings.INTERSWITCH_CURRENCY_CODE),
            status=Transaction.Status.PENDING,
        )

        return Response({
            'txn_ref': txn.txn_ref,
            'checkout_config': {
                'merchant_code': settings.INTERSWITCH_MERCHANT_CODE,
                'pay_item_id': settings.INTERSWITCH_PAY_ITEM_ID,
                'pay_item_name': f"Electricity recharge - {meter.serial_number}",
                'txn_ref': txn.txn_ref,
                'amount': txn.amount_minor_units,  # kobo
                'currency': settings.INTERSWITCH_CURRENCY_CODE,
                'cust_name': request.user.get_full_name() or request.user.username,
                'cust_email': request.user.email,
                'cust_id': str(request.user.id),
                'site_redirect_url': settings.SITE_REDIRECT_URL,
                'mode': settings.INTERSWITCH_MODE,
            }
        }, status=status.HTTP_201_CREATED)


def _verify_and_fulfill(txn_ref):
    """
    Shared verification logic used by both the client-triggered verify endpoint
    AND the webhook endpoint, so both paths are equally idempotent and equally
    untrusting of whatever payload triggered them.

    Returns (transaction, already_processed: bool)
    """
    try:
        txn = Transaction.objects.select_for_update().get(txn_ref=txn_ref)
    except Transaction.DoesNotExist:
        return None, False

    # Idempotency: if we already marked this successful, don't credit twice.
    if txn.status == Transaction.Status.SUCCESS:
        return txn, True

    try:
        result = requery_transaction(txn_ref, txn.amount_minor_units)
    except InterswitchVerificationError as e:
        logger.error("Interswitch requery failed for %s: %s", txn_ref, e)
        return txn, False

    txn.provider_response = result['raw']

    if result['is_successful']:
        txn.status = Transaction.Status.SUCCESS
        from django.utils import timezone
        txn.verified_at = timezone.now()
        txn.save()

        # Automatic credit fulfillment
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


class InterswitchWebhookView(APIView):
    """
    POST /api/payments/webhook/interswitch/
    Public endpoint (no JWT — Interswitch's servers call this, not the browser).

    NOTE: Interswitch's webhook payload format/signature scheme should be
    confirmed against your merchant dashboard's webhook configuration docs —
    the public Web Checkout doc doesn't specify a signature header, only that
    "a POST request is made every time a transaction status changes." Because
    of that, this handler treats the webhook as a NOTIFICATION ONLY — a
    trigger to re-run the same server-side requery used by VerifyTransactionView,
    never as a source of truth by itself. This keeps the endpoint safe even if
    signature validation can't be confirmed/added, and keeps both trigger paths
    (client callback + webhook) sharing one idempotent code path.
    """
    permission_classes = [permissions.AllowAny]

    @db_transaction.atomic
    def post(self, request):
        txn_ref = request.data.get('txnref') or request.data.get('txn_ref')
        if not txn_ref:
            return Response({'detail': 'Missing txn_ref.'}, status=status.HTTP_400_BAD_REQUEST)

        txn, _already = _verify_and_fulfill(txn_ref)
        if txn is None:
            # Return 200 anyway — returning an error here just causes the
            # provider to retry a webhook for a txn_ref we'll never recognize.
            logger.warning("Webhook received for unknown txn_ref: %s", txn_ref)
            return Response({'received': True})

        return Response({'received': True, 'status': txn.status})


class TransactionListView(generics.ListAPIView):
    """GET /api/payments/transactions/ — current user's recharge history."""
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user).order_by('-created_at')

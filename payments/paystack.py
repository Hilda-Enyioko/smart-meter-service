import requests
from django.conf import settings


class PaystackVerificationError(Exception):
    pass


def verify_transaction(reference, expected_amount_minor_units):
    """
    Calls Paystack's server-side transaction verify endpoint.
    Per Paystack docs: never trust the frontend popup's callback result alone —
    always verify server-side using the secret key before giving value.
    """
    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        raise PaystackVerificationError(f"Verify request failed: {e}")

    payload = response.json()
    data = payload.get('data', {})

    paystack_status = data.get('status')       # 'success', 'failed', 'abandoned', etc.
    returned_amount = data.get('amount')        # in kobo

    is_successful = (
        payload.get('status') is True
        and paystack_status == 'success'
        and returned_amount is not None
        and int(returned_amount) == int(expected_amount_minor_units)
    )

    return {
        'is_successful': is_successful,
        'paystack_status': paystack_status,
        'gateway_response': data.get('gateway_response'),
        'returned_amount': returned_amount,
        'raw': payload,
    }

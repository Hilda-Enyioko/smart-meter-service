import requests
from django.conf import settings


class InterswitchVerificationError(Exception):
    pass


def requery_transaction(txn_ref, expected_amount_minor_units):
    """
    Calls Interswitch's server-side transaction requery endpoint.
    Per Interswitch docs: only transactions from the last 3 months can be requeried,
    and the response's Amount MUST be compared against what you expected before
    giving value — never trust resp/desc from a client redirect or webhook alone.
    """
    url = f"{settings.INTERSWITCH_REQUERY_BASE_URL}/collections/api/v1/gettransaction.json"
    params = {
        'merchantcode': settings.INTERSWITCH_MERCHANT_CODE,
        'transactionreference': txn_ref,
        'amount': expected_amount_minor_units,
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        raise InterswitchVerificationError(f"Requery request failed: {e}")

    data = response.json()

    response_code = data.get('ResponseCode')
    returned_amount = data.get('Amount')

    is_successful = (
        response_code == '00'
        and returned_amount is not None
        and int(returned_amount) == int(expected_amount_minor_units)
    )

    return {
        'is_successful': is_successful,
        'response_code': response_code,
        'response_description': data.get('ResponseDescription'),
        'returned_amount': returned_amount,
        'raw': data,
    }

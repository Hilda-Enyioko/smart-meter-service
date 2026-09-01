import logging
import resend
from django.conf import settings

logger = logging.getLogger(__name__)
resend.api_key = settings.RESEND_API_KEY


def send_email(to_email, subject, html_body):
    """
    Sends via Resend. Returns (success: bool, error: str).
    Never raises — a failed email must not break the calling flow (e.g. a
    telemetry POST from the ESP32 should never 500 because an email failed).
    """
    if not to_email:
        return False, "No recipient email on file."

    try:
        resend.Emails.send({
            "from": settings.NOTIFICATION_FROM_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html_body,
        })
        return True, ""
    except Exception as e:
        logger.error("Resend email failed to %s: %s", to_email, e)
        return False, str(e)

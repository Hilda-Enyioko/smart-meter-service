from .emailer import send_email
from .models import Notification, NotificationPreference


TEMPLATES = {
    Notification.Type.LOW_CREDIT: {
        'pref_field': 'low_credit_alerts',
        'subject': "Low Credit Alert - {meter}",
        'title': "Low Credit Warning",
    },
    Notification.Type.RECHARGE_CONFIRMATION: {
        'pref_field': 'recharge_confirmation',
        'subject': "Recharge Successful - {meter}",
        'title': "Recharge Confirmed",
    },
    Notification.Type.POWER_DISCONNECTION: {
        'pref_field': 'power_disconnection_alerts',
        'subject': "Power Disconnected - {meter}",
        'title': "Power Disconnected",
    },
    Notification.Type.POWER_RESTORATION: {
        'pref_field': 'power_restoration_alerts',
        'subject': "Power Restored - {meter}",
        'title': "Power Restored",
    },
    Notification.Type.METER_OFFLINE: {
        'pref_field': 'meter_offline_alerts',
        'subject': "Meter Offline - {meter}",
        'title': "Meter Offline",
    },
    Notification.Type.FAILED_PAYMENT: {
        'pref_field': 'failed_payment_alerts',
        'subject': "Payment Failed - {meter}",
        'title': "Payment Failed",
    },
}


def notify(user, notif_type, message, meter=None):
    """
    Central entry point for every notification in the system.
    - Respects the user's NotificationPreference flags (both the specific alert
      type AND email_enabled).
    - Always creates a Notification row (in-app history), regardless of whether
      email is enabled, so the in-app list is a complete record.
    - Never raises — safe to call from anywhere, including hot paths like
      telemetry ingestion.
    """
    config = TEMPLATES[notif_type]
    meter_label = meter.nickname or meter.serial_number if meter else "your account"

    prefs, _ = NotificationPreference.objects.get_or_create(user=user)
    alert_enabled = getattr(prefs, config['pref_field'])

    notification = Notification.objects.create(
        user=user,
        meter=meter,
        type=notif_type,
        title=config['title'],
        message=message,
    )

    if not alert_enabled:
        return notification  # user opted out of this alert type entirely

    if prefs.email_enabled:
        subject = config['subject'].format(meter=meter_label)
        html_body = f"""
            <h2>{config['title']}</h2>
            <p>{message}</p>
            <p style="color:#888;font-size:12px;">Smart Energy Metering System</p>
        """
        success, error = send_email(user.email, subject, html_body)
        notification.email_sent = success
        notification.email_error = error
        notification.save()

    return notification

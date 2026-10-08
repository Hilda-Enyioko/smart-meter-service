from django.db.models import Q
from django.utils import timezone

from notifications.models import Notification
from notifications.services import notify
from .models import Meter, OFFLINE_AFTER


def mark_stale_meters_offline():
    cutoff = timezone.now() - OFFLINE_AFTER
    stale_filter = Q(last_seen_at__lt=cutoff) | Q(last_seen_at__isnull=True)

    candidates = (
        Meter.objects.filter(status=Meter.Status.ONLINE)
        .filter(stale_filter)
        .select_related('user')
    )

    marked = alerted = 0
    for meter in candidates:
        # Atomic claim: only succeeds if the meter is STILL online and STILL stale.
        # Avoids overwriting fresh telemetry and prevents duplicate alerts
        # if two sweeps overlap.
        claimed = (
            Meter.objects
            .filter(pk=meter.pk, status=Meter.Status.ONLINE)
            .filter(stale_filter)
            .update(status=Meter.Status.OFFLINE, updated_at=timezone.now())
        )
        if not claimed:
            continue
        marked += 1

        if meter.user:
            sent = (
                Meter.objects
                .filter(pk=meter.pk, offline_alert_sent=False)
                .update(offline_alert_sent=True)
            )
            if sent:
                notify(
                    meter.user,
                    Notification.Type.METER_OFFLINE,
                    f"{meter.nickname or meter.serial_number} has stopped "
                    f"reporting data and appears to be offline.",
                    meter=meter,
                )
                alerted += 1

    return marked, alerted

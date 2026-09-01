from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import models

from meters.models import Meter
from notifications.services import notify
from notifications.models import Notification

OFFLINE_THRESHOLD_MINUTES = 2  # meter expected to check in every ~10s


class Command(BaseCommand):
    help = "Scans for meters that have gone silent and sends a one-time offline alert."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(minutes=OFFLINE_THRESHOLD_MINUTES)

        stale_meters = Meter.objects.filter(
            user__isnull=False,
            offline_alert_sent=False,
        ).filter(
            models.Q(last_seen_at__lt=cutoff) | models.Q(last_seen_at__isnull=True)
        )

        count = 0
        for meter in stale_meters:
            meter.status = Meter.Status.OFFLINE
            meter.offline_alert_sent = True
            meter.save()

            notify(
                meter.user,
                Notification.Type.METER_OFFLINE,
                f"{meter.nickname or meter.serial_number} has not reported data in "
                f"over {OFFLINE_THRESHOLD_MINUTES} minutes and may be offline.",
                meter=meter,
            )
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Checked meters. {count} marked offline and notified."))

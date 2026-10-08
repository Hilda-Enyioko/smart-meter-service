from django.core.management.base import BaseCommand
from meters.services import mark_stale_meters_offline


class Command(BaseCommand):
    help = "Mark silent meters offline and send a one-time offline alert."

    def handle(self, *args, **options):
        marked, alerted = mark_stale_meters_offline()
        self.stdout.write(self.style.SUCCESS(f"{marked} marked offline, {alerted} notified."))
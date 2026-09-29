from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from appearance.models import PowerAutomateDelivery
from appearance.power_automate import attempt_power_automate_delivery, retry_delay_seconds


class Command(BaseCommand):
    help = "Retry failed/pending Power Automate deliveries using bounded exponential-style delays."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        if not settings.POWER_AUTOMATE_ENABLED:
            self.stdout.write(self.style.WARNING("Power Automate delivery is disabled."))
            return

        limit = max(1, min(options["limit"], 1000))
        max_attempts = settings.POWER_AUTOMATE_MAX_ATTEMPTS
        now = timezone.now()

        candidates = (
            PowerAutomateDelivery.objects
            .filter(status__in=[
                PowerAutomateDelivery.Status.FAILED,
                PowerAutomateDelivery.Status.PENDING,
            ])
            .filter(attempts__lt=max_attempts)
            .select_related("appearance_check", "appearance_check__recorded_by")
            .order_by("last_attempt_at", "created_at")[:limit]
        )

        sent = failed = skipped = 0
        for delivery in candidates:
            if delivery.last_attempt_at:
                due_at = delivery.last_attempt_at + timedelta(
                    seconds=retry_delay_seconds(delivery.attempts)
                )
                if due_at > now:
                    skipped += 1
                    continue

            result = attempt_power_automate_delivery(delivery)
            if result.status == PowerAutomateDelivery.Status.SENT:
                sent += 1
            else:
                failed += 1

        self.stdout.write(
            f"Power Automate retry complete: sent={sent} failed={failed} not_due={skipped}"
        )

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from appearance.models import DataUpload, ImportBatch


class Command(BaseCommand):
    help = "Delete retained source upload files after their configured retention period."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=settings.UPLOAD_RETENTION_DAYS)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        days = max(1, options["days"])
        cutoff = timezone.now() - timedelta(days=days)
        queryset = (
            DataUpload.objects
            .filter(
                processed_at__lt=cutoff,
                status__in=[
                    ImportBatch.Status.SUCCESS,
                    ImportBatch.Status.PARTIAL,
                    ImportBatch.Status.SKIPPED,
                ],
            )
            .exclude(file="")
            .order_by("pk")
        )

        count = 0
        for upload in queryset.iterator(chunk_size=100):
            count += 1
            if options["dry_run"]:
                continue

            name = upload.file.name
            storage = upload.file.storage
            if name and storage.exists(name):
                storage.delete(name)
            DataUpload.objects.filter(pk=upload.pk).update(file="")

        action = "would purge" if options["dry_run"] else "purged"
        self.stdout.write(f"{action} {count} retained upload file(s) older than {days} day(s).")

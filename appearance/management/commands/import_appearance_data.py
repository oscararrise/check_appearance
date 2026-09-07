import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from appearance.import_services import import_workbook
from appearance.models import DataUpload, ImportBatch


class Command(BaseCommand):
    help = "Import AP source workbooks (tattoos or appearance approvals) from data/inbox."

    def add_arguments(self, parser):
        parser.add_argument("--file", help="Optional specific .xlsx file to import.")
        parser.add_argument(
            "--source",
            choices=["auto", "tattoos", "approvals"],
            default="auto",
            help="Force a source type or auto-detect it.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-import a workbook even if its hash was already processed.",
        )

    def handle(self, *args, **options):
        inbox = Path(settings.DATA_INBOX)
        processed = Path(settings.DATA_PROCESSED)
        rejected = Path(settings.DATA_REJECTED)
        inbox.mkdir(parents=True, exist_ok=True)
        processed.mkdir(parents=True, exist_ok=True)
        rejected.mkdir(parents=True, exist_ok=True)

        files = [Path(options["file"])] if options.get("file") else sorted(inbox.glob("*.xlsx"))
        if not files:
            self.stdout.write(self.style.WARNING("No .xlsx files found in data/inbox."))
            return

        source_map = {
            "auto": DataUpload.SourceType.AUTO,
            "tattoos": ImportBatch.SourceType.TATTOOS,
            "approvals": ImportBatch.SourceType.APPEARANCE_APPROVALS,
        }
        source_type = source_map[options["source"]]

        for path in files:
            try:
                batch = import_workbook(path, source_type=source_type, force=options["force"])
                if batch.status == ImportBatch.Status.SKIPPED:
                    self.stdout.write(self.style.WARNING(f"{path.name}: already imported, skipped."))
                else:
                    self.stdout.write(self.style.SUCCESS(
                        f"{path.name}: source={batch.source_type}, imported={batch.rows_imported}, "
                        f"rejected={batch.rows_rejected}, status={batch.status}."
                    ))

                if path.parent.resolve() == inbox.resolve():
                    target = processed / path.name
                    if target.exists():
                        target.unlink()
                    shutil.move(str(path), str(target))
            except Exception as exc:
                if path.exists() and path.parent.resolve() == inbox.resolve():
                    target = rejected / path.name
                    if target.exists():
                        target.unlink()
                    shutil.move(str(path), str(target))
                raise CommandError(f"Failed to import {path.name}: {exc}") from exc

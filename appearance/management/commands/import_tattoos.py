from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Backward-compatible wrapper for importing the GP tattoo tracker."

    def add_arguments(self, parser):
        parser.add_argument("--file", help="Optional specific .xlsx file to import.")
        parser.add_argument("--force", action="store_true", help="Re-import a file even if its hash was already processed.")

    def handle(self, *args, **options):
        kwargs = {
            "source": "tattoos",
            "force": options["force"],
        }
        if options.get("file"):
            kwargs["file"] = options["file"]
        call_command("import_appearance_data", **kwargs)

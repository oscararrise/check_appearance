from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the non-admin Appearance role groups used by the application."

    def handle(self, *args, **options):
        supervisor, created = Group.objects.get_or_create(name="Appearance Supervisors")
        state = "created" if created else "already exists"
        self.stdout.write(f"Appearance Supervisors: {state}")
        self.stdout.write(
            "Operators only need an active Django account. Add export-capable users to Appearance Supervisors."
        )

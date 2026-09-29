from django.apps import AppConfig


class AppearanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "appearance"

    def ready(self):
        # Register production configuration checks.
        from . import checks  # noqa: F401

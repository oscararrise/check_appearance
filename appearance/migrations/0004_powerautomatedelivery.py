# Generated manually for the Appearance Power Automate integration.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("appearance", "0003_processschedule"),
    ]

    operations = [
        migrations.CreateModel(
            name="PowerAutomateDelivery",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("SENT", "Sent"),
                            ("FAILED", "Failed"),
                            ("DISABLED", "Integration disabled"),
                        ],
                        db_index=True,
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                ("payload", models.JSONField(default=dict)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("response_status", models.PositiveIntegerField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                ("last_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "appearance_check",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="power_automate_delivery",
                        to="appearance.appearancecheck",
                    ),
                ),
            ],
            options={
                "verbose_name": "Power Automate delivery",
                "verbose_name_plural": "Power Automate deliveries",
                "ordering": ["-created_at"],
            },
        ),
    ]

from datetime import time

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_default_schedules(apps, schema_editor):
    ProcessSchedule = apps.get_model("appearance", "ProcessSchedule")
    defaults = [
        ("PREPARATION", "MORNING", time(6, 0), time(8, 0)),
        ("PREPARATION", "AFTERNOON", time(14, 0), time(16, 0)),
        ("PREPARATION", "NIGHT", time(22, 0), time(0, 0)),
        ("CHECK", "MORNING", time(6, 50), time(7, 30)),
        ("CHECK", "AFTERNOON", time(14, 50), time(15, 30)),
        ("CHECK", "NIGHT", time(22, 50), time(23, 30)),
    ]
    for process, shift, start_time, end_time in defaults:
        ProcessSchedule.objects.get_or_create(
            process=process,
            shift=shift,
            defaults={"start_time": start_time, "end_time": end_time},
        )


def remove_seeded_schedules(apps, schema_editor):
    ProcessSchedule = apps.get_model("appearance", "ProcessSchedule")
    ProcessSchedule.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("appearance", "0002_ap_source_imports"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProcessSchedule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("process", models.CharField(choices=[("PREPARATION", "Appearance Preparation"), ("CHECK", "Appearance Check")], db_index=True, max_length=20)),
                ("shift", models.CharField(choices=[("MORNING", "Morning"), ("AFTERNOON", "Afternoon"), ("NIGHT", "Night")], max_length=20)),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="appearance_schedule_updates", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Operating schedule",
                "verbose_name_plural": "Operating schedules",
                "ordering": ["process", "shift"],
            },
        ),
        migrations.AddConstraint(
            model_name="processschedule",
            constraint=models.UniqueConstraint(fields=("process", "shift"), name="app_sched_proc_shift_uniq"),
        ),
        migrations.RunPython(seed_default_schedules, remove_seeded_schedules),
    ]

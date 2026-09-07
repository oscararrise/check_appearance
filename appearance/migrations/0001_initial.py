import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="ImportBatch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file_name", models.CharField(max_length=255)),
                ("file_hash", models.CharField(db_index=True, max_length=64)),
                ("source_type", models.CharField(default="TATTOOS", max_length=50)),
                ("status", models.CharField(choices=[("PROCESSING", "Processing"), ("SUCCESS", "Success"), ("PARTIAL", "Partial"), ("FAILED", "Failed"), ("SKIPPED", "Skipped")], default="PROCESSING", max_length=20)),
                ("rows_received", models.PositiveIntegerField(default=0)),
                ("rows_imported", models.PositiveIntegerField(default=0)),
                ("rows_rejected", models.PositiveIntegerField(default=0)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ["-started_at"]},
        ),
        migrations.CreateModel(
            name="AppearanceCheck",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("employee_id", models.CharField(db_index=True, max_length=50)),
                ("employee_name", models.CharField(max_length=255)),
                ("role", models.CharField(blank=True, max_length=255)),
                ("shift", models.CharField(choices=[("MORNING", "Morning"), ("AFTERNOON", "Afternoon"), ("NIGHT", "Night")], db_index=True, max_length=20)),
                ("recorded_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("status", models.CharField(choices=[("READY", "Ready"), ("NOT_READY", "Not Ready"), ("DECLINED", "Declined")], max_length=20)),
                ("comment", models.CharField(blank=True, max_length=500)),
                ("recorded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Appearance check", "verbose_name_plural": "Appearance checks", "ordering": ["-recorded_at"]},
        ),
        migrations.CreateModel(
            name="PreparationScan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("employee_id", models.CharField(db_index=True, max_length=50)),
                ("employee_name", models.CharField(max_length=255)),
                ("role", models.CharField(blank=True, max_length=255)),
                ("shift", models.CharField(choices=[("MORNING", "Morning"), ("AFTERNOON", "Afternoon"), ("NIGHT", "Night")], db_index=True, max_length=20)),
                ("recorded_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("recorded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Preparation scan", "verbose_name_plural": "Preparation scans", "ordering": ["-recorded_at"]},
        ),
        migrations.CreateModel(
            name="ImportIssue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("row_number", models.PositiveIntegerField(blank=True, null=True)),
                ("employee_id", models.CharField(blank=True, max_length=50)),
                ("message", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("batch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="issues", to="appearance.importbatch")),
            ],
            options={"ordering": ["row_number", "id"]},
        ),
        migrations.CreateModel(
            name="TattooRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("employee_id", models.CharField(db_index=True, max_length=50)),
                ("source_name", models.CharField(blank=True, max_length=255)),
                ("tattoo_details", models.TextField(blank=True)),
                ("should_be_covered", models.BooleanField(blank=True, null=True)),
                ("connotation", models.TextField(blank=True)),
                ("location", models.CharField(blank=True, max_length=255)),
                ("source_date", models.DateField(blank=True, null=True)),
                ("source_sheet", models.CharField(blank=True, max_length=100)),
                ("source_file", models.CharField(max_length=255)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("import_batch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="tattoos", to="appearance.importbatch")),
            ],
            options={"ordering": ["employee_id", "-created_at"]},
        ),
        migrations.AddIndex(
            model_name="tattoorecord",
            index=models.Index(fields=["employee_id", "is_active"], name="appearance__employe_290a15_idx"),
        ),
    ]

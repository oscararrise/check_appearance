import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("appearance", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="importbatch",
            name="source_type",
            field=models.CharField(
                choices=[
                    ("TATTOOS", "GP tattoo tracker"),
                    ("APPEARANCE_APPROVALS", "Appearance approvals tracker"),
                ],
                default="TATTOOS",
                max_length=50,
            ),
        ),
        migrations.CreateModel(
            name="AppearanceApprovalRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("employee_id", models.CharField(db_index=True, max_length=50)),
                ("source_name", models.CharField(blank=True, max_length=255)),
                ("responsible", models.CharField(blank=True, max_length=255)),
                ("situation", models.CharField(blank=True, max_length=255)),
                ("test_time_frame_needed", models.CharField(choices=[("YES", "Yes"), ("NO", "No"), ("NA", "N/A"), ("UNKNOWN", "Not specified")], default="UNKNOWN", max_length=20)),
                ("medical_condition", models.CharField(choices=[("YES", "Yes"), ("NO", "No"), ("NA", "N/A"), ("UNKNOWN", "Not specified")], default="UNKNOWN", max_length=20)),
                ("paperwork_submitted", models.CharField(choices=[("YES", "Yes"), ("NO", "No"), ("NA", "N/A"), ("UNKNOWN", "Not specified")], default="UNKNOWN", max_length=20)),
                ("test_initial_date", models.DateField(blank=True, null=True)),
                ("test_initial_date_raw", models.CharField(blank=True, max_length=100)),
                ("test_final_date", models.DateField(blank=True, null=True)),
                ("test_final_date_raw", models.CharField(blank=True, max_length=100)),
                ("status", models.CharField(choices=[("APPROVED", "Approved"), ("REJECTED", "Rejected"), ("IN_PROGRESS", "In progress"), ("UNKNOWN", "Not specified")], db_index=True, default="UNKNOWN", max_length=20)),
                ("comments", models.TextField(blank=True)),
                ("source_sheet", models.CharField(blank=True, max_length=100)),
                ("source_file", models.CharField(max_length=255)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("import_batch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="appearance_approvals", to="appearance.importbatch")),
            ],
            options={"ordering": ["employee_id", "situation", "-created_at"]},
        ),
        migrations.AddIndex(
            model_name="appearanceapprovalrecord",
            index=models.Index(fields=["employee_id", "is_active"], name="appearance__employee_approval_idx"),
        ),
        migrations.CreateModel(
            name="DataUpload",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(upload_to="appearance_imports/%Y/%m/")),
                ("source_type", models.CharField(choices=[("AUTO", "Auto-detect"), ("TATTOOS", "GP tattoo tracker"), ("APPEARANCE_APPROVALS", "Appearance approvals tracker")], default="AUTO", max_length=50)),
                ("detected_source_type", models.CharField(blank=True, max_length=50)),
                ("status", models.CharField(choices=[("PROCESSING", "Processing"), ("SUCCESS", "Success"), ("PARTIAL", "Partial"), ("FAILED", "Failed"), ("SKIPPED", "Skipped")], default="PROCESSING", max_length=20)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("import_batch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="uploads", to="appearance.importbatch")),
                ("uploaded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="appearance_data_uploads", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-uploaded_at"]},
        ),
    ]

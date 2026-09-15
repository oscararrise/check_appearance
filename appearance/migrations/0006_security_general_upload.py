from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("appearance", "0005_hibobemployee_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="importbatch",
            name="source_type",
            field=models.CharField(
                choices=[
                    ("TATTOOS", "GP tattoo tracker"),
                    ("APPEARANCE_APPROVALS", "Appearance approvals tracker"),
                    ("SECURITY_GENERAL", "Security general base"),
                ],
                default="TATTOOS",
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="dataupload",
            name="source_type",
            field=models.CharField(
                choices=[
                    ("AUTO", "Auto-detect"),
                    ("TATTOOS", "GP tattoo tracker"),
                    ("APPEARANCE_APPROVALS", "Appearance approvals tracker"),
                    ("SECURITY_GENERAL", "Security general base"),
                ],
                default="AUTO",
                max_length=50,
            ),
        ),
        migrations.CreateModel(
            name="SecurityInfoRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("employee_id", models.CharField(blank=True, db_index=True, max_length=50)),
                ("document", models.CharField(db_index=True, max_length=50)),
                ("first_name", models.CharField(blank=True, max_length=150)),
                ("last_name", models.CharField(blank=True, max_length=200)),
                ("contact_number", models.CharField(blank=True, max_length=100)),
                ("blood_type", models.CharField(blank=True, max_length=20)),
                ("vehicle_type", models.CharField(blank=True, max_length=100)),
                ("vehicle_brand", models.CharField(blank=True, max_length=100)),
                ("vehicle_model", models.CharField(blank=True, max_length=100)),
                ("vehicle_color", models.CharField(blank=True, max_length=100)),
                ("vehicle_plate", models.CharField(blank=True, max_length=100)),
                ("department", models.CharField(blank=True, max_length=255)),
                ("role", models.CharField(blank=True, max_length=255)),
                ("card_number", models.CharField(blank=True, max_length=255)),
                ("secondary_card_number", models.CharField(blank=True, max_length=255)),
                ("facility_code_wfm", models.CharField(blank=True, max_length=100)),
                ("facility_code_se", models.CharField(blank=True, max_length=100)),
                ("photo_and_data", models.CharField(blank=True, max_length=100)),
                ("eps", models.CharField(blank=True, max_length=255)),
                ("six_digit_card_number", models.CharField(blank=True, max_length=255)),
                ("first_replacement", models.CharField(blank=True, max_length=255)),
                ("first_replacement_date", models.CharField(blank=True, max_length=100)),
                ("second_replacement", models.CharField(blank=True, max_length=255)),
                ("second_replacement_date", models.CharField(blank=True, max_length=100)),
                ("source_file", models.CharField(max_length=255)),
                ("source_sheet", models.CharField(blank=True, max_length=100)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "import_batch",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="security_records",
                        to="appearance.importbatch",
                    ),
                ),
            ],
            options={
                "verbose_name": "Security information",
                "verbose_name_plural": "Security information",
                "ordering": ["employee_id", "document", "-created_at"],
                "indexes": [
                    models.Index(fields=["employee_id", "is_active"], name="sec_info_emp_active_idx"),
                    models.Index(fields=["document", "is_active"], name="sec_info_doc_active_idx"),
                ],
            },
        ),
    ]

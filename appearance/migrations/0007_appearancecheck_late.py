from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("appearance", "0006_security_general_upload"),
    ]

    operations = [
        migrations.AddField(
            model_name="appearancecheck",
            name="is_late",
            field=models.BooleanField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="appearancecheck",
            name="late_marked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

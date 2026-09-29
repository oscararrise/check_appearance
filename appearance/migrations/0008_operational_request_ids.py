import uuid

from django.db import migrations, models


def backfill_request_ids(apps, schema_editor):
    for model_name in ("PreparationScan", "AppearanceCheck"):
        model = apps.get_model("appearance", model_name)
        for row in model.objects.filter(request_id__isnull=True).only("pk").iterator(chunk_size=1000):
            model.objects.filter(pk=row.pk).update(request_id=uuid.uuid4())


class Migration(migrations.Migration):

    dependencies = [
        ("appearance", "0007_appearancecheck_late"),
    ]

    operations = [
        migrations.AddField(
            model_name="preparationscan",
            name="request_id",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="appearancecheck",
            name="request_id",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(backfill_request_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="preparationscan",
            name="request_id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name="appearancecheck",
            name="request_id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]

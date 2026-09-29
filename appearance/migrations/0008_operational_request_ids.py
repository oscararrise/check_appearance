import uuid

from django.db import migrations, models


def backfill_request_ids(apps, schema_editor):
    for model_name in ("PreparationScan", "AppearanceCheck"):
        model = apps.get_model("appearance", model_name)
        pending = []

        for row in model.objects.filter(request_id__isnull=True).only("pk").iterator(chunk_size=1000):
            row.request_id = uuid.uuid4()
            pending.append(row)

            if len(pending) >= 1000:
                model.objects.bulk_update(pending, ["request_id"], batch_size=1000)
                pending.clear()

        if pending:
            model.objects.bulk_update(pending, ["request_id"], batch_size=1000)


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

from django.db import migrations


def backfill_tax_rate(apps, schema_editor):
    AccountItem = apps.get_model("invoice", "AccountItem")
    AccountItem.objects.filter(item_code__slug="NT").update(tax_rate=0)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("invoice", "0032_accountitem_tax_rate"),
    ]

    operations = [
        migrations.RunPython(backfill_tax_rate, noop),
    ]

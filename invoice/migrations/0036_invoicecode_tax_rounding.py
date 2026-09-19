from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("invoice", "0035_accountitem_deleted_at_invoicecode_amended"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoicecode",
            name="tax_rounding",
            field=models.CharField(
                blank=True,
                choices=[("floor", "切捨て"), ("round", "四捨五入")],
                default="",
                max_length=10,
                verbose_name="端数処理",
            ),
        ),
    ]

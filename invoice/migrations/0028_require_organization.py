from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('invoice', '0027_backfill_default_organization'),
    ]

    operations = [
        migrations.AlterField(
            model_name='client',
            name='organization',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='clients', to='invoice.organization', verbose_name='組織'),
        ),
        migrations.AlterField(
            model_name='itemcode',
            name='organization',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='item_codes', to='invoice.organization', verbose_name='組織'),
        ),
        migrations.AlterField(
            model_name='accountitem',
            name='organization',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='account_items', to='invoice.organization', verbose_name='組織'),
        ),
    ]

from django.db import migrations


def rename_from_legacy_my_company(apps, schema_editor):
    """The placeholder "Default Organization" name should be the real
    company name, taken from the same legacy pk=2 Client row used in
    0030_backfill_organization_issuer_fields."""
    Organization = apps.get_model("invoice", "Organization")
    Client = apps.get_model("invoice", "Client")

    try:
        my_company = Client.objects.get(pk=2)
    except Client.DoesNotExist:
        return

    organization = my_company.organization
    if organization is None or organization.name != "Default Organization":
        return

    organization.name = my_company.name
    organization.save()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("invoice", "0030_backfill_organization_issuer_fields"),
    ]

    operations = [
        migrations.RunPython(rename_from_legacy_my_company, noop_reverse),
    ]

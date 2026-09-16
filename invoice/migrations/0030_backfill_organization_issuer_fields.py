from django.db import migrations


def backfill_from_legacy_my_company(apps, schema_editor):
    """
    calc.py used to hardcode `Client.objects.get(pk=2)` as "our own company"
    (the invoice issuer) for every tenant. Copy that row's details onto the
    Organization it belongs to, so the org-scoped PDF pipeline has the same
    data to work with.
    """
    Organization = apps.get_model("invoice", "Organization")
    Client = apps.get_model("invoice", "Client")

    try:
        my_company = Client.objects.get(pk=2)
    except Client.DoesNotExist:
        return

    organization = my_company.organization
    if organization is None:
        return

    organization.bank_account_id = my_company.bank_account_id
    organization.register_no = my_company.register_no
    organization.post_code = my_company.post_code
    organization.address1 = my_company.address1
    organization.address2 = my_company.address2
    organization.tel = my_company.tel
    organization.email = my_company.email
    organization.save()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("invoice", "0029_organization_issuer_fields"),
    ]

    operations = [
        migrations.RunPython(backfill_from_legacy_my_company, noop_reverse),
    ]

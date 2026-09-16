from django.conf import settings
from django.db import migrations


def create_default_org_and_backfill(apps, schema_editor):
    Organization = apps.get_model('invoice', 'Organization')
    OrganizationMembership = apps.get_model('invoice', 'OrganizationMembership')
    Client = apps.get_model('invoice', 'Client')
    ItemCode = apps.get_model('invoice', 'ItemCode')
    AccountItem = apps.get_model('invoice', 'AccountItem')
    user_app_label, user_model_name = settings.AUTH_USER_MODEL.split('.')
    User = apps.get_model(user_app_label, user_model_name)

    org, _ = Organization.objects.get_or_create(
        slug='default',
        defaults={'name': 'Default Organization'},
    )

    for user in User.objects.all():
        OrganizationMembership.objects.get_or_create(
            user=user, organization=org, defaults={'role': 'owner'},
        )

    Client.objects.filter(organization__isnull=True).update(organization=org)
    ItemCode.objects.filter(organization__isnull=True).update(organization=org)
    AccountItem.objects.filter(organization__isnull=True).update(organization=org)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('invoice', '0026_organization_multitenancy_schema'),
    ]

    operations = [
        migrations.RunPython(create_default_org_and_backfill, noop_reverse),
    ]

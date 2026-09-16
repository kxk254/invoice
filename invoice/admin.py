from django.contrib import admin
from .models import (
    BankAccount, Client, AccountItem, InvoiceCode, ItemCode, CsvDate,
    Organization, OrganizationMembership,
)

# Register your models here.
admin.site.register(BankAccount)
admin.site.register(Client)
admin.site.register(AccountItem)
admin.site.register(InvoiceCode)
admin.site.register(ItemCode)
admin.site.register(CsvDate)
admin.site.register(Organization)
admin.site.register(OrganizationMembership)
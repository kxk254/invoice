from django.contrib import admin
from .models import BankAccount, Company, AccountItem, InvoiceCode, ItemCode, CsvDate

# Register your models here.
admin.site.register(BankAccount)
admin.site.register(Company)
admin.site.register(AccountItem)
admin.site.register(InvoiceCode)
admin.site.register(ItemCode)
admin.site.register(CsvDate)
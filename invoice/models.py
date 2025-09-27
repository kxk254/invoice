from django.db import models
import datetime
import calendar
from datetime import date


class BankAccount(models.Model):
    name = models.CharField(verbose_name="銀行名", max_length=50)
    branch_name = models.CharField(verbose_name="支店名", max_length=50, blank=True, null=True)
    branch_code = models.CharField(verbose_name="支店コード", max_length=15, blank=True, null=True)
    account_type = models.CharField(verbose_name="預金種別", max_length=20, blank=True, null=True)
    account_number = models.CharField(verbose_name="口座番号", max_length=50, blank=True, null=True)
    account_name = models.CharField(verbose_name="名義人", max_length=80, blank=True, null=True)
    account_name_kana = models.CharField(verbose_name="名義人カナ", max_length=80, blank=True, null=True)

    def __str__(self):
        return self.name


# Create your models here.
class Company(models.Model):
    name = models.CharField(verbose_name="会社名", max_length=50)
    bank_account = models.ForeignKey(BankAccount, verbose_name="銀行名", on_delete=models.CASCADE)
    short_name = models.CharField(verbose_name="短縮名", max_length=20)
    name_yayoi = models.CharField(verbose_name="弥生補助科目", max_length=20, blank=True, null=True)
    register_no = models.CharField(verbose_name="登録番号", max_length=20, blank=True, null=True)
    post_code = models.CharField(verbose_name="〒", max_length=20, blank=True, null=True)
    address1 = models.CharField(verbose_name="住所１", max_length=150, default='')
    address2 = models.CharField(verbose_name="住所２", max_length=150, default='', blank=True, null=True)
    tel = models.CharField(verbose_name="電話", max_length=50, default='', blank=True, null=True)
    email = models.EmailField(verbose_name="Email", max_length=100, default='', blank=True, null=True)
    slug = models.CharField(verbose_name="会社キー", max_length=20, blank=True, null=True)

    def __str__(self):
        return self.short_name
    
class ItemCode(models.Model):
    name = models.CharField(verbose_name="項目名", max_length=50)
    short_name = models.CharField(verbose_name="短縮名", max_length=20)
    tax_rate = models.CharField(verbose_name="税率", max_length=20, blank=True, null=True)
    slug = models.CharField(verbose_name="項目キー", max_length=20, blank=True, null=True)

    def __str__(self):
        return self.short_name

class AccountItem(models.Model):
    # Start of next month
    def get_start_of_this_month():
        today = datetime.date.today()
        # Calculate the first day of next month
        first_day_this_month = today.replace(day=1)
        return first_day_this_month.replace(day=1)
    
    # Start of next month
    def get_start_of_next_month():
        today = datetime.date.today()
        # Calculate the first day of next month
        first_day_next_month = today.replace(day=1) + datetime.timedelta(days=32)
        return first_day_next_month.replace(day=1)

    # End of next month
    def get_end_of_next_month():
        today = datetime.date.today()
        # Calculate the first day of the next month
        first_day_next_month = today.replace(day=1) + datetime.timedelta(days=32)
        # Get the last day of next month
        last_day_next_month = first_day_next_month.replace(day=1) + datetime.timedelta(days=32)
        # Go back to the last day of the previous month
        last_day_next_month = last_day_next_month.replace(day=1) - datetime.timedelta(days=1)
        return last_day_next_month

    def get_end_of_this_month():
        today = datetime.date.today()
        # Calculate the first day of the next month
        first_day_this_month = today.replace(day=1) 
        # Get the last day of next month
        last_day_this_month = first_day_this_month.replace(day=1) + datetime.timedelta(days=32)
        # Go back to the last day of the previous month
        last_day_this_month = last_day_this_month.replace(day=1) - datetime.timedelta(days=1)
        return last_day_this_month
    
    def get_first_of_last_month():
        today = datetime.date.today()
        # Calculate the first day of the next month
        first_day_last_month = today.replace(day=1) - datetime.timedelta(days=27)
        # Get the last day of next month
        first_day_last_month = first_day_last_month.replace(day=1) 
        return first_day_last_month
    
    def default_item_code():
        # Retrieve the ItemCode instance with the code "C01"
        return ItemCode.objects.get(slug="C01")
    
    company = models.ForeignKey(Company, verbose_name="取引先", on_delete=models.PROTECT)
    invoice_date = models.DateField(verbose_name="請求日", default=get_start_of_this_month, blank=True, null=True)
    payment_due = models.DateField(verbose_name="支払期日", default=get_end_of_this_month, blank=True, null=True)
    action_date = models.DateField(verbose_name="該当月", default=get_first_of_last_month, blank=True, null=True)
    action_name = models.CharField(verbose_name="項目", default="業務委託費", max_length=150, blank=True, null=True)
    action_note = models.CharField(verbose_name="備考", max_length=150, default='', blank=True, null=True)
    item_code = models.ForeignKey(ItemCode, verbose_name="項目キー", default=default_item_code, on_delete=models.PROTECT)
    invoice_bt = models.IntegerField(verbose_name="請求額", default=0)
    invoice_tax = models.IntegerField(verbose_name="税金", default=0)
    invoice_at = models.IntegerField(verbose_name="税込請求額", default=0)
    flag = models.BooleanField(verbose_name="請求書作成済",default=False)
    slug = models.CharField(verbose_name="請求書キー", max_length=150, blank=True, null=True)

   
    def __str__(self):
        mmdate = self.invoice_date.strftime("%Y%m")
        return f"{self.company}-{mmdate}"
    
    

class InvoiceCode(models.Model):
    account_item_slug = models.CharField(verbose_name="請求書キー", max_length=30, unique=True)
    account_item = models.ForeignKey(AccountItem, verbose_name="取引キー", on_delete=models.PROTECT)
    payment_due = models.DateField(verbose_name="支払期日", blank=True, null=True)
    invoice_bt_ttl_0 = models.IntegerField(verbose_name="請求額", default=0)
    invoice_bt_ttl = models.IntegerField(verbose_name="請求額", default=0)
    invoice_tax_ttl = models.IntegerField(verbose_name="税金", default=0)
    invoice_at_ttl = models.IntegerField(verbose_name="税込請求額", default=0)
    invoice_bt_gttl = models.IntegerField(verbose_name="税込請求額", default=0)
    invoice_at_gttl = models.IntegerField(verbose_name="税込請求額", default=0)
    invoice_tax_flag = models.BooleanField(verbose_name="有税無税", default=True)
    invoice_slug = models.CharField(verbose_name="請求書番号", max_length=30, blank=True, null=True)
    
    def __str__(self):
        mmdate = self.account_item.invoice_date.strftime('%Y%m')
        return f"{self.account_item}-{mmdate}"
    
class CsvDate(models.Model):
    csvdate = models.DateField(default=date(2024, 9, 1))
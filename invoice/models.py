from django.db import models
from django.conf import settings
import datetime
import calendar
from datetime import date


class Organization(models.Model):
    """A tenant of the SaaS product (one SME customer). Also holds the
    tenant's own issuer details (bank account, address, etc.) used when
    generating invoices, replacing the old hardcoded "my company" row."""
    name = models.CharField(verbose_name="組織名", max_length=100)
    slug = models.SlugField(verbose_name="組織キー", max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    bank_account = models.ForeignKey("BankAccount", verbose_name="銀行名", on_delete=models.SET_NULL, null=True, blank=True)
    register_no = models.CharField(verbose_name="登録番号", max_length=20, blank=True, null=True)
    post_code = models.CharField(verbose_name="〒", max_length=20, blank=True, null=True)
    address1 = models.CharField(verbose_name="住所１", max_length=150, default="", blank=True)
    address2 = models.CharField(verbose_name="住所２", max_length=150, default="", blank=True, null=True)
    tel = models.CharField(verbose_name="電話", max_length=50, default="", blank=True, null=True)
    email = models.EmailField(verbose_name="Email", max_length=100, default="", blank=True, null=True)

    def __str__(self):
        return self.name


class OrganizationMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        STAFF = "staff", "Staff"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STAFF)

    class Meta:
        unique_together = ("user", "organization")

    def __str__(self):
        return f"{self.user} @ {self.organization} ({self.role})"


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
class Client(models.Model):
    """A company that this organization (tenant) issues invoices to."""
    organization = models.ForeignKey(Organization, verbose_name="組織", on_delete=models.CASCADE, related_name="clients")
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
    organization = models.ForeignKey(Organization, verbose_name="組織", on_delete=models.CASCADE, related_name="item_codes")
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
    
    organization = models.ForeignKey(Organization, verbose_name="組織", on_delete=models.CASCADE, related_name="account_items")
    company = models.ForeignKey(Client, verbose_name="取引先", on_delete=models.PROTECT)
    invoice_date = models.DateField(verbose_name="請求日", default=get_start_of_this_month, blank=True, null=True)
    payment_due = models.DateField(verbose_name="支払期日", default=get_end_of_this_month, blank=True, null=True)
    action_date = models.DateField(verbose_name="該当月", default=get_first_of_last_month, blank=True, null=True)
    action_name = models.CharField(verbose_name="項目", default="業務委託費", max_length=150, blank=True, null=True)
    action_note = models.CharField(verbose_name="備考", max_length=150, default='', blank=True, null=True)
    item_code = models.ForeignKey(ItemCode, verbose_name="項目キー", default=default_item_code, on_delete=models.PROTECT)
    tax_rate = models.PositiveSmallIntegerField(verbose_name="税率(%)", default=10)
    invoice_bt = models.IntegerField(verbose_name="請求額", default=0)
    invoice_tax = models.IntegerField(verbose_name="税金", default=0)
    invoice_at = models.IntegerField(verbose_name="税込請求額", default=0)
    flag = models.BooleanField(verbose_name="請求書作成済",default=False)
    slug = models.CharField(verbose_name="請求書キー", max_length=150, blank=True, null=True)
    # Logical delete only: once an invoice has been sent, a line item can no
    # longer be physically removed (that would silently change a document
    # the client already has). Setting this instead keeps the row for audit
    # purposes while excluding it from totals, the PDF, and CSV exports.
    deleted_at = models.DateTimeField(verbose_name="論理削除日時", blank=True, null=True)

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
    sent_at = models.DateTimeField(verbose_name="送信日時", blank=True, null=True)
    # Flips to True the first time a line item under this invoice is
    # added/edited/voided after sent_at was set - i.e. the client already has
    # a copy, so this is now a correction to an issued document (修正版), not
    # a still-in-progress draft. Never reset back to False.
    amended = models.BooleanField(verbose_name="修正版", default=False)
    # Consumption-tax rounding method used for this invoice's totals. Blank
    # means "not frozen yet": an unsent invoice follows calc.DEFAULT_TAX_ROUNDING,
    # a sent one is treated as 切捨て (what every invoice used before this field
    # existed). It is stamped when the invoice is sent (or un-sent) and never
    # changed afterwards, so a later change of the default cannot alter an
    # invoice the client already has.
    TAX_ROUNDING_CHOICES = [("floor", "切捨て"), ("round", "四捨五入")]
    tax_rounding = models.CharField(verbose_name="端数処理", max_length=10, choices=TAX_ROUNDING_CHOICES, blank=True, default="")

    def __str__(self):
        mmdate = self.account_item.invoice_date.strftime('%Y%m')
        return f"{self.account_item}-{mmdate}"
    
class CsvDate(models.Model):
    csvdate = models.DateField(default=date(2024, 9, 1))
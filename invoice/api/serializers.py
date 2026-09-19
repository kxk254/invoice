from rest_framework import serializers

from ..models import AccountItem, ChangeLog, Client, InvoiceCode, ItemCode


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        exclude = ["organization"]


class ItemCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemCode
        exclude = ["organization"]


class AccountItemSerializer(serializers.ModelSerializer):
    # Logical-delete marker: never client-writable, only ever set by the
    # soft-delete path in AccountItemViewSet.perform_destroy.
    deleted_at = serializers.DateTimeField(read_only=True)
    # Tells the frontend whether this row's invoice has already been sent -
    # if so, its invoice_date input should be locked, since the server will
    # reject any attempt to change it (see AccountItemViewSet.perform_update).
    invoice_issued = serializers.SerializerMethodField()

    class Meta:
        model = AccountItem
        exclude = ["organization"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        organization = getattr(request, "organization", None) if request else None
        if organization is not None:
            self.fields["company"].queryset = Client.objects.filter(organization=organization)
            self.fields["item_code"].queryset = ItemCode.objects.filter(organization=organization)

    def get_invoice_issued(self, obj):
        sent_slugs = self.context.get("sent_slugs")
        if sent_slugs is None:
            from .. import calc
            invoice_code = calc.find_invoice_code_for_item(obj.organization, obj.company, obj.invoice_date)
            return bool(invoice_code and invoice_code.sent_at)
        if not obj.company_id or not obj.invoice_date:
            return False
        candidate_slug = f"{obj.company.slug}-{obj.invoice_date.strftime('%Y%m')}"
        return candidate_slug in sent_slugs


class InvoiceCodeSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="account_item.company.name", read_only=True)
    client_id = serializers.IntegerField(source="account_item.company_id", read_only=True)
    items = AccountItemSerializer(source="items_for_month", many=True, read_only=True)

    class Meta:
        model = InvoiceCode
        fields = [
            "id", "account_item_slug", "invoice_slug", "client_id", "client_name",
            "payment_due", "invoice_bt_ttl_0", "invoice_bt_ttl", "invoice_tax_ttl",
            "invoice_at_ttl", "invoice_bt_gttl", "invoice_at_gttl", "invoice_tax_flag",
            "sent_at", "amended", "tax_rounding", "items",
        ]


class ChangeLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChangeLog
        fields = [
            "id", "object_id", "action", "source", "changes", "client_name",
            "invoice_slug", "after_sent", "username", "created_at",
        ]

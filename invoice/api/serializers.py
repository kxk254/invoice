from rest_framework import serializers

from ..models import AccountItem, Client, InvoiceCode, ItemCode


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        exclude = ["organization"]


class ItemCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemCode
        exclude = ["organization"]


class AccountItemSerializer(serializers.ModelSerializer):
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
            "sent_at", "items",
        ]

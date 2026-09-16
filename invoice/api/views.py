from django.db.models import Q
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import calc
from ..calc import strip_date
from ..models import AccountItem, Client, InvoiceCode, ItemCode
from .permissions import OrganizationScopedMixin, get_active_organization
from .serializers import AccountItemSerializer, ClientSerializer, InvoiceCodeSerializer, ItemCodeSerializer


class MeView(APIView):
    def get(self, request):
        organization = get_active_organization(request.user)
        return Response({
            "username": request.user.username,
            "organization": {"id": organization.id, "name": organization.name, "slug": organization.slug},
        })


class ClientViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer


class ItemCodeViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    queryset = ItemCode.objects.all()
    serializer_class = ItemCodeSerializer


class AccountItemViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    queryset = AccountItem.objects.all()
    serializer_class = AccountItemSerializer

    def get_queryset(self):
        qs = super().get_queryset().order_by("-invoice_date", "item_code__slug")
        company = self.request.query_params.get("company")
        month = self.request.query_params.get("month")
        if company:
            qs = qs.filter(company_id=company)
        if month:
            _, start_month, end_of_month = strip_date(month)
            qs = qs.filter(invoice_date__gte=start_month, invoice_date__lte=end_of_month)
        return qs

    @action(detail=False, methods=["get"], url_path="export-csv")
    def export_csv(self, request):
        start = request.query_params.get("start")
        end = request.query_params.get("end")
        if not start or not end:
            return Response({"detail": "start and end are required (YYYY-MM-DD)."}, status=status.HTTP_400_BAD_REQUEST)
        _, start_of_month, _ = strip_date(start)
        _, _, end_of_month = strip_date(end)
        qs = AccountItem.objects.filter(
            organization=request.organization,
            action_date__gte=start_of_month,
            action_date__lte=end_of_month,
        )
        st = start_of_month.replace("-", "")[:6]
        ed = end_of_month.replace("-", "")[:6]
        return calc.export_to_csv(qs, st, ed)


class InvoiceCodeViewSet(OrganizationScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = InvoiceCode.objects.all()
    serializer_class = InvoiceCodeSerializer
    organization_lookup = "account_item__organization"

    def get_queryset(self):
        qs = super().get_queryset().select_related("account_item", "account_item__company").order_by("-payment_due")
        company = self.request.query_params.get("company")
        month = self.request.query_params.get("month")
        if company:
            qs = qs.filter(account_item__company_id=company)
        if month:
            _, start_month, end_of_month = strip_date(month)
            qs = qs.filter(account_item__invoice_date__gte=start_month, account_item__invoice_date__lte=end_of_month)
        return qs

    def list(self, request, *args, **kwargs):
        organization = request.organization
        # Recompute invoice codes/totals from current line items before
        # listing, mirroring what the old Django home page did on every
        # visit (it ran this pipeline unconditionally before rendering).
        calc.set_invoice_code(organization)
        calc.invoice_code_slug_save(organization)
        calc.total_amount_calc(organization)

        invoices = list(self.get_queryset())
        month = request.query_params.get("month")
        start_month = end_of_month = None
        if month:
            _, start_month, end_of_month = strip_date(month)
        for invoice in invoices:
            items_qs = AccountItem.objects.filter(organization=organization, company=invoice.account_item.company)
            if start_month:
                items_qs = items_qs.filter(invoice_date__gte=start_month, invoice_date__lte=end_of_month)
            invoice.items_for_month = items_qs.order_by("item_code", "-invoice_date")

        serializer = self.get_serializer(invoices, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="tax-calc")
    def tax_calc(self, request):
        company = request.data.get("company", "")
        month = request.data.get("month")
        if not month:
            return Response({"detail": "month is required (YYYY-MM-DD)."}, status=status.HTTP_400_BAD_REQUEST)
        calc.tax_calc_def(request.organization, company, month)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _resolve_ref(queryset, value):
    """Resolve an account-item's `company`/`item_code` reference, which can
    be given as a numeric id or as a short_name/slug string, to a pk."""
    if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
        obj = queryset.filter(pk=int(value)).first()
    else:
        obj = queryset.filter(Q(short_name=value) | Q(slug=value) | Q(name=value)).first()
    if obj is None:
        raise ValueError(f"no match for {value!r}")
    return obj.pk


class ImportView(APIView):
    """
    Imports AccountItem (line item) rows into the requesting user's own
    organization only. Never touches other organizations' data and never
    deletes anything — unlike the old Django `restore_view`, which flushed
    the entire database before reloading.

    Body: {"account_items": [{"company": "<id or short_name/slug>",
    "item_code": "<id or short_name/slug>", "invoice_date": "YYYY-MM-DD",
    "payment_due": "YYYY-MM-DD", "action_date": "YYYY-MM-DD", "action_name":
    str, "action_note": str, "invoice_bt": int, "invoice_tax": int,
    "invoice_at": int}, ...]}
    """

    def post(self, request):
        organization = get_active_organization(request.user)
        rows = request.data.get("account_items")
        if not isinstance(rows, list):
            return Response({"detail": "account_items must be a list."}, status=status.HTTP_400_BAD_REQUEST)

        clients = Client.objects.filter(organization=organization)
        item_codes = ItemCode.objects.filter(organization=organization)

        created = 0
        errors = []
        for index, row in enumerate(rows):
            try:
                row = dict(row)
                row["company"] = _resolve_ref(clients, row.get("company"))
                row["item_code"] = _resolve_ref(item_codes, row.get("item_code"))
            except (ValueError, TypeError) as e:
                errors.append({"index": index, "detail": str(e)})
                continue

            serializer = AccountItemSerializer(data=row, context={"request": request})
            if serializer.is_valid():
                serializer.save(organization=organization)
                created += 1
            else:
                errors.append({"index": index, "detail": serializer.errors})

        return Response({"created": created, "errors": errors}, status=status.HTTP_200_OK)


class InvoicePdfView(APIView):
    def get(self, request, slug):
        organization = get_active_organization(request.user)
        try:
            pdf_bytes, encoded_filename = calc.render_invoice_pdf(organization, slug)
        except InvoiceCode.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        disposition = "attachment" if request.query_params.get("download") else "inline"
        response["Content-Disposition"] = f'{disposition}; filename="{encoded_filename}.pdf"'
        return response

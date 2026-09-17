from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import calc, restore_logic
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
            # "month" here means 該当月 (the month the line item's work/expense
            # relates to), matching export_csv below and how line items are
            # actually entered/edited on a monthly basis — not 請求日
            # (invoice_date), which by default is a month ahead of action_date
            # and would silently show the wrong month's rows.
            _, start_month, end_of_month = strip_date(month)
            qs = qs.filter(action_date__gte=start_month, action_date__lte=end_of_month)
        return qs

    @action(detail=False, methods=["post"], url_path="bulk-update")
    def bulk_update(self, request):
        """
        Saves a month's worth of edited line items in one request instead of
        one PATCH per row. Body: {"items": [{"id": <id>, ...fields}, ...]}.
        All rows are validated before anything is written, so a mistake in
        one row never leaves the others half-saved.
        """
        rows = request.data.get("items")
        if not isinstance(rows, list):
            return Response({"detail": "items must be a list."}, status=status.HTTP_400_BAD_REQUEST)

        qs = self.get_queryset()
        to_save = []
        errors = []
        for index, row in enumerate(rows):
            item_id = row.get("id")
            instance = qs.filter(pk=item_id).first()
            if instance is None:
                errors.append({"index": index, "id": item_id, "detail": "not found"})
                continue
            serializer = AccountItemSerializer(instance, data=row, partial=True, context={"request": request})
            if not serializer.is_valid():
                errors.append({"index": index, "id": item_id, "detail": serializer.errors})
                continue
            to_save.append(serializer)

        if errors:
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            for serializer in to_save:
                serializer.save()

        return Response({"updated": len(to_save)})

    @action(detail=False, methods=["post"], url_path="diff-import")
    def diff_import(self, request):
        """
        Read-only sanity check for a backup/export file: for each row, look
        up the existing AccountItem by `slug` and report whether it's
        missing from the database, differs from it, or matches exactly.
        Never creates, updates, or deletes anything. Accepts the same
        shapes as ImportView (flat objects, or dumpdata-style
        {"fields": {...}} rows).
        """
        rows = request.data.get("account_items")
        if not isinstance(rows, list):
            return Response({"detail": "account_items must be a list."}, status=status.HTTP_400_BAD_REQUEST)

        clients = Client.objects.filter(organization=request.organization)
        item_codes = ItemCode.objects.filter(organization=request.organization)
        qs = self.get_queryset()

        compare_fields = [
            "invoice_date", "payment_due", "action_date", "action_name",
            "action_note", "invoice_bt", "invoice_tax", "invoice_at",
            "tax_rate", "flag",
        ]

        missing = []
        differing = []
        errors = []
        matched = 0

        for index, row in enumerate(rows):
            row = dict(row)
            if isinstance(row.get("fields"), dict):
                row = dict(row["fields"])

            slug = row.get("slug")
            if not slug:
                errors.append({"index": index, "detail": "row has no slug to match on"})
                continue

            instance = qs.filter(slug=slug).first()
            if instance is None:
                missing.append({"index": index, "slug": slug})
                continue

            diffs = {}
            for field in compare_fields:
                if field not in row:
                    continue
                file_value = row[field]
                db_value = getattr(instance, field)
                if hasattr(db_value, "isoformat"):
                    db_value = db_value.isoformat()
                if file_value != db_value:
                    diffs[field] = {"file": file_value, "db": db_value}

            for ref_field, ref_queryset in (("company", clients), ("item_code", item_codes)):
                if ref_field not in row:
                    continue
                try:
                    resolved = _resolve_ref(ref_queryset, row[ref_field])
                except (ValueError, TypeError):
                    resolved = None
                db_value = getattr(instance, f"{ref_field}_id")
                if resolved != db_value:
                    diffs[ref_field] = {"file": row[ref_field], "db": db_value}

            if diffs:
                differing.append({"index": index, "slug": slug, "diffs": diffs})
            else:
                matched += 1

        return Response({
            "total": len(rows),
            "matched": matched,
            "missing": missing,
            "differing": differing,
            "errors": errors,
        })

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

    @action(detail=True, methods=["post"], url_path="mark-sent")
    def mark_sent(self, request, pk=None):
        invoice = self.get_object()
        invoice.sent_at = timezone.now()
        invoice.save(update_fields=["sent_at"])
        return Response(self.get_serializer(invoice).data)

    @action(detail=True, methods=["post"], url_path="unmark-sent")
    def unmark_sent(self, request, pk=None):
        invoice = self.get_object()
        invoice.sent_at = None
        invoice.save(update_fields=["sent_at"])
        return Response(self.get_serializer(invoice).data)


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
    organization only. Never touches other organizations' data — unlike the
    old Django `restore_view`, which flushed the entire database before
    reloading.

    Body: {"account_items": [{"company": "<id or short_name/slug>",
    "item_code": "<id or short_name/slug>", "invoice_date": "YYYY-MM-DD",
    "payment_due": "YYYY-MM-DD", "action_date": "YYYY-MM-DD", "action_name":
    str, "action_note": str, "invoice_bt": int, "invoice_tax": int,
    "invoice_at": int}, ...], "mode": "create" | "replace"}

    mode="create" (default) only ever adds rows, same as before.

    mode="replace" groups the incoming rows by (company, invoice_date's
    year-month) — the same key that ties line items to one InvoiceCode — and
    for each such period swaps out its existing line items for the new ones.
    The InvoiceCode row for that period (and therefore its already-issued
    invoice number, which is derived from the InvoiceCode's own id, not from
    the line items) is never deleted or recreated, only repointed at a
    surviving line item. A bad row anywhere aborts the whole replace before
    anything is written, so a period's invoiced items are never deleted
    without a full replacement landing in the same request.

    Rows that exactly match an already-existing line item (same company,
    item code, dates, description, and amount) are skipped rather than
    inserted again, in "create" mode - re-uploading the same export, or a
    request that silently retried and actually landed twice (the cause of
    a real incident: see the "data triplication" fix commit), used to
    double every affected period's total instead of being a no-op. A row is
    also skipped if it duplicates an earlier row within the same request.
    Skipped rows are reported under "skipped_duplicates", never silently
    dropped.
    """

    # What counts as "the same line item" for duplicate detection. Deliberately
    # excludes invoice_tax/invoice_at (derived from invoice_bt + tax_rate) and
    # payment_due/flag/slug (bookkeeping, not part of what a human entered).
    DUPLICATE_FIELDS = ["company", "item_code", "invoice_date", "action_date", "action_name", "action_note", "invoice_bt", "tax_rate"]

    def post(self, request):
        organization = get_active_organization(request.user)
        rows = request.data.get("account_items")
        mode = request.data.get("mode", "create")
        if mode not in ("create", "replace"):
            return Response({"detail": "mode must be 'create' or 'replace'."}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(rows, list):
            return Response({"detail": "account_items must be a list."}, status=status.HTTP_400_BAD_REQUEST)

        clients = Client.objects.filter(organization=organization)
        item_codes = ItemCode.objects.filter(organization=organization)

        existing_keys = set()
        if mode == "create":
            existing_keys = set(
                AccountItem.objects.filter(organization=organization).values_list(*self.DUPLICATE_FIELDS)
            )
        seen_keys = set()

        prepared = []
        errors = []
        duplicates = []
        for index, row in enumerate(rows):
            try:
                row = dict(row)
                # Also accept Django `dumpdata`-style fixture rows
                # ({"model": "invoice.accountitem", "pk": ..., "fields":
                # {...}}), since that's what a database backup/export looks
                # like and people restoring old data reach for it naturally.
                if isinstance(row.get("fields"), dict):
                    row = dict(row["fields"])
                row["company"] = _resolve_ref(clients, row.get("company"))
                row["item_code"] = _resolve_ref(item_codes, row.get("item_code"))
            except (ValueError, TypeError) as e:
                errors.append({"index": index, "detail": str(e)})
                continue

            # Rows imported against the 無税 (NT) item code without an
            # explicit tax_rate should land as tax-exempt, not the model's
            # 10% default.
            if not row.get("tax_rate"):
                item_code = item_codes.filter(pk=row["item_code"]).first()
                if item_code is not None and item_code.slug == "NT":
                    row["tax_rate"] = 0

            serializer = AccountItemSerializer(data=row, context={"request": request})
            if not serializer.is_valid():
                errors.append({"index": index, "detail": serializer.errors})
                continue

            if mode == "replace" and serializer.validated_data.get("invoice_date") is None:
                errors.append({"index": index, "detail": "invoice_date is required to replace a period."})
                continue

            # company/item_code come from `row` (still plain ids from
            # _resolve_ref above), not validated_data - DRF's
            # PrimaryKeyRelatedField turns those into model instances there,
            # which would never equal the plain ids `existing_keys` holds.
            key = tuple(
                row[f] if f in ("company", "item_code") else serializer.validated_data.get(f)
                for f in self.DUPLICATE_FIELDS
            )
            if key in existing_keys or key in seen_keys:
                duplicates.append({"index": index, "slug": row.get("slug"), "detail": "matches an existing line item; skipped"})
                continue
            seen_keys.add(key)

            prepared.append((row["company"], serializer))

        if errors and mode == "replace":
            # Still a normal 200: this is a fully-formed, structured
            # response the frontend already knows how to render (same shape
            # as a successful call, just with created=0), not an HTTP-level
            # failure. Returning 400 here made apiMutate() throw and show a
            # raw, unparsed error blob instead of the usual error list.
            return Response({"created": 0, "replaced_periods": [], "errors": errors, "skipped_duplicates": duplicates})

        created = 0
        replaced_periods = []
        with transaction.atomic():
            if mode == "replace":
                periods = {}
                for company_id, serializer in prepared:
                    month_start = serializer.validated_data["invoice_date"].replace(day=1)
                    periods.setdefault((company_id, month_start), []).append(serializer)

                for (company_id, month_start), serializers in periods.items():
                    _, _, month_end = strip_date(month_start.isoformat())
                    company = clients.get(pk=company_id)
                    generated_id = f"{company.slug}-{month_start.strftime('%Y%m')}"

                    old_items = list(AccountItem.objects.filter(
                        organization=organization, company_id=company_id,
                        invoice_date__gte=month_start, invoice_date__lte=month_end,
                    ))

                    new_items = [s.save(organization=organization) for s in serializers]
                    created += len(new_items)

                    # Repoint the existing InvoiceCode (if any) at a
                    # surviving line item before deleting the old ones —
                    # its account_item FK is PROTECTed, and this is what
                    # keeps the invoice number (derived from the
                    # InvoiceCode's own id) unchanged across the replace.
                    invoice_code = InvoiceCode.objects.filter(account_item_slug=generated_id).first()
                    if invoice_code is not None:
                        invoice_code.account_item = new_items[0]
                        invoice_code.save(update_fields=["account_item"])

                    removed = len(old_items)
                    for item in old_items:
                        item.delete()

                    replaced_periods.append({
                        "company": company_id,
                        "month": month_start.isoformat(),
                        "removed": removed,
                        "added": len(new_items),
                        "invoice_slug": invoice_code.invoice_slug if invoice_code else None,
                    })
            else:
                for _, serializer in prepared:
                    serializer.save(organization=organization)
                    created += 1

            # Re-run the same pipeline the invoice list already runs on
            # every load, so newly-inserted rows are flagged/slugged and
            # totals reflect the replacement immediately.
            calc.set_invoice_code(organization)
            calc.invoice_code_slug_save(organization)
            calc.total_amount_calc(organization)

        return Response(
            {"created": created, "replaced_periods": replaced_periods, "errors": errors, "skipped_duplicates": duplicates},
            status=status.HTTP_200_OK,
        )


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


def _extract_backup_rows(request):
    """Accepts either a bare dumpdata-style array (what `manage.py dumpdata`
    and the NAS backup actually produce) or that array wrapped as
    {"backup": [...]}, matching how ImportView accepts either shape."""
    body = request.data
    rows = body if isinstance(body, list) else body.get("backup")
    if not isinstance(rows, list):
        return None
    return rows


class RestorePreviewView(APIView):
    """
    Read-only: never creates, updates, or deletes anything. Body: a
    `manage.py dumpdata` JSON backup (bare array, or {"backup": [...]}).
    Reports exactly what a RestoreApplyView call with the same body would
    create/update/delete for the caller's own organization, and any
    conflicts that would make it refuse to run at all.
    """

    def post(self, request):
        organization = get_active_organization(request.user)
        rows = _extract_backup_rows(request)
        if rows is None:
            return Response({"detail": "Body must be a dumpdata JSON array, or {\"backup\": [...]}."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            plan = restore_logic.build_restore_plan(organization, rows)
        except restore_logic.RestoreError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"diff": plan.diff(), "conflicts": plan.conflicts()})


class RestoreApplyView(APIView):
    """
    Destructive: restores the caller's own organization to match the given
    backup exactly - existing-and-still-present rows are overwritten with
    the backup's values (at their original ids, so invoice numbers are
    unchanged), rows present in the backup but missing live are recreated,
    and rows that exist live but aren't in the backup are deleted. Other
    organizations are never read or written. Requires `confirm: true` in
    the body as a deliberate extra step beyond just POSTing a file, and
    refuses (with no changes at all) if any row would collide with another
    organization's data.

    Body: a `manage.py dumpdata` JSON backup (bare array, or
    {"backup": [...], "confirm": true}).
    """

    def post(self, request):
        organization = get_active_organization(request.user)
        rows = _extract_backup_rows(request)
        if rows is None:
            return Response({"detail": "Body must be a dumpdata JSON array, or {\"backup\": [...]}."}, status=status.HTTP_400_BAD_REQUEST)
        if not (isinstance(request.data, dict) and request.data.get("confirm") is True):
            return Response({"detail": "Set confirm: true to apply a restore."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            plan = restore_logic.build_restore_plan(organization, rows)
            result = plan.apply()
        except restore_logic.RestoreError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)

        return Response(result)

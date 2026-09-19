import logging
import math, csv
from collections import Counter
from . import audit
from .models import AccountItem, ChangeLog, InvoiceCode, Client
from django.db.models import Sum
from datetime import datetime, timedelta
from django.db import IntegrityError
from django.db import transaction
from django.http import HttpResponse
import weasyprint
from weasyprint import CSS, HTML
from django.template.loader import render_to_string
from urllib.parse import quote, unquote
from django.shortcuts import render
import io
import base64
from django.conf import settings
from pathlib import Path

logger = logging.getLogger(__name__)


'''
Set Invoice ID for invoice generation
'''
def set_invoice_code(organization):

    accounts = AccountItem.objects.filter(flag=False, organization=organization)
    if accounts.exists():
        for account in accounts:
            report_date_formatted = account.invoice_date.strftime("%Y%m") if account.invoice_date else "000000"
            generated_id = f"{account.company.slug}-{report_date_formatted}"

             # Start a transaction block to ensure atomicity
            with transaction.atomic():
                account.slug = generated_id
                account.flag = True
                account.save()

                # Check if the generated 契約書ID already exists in 請求書ID管理
                if InvoiceCode.objects.filter(account_item_slug=generated_id).exists():
                    continue  # Only skip this account; other unflagged accounts still need processing

                try:
                    InvoiceCode.objects.create(
                        account_item_slug=generated_id,
                        account_item=account,
                        payment_due=account.payment_due,
                        invoice_bt_ttl=0,
                        invoice_tax_ttl=0,
                        invoice_at_ttl=0,
                    )
                except IntegrityError:
                    logger.warning("Skipping InvoiceCode creation for %s: already exists.", generated_id)


"""

"""
def invoice_code_slug_save(organization):
    """Override save method to delete old slugs and reassign new ones."""
    qs = InvoiceCode.objects.filter(account_item__organization=organization)
    for q in qs:
        if q.account_item.invoice_date:
            mmdate = q.account_item.invoice_date.strftime('%Y%m')
        else:
            mmdate = "000000"
        formatted_number = f"{q.id:07d}" 
        invoice_slug = f"{q.account_item.company.slug}-{mmdate}-{formatted_number}"
        q.invoice_slug = invoice_slug
        q.save()

"""
Calculate Total Amount use for InvoiceCode
"""
def total_amount_calc(organization):
    revenues = AccountItem.objects.filter(organization=organization)
    # all_invoices = InvoiceId.objects.filter(revenue_at_ttl=0)
    all_invoices = InvoiceCode.objects.filter(account_item__organization=organization)

    for invoice in all_invoices:

        # Logically-deleted rows (voided after the invoice was sent) stay in
        # the database for audit purposes but must never count toward totals.
        sort_revenues = revenues.filter(slug=invoice.account_item_slug, deleted_at__isnull=True)

        """COMPLY WITH LAWS"""
        # Japan's qualified-invoice rules require consumption tax to be
        # rounded down exactly once per tax rate per invoice (on the summed
        # base for that rate), not once per line item, so bases are grouped
        # by rate first and tax is computed on each group's sum.
        rate_bases = {}
        for sr in sort_revenues:
            rate_bases[sr.tax_rate] = rate_bases.get(sr.tax_rate, 0) + sr.invoice_bt

        before_zero_tax = rate_bases.pop(0, 0)
        before_tax = sum(rate_bases.values())
        method = invoice_tax_method(invoice)
        tax_amt = sum(tax_on_exclusive(base, rate, method) for rate, base in rate_bases.items())

        total_aft_tax = before_tax + tax_amt
        grand_total = before_zero_tax + total_aft_tax


        invoice.invoice_bt_ttl_0 = before_zero_tax
        invoice.invoice_bt_ttl = before_tax
        invoice.invoice_at_ttl = total_aft_tax
        invoice.invoice_tax_ttl = tax_amt
        invoice.invoice_bt_gttl = before_zero_tax + before_tax
        invoice.invoice_at_gttl = grand_total
        invoice.save()


"""
Align date to start from 1st day of the month
"""
def strip_date(month):
    start_date = datetime.strptime(month, '%Y-%m-%d')
    # start_date = datetime.strptime(month, '%B %d, %Y')
    start_of_month = start_date.strftime('%Y-%m-01')
    end_of_month = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    end_of_month = end_of_month.strftime('%Y-%m-%d')
    return start_date, start_of_month, end_of_month

'''
PREPROCESS the data to take off comma from 000s format
'''
def preprocess_post_data(post_data):
    """
    Clean numeric fields in POST data by removing commas and converting to integers.
    """
    cleaned_data = post_data.copy()  # Make a mutable copy of the POST data

    number_of_forms = int(post_data.get('form-INITIAL_FORMS', 0))
    for i in range(0, number_of_forms+1):
        invoice_bt = f"form-{i}-invoice_bt"
        invoice_at = f"form-{i}-invoice_at"
        invoice_tax = f"form-{i}-invoice_tax"

        # Clean invoice_bt field
        if invoice_bt in cleaned_data:
            invoice_bt_value = cleaned_data[invoice_bt]
            if invoice_bt_value and isinstance(invoice_bt_value, str):
                cleaned_data[invoice_bt] = invoice_bt_value.replace(',', '')

        # Clean invoice_at field
        if invoice_at in cleaned_data:
            invoice_at_value = cleaned_data[invoice_at]
            if invoice_at_value and isinstance(invoice_at_value, str):
                cleaned_data[invoice_at] = invoice_at_value.replace(',', '')

        # Clean tax field
        if invoice_tax in cleaned_data:
            tax_value = cleaned_data[invoice_tax]
            if tax_value and isinstance(tax_value, str):
                cleaned_data[invoice_tax] = tax_value.replace(',', '')

    return cleaned_data

"""
Rounding basis: fractions of a yen are handled once per tax rate per invoice
(消令70の10, 基通1-8-15); the method itself is free to choose.
https://www.nta.go.jp/taxes/shiraberu/zeimokubetsu/shohi/keigenzeiritsu/pdf/qa/57.pdf

Consumption tax on a (possibly negative) amount, in exact integer math.

Fractions are dropped from the magnitude, so a credit/discount line mirrors
the invoice it offsets (-1005 @10% -> -100, exactly the negative of +1005 ->
100) instead of floor() pushing negatives one yen further from zero.
"""
def _sign(n):
    return -1 if n < 0 else 1


# Rounding for NEW invoices. Sent invoices keep the method stamped on them.
DEFAULT_TAX_ROUNDING = "round"


def invoice_tax_method(invoice):
    if invoice.tax_rounding:
        return invoice.tax_rounding
    # Never stamped: an already-sent invoice predates the setting (all of
    # those were 切捨て); a draft follows the current default.
    return "floor" if invoice.sent_at else DEFAULT_TAX_ROUNDING


def tax_on_exclusive(amount_bt, rate, method="floor"):
    """method "floor" drops the fraction (per-line reference figures use this);
    "round" is 四捨五入, half away from zero so a credit mirrors its charge."""
    if method == "round":
        return _sign(amount_bt) * ((abs(amount_bt) * rate * 2 + 100) // 200)
    return _sign(amount_bt) * (abs(amount_bt) * rate // 100)


def tax_in_inclusive(amount_at, rate):
    return _sign(amount_at) * (abs(amount_at) * rate // (100 + rate))


"""
Tax-amount reconciliation for the line items of one month (optionally one
company). Logically-deleted rows are ignored. Per row:

  - only one of 税抜(invoice_bt) / 税込(invoice_at) filled -> "fill": derive
    the other and the tax. Nothing to decide.
  - both filled and consistent (either one implies the other) -> at most a
    tax-only sync.
  - both filled but neither implies the other -> "conflict": the caller has
    to choose which figure is right ("bt" or "at"); we never guess.

This only fixes the per-line figures. Invoice totals (total_amount_calc)
always re-derive tax once per rate from the summed 税抜 amounts, as the
qualified-invoice rules require.
"""
def plan_tax_calc(organization, selected_company="", selected_month="", date_field="invoice_date"):
    # The month is matched on 請求日 (Invoices page) or on 該当月 (Line items
    # page, whose month filter means action_date).
    if date_field not in ("invoice_date", "action_date"):
        date_field = "invoice_date"
    _, start_of_month, end_of_month = strip_date(selected_month)
    queryset = AccountItem.objects.filter(
        organization=organization,
        **{f"{date_field}__gte": start_of_month, f"{date_field}__lte": end_of_month},
        deleted_at__isnull=True,
    ).select_related("company", "item_code").order_by("company__name", "invoice_date", "id")
    if selected_company:
        queryset = queryset.filter(company=selected_company)

    invoices_by_period = invoice_codes_by_period(organization)

    fills, conflicts = [], []
    for item in queryset:
        bt, tax, at, rate = item.invoice_bt, item.invoice_tax, item.invoice_at, item.tax_rate
        if bt == 0 and at == 0:
            continue

        invoice = invoices_by_period.get((item.company_id, item.invoice_date.strftime("%Y-%m")))
        row = {
            "id": item.id,
            "company_name": item.company.name,
            "action_name": item.action_name or "",
            "item_code": item.item_code.name,
            "invoice_date": item.invoice_date.isoformat(),
            "tax_rate": rate,
            "invoice_sent": bool(invoice and invoice.sent_at),
            "invoice_id": invoice.pk if invoice else None,
            "current": {"bt": bt, "tax": tax, "at": at},
        }
        from_bt_tax = tax_on_exclusive(bt, rate)
        from_bt = {"bt": bt, "tax": from_bt_tax, "at": bt + from_bt_tax}
        from_at_tax = tax_in_inclusive(at, rate)
        from_at = {"bt": at - from_at_tax, "tax": from_at_tax, "at": at}

        if at == 0:
            fills.append({**row, "after": from_bt})
        elif bt == 0:
            fills.append({**row, "after": from_at})
        elif at == from_bt["at"] or bt == from_at["bt"]:
            after = from_bt if at == from_bt["at"] else from_at
            if tax != after["tax"]:
                fills.append({**row, "after": after})
        else:
            conflicts.append({**row, "if_bt": from_bt, "if_at": from_at})

    return fills, conflicts


"""
Applies plan_tax_calc(). Fills are always applied; a conflict is applied only
if `resolutions` (row id as str/int -> "bt" | "at") picks a side - anything
else is left untouched and counted as unresolved. Because the plan is
recomputed here, a stale resolution for a row that has since changed or been
fixed is simply ignored.

Changing a row on an invoice that was already sent is allowed (that is how
you correct one) but flags that invoice as amended (修正版), matching every
other post-send edit.
"""
def apply_tax_calc(organization, selected_company="", selected_month="", resolutions=None, user=None, date_field="invoice_date"):
    resolutions = {str(k): v for k, v in (resolutions or {}).items()}
    fills, conflicts = plan_tax_calc(organization, selected_company, selected_month, date_field)

    updates = {row["id"]: (row, row["after"]) for row in fills}
    unresolved = 0
    for row in conflicts:
        choice = resolutions.get(str(row["id"]))
        if choice == "bt":
            updates[row["id"]] = (row, row["if_bt"])
        elif choice == "at":
            updates[row["id"]] = (row, row["if_at"])
        else:
            unresolved += 1

    amended_ids = set()
    with transaction.atomic():
        for item in AccountItem.objects.filter(organization=organization, id__in=updates.keys()).select_related("company", "item_code"):
            row, after = updates[item.id]
            before_snapshot = audit.snapshot(item)
            item.invoice_bt, item.invoice_tax, item.invoice_at = after["bt"], after["tax"], after["at"]
            item.save(update_fields=["invoice_bt", "invoice_tax", "invoice_at"])
            audit.record_change(
                organization, item, ChangeLog.Action.UPDATE, before=before_snapshot, after=audit.snapshot(item),
                user=user, source="tax-calc", after_sent=bool(row["invoice_sent"]),
            )
            if row["invoice_sent"] and after != row["current"]:
                amended_ids.add(row["invoice_id"])
        if amended_ids:
            InvoiceCode.objects.filter(pk__in=amended_ids).update(amended=True)

    return {"applied": len(updates), "unresolved": unresolved, "amended_invoices": len(amended_ids)}


# Kept for the legacy Django template view: fills only, never resolves conflicts.
def tax_calc_def(organization, selected_company, selected_month):
    return apply_tax_calc(organization, selected_company, selected_month)


"""
{(company_id, "YYYY-MM"): InvoiceCode} for the organization, keyed by the client
and month of each invoice's own line item rather than by the slug text - so it
still finds the invoice if a client's slug was changed after it was issued.
`.sent_at` on the value tells whether that period is frozen.
"""
def invoice_codes_by_period(organization):
    found = {}
    for invoice in InvoiceCode.objects.filter(account_item__organization=organization).select_related("account_item"):
        anchor = invoice.account_item
        if anchor.invoice_date:
            found[(anchor.company_id, anchor.invoice_date.strftime("%Y-%m"))] = invoice
    return found


def _period_key(company_id, invoice_date):
    return (company_id, invoice_date.strftime("%Y-%m") if invoice_date else None)


"""
Editing a line's client or invoice date can move it to another invoice (an
invoice is one client + one month). Returns (errors, moves, old_invoice):

  errors       {field: message} - refused, nothing may be written:
               - the line's own invoice was already sent: it may not change
                 client or date (it would leave a document the client holds);
               - the destination invoice was already sent: nothing may be
                 moved into it either;
               - the line is the only one on its invoice: moving it would
                 leave an empty invoice behind.
  moves        the client/month changes, so the caller must call
               apply_line_move() after saving the edit.
  old_invoice  the invoice the line belonged to before the edit, if any.
"""
def plan_line_move(organization, instance, new_company, new_date, invoices_by_period=None):
    invoices = invoices_by_period if invoices_by_period is not None else invoice_codes_by_period(organization)
    old_key = _period_key(instance.company_id, instance.invoice_date)
    new_key = _period_key(new_company.pk if new_company else None, new_date)
    old_invoice = invoices.get(old_key)
    errors = {}

    if old_invoice and old_invoice.sent_at:
        if new_company is not None and new_company.pk != instance.company_id:
            errors["company"] = "This invoice has already been sent; its lines can no longer be moved to another client."
        if new_date != instance.invoice_date:
            errors["invoice_date"] = "This invoice has already been sent; its issue date can no longer be changed."
        return errors, False, old_invoice

    moves = old_key != new_key
    if moves:
        field = "company" if new_key[0] != old_key[0] else "invoice_date"
        new_invoice = invoices.get(new_key)
        if new_invoice and new_invoice.sent_at:
            errors[field] = "The invoice for that client and month has already been sent; lines can no longer be moved into it."
        elif old_invoice and old_invoice.account_item_id == instance.id:
            has_others = AccountItem.objects.filter(
                organization=organization, slug=old_invoice.account_item_slug, deleted_at__isnull=True
            ).exclude(pk=instance.pk).exists()
            if not has_others:
                errors[field] = f"This is the only line of invoice {old_invoice.account_item_slug}; it can't be moved to another period."
    return errors, moves, old_invoice


"""
Second half of a move planned by plan_line_move(), run after the edit is saved.
The line's invoice key is cleared so the next pass of set_invoice_code() files
it under its new client + month (creating that invoice if needed) - otherwise it
would stay counted in the old invoice's totals - and if the line was the old
invoice's anchor, the invoice is re-pointed at another of its lines.
"""
def apply_line_move(organization, item, old_invoice):
    if old_invoice and old_invoice.account_item_id == item.id:
        other = AccountItem.objects.filter(
            organization=organization, slug=old_invoice.account_item_slug, deleted_at__isnull=True
        ).exclude(pk=item.pk).order_by("pk").first()
        if other is not None:
            old_invoice.account_item = other
            old_invoice.save(update_fields=["account_item"])
    item.slug = None
    item.flag = False
    item.save(update_fields=["slug", "flag"])


"""
Looks up the InvoiceCode (if any) that a line item with this company +
invoice_date belongs to, using the same (company slug, year-month) grouping
key set_invoice_code() assigns - independent of whether that item's own
`slug` field has actually been refreshed yet (plain AccountItem create/
update/delete never re-runs that pipeline, only the Invoices page and
import/bulk actions do).
"""
def find_invoice_code_for_item(organization, company, invoice_date):
    if not company or not invoice_date:
        return None
    candidate_slug = f"{company.slug}-{invoice_date.strftime('%Y%m')}"
    return InvoiceCode.objects.filter(account_item_slug=candidate_slug, account_item__organization=organization).first()


"""
請求日の表記ゆれ補正 (invoice_date alignment)

Line items are grouped into one invoice by (company, invoice_date's
year-month) - see set_invoice_code(). Within that group every row should
carry the same invoice_date (the day the invoice was issued), but a manual
typo can leave one row on a different day of the same month (e.g. most of
a period's rows are 2025-09-01 but one was entered as 2025-09-15). This
finds those stragglers and proposes correcting them to whichever exact
date is most common in their group - the "obviously it should have been
this" value, not a guess. A group with no single most-common date (an
exact tie) is left alone and reported separately, since there's no safe
default to pick for the caller.
"""
def plan_invoice_date_alignment(organization, company="", month=""):
    # Voided (logically-deleted) lines are not part of the invoice any more:
    # they neither vote for a date nor get rewritten.
    qs = AccountItem.objects.filter(organization=organization, invoice_date__isnull=False, deleted_at__isnull=True).select_related("company")
    invoices_by_period = invoice_codes_by_period(organization)
    if month:
        _, start_of_month, end_of_month = strip_date(month)
        qs = qs.filter(invoice_date__gte=start_of_month, invoice_date__lte=end_of_month)
    if company:
        qs = qs.filter(company_id=company)

    groups = {}
    for item in qs:
        key = (item.company_id, item.invoice_date.strftime("%Y-%m"))
        groups.setdefault(key, []).append(item)

    changes = []
    skipped_ties = []
    for (company_id, period), items in groups.items():
        # Once an invoice has been sent, its issue date is frozen (see
        # AccountItemViewSet.perform_update) - realigning it automatically
        # here would silently rewrite a document the client already has.
        invoice_code = invoices_by_period.get((company_id, period))
        if invoice_code and invoice_code.sent_at:
            continue

        counts = Counter(item.invoice_date for item in items)
        if len(counts) == 1:
            continue  # every row in this invoice already agrees

        ranked = counts.most_common()
        top_count = ranked[0][1]
        tied = [d for d, c in ranked if c == top_count]
        if len(tied) > 1:
            skipped_ties.append({
                "company_id": company_id,
                "company_name": items[0].company.name,
                "period": period,
                "candidates": {d.isoformat(): c for d, c in ranked},
            })
            continue

        target = tied[0]
        for item in items:
            if item.invoice_date != target:
                changes.append({
                    "id": item.id,
                    "company_id": company_id,
                    "company_name": items[0].company.name,
                    "period": period,
                    "current": item.invoice_date.isoformat(),
                    "target": target.isoformat(),
                })

    return changes, skipped_ties


def apply_invoice_date_alignment(organization, company="", month=""):
    changes, skipped_ties = plan_invoice_date_alignment(organization, company, month)
    target_by_id = {c["id"]: c["target"] for c in changes}
    if target_by_id:
        with transaction.atomic():
            for item in AccountItem.objects.filter(organization=organization, id__in=target_by_id.keys()):
                item.invoice_date = datetime.strptime(target_by_id[item.id], "%Y-%m-%d").date()
                item.save(update_fields=["invoice_date"])
    return changes, skipped_ties


"""
メールのテナント情報、金額、合計金額の情報要素を作成
kwargs = {
    'slug': slug, 
    }
"""
def prepare_invoice_items(organization, slug, interactive=False):
    context = {'interactive': interactive}
    invoicecode = InvoiceCode.objects.get(account_item_slug=slug['slug'], account_item__organization=organization)

    _, month_ym, _ = strip_date(str(invoicecode.account_item.invoice_date))
    date_obj = datetime.strptime(str(invoicecode.account_item.invoice_date), "%Y-%m-%d")
    act_date = datetime.strptime(str(invoicecode.account_item.action_date), "%Y-%m-%d")
    # Logically-deleted (voided) line items never appear on the PDF the
    # client sees, even though they stay in the database for audit purposes.
    accountitem = AccountItem.objects.filter(
        slug=slug['slug'], organization=organization, deleted_at__isnull=True
    ).order_by('-invoice_date', 'item_code')

    # 税率毎の明細：実際に使われている税率ごとに動的に集計（0%/8%/10%等が混在しても対応）
    # 消費税額は税率区分ごとに合計した金額に対して一度だけ端数処理する（明細行ごとの
    # 端数処理は法令上認められないため）。
    rate_bases = {}
    for record in accountitem:
        rate_bases[record.tax_rate] = rate_bases.get(record.tax_rate, 0) + record.invoice_bt
    tax_method = invoice_tax_method(invoicecode)
    tax_breakdown_rows = [
        {'rate': rate, 'base': base, 'tax': (tax := tax_on_exclusive(base, rate, tax_method)), 'total': base + tax}
        for rate, base in sorted(rate_bases.items())
    ]

    # 請求書のアイテム毎金額を取得
    context['slug'] = slug
    context['object'] = accountitem
    context['tax_breakdown_rows'] = tax_breakdown_rows
    # 物件番号、レポート日、部屋番号、請求書番号を取得
    context['selected_company'] = invoicecode.account_item.company.name
    context['selected_month'] = month_ym
    context['payment_due'] = invoicecode.payment_due
    # 請求書番号、テナントID、合計額、本日の日付を取得
    context['invoice_num'] = invoicecode.invoice_slug  #請求書番号
    context['amended'] = invoicecode.amended
    context['total_amount_bt'] = invoicecode.invoice_bt_ttl 
    context['total_tax'] = invoicecode.invoice_tax_ttl 
    context['total_amount_at'] = invoicecode.invoice_at_ttl 
    context['total_bt_gttl'] = invoicecode.invoice_bt_gttl 
    context['total_at_gttl'] = invoicecode.invoice_at_gttl 
    context['total_bt_gttl_0'] = invoicecode.invoice_bt_ttl_0 
    context['today'] = datetime.today()
    context['report_date_yymm'] = date_obj.strftime('%Y%m')
    context['report_date_year'] = date_obj.strftime('%Y')
    context['report_date_month'] = date_obj.strftime('%m')
    context['act_date_year'] = act_date.strftime('%Y')
    context['act_date_month'] = act_date.strftime('%m')
    
    # 銀行情報 (issuer = the requesting organization itself)
    my_company = organization
    context['bank_name'] = my_company.bank_account.name
    context['branch_name'] = my_company.bank_account.branch_name
    context['branch_code'] = my_company.bank_account.branch_code
    context['account_type'] = my_company.bank_account.account_type
    context['account_number'] = my_company.bank_account.account_number
    context['account_name'] = my_company.bank_account.account_name
    context['account_name_kana'] = my_company.bank_account.account_name_kana

    # 当社の情報
    context['my_company'] = my_company.name
    context['register_no'] = my_company.register_no
    context['post_code'] = my_company.post_code
    context['address1'] = my_company.address1
    context['address2'] = my_company.address2
    context['tel'] = my_company.tel
    context['email'] = my_company.email
    # context['stamp_path'] = 'http://localhost:8000/static/images/soliton_stamp.png'

    # encoded_filename = urllib.parse.quote(f"【CS築地{month}月】{floor}請求書.pdf")
    amended_suffix = "（修正版）" if invoicecode.amended else ""
    context['filename'] = f"【{context['my_company'][:9]}】{invoicecode.account_item.company.slug}-{context['act_date_year']}年{context['act_date_month']}月分請求書{amended_suffix}"
    context['encoded_filename'] = quote(context['filename'])

    #html テンプレート作成
    template_name = 'invoice/invoice_detail.html'
    context['html_content'] = render_to_string(template_name, {
        'object': context['object'],
        'tax_breakdown_rows': tax_breakdown_rows,
        'context': context,
        'today': datetime.today(),
        'slug': slug,
        'filename':context['filename'],
        'interactive': False,

    # 物件番号、レポート日、部屋番号、請求書番号を取得
        'selected_company': invoicecode.account_item.company.name,
        'selected_month': month_ym,
        # An invoice groups lines by 請求日 month, NOT by 対象月, so its lines may
        # carry different 対象月. Each table row shows its own; the header lists
        # every one that appears.
        'target_month': act_date,
        'target_months': sorted({record.action_date for record in accountitem if record.action_date}),
        'payment_due': invoicecode.payment_due,
        # 請求書番号、テナントID、合計額、本日の日付を取得
        'invoice_num': invoicecode.invoice_slug,  #請求書番号
        'amended': invoicecode.amended,
        'total_amount': invoicecode.invoice_bt_ttl,
        'total_tax': invoicecode.invoice_tax_ttl,
        'total_inclusive': invoicecode.invoice_at_ttl, 


        'invoice_num': invoicecode.invoice_slug, #請求書番号
        'total_amount_bt':invoicecode.invoice_bt_ttl,
        'total_amount_at':invoicecode.invoice_at_ttl,
        'total_bt_gttl':invoicecode.invoice_bt_gttl,
        'total_at_gttl':invoicecode.invoice_at_gttl, 
        'total_bt_gttl_0':invoicecode.invoice_bt_ttl_0,


        'today': datetime.today(),
        # 請求書発行日: the line item's own invoice_date (user-editable,
        # defaults to the 1st of the month), not the date the PDF happens
        # to be rendered/downloaded on.
        'invoice_date': date_obj,
        'report_date_yymm': date_obj.strftime('%Y%m'),
        'report_date_year': date_obj.strftime('%Y'),
        'report_date_month': date_obj.strftime('%m'),
    
        # 銀行情報
        'bank_name': my_company.bank_account.name,
        'branch_name': my_company.bank_account.branch_name,
        'branch_code': my_company.bank_account.branch_code,
        'account_type': my_company.bank_account.account_type,
        'account_number': my_company.bank_account.account_number,
        'account_name': my_company.bank_account.account_name,
        'account_name_kana': my_company.bank_account.account_name_kana,

    # 当社の情報
        'my_company': my_company.name,
        'register_no': my_company.register_no,
        'post_code': my_company.post_code,
        'address1': my_company.address1,
        'address2': my_company.address2,
        'tel': my_company.tel,
        'email': my_company.email,

        # 'stamp_path': 'http://localhost:8000/static/images/soliton_stamp.png',

        'pdf_key': 'yes',
    })

    return context

"""FOR WEASY PRINT"""
def modify_html_for_weasyprint(html_content):
    static_url_prefix = settings.STATIC_URL
    static_root_path = Path(settings.STATIC_ROOT).resolve()
    static_root_file_url_base = static_root_path.as_uri()
    if not static_root_file_url_base.endswith('/'):
        static_root_file_url_base += '/'

    return html_content.replace(static_url_prefix, static_root_file_url_base)



"""
PDFの確認
"""
def preview_email_before_send(request, organization, **kwargs):
    context = prepare_invoice_items(organization, kwargs)

    html_content_modified = modify_html_for_weasyprint(context['html_content'])

    try:
        pdf_bytes = HTML(string=html_content_modified).write_pdf(stylesheets=[CSS(string='@page { size: A4; margin: 1cm; }')])
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
    except Exception:
        logger.exception("Error generating PDF preview")
    
    slug = context['slug']['slug']
    
    return render(request, 'invoice/pdf_preview.html', {
        'pdf_doc': pdf_base64,
        'pdf_file': pdf_base64,  # pass PDF data if needed
        'context': context,
        'slug': slug,
        'encoded_filename':unquote(context['filename']),
        'stamp_path': 'http://localhost:8000/static/images/soliton_stamp.png',
    })


"""
PDFの作成 (shared by the classic Django view and the API)
"""
def render_invoice_pdf(organization, slug):
    context = prepare_invoice_items(organization, {'slug': slug})
    html_content_modified = modify_html_for_weasyprint(context['html_content'])
    pdf_bytes = weasyprint.HTML(string=html_content_modified).write_pdf(
        stylesheets=[CSS(string='@page { size: A4; margin: 1cm; }')]
    )
    return pdf_bytes, context['encoded_filename']


def generate_pdf(request, organization, **kwargs):
        pdf_file, encoded_filename = render_invoice_pdf(organization, kwargs['slug'])

        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="{encoded_filename}.pdf"; '
        )
        response['Content-Type'] = 'application/octet-stream'  # Forcing download

        return response

'''
EXPORT TO CSV 請求書
'''
def export_to_csv(queryset, st, ed):
        # Build the CSV in memory first and encode once with a single
        # leading BOM. Writing straight to an HttpResponse with
        # charset='utf_8_sig' re-encodes (and re-prepends a BOM onto) every
        # csv.writer.writerow() call individually, corrupting every row
        # after the first with a stray BOM.
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=',')

        # writer.writerow(['年', '月', '日', '収入',
        #                  '支出', '適用', '補助科目', '請求書区分', 
        #                  ])

        for obj in queryset:
            # Check if the foreign keys are None and handle them accordingly
            年 = obj.action_date.strftime('%Y') if obj.action_date else ''  # Handle None by returning an empty string
            月 = obj.action_date.strftime('%m') if obj.action_date else ''
            日 = obj.action_date.strftime('%d') if obj.action_date else ''
            収入 = obj.invoice_at if obj.invoice_at else 0
            支出 = 0
            適用 = obj.action_date.strftime('%Y') + '年' + obj.action_date.strftime('%m')+ '月分' + obj.action_name + '-' + obj.company.name_yayoi if obj.action_name else ''
            請求書区分 = '適格'

            writer.writerow([
                年,  # Assuming 物件ID is a ForeignKey
                月,  # Assuming テナントID is a ForeignKey
                日,  # Assuming 管理項目コード is a related object with a code field
                収入,  # Assuming 契約ID is a ForeignKey
                支出,  # Format the date as a string
                適用,
                請求書区分,
            ])

        response = HttpResponse(buffer.getvalue().encode('utf_8_sig'), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{st}-{ed}-Invoice_list.csv"'
        return response

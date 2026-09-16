import math, csv
from .models import AccountItem, InvoiceCode, Client
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

                print("generated_id in account.slug", account.slug)

                if isinstance(account, AccountItem):
                    print("This is a valid AccountItem object.", account)
                else:
                    print("This is NOT a valid AccountItem object.")

                # Check if the generated 契約書ID already exists in 請求書ID管理
                if InvoiceCode.objects.filter(account_item_slug=generated_id).exists():
                    print(f"Duplicate detected in InvoiceCode for 契約書ID: {generated_id}. Skipping creation/update in InvoiceCode.")
                    return generated_id  # Still return the ID for reference

                try:
                    InvoiceCode.objects.create(
                        account_item_slug=generated_id,
                        account_item=account,
                        payment_due=account.payment_due,
                        invoice_bt_ttl=0,
                        invoice_tax_ttl=0,
                        invoice_at_ttl=0,
                    )
                    print(f"Created new InvoiceCode with slug:  {generated_id}")
                    print("created invoicecode")
                    print("generated_id", generated_id)
                    print("account_item", account)
                    print("payment_due", account.payment_due)
                except IntegrityError as e:
                    print(f"IntegrityError detected for 契約書ID: {generated_id}. Error: {str(e)}")
                    print(f"Skipping creation/update for this ID: {generated_id}")


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

        sort_revenues = revenues.filter(slug=invoice.account_item_slug)

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
        tax_amt = sum(math.floor(base * rate / 100) for rate, base in rate_bases.items())

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
        print("form-{i}-invoice_tax",invoice_tax)

        # Clean invoice_bt field
        if invoice_bt in cleaned_data:
            invoice_bt_value = cleaned_data[invoice_bt]
            if invoice_bt_value and isinstance(invoice_bt_value, str):
                cleaned_data[invoice_bt] = invoice_bt_value.replace(',', '')
                print("cleaned data invoice_bt",cleaned_data[invoice_bt])

        # Clean invoice_at field
        if invoice_at in cleaned_data:
            invoice_at_value = cleaned_data[invoice_at]
            if invoice_at_value and isinstance(invoice_at_value, str):
                cleaned_data[invoice_at] = invoice_at_value.replace(',', '')
                print("cleaned data invoice_at",cleaned_data[invoice_at])
        
        # Clean tax field
        if invoice_tax in cleaned_data:
            tax_value = cleaned_data[invoice_tax]
            if tax_value and isinstance(tax_value, str):
                cleaned_data[invoice_tax] = tax_value.replace(',', '')
                print("cleaned data invoice_tax",cleaned_data[invoice_tax])

    return cleaned_data

def tax_calc_def(organization, selected_company, selected_month):
        queryset = AccountItem.objects.filter(organization=organization)

        # Filter by the selected bukken if provided
        _, start_of_month, end_of_month = strip_date(selected_month)
        if selected_company == "" or selected_company is None:
            queryset = queryset.filter(invoice_date__gte=start_of_month, invoice_date__lte=end_of_month)
        else:
            queryset = queryset.filter(company=selected_company, invoice_date__gte=start_of_month, invoice_date__lte=end_of_month)
        
        print("BEFORE QUERY SET TAX", queryset.query)
        for query in queryset:
            print("QUERY", query)
            rate = query.tax_rate / 100
            if query.invoice_at == 0:
                query.invoice_tax = int(query.invoice_bt * rate)
                print("請求消費税 ", query.invoice_tax)
                query.invoice_at = query.invoice_bt + query.invoice_tax
                print("請求金額 SEIKYU KINGAKU", query.invoice_bt)
                query.save()
            elif query.invoice_bt == 0:
                query.invoice_tax = int(query.invoice_at * (1 - 1 / (1 + rate)))
                print("請求消費税 ", query.invoice_tax)
                query.invoice_bt = query.invoice_at - query.invoice_tax
                print("請求金額 SEIKYU KINGAKU", query.invoice_bt)
                query.save()




"""
メールのテナント情報、金額、合計金額の情報要素を作成
kwargs = {
    'slug': slug, 
    }
"""
def prepare_invoice_items(organization, slug, interactive=False):
    # print("5000 kwargs print", slug)
    context = {'interactive': interactive}
    invoicecode = InvoiceCode.objects.get(account_item_slug=slug['slug'], account_item__organization=organization)
    # print("invoicecode 5000  print", invoicecode)

    _, month_ym, _ = strip_date(str(invoicecode.account_item.invoice_date))
    date_obj = datetime.strptime(str(invoicecode.account_item.invoice_date), "%Y-%m-%d")
    act_date = datetime.strptime(str(invoicecode.account_item.action_date), "%Y-%m-%d")
    accountitem = AccountItem.objects.filter(slug=slug['slug'], organization=organization).order_by('-invoice_date', 'item_code')
    # print("accountitem 5000  print", accountitem)

    # 税率毎の明細：実際に使われている税率ごとに動的に集計（0%/8%/10%等が混在しても対応）
    # 消費税額は税率区分ごとに合計した金額に対して一度だけ端数処理する（明細行ごとの
    # 端数処理は法令上認められないため）。
    rate_bases = {}
    for record in accountitem:
        rate_bases[record.tax_rate] = rate_bases.get(record.tax_rate, 0) + record.invoice_bt
    tax_breakdown_rows = [
        {'rate': rate, 'base': base, 'tax': (tax := math.floor(base * rate / 100)), 'total': base + tax}
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
    context['filename'] = f"【{context['my_company'][:9]}】{invoicecode.account_item.company.slug}-{context['act_date_year']}年{context['act_date_month']}月分請求書"
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
        'payment_due': invoicecode.payment_due,
        # 請求書番号、テナントID、合計額、本日の日付を取得
        'invoice_num': invoicecode.invoice_slug,  #請求書番号
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
    print("[modify_html_for_weasyprint]-static_url_prefix:", static_url_prefix)
    static_root_path = Path(settings.STATIC_ROOT).resolve()

    print("[modify_html_for_weasyprint]-Modified html content snippet:", static_root_path)
    static_root_file_url_base = static_root_path.as_uri()
    print("[modify_html_for_weasyprint]-static_root_file_url_base:", static_root_file_url_base)
    if not static_root_file_url_base.endswith('/'):
        static_root_file_url_base += '/'
    
    html_content_modified = html_content.replace(
        static_url_prefix, static_root_file_url_base
    )
    print("[modify_html_for_weasyprint]-Modified html content snippet:", html_content_modified)
    return html_content_modified



"""
PDFの確認
"""
def preview_email_before_send(request, organization, **kwargs):
    context = prepare_invoice_items(organization, kwargs)

    html_content_modified = modify_html_for_weasyprint(context['html_content'])

    try:
        pdf_bytes = HTML(string=html_content_modified).write_pdf(stylesheets=[CSS(string='@page { size: A4; margin: 1cm; }')])
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
    except Exception as e:
        print(f"Error generating PDF: {e}")
    
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

            print("year",年 , "month", 月, "day", 日, 'income', 収入, '適用',適用, '請求書区分', 請求書区分)

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
        response['Content-Disposition'] = f"attachment; filename = {st}-{ed}-Invoice_list.csv"
        return response

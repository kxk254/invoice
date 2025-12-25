from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.views.generic import View, ListView, DetailView
from django.urls import reverse_lazy, reverse
from .models import AccountItem, Company, InvoiceCode, CsvDate
from . import calc
from .calc import strip_date
from .forms import AccountItemFormSet
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from datetime import datetime
import os, subprocess
from .  import backup_logic
from django.contrib.auth import logout

# Create your views here.
@login_required
def index(request):
    calc.set_invoice_code()
    calc.invoice_code_slug_save()
    calc.total_amount_calc()
    return render(request, 'invoice/index.html')


"""
Account Item Update
"""
class AccountItemUpdateView(LoginRequiredMixin, View):
    template_name = 'invoice/account_item_input.html'

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return render(request, self.template_name, context)

    def get_context_data(self, **kwargs):
        context = {}
        selected_company = self.request.GET.get('company')
        if selected_company == "" or selected_company is None:
            selected_company = ""
        print("selected_company 101", selected_company)
        print("passing 101")
        selected_month = self.request.GET.get('month') if self.request.GET.get('month') else timezone.now().strftime('%Y-%m-%d')
        _, start_month, end_of_month = strip_date(selected_month)

        if selected_company == "" or selected_company is None:
            print("passing 102")
            queryset = AccountItem.objects.filter(
                invoice_date__gte=start_month,
                invoice_date__lte=end_of_month,
                ).order_by('-item_code__slug', 'invoice_date')
        else:
            print("passing 103")
            queryset = AccountItem.objects.filter(
                company=Company.objects.get(id=selected_company),
                invoice_date__gte=start_month,
                invoice_date__lte=end_of_month,
                ).order_by('-item_code__slug', 'invoice_date')
        
        formset = AccountItemFormSet(queryset=queryset)
        context['companies'] = Company.objects.all()  # Assuming Bukken is your model name
        context['selected_company'] = selected_company  # Selected bukken value
        context['selected_month'] = selected_month  # Selected month value
        context['formset'] = formset  # Formset for the selected month

        return context
    
    def post(self, request, *args, **kwargs):
        
        selected_company = request.POST.get('company', None)
        selected_month = request.POST.get('month', None) 
        if selected_company == "":
            selected_company = ""  # Treat as no filter for company (all companies)
        url = reverse('invoice:update')  # This gets the URL pattern for '売上-input'
        query_params = f'?company={selected_company or ""}&month={selected_month}'
        redirect_url = f'{url}{query_params}'

        if 'tax_calc' in request.POST:
            calc.tax_calc_def(selected_company, selected_month)
            return HttpResponseRedirect(redirect_url)
        
        processed_request = calc.preprocess_post_data(self.request.POST)
        formset = AccountItemFormSet(processed_request)
        
        if formset.is_valid():
            formset.save()
            print("formset was saved")
            return HttpResponseRedirect(redirect_url)
        else:
            print("formerror", formset.errors)
            for i, form in enumerate(formset):
                print(f"Errors in form {i}: {form.errors}")
            return HttpResponseRedirect(redirect_url)

"""
List AccountItem sort by Company & Month
"""
class RevenueListView(LoginRequiredMixin, ListView):
    model = InvoiceCode
    template_name = 'invoice/invoice_list.html'

    def get_context_data(self, **kwargs):
        companies = Company.objects.all()
        company = self.request.GET.get('company')
        month = self.request.GET.get('month') if self.request.GET.get('month') else timezone.now().strftime('%Y-%m-%d')
        _, start_month, eom = strip_date(month)
        invoices = InvoiceCode.objects.filter(
            account_item__invoice_date__gte=start_month, 
            account_item__invoice_date__lte=eom
            ).order_by('-payment_due')
        invoice_data = []


        for invoice in invoices:
            items = AccountItem.objects.filter(company=invoice.account_item.company, invoice_date__gte=start_month, invoice_date__lte=eom).order_by('item_code', '-invoice_date')
            print(f"Filtering Revenue for Invoice ID: {invoice.account_item_slug}, Month: {start_month}")
            print("items", items)
            invoice_data.append({
                'invoice':invoice,
                'items':items
            })
        context = {'forms': invoice_data,'companies':companies,'selected_month':month,'selected_company':company,}
        return context
    
    def post(self, request, *args, **kwargs):
        company = self.request.POST.get('company')  # Use POST instead of GET here
        month = self.request.POST.get('month')  # Use POST instead of GET here
        print("company==>", company)
        print("month==>", month)
        _, start_month, eom = strip_date(month)

        queryset = AccountItem.objects.filter(company=company, invoice_date__gte=start_month, invoice_date__lte=eom).order_by('item_code', '-invoice_date')


        return HttpResponseRedirect(reverse('invoice:invoice-list'))

class PdfCreateDetailView(LoginRequiredMixin, DetailView):
    model = InvoiceCode
    template_name = 'invoice/invoice_detail.html'
    context_object_name = 'contract'

    def get_object(self):
        queryset = AccountItem.objects.all()
        print("kwargs 2001 ====", self.kwargs)
        # Capture the contract_id, selected_bukken, and selected_month from the URL

        if self.kwargs['slug']:
            queryset = queryset.filter(slug=self.kwargs['slug'])

        for invoice in queryset:
            # Access fields of each 請求書 object
            print(f"2001 inside queryset /// 契約書ID: {invoice.slug}, 売上_id: {invoice.id}, 税込売上額: {invoice.invoice_at}")

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # You can also pass the selected_bukken and selected_month if you need them in the template
        context = calc.prepare_invoice_items(self.kwargs)

        return context

    def post(self, request, *args, **kwargs):

        if 'create_pdf' in request.POST:
           
            import ast
            slug = request.POST.get('slug')
            slug = ast.literal_eval(slug)
            kwargs = slug
            # print("kwargs in pdf", slug)
            # return calc.generate_pdf(request, **slug)
            return calc.preview_email_before_send(request, **slug)

def pdfcreate(request, slug):
    slug = {
        'slug':slug,
    }
    return calc.generate_pdf(request, **slug)

class CSVListView(LoginRequiredMixin, ListView):
    template_name = 'invoice/invoice_csv_list.html'
    model = AccountItem

    def get_context_data(self, **kwargs):
        queryset = AccountItem.objects.all() # Article.objects.all() と同じ結果

        orig_start = CsvDate.objects.get(pk=1)
        orig_start = str(orig_start.csvdate)
        orig_end = datetime.today().strftime('%Y-%m-%d')
        # GETリクエストパラメータにkeywordがあれば、それでフィルタする
        start = self.request.GET.get('start')
        if start:
            _, start, _ = strip_date(start)
            end = self.request.GET.get('end')
            _, _, end = strip_date(end)
            queryset = queryset.filter(action_date__gte=start, action_date__lte=end)
            context = {'orig_start':start, 'orig_end':end, 'forms':queryset }
        elif start is None:
            queryset = queryset.filter(action_date__gte=orig_start, action_date__lte=orig_end)
            context = {'orig_start':orig_start, 'orig_end':orig_end, 'forms':queryset }
        return context
    
    def post(self, *args, **kwargs):

        start = self.request.POST.get('start')
        _, start, _ = strip_date(start)
        end = self.request.POST.get('end')
        _, _, end = strip_date(end)
        url = reverse('invoice:csv-create')  # This gets the URL pattern for '売上-input'
        query_params = f'?start={start}&end={end}'
        redirect_url = f'{url}{query_params}'

        queryset = AccountItem.objects.filter(action_date__gte=start, action_date__lte=end)
        st = datetime.strptime(str(start), "%Y-%m-%d")
        ed = datetime.strptime(str(end), "%Y-%m-%d")
        st = st.strftime("%Y%m")
        ed = ed.strftime("%Y%m")
        if queryset.exists():
            calc.export_to_csv(queryset, st, ed)  # Export to CSV
            # No need to redirect before CSV is returned
            orig_start = CsvDate.objects.get(pk=1)
            
            today = datetime.today().strftime('%Y-%m-%d')
            orig_start.csvdate = str(today)
            orig_start.save()
            return calc.export_to_csv(queryset, st, ed)
        
        return HttpResponseRedirect(redirect_url)


"""
CREATE DATABASE BACKUP
"""
def local_db_backup_view(request):
    """Django view to trigger the local database backup."""
    try:
        local_copy_path = backup_logic.copy_local_db()
        filename = os.path.basename(local_copy_path)
        # Success message, maybe include the filename
        return HttpResponse(f"Successfully created local backup:<br>{filename}<br><br>Now you can try copying to NAS.")
    except FileNotFoundError as e:
        return HttpResponse(f"Error: {e}", status=404) # Not Found
    except PermissionError as e:
        return HttpResponse(f"Error: {e}", status=403) # Forbidden
    except Exception as e:
        # Catch any other exceptions from the logic
        return HttpResponse(f"An unexpected error occurred during local backup: {e}", status=500) # Internal Server Error

def nas_db_backup_view(request):
    """Django view to trigger copying the latest local backup to NAS."""
    try:
        nas_copy_path = backup_logic.copy_to_nas()
        filename = os.path.basename(nas_copy_path)
        # Success message
        return HttpResponse(f"Successfully copied local backup to NAS:<br>{filename}")
    except FileNotFoundError as e:
        # This specific error means no local backup was found by copy_to_nas
        return HttpResponse(f"Error: {e}<br>Please run 'Copy Local DB' first.", status=404)
    except OSError as e:
        # Error accessing/creating NAS directory
        return HttpResponse(f"Error: Cannot access NAS directory. {e}", status=500)
    except PermissionError as e:
         return HttpResponse(f"Error: Permission denied to write to NAS directory. {e}", status=403)
    except Exception as e:
        # Catch any other exceptions
        return HttpResponse(f"An unexpected error occurred during NAS copy: {e}", status=500)

# Optional: A simple view to display the links
def backup_home_view(request):
    context = {
        'SOURCE_DB_PATH': backup_logic.SOURCE_DB_PATH,
        'LOCAL_BACKUP_DIR': backup_logic.LOCAL_BACKUP_DIR,
        'NAS_BACKUP_DIR': backup_logic.NAS_BACKUP_DIR,
    }
    return render(request, 'invoice/backup_home.html', context) # You'll create this template next

"""
CREATE POSTGRES DATABASE BACKUP
"""
def postgres_db_backup_to_nas_as_json(request):
    """Django view to dump json data as backup to NAS."""
    try:
        local_copy_path = backup_logic.dump_postgres_to_json()
        filename = os.path.basename(local_copy_path)
        # Success message, maybe include the filename
        return HttpResponse(f"Successfully dump json data to NAS:<br>{filename}<br><br>{local_copy_path}")
    except FileNotFoundError as e:
        return HttpResponse(f"Error: {e}", status=404) # Not Found
    except PermissionError as e:
        return HttpResponse(f"Error: {e}", status=403) # Forbidden
    except Exception as e:
        # Catch any other exceptions from the logic
        return HttpResponse(f"An unexpected error occurred during local backup: {e}", status=500) # Internal Server Error

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def restore_view(request):
    if request.method == "POST":
        json_file = request.FILES.get("json_file")
        if not json_file:
            return HttpResponse("No file uploaded", status=400)
        
        # save temporary
        temp_path = f"/tmp/{json_file.name}"
        with open(temp_path, "wb+") as f:
            for chunk in json_file.chunks():
                f.write(chunk)
        
        # Load into DB
        try:
            # ⚠️ Wipe all existing data
            subprocess.run(["python", "manage.py", "flush", "--noinput"], check=True)
            
            # ✅ Load new data
            subprocess.run(["python", "manage.py", "loaddata", temp_path], check=True)
            
            return HttpResponse(f"Restored database from {json_file.name}")
        except subprocess.CalledProcessError as e:
            return HttpResponse(F"Restore failed: {e}", status=500)
        finally:
            os.remove(temp_path)
    else:
        return render(request, "invoice/restore_postgres.html")


"""
UPDATED BACKUP UPON LOGOFF 2025/12/25
"""
def logout_and_backup_view(request):
    # Step 1: Trigger NAS backup
    try:
        backup_path = backup_logic.dump_postgres_to_json_to_nas()
        filename = os.path.basename(backup_path)
        # Optionally: show a message to the user
        print(f"NAS backup successful: {filename}")
    except Exception as e:
        print(f"NAS backup error: {e}")  # or log it properly

    # Step 2: Logout user
    logout(request)

    # Step 3: Redirect to login page (or homepage)
    return redirect('account_login')  # change to your login URL name
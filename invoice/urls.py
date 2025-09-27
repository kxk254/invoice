from django.urls import include, path
from . import views

app_name = 'invoice'

urlpatterns = [
    path('', views.index, name="index"),
    path('update/', views.AccountItemUpdateView.as_view(), name="update"),
    path('invoice_list/', views.RevenueListView.as_view(), name="invoice-list"),
    path('pdf_preview/<str:slug>', views.PdfCreateDetailView.as_view(), name="pdf-preview"),
    path('pdf_create/<str:slug>', views.pdfcreate, name="pdf-create"),

    path('csv_create/', views.CSVListView.as_view(), name="csv-create"),

    ### BACKUP ROUTE
    # URL for the home page (optional)
    path('backup/', views.backup_home_view, name='backup_home'),

    # URL to trigger the local backup
    path('backup/local/', views.local_db_backup_view, name='local_db_backup'),

    # URL to trigger the NAS copy (copies the latest local backup)
    path('backup/nas/', views.nas_db_backup_view, name='nas_db_backup'),
]
from rest_framework.routers import DefaultRouter
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    AccountItemViewSet, ClientViewSet, ImportView, InvoiceCodeViewSet,
    InvoicePdfView, ItemCodeViewSet, MeView, RestoreApplyView, RestorePreviewView,
)

router = DefaultRouter()
router.register("clients", ClientViewSet, basename="client")
router.register("item-codes", ItemCodeViewSet, basename="item-code")
router.register("account-items", AccountItemViewSet, basename="account-item")
router.register("invoices", InvoiceCodeViewSet, basename="invoice")

urlpatterns = [
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("me/", MeView.as_view(), name="me"),
    path("invoices/<str:slug>/pdf/", InvoicePdfView.as_view(), name="invoice-pdf"),
    path("import/", ImportView.as_view(), name="import"),
    path("restore/preview/", RestorePreviewView.as_view(), name="restore-preview"),
    path("restore/apply/", RestoreApplyView.as_view(), name="restore-apply"),
    path("", include(router.urls)),
]

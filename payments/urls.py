from django.urls import path

from .views import (
    InitializeCheckoutView,
    PaystackWebhookView,
    TransactionListView,
    VerifyTransactionView,
)

urlpatterns = [
    path('initialize/', InitializeCheckoutView.as_view(), name='payment-initialize'),
    path('verify/', VerifyTransactionView.as_view(), name='payment-verify'),
    path('webhook/paystack/', PaystackWebhookView.as_view(), name='payment-webhook'),
    path('transactions/', TransactionListView.as_view(), name='payment-transactions'),
]

from django.contrib import admin
from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('txn_ref', 'user', 'meter', 'amount', 'status', 'created_at', 'verified_at')
    list_filter = ('status',)
    search_fields = ('txn_ref', 'user__username', 'meter__serial_number')

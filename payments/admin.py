from django.contrib import admin
from .models import Transaction, TransactionAuditLog


class TransactionAuditLogInline(admin.TabularInline):
    model = TransactionAuditLog
    extra = 0
    readonly_fields = ('event', 'detail', 'created_at')
    can_delete = False
    ordering = ('created_at',)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'txn_ref', 'user', 'meter', 'amount', 'status', 'fulfillment_status',
        'payment_method', 'created_at', 'fulfilled_at',
    )
    list_filter = ('status', 'fulfillment_status', 'payment_method')
    search_fields = ('txn_ref', 'user__username', 'meter__serial_number')
    inlines = [TransactionAuditLogInline]

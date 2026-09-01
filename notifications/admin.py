from django.contrib import admin
from .models import Notification, NotificationPreference

admin.site.register(NotificationPreference)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('type', 'user', 'meter', 'email_sent', 'is_read', 'created_at')
    list_filter = ('type', 'email_sent', 'is_read')
    search_fields = ('user__username', 'meter__serial_number')
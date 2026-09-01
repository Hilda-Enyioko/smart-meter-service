from django.urls import path
from .views import (
    NotificationPreferenceView,
    MarkNotificationReadView,
    NotificationListView,
)

urlpatterns = [
    path('preferences/', NotificationPreferenceView.as_view(), name='notification-preferences'),
    path('', NotificationListView.as_view(), name='notification-list'),
    path('<int:pk>/read/', MarkNotificationReadView.as_view(), name='notification-mark-read'),
]
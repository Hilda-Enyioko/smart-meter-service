from django.urls import path

from .views import (
    MeterDetailView,
    MyMetersListView,
    RegisterMeterView,
    DeviceTelemetryView,
    DeviceCommandView,
    MeterDashboardView,
)

urlpatterns = [
    path('register/', RegisterMeterView.as_view(), name='meter-register'),
    path('', MyMetersListView.as_view(), name='meter-list'),
    path('<int:pk>/', MeterDetailView.as_view(), name='meter-detail'),
    path('device/telemetry/', DeviceTelemetryView.as_view(), name='device-telemetry'),
    path('device/command/', DeviceCommandView.as_view(), name='device-command'),
    path('<int:pk>/dashboard/', MeterDashboardView.as_view(), name='meter-dashboard'),
]

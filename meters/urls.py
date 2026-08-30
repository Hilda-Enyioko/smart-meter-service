from django.urls import path

from .views import (
    MeterDetailView,
    MyMetersListView,
    RegisterMeterView,
    DeviceTelemetryView,
    DeviceCommandView,
    MeterDashboardView,
    MeterConsumptionView,
    MeterCreditUsageView,
    MeterHistoryView,
    MeterRuntimeEstimateView,
    AdminAddCreditView,
    LowCreditThresholdView,
    RelayControlView,
)

urlpatterns = [
    path('register/', RegisterMeterView.as_view(), name='meter-register'),
    path('', MyMetersListView.as_view(), name='meter-list'),
    path('<int:pk>/', MeterDetailView.as_view(), name='meter-detail'),
    path('device/telemetry/', DeviceTelemetryView.as_view(), name='device-telemetry'),
    path('device/command/', DeviceCommandView.as_view(), name='device-command'),
    path('<int:pk>/dashboard/', MeterDashboardView.as_view(), name='meter-dashboard'),
    path('<int:pk>/analytics/history/', MeterHistoryView.as_view(), name='meter-history'),
    path('<int:pk>/analytics/consumption/', MeterConsumptionView.as_view(), name='meter-consumption'),
    path('<int:pk>/analytics/credit-usage/', MeterCreditUsageView.as_view(), name='meter-credit-usage'),
    path('<int:pk>/analytics/runtime-estimate/', MeterRuntimeEstimateView.as_view(), name='meter-runtime-estimate'),
    path('<int:pk>/threshold/', LowCreditThresholdView.as_view(), name='meter-threshold'),
    path('<int:pk>/relay/', RelayControlView.as_view(), name='meter-relay-control'),
    path('<int:pk>/admin-add-credit/', AdminAddCreditView.as_view(), name='meter-admin-add-credit'),
]

from django.urls import path

from .views import MeterDetailView, MyMetersListView, RegisterMeterView

urlpatterns = [
    path('register/', RegisterMeterView.as_view(), name='meter-register'),
    path('', MyMetersListView.as_view(), name='meter-list'),
    path('<int:pk>/', MeterDetailView.as_view(), name='meter-detail'),
]

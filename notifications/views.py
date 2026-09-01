from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from .models import Notification, NotificationPreference
from .serializers import NotificationSerializer, NotificationPreferenceSerializer

class NotificationListView(generics.ListAPIView):
    """GET /api/notifications/ — current user's notification history, newest first."""
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


class MarkNotificationReadView(APIView):
    """POST /api/notifications/<id>/read/ — mark a single notification as read."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        notif = get_object_or_404(Notification, pk=pk, user=request.user)
        notif.is_read = True
        notif.save()
        return Response({'id': notif.id, 'is_read': True})

class NotificationPreferenceView(generics.RetrieveUpdateAPIView):
    """Get or update the current user's notification preferences (auto-created on first access)."""
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        prefs, _created = NotificationPreference.objects.get_or_create(user=self.request.user)
        return prefs

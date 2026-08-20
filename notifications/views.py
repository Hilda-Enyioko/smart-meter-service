from rest_framework import generics, permissions

from .models import NotificationPreference
from .serializers import NotificationPreferenceSerializer


class NotificationPreferenceView(generics.RetrieveUpdateAPIView):
    """Get or update the current user's notification preferences (auto-created on first access)."""
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        prefs, _created = NotificationPreference.objects.get_or_create(user=self.request.user)
        return prefs

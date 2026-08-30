from rest_framework.permissions import BasePermission
from .models import Meter


class DeviceKeyAuthenticated(BasePermission):
    """
    Checks serial_number + device_key from request data/query params against the DB.
    Attaches the matched meter to request.meter for the view to use.
    """
    message = "Invalid serial_number or device_key."

    def has_permission(self, request, view):
        serial_number = request.data.get('serial_number') or request.query_params.get('serial_number')
        device_key = request.data.get('device_key') or request.query_params.get('device_key')

        if not serial_number or not device_key:
            return False

        try:
            meter = Meter.objects.get(serial_number=serial_number, device_key=device_key)
        except Meter.DoesNotExist:
            return False

        request.meter = meter
        return True


class IsMeterOwnerOrAdmin(BasePermission):
    """Allows the meter's linked user, or an admin, to control it manually."""
    def has_object_permission(self, request, view, obj):
        if request.user.role == request.user.Role.ADMIN:
            return True
        return obj.user_id == request.user.id

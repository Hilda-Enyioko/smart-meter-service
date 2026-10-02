from rest_framework import status
from rest_framework.test import APITestCase

from .models import Meter


class DeviceEndpointTests(APITestCase):
    def setUp(self):
        self.meter = Meter.objects.create(
            serial_number='30530268918',
            device_key='test-device-key',
            credit_balance='12.50',
        )

    def test_command_uses_device_credentials_without_user_auth(self):
        response = self.client.get(
            '/api/meters/device/command/',
            {'serial_number': self.meter.serial_number, 'device_key': self.meter.device_key},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'relay_command': 'ON', 'credit_balance': '12.50'})

    def test_command_wrong_key_returns_json_error(self):
        response = self.client.get(
            '/api/meters/device/command/',
            {'serial_number': self.meter.serial_number, 'device_key': 'wrong-key'},
        )

        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
        self.assertEqual(response['Content-Type'].split(';')[0], 'application/json')
        self.assertIn('detail', response.json())

    def test_telemetry_uses_device_credentials_and_returns_command(self):
        response = self.client.post(
            '/api/meters/device/telemetry/',
            {
                'serial_number': self.meter.serial_number,
                'device_key': self.meter.device_key,
                'voltage': 230.0,
                'current': 1.25,
                'power': 287.5,
                'energy': 0.1,
                'relay_state': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['relay_command'], 'ON')
        self.assertTrue(response.json()['received'])

    def test_device_endpoints_require_the_documented_methods(self):
        command_response = self.client.post('/api/meters/device/command/', {}, format='json')
        telemetry_response = self.client.get('/api/meters/device/telemetry/')

        self.assertEqual(command_response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(telemetry_response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(command_response['Content-Type'].split(';')[0], 'application/json')
        self.assertEqual(telemetry_response['Content-Type'].split(';')[0], 'application/json')

    def test_telemetry_wrong_key_returns_json_error(self):
        response = self.client.post(
            '/api/meters/device/telemetry/',
            {
                'serial_number': self.meter.serial_number,
                'device_key': 'wrong-key',
                'voltage': 230,
                'current': 1,
                'power': 230,
                'energy': 0.1,
                'relay_state': True,
            },
            format='json',
        )

        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
        self.assertEqual(response['Content-Type'].split(';')[0], 'application/json')
        self.assertIn('detail', response.json())

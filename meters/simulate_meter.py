import requests
import random
import time

BASE_URL = "https://smart-meter-service-72mv.onrender.com/api/meters/device"
SERIAL_NUMBER = "MTR-001"
DEVICE_KEY = "paste-the-device_key-here"

def send_telemetry():
    payload = {
        "serial_number": SERIAL_NUMBER,
        "device_key": DEVICE_KEY,
        "voltage": round(random.uniform(215, 235), 2),
        "current": round(random.uniform(0.5, 5.0), 2),
        "power": round(random.uniform(100, 1000), 2),
        "energy": round(random.uniform(0.01, 0.05), 4),
        "relay_state": True,
    }
    r = requests.post(f"{BASE_URL}/telemetry/", json=payload, timeout=10)
    print("Telemetry:", r.status_code, r.json())

def check_command():
    params = {"serial_number": SERIAL_NUMBER, "device_key": DEVICE_KEY}
    r = requests.get(f"{BASE_URL}/command/", params=params, timeout=10)
    print("Command:", r.status_code, r.json())

if __name__ == "__main__":
    while True:
        send_telemetry()
        check_command()
        time.sleep(10)

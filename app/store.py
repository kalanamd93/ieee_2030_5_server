"""
In-memory data store for the IEEE 2030.5 test server.
"""

import time
import uuid
from collections import deque


class DataStore:
    def __init__(self):
        self.start_time = int(time.time())

        # Server identity
        self.server_sfdi = "123456789012"
        self.server_lfdi = "AABBCCDDEEFF00112233445566778899AABBCCDD"

        # Resources
        self.end_devices = {}
        self.registrations = {}
        self.mirror_usage_points = {}
        self.meter_readings = {}       # mupId -> list of readings
        self.der_programs = {}
        self.der_controls = {}
        self.der_control_lists = {}
        self.der_capabilities = {}
        self.der_settings_store = {}
        self.der_availability_store = {}
        self.der_status_store = {}
        self.ders = {}
        self.dr_programs = self._default_dr_programs()
        self.end_device_controls = {}
        self.subscriptions = {}
        self.messages = {}
        self.responses = []

        # Power/frequency limits (used by DERSettings & DefaultDERControl)
        self.limits = {
            "maxW": 10000,       # Watts * 10^-3 → 10 kW
            "maxVar": 5000,      # VAR * 10^-3 → 5 kVAR
            "maxVA": 11000,      # VA * 10^-3 → 11 kVA
            "highFreq": 6020,    # 60.20 Hz * 100
            "lowFreq": 5970,     # 59.70 Hz * 100
            "highVolt": 12000,   # 120.00 V * 100
            "lowVolt": 10800,    # 108.00 V * 100
            "gradW": 1000,       # W/s * 10^-3
            "softGradW": 500,
        }

        # Telemetry timeline (for dashboard)
        self.telemetry = deque(maxlen=2000)

        # Log events
        self.log_events = deque(maxlen=500)
        self._log_id = 0

        # Power status
        self.power_status = {
            "estimatedChargeRemaining": 10000,
            "estimatedTimeRemaining": 3600,
        }

        self.add_log("IEEE 2030.5 Test Server started")

    def _default_dr_programs(self):
        return {
            "default": {
                "id": "default",
                "mRID": "DR-DEFAULT",
                "description": "Default Demand Response Program",
                "primacy": 1,
                "href": "/dr/default",
            }
        }

    def add_log(self, message):
        self._log_id += 1
        self.log_events.append({
            "id": self._log_id,
            "message": message,
            "timestamp": int(time.time()),
        })

    def add_telemetry(self, entry):
        self.telemetry.append(entry)

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

        # End Devices & Registration
        self.end_devices   = {}
        self.registrations = {}

        # Per-device sub-resources
        self.edev_device_info    = {}   # key: <eid>_di
        self.edev_device_status  = {}   # key: <eid>_dstat
        self.edev_power_status   = {}   # key: <eid>_ps

        # DER resources
        self.ders                   = {}   # key: <eid>_ders  → list
        self.der_capabilities       = {}   # key: <eid>_<did>_cap
        self.der_settings_store     = {}   # key: <eid>_<did>_settings
        self.der_availability_store = {}   # key: <eid>_<did>_avail
        self.der_status_store       = {}   # key: <eid>_<did>_status

        # DER Programs, Controls, Curves
        self.der_programs      = {}
        self.der_controls      = {}        # key: <pid>_dderc  (default control store)
        self.der_control_lists = {}        # key: <pid>_controls  → list
        self.der_curves        = {}        # key: <pid>_curves    → list

        # Demand Response
        self.dr_programs         = self._default_dr_programs()
        self.end_device_controls = {}      # key: <pid>_edcs  → list

        # Mirror Usage Points & Readings
        self.mirror_usage_points = {}
        self.meter_readings      = {}      # mupId → list

        # Server-side Usage Points
        self.usage_points  = {}
        self.upt_readings  = {}            # upid → list

        # Pricing
        self.tariff_profiles = {}

        # Messaging
        self.messages = {}

        # Response Sets & Responses
        self.response_sets    = {}
        self.responses_by_set = {}         # rsid → list

        # Subscriptions
        self.subscriptions = {}

        # Flow Reservations
        self.flow_reservations          = {}
        self.flow_reservation_responses = {}

        # Prepayments
        self.prepayments = {}

        # Power limits (served via DERSettings / DefaultDERControl)
        self.limits = {
            "maxW":      10000,   # W  × 10^-3  → 10 kW
            "maxVar":     5000,   # VAR × 10^-3 → 5 kVAR
            "maxVA":     11000,   # VA × 10^-3  → 11 kVA
            "highFreq":   6020,   # Hz × 100    → 60.20 Hz
            "lowFreq":    5970,   # Hz × 100    → 59.70 Hz
            "highVolt":  12000,   # V × 100     → 120.00 V
            "lowVolt":   10800,   # V × 100     → 108.00 V
            "gradW":      1000,
            "softGradW":   500,
        }

        # Telemetry timeline (for dashboard charts)
        self.telemetry = deque(maxlen=2000)

        # Log events
        self.log_events = deque(maxlen=500)
        self._log_id    = 0

        # Server power status
        self.power_status = {
            "estimatedChargeRemaining": 10000,
            "estimatedTimeRemaining":   3600,
        }

        self.add_log("IEEE 2030.5 Test Server started")

    def _default_dr_programs(self):
        return {
            "default": {
                "id":          "default",
                "mRID":        "DR-DEFAULT",
                "description": "Default Demand Response Program",
                "primacy":     1,
                "href":        "/dr/default",
            }
        }

    def add_log(self, message):
        self._log_id += 1
        self.log_events.append({
            "id":        self._log_id,
            "message":   message,
            "timestamp": int(time.time()),
        })

    def add_telemetry(self, entry):
        self.telemetry.append(entry)

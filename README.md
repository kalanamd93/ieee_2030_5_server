# IEEE 2030.5 / SEP 2.0 Test Server

A full-featured IEEE 2030.5 (SEP 2.0) test server with:
- All major resource endpoints per the standard
- No mTLS (plain HTTP for local testing)
- Live telemetry dashboard at `http://localhost:8080/`
- Configurable DER limits via the dashboard UI or REST API

---

## Quick Start (Docker Desktop)

```bash
# Build and start
docker compose up --build

# Or run detached
docker compose up -d --build
```

The server starts on **http://localhost:8080**

| URL | What it is |
|-----|-----------|
| `http://localhost:8080/` | Telemetry dashboard |
| `http://localhost:8080/dcap` | Device Capability (entry point) |
| `http://localhost:8080/tm` | Time resource |

---

## Implemented IEEE 2030.5 Endpoints

### Core / Device
| Method | Path | Resource |
|--------|------|----------|
| GET | `/dcap` | DeviceCapability (entry point) |
| GET | `/tm` | Time |
| GET | `/sdev` | SelfDevice |
| GET | `/sdev/di` | DeviceInformation |
| GET | `/sdev/dstat` | DeviceStatus |
| GET | `/sdev/ps` | PowerStatus |

### End Devices
| Method | Path | Resource |
|--------|------|----------|
| GET, POST | `/edev` | EndDeviceList |
| GET, PUT, DELETE | `/edev/<eid>` | EndDevice |
| GET, PUT | `/edev/<eid>/reg` | Registration |
| GET | `/edev/<eid>/fsa` | FunctionSetAssignmentsList |

### DER (Distributed Energy Resources)
| Method | Path | Resource |
|--------|------|----------|
| GET, POST | `/edev/<eid>/der` | DERList |
| GET, PUT | `/edev/<eid>/der/<did>/derc` | DERCapability |
| GET, PUT | `/edev/<eid>/der/<did>/ders` | DERSettings |
| GET, PUT | `/edev/<eid>/der/<did>/dera` | DERAvailability |
| GET, PUT | `/edev/<eid>/der/<did>/derstatus` | DERStatus |
| GET, POST | `/derp` | DERProgramList |
| GET, DELETE | `/derp/<pid>` | DERProgram |
| GET, PUT | `/derp/<pid>/dderc` | DefaultDERControl |
| GET, POST | `/derp/<pid>/derc` | DERControlList |

### Metering / Mirror Usage Points
| Method | Path | Resource |
|--------|------|----------|
| GET, POST | `/mup` | MirrorUsagePointList |
| GET, DELETE | `/mup/<mid>` | MirrorUsagePoint |
| GET, POST | `/mup/<mid>/mr` | MirrorMeterReadingList |
| GET | `/mup/<mid>/mr/<rid>` | MirrorMeterReading |
| GET | `/upt` | UsagePointList |

### Demand Response
| Method | Path | Resource |
|--------|------|----------|
| GET | `/dr` | DemandResponseProgramList |
| GET | `/dr/<pid>` | DemandResponseProgram |
| GET, POST | `/dr/<pid>/edc` | EndDeviceControlList |

### Misc
| Method | Path | Resource |
|--------|------|----------|
| GET | `/lel` | LogEventList |
| GET, POST | `/sub` | SubscriptionList |
| GET, DELETE | `/sub/<sid>` | Subscription |
| GET | `/pricep` | TariffProfileList (stub) |
| GET, POST | `/msg` | MessagingProgramList |
| GET | `/rsps` | ResponseSetList |
| POST | `/rsps/<rsid>/rsp` | Response |
| GET | `/frp` | FlowReservationRequestList |

### Dashboard API (JSON)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/telemetry` | Recent telemetry readings |
| GET, POST | `/api/limits` | Get / update DER limits |
| GET | `/api/logs` | Server log events |
| GET | `/api/devices` | End devices + MUPs |
| POST | `/api/send_message` | Queue a message |

---

## Typical Client Flow

### 1. Register an EndDevice
```bash
curl -X POST http://localhost:8080/edev \
  -H "Content-Type: application/sep+xml" \
  -d '<sep:EndDevice xmlns:sep="urn:ieee:std:2030.5:ns">
        <sep:lFDI>AABBCCDDEEFF</sep:lFDI>
        <sep:sFDI>123456789</sep:sFDI>
        <sep:enabled>true</sep:enabled>
      </sep:EndDevice>'
```

### 2. Create a Mirror Usage Point
```bash
curl -X POST http://localhost:8080/mup \
  -H "Content-Type: application/sep+xml" \
  -d '<sep:MirrorUsagePoint xmlns:sep="urn:ieee:std:2030.5:ns">
        <sep:mRID>MUP-CLIENT-001</sep:mRID>
        <sep:description>Solar Inverter</sep:description>
        <sep:deviceLFDI>AABBCCDDEEFF</sep:deviceLFDI>
      </sep:MirrorUsagePoint>'
# Note the `href` in the response, e.g. /mup/a1b2c3d4
```

### 3. Post a Meter Reading (Active Power - UOM 38 = W)
```bash
# Replace <mid> with the ID returned above
curl -X POST http://localhost:8080/mup/<mid>/mr \
  -H "Content-Type: application/sep+xml" \
  -d '<sep:MirrorMeterReading xmlns:sep="urn:ieee:std:2030.5:ns">
        <sep:mRID>MR-001</sep:mRID>
        <sep:description>Active Power</sep:description>
        <sep:Reading>
          <sep:value>5500</sep:value>
          <sep:uom>38</sep:uom>
        </sep:Reading>
        <sep:ReadingType>
          <sep:multiplier>-3</sep:multiplier>
          <sep:uom>38</sep:uom>
        </sep:ReadingType>
      </sep:MirrorMeterReading>'
```

### 4. Poll DER Settings (client reads limits from here)
```bash
curl http://localhost:8080/edev/<eid>/der/<did>/ders
```

### 5. Get Device Capability (entry point)
```bash
curl http://localhost:8080/dcap
```

---

## DER Limits

Limits can be updated:

**Via Dashboard UI** — open `http://localhost:8080/` and use the "DER Limits" panel.

**Via REST API:**
```bash
curl -X POST http://localhost:8080/api/limits \
  -H "Content-Type: application/json" \
  -d '{
    "maxW": 8000,
    "maxVar": 4000,
    "maxVA": 9000,
    "highFreq": 6020,
    "lowFreq": 5970,
    "highVolt": 12600,
    "lowVolt": 10800
  }'
```

The client will see updated values next time it GETs `/edev/<eid>/der/<did>/ders` or `/derp/<pid>/dderc`.

---

## UOM Reference (IEEE 1377)

| Code | Unit | Typical use |
|------|------|-------------|
| 5 | A | Current |
| 29 | VAR | Reactive power |
| 33 | Hz | Frequency |
| 38 | W | Active power |
| 61 | VA | Apparent power |
| 63 | V | Voltage |
| 72 | Wh | Energy |

---

## Content Types

IEEE 2030.5 uses `application/sep+xml` for all resource endpoints.  
The dashboard API uses `application/json`.

---

## Stopping the server

```bash
docker compose down
```

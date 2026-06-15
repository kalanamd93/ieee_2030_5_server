"""
IEEE 2030.5 (SEP 2.0) Test Server
Implements all major resource endpoints per the IEEE 2030.5 standard.
No mTLS — plain HTTP/HTTPS for local testing.
"""

from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS
import xml.etree.ElementTree as ET
import xml.dom.minidom
import json
import uuid
import time
import threading
from datetime import datetime, timezone
from collections import deque
try:
    from store import DataStore
except ImportError:
    from app.store import DataStore

app = Flask(__name__, template_folder="../templates", static_folder="../static")
CORS(app)

store = DataStore()

SEP_NS = "urn:ieee:std:2030.5:ns"
SEP_PREFIX = "sep"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ts():
    """Current Unix timestamp (seconds)."""
    return int(time.time())


def make_xml(tag, attribs=None, children=None, text=None, ns=SEP_NS):
    """Build a simple XML element string."""
    root = ET.Element(f"{{{ns}}}{tag}", attribs or {})
    if text is not None:
        root.text = str(text)
    for child in (children or []):
        root.append(child)
    raw = ET.tostring(root, encoding="unicode", xml_declaration=False)
    pretty = xml.dom.minidom.parseString(raw).toprettyxml(indent="  ")
    # remove the xml declaration line added by toprettyxml
    lines = pretty.split("\n")[1:]
    return "\n".join(lines)


def xml_response(xml_str, status=200):
    return Response(xml_str, status=status, mimetype="application/sep+xml")


def elem(tag, text=None, attribs=None, ns=SEP_NS):
    e = ET.Element(f"{{{ns}}}{tag}", attribs or {})
    if text is not None:
        e.text = str(text)
    return e


def build_xml(tag, children_fn, attribs=None, ns=SEP_NS):
    """Build XML tree via a callback, return pretty string."""
    root = ET.Element(f"{{{ns}}}{tag}", attribs or {})
    if children_fn:
        children_fn(root)
    raw = ET.tostring(root, encoding="unicode")
    try:
        pretty = xml.dom.minidom.parseString(raw).toprettyxml(indent="  ")
        return "\n".join(pretty.split("\n")[1:])
    except Exception:
        return raw


# ---------------------------------------------------------------------------
# Device Capability (DCap) — entry point
# ---------------------------------------------------------------------------

@app.route("/dcap", methods=["GET"])
def device_capability():
    def children(root):
        root.set("href", "/dcap")
        root.append(elem("pollRate", "900"))
        root.append(elem("EndDeviceListLink", attribs={"href": "/edev", "all": str(len(store.end_devices))}))
        root.append(elem("MirrorUsagePointListLink", attribs={"href": "/mup", "all": str(len(store.mirror_usage_points))}))
        root.append(elem("SelfDeviceLink", attribs={"href": "/sdev"}))
        root.append(elem("TimeLink", attribs={"href": "/tm"}))
        root.append(elem("DERProgramListLink", attribs={"href": "/derp", "all": str(len(store.der_programs))}))
        root.append(elem("DemandResponseProgramListLink", attribs={"href": "/dr", "all": "1"}))
        root.append(elem("PricingProgramListLink", attribs={"href": "/pricep", "all": "0"}))
        root.append(elem("MessagingProgramListLink", attribs={"href": "/msg", "all": "0"}))
        root.append(elem("ResponseSetListLink", attribs={"href": "/rsps", "all": "0"}))
        root.append(elem("LogEventListLink", attribs={"href": "/lel", "all": str(len(store.log_events))}))
    return xml_response(build_xml("DeviceCapability", children))


# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------

@app.route("/tm", methods=["GET"])
def time_resource():
    now = int(time.time())
    def children(root):
        root.set("href", "/tm")
        root.append(elem("currentTime", str(now)))
        root.append(elem("dstEndTime", str(now + 86400 * 180)))
        root.append(elem("dstOffset", "3600"))
        root.append(elem("dstStartTime", str(now - 86400 * 180)))
        root.append(elem("localTime", str(now)))
        root.append(elem("quality", "7"))
        root.append(elem("tzOffset", "0"))
    return xml_response(build_xml("Time", children))


# ---------------------------------------------------------------------------
# Self Device
# ---------------------------------------------------------------------------

@app.route("/sdev", methods=["GET"])
def self_device():
    def children(root):
        root.set("href", "/sdev")
        root.append(elem("sFDI", store.server_sfdi))
        root.append(elem("lFDI", store.server_lfdi))
        root.append(elem("DeviceInformationLink", attribs={"href": "/sdev/di"}))
        root.append(elem("DeviceStatusLink", attribs={"href": "/sdev/dstat"}))
        root.append(elem("PowerStatusLink", attribs={"href": "/sdev/ps"}))
        root.append(elem("LogEventListLink", attribs={"href": "/sdev/lel", "all": "0"}))
    return xml_response(build_xml("SelfDevice", children))


@app.route("/sdev/di", methods=["GET"])
def self_device_info():
    def children(root):
        root.set("href", "/sdev/di")
        root.append(elem("mfHwVer", "1.0"))
        root.append(elem("mfID", "65535"))
        root.append(elem("mfInfo", "IEEE2030.5 Test Server"))
        root.append(elem("mfModel", "TestServer"))
        root.append(elem("mfSerNum", "SN-TEST-001"))
        root.append(elem("mfSwVer", "1.0.0"))
        root.append(elem("primaryPower", "1"))
        root.append(elem("secondaryPower", "0"))
    return xml_response(build_xml("DeviceInformation", children))


@app.route("/sdev/dstat", methods=["GET"])
def self_device_status():
    def children(root):
        root.set("href", "/sdev/dstat")
        root.append(elem("changedTime", str(ts())))
        root.append(elem("onCount", "1"))
        root.append(elem("opState", "1"))
        root.append(elem("opTime", str(ts() - store.start_time)))
    return xml_response(build_xml("DeviceStatus", children))


@app.route("/sdev/ps", methods=["GET"])
def self_power_status():
    ps = store.power_status
    def children(root):
        root.set("href", "/sdev/ps")
        root.append(elem("currentPowerSource", "1"))
        root.append(elem("estimatedChargeRemaining", str(ps.get("estimatedChargeRemaining", 10000))))
        root.append(elem("estimatedTimeRemaining", str(ps.get("estimatedTimeRemaining", 3600))))
        root.append(elem("PEVInfoLink", attribs={"href": "/sdev/ps/pev"}))
        root.append(elem("sessionTimeOnBattery", "0"))
        root.append(elem("totalTimeOnBattery", "0"))
    return xml_response(build_xml("PowerStatus", children))


# ---------------------------------------------------------------------------
# End Device List
# ---------------------------------------------------------------------------

@app.route("/edev", methods=["GET", "POST"])
def end_device_list():
    if request.method == "POST":
        import random
        eid = str(uuid.uuid4())[:8]
        body = request.data.decode()

        # Parse lFDI / sFDI from request body if provided
        lfdi = f"LFDI-{eid}"
        sfdi = str(int(uuid.uuid4().int % 281474976710655))
        try:
            ns_map = {"sep": SEP_NS}
            root_el = ET.fromstring(body)
            l = root_el.find("sep:lFDI", ns_map)
            s = root_el.find("sep:sFDI", ns_map)
            if l is not None and l.text: lfdi = l.text.strip()
            if s is not None and s.text: sfdi = s.text.strip()
        except Exception:
            pass

        store.end_devices[eid] = {
            "id": eid,
            "href": f"/edev/{eid}",
            "lFDI": lfdi,
            "sFDI": sfdi,
            "changedTime": ts(),
            "enabled": False,
            "registrationStatus": "pending",
            "raw": body,
        }
        # Auto-create Registration with a random 6-digit PIN
        pin = str(random.randint(100000, 999999))
        store.registrations[eid] = {
            "dateTimeRegistered": ts(),
            "pIN": pin,
            "status": "pending",
            "eid": eid,
        }
        store.add_log(f"EndDevice registered (pending): {eid} lFDI={lfdi} PIN={pin}")
        return xml_response(f'<sep:EndDevice xmlns:sep="{SEP_NS}" href="/edev/{eid}"/>', 201)

    start = int(request.args.get("s", 0))
    limit = int(request.args.get("l", 255))
    devs = list(store.end_devices.values())[start:start + limit]

    def children(root):
        root.set("href", "/edev")
        root.set("all", str(len(store.end_devices)))
        root.set("results", str(len(devs)))
        for d in devs:
            ed = elem("EndDevice", attribs={"href": d["href"]})
            ed.append(elem("lFDI", d["lFDI"]))
            ed.append(elem("sFDI", d["sFDI"]))
            ed.append(elem("changedTime", str(d["changedTime"])))
            ed.append(elem("enabled", "true" if d["enabled"] else "false"))
            ed.append(elem("RegistrationLink", attribs={"href": f"/edev/{d['id']}/reg"}))
            ed.append(elem("FunctionSetAssignmentsListLink", attribs={"href": f"/edev/{d['id']}/fsa", "all": "1"}))
            ed.append(elem("PowerStatusLink", attribs={"href": f"/edev/{d['id']}/ps"}))
            ed.append(elem("DERListLink", attribs={"href": f"/edev/{d['id']}/der", "all": "1"}))
            ed.append(elem("LogEventListLink", attribs={"href": f"/edev/{d['id']}/lel", "all": "0"}))
            root.append(ed)
    return xml_response(build_xml("EndDeviceList", children))


@app.route("/edev/<eid>", methods=["GET", "PUT", "DELETE"])
def end_device(eid):
    if request.method == "DELETE":
        store.end_devices.pop(eid, None)
        return xml_response("", 204)
    if request.method == "PUT":
        d = store.end_devices.get(eid, {"id": eid, "href": f"/edev/{eid}"})
        d["changedTime"] = ts()
        store.end_devices[eid] = d
        return xml_response("", 204)

    d = store.end_devices.get(eid)
    if not d:
        return xml_response("<sep:Error>Not Found</sep:Error>", 404)

    def children(root):
        root.set("href", d["href"])
        root.append(elem("lFDI", d["lFDI"]))
        root.append(elem("sFDI", d["sFDI"]))
        root.append(elem("changedTime", str(d["changedTime"])))
        root.append(elem("enabled", "true" if d["enabled"] else "false"))
        root.append(elem("RegistrationLink", attribs={"href": f"/edev/{eid}/reg"}))
        root.append(elem("FunctionSetAssignmentsListLink", attribs={"href": f"/edev/{eid}/fsa", "all": "1"}))
        root.append(elem("PowerStatusLink", attribs={"href": f"/edev/{eid}/ps"}))
        root.append(elem("DERListLink", attribs={"href": f"/edev/{eid}/der", "all": "1"}))
        root.append(elem("LogEventListLink", attribs={"href": f"/edev/{eid}/lel", "all": "0"}))
    return xml_response(build_xml("EndDevice", children))


@app.route("/edev/<eid>/reg", methods=["GET", "PUT"])
def end_device_registration(eid):
    d = store.end_devices.get(eid)
    if not d:
        return xml_response(f'<sep:Error xmlns:sep="{SEP_NS}">EndDevice not found</sep:Error>', 404)

    reg = store.registrations.get(eid)
    if not reg:
        # Shouldn't happen — created on POST /edev — but handle gracefully
        import random
        pin = str(random.randint(100000, 999999))
        reg = {"dateTimeRegistered": ts(), "pIN": pin, "status": "pending", "eid": eid}
        store.registrations[eid] = reg

    if request.method == "PUT":
        body = request.data.decode()
        submitted_pin = None
        try:
            ns_map = {"sep": SEP_NS}
            root_el = ET.fromstring(body)
            p = root_el.find("sep:pIN", ns_map)
            if p is not None and p.text:
                submitted_pin = p.text.strip()
        except Exception:
            pass

        if submitted_pin is not None:
            if submitted_pin == reg["pIN"]:
                reg["status"] = "confirmed"
                reg["dateTimeRegistered"] = ts()
                store.end_devices[eid]["enabled"] = True
                store.end_devices[eid]["registrationStatus"] = "confirmed"
                store.add_log(f"EndDevice {eid} registration CONFIRMED (PIN matched)")
                store.registrations[eid] = reg
                return xml_response("", 204)
            else:
                store.add_log(f"EndDevice {eid} registration FAILED: wrong PIN (got {submitted_pin}, expected {reg['pIN']})")
                return xml_response(
                    f'<sep:Error xmlns:sep="{SEP_NS}"><sep:message>Invalid PIN</sep:message></sep:Error>', 403)
        else:
            # No PIN in body — treat as a plain update (e.g. server-side confirm)
            reg["dateTimeRegistered"] = ts()
            store.registrations[eid] = reg
            return xml_response("", 204)

    def children(root):
        root.set("href", f"/edev/{eid}/reg")
        root.append(elem("dateTimeRegistered", str(reg["dateTimeRegistered"])))
        root.append(elem("pIN", reg["pIN"]))
    return xml_response(build_xml("Registration", children))


@app.route("/edev/<eid>/fsa", methods=["GET"])
def function_set_assignments_list(eid):
    def children(root):
        root.set("href", f"/edev/{eid}/fsa")
        root.set("all", "1")
        root.set("results", "1")
        fsa = elem("FunctionSetAssignments", attribs={"href": f"/edev/{eid}/fsa/0"})
        fsa.append(elem("mRID", f"FSA-{eid}"))
        fsa.append(elem("description", "Default FSA"))
        fsa.append(elem("DERProgramListLink", attribs={"href": f"/edev/{eid}/derp", "all": "1"}))
        fsa.append(elem("DemandResponseProgramListLink", attribs={"href": f"/edev/{eid}/dr", "all": "1"}))
        fsa.append(elem("TimeLink", attribs={"href": "/tm"}))
        root.append(fsa)
    return xml_response(build_xml("FunctionSetAssignmentsList", children))


# ---------------------------------------------------------------------------
# DER (Distributed Energy Resources)
# ---------------------------------------------------------------------------

@app.route("/edev/<eid>/der", methods=["GET", "POST"])
def der_list(eid):
    key = f"{eid}_ders"
    ders = store.ders.get(key, [])

    if request.method == "POST":
        did = str(uuid.uuid4())[:8]
        ders.append({"id": did, "href": f"/edev/{eid}/der/{did}", "changedTime": ts()})
        store.ders[key] = ders
        return xml_response(f'<sep:DER xmlns:sep="{SEP_NS}" href="/edev/{eid}/der/{did}"/>', 201)

    def children(root):
        root.set("href", f"/edev/{eid}/der")
        root.set("all", str(len(ders)))
        root.set("results", str(len(ders)))
        for d in ders:
            der = elem("DER", attribs={"href": d["href"]})
            der.append(elem("AssociatedDERProgramListLink", attribs={"href": f"{d['href']}/derp", "all": "0"}))
            der.append(elem("CurrentDERProgramLink", attribs={"href": f"{d['href']}/cdp"}))
            der.append(elem("DERAvailabilityLink", attribs={"href": f"{d['href']}/dera"}))
            der.append(elem("DERCapabilityLink", attribs={"href": f"{d['href']}/derc"}))
            der.append(elem("DERSettingsLink", attribs={"href": f"{d['href']}/ders"}))
            der.append(elem("DERStatusLink", attribs={"href": f"{d['href']}/derstatus"}))
            root.append(der)
    return xml_response(build_xml("DERList", children))


@app.route("/edev/<eid>/der/<did>/derc", methods=["GET", "PUT"])
def der_capability(eid, did):
    key = f"{eid}_{did}_cap"
    cap = store.der_capabilities.get(key, {
        "modesSupported": "3F",
        "rtgMaxW": store.limits.get("maxW", 10000),
        "rtgMaxVar": store.limits.get("maxVar", 5000),
        "rtgMaxVA": store.limits.get("maxVA", 11000),
        "rtgMaxChargeRateW": 7500,
        "rtgMaxDischargeRateW": 7500,
        "rtgMinPFOverExcited": 850,
        "rtgMinPFUnderExcited": 850,
        "type": "85"
    })

    if request.method == "PUT":
        store.der_capabilities[key] = cap
        return xml_response("", 204)

    def children(root):
        root.set("href", f"/edev/{eid}/der/{did}/derc")
        root.append(elem("modesSupported", cap["modesSupported"]))
        mw = elem("rtgMaxW"); mw.append(elem("multiplier", "-3")); mw.append(elem("value", str(cap["rtgMaxW"]))); root.append(mw)
        mv = elem("rtgMaxVar"); mv.append(elem("multiplier", "-3")); mv.append(elem("value", str(cap["rtgMaxVar"]))); root.append(mv)
        mva = elem("rtgMaxVA"); mva.append(elem("multiplier", "-3")); mva.append(elem("value", str(cap["rtgMaxVA"]))); root.append(mva)
        root.append(elem("type", cap["type"]))
    return xml_response(build_xml("DERCapability", children))


@app.route("/edev/<eid>/der/<did>/ders", methods=["GET", "PUT"])
def der_settings(eid, did):
    key = f"{eid}_{did}_settings"
    if request.method == "PUT":
        store.der_settings_store[key] = {"changedTime": ts(), "raw": request.data.decode()}
        return xml_response("", 204)

    settings = store.der_settings_store.get(key, {})
    lim = store.limits

    def children(root):
        root.set("href", f"/edev/{eid}/der/{did}/ders")
        root.append(elem("updatedTime", str(settings.get("changedTime", ts()))))
        mw = elem("setMaxW"); mw.append(elem("multiplier", "-3")); mw.append(elem("value", str(lim.get("maxW", 10000)))); root.append(mw)
        mv = elem("setMaxVar"); mv.append(elem("multiplier", "-3")); mv.append(elem("value", str(lim.get("maxVar", 5000)))); root.append(mv)
        mva = elem("setMaxVA"); mva.append(elem("multiplier", "-3")); mva.append(elem("value", str(lim.get("maxVA", 11000)))); root.append(mva)
        root.append(elem("setESDelay", "0"))
        root.append(elem("setESHighFreq", str(lim.get("highFreq", 6020))))
        root.append(elem("setESHighVolt", str(lim.get("highVolt", 12000))))
        root.append(elem("setESLowFreq", str(lim.get("lowFreq", 5970))))
        root.append(elem("setESLowVolt", str(lim.get("lowVolt", 10800))))
        root.append(elem("setESRampTms", "60"))
        root.append(elem("setESRandomDelay", "0"))
        root.append(elem("setGradW", str(lim.get("gradW", 1000))))
        root.append(elem("setSoftGradW", str(lim.get("softGradW", 500))))
    return xml_response(build_xml("DERSettings", children))


@app.route("/edev/<eid>/der/<did>/dera", methods=["GET", "PUT"])
def der_availability(eid, did):
    key = f"{eid}_{did}_avail"
    if request.method == "PUT":
        store.der_availability_store[key] = {"changedTime": ts(), "raw": request.data.decode()}
        store.add_log(f"DERAvailability updated for {eid}/{did}")
        return xml_response("", 204)

    avail = store.der_availability_store.get(key, {})
    def children(root):
        root.set("href", f"/edev/{eid}/der/{did}/dera")
        root.append(elem("availabilityDuration", str(avail.get("availabilityDuration", 3600))))
        root.append(elem("maxChargeDuration", str(avail.get("maxChargeDuration", 3600))))
        root.append(elem("readyTime", str(avail.get("readyTime", ts()))))
        root.append(elem("soc", str(avail.get("soc", 8000))))
        root.append(elem("statWAvail", str(avail.get("statWAvail", 5000))))
    return xml_response(build_xml("DERAvailability", children))


@app.route("/edev/<eid>/der/<did>/derstatus", methods=["GET", "PUT"])
def der_status(eid, did):
    key = f"{eid}_{did}_status"
    if request.method == "PUT":
        store.der_status_store[key] = {"changedTime": ts(), "raw": request.data.decode()}
        store.add_log(f"DERStatus updated for {eid}/{did}")
        return xml_response("", 204)

    status = store.der_status_store.get(key, {})
    def children(root):
        root.set("href", f"/edev/{eid}/der/{did}/derstatus")
        root.append(elem("changedTime", str(status.get("changedTime", ts()))))
        gs = elem("genConnectStatus"); gs.append(elem("dateTime", str(ts()))); gs.append(elem("value", "1")); root.append(gs)
        inv = elem("inverterStatus"); inv.append(elem("dateTime", str(ts()))); inv.append(elem("value", "1")); root.append(inv)
        ops = elem("operationalModeStatus"); ops.append(elem("dateTime", str(ts()))); ops.append(elem("value", "1")); root.append(ops)
        sc = elem("storConnectStatus"); sc.append(elem("dateTime", str(ts()))); sc.append(elem("value", "1")); root.append(sc)
    return xml_response(build_xml("DERStatus", children))


# ---------------------------------------------------------------------------
# DER Programs
# ---------------------------------------------------------------------------

@app.route("/derp", methods=["GET", "POST"])
def der_program_list():
    if request.method == "POST":
        pid = str(uuid.uuid4())[:8]
        store.der_programs[pid] = {
            "id": pid, "mRID": f"DERP-{pid}", "description": "Auto Program",
            "primacy": 1, "href": f"/derp/{pid}", "changedTime": ts()
        }
        return xml_response(f'<sep:DERProgram xmlns:sep="{SEP_NS}" href="/derp/{pid}"/>', 201)

    progs = list(store.der_programs.values())
    def children(root):
        root.set("href", "/derp")
        root.set("all", str(len(progs)))
        root.set("results", str(len(progs)))
        for p in progs:
            pr = elem("DERProgram", attribs={"href": p["href"]})
            pr.append(elem("mRID", p["mRID"]))
            pr.append(elem("description", p.get("description", "")))
            pr.append(elem("primacy", str(p.get("primacy", 1))))
            pr.append(elem("ActiveDERControlLink", attribs={"href": f"{p['href']}/acderc"}))
            pr.append(elem("DERControlListLink", attribs={"href": f"{p['href']}/derc", "all": "0"}))
            pr.append(elem("DERCurveListLink", attribs={"href": f"{p['href']}/dc", "all": "0"}))
            pr.append(elem("DefaultDERControlLink", attribs={"href": f"{p['href']}/dderc"}))
            root.append(pr)
    return xml_response(build_xml("DERProgramList", children))


@app.route("/derp/<pid>", methods=["GET", "DELETE"])
def der_program(pid):
    if request.method == "DELETE":
        store.der_programs.pop(pid, None)
        return xml_response("", 204)

    p = store.der_programs.get(pid)
    if not p:
        return xml_response("<sep:Error>Not Found</sep:Error>", 404)

    def children(root):
        root.set("href", p["href"])
        root.append(elem("mRID", p["mRID"]))
        root.append(elem("description", p.get("description", "")))
        root.append(elem("primacy", str(p.get("primacy", 1))))
        root.append(elem("ActiveDERControlLink", attribs={"href": f"{p['href']}/acderc"}))
        root.append(elem("DERControlListLink", attribs={"href": f"{p['href']}/derc", "all": "0"}))
        root.append(elem("DERCurveListLink", attribs={"href": f"{p['href']}/dc", "all": "0"}))
        root.append(elem("DefaultDERControlLink", attribs={"href": f"{p['href']}/dderc"}))
    return xml_response(build_xml("DERProgram", children))


@app.route("/derp/<pid>/dderc", methods=["GET", "PUT"])
def default_der_control(pid):
    key = f"{pid}_dderc"
    if request.method == "PUT":
        store.der_controls[key] = {"changedTime": ts(), "raw": request.data.decode()}
        return xml_response("", 204)

    lim = store.limits
    def children(root):
        root.set("href", f"/derp/{pid}/dderc")
        dc = elem("DERControlBase")
        opW = elem("opModConnect"); opW.text = "true"; dc.append(opW)
        mw = elem("opModMaxLimW"); mw.append(elem("multiplier", "-3")); mw.append(elem("value", str(lim.get("maxW", 10000)))); dc.append(mw)
        mv = elem("opModFixedVar"); mv.append(elem("refType", "0")); mv.append(elem("multiplier", "-3")); mv.append(elem("value", str(lim.get("maxVar", 0)))); dc.append(mv)
        root.append(dc)
    return xml_response(build_xml("DefaultDERControl", children))


@app.route("/derp/<pid>/derc", methods=["GET", "POST"])
def der_control_list(pid):
    key = f"{pid}_controls"
    controls = store.der_control_lists.get(key, [])

    if request.method == "POST":
        cid = str(uuid.uuid4())[:8]
        controls.append({"id": cid, "href": f"/derp/{pid}/derc/{cid}", "mRID": f"DERC-{cid}", "changedTime": ts()})
        store.der_control_lists[key] = controls
        return xml_response(f'<sep:DERControl xmlns:sep="{SEP_NS}" href="/derp/{pid}/derc/{cid}"/>', 201)

    def children(root):
        root.set("href", f"/derp/{pid}/derc")
        root.set("all", str(len(controls)))
        root.set("results", str(len(controls)))
        for c in controls:
            ctrl = elem("DERControl", attribs={"href": c["href"]})
            ctrl.append(elem("mRID", c["mRID"]))
            ctrl.append(elem("deviceCategory", "FFFFFFFF"))
            ctrl.append(elem("interval"))
            root.append(ctrl)
    return xml_response(build_xml("DERControlList", children))


# ---------------------------------------------------------------------------
# Mirror Usage Points (MUP) — client posts meter readings here
# ---------------------------------------------------------------------------

@app.route("/mup", methods=["GET", "POST"])
def mirror_usage_point_list():
    if request.method == "POST":
        mid = str(uuid.uuid4())[:8]
        body = request.data.decode()
        store.mirror_usage_points[mid] = {
            "id": mid, "href": f"/mup/{mid}",
            "mRID": f"MUP-{mid}", "description": "Mirror Usage Point",
            "deviceLFDI": "unknown", "changedTime": ts(), "raw": body,
        }
        store.add_log(f"MirrorUsagePoint created: {mid}")
        resp = f'<sep:MirrorUsagePoint xmlns:sep="{SEP_NS}" href="/mup/{mid}"/>'
        return xml_response(resp, 201)

    mups = list(store.mirror_usage_points.values())
    def children(root):
        root.set("href", "/mup")
        root.set("all", str(len(mups)))
        root.set("results", str(len(mups)))
        for m in mups:
            mu = elem("MirrorUsagePoint", attribs={"href": m["href"]})
            mu.append(elem("mRID", m["mRID"]))
            mu.append(elem("description", m.get("description", "")))
            mu.append(elem("deviceLFDI", m.get("deviceLFDI", "")))
            mu.append(elem("MirrorMeterReadingListLink", attribs={"href": f"{m['href']}/mr", "all": str(len(store.meter_readings.get(m['id'], [])))}))
            root.append(mu)
    return xml_response(build_xml("MirrorUsagePointList", children))


@app.route("/mup/<mid>", methods=["GET", "DELETE"])
def mirror_usage_point(mid):
    if request.method == "DELETE":
        store.mirror_usage_points.pop(mid, None)
        return xml_response("", 204)

    m = store.mirror_usage_points.get(mid)
    if not m:
        return xml_response("<sep:Error>Not Found</sep:Error>", 404)

    def children(root):
        root.set("href", m["href"])
        root.append(elem("mRID", m["mRID"]))
        root.append(elem("description", m.get("description", "")))
        root.append(elem("deviceLFDI", m.get("deviceLFDI", "")))
        root.append(elem("MirrorMeterReadingListLink", attribs={"href": f"{m['href']}/mr", "all": str(len(store.meter_readings.get(mid, [])))}))
    return xml_response(build_xml("MirrorUsagePoint", children))


@app.route("/mup/<mid>/mr", methods=["GET", "POST"])
def mirror_meter_reading_list(mid):
    readings = store.meter_readings.get(mid, [])

    if request.method == "POST":
        body = request.data.decode()
        rid = str(uuid.uuid4())[:8]
        reading = {
            "id": rid,
            "href": f"/mup/{mid}/mr/{rid}",
            "mRID": f"MR-{rid}",
            "raw": body,
            "timestamp": ts(),
            "mupId": mid,
        }
        # Try to parse key values from XML
        try:
            ns = {"sep": SEP_NS}
            root_el = ET.fromstring(body)
            tag = root_el.tag.split("}")[-1] if "}" in root_el.tag else root_el.tag

            def find_val(el, *paths):
                for p in paths:
                    f = el.find(p, ns)
                    if f is not None and f.text:
                        return f.text
                return None

            reading["value"] = find_val(root_el, ".//sep:value", ".//sep:ReadingValue")
            reading["uom"] = find_val(root_el, ".//sep:uom")
            reading["description"] = find_val(root_el, "sep:description") or tag
            reading["multiplier"] = find_val(root_el, ".//sep:multiplier") or "0"
        except Exception:
            pass

        if mid not in store.meter_readings:
            store.meter_readings[mid] = []
        store.meter_readings[mid].append(reading)

        # Also store in global telemetry timeline
        store.add_telemetry({
            "mupId": mid,
            "readingId": rid,
            "value": reading.get("value"),
            "uom": reading.get("uom"),
            "description": reading.get("description", "Reading"),
            "multiplier": reading.get("multiplier", "0"),
            "timestamp": ts(),
        })
        store.add_log(f"MeterReading posted to MUP {mid}: value={reading.get('value')} uom={reading.get('uom')}")
        return xml_response(f'<sep:MirrorMeterReading xmlns:sep="{SEP_NS}" href="/mup/{mid}/mr/{rid}"/>', 201)

    def children(root):
        root.set("href", f"/mup/{mid}/mr")
        root.set("all", str(len(readings)))
        root.set("results", str(len(readings)))
        for r in readings:
            mr = elem("MirrorMeterReading", attribs={"href": r["href"]})
            mr.append(elem("mRID", r["mRID"]))
            if r.get("description"):
                mr.append(elem("description", r["description"]))
            root.append(mr)
    return xml_response(build_xml("MirrorMeterReadingList", children))


@app.route("/mup/<mid>/mr/<rid>", methods=["GET"])
def mirror_meter_reading(mid, rid):
    readings = store.meter_readings.get(mid, [])
    r = next((x for x in readings if x["id"] == rid), None)
    if not r:
        return xml_response("<sep:Error>Not Found</sep:Error>", 404)

    def children(root):
        root.set("href", r["href"])
        root.append(elem("mRID", r["mRID"]))
        if r.get("description"):
            root.append(elem("description", r["description"]))
        if r.get("value"):
            reading = elem("Reading")
            reading.append(elem("value", r["value"]))
            if r.get("uom"):
                reading.append(elem("uom", r["uom"]))
            root.append(reading)
    return xml_response(build_xml("MirrorMeterReading", children))


# ---------------------------------------------------------------------------
# Demand Response
# ---------------------------------------------------------------------------

@app.route("/dr", methods=["GET"])
def demand_response_list():
    progs = list(store.dr_programs.values())
    def children(root):
        root.set("href", "/dr")
        root.set("all", str(len(progs)))
        root.set("results", str(len(progs)))
        for p in progs:
            pr = elem("DemandResponseProgram", attribs={"href": p["href"]})
            pr.append(elem("mRID", p["mRID"]))
            pr.append(elem("description", p.get("description", "")))
            pr.append(elem("primacy", str(p.get("primacy", 1))))
            pr.append(elem("ActiveEndDeviceControlListLink", attribs={"href": f"{p['href']}/aedc", "all": "0"}))
            pr.append(elem("EndDeviceControlListLink", attribs={"href": f"{p['href']}/edc", "all": "0"}))
            root.append(pr)
    return xml_response(build_xml("DemandResponseProgramList", children))


@app.route("/dr/<pid>", methods=["GET"])
def demand_response_program(pid):
    p = store.dr_programs.get(pid)
    if not p:
        return xml_response("<sep:Error>Not Found</sep:Error>", 404)

    def children(root):
        root.set("href", p["href"])
        root.append(elem("mRID", p["mRID"]))
        root.append(elem("description", p.get("description", "")))
        root.append(elem("primacy", str(p.get("primacy", 1))))
    return xml_response(build_xml("DemandResponseProgram", children))


@app.route("/dr/<pid>/edc", methods=["GET", "POST"])
def end_device_control_list(pid):
    key = f"{pid}_edcs"
    edcs = store.end_device_controls.get(key, [])

    if request.method == "POST":
        cid = str(uuid.uuid4())[:8]
        edcs.append({
            "id": cid,
            "href": f"/dr/{pid}/edc/{cid}",
            "mRID": f"EDC-{cid}",
            "deviceCategory": "FFFFFFFF",
            "changedTime": ts(),
            "raw": request.data.decode()
        })
        store.end_device_controls[key] = edcs
        return xml_response(f'<sep:EndDeviceControl xmlns:sep="{SEP_NS}" href="/dr/{pid}/edc/{cid}"/>', 201)

    def children(root):
        root.set("href", f"/dr/{pid}/edc")
        root.set("all", str(len(edcs)))
        root.set("results", str(len(edcs)))
        for c in edcs:
            ctrl = elem("EndDeviceControl", attribs={"href": c["href"]})
            ctrl.append(elem("mRID", c["mRID"]))
            ctrl.append(elem("deviceCategory", c.get("deviceCategory", "FFFFFFFF")))
            root.append(ctrl)
    return xml_response(build_xml("EndDeviceControlList", children))


# ---------------------------------------------------------------------------
# Usage Point / Meter Reading (server-side, read only)
# ---------------------------------------------------------------------------

@app.route("/upt", methods=["GET"])
def usage_point_list():
    def children(root):
        root.set("href", "/upt")
        root.set("all", "0")
        root.set("results", "0")
    return xml_response(build_xml("UsagePointList", children))


# ---------------------------------------------------------------------------
# Log Events
# ---------------------------------------------------------------------------

@app.route("/lel", methods=["GET"])
def log_event_list():
    events = list(store.log_events)
    start = int(request.args.get("s", 0))
    limit = int(request.args.get("l", 255))
    page = events[start:start + limit]

    def children(root):
        root.set("href", "/lel")
        root.set("all", str(len(events)))
        root.set("results", str(len(page)))
        for e in reversed(page):
            le = elem("LogEvent", attribs={"href": f"/lel/{e['id']}"})
            le.append(elem("createdDateTime", str(e["timestamp"])))
            le.append(elem("details", e["message"]))
            le.append(elem("logEventCode", "1"))
            le.append(elem("logEventID", str(e["id"])))
            le.append(elem("profileID", "0"))
            le.append(elem("extendedData", "0"))
            root.append(le)
    return xml_response(build_xml("LogEventList", children))


# ---------------------------------------------------------------------------
# Subscription / Notification (stub — IEEE 2030.5 §10)
# ---------------------------------------------------------------------------

@app.route("/sub", methods=["GET", "POST"])
def subscription_list():
    if request.method == "POST":
        sid = str(uuid.uuid4())[:8]
        store.subscriptions[sid] = {
            "id": sid, "href": f"/sub/{sid}",
            "subscribedResource": request.args.get("res", "/"),
            "notificationURI": request.args.get("uri", ""),
            "changedTime": ts(),
        }
        return xml_response(f'<sep:Subscription xmlns:sep="{SEP_NS}" href="/sub/{sid}"/>', 201)

    subs = list(store.subscriptions.values())
    def children(root):
        root.set("href", "/sub")
        root.set("all", str(len(subs)))
        root.set("results", str(len(subs)))
        for s in subs:
            sub = elem("Subscription", attribs={"href": s["href"]})
            sub.append(elem("subscribedResource", s["subscribedResource"]))
            sub.append(elem("notificationURI", s["notificationURI"]))
            root.append(sub)
    return xml_response(build_xml("SubscriptionList", children))


@app.route("/sub/<sid>", methods=["GET", "DELETE"])
def subscription(sid):
    if request.method == "DELETE":
        store.subscriptions.pop(sid, None)
        return xml_response("", 204)
    s = store.subscriptions.get(sid)
    if not s:
        return xml_response("<sep:Error>Not Found</sep:Error>", 404)

    def children(root):
        root.set("href", s["href"])
        root.append(elem("subscribedResource", s["subscribedResource"]))
        root.append(elem("notificationURI", s["notificationURI"]))
    return xml_response(build_xml("Subscription", children))


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------

@app.route("/pricep", methods=["GET"])
def pricing_program_list():
    def children(root):
        root.set("href", "/pricep")
        root.set("all", "0")
        root.set("results", "0")
    return xml_response(build_xml("TariffProfileList", children))


# ---------------------------------------------------------------------------
# Messaging
# ---------------------------------------------------------------------------

@app.route("/msg", methods=["GET"])
def messaging_program_list():
    msgs = list(store.messages.values())
    def children(root):
        root.set("href", "/msg")
        root.set("all", str(len(msgs)))
        root.set("results", str(len(msgs)))
        for m in msgs:
            me = elem("TextMessage", attribs={"href": m["href"]})
            me.append(elem("mRID", m["mRID"]))
            me.append(elem("createdDateTime", str(m["createdDateTime"])))
            me.append(elem("message", m["message"]))
            me.append(elem("priority", str(m.get("priority", 0))))
            root.append(me)
    return xml_response(build_xml("MessagingProgramList", children))


@app.route("/msg", methods=["POST"])
def create_message():
    mid = str(uuid.uuid4())[:8]
    body = request.data.decode()
    store.messages[mid] = {
        "id": mid, "href": f"/msg/{mid}", "mRID": f"MSG-{mid}",
        "message": body or "Server message", "priority": 0,
        "createdDateTime": ts(),
    }
    return xml_response(f'<sep:TextMessage xmlns:sep="{SEP_NS}" href="/msg/{mid}"/>', 201)


# ---------------------------------------------------------------------------
# Response Set
# ---------------------------------------------------------------------------

@app.route("/rsps", methods=["GET"])
def response_set_list():
    def children(root):
        root.set("href", "/rsps")
        root.set("all", "0")
        root.set("results", "0")
    return xml_response(build_xml("ResponseSetList", children))


@app.route("/rsps/<rsid>/rsp", methods=["POST"])
def create_response(rsid):
    rid = str(uuid.uuid4())[:8]
    store.responses.append({"id": rid, "rsid": rsid, "raw": request.data.decode(), "timestamp": ts()})
    store.add_log(f"Response received for ResponseSet {rsid}")
    return xml_response(f'<sep:Response xmlns:sep="{SEP_NS}" href="/rsps/{rsid}/rsp/{rid}"/>', 201)


# ---------------------------------------------------------------------------
# Flow Reservation (IEEE 2030.5 §13)
# ---------------------------------------------------------------------------

@app.route("/frp", methods=["GET"])
def flow_reservation_list():
    def children(root):
        root.set("href", "/frp")
        root.set("all", "0")
        root.set("results", "0")
    return xml_response(build_xml("FlowReservationRequestList", children))


# ---------------------------------------------------------------------------
# Dashboard API endpoints
# ---------------------------------------------------------------------------

@app.route("/api/telemetry", methods=["GET"])
def api_telemetry():
    """Return recent telemetry as JSON for the dashboard."""
    limit = int(request.args.get("limit", 200))
    data = list(store.telemetry)[-limit:]
    return jsonify({
        "telemetry": data,
        "limits": store.limits,
        "endDeviceCount": len(store.end_devices),
        "mupCount": len(store.mirror_usage_points),
        "logCount": len(store.log_events),
        "serverTime": ts(),
    })


@app.route("/api/limits", methods=["GET", "POST"])
def api_limits():
    """Get or update power limits."""
    if request.method == "POST":
        data = request.get_json(force=True)
        for k in ("maxW", "maxVar", "maxVA", "highFreq", "lowFreq", "highVolt", "lowVolt", "gradW", "softGradW"):
            if k in data:
                store.limits[k] = int(data[k])
        store.add_log(f"Limits updated: {data}")
        return jsonify({"status": "ok", "limits": store.limits})
    return jsonify(store.limits)


@app.route("/api/logs", methods=["GET"])
def api_logs():
    limit = int(request.args.get("limit", 100))
    return jsonify({"logs": list(store.log_events)[-limit:]})


@app.route("/api/devices", methods=["GET"])
def api_devices():
    # Enrich end devices with their registration record
    devices = []
    for d in store.end_devices.values():
        dev = dict(d)
        reg = store.registrations.get(d["id"])
        if reg:
            dev["pin"] = reg["pIN"]
            dev["registrationStatus"] = reg.get("status", "pending")
            dev["dateTimeRegistered"] = reg.get("dateTimeRegistered")
        devices.append(dev)
    return jsonify({
        "endDevices": devices,
        "mirrorUsagePoints": list(store.mirror_usage_points.values()),
    })


@app.route("/api/devices/<eid>/approve", methods=["POST"])
def api_approve_device(eid):
    """Dashboard shortcut: manually approve a device without PIN check."""
    d = store.end_devices.get(eid)
    if not d:
        return jsonify({"error": "not found"}), 404
    reg = store.registrations.get(eid, {})
    reg["status"] = "confirmed"
    reg["dateTimeRegistered"] = ts()
    store.registrations[eid] = reg
    store.end_devices[eid]["enabled"] = True
    store.end_devices[eid]["registrationStatus"] = "confirmed"
    store.add_log(f"EndDevice {eid} manually approved via dashboard")
    return jsonify({"status": "ok"})


@app.route("/api/devices/<eid>/reject", methods=["POST"])
def api_reject_device(eid):
    """Dashboard shortcut: reject / disable a device."""
    d = store.end_devices.get(eid)
    if not d:
        return jsonify({"error": "not found"}), 404
    reg = store.registrations.get(eid, {})
    reg["status"] = "rejected"
    store.registrations[eid] = reg
    store.end_devices[eid]["enabled"] = False
    store.end_devices[eid]["registrationStatus"] = "rejected"
    store.add_log(f"EndDevice {eid} rejected via dashboard")
    return jsonify({"status": "ok"})


@app.route("/api/devices/<eid>/regenerate_pin", methods=["POST"])
def api_regenerate_pin(eid):
    """Issue a new PIN for a device (resets status to pending)."""
    import random
    d = store.end_devices.get(eid)
    if not d:
        return jsonify({"error": "not found"}), 404
    pin = str(random.randint(100000, 999999))
    reg = store.registrations.get(eid, {})
    reg["pIN"] = pin
    reg["status"] = "pending"
    store.registrations[eid] = reg
    store.end_devices[eid]["enabled"] = False
    store.end_devices[eid]["registrationStatus"] = "pending"
    store.add_log(f"EndDevice {eid} PIN regenerated")
    return jsonify({"status": "ok", "pin": pin})


@app.route("/api/readings/<mid>", methods=["GET"])
def api_readings(mid):
    return jsonify({"readings": store.meter_readings.get(mid, [])})


@app.route("/api/send_message", methods=["POST"])
def api_send_message():
    data = request.get_json(force=True)
    mid = str(uuid.uuid4())[:8]
    store.messages[mid] = {
        "id": mid, "href": f"/msg/{mid}", "mRID": f"MSG-{mid}",
        "message": data.get("message", ""), "priority": data.get("priority", 0),
        "createdDateTime": ts(),
    }
    store.add_log(f"Dashboard message queued: {data.get('message', '')}")
    return jsonify({"status": "ok", "id": mid})


# ---------------------------------------------------------------------------
# Dashboard Web UI
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
@app.route("/dashboard", methods=["GET"])
def dashboard():
    return render_template("dashboard.html")


# ---------------------------------------------------------------------------
# Catch-all: return 404 in SEP XML
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return xml_response(f'<sep:Error xmlns:sep="{SEP_NS}"><sep:message>Not Found</sep:message></sep:Error>', 404)


@app.errorhandler(405)
def method_not_allowed(e):
    return xml_response(f'<sep:Error xmlns:sep="{SEP_NS}"><sep:message>Method Not Allowed</sep:message></sep:Error>', 405)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)

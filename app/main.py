"""
IEEE 2030.5 (SEP 2.0) Test Server
Full implementation of all major resource endpoints per the IEEE 2030.5 standard.
No mTLS — plain HTTP for local testing.
"""

from flask import Flask, request, jsonify, render_template, Response
import xml.etree.ElementTree as ET
import xml.dom.minidom
import uuid
import time
import random
from collections import deque

try:
    from store import DataStore
except ImportError:
    from app.store import DataStore

app = Flask(__name__, template_folder="../templates", static_folder="../static")

store = DataStore()

SEP_NS = "urn:ieee:std:2030.5:ns"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ts():
    return int(time.time())


def elem(tag, text=None, attribs=None, ns=SEP_NS):
    e = ET.Element(f"{{{ns}}}{tag}", attribs or {})
    if text is not None:
        e.text = str(text)
    return e


def build_xml(tag, children_fn, attribs=None, ns=SEP_NS):
    root = ET.Element(f"{{{ns}}}{tag}", attribs or {})
    if children_fn:
        children_fn(root)
    raw = ET.tostring(root, encoding="unicode")
    try:
        pretty = xml.dom.minidom.parseString(raw).toprettyxml(indent="  ")
        return "\n".join(pretty.split("\n")[1:])
    except Exception:
        return raw


def xml_response(xml_str, status=200):
    return Response(xml_str, status=status, mimetype="application/sep+xml")


def parse_xml_body():
    """Parse request body as XML, return root element or None."""
    try:
        return ET.fromstring(request.data.decode())
    except Exception:
        return None


def xml_find(root, tag):
    """Find child element by local tag name, ignoring namespace."""
    if root is None:
        return None
    ns_map = {"sep": SEP_NS}
    el = root.find(f"sep:{tag}", ns_map)
    if el is not None:
        return el
    # fallback: search by local name
    for child in root:
        local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if local == tag:
            return child
    return None


def xml_val(root, tag, default=None):
    el = xml_find(root, tag)
    return el.text.strip() if (el is not None and el.text) else default


def power_elem(root, tag, value, multiplier="-3"):
    """Append a UnitValueType child (value + multiplier)."""
    e = elem(tag)
    e.append(elem("multiplier", multiplier))
    e.append(elem("value", str(value)))
    root.append(e)


def not_found_xml():
    return xml_response(f'<sep:Error xmlns:sep="{SEP_NS}"><sep:message>Not Found</sep:message></sep:Error>', 404)


# ---------------------------------------------------------------------------
# 1. Device Capability (entry point)
# ---------------------------------------------------------------------------

@app.route("/dcap", methods=["GET"])
def device_capability():
    def c(root):
        root.set("href", "/dcap")
        root.append(elem("pollRate", "900"))
        root.append(elem("EndDeviceListLink",        attribs={"href": "/edev",   "all": str(len(store.end_devices))}))
        root.append(elem("MirrorUsagePointListLink", attribs={"href": "/mup",    "all": str(len(store.mirror_usage_points))}))
        root.append(elem("SelfDeviceLink",           attribs={"href": "/sdev"}))
        root.append(elem("TimeLink",                 attribs={"href": "/tm"}))
        root.append(elem("DERProgramListLink",       attribs={"href": "/derp",   "all": str(len(store.der_programs))}))
        root.append(elem("DemandResponseProgramListLink", attribs={"href": "/dr", "all": str(len(store.dr_programs))}))
        root.append(elem("TariffProfileListLink",    attribs={"href": "/pricep", "all": str(len(store.tariff_profiles))}))
        root.append(elem("MessagingProgramListLink", attribs={"href": "/msg",    "all": str(len(store.messages))}))
        root.append(elem("ResponseSetListLink",      attribs={"href": "/rsps",   "all": str(len(store.response_sets))}))
        root.append(elem("LogEventListLink",         attribs={"href": "/lel",    "all": str(len(store.log_events))}))
        root.append(elem("UsagePointListLink",       attribs={"href": "/upt",    "all": str(len(store.usage_points))}))
        root.append(elem("PrepaymentListLink",       attribs={"href": "/ppy",    "all": str(len(store.prepayments))}))
        root.append(elem("FlowReservationRequestListLink", attribs={"href": "/frp", "all": str(len(store.flow_reservations))}))
    return xml_response(build_xml("DeviceCapability", c))


# ---------------------------------------------------------------------------
# 2. Time
# ---------------------------------------------------------------------------

@app.route("/tm", methods=["GET"])
def time_resource():
    now = ts()
    def c(root):
        root.set("href", "/tm")
        root.append(elem("currentTime",  str(now)))
        root.append(elem("dstEndTime",   str(now + 86400 * 180)))
        root.append(elem("dstOffset",    "3600"))
        root.append(elem("dstStartTime", str(now - 86400 * 180)))
        root.append(elem("localTime",    str(now)))
        root.append(elem("quality",      "7"))
        root.append(elem("tzOffset",     "0"))
    return xml_response(build_xml("Time", c))


# ---------------------------------------------------------------------------
# 3. Self Device
# ---------------------------------------------------------------------------

@app.route("/sdev", methods=["GET"])
def self_device():
    def c(root):
        root.set("href", "/sdev")
        root.append(elem("sFDI", store.server_sfdi))
        root.append(elem("lFDI", store.server_lfdi))
        root.append(elem("DeviceInformationLink", attribs={"href": "/sdev/di"}))
        root.append(elem("DeviceStatusLink",      attribs={"href": "/sdev/dstat"}))
        root.append(elem("PowerStatusLink",       attribs={"href": "/sdev/ps"}))
        root.append(elem("LogEventListLink",      attribs={"href": "/sdev/lel", "all": str(len(store.log_events))}))
    return xml_response(build_xml("SelfDevice", c))


@app.route("/sdev/di", methods=["GET"])
def self_device_info():
    def c(root):
        root.set("href", "/sdev/di")
        root.append(elem("mfHwVer",      "1.0"))
        root.append(elem("mfID",         "65535"))
        root.append(elem("mfInfo",       "IEEE2030.5 Test Server"))
        root.append(elem("mfModel",      "TestServer"))
        root.append(elem("mfSerNum",     "SN-TEST-001"))
        root.append(elem("mfSwVer",      "1.0.0"))
        root.append(elem("primaryPower", "1"))
        root.append(elem("secondaryPower","0"))
    return xml_response(build_xml("DeviceInformation", c))


@app.route("/sdev/dstat", methods=["GET"])
def self_device_status():
    def c(root):
        root.set("href", "/sdev/dstat")
        root.append(elem("changedTime", str(ts())))
        root.append(elem("onCount",     "1"))
        root.append(elem("opState",     "1"))
        root.append(elem("opTime",      str(ts() - store.start_time)))
    return xml_response(build_xml("DeviceStatus", c))


@app.route("/sdev/ps", methods=["GET"])
def self_power_status():
    ps = store.power_status
    def c(root):
        root.set("href", "/sdev/ps")
        root.append(elem("currentPowerSource",       "1"))
        root.append(elem("estimatedChargeRemaining", str(ps.get("estimatedChargeRemaining", 10000))))
        root.append(elem("estimatedTimeRemaining",   str(ps.get("estimatedTimeRemaining", 3600))))
        root.append(elem("sessionTimeOnBattery",     "0"))
        root.append(elem("totalTimeOnBattery",       "0"))
    return xml_response(build_xml("PowerStatus", c))


@app.route("/sdev/lel", methods=["GET"])
def self_log_event_list():
    return _log_event_list_response("/sdev/lel", list(store.log_events))


# ---------------------------------------------------------------------------
# 4. End Device List
# ---------------------------------------------------------------------------

@app.route("/edev", methods=["GET", "POST"])
def end_device_list():
    if request.method == "POST":
        eid  = str(uuid.uuid4())[:8]
        body = request.data.decode()
        lfdi = f"LFDI-{eid}"
        sfdi = str(int(uuid.uuid4().int % 281474976710655))
        root_el = parse_xml_body()
        if root_el is not None:
            lfdi = xml_val(root_el, "lFDI", lfdi)
            sfdi = xml_val(root_el, "sFDI", sfdi)

        store.end_devices[eid] = {
            "id": eid, "href": f"/edev/{eid}",
            "lFDI": lfdi, "sFDI": sfdi,
            "changedTime": ts(), "enabled": False,
            "registrationStatus": "pending", "raw": body,
        }
        pin = str(random.randint(100000, 999999))
        store.registrations[eid] = {
            "dateTimeRegistered": ts(), "pIN": pin,
            "status": "pending", "eid": eid,
        }
        store.add_log(f"EndDevice registered (pending): {eid} lFDI={lfdi} PIN={pin}")
        return xml_response(f'<sep:EndDevice xmlns:sep="{SEP_NS}" href="/edev/{eid}"/>', 201)

    start = int(request.args.get("s", 0))
    limit = int(request.args.get("l", 255))
    devs  = list(store.end_devices.values())[start:start + limit]

    def c(root):
        root.set("href", "/edev")
        root.set("all",     str(len(store.end_devices)))
        root.set("results", str(len(devs)))
        for d in devs:
            _edev_elem(root, d)
    return xml_response(build_xml("EndDeviceList", c))


def _edev_elem(parent, d):
    eid = d["id"]
    ed  = elem("EndDevice", attribs={"href": d["href"]})
    ed.append(elem("lFDI",        d["lFDI"]))
    ed.append(elem("sFDI",        d["sFDI"]))
    ed.append(elem("changedTime", str(d["changedTime"])))
    ed.append(elem("enabled",     "true" if d.get("enabled") else "false"))
    ed.append(elem("RegistrationLink",              attribs={"href": f"/edev/{eid}/reg"}))
    ed.append(elem("DeviceInformationLink",         attribs={"href": f"/edev/{eid}/di"}))
    ed.append(elem("DeviceStatusLink",              attribs={"href": f"/edev/{eid}/dstat"}))
    ed.append(elem("PowerStatusLink",               attribs={"href": f"/edev/{eid}/ps"}))
    ed.append(elem("FunctionSetAssignmentsListLink",attribs={"href": f"/edev/{eid}/fsa", "all": "1"}))
    ed.append(elem("DERListLink",                   attribs={"href": f"/edev/{eid}/der", "all": str(len(store.ders.get(f"{eid}_ders", [])))}))
    ed.append(elem("LogEventListLink",              attribs={"href": f"/edev/{eid}/lel", "all": "0"}))
    ed.append(elem("SubscriptionListLink",          attribs={"href": f"/edev/{eid}/sub", "all": "0"}))
    parent.append(ed)


@app.route("/edev/<eid>", methods=["GET", "PUT", "DELETE"])
def end_device(eid):
    if request.method == "DELETE":
        store.end_devices.pop(eid, None)
        store.registrations.pop(eid, None)
        store.add_log(f"EndDevice {eid} deleted")
        return xml_response("", 204)
    if request.method == "PUT":
        d = store.end_devices.get(eid, {"id": eid, "href": f"/edev/{eid}", "lFDI": "", "sFDI": "", "changedTime": ts(), "enabled": False, "registrationStatus": "pending"})
        root_el = parse_xml_body()
        if root_el is not None:
            en = xml_val(root_el, "enabled")
            if en is not None:
                d["enabled"] = en.lower() == "true"
        d["changedTime"] = ts()
        store.end_devices[eid] = d
        return xml_response("", 204)

    d = store.end_devices.get(eid)
    if not d:
        return not_found_xml()

    def c(root):
        _edev_elem(root, d)
    # build_xml wraps in EndDeviceList — build manually here
    root_el = ET.Element(f"{{{SEP_NS}}}EndDevice", {"href": d["href"]})
    root_el.append(elem("lFDI",        d["lFDI"]))
    root_el.append(elem("sFDI",        d["sFDI"]))
    root_el.append(elem("changedTime", str(d["changedTime"])))
    root_el.append(elem("enabled",     "true" if d.get("enabled") else "false"))
    root_el.append(elem("RegistrationLink",               attribs={"href": f"/edev/{eid}/reg"}))
    root_el.append(elem("DeviceInformationLink",          attribs={"href": f"/edev/{eid}/di"}))
    root_el.append(elem("DeviceStatusLink",               attribs={"href": f"/edev/{eid}/dstat"}))
    root_el.append(elem("PowerStatusLink",                attribs={"href": f"/edev/{eid}/ps"}))
    root_el.append(elem("FunctionSetAssignmentsListLink", attribs={"href": f"/edev/{eid}/fsa", "all": "1"}))
    root_el.append(elem("DERListLink",                    attribs={"href": f"/edev/{eid}/der", "all": str(len(store.ders.get(f"{eid}_ders", [])))}))
    root_el.append(elem("LogEventListLink",               attribs={"href": f"/edev/{eid}/lel", "all": "0"}))
    root_el.append(elem("SubscriptionListLink",           attribs={"href": f"/edev/{eid}/sub", "all": "0"}))
    raw = ET.tostring(root_el, encoding="unicode")
    try:
        pretty = xml.dom.minidom.parseString(raw).toprettyxml(indent="  ")
        return xml_response("\n".join(pretty.split("\n")[1:]))
    except Exception:
        return xml_response(raw)


# ---------------------------------------------------------------------------
# 4a. Per-device sub-resources
# ---------------------------------------------------------------------------

@app.route("/edev/<eid>/di", methods=["GET", "PUT"])
def edev_device_info(eid):
    if eid not in store.end_devices:
        return not_found_xml()
    key  = f"{eid}_di"
    info = store.edev_device_info.get(key, {})
    if request.method == "PUT":
        root_el = parse_xml_body()
        if root_el is not None:
            for tag in ("mfHwVer","mfID","mfInfo","mfModel","mfSerNum","mfSwVer","primaryPower","secondaryPower"):
                v = xml_val(root_el, tag)
                if v: info[tag] = v
        store.edev_device_info[key] = info
        return xml_response("", 204)
    def c(root):
        root.set("href", f"/edev/{eid}/di")
        root.append(elem("mfHwVer",       info.get("mfHwVer",  "1.0")))
        root.append(elem("mfID",          info.get("mfID",     "0")))
        root.append(elem("mfInfo",        info.get("mfInfo",   "")))
        root.append(elem("mfModel",       info.get("mfModel",  "")))
        root.append(elem("mfSerNum",      info.get("mfSerNum", "")))
        root.append(elem("mfSwVer",       info.get("mfSwVer",  "")))
        root.append(elem("primaryPower",  info.get("primaryPower", "1")))
        root.append(elem("secondaryPower",info.get("secondaryPower","0")))
    return xml_response(build_xml("DeviceInformation", c))


@app.route("/edev/<eid>/dstat", methods=["GET"])
def edev_device_status(eid):
    if eid not in store.end_devices:
        return not_found_xml()
    key  = f"{eid}_dstat"
    stat = store.edev_device_status.get(key, {})
    def c(root):
        root.set("href", f"/edev/{eid}/dstat")
        root.append(elem("changedTime", str(stat.get("changedTime", ts()))))
        root.append(elem("onCount",     str(stat.get("onCount", 0))))
        root.append(elem("opState",     str(stat.get("opState", 0))))
        root.append(elem("opTime",      str(stat.get("opTime",  0))))
    return xml_response(build_xml("DeviceStatus", c))


@app.route("/edev/<eid>/ps", methods=["GET", "PUT"])
def edev_power_status(eid):
    if eid not in store.end_devices:
        return not_found_xml()
    key = f"{eid}_ps"
    ps  = store.edev_power_status.get(key, {})
    if request.method == "PUT":
        root_el = parse_xml_body()
        if root_el is not None:
            for tag in ("currentPowerSource","estimatedChargeRemaining","estimatedTimeRemaining"):
                v = xml_val(root_el, tag)
                if v: ps[tag] = v
        store.edev_power_status[key] = ps
        store.add_log(f"PowerStatus updated for EndDevice {eid}")
        return xml_response("", 204)
    def c(root):
        root.set("href", f"/edev/{eid}/ps")
        root.append(elem("currentPowerSource",       str(ps.get("currentPowerSource", "1"))))
        root.append(elem("estimatedChargeRemaining", str(ps.get("estimatedChargeRemaining", 0))))
        root.append(elem("estimatedTimeRemaining",   str(ps.get("estimatedTimeRemaining", 0))))
        root.append(elem("sessionTimeOnBattery",     "0"))
        root.append(elem("totalTimeOnBattery",       "0"))
    return xml_response(build_xml("PowerStatus", c))


@app.route("/edev/<eid>/lel", methods=["GET"])
def edev_log_event_list(eid):
    if eid not in store.end_devices:
        return not_found_xml()
    events = [e for e in store.log_events if eid in e.get("message", "")]
    return _log_event_list_response(f"/edev/{eid}/lel", events)


@app.route("/edev/<eid>/sub", methods=["GET"])
def edev_subscription_list(eid):
    if eid not in store.end_devices:
        return not_found_xml()
    subs = [s for s in store.subscriptions.values() if s.get("eid") == eid]
    def c(root):
        root.set("href", f"/edev/{eid}/sub")
        root.set("all",     str(len(subs)))
        root.set("results", str(len(subs)))
        for s in subs:
            sub = elem("Subscription", attribs={"href": s["href"]})
            sub.append(elem("subscribedResource", s["subscribedResource"]))
            sub.append(elem("notificationURI",    s["notificationURI"]))
            root.append(sub)
    return xml_response(build_xml("SubscriptionList", c))


# ---------------------------------------------------------------------------
# 5. Registration
# ---------------------------------------------------------------------------

@app.route("/edev/<eid>/reg", methods=["GET", "PUT"])
def end_device_registration(eid):
    d = store.end_devices.get(eid)
    if not d:
        return not_found_xml()

    reg = store.registrations.get(eid)
    if not reg:
        pin = str(random.randint(100000, 999999))
        reg = {"dateTimeRegistered": ts(), "pIN": pin, "status": "pending", "eid": eid}
        store.registrations[eid] = reg

    if request.method == "PUT":
        root_el      = parse_xml_body()
        submitted_pin = xml_val(root_el, "pIN") if root_el is not None else None

        if submitted_pin is not None:
            if submitted_pin == reg["pIN"]:
                reg["status"] = "confirmed"
                reg["dateTimeRegistered"] = ts()
                store.end_devices[eid]["enabled"] = True
                store.end_devices[eid]["registrationStatus"] = "confirmed"
                store.registrations[eid] = reg
                store.add_log(f"EndDevice {eid} registration CONFIRMED")
                return xml_response("", 204)
            else:
                store.add_log(f"EndDevice {eid} registration FAILED: wrong PIN")
                return xml_response(
                    f'<sep:Error xmlns:sep="{SEP_NS}"><sep:message>Invalid PIN</sep:message></sep:Error>', 403)
        else:
            reg["dateTimeRegistered"] = ts()
            store.registrations[eid] = reg
            return xml_response("", 204)

    def c(root):
        root.set("href", f"/edev/{eid}/reg")
        root.append(elem("dateTimeRegistered", str(reg["dateTimeRegistered"])))
        root.append(elem("pIN", reg["pIN"]))
    return xml_response(build_xml("Registration", c))


# ---------------------------------------------------------------------------
# 6. Function Set Assignments
# ---------------------------------------------------------------------------

@app.route("/edev/<eid>/fsa", methods=["GET"])
def function_set_assignments_list(eid):
    def c(root):
        root.set("href", f"/edev/{eid}/fsa")
        root.set("all", "1"); root.set("results", "1")
        fsa = elem("FunctionSetAssignments", attribs={"href": f"/edev/{eid}/fsa/0"})
        fsa.append(elem("mRID",        f"FSA-{eid}"))
        fsa.append(elem("description", "Default FSA"))
        fsa.append(elem("DERProgramListLink",          attribs={"href": f"/edev/{eid}/derp", "all": "1"}))
        fsa.append(elem("DemandResponseProgramListLink",attribs={"href": f"/edev/{eid}/dr",  "all": "1"}))
        fsa.append(elem("MessagingProgramListLink",    attribs={"href": "/msg",               "all": str(len(store.messages))}))
        fsa.append(elem("TimeLink",                    attribs={"href": "/tm"}))
        fsa.append(elem("TariffProfileListLink",       attribs={"href": "/pricep",            "all": str(len(store.tariff_profiles))}))
        root.append(fsa)
    return xml_response(build_xml("FunctionSetAssignmentsList", c))


@app.route("/edev/<eid>/fsa/<fsaid>", methods=["GET"])
def function_set_assignment(eid, fsaid):
    def c(root):
        root.set("href", f"/edev/{eid}/fsa/{fsaid}")
        root.append(elem("mRID",        f"FSA-{eid}-{fsaid}"))
        root.append(elem("description", "Default FSA"))
        root.append(elem("DERProgramListLink",          attribs={"href": f"/edev/{eid}/derp", "all": "1"}))
        root.append(elem("DemandResponseProgramListLink",attribs={"href": f"/edev/{eid}/dr",  "all": "1"}))
        root.append(elem("TimeLink",                    attribs={"href": "/tm"}))
    return xml_response(build_xml("FunctionSetAssignments", c))


# ---------------------------------------------------------------------------
# 7. DER List & per-DER resources
# ---------------------------------------------------------------------------

@app.route("/edev/<eid>/der", methods=["GET", "POST"])
def der_list(eid):
    key  = f"{eid}_ders"
    ders = store.ders.get(key, [])

    if request.method == "POST":
        did = str(uuid.uuid4())[:8]
        ders.append({"id": did, "href": f"/edev/{eid}/der/{did}", "changedTime": ts()})
        store.ders[key] = ders
        store.add_log(f"DER {did} created under EndDevice {eid}")
        return xml_response(f'<sep:DER xmlns:sep="{SEP_NS}" href="/edev/{eid}/der/{did}"/>', 201)

    def c(root):
        root.set("href", f"/edev/{eid}/der")
        root.set("all",     str(len(ders)))
        root.set("results", str(len(ders)))
        for d in ders:
            _der_elem(root, eid, d)
    return xml_response(build_xml("DERList", c))


def _der_elem(parent, eid, d):
    did = d["id"]
    der = elem("DER", attribs={"href": d["href"]})
    der.append(elem("AssociatedDERProgramListLink", attribs={"href": f"/edev/{eid}/derp",            "all": "1"}))
    der.append(elem("CurrentDERProgramLink",        attribs={"href": f"/edev/{eid}/der/{did}/cdp"}))
    der.append(elem("DERAvailabilityLink",          attribs={"href": f"/edev/{eid}/der/{did}/dera"}))
    der.append(elem("DERCapabilityLink",            attribs={"href": f"/edev/{eid}/der/{did}/derc"}))
    der.append(elem("DERSettingsLink",              attribs={"href": f"/edev/{eid}/der/{did}/ders"}))
    der.append(elem("DERStatusLink",                attribs={"href": f"/edev/{eid}/der/{did}/derstatus"}))
    parent.append(der)


@app.route("/edev/<eid>/der/<did>", methods=["GET", "PUT", "DELETE"])
def der_resource(eid, did):
    key  = f"{eid}_ders"
    ders = store.ders.get(key, [])
    d    = next((x for x in ders if x["id"] == did), None)

    if request.method == "DELETE":
        store.ders[key] = [x for x in ders if x["id"] != did]
        store.add_log(f"DER {did} deleted from EndDevice {eid}")
        return xml_response("", 204)

    if request.method == "PUT":
        if not d:
            d = {"id": did, "href": f"/edev/{eid}/der/{did}", "changedTime": ts()}
            ders.append(d)
            store.ders[key] = ders
        d["changedTime"] = ts()
        return xml_response("", 204)

    if not d:
        return not_found_xml()

    root_el = ET.Element(f"{{{SEP_NS}}}DER", {"href": d["href"]})
    _der_elem(root_el, eid, d)
    # _der_elem adds to parent; build manually
    root_el2 = ET.Element(f"{{{SEP_NS}}}DER", {"href": d["href"]})
    root_el2.append(elem("AssociatedDERProgramListLink", attribs={"href": f"/edev/{eid}/derp", "all": "1"}))
    root_el2.append(elem("CurrentDERProgramLink",        attribs={"href": f"/edev/{eid}/der/{did}/cdp"}))
    root_el2.append(elem("DERAvailabilityLink",          attribs={"href": f"/edev/{eid}/der/{did}/dera"}))
    root_el2.append(elem("DERCapabilityLink",            attribs={"href": f"/edev/{eid}/der/{did}/derc"}))
    root_el2.append(elem("DERSettingsLink",              attribs={"href": f"/edev/{eid}/der/{did}/ders"}))
    root_el2.append(elem("DERStatusLink",                attribs={"href": f"/edev/{eid}/der/{did}/derstatus"}))
    raw = ET.tostring(root_el2, encoding="unicode")
    try:
        pretty = xml.dom.minidom.parseString(raw).toprettyxml(indent="  ")
        return xml_response("\n".join(pretty.split("\n")[1:]))
    except Exception:
        return xml_response(raw)


@app.route("/edev/<eid>/der/<did>/derc", methods=["GET", "PUT"])
def der_capability(eid, did):
    key = f"{eid}_{did}_cap"
    cap = store.der_capabilities.get(key, {})
    if request.method == "PUT":
        root_el = parse_xml_body()
        if root_el is not None:
            cap["modesSupported"] = xml_val(root_el, "modesSupported", cap.get("modesSupported","3F"))
            cap["type"]           = xml_val(root_el, "type", cap.get("type","85"))
        store.der_capabilities[key] = cap
        return xml_response("", 204)
    lim = store.limits
    def c(root):
        root.set("href", f"/edev/{eid}/der/{did}/derc")
        root.append(elem("modesSupported", cap.get("modesSupported", "3F")))
        power_elem(root, "rtgMaxW",              lim.get("maxW",   10000))
        power_elem(root, "rtgMaxVar",            lim.get("maxVar",  5000))
        power_elem(root, "rtgMaxVA",             lim.get("maxVA",  11000))
        power_elem(root, "rtgMaxChargeRateW",    7500)
        power_elem(root, "rtgMaxDischargeRateW", 7500)
        root.append(elem("rtgMinPFOverExcited",  "850"))
        root.append(elem("rtgMinPFUnderExcited", "850"))
        root.append(elem("type", cap.get("type", "85")))
    return xml_response(build_xml("DERCapability", c))


@app.route("/edev/<eid>/der/<did>/ders", methods=["GET", "PUT"])
def der_settings(eid, did):
    key      = f"{eid}_{did}_settings"
    settings = store.der_settings_store.get(key, {})
    if request.method == "PUT":
        store.der_settings_store[key] = {"changedTime": ts(), "raw": request.data.decode()}
        store.add_log(f"DERSettings updated for {eid}/{did}")
        return xml_response("", 204)
    lim = store.limits
    def c(root):
        root.set("href", f"/edev/{eid}/der/{did}/ders")
        root.append(elem("updatedTime", str(settings.get("changedTime", ts()))))
        power_elem(root, "setMaxW",   lim.get("maxW",    10000))
        power_elem(root, "setMaxVar", lim.get("maxVar",   5000))
        power_elem(root, "setMaxVA",  lim.get("maxVA",  11000))
        root.append(elem("setESDelay",        "0"))
        root.append(elem("setESHighFreq",     str(lim.get("highFreq",  6020))))
        root.append(elem("setESHighVolt",     str(lim.get("highVolt", 12000))))
        root.append(elem("setESLowFreq",      str(lim.get("lowFreq",   5970))))
        root.append(elem("setESLowVolt",      str(lim.get("lowVolt",  10800))))
        root.append(elem("setESRampTms",      "60"))
        root.append(elem("setESRandomDelay",  "0"))
        root.append(elem("setGradW",          str(lim.get("gradW",     1000))))
        root.append(elem("setSoftGradW",      str(lim.get("softGradW",  500))))
    return xml_response(build_xml("DERSettings", c))


@app.route("/edev/<eid>/der/<did>/dera", methods=["GET", "PUT"])
def der_availability(eid, did):
    key   = f"{eid}_{did}_avail"
    avail = store.der_availability_store.get(key, {})
    if request.method == "PUT":
        root_el = parse_xml_body()
        entry   = {"changedTime": ts(), "raw": request.data.decode()}
        if root_el is not None:
            for tag in ("availabilityDuration","maxChargeDuration","readyTime","soc","statWAvail"):
                v = xml_val(root_el, tag)
                if v: entry[tag] = v
        store.der_availability_store[key] = entry
        store.add_log(f"DERAvailability updated for {eid}/{did}")
        return xml_response("", 204)
    def c(root):
        root.set("href", f"/edev/{eid}/der/{did}/dera")
        root.append(elem("availabilityDuration", str(avail.get("availabilityDuration", 3600))))
        root.append(elem("maxChargeDuration",    str(avail.get("maxChargeDuration",    3600))))
        root.append(elem("readyTime",            str(avail.get("readyTime",           ts()))))
        root.append(elem("soc",                  str(avail.get("soc",                 8000))))
        root.append(elem("statWAvail",           str(avail.get("statWAvail",          5000))))
    return xml_response(build_xml("DERAvailability", c))


@app.route("/edev/<eid>/der/<did>/derstatus", methods=["GET", "PUT"])
def der_status(eid, did):
    key    = f"{eid}_{did}_status"
    status = store.der_status_store.get(key, {})
    if request.method == "PUT":
        root_el = parse_xml_body()
        entry   = {"changedTime": ts(), "raw": request.data.decode()}
        if root_el is not None:
            for tag in ("genConnectStatus","inverterStatus","operationalModeStatus","storConnectStatus"):
                el = xml_find(root_el, tag)
                if el is not None:
                    entry[tag] = xml_val(el, "value", "1")
        store.der_status_store[key] = entry
        store.add_log(f"DERStatus updated for {eid}/{did}")
        return xml_response("", 204)
    def c(root):
        root.set("href", f"/edev/{eid}/der/{did}/derstatus")
        root.append(elem("changedTime", str(status.get("changedTime", ts()))))
        for tag in ("genConnectStatus","inverterStatus","operationalModeStatus","storConnectStatus"):
            e = elem(tag)
            e.append(elem("dateTime", str(ts())))
            e.append(elem("value",    str(status.get(tag, "1"))))
            root.append(e)
    return xml_response(build_xml("DERStatus", c))


@app.route("/edev/<eid>/der/<did>/cdp", methods=["GET"])
def current_der_program(eid, did):
    """CurrentDERProgram — points to the active DER program."""
    # Find the first DER program assigned to this device (via FSA)
    active_pid = next(iter(store.der_programs), None)
    def c(root):
        root.set("href", f"/edev/{eid}/der/{did}/cdp")
        if active_pid:
            p = store.der_programs[active_pid]
            root.append(elem("mRID",        p["mRID"]))
            root.append(elem("description", p.get("description", "")))
            root.append(elem("primacy",     str(p.get("primacy", 1))))
            root.append(elem("ActiveDERControlLink",  attribs={"href": f"/derp/{active_pid}/acderc"}))
            root.append(elem("DefaultDERControlLink", attribs={"href": f"/derp/{active_pid}/dderc"}))
            root.append(elem("DERControlListLink",    attribs={"href": f"/derp/{active_pid}/derc", "all": "0"}))
    return xml_response(build_xml("DERProgram", c))


@app.route("/edev/<eid>/derp", methods=["GET"])
def edev_der_program_list(eid):
    """Per-device DERProgram list (via FSA)."""
    progs = list(store.der_programs.values())
    def c(root):
        root.set("href",    f"/edev/{eid}/derp")
        root.set("all",     str(len(progs)))
        root.set("results", str(len(progs)))
        for p in progs:
            _derp_elem(root, p)
    return xml_response(build_xml("DERProgramList", c))


@app.route("/edev/<eid>/dr", methods=["GET"])
def edev_dr_list(eid):
    """Per-device DemandResponseProgram list (via FSA)."""
    progs = list(store.dr_programs.values())
    def c(root):
        root.set("href",    f"/edev/{eid}/dr")
        root.set("all",     str(len(progs)))
        root.set("results", str(len(progs)))
        for p in progs:
            _dr_elem(root, p)
    return xml_response(build_xml("DemandResponseProgramList", c))


# ---------------------------------------------------------------------------
# 8. DER Programs
# ---------------------------------------------------------------------------

def _derp_elem(parent, p):
    pid = p["id"]
    pr  = elem("DERProgram", attribs={"href": p["href"]})
    pr.append(elem("mRID",        p["mRID"]))
    pr.append(elem("description", p.get("description", "")))
    pr.append(elem("primacy",     str(p.get("primacy", 1))))
    pr.append(elem("ActiveDERControlLink",  attribs={"href": f"/derp/{pid}/acderc"}))
    pr.append(elem("DefaultDERControlLink", attribs={"href": f"/derp/{pid}/dderc"}))
    pr.append(elem("DERControlListLink",    attribs={"href": f"/derp/{pid}/derc", "all": str(len(store.der_control_lists.get(f"{pid}_controls", [])))}))
    pr.append(elem("DERCurveListLink",      attribs={"href": f"/derp/{pid}/dc",   "all": str(len(store.der_curves.get(f"{pid}_curves", [])))}))
    parent.append(pr)


@app.route("/derp", methods=["GET", "POST"])
def der_program_list():
    if request.method == "POST":
        pid = str(uuid.uuid4())[:8]
        root_el = parse_xml_body()
        store.der_programs[pid] = {
            "id": pid, "mRID": xml_val(root_el, "mRID", f"DERP-{pid}") if root_el else f"DERP-{pid}",
            "description": xml_val(root_el, "description", "DER Program") if root_el else "DER Program",
            "primacy": int(xml_val(root_el, "primacy", "1") or 1),
            "href": f"/derp/{pid}", "changedTime": ts(),
        }
        store.add_log(f"DERProgram {pid} created")
        return xml_response(f'<sep:DERProgram xmlns:sep="{SEP_NS}" href="/derp/{pid}"/>', 201)

    progs = list(store.der_programs.values())
    def c(root):
        root.set("href", "/derp")
        root.set("all",     str(len(progs)))
        root.set("results", str(len(progs)))
        for p in progs:
            _derp_elem(root, p)
    return xml_response(build_xml("DERProgramList", c))


@app.route("/derp/<pid>", methods=["GET", "PUT", "DELETE"])
def der_program(pid):
    if request.method == "DELETE":
        store.der_programs.pop(pid, None)
        return xml_response("", 204)
    if request.method == "PUT":
        p       = store.der_programs.get(pid, {"id": pid, "href": f"/derp/{pid}", "mRID": f"DERP-{pid}", "changedTime": ts()})
        root_el = parse_xml_body()
        if root_el is not None:
            p["description"] = xml_val(root_el, "description", p.get("description",""))
            p["primacy"]     = int(xml_val(root_el, "primacy", str(p.get("primacy",1))) or 1)
        p["changedTime"] = ts()
        store.der_programs[pid] = p
        return xml_response("", 204)

    p = store.der_programs.get(pid)
    if not p:
        return not_found_xml()

    def c(root):
        _derp_elem(root, p)
    # build manually to avoid double-wrapping
    root_el = ET.Element(f"{{{SEP_NS}}}DERProgram", {"href": p["href"]})
    root_el.append(elem("mRID",        p["mRID"]))
    root_el.append(elem("description", p.get("description","")))
    root_el.append(elem("primacy",     str(p.get("primacy",1))))
    root_el.append(elem("ActiveDERControlLink",  attribs={"href": f"/derp/{pid}/acderc"}))
    root_el.append(elem("DefaultDERControlLink", attribs={"href": f"/derp/{pid}/dderc"}))
    root_el.append(elem("DERControlListLink",    attribs={"href": f"/derp/{pid}/derc", "all": str(len(store.der_control_lists.get(f"{pid}_controls", [])))}))
    root_el.append(elem("DERCurveListLink",      attribs={"href": f"/derp/{pid}/dc",   "all": str(len(store.der_curves.get(f"{pid}_curves", [])))}))
    raw = ET.tostring(root_el, encoding="unicode")
    try:
        pretty = xml.dom.minidom.parseString(raw).toprettyxml(indent="  ")
        return xml_response("\n".join(pretty.split("\n")[1:]))
    except Exception:
        return xml_response(raw)


@app.route("/derp/<pid>/dderc", methods=["GET", "PUT"])
def default_der_control(pid):
    key = f"{pid}_dderc"
    if request.method == "PUT":
        store.der_controls[key] = {"changedTime": ts(), "raw": request.data.decode()}
        store.add_log(f"DefaultDERControl updated for program {pid}")
        return xml_response("", 204)
    lim = store.limits
    def c(root):
        root.set("href", f"/derp/{pid}/dderc")
        dc = elem("DERControlBase")
        dc.append(elem("opModConnect", "true"))
        power_elem(dc, "opModMaxLimW", lim.get("maxW", 10000))
        fv = elem("opModFixedVar")
        fv.append(elem("refType", "0"))
        power_elem(fv, "value", lim.get("maxVar", 0), multiplier="-3")
        dc.append(fv)
        root.append(dc)
    return xml_response(build_xml("DefaultDERControl", c))


@app.route("/derp/<pid>/acderc", methods=["GET"])
def active_der_control(pid):
    """ActiveDERControl — the currently active control event, if any."""
    controls = store.der_control_lists.get(f"{pid}_controls", [])
    now      = ts()
    active   = next((ctrl for ctrl in controls if ctrl.get("startTime", 0) <= now <= ctrl.get("startTime", 0) + ctrl.get("duration", 0)), None)
    lim      = store.limits

    def c(root):
        root.set("href", f"/derp/{pid}/acderc")
        if active:
            root.append(elem("mRID",           active["mRID"]))
            root.append(elem("deviceCategory", active.get("deviceCategory","FFFFFFFF")))
            iv = elem("interval")
            iv.append(elem("duration", str(active.get("duration", 3600))))
            iv.append(elem("start",    str(active.get("startTime", now))))
            root.append(iv)
            dc = elem("DERControlBase")
            dc.append(elem("opModConnect", "true"))
            power_elem(dc, "opModMaxLimW", lim.get("maxW", 10000))
            root.append(dc)
        else:
            root.append(elem("mRID", "0"))
    return xml_response(build_xml("DERControl", c))


@app.route("/derp/<pid>/derc", methods=["GET", "POST"])
def der_control_list(pid):
    key      = f"{pid}_controls"
    controls = store.der_control_lists.get(key, [])

    if request.method == "POST":
        cid     = str(uuid.uuid4())[:8]
        root_el = parse_xml_body()
        ctrl    = {
            "id": cid, "href": f"/derp/{pid}/derc/{cid}",
            "mRID":           xml_val(root_el, "mRID", f"DERC-{cid}") if root_el else f"DERC-{cid}",
            "deviceCategory": xml_val(root_el, "deviceCategory", "FFFFFFFF") if root_el else "FFFFFFFF",
            "startTime":      int(xml_val(root_el, "start", str(ts())) or ts()) if root_el else ts(),
            "duration":       int(xml_val(root_el, "duration", "3600") or 3600) if root_el else 3600,
            "changedTime":    ts(),
        }
        controls.append(ctrl)
        store.der_control_lists[key] = controls
        store.add_log(f"DERControl {cid} created in program {pid}")
        return xml_response(f'<sep:DERControl xmlns:sep="{SEP_NS}" href="/derp/{pid}/derc/{cid}"/>', 201)

    def c(root):
        root.set("href",    f"/derp/{pid}/derc")
        root.set("all",     str(len(controls)))
        root.set("results", str(len(controls)))
        for ctrl in controls:
            _derc_elem(root, pid, ctrl)
    return xml_response(build_xml("DERControlList", c))


def _derc_elem(parent, pid, ctrl):
    ce = elem("DERControl", attribs={"href": ctrl["href"]})
    ce.append(elem("mRID",           ctrl["mRID"]))
    ce.append(elem("deviceCategory", ctrl.get("deviceCategory","FFFFFFFF")))
    iv = elem("interval")
    iv.append(elem("duration", str(ctrl.get("duration", 3600))))
    iv.append(elem("start",    str(ctrl.get("startTime", ts()))))
    ce.append(iv)
    parent.append(ce)


@app.route("/derp/<pid>/derc/<dcid>", methods=["GET", "PUT", "DELETE"])
def der_control(pid, dcid):
    key      = f"{pid}_controls"
    controls = store.der_control_lists.get(key, [])
    ctrl     = next((x for x in controls if x["id"] == dcid), None)

    if request.method == "DELETE":
        store.der_control_lists[key] = [x for x in controls if x["id"] != dcid]
        store.add_log(f"DERControl {dcid} deleted from program {pid}")
        return xml_response("", 204)

    if request.method == "PUT":
        if not ctrl:
            ctrl = {"id": dcid, "href": f"/derp/{pid}/derc/{dcid}", "mRID": f"DERC-{dcid}", "changedTime": ts(), "deviceCategory":"FFFFFFFF", "startTime": ts(), "duration": 3600}
            controls.append(ctrl)
        root_el = parse_xml_body()
        if root_el is not None:
            ctrl["deviceCategory"] = xml_val(root_el, "deviceCategory", ctrl.get("deviceCategory","FFFFFFFF"))
        ctrl["changedTime"] = ts()
        store.der_control_lists[key] = controls
        return xml_response("", 204)

    if not ctrl:
        return not_found_xml()

    root_el = ET.Element(f"{{{SEP_NS}}}DERControl", {"href": ctrl["href"]})
    root_el.append(elem("mRID",           ctrl["mRID"]))
    root_el.append(elem("deviceCategory", ctrl.get("deviceCategory","FFFFFFFF")))
    iv = elem("interval")
    iv.append(elem("duration", str(ctrl.get("duration", 3600))))
    iv.append(elem("start",    str(ctrl.get("startTime", ts()))))
    root_el.append(iv)
    raw = ET.tostring(root_el, encoding="unicode")
    try:
        pretty = xml.dom.minidom.parseString(raw).toprettyxml(indent="  ")
        return xml_response("\n".join(pretty.split("\n")[1:]))
    except Exception:
        return xml_response(raw)


# ---------------------------------------------------------------------------
# 9. DER Curves
# ---------------------------------------------------------------------------

@app.route("/derp/<pid>/dc", methods=["GET", "POST"])
def der_curve_list(pid):
    key    = f"{pid}_curves"
    curves = store.der_curves.get(key, [])

    if request.method == "POST":
        cid     = str(uuid.uuid4())[:8]
        root_el = parse_xml_body()
        curve   = {
            "id": cid, "href": f"/derp/{pid}/dc/{cid}",
            "mRID":        xml_val(root_el, "mRID", f"DC-{cid}") if root_el else f"DC-{cid}",
            "description": xml_val(root_el, "description", "DER Curve") if root_el else "DER Curve",
            "curveType":   xml_val(root_el, "curveType", "0") if root_el else "0",
            "changedTime": ts(),
            "points":      [],
        }
        curves.append(curve)
        store.der_curves[key] = curves
        store.add_log(f"DERCurve {cid} created in program {pid}")
        return xml_response(f'<sep:DERCurve xmlns:sep="{SEP_NS}" href="/derp/{pid}/dc/{cid}"/>', 201)

    def c(root):
        root.set("href",    f"/derp/{pid}/dc")
        root.set("all",     str(len(curves)))
        root.set("results", str(len(curves)))
        for curve in curves:
            _dc_elem(root, curve)
    return xml_response(build_xml("DERCurveList", c))


def _dc_elem(parent, curve):
    ce = elem("DERCurve", attribs={"href": curve["href"]})
    ce.append(elem("mRID",        curve["mRID"]))
    ce.append(elem("description", curve.get("description","")))
    ce.append(elem("curveType",   str(curve.get("curveType","0"))))
    ce.append(elem("changedTime", str(curve.get("changedTime", ts()))))
    for pt in curve.get("points",[]):
        p = elem("CurveData")
        p.append(elem("excitation", str(pt.get("excitation","0"))))
        p.append(elem("xvalue",     str(pt.get("xvalue","0"))))
        p.append(elem("yvalue",     str(pt.get("yvalue","0"))))
        ce.append(p)
    parent.append(ce)


@app.route("/derp/<pid>/dc/<dcid>", methods=["GET", "PUT", "DELETE"])
def der_curve(pid, dcid):
    key    = f"{pid}_curves"
    curves = store.der_curves.get(key, [])
    curve  = next((x for x in curves if x["id"] == dcid), None)

    if request.method == "DELETE":
        store.der_curves[key] = [x for x in curves if x["id"] != dcid]
        return xml_response("", 204)

    if request.method == "PUT":
        if not curve:
            curve = {"id": dcid, "href": f"/derp/{pid}/dc/{dcid}", "mRID": f"DC-{dcid}", "curveType":"0", "changedTime": ts(), "points":[]}
            curves.append(curve)
        root_el = parse_xml_body()
        if root_el is not None:
            curve["curveType"]   = xml_val(root_el, "curveType", curve.get("curveType","0"))
            curve["description"] = xml_val(root_el, "description", curve.get("description",""))
        curve["changedTime"] = ts()
        store.der_curves[key] = curves
        return xml_response("", 204)

    if not curve:
        return not_found_xml()

    root_el = ET.Element(f"{{{SEP_NS}}}DERCurve", {"href": curve["href"]})
    _dc_elem(root_el, curve)
    # _dc_elem appends to parent — build manually
    root_el2 = ET.Element(f"{{{SEP_NS}}}DERCurve", {"href": curve["href"]})
    root_el2.append(elem("mRID",        curve["mRID"]))
    root_el2.append(elem("description", curve.get("description","")))
    root_el2.append(elem("curveType",   str(curve.get("curveType","0"))))
    root_el2.append(elem("changedTime", str(curve.get("changedTime", ts()))))
    raw = ET.tostring(root_el2, encoding="unicode")
    try:
        pretty = xml.dom.minidom.parseString(raw).toprettyxml(indent="  ")
        return xml_response("\n".join(pretty.split("\n")[1:]))
    except Exception:
        return xml_response(raw)


# ---------------------------------------------------------------------------
# 10. Demand Response Programs
# ---------------------------------------------------------------------------

def _dr_elem(parent, p):
    pid = p["id"]
    pr  = elem("DemandResponseProgram", attribs={"href": p["href"]})
    pr.append(elem("mRID",        p["mRID"]))
    pr.append(elem("description", p.get("description","")))
    pr.append(elem("primacy",     str(p.get("primacy",1))))
    pr.append(elem("ActiveEndDeviceControlListLink", attribs={"href": f"/dr/{pid}/aedc", "all": "0"}))
    pr.append(elem("EndDeviceControlListLink",       attribs={"href": f"/dr/{pid}/edc",  "all": str(len(store.end_device_controls.get(f"{pid}_edcs",[])))}))
    parent.append(pr)


@app.route("/dr", methods=["GET", "POST"])
def demand_response_list():
    if request.method == "POST":
        pid     = str(uuid.uuid4())[:8]
        root_el = parse_xml_body()
        store.dr_programs[pid] = {
            "id": pid, "href": f"/dr/{pid}",
            "mRID":        xml_val(root_el, "mRID", f"DR-{pid}") if root_el else f"DR-{pid}",
            "description": xml_val(root_el, "description", "DR Program") if root_el else "DR Program",
            "primacy":     int(xml_val(root_el, "primacy", "1") or 1),
        }
        store.add_log(f"DemandResponseProgram {pid} created")
        return xml_response(f'<sep:DemandResponseProgram xmlns:sep="{SEP_NS}" href="/dr/{pid}"/>', 201)

    progs = list(store.dr_programs.values())
    def c(root):
        root.set("href",    "/dr")
        root.set("all",     str(len(progs)))
        root.set("results", str(len(progs)))
        for p in progs:
            _dr_elem(root, p)
    return xml_response(build_xml("DemandResponseProgramList", c))


@app.route("/dr/<pid>", methods=["GET", "PUT", "DELETE"])
def demand_response_program(pid):
    if request.method == "DELETE":
        store.dr_programs.pop(pid, None)
        return xml_response("", 204)
    if request.method == "PUT":
        p       = store.dr_programs.get(pid, {"id": pid, "href": f"/dr/{pid}", "mRID": f"DR-{pid}"})
        root_el = parse_xml_body()
        if root_el is not None:
            p["description"] = xml_val(root_el, "description", p.get("description",""))
            p["primacy"]     = int(xml_val(root_el, "primacy", str(p.get("primacy",1))) or 1)
        store.dr_programs[pid] = p
        return xml_response("", 204)

    p = store.dr_programs.get(pid)
    if not p:
        return not_found_xml()

    root_el = ET.Element(f"{{{SEP_NS}}}DemandResponseProgram", {"href": p["href"]})
    root_el.append(elem("mRID",        p["mRID"]))
    root_el.append(elem("description", p.get("description","")))
    root_el.append(elem("primacy",     str(p.get("primacy",1))))
    root_el.append(elem("ActiveEndDeviceControlListLink", attribs={"href": f"/dr/{pid}/aedc","all":"0"}))
    root_el.append(elem("EndDeviceControlListLink",       attribs={"href": f"/dr/{pid}/edc", "all": str(len(store.end_device_controls.get(f"{pid}_edcs",[])))}))
    raw = ET.tostring(root_el, encoding="unicode")
    try:
        pretty = xml.dom.minidom.parseString(raw).toprettyxml(indent="  ")
        return xml_response("\n".join(pretty.split("\n")[1:]))
    except Exception:
        return xml_response(raw)


@app.route("/dr/<pid>/edc", methods=["GET", "POST"])
def end_device_control_list(pid):
    key  = f"{pid}_edcs"
    edcs = store.end_device_controls.get(key, [])

    if request.method == "POST":
        cid     = str(uuid.uuid4())[:8]
        root_el = parse_xml_body()
        edc     = {
            "id": cid, "href": f"/dr/{pid}/edc/{cid}",
            "mRID":           xml_val(root_el, "mRID", f"EDC-{cid}") if root_el else f"EDC-{cid}",
            "deviceCategory": xml_val(root_el, "deviceCategory", "FFFFFFFF") if root_el else "FFFFFFFF",
            "startTime":      int(xml_val(root_el, "start", str(ts())) or ts()) if root_el else ts(),
            "duration":       int(xml_val(root_el, "duration", "3600") or 3600) if root_el else 3600,
            "changedTime":    ts(),
        }
        edcs.append(edc)
        store.end_device_controls[key] = edcs
        store.add_log(f"EndDeviceControl {cid} created in DR program {pid}")
        return xml_response(f'<sep:EndDeviceControl xmlns:sep="{SEP_NS}" href="/dr/{pid}/edc/{cid}"/>', 201)

    def c(root):
        root.set("href",    f"/dr/{pid}/edc")
        root.set("all",     str(len(edcs)))
        root.set("results", str(len(edcs)))
        for edc in edcs:
            _edc_elem(root, pid, edc)
    return xml_response(build_xml("EndDeviceControlList", c))


def _edc_elem(parent, pid, edc):
    ce = elem("EndDeviceControl", attribs={"href": edc["href"]})
    ce.append(elem("mRID",           edc["mRID"]))
    ce.append(elem("deviceCategory", edc.get("deviceCategory","FFFFFFFF")))
    iv = elem("interval")
    iv.append(elem("duration", str(edc.get("duration",3600))))
    iv.append(elem("start",    str(edc.get("startTime",ts()))))
    ce.append(iv)
    parent.append(ce)


@app.route("/dr/<pid>/edc/<edcid>", methods=["GET", "PUT", "DELETE"])
def end_device_control(pid, edcid):
    key  = f"{pid}_edcs"
    edcs = store.end_device_controls.get(key, [])
    edc  = next((x for x in edcs if x["id"] == edcid), None)

    if request.method == "DELETE":
        store.end_device_controls[key] = [x for x in edcs if x["id"] != edcid]
        store.add_log(f"EndDeviceControl {edcid} deleted")
        return xml_response("", 204)

    if request.method == "PUT":
        if not edc:
            edc = {"id": edcid, "href": f"/dr/{pid}/edc/{edcid}", "mRID": f"EDC-{edcid}", "deviceCategory":"FFFFFFFF", "startTime": ts(), "duration":3600, "changedTime":ts()}
            edcs.append(edc)
        root_el = parse_xml_body()
        if root_el is not None:
            edc["deviceCategory"] = xml_val(root_el, "deviceCategory", edc["deviceCategory"])
        edc["changedTime"] = ts()
        store.end_device_controls[key] = edcs
        return xml_response("", 204)

    if not edc:
        return not_found_xml()

    root_el = ET.Element(f"{{{SEP_NS}}}EndDeviceControl", {"href": edc["href"]})
    _edc_elem(root_el, pid, edc)
    root_el2 = ET.Element(f"{{{SEP_NS}}}EndDeviceControl", {"href": edc["href"]})
    root_el2.append(elem("mRID",           edc["mRID"]))
    root_el2.append(elem("deviceCategory", edc.get("deviceCategory","FFFFFFFF")))
    iv = elem("interval")
    iv.append(elem("duration", str(edc.get("duration",3600))))
    iv.append(elem("start",    str(edc.get("startTime",ts()))))
    root_el2.append(iv)
    raw = ET.tostring(root_el2, encoding="unicode")
    try:
        pretty = xml.dom.minidom.parseString(raw).toprettyxml(indent="  ")
        return xml_response("\n".join(pretty.split("\n")[1:]))
    except Exception:
        return xml_response(raw)


@app.route("/dr/<pid>/aedc", methods=["GET"])
def active_end_device_control_list(pid):
    """Active EndDeviceControls (currently running)."""
    key  = f"{pid}_edcs"
    edcs = store.end_device_controls.get(key, [])
    now  = ts()
    active = [e for e in edcs if e.get("startTime",0) <= now <= e.get("startTime",0) + e.get("duration",0)]
    def c(root):
        root.set("href",    f"/dr/{pid}/aedc")
        root.set("all",     str(len(active)))
        root.set("results", str(len(active)))
        for edc in active:
            _edc_elem(root, pid, edc)
    return xml_response(build_xml("EndDeviceControlList", c))


# ---------------------------------------------------------------------------
# 11. Mirror Usage Points
# ---------------------------------------------------------------------------

@app.route("/mup", methods=["GET", "POST"])
def mirror_usage_point_list():
    if request.method == "POST":
        mid     = str(uuid.uuid4())[:8]
        root_el = parse_xml_body()
        store.mirror_usage_points[mid] = {
            "id": mid, "href": f"/mup/{mid}",
            "mRID":       xml_val(root_el, "mRID", f"MUP-{mid}") if root_el else f"MUP-{mid}",
            "description":xml_val(root_el, "description", "Mirror Usage Point") if root_el else "Mirror Usage Point",
            "deviceLFDI": xml_val(root_el, "deviceLFDI", "") if root_el else "",
            "changedTime":ts(),
        }
        store.add_log(f"MirrorUsagePoint {mid} created")
        return xml_response(f'<sep:MirrorUsagePoint xmlns:sep="{SEP_NS}" href="/mup/{mid}"/>', 201)

    mups = list(store.mirror_usage_points.values())
    def c(root):
        root.set("href",    "/mup")
        root.set("all",     str(len(mups)))
        root.set("results", str(len(mups)))
        for m in mups:
            mu = elem("MirrorUsagePoint", attribs={"href": m["href"]})
            mu.append(elem("mRID",        m["mRID"]))
            mu.append(elem("description", m.get("description","")))
            mu.append(elem("deviceLFDI",  m.get("deviceLFDI","")))
            mu.append(elem("MirrorMeterReadingListLink", attribs={"href": f"{m['href']}/mr", "all": str(len(store.meter_readings.get(m["id"],[])))}))
            root.append(mu)
    return xml_response(build_xml("MirrorUsagePointList", c))


@app.route("/mup/<mid>", methods=["GET", "DELETE"])
def mirror_usage_point(mid):
    if request.method == "DELETE":
        store.mirror_usage_points.pop(mid, None)
        store.meter_readings.pop(mid, None)
        return xml_response("", 204)
    m = store.mirror_usage_points.get(mid)
    if not m:
        return not_found_xml()
    def c(root):
        root.set("href", m["href"])
        root.append(elem("mRID",        m["mRID"]))
        root.append(elem("description", m.get("description","")))
        root.append(elem("deviceLFDI",  m.get("deviceLFDI","")))
        root.append(elem("MirrorMeterReadingListLink", attribs={"href": f"{m['href']}/mr", "all": str(len(store.meter_readings.get(mid,[])))}))
    return xml_response(build_xml("MirrorUsagePoint", c))


@app.route("/mup/<mid>/mr", methods=["GET", "POST"])
def mirror_meter_reading_list(mid):
    readings = store.meter_readings.get(mid, [])

    if request.method == "POST":
        rid     = str(uuid.uuid4())[:8]
        body    = request.data.decode()
        reading = {"id": rid, "href": f"/mup/{mid}/mr/{rid}", "mRID": f"MR-{rid}", "raw": body, "timestamp": ts(), "mupId": mid}
        try:
            root_el = ET.fromstring(body)
            def fv(*tags):
                for tag in tags:
                    el = xml_find(root_el, tag)
                    if el is not None and el.text: return el.text.strip()
                    # search nested
                    for child in root_el:
                        el2 = xml_find(child, tag)
                        if el2 is not None and el2.text: return el2.text.strip()
                return None
            reading["value"]       = fv("value","ReadingValue")
            reading["uom"]         = fv("uom")
            reading["description"] = fv("description") or "Reading"
            reading["multiplier"]  = fv("multiplier") or "0"
        except Exception:
            pass

        store.meter_readings.setdefault(mid, []).append(reading)
        store.add_telemetry({
            "mupId": mid, "readingId": rid,
            "value": reading.get("value"), "uom": reading.get("uom"),
            "description": reading.get("description","Reading"),
            "multiplier":  reading.get("multiplier","0"),
            "timestamp":   ts(),
        })
        store.add_log(f"MeterReading posted to MUP {mid}: value={reading.get('value')} uom={reading.get('uom')}")
        return xml_response(f'<sep:MirrorMeterReading xmlns:sep="{SEP_NS}" href="/mup/{mid}/mr/{rid}"/>', 201)

    def c(root):
        root.set("href",    f"/mup/{mid}/mr")
        root.set("all",     str(len(readings)))
        root.set("results", str(len(readings)))
        for r in readings:
            mr = elem("MirrorMeterReading", attribs={"href": r["href"]})
            mr.append(elem("mRID", r["mRID"]))
            if r.get("description"): mr.append(elem("description", r["description"]))
            root.append(mr)
    return xml_response(build_xml("MirrorMeterReadingList", c))


@app.route("/mup/<mid>/mr/<rid>", methods=["GET"])
def mirror_meter_reading(mid, rid):
    readings = store.meter_readings.get(mid, [])
    r = next((x for x in readings if x["id"] == rid), None)
    if not r:
        return not_found_xml()
    def c(root):
        root.set("href", r["href"])
        root.append(elem("mRID", r["mRID"]))
        if r.get("description"): root.append(elem("description", r["description"]))
        if r.get("value"):
            reading = elem("Reading")
            reading.append(elem("value", r["value"]))
            if r.get("uom"): reading.append(elem("uom", r["uom"]))
            root.append(reading)
            rt = elem("ReadingType")
            rt.append(elem("uom",        r.get("uom","0")))
            rt.append(elem("multiplier", r.get("multiplier","0")))
            root.append(rt)
    return xml_response(build_xml("MirrorMeterReading", c))


# ---------------------------------------------------------------------------
# 12. Usage Points (server-side metering)
# ---------------------------------------------------------------------------

@app.route("/upt", methods=["GET", "POST"])
def usage_point_list():
    if request.method == "POST":
        upid    = str(uuid.uuid4())[:8]
        root_el = parse_xml_body()
        store.usage_points[upid] = {
            "id": upid, "href": f"/upt/{upid}",
            "mRID":        xml_val(root_el, "mRID", f"UP-{upid}") if root_el else f"UP-{upid}",
            "description": xml_val(root_el, "description", "Usage Point") if root_el else "Usage Point",
            "roleFlags":   xml_val(root_el, "roleFlags", "00") if root_el else "00",
            "serviceCategoryKind": xml_val(root_el, "serviceCategoryKind", "0") if root_el else "0",
            "changedTime": ts(),
        }
        return xml_response(f'<sep:UsagePoint xmlns:sep="{SEP_NS}" href="/upt/{upid}"/>', 201)

    ups = list(store.usage_points.values())
    def c(root):
        root.set("href",    "/upt")
        root.set("all",     str(len(ups)))
        root.set("results", str(len(ups)))
        for u in ups:
            _upt_elem(root, u)
    return xml_response(build_xml("UsagePointList", c))


def _upt_elem(parent, u):
    upid = u["id"]
    up   = elem("UsagePoint", attribs={"href": u["href"]})
    up.append(elem("mRID",        u["mRID"]))
    up.append(elem("description", u.get("description","")))
    up.append(elem("roleFlags",   u.get("roleFlags","00")))
    up.append(elem("serviceCategoryKind", u.get("serviceCategoryKind","0")))
    up.append(elem("MeterReadingListLink", attribs={"href": f"/upt/{upid}/mr", "all": str(len(store.upt_readings.get(upid,[])))}))
    parent.append(up)


@app.route("/upt/<upid>", methods=["GET", "PUT", "DELETE"])
def usage_point(upid):
    if request.method == "DELETE":
        store.usage_points.pop(upid, None)
        return xml_response("", 204)
    if request.method == "PUT":
        u       = store.usage_points.get(upid, {"id": upid, "href": f"/upt/{upid}", "mRID": f"UP-{upid}", "changedTime": ts()})
        root_el = parse_xml_body()
        if root_el is not None:
            u["description"] = xml_val(root_el, "description", u.get("description",""))
        u["changedTime"] = ts()
        store.usage_points[upid] = u
        return xml_response("", 204)
    u = store.usage_points.get(upid)
    if not u:
        return not_found_xml()
    def c(root):
        _upt_elem(root, u)
    root_el2 = ET.Element(f"{{{SEP_NS}}}UsagePoint", {"href": u["href"]})
    root_el2.append(elem("mRID",        u["mRID"]))
    root_el2.append(elem("description", u.get("description","")))
    root_el2.append(elem("roleFlags",   u.get("roleFlags","00")))
    root_el2.append(elem("serviceCategoryKind", u.get("serviceCategoryKind","0")))
    root_el2.append(elem("MeterReadingListLink", attribs={"href": f"/upt/{upid}/mr", "all": str(len(store.upt_readings.get(upid,[])))}))
    raw = ET.tostring(root_el2, encoding="unicode")
    try:
        pretty = xml.dom.minidom.parseString(raw).toprettyxml(indent="  ")
        return xml_response("\n".join(pretty.split("\n")[1:]))
    except Exception:
        return xml_response(raw)


@app.route("/upt/<upid>/mr", methods=["GET"])
def upt_meter_reading_list(upid):
    readings = store.upt_readings.get(upid, [])
    def c(root):
        root.set("href",    f"/upt/{upid}/mr")
        root.set("all",     str(len(readings)))
        root.set("results", str(len(readings)))
        for r in readings:
            mr = elem("MeterReading", attribs={"href": r["href"]})
            mr.append(elem("mRID", r["mRID"]))
            root.append(mr)
    return xml_response(build_xml("MeterReadingList", c))


@app.route("/upt/<upid>/mr/<mrid>", methods=["GET"])
def upt_meter_reading(upid, mrid):
    readings = store.upt_readings.get(upid, [])
    r = next((x for x in readings if x["id"] == mrid), None)
    if not r:
        return not_found_xml()
    def c(root):
        root.set("href", r["href"])
        root.append(elem("mRID", r["mRID"]))
        root.append(elem("ReadingListLink", attribs={"href": f"/upt/{upid}/mr/{mrid}/r", "all": "0"}))
    return xml_response(build_xml("MeterReading", c))


@app.route("/upt/<upid>/mr/<mrid>/r", methods=["GET"])
def upt_reading_list(upid, mrid):
    def c(root):
        root.set("href",    f"/upt/{upid}/mr/{mrid}/r")
        root.set("all",     "0")
        root.set("results", "0")
    return xml_response(build_xml("ReadingList", c))


# ---------------------------------------------------------------------------
# 13. Pricing (TariffProfile)
# ---------------------------------------------------------------------------

@app.route("/pricep", methods=["GET"])
def tariff_profile_list():
    profiles = list(store.tariff_profiles.values())
    def c(root):
        root.set("href",    "/pricep")
        root.set("all",     str(len(profiles)))
        root.set("results", str(len(profiles)))
        for p in profiles:
            tp = elem("TariffProfile", attribs={"href": p["href"]})
            tp.append(elem("mRID",        p["mRID"]))
            tp.append(elem("description", p.get("description","")))
            tp.append(elem("pricePowerOfTenMultiplier", str(p.get("pricePowerOfTenMultiplier",0))))
            tp.append(elem("currency",    str(p.get("currency",840))))
            tp.append(elem("RateComponentListLink", attribs={"href": f"{p['href']}/rts", "all": "0"}))
            root.append(tp)
    return xml_response(build_xml("TariffProfileList", c))


@app.route("/pricep/<tpid>", methods=["GET"])
def tariff_profile(tpid):
    p = store.tariff_profiles.get(tpid)
    if not p:
        return not_found_xml()
    def c(root):
        root.set("href", p["href"])
        root.append(elem("mRID",        p["mRID"]))
        root.append(elem("description", p.get("description","")))
        root.append(elem("pricePowerOfTenMultiplier", str(p.get("pricePowerOfTenMultiplier",0))))
        root.append(elem("currency",    str(p.get("currency",840))))
        root.append(elem("RateComponentListLink", attribs={"href": f"/pricep/{tpid}/rts","all":"0"}))
    return xml_response(build_xml("TariffProfile", c))


@app.route("/pricep/<tpid>/rts", methods=["GET"])
def rate_component_list(tpid):
    def c(root):
        root.set("href",    f"/pricep/{tpid}/rts")
        root.set("all",     "0")
        root.set("results", "0")
    return xml_response(build_xml("RateComponentList", c))


@app.route("/pricep/<tpid>/rts/<rcid>/tou", methods=["GET"])
def time_tariff_interval_list(tpid, rcid):
    def c(root):
        root.set("href",    f"/pricep/{tpid}/rts/{rcid}/tou")
        root.set("all",     "0")
        root.set("results", "0")
    return xml_response(build_xml("TimeTariffIntervalList", c))


# ---------------------------------------------------------------------------
# 14. Messaging
# ---------------------------------------------------------------------------

@app.route("/msg", methods=["GET", "POST"])
def messaging_list():
    if request.method == "POST":
        mid     = str(uuid.uuid4())[:8]
        root_el = parse_xml_body()
        body    = request.data.decode()
        store.messages[mid] = {
            "id": mid, "href": f"/msg/{mid}", "mRID": f"MSG-{mid}",
            "message":         xml_val(root_el, "message", body) if root_el else body,
            "priority":        int(xml_val(root_el, "priority","0") or 0) if root_el else 0,
            "createdDateTime": ts(),
        }
        store.add_log(f"TextMessage {mid} created")
        return xml_response(f'<sep:TextMessage xmlns:sep="{SEP_NS}" href="/msg/{mid}"/>', 201)

    msgs = list(store.messages.values())
    def c(root):
        root.set("href",    "/msg")
        root.set("all",     str(len(msgs)))
        root.set("results", str(len(msgs)))
        for m in msgs:
            me = elem("TextMessage", attribs={"href": m["href"]})
            me.append(elem("mRID",            m["mRID"]))
            me.append(elem("createdDateTime", str(m["createdDateTime"])))
            me.append(elem("message",         m["message"]))
            me.append(elem("priority",        str(m.get("priority",0))))
            root.append(me)
    return xml_response(build_xml("MessagingProgramList", c))


@app.route("/msg/<mid>", methods=["GET", "DELETE"])
def message(mid):
    if request.method == "DELETE":
        store.messages.pop(mid, None)
        return xml_response("", 204)
    m = store.messages.get(mid)
    if not m:
        return not_found_xml()
    def c(root):
        root.set("href", m["href"])
        root.append(elem("mRID",            m["mRID"]))
        root.append(elem("createdDateTime", str(m["createdDateTime"])))
        root.append(elem("message",         m["message"]))
        root.append(elem("priority",        str(m.get("priority",0))))
    return xml_response(build_xml("TextMessage", c))


# ---------------------------------------------------------------------------
# 15. Response Sets
# ---------------------------------------------------------------------------

@app.route("/rsps", methods=["GET", "POST"])
def response_set_list():
    if request.method == "POST":
        rsid    = str(uuid.uuid4())[:8]
        root_el = parse_xml_body()
        store.response_sets[rsid] = {
            "id": rsid, "href": f"/rsps/{rsid}",
            "mRID":        xml_val(root_el, "mRID", f"RS-{rsid}") if root_el else f"RS-{rsid}",
            "description": xml_val(root_el, "description", "") if root_el else "",
            "changedTime": ts(),
        }
        return xml_response(f'<sep:ResponseSet xmlns:sep="{SEP_NS}" href="/rsps/{rsid}"/>', 201)

    rsets = list(store.response_sets.values())
    def c(root):
        root.set("href",    "/rsps")
        root.set("all",     str(len(rsets)))
        root.set("results", str(len(rsets)))
        for rs in rsets:
            rse = elem("ResponseSet", attribs={"href": rs["href"]})
            rse.append(elem("mRID",        rs["mRID"]))
            rse.append(elem("description", rs.get("description","")))
            rse.append(elem("ResponseListLink", attribs={"href": f"{rs['href']}/rsp", "all": str(len(store.responses_by_set.get(rs["id"],[])))}))
            root.append(rse)
    return xml_response(build_xml("ResponseSetList", c))


@app.route("/rsps/<rsid>", methods=["GET", "DELETE"])
def response_set(rsid):
    if request.method == "DELETE":
        store.response_sets.pop(rsid, None)
        store.responses_by_set.pop(rsid, None)
        return xml_response("", 204)
    rs = store.response_sets.get(rsid)
    if not rs:
        return not_found_xml()
    def c(root):
        root.set("href", rs["href"])
        root.append(elem("mRID",        rs["mRID"]))
        root.append(elem("description", rs.get("description","")))
        root.append(elem("ResponseListLink", attribs={"href": f"/rsps/{rsid}/rsp", "all": str(len(store.responses_by_set.get(rsid,[])))}))
    return xml_response(build_xml("ResponseSet", c))


@app.route("/rsps/<rsid>/rsp", methods=["GET", "POST"])
def response_list(rsid):
    responses = store.responses_by_set.get(rsid, [])
    if request.method == "POST":
        rid = str(uuid.uuid4())[:8]
        responses.append({"id": rid, "href": f"/rsps/{rsid}/rsp/{rid}", "raw": request.data.decode(), "timestamp": ts()})
        store.responses_by_set[rsid] = responses
        store.add_log(f"Response received for ResponseSet {rsid}")
        return xml_response(f'<sep:Response xmlns:sep="{SEP_NS}" href="/rsps/{rsid}/rsp/{rid}"/>', 201)

    def c(root):
        root.set("href",    f"/rsps/{rsid}/rsp")
        root.set("all",     str(len(responses)))
        root.set("results", str(len(responses)))
        for r in responses:
            re = elem("Response", attribs={"href": r["href"]})
            re.append(elem("createdDateTime", str(r["timestamp"])))
            root.append(re)
    return xml_response(build_xml("ResponseList", c))


@app.route("/rsps/<rsid>/rsp/<rid>", methods=["GET", "DELETE"])
def response(rsid, rid):
    responses = store.responses_by_set.get(rsid, [])
    r = next((x for x in responses if x["id"] == rid), None)
    if request.method == "DELETE":
        store.responses_by_set[rsid] = [x for x in responses if x["id"] != rid]
        return xml_response("", 204)
    if not r:
        return not_found_xml()
    def c(root):
        root.set("href", r["href"])
        root.append(elem("createdDateTime", str(r["timestamp"])))
    return xml_response(build_xml("Response", c))


# ---------------------------------------------------------------------------
# 16. Subscriptions
# ---------------------------------------------------------------------------

@app.route("/sub", methods=["GET", "POST"])
def subscription_list():
    if request.method == "POST":
        sid     = str(uuid.uuid4())[:8]
        root_el = parse_xml_body()
        store.subscriptions[sid] = {
            "id": sid, "href": f"/sub/{sid}",
            "subscribedResource": xml_val(root_el, "subscribedResource", "/") if root_el else request.args.get("res","/"),
            "notificationURI":    xml_val(root_el, "notificationURI", "") if root_el else request.args.get("uri",""),
            "changedTime": ts(),
        }
        return xml_response(f'<sep:Subscription xmlns:sep="{SEP_NS}" href="/sub/{sid}"/>', 201)

    subs = list(store.subscriptions.values())
    def c(root):
        root.set("href",    "/sub")
        root.set("all",     str(len(subs)))
        root.set("results", str(len(subs)))
        for s in subs:
            sub = elem("Subscription", attribs={"href": s["href"]})
            sub.append(elem("subscribedResource", s["subscribedResource"]))
            sub.append(elem("notificationURI",    s["notificationURI"]))
            root.append(sub)
    return xml_response(build_xml("SubscriptionList", c))


@app.route("/sub/<sid>", methods=["GET", "DELETE"])
def subscription(sid):
    if request.method == "DELETE":
        store.subscriptions.pop(sid, None)
        return xml_response("", 204)
    s = store.subscriptions.get(sid)
    if not s:
        return not_found_xml()
    def c(root):
        root.set("href", s["href"])
        root.append(elem("subscribedResource", s["subscribedResource"]))
        root.append(elem("notificationURI",    s["notificationURI"]))
    return xml_response(build_xml("Subscription", c))


# ---------------------------------------------------------------------------
# 17. Log Events
# ---------------------------------------------------------------------------

def _log_event_list_response(href, events):
    start = int(request.args.get("s", 0))
    limit = int(request.args.get("l", 255))
    page  = list(events)[start:start + limit]
    def c(root):
        root.set("href",    href)
        root.set("all",     str(len(events)))
        root.set("results", str(len(page)))
        for e in reversed(page):
            le = elem("LogEvent", attribs={"href": f"{href}/{e['id']}"})
            le.append(elem("createdDateTime", str(e["timestamp"])))
            le.append(elem("details",         e["message"]))
            le.append(elem("logEventCode",    "1"))
            le.append(elem("logEventID",      str(e["id"])))
            le.append(elem("profileID",       "0"))
            le.append(elem("extendedData",    "0"))
            root.append(le)
    return xml_response(build_xml("LogEventList", c))


@app.route("/lel", methods=["GET"])
def log_event_list():
    return _log_event_list_response("/lel", list(store.log_events))


@app.route("/lel/<int:leid>", methods=["GET"])
def log_event(leid):
    e = next((x for x in store.log_events if x["id"] == leid), None)
    if not e:
        return not_found_xml()
    def c(root):
        root.set("href", f"/lel/{leid}")
        root.append(elem("createdDateTime", str(e["timestamp"])))
        root.append(elem("details",         e["message"]))
        root.append(elem("logEventCode",    "1"))
        root.append(elem("logEventID",      str(e["id"])))
        root.append(elem("profileID",       "0"))
        root.append(elem("extendedData",    "0"))
    return xml_response(build_xml("LogEvent", c))


# ---------------------------------------------------------------------------
# 18. Prepayment (§22) — stubs
# ---------------------------------------------------------------------------

@app.route("/ppy", methods=["GET"])
def prepayment_list():
    preps = list(store.prepayments.values())
    def c(root):
        root.set("href",    "/ppy")
        root.set("all",     str(len(preps)))
        root.set("results", str(len(preps)))
        for p in preps:
            pp = elem("Prepayment", attribs={"href": p["href"]})
            pp.append(elem("mRID",        p["mRID"]))
            pp.append(elem("description", p.get("description","")))
            pp.append(elem("CreditExpiryLevelLink", attribs={"href": f"{p['href']}/cel"}))
            pp.append(elem("CreditStatusListLink",  attribs={"href": f"{p['href']}/csl", "all":"0"}))
            pp.append(elem("ActiveSupplyInterruptionOverrideListLink", attribs={"href": f"{p['href']}/at", "all":"0"}))
            root.append(pp)
    return xml_response(build_xml("PrepaymentList", c))


@app.route("/ppy/<ppid>/csl", methods=["GET"])
def credit_status_list(ppid):
    def c(root):
        root.set("href", f"/ppy/{ppid}/csl")
        root.set("all", "0"); root.set("results", "0")
    return xml_response(build_xml("CreditStatusList", c))


@app.route("/ppy/<ppid>/at", methods=["GET"])
def active_supply_interruption_list(ppid):
    def c(root):
        root.set("href", f"/ppy/{ppid}/at")
        root.set("all", "0"); root.set("results", "0")
    return xml_response(build_xml("ActiveSupplyInterruptionOverrideList", c))


# ---------------------------------------------------------------------------
# 19. Flow Reservation (§21)
# ---------------------------------------------------------------------------

@app.route("/frp", methods=["GET", "POST"])
def flow_reservation_request_list():
    if request.method == "POST":
        frid    = str(uuid.uuid4())[:8]
        root_el = parse_xml_body()
        store.flow_reservations[frid] = {
            "id": frid, "href": f"/frp/{frid}",
            "mRID":       xml_val(root_el, "mRID", f"FR-{frid}") if root_el else f"FR-{frid}",
            "description":xml_val(root_el, "description","") if root_el else "",
            "changedTime":ts(),
        }
        return xml_response(f'<sep:FlowReservationRequest xmlns:sep="{SEP_NS}" href="/frp/{frid}"/>', 201)

    frs = list(store.flow_reservations.values())
    def c(root):
        root.set("href",    "/frp")
        root.set("all",     str(len(frs)))
        root.set("results", str(len(frs)))
        for fr in frs:
            fre = elem("FlowReservationRequest", attribs={"href": fr["href"]})
            fre.append(elem("mRID",        fr["mRID"]))
            fre.append(elem("description", fr.get("description","")))
            root.append(fre)
    return xml_response(build_xml("FlowReservationRequestList", c))


@app.route("/frp/<frid>", methods=["GET", "PUT", "DELETE"])
def flow_reservation_request(frid):
    if request.method == "DELETE":
        store.flow_reservations.pop(frid, None)
        return xml_response("", 204)
    if request.method == "PUT":
        fr       = store.flow_reservations.get(frid, {"id": frid, "href": f"/frp/{frid}", "mRID": f"FR-{frid}"})
        fr["changedTime"] = ts()
        store.flow_reservations[frid] = fr
        return xml_response("", 204)
    fr = store.flow_reservations.get(frid)
    if not fr:
        return not_found_xml()
    def c(root):
        root.set("href", fr["href"])
        root.append(elem("mRID",        fr["mRID"]))
        root.append(elem("description", fr.get("description","")))
        root.append(elem("changedTime", str(fr.get("changedTime",ts()))))
    return xml_response(build_xml("FlowReservationRequest", c))


@app.route("/frr", methods=["GET", "POST"])
def flow_reservation_response_list():
    frrs = list(store.flow_reservation_responses.values())
    if request.method == "POST":
        frid    = str(uuid.uuid4())[:8]
        root_el = parse_xml_body()
        store.flow_reservation_responses[frid] = {
            "id": frid, "href": f"/frr/{frid}",
            "mRID": xml_val(root_el, "mRID", f"FRR-{frid}") if root_el else f"FRR-{frid}",
            "changedTime": ts(),
        }
        return xml_response(f'<sep:FlowReservationResponse xmlns:sep="{SEP_NS}" href="/frr/{frid}"/>', 201)

    def c(root):
        root.set("href",    "/frr")
        root.set("all",     str(len(frrs)))
        root.set("results", str(len(frrs)))
        for fr in frrs:
            fre = elem("FlowReservationResponse", attribs={"href": fr["href"]})
            fre.append(elem("mRID", fr["mRID"]))
            root.append(fre)
    return xml_response(build_xml("FlowReservationResponseList", c))


@app.route("/frr/<frid>", methods=["GET", "DELETE"])
def flow_reservation_response(frid):
    if request.method == "DELETE":
        store.flow_reservation_responses.pop(frid, None)
        return xml_response("", 204)
    fr = store.flow_reservation_responses.get(frid)
    if not fr:
        return not_found_xml()
    def c(root):
        root.set("href", fr["href"])
        root.append(elem("mRID", fr["mRID"]))
    return xml_response(build_xml("FlowReservationResponse", c))


# ---------------------------------------------------------------------------
# 20. Dashboard API
# ---------------------------------------------------------------------------

@app.route("/api/telemetry", methods=["GET"])
def api_telemetry():
    limit = int(request.args.get("limit", 200))
    data  = list(store.telemetry)[-limit:]
    return jsonify({
        "telemetry":     data,
        "limits":        store.limits,
        "endDeviceCount":len(store.end_devices),
        "mupCount":      len(store.mirror_usage_points),
        "logCount":      len(store.log_events),
        "serverTime":    ts(),
    })


@app.route("/api/limits", methods=["GET", "POST"])
def api_limits():
    if request.method == "POST":
        data = request.get_json(force=True)
        for k in ("maxW","maxVar","maxVA","highFreq","lowFreq","highVolt","lowVolt","gradW","softGradW"):
            if k in data:
                store.limits[k] = int(data[k])
        store.add_log(f"Limits updated via dashboard: {data}")
        return jsonify({"status": "ok", "limits": store.limits})
    return jsonify(store.limits)


@app.route("/api/logs", methods=["GET"])
def api_logs():
    limit = int(request.args.get("limit", 100))
    return jsonify({"logs": list(store.log_events)[-limit:]})


@app.route("/api/devices", methods=["GET"])
def api_devices():
    devices = []
    for d in store.end_devices.values():
        dev = dict(d)
        reg = store.registrations.get(d["id"])
        if reg:
            dev["pin"]                = reg["pIN"]
            dev["registrationStatus"] = reg.get("status","pending")
            dev["dateTimeRegistered"] = reg.get("dateTimeRegistered")
        devices.append(dev)
    return jsonify({
        "endDevices":       devices,
        "mirrorUsagePoints":list(store.mirror_usage_points.values()),
    })


@app.route("/api/devices/<eid>/approve", methods=["POST"])
def api_approve_device(eid):
    d = store.end_devices.get(eid)
    if not d: return jsonify({"error":"not found"}), 404
    reg = store.registrations.get(eid, {})
    reg["status"] = "confirmed"; reg["dateTimeRegistered"] = ts()
    store.registrations[eid] = reg
    store.end_devices[eid]["enabled"] = True
    store.end_devices[eid]["registrationStatus"] = "confirmed"
    store.add_log(f"EndDevice {eid} manually approved")
    return jsonify({"status":"ok"})


@app.route("/api/devices/<eid>/reject", methods=["POST"])
def api_reject_device(eid):
    d = store.end_devices.get(eid)
    if not d: return jsonify({"error":"not found"}), 404
    reg = store.registrations.get(eid, {})
    reg["status"] = "rejected"
    store.registrations[eid] = reg
    store.end_devices[eid]["enabled"] = False
    store.end_devices[eid]["registrationStatus"] = "rejected"
    store.add_log(f"EndDevice {eid} rejected")
    return jsonify({"status":"ok"})


@app.route("/api/devices/<eid>/regenerate_pin", methods=["POST"])
def api_regenerate_pin(eid):
    d = store.end_devices.get(eid)
    if not d: return jsonify({"error":"not found"}), 404
    pin = str(random.randint(100000, 999999))
    reg = store.registrations.get(eid, {})
    reg["pIN"] = pin; reg["status"] = "pending"
    store.registrations[eid] = reg
    store.end_devices[eid]["enabled"] = False
    store.end_devices[eid]["registrationStatus"] = "pending"
    store.add_log(f"EndDevice {eid} PIN regenerated")
    return jsonify({"status":"ok","pin":pin})


@app.route("/api/readings/<mid>", methods=["GET"])
def api_readings(mid):
    return jsonify({"readings": store.meter_readings.get(mid, [])})


@app.route("/api/send_message", methods=["POST"])
def api_send_message():
    data = request.get_json(force=True)
    mid  = str(uuid.uuid4())[:8]
    store.messages[mid] = {
        "id": mid, "href": f"/msg/{mid}", "mRID": f"MSG-{mid}",
        "message":         data.get("message",""),
        "priority":        data.get("priority",0),
        "createdDateTime": ts(),
    }
    store.add_log(f"Dashboard message queued: {data.get('message','')}")
    return jsonify({"status":"ok","id":mid})


# ---------------------------------------------------------------------------
# 21. Dashboard UI
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
@app.route("/dashboard", methods=["GET"])
def dashboard():
    return render_template("dashboard.html")


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return xml_response(f'<sep:Error xmlns:sep="{SEP_NS}"><sep:message>Not Found</sep:message></sep:Error>', 404)

@app.errorhandler(405)
def method_not_allowed(e):
    return xml_response(f'<sep:Error xmlns:sep="{SEP_NS}"><sep:message>Method Not Allowed</sep:message></sep:Error>', 405)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)

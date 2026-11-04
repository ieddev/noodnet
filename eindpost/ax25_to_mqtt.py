"""
ax25_to_mqtt.py - draait op een EINDPOST (brandweer, ambulance, gemeente, ...)
of op een centrale Meldkamer. Versie 2.

Leest de leesbare 2m-berichten van de Steunpunten via Direwolf, verwerkt wat
voor deze post bedoeld is, stuurt daarvoor een ACK terug, en publiceert op
MQTT in hetzelfde formaat als voorheen (Node-RED en Grafana blijven werken).

    Steunpunt -> 2 m -> transceiver -> Direwolf -> DIT SCRIPT -> MQTT

Welke berichten "voor deze post" zijn, bepaalt DISCIPLINES:
  - ["alle"]           : alles verwerken en bevestigen (centrale Meldkamer,
                         en zo werkte versie 1)
  - ["brandweer"]      : alleen meldingen met 'aan=brandweer' verwerken/bevestigen
  - MEELEZEN = True    : ook alle andere meldingen tonen, maar NIET bevestigen
                         (bijvoorbeeld het gemeentehuis)
Posities (GPS), announces en de hartslag van steunpunten gaan altijd naar
iedereen en worden nooit bevestigd.

Reticulum (rnsd) is op een eindpost NIET nodig (en hoort er niet: zo komt er
nooit iets versleuteld op 2 m).

Logboek: alles wat deze post verwerkt komt ook in logboek/JJJJ-MM-DD.txt
(leesbaar) en logboek/JJJJ-MM-DD.csv (voor Excel/Grafana achteraf), los van
MQTT en Node-RED.

Instellingen: eindpost_instellingen.json (beheerpagina http://<pi>:8080)
gaat voor de standaardwaarden hieronder.

Benodigd: noodnet_proto.py en methane.py naast dit script,
Direwolf met KISSPORT 8001, Python-module paho-mqtt.
"""

import json
import os
import sys
import threading
import time

import paho.mqtt.client as mqtt

import methane
import noodnet_proto as proto

# ---- CONFIGURATIE ----------------------------------------------------------
# Naam en roepnaam van deze post (de roepnaam is de bron van de ACK-frames)
EINDPOST_NAAM = "Eindpost"
CALLSIGN = "N0CALL-2"
# Disciplines van deze post (zelfde namen als in noodnet_netwerk.json op de
# steunpunten). ["alle"] = alles verwerken en bevestigen.
DISCIPLINES = ["alle"]
# Ook meldingen voor andere disciplines tonen (zonder te bevestigen)
MEELEZEN = False
DIREWOLF_HOST = "127.0.0.1"
DIREWOLF_PORT = 8001

MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC = "reticulum/tbeam"
MQTT_USER = ""
MQTT_PASS = ""

# Alleen frames van deze steunpunten verwerken. Leeg = alle steunpunten.
# Voorbeeld: ["PD3PAM-1", "PA1ABC-1"]
TOEGESTANE_STEUNPUNTEN = []

METHANE_TZ = "Europe/Amsterdam"
# Ook posities (GPS) in het logboek (CSV). Levenstekens zijn veel regels.
LOG_POSITIES = True
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SEEN_FILE = os.path.join(SCRIPT_DIR, "meldkamer_ontvangen.json")
INSTELLINGEN_FILE = os.path.join(SCRIPT_DIR, "eindpost_instellingen.json")
LOGBOEK_DIR = os.path.join(SCRIPT_DIR, "logboek")

_INST = {"eindpost_naam": "EINDPOST_NAAM", "roepnaam": "CALLSIGN", "disciplines": "DISCIPLINES",
         "meelezen": "MEELEZEN", "mqtt_broker": "MQTT_BROKER", "mqtt_poort": "MQTT_PORT",
         "mqtt_gebruiker": "MQTT_USER", "mqtt_wachtwoord": "MQTT_PASS",
         "toegestane_steunpunten": "TOEGESTANE_STEUNPUNTEN", "log_posities": "LOG_POSITIES"}
_INST_FOUT = None
try:
    with open(INSTELLINGEN_FILE, "r", encoding="utf-8") as _f:
        _i = json.load(_f)
    for _k, _var in _INST.items():
        if _k in _i and _i[_k] not in ("", None):
            globals()[_var] = _i[_k]
except FileNotFoundError:
    pass
except (OSError, ValueError) as _e:
    _INST_FOUT = str(_e)


def log(msg):
    print(time.strftime("%H:%M:%S ") + msg, flush=True)


# ---------------------------------------------------------------------------
# MQTT: start ook als de broker (nog) niet bereikbaar is
# ---------------------------------------------------------------------------

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
if MQTT_USER and MQTT_PASS:
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
mqtt_client.reconnect_delay_set(min_delay=2, max_delay=30)


def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        log("[+] MQTT: verbonden met broker")
        _connect_fail_reported[0] = False
    else:
        log(f"[-] MQTT: verbinding geweigerd ({reason_code})")


def on_disconnect(client, userdata, flags, reason_code, properties=None):
    log(f"[!] MQTT: verbinding verbroken ({reason_code}), opnieuw proberen...")


_connect_fail_reported = [False]


def on_connect_fail(client, userdata):
    if not _connect_fail_reported[0]:
        log(f"[-] MQTT: kan broker {MQTT_BROKER}:{MQTT_PORT} niet bereiken; blijf het proberen. "
            f"Berichten worden bewaard en verstuurd zodra de broker bereikbaar is.")
        _connect_fail_reported[0] = True


def check_broker():
    """Zegt bij het opstarten duidelijk of (en waarom niet) de broker bereikbaar is."""
    import socket
    try:
        ip = socket.gethostbyname(MQTT_BROKER)
    except OSError as e:
        log(f"[-] MQTT: naam '{MQTT_BROKER}' kan niet worden opgezocht ({e}). "
            f"Geen internet/DNS? Gebruik het IP-adres van de broker in MQTT_BROKER.")
        return
    try:
        socket.create_connection((ip, MQTT_PORT), timeout=5).close()
        log(f"[i] MQTT: broker {MQTT_BROKER} ({ip}) poort {MQTT_PORT} is bereikbaar, inloggen...")
    except OSError as e:
        log(f"[-] MQTT: {MQTT_BROKER} ({ip}) poort {MQTT_PORT} niet bereikbaar ({e}). "
            f"Draait de broker? Firewall? Klopt het adres?")


mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect
mqtt_client.on_connect_fail = on_connect_fail
check_broker()
mqtt_client.connect_async(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()


def publish(topic, payload, retain=False):
    mqtt_client.publish(f"{MQTT_TOPIC}/{topic}",
                        json.dumps(payload, ensure_ascii=False, default=str),
                        qos=1, retain=retain)


# ---------------------------------------------------------------------------
# Logboek (tekst + CSV per dag), onafhankelijk van MQTT/Node-RED
# ---------------------------------------------------------------------------

import csv

_log_lock = threading.Lock()
CSV_KOLOMMEN = ["tijd", "soort", "meldcode", "van", "adres", "steunpunt", "aan", "voor_deze_post",
                "lat", "lon", "rssi", "accu_rnode", "tekst"]


def logboek(soort, src, d, voor_mij, meldcode="", tekst=None, regels=None):
    """Schrijft één gebeurtenis naar logboek/<datum>.csv en (behalve posities) naar <datum>.txt."""
    nu = time.time()
    dag = time.strftime("%Y-%m-%d", time.localtime(nu))
    tijd = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(nu))
    if tekst is None:
        tekst = d.get("tekst", "")
    rij = {"tijd": tijd, "soort": soort, "meldcode": meldcode, "van": d.get("van", ""),
           "adres": d.get("adr", ""), "steunpunt": src, "aan": d.get("aan", ""),
           "voor_deze_post": "ja" if voor_mij else "nee (meelezen)",
           "lat": d.get("lat", ""), "lon": d.get("lon", ""),
           "rssi": d.get("s_rssi", ""), "accu_rnode": d.get("rbat", ""),
           "tekst": " | ".join(x.strip() for x in str(tekst or "").splitlines() if x.strip())}
    try:
        os.makedirs(LOGBOEK_DIR, exist_ok=True)
        with _log_lock:
            pad_csv = os.path.join(LOGBOEK_DIR, dag + ".csv")
            nieuw = not os.path.exists(pad_csv)
            with open(pad_csv, "a", encoding="utf-8-sig" if nieuw else "utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=CSV_KOLOMMEN, delimiter=";")
                if nieuw:
                    w.writeheader()
                w.writerow(rij)
            if regels is not None:
                with open(os.path.join(LOGBOEK_DIR, dag + ".txt"), "a", encoding="utf-8") as f:
                    f.write("\n".join(regels) + "\n\n")
    except OSError as e:
        log(f"[-] Logboek schrijven mislukt: {e}")


def kop(soort, src, d, voor_mij, extra=""):
    t = time.strftime("%Y-%m-%d %H:%M:%S")
    meelees = "" if voor_mij else "  (meelezen, niet voor deze post)"
    regels = [f"=== {t}  {soort}{extra}  van {d.get('van') or '?'} via {src}"
              f"{('  aan ' + d.get('aan')) if d.get('aan') else ''}{meelees}"]
    try:
        with open(os.path.join(SCRIPT_DIR, "operator.json"), encoding="utf-8") as f:
            o = json.load(f)
        if o.get("roepnaam"):
            regels.append(f"    dienstdoende operator: {o['roepnaam']}" + (f" ({o['naam']})" if o.get("naam") else ""))
    except (OSError, ValueError):
        pass
    return regels


# ---------------------------------------------------------------------------
# Dubbelen herkennen (herhalingen van het steunpunt), bewaard op schijf
# ---------------------------------------------------------------------------

_seen_lock = threading.Lock()
try:
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        seen = json.load(f)
except (OSError, ValueError):
    seen = {}


def already_seen(key):
    now = time.time()
    with _seen_lock:
        for k in [k for k, t in seen.items() if now - t > 24 * 3600]:
            del seen[k]
        if key in seen:
            return True
        seen[key] = now
        try:
            tmp = SEEN_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(seen, f)
            os.replace(tmp, SEEN_FILE)
        except OSError:
            pass
        return False


methane_cache = methane.MeldcodeCache(os.path.join(SCRIPT_DIR, "methane_meldcodes.json"))


# ---------------------------------------------------------------------------
# Hulpfuncties
# ---------------------------------------------------------------------------

def num(d, key):
    v = d.get(key)
    if v is None or v == "":
        return None
    try:
        f = float(v)
        return int(f) if f == int(f) else f
    except ValueError:
        return None


def topic_name(name, adr):
    name = name or adr
    for ch in " /+#":
        name = name.replace(ch, "_")
    return name


# Namen van de steunpunten (uit hun hartslag)
steunpunt_namen = {}


def aan_lijst(d):
    return [a.strip().lower() for a in d.get("aan", "").split(",") if a.strip()]


def is_voor_mij(d):
    aan = aan_lijst(d)
    eigen = [x.strip().lower() for x in DISCIPLINES]
    return not aan or "alle" in eigen or bool(set(aan) & set(eigen))


def common(d, src):
    adr = d.get("adr", "")
    return {
        "sender": f"<{adr}>" if adr else None,
        "sender_name": d.get("van"),
        "timestamp": time.time(),
        "steunpunt": src,
        "steunpunt_naam": steunpunt_namen.get(src),
        "ontvangen_steunpunt": num(d, "ontv"),
        "aan": aan_lijst(d),
        "voor_mij": is_voor_mij(d),
        "eindpost": EINDPOST_NAAM,
        "onbevestigd": d.get("onbevestigd") == "1",
    }


# ---------------------------------------------------------------------------
# Verwerking per soort
# ---------------------------------------------------------------------------

def handle_gps(src, d):
    data = {"type": "TELEMETRY", **common(d, src)}
    data.update({
        "latitude": num(d, "lat"),
        "longitude": num(d, "lon"),
        "altitude_m": num(d, "alt"),
        "speed_ms": num(d, "snelh"),
        "bearing_deg": num(d, "richt"),
        "accuracy_m": num(d, "nauwk"),
        "sensor_time_utc": num(d, "tijd"),
        "battery": num(d, "bat"),
        "battery_charging": (num(d, "laden") == 1) if "laden" in d else None,
        "rnode_battery": num(d, "rbat"),
        # Gemeten door de RNode van de telefoon (downlink steunpunt -> mobiel)
        "link_rssi": num(d, "m_rssi"),
        "link_snr": num(d, "m_snr"),
        "link_q": num(d, "m_q"),
        # Gemeten door de RNode van het steunpunt (uplink mobiel -> steunpunt)
        "steunpunt_rssi": num(d, "s_rssi"),
        "steunpunt_snr": num(d, "s_snr"),
        "steunpunt_q": num(d, "s_q"),
    })
    # rssi/snr/q zoals voorheen: meting van de telefoon, anders die van het steunpunt
    if data["link_rssi"] is not None or data["link_snr"] is not None:
        data["rssi"], data["snr"], data["q"] = data["link_rssi"], data["link_snr"], data["link_q"]
        data["rssi_bron"] = "mobiel"
    elif data["steunpunt_rssi"] is not None:
        data["rssi"], data["snr"], data["q"] = data["steunpunt_rssi"], data["steunpunt_snr"], data["steunpunt_q"]
        data["rssi_bron"] = "steunpunt"
    else:
        data["rssi"] = data["snr"] = data["q"] = None
        data["rssi_bron"] = None

    publish("gps", data)
    if LOG_POSITIES:
        logboek("POSITIE", src, d, True, tekst="")

    values = {k: data.get(k) for k in
              ("rssi", "snr", "q", "latitude", "longitude", "battery", "rnode_battery",
               "steunpunt_rssi", "steunpunt_snr")}
    flat = {"sender": data["sender"], "sender_name": data["sender_name"],
            "timestamp": data["timestamp"], "rssi_bron": data["rssi_bron"], "steunpunt": src}
    flat.update(values)
    publish("signaal", flat)
    base = f"{MQTT_TOPIC}/signaal/{topic_name(data['sender_name'], d.get('adr', ''))}"
    for k, v in values.items():
        if v is not None:
            mqtt_client.publish(f"{base}/{k}", str(v), qos=1)

    log(f"[GPS] {data['sender_name']} via {src}: lat={data['latitude']} lon={data['longitude']} "
        f"rssi={data['rssi']} ({data['rssi_bron']}) bat={data['battery']} rbat={data['rnode_battery']}")


def handle_msg(src, d):
    data = {"type": "MESSAGE", **common(d, src),
            "rssi": num(d, "s_rssi"), "snr": num(d, "s_snr"),
            "latitude": num(d, "lat"), "longitude": num(d, "lon"),
            "raw_payload": d.get("tekst", "")}
    publish("message", data)
    logboek("BERICHT", src, d, data["voor_mij"],
            regels=kop("BERICHT", src, d, data["voor_mij"]) + [data["raw_payload"]])
    meelees = "" if data["voor_mij"] else " (meelezen)"
    log(f"[MSG] {data['sender_name']} via {src} aan {','.join(data['aan']) or '-'}{meelees}: "
        f"{data['raw_payload'][:80]}")


def handle_mth(src, d):
    parsed = methane.parse_methane(d.get("tekst", ""))
    if not parsed:
        log(f"[-] M/ETHANE van {d.get('van')} kon niet gelezen worden; als gewoon bericht doorgezet")
        handle_msg(src, d)
        return
    record = methane.build_record(
        parsed,
        afzender=d.get("adr", ""),
        ontvanger=src,
        rssi=num(d, "s_rssi"),
        snr=num(d, "s_snr"),
        tz_name=METHANE_TZ,
        cache=methane_cache,
    )
    record["afzender_naam"] = d.get("van")
    record.update({k: v for k, v in common(d, src).items()
                   if k in ("steunpunt", "steunpunt_naam", "aan", "voor_mij", "eindpost", "onbevestigd")})
    # Locatie van de melder, als die in de app is meegestuurd
    record["latitude"] = num(d, "lat")
    record["longitude"] = num(d, "lon")
    record["accuracy_m"] = num(d, "nauwk")
    publish("methane", record)
    publish("methane/laatste", record, retain=True)
    plek = f"  positie melder: {record['latitude']}, {record['longitude']}" if record["latitude"] is not None else ""
    logboek("M/ETHANE", src, d, record["voor_mij"], meldcode=record.get("meldcode", ""),
            regels=kop("M/ETHANE", src, d, record["voor_mij"], "  " + str(record.get("meldcode", "")))
            + [d.get("tekst", "")] + ([plek] if plek else []))
    extra = " (herhaalde verzending)" if record["herhaling"] else ""
    extra += "" if record["voor_mij"] else " (meelezen)"
    if record["latitude"] is not None:
        extra += f" @ {record['latitude']},{record['longitude']}"
    log(f"[MTH] {record['meldcode']}{extra} van {record['afzender_naam']} via {src} "
        f"aan {','.join(record['aan']) or '-'} | "
        f"groot incident: {record['groot_incident']} | soort: {record['soort_incident']} | "
        f"locatie: {record['locatie']}")


def handle_ann(src, d):
    data = {"type": "ANNOUNCE", **common(d, src), "rssi": None, "snr": None, "status": "online"}
    publish("announce", data)
    log(f"[ANN] {data['sender_name']} is in de lucht (via {src})")


def handle_sta(src, d):
    if d.get("naam"):
        steunpunt_namen[src] = d["naam"]
    data = {"type": "STEUNPUNT", "steunpunt": d.get("stp", src), "steunpunt_naam": d.get("naam"),
            "timestamp": time.time(), "latitude": num(d, "lat"), "longitude": num(d, "lon"),
            "wachtrij": num(d, "wachtrij"), "aangemeld": num(d, "aangemeld"),
            "gehoord": num(d, "gehoord"), "accu_laag": num(d, "laag"),
            "uptime_s": num(d, "uptime"), "status": "online"}
    publish(f"steunpunt/{topic_name(src, src)}", data, retain=True)
    samen = (f"steunpunt {d.get('naam') or src} leeft: aangemeld {data['aangemeld']}, gehoord {data['gehoord']}, "
             f"accu laag {data['accu_laag']}, wachtrij {data['wachtrij']}")
    logboek("STATUS", src, {"van": d.get("naam") or src}, True, tekst=samen, regels=[f"--- {time.strftime('%H:%M:%S')}  {samen}"])
    log(f"[STA] Steunpunt {d.get('naam') or src} ({src}) leeft; wachtrij {data['wachtrij']}, "
        f"aangemeld {data['aangemeld']}, gehoord {data['gehoord']}, accu laag {data['accu_laag']}")


HANDLERS = {"GPS": handle_gps, "MSG": handle_msg, "MTH": handle_mth,
            "ANN": handle_ann, "STA": handle_sta}


# ---------------------------------------------------------------------------
# 2 m ontvangen
# ---------------------------------------------------------------------------

reassembler = proto.Reassembler()


def on_frame(src, dst, info):
    parsed = proto.parse_info(info)
    if not parsed:
        return
    soort, msg_id, i, n, chunk = parsed
    if soort == "ACK":
        return
    if TOEGESTANE_STEUNPUNTEN and src.upper() not in [s.upper() for s in TOEGESTANE_STEUNPUNTEN]:
        log(f"[x] Frame van onbekend steunpunt {src} genegeerd")
        return
    body = reassembler.add(src, soort, msg_id, i, n, chunk, time.time())
    if body is None:
        return                          # wacht op de overige delen

    d = proto.parse_body(body)
    voor_mij = is_voor_mij(d)
    bevestigen = soort in proto.ACK_SOORTEN and voor_mij

    # Altijd bevestigen wat voor ons is (ook herhalingen), anders blijft het
    # steunpunt herhalen. Meelezen wordt nooit bevestigd.
    if bevestigen:
        for ack in proto.make_infos("ACK", msg_id, ""):
            link.send_info(ack)

    if soort in ("MSG", "MTH") and not voor_mij and not MEELEZEN:
        if not already_seen(f"{src}|{msg_id}|niet"):
            log(f"[·] {soort} {msg_id} van {src} is voor {d.get('aan')}, niet voor deze post")
        return

    if already_seen(f"{src}|{msg_id}"):
        extra = ", opnieuw bevestigd" if bevestigen else ""
        log(f"[=] {soort} {msg_id} van {src} al ontvangen (herhaling){extra}")
        return
    try:
        HANDLERS[soort](src, d)
    except Exception as e:
        log(f"[-] Fout bij verwerken {soort} {msg_id}: {e}")


link = proto.KissLink(DIREWOLF_HOST, DIREWOLF_PORT, CALLSIGN, on_frame, log=log)

log(f"[!] EINDPOST ACTIEF: '{EINDPOST_NAAM}', roepnaam {CALLSIGN}, disciplines {', '.join(DISCIPLINES)}"
    + (", meelezen AAN" if MEELEZEN else ""))
if _INST_FOUT:
    log(f"[!] {INSTELLINGEN_FILE} onleesbaar ({_INST_FOUT}); standaardwaarden gebruikt")
log(f"    Logboek: {LOGBOEK_DIR}  |  MQTT: {MQTT_BROKER}:{MQTT_PORT}")
log("    Wacht op berichten van de steunpunten...")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    link.close()
    mqtt_client.loop_stop()
    sys.exit(0)

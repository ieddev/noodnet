"""
steunpunt_brug.py - draait op de Pi van een Noodsteunpunt (versie 2).

Het Steunpunt is een doorgeefluik:

    vrijwilliger -> LoRa (ISM) -> DIT STEUNPUNT -> leesbare tekst over 2 m
                                                   -> eindposten (brandweer,
                                                      ambulance, gemeente, ...)

Wat dit script doet:
  - ontvangt LXMF-berichten van de telefoons via LoRa (versleuteld mag daar);
  - zendt de inhoud als LEESBARE AX.25-tekst met roepnaam over 2 meter;
  - M/ETHANE gaat naar de disciplines uit "GEMELD AAN", en wordt herhaald tot
    ELKE geadresseerde eindpost een ACK heeft gestuurd;
  - chatberichten gaan naar 'berichten_aan' uit de netwerkconfig, of naar wie
    met @discipline aan het begin van het bericht genoemd wordt;
  - AANMELDEN: vrijwilligers melden zich aan met de code van de kaart; de
    zendamateur (beheerder) keurt goed met JA/NEE vanuit zijn eigen Sideband;
  - hartslag (STA) met naam en vaste coördinaten van dit steunpunt.

Benodigd naast dit script: noodnet_proto.py en noodnet_netwerk.json.
rnsd moet draaien (shared instance), Direwolf met KISSPORT 8001.
In de Reticulum-config van de Pi mag GEEN interface naar Direwolf aan staan.
"""

import hashlib
import json
import os
import random
import re
import struct
import sys
import threading
import time

import RNS
import LXMF

import noodnet_proto as proto

# ---- CONFIGURATIE (per steunpunt) ------------------------------------------
# Stel dit in via de beheerpagina (http://<pi>:8080) of in
# steunpunt_instellingen.json. Die waarden gaan VOOR; wat hieronder staat zijn
# alleen de standaardwaarden als er nog niets is ingesteld.
# Naam van dit steunpunt; zo verschijnt het in Sideband en bij de eindposten
STEUNPUNT_NAAM = "Noodsteunpunt"
# Roepnaam van dit steunpunt op 2 m (elk steunpunt een eigen roepnaam/SSID)
CALLSIGN = "N0CALL-1"
# Vaste locatie van dit steunpunt (graden, decimaal). None = niet meesturen.
LATITUDE = None
LONGITUDE = None

# Code die op de kaart staat. Wijzig na elke inzet (kan ook op afstand door
# de beheerder met: CODE <nieuwe code>).
AANMELDCODE = "WIJZIG-MIJ"
# LXMF-adressen (32 tekens) van de zendamateur(s) die aanmeldingen
# goedkeuren. Zie in Sideband: "Your address".
BEHEERDERS = [
    # "0123456789abcdef0123456789abcdef",
]

# Witte lijst: "uit", "leren" of "aan". Met "aan" komen alleen aangemelde
# (goedgekeurde) telefoons door. Aanmelden en beheer werken altijd.
WHITELIST_MODE = "aan"

DIREWOLF_HOST = "127.0.0.1"
DIREWOLF_PORT = 8001

# Bekendmaken van dit steunpunt via LoRa (seconden)
ANNOUNCE_INTERVAL = 60 * 60
# Announces van telefoons doorgeven (ANN), max 1x per telefoon per periode. 0 = nooit
ANN_DOORGEVEN_INTERVAL = 60 * 60
# Hartslag naar de eindposten (STA). 0 = uit
STATUS_INTERVAL = 30 * 60
# Bewaking van aangemelde vrijwilligers (bericht naar de beheerders, niets over 2 m)
# "Uit beeld" na dit aantal minuten stilte. None = automatisch: 1,5 x het
# baken-interval uit noodnet_netwerk.json (standaard 30 min -> 45 min).
UIT_BEELD_MIN = None
BATTERIJ_LAAG = 20          # % accu van de RNode waarbij gewaarschuwd wordt

# Herhalen tot ACK (chat en M/ETHANE): wachttijden tussen de pogingen (s)
HERHAAL_SCHEMA = [30, 60, 120, 240, 300, 300, 300, 300, 300, 300]
# Deze soorten worden nooit opgegeven (blijven elke 5 min herhaald)
NOOIT_OPGEVEN = ("MTH",)
# Minimale pauze tussen twee berichten op 2 m (s)
MIN_PAUZE = 3
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INSTELLINGEN_FILE = os.path.join(SCRIPT_DIR, "steunpunt_instellingen.json")

# Instellingen uit steunpunt_instellingen.json (beheerpagina) gaan voor
_INST_SLEUTELS = {
    "steunpunt_naam": "STEUNPUNT_NAAM", "roepnaam": "CALLSIGN",
    "latitude": "LATITUDE", "longitude": "LONGITUDE",
    "aanmeldcode": "AANMELDCODE", "witte_lijst_modus": "WHITELIST_MODE",
    "uit_beeld_min": "UIT_BEELD_MIN", "batterij_laag": "BATTERIJ_LAAG",
}
_INSTELLINGEN_FOUT = None
try:
    with open(INSTELLINGEN_FILE, "r", encoding="utf-8") as _f:
        _inst = json.load(_f)
    for _k, _var in _INST_SLEUTELS.items():
        if _k in _inst and _inst[_k] not in ("", None):
            globals()[_var] = _inst[_k]
    if isinstance(_inst.get("beheerders"), list):
        BEHEERDERS = [b.get("adres", "") if isinstance(b, dict) else b for b in _inst["beheerders"]]
except FileNotFoundError:
    pass
except (OSError, ValueError) as _e:
    _INSTELLINGEN_FOUT = str(_e)

WHITELIST_FILE = os.path.join(SCRIPT_DIR, "witte_lijst.txt")
UNKNOWN_SENDERS_FILE = os.path.join(SCRIPT_DIR, "onbekende_afzenders.txt")
NETWERK_FILE = os.path.join(SCRIPT_DIR, "noodnet_netwerk.json")

storage_path = os.path.expanduser("~/.reticulum/lxmf")
os.makedirs(storage_path, exist_ok=True)
IDENTITY_FILE = os.path.join(storage_path, "gateway.id")
OUTBOX_FILE = os.path.join(storage_path, "brug_wachtrij.json")
FAILED_FILE = os.path.join(storage_path, "brug_mislukt.json")
SENDER_NAMES_PATH = os.path.join(storage_path, "sender_names.json")
AANMELD_FILE = os.path.join(storage_path, "aanmeldingen.json")
GEHOORD_FILE = os.path.join(storage_path, "gehoord.json")
OPDRACHTEN_FILE = os.path.join(storage_path, "web_opdrachten.json")   # van de beheerpagina
RONDZENDING_FILE = os.path.join(storage_path, "rondzending.json")     # laatste bericht aan alle vrijwilligers
BERICHTEN_FILE = os.path.join(storage_path, "berichten.json")         # laatste berichten aan één vrijwilliger


def log(msg):
    print(time.strftime("%H:%M:%S ") + msg, flush=True)


def norm_call(call):
    call = str(call).strip().upper()
    return call[:-2] if call.endswith("-0") else call


def _norm_hash(h):
    return str(h).replace("<", "").replace(">", "").replace(":", "").replace(" ", "").strip().lower()


def _controleer_beheerders(lijst):
    """Houdt alleen geldige adressen over (32 hex-tekens). Een losse tekst
    in plaats van een lijst wordt ook geaccepteerd."""
    if isinstance(lijst, str):
        lijst = [lijst]
    goed, fout = [], []
    for b in lijst:
        n = _norm_hash(b)
        if re.fullmatch(r"[0-9a-f]{32}", n):
            goed.append(n)
        else:
            fout.append(str(b))
    return goed, fout


BEHEERDERS, _BEHEERDERS_FOUT = _controleer_beheerders(BEHEERDERS)


# ---------------------------------------------------------------------------
# Netwerkconfig (disciplines en eindposten), wordt bij wijziging herladen
# ---------------------------------------------------------------------------

_netwerk = {"mtime": None, "data": {}}


def netwerk():
    try:
        mtime = os.path.getmtime(NETWERK_FILE)
    except OSError:
        if _netwerk["mtime"] is not False:
            log(f"[!] Geen {os.path.basename(NETWERK_FILE)} gevonden: alle meldingen gaan naar "
                f"elke eindpost ('alle'); de eerste ACK telt.")
            _netwerk.update(mtime=False, data={})
        return _netwerk["data"]
    if mtime != _netwerk["mtime"]:
        try:
            with open(NETWERK_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            _netwerk.update(mtime=mtime, data=data)
            disc = data.get("disciplines", {})
            log(f"[+] Netwerkconfig '{data.get('gemeente', '?')}' ingelezen: "
                + ", ".join(f"{k}({len(v.get('eindposten', []))})" for k, v in disc.items()))
        except (OSError, ValueError) as e:
            log(f"[-] Kon {NETWERK_FILE} niet lezen: {e} (vorige versie blijft actief)")
            _netwerk["mtime"] = mtime
    return _netwerk["data"]


def discipline_key(label):
    """Zet een naam uit 'GEMELD AAN' of '@...' om naar een discipline-sleutel."""
    lab = label.strip().strip("@").strip().lower()
    if not lab:
        return None
    for key, d in netwerk().get("disciplines", {}).items():
        if lab == key.lower() or lab == str(d.get("label", "")).lower():
            return key
    return lab        # onbekende discipline: toch meenemen, dan zie je hem bij de eindposten


def route(labels):
    """Geeft (aan, wacht_op): disciplines en de roepnamen waarvan een ACK nodig is."""
    net = netwerk()
    disc = net.get("disciplines", {})
    aan = []
    for lab in labels:
        k = discipline_key(lab)
        if k and k not in aan:
            aan.append(k)
    wacht = {norm_call(c) for k in aan for c in disc.get(k, {}).get("eindposten", [])}
    if not wacht:
        for k in net.get("vangnet", []):
            if k not in aan:
                aan.append(k)
            wacht |= {norm_call(c) for c in disc.get(k, {}).get("eindposten", [])}
    if not wacht:
        wacht = {"*"}          # geen eindposten bekend: eerste ACK van wie dan ook telt
    return aan, sorted(wacht)


# ---------------------------------------------------------------------------
# Afzendernamen
# ---------------------------------------------------------------------------

_names_lock = threading.Lock()


def _load_sender_names():
    try:
        with open(SENDER_NAMES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {_norm_hash(k): v for k, v in data.items() if isinstance(v, str) and v.strip()}
    except (OSError, ValueError, AttributeError):
        return {}


sender_names = _load_sender_names()


def _save_sender_names():
    tmp = SENDER_NAMES_PATH + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(sender_names, f, ensure_ascii=False, indent=1)
        os.replace(tmp, SENDER_NAMES_PATH)
    except OSError as e:
        log(f"[-] Kon afzendernamen niet opslaan: {e}")


def name_from_app_data(app_data):
    try:
        name = LXMF.display_name_from_app_data(app_data)
    except Exception:
        return None
    if isinstance(name, str):
        name = name.replace("\x00", "").strip()
        return name or None
    return None


def remember_sender_name(hash_bytes, name):
    if not name:
        return
    key = hash_bytes.hex()
    with _names_lock:
        if sender_names.get(key) != name:
            sender_names[key] = name
            _save_sender_names()


def sender_name_for(hash_bytes):
    key = hash_bytes.hex()
    with _names_lock:
        if key in sender_names:
            return sender_names[key]
    try:
        name = name_from_app_data(RNS.Identity.recall_app_data(hash_bytes))
    except Exception:
        name = None
    remember_sender_name(hash_bytes, name)
    return name


# ---------------------------------------------------------------------------
# Witte lijst
# ---------------------------------------------------------------------------

_WHITELIST_TEMPLATE = """# Witte lijst van dit steunpunt
# Per regel: LXMF-adres van een telefoon (32 tekens), daarna een naam.
# Wordt ook automatisch aangevuld bij goedgekeurde aanmeldingen.
"""

_whitelist = {}
_whitelist_mtime = None
_whitelist_lock = threading.Lock()
_reported_unknown = set()


def _load_whitelist():
    global _whitelist, _whitelist_mtime
    try:
        mtime = os.path.getmtime(WHITELIST_FILE)
    except OSError:
        try:
            with open(WHITELIST_FILE, "w", encoding="utf-8") as f:
                f.write(_WHITELIST_TEMPLATE)
            log(f"[i] Witte lijst aangemaakt: {WHITELIST_FILE}")
            mtime = os.path.getmtime(WHITELIST_FILE)
        except OSError as e:
            log(f"[-] Kon witte lijst niet aanmaken: {e}")
            return
    if mtime == _whitelist_mtime:
        return
    entries = {}
    try:
        with open(WHITELIST_FILE, "r", encoding="utf-8") as f:
            for nr, line in enumerate(f, 1):
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue
                parts = line.split(None, 1)
                h = _norm_hash(parts[0])
                if len(h) != 32 or any(c not in "0123456789abcdef" for c in h):
                    log(f"[-] Witte lijst regel {nr}: '{parts[0]}' is geen geldig adres, overgeslagen")
                    continue
                entries[h] = parts[1].strip() if len(parts) > 1 else ""
    except OSError as e:
        log(f"[-] Kon witte lijst niet lezen: {e}")
        return
    with _whitelist_lock:
        _whitelist = entries
        _whitelist_mtime = mtime
    log(f"[+] Witte lijst ingelezen: {len(entries)} telefoon(s) (modus: {WHITELIST_MODE})")


def whitelist_entries():
    _load_whitelist()
    with _whitelist_lock:
        return dict(_whitelist)


def whitelist_add(hash_hex, naam, door):
    _load_whitelist()
    with _whitelist_lock:
        if hash_hex in _whitelist:
            return False
    with open(WHITELIST_FILE, "a", encoding="utf-8") as f:
        f.write(f"{hash_hex}   {naam}   # aangemeld {time.strftime('%Y-%m-%d %H:%M')}, goedgekeurd door {door}\n")
    _load_whitelist()
    return True


def whitelist_remove(zoek):
    """Verwijdert regels waarvan de naam gelijk is of het adres begint met 'zoek'."""
    zoek = zoek.strip().lower()
    if not zoek:
        return []
    weg, keep = [], []
    with open(WHITELIST_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines:
        kern = line.split("#", 1)[0].strip()
        parts = kern.split(None, 1)
        if parts:
            h = _norm_hash(parts[0])
            naam = parts[1].strip().lower() if len(parts) > 1 else ""
            if naam == zoek or (len(zoek) >= 6 and h.startswith(zoek)):
                weg.append((h, parts[1].strip() if len(parts) > 1 else ""))
                continue
        keep.append(line)
    if weg:
        with open(WHITELIST_FILE, "w", encoding="utf-8") as f:
            f.writelines(keep)
        _load_whitelist()
    return weg


def _remember_unknown(hash_hex, name):
    try:
        existing = ""
        if os.path.exists(UNKNOWN_SENDERS_FILE):
            with open(UNKNOWN_SENDERS_FILE, "r", encoding="utf-8") as f:
                existing = f.read()
        if hash_hex in existing:
            return
        with open(UNKNOWN_SENDERS_FILE, "a", encoding="utf-8") as f:
            f.write(f"{hash_hex}   {name or ''}   # gezien {time.strftime('%Y-%m-%d %H:%M')}\n")
    except OSError as e:
        log(f"[-] Kon onbekende afzender niet opslaan: {e}")


def sender_allowed(hash_bytes, sender_name, soort):
    mode = (WHITELIST_MODE or "uit").strip().lower()
    if mode == "uit":
        return True
    h = hash_bytes.hex()
    if h in whitelist_entries() or h in {_norm_hash(b) for b in BEHEERDERS}:
        return True
    first = h not in _reported_unknown
    _reported_unknown.add(h)
    if first:
        _remember_unknown(h, sender_name)
    if mode == "leren":
        if first:
            log(f"[?] Niet-aangemelde telefoon: {sender_name or 'onbekend'} <{h}> ({soort}); "
                f"wordt nog doorgegeven (modus 'leren').")
        return True
    if first or soort != "announce":
        log(f"[x] GEWEIGERD ({soort}) van {sender_name or 'onbekend'} <{h}>: niet aangemeld")
    return False


# ---------------------------------------------------------------------------
# Telemetrie en signaalwaarden
# ---------------------------------------------------------------------------

SID_TIME, SID_LOCATION, SID_BATTERY = 1, 2, 4


def decode_telemetry(raw):
    out = {}
    try:
        import RNS.vendor.umsgpack as msgpack
        decoded = msgpack.unpackb(raw)
    except Exception as e:
        log(f"[-] Kon telemetrie niet decoderen: {e}")
        return out
    if not isinstance(decoded, dict):
        return out
    if SID_TIME in decoded:
        out["tijd"] = decoded[SID_TIME]
    loc = decoded.get(SID_LOCATION)
    if isinstance(loc, (list, tuple)) and len(loc) >= 6:
        try:
            out["lat"] = round(struct.unpack("!i", loc[0])[0] / 1e6, 5)
            out["lon"] = round(struct.unpack("!i", loc[1])[0] / 1e6, 5)
            out["alt"] = round(struct.unpack("!i", loc[2])[0] / 1000.0, 1)
            out["snelh"] = round(struct.unpack("!i", loc[3])[0] / 1000.0, 1)
            out["richt"] = round(struct.unpack("!i", loc[4])[0] / 100.0)
            out["nauwk"] = round(struct.unpack("!H", loc[5])[0] / 1000.0, 1)
        except Exception as e:
            log(f"[-] Kon locatie niet uitpakken: {e}")
    bat = decoded.get(SID_BATTERY)
    if isinstance(bat, (list, tuple)) and bat:
        try:
            out["bat"] = round(float(bat[0]))
            if len(bat) >= 2:
                out["laden"] = 1 if bat[1] else 0
        except Exception:
            pass
    return out


def message_telemetry(message):
    try:
        if message.fields and LXMF.FIELD_TELEMETRY in message.fields:
            tel = message.fields[LXMF.FIELD_TELEMETRY]
            if tel:
                return decode_telemetry(tel)
    except Exception:
        pass
    return {}


def parse_link_stats(text):
    """Leest "RSSI=-97;SNR=6.25;Q=80;BAT=85" van de plugin send_Telemetry.py."""
    if not text:
        return {}
    keys = {"RSSI": "m_rssi", "SNR": "m_snr", "Q": "m_q", "BAT": "rbat"}
    result = {}
    for part in text.strip().split(";"):
        if "=" not in part:
            return {}
        k, v = part.split("=", 1)
        k = k.strip().upper()
        if k not in keys:
            return {}
        try:
            f = float(v.strip())
        except ValueError:
            return {}
        result[keys[k]] = int(f) if f == int(f) else round(f, 2)
    return result


def _num(v):
    if v is None:
        return None
    try:
        f = float(v)
        return int(f) if f == int(f) else round(f, 2)
    except (TypeError, ValueError):
        return None


_GEMELD_RE = re.compile(r"^\s*GEMELD\s+AAN\s*:\s*(.*)$", re.I | re.M)


def gemeld_aan(text):
    m = _GEMELD_RE.search(text or "")
    if not m:
        return []
    return [p.strip() for p in m.group(1).split(",") if p.strip() and p.strip().lower() != "onbekend"]


_LOC_RE = re.compile(r"^\s*LOCATIE\s*:\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)(?:\s*\(±\s*(\d+(?:\.\d+)?)\s*m\))?", re.I | re.M)


def lees_locatie_regel(text):
    m = _LOC_RE.search(text or "")
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(2))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon, (float(m.group(3)) if m.group(3) else None)


def chat_adressen(text):
    """'@brandweer @gemeente tekst' -> ['brandweer', 'gemeente']"""
    labels = []
    for woord in (text or "").split():
        if woord.startswith("@") and len(woord) > 1:
            labels.append(woord[1:].strip(",.:;"))
        else:
            break
    return labels


# ---------------------------------------------------------------------------
# Wachtrij voor 2 m, met ACK per eindpost
# ---------------------------------------------------------------------------

class Outbox:
    def __init__(self):
        self.lock = threading.Lock()
        self.items = []
        self.recent = {}
        try:
            with open(OUTBOX_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.items = data.get("items", [])
            self.recent = data.get("recent", {})
            for i in self.items:                      # wachtrij van versie 1
                i.setdefault("wacht_op", ["*"] if i.get("ack") else [])
            if self.items:
                log(f"[i] Wachtrij hersteld: {len(self.items)} bericht(en) nog te verzenden")
        except (OSError, ValueError):
            pass

    def _save(self):
        tmp = OUTBOX_FILE + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"items": self.items, "recent": self.recent}, f, ensure_ascii=False)
            os.replace(tmp, OUTBOX_FILE)
        except OSError as e:
            log(f"[-] Kon wachtrij niet opslaan: {e}")

    def add(self, soort, msg_id, body, wacht_op=None):
        now = time.time()
        ack = soort in proto.ACK_SOORTEN
        with self.lock:
            self.recent = {k: v for k, v in self.recent.items() if now - v < 24 * 3600}
            if msg_id in self.recent or any(i["id"] == msg_id for i in self.items):
                return False
            self.recent[msg_id] = now
            self.items.append({
                "id": msg_id, "soort": soort, "body": body, "ack": ack,
                "wacht_op": list(wacht_op or (["*"] if ack else [])),
                "pogingen": 0, "volgende": 0, "gemaakt": now,
            })
            self._save()
        return True

    def next_due(self):
        now = time.time()
        with self.lock:
            due = [i for i in self.items if i["volgende"] <= now]
            if not due:
                return None
            prio = {"MTH": 0, "MSG": 1, "STA": 2, "GPS": 3, "ANN": 4}
            due.sort(key=lambda i: (prio.get(i["soort"], 9), i["gemaakt"]))
            return dict(due[0])

    def sent(self, msg_id):
        with self.lock:
            for item in self.items:
                if item["id"] != msg_id:
                    continue
                item["pogingen"] += 1
                if not item["ack"]:
                    self.items.remove(item)
                else:
                    wacht = HERHAAL_SCHEMA[min(item["pogingen"], len(HERHAAL_SCHEMA)) - 1]
                    # Willekeurig 75-125%: twee steunpunten die elkaar niet horen en tegelijk
                    # zonden, botsen anders bij elke herhaling opnieuw op hetzelfde moment.
                    item["volgende"] = time.time() + wacht * random.uniform(0.75, 1.25)
                break
            self._save()

    def give_up_if_exhausted(self, msg_id):
        with self.lock:
            for item in self.items:
                if (item["id"] == msg_id and item["ack"] and item["soort"] not in NOOIT_OPGEVEN
                        and item["pogingen"] >= len(HERHAAL_SCHEMA)):
                    self.items.remove(item)
                    self._failed(item)
                    self._save()
                    return True
        return False

    def acked(self, msg_id, van):
        van = norm_call(van)
        with self.lock:
            for item in self.items:
                if item["id"] != msg_id:
                    continue
                wacht = item["wacht_op"]
                if "*" in wacht:
                    wacht.clear()
                elif van in wacht:
                    wacht.remove(van)
                else:
                    return False            # ACK van een eindpost waar we niet op wachten
                duur = time.time() - item["gemaakt"]
                if wacht:
                    log(f"[✓] ACK van {van} voor {item['soort']} {msg_id}; wacht nog op: {', '.join(wacht)}")
                    self._save()
                else:
                    self.items.remove(item)
                    self._save()
                    log(f"[✓] {item['soort']} {msg_id} door alle eindposten bevestigd "
                        f"(laatste: {van}; {item['pogingen']} poging(en), {duur:.0f} s)")
                return True
        return False

    def niet_meer_wachten(self, msg_id, call):
        """Beheerpagina: niet langer wachten op de ACK van één eindpost. Geeft tekst voor het log."""
        call = norm_call(call)
        with self.lock:
            for item in self.items:
                if item["id"] != msg_id:
                    continue
                if call not in item["wacht_op"]:
                    return f"{item['soort']} {msg_id} wachtte niet op {call}"
                item["wacht_op"].remove(call)
                if not item["wacht_op"]:
                    self.items.remove(item)
                    self._save()
                    return f"{item['soort']} {msg_id}: niet meer gewacht op {call}; uit de wachtrij"
                self._save()
                return f"{item['soort']} {msg_id}: niet meer gewacht op {call}; wacht nog op {', '.join(item['wacht_op'])}"
        return f"{msg_id} staat niet (meer) in de wachtrij"

    def _failed(self, item):
        log(f"[!] MISLUKT: {item['soort']} {item['id']} niet bevestigd door: "
            f"{', '.join(item['wacht_op'])}. Bewaard in {FAILED_FILE}")
        try:
            failed = []
            if os.path.exists(FAILED_FILE):
                with open(FAILED_FILE, "r", encoding="utf-8") as f:
                    failed = json.load(f)
            item["mislukt_op"] = time.strftime("%Y-%m-%d %H:%M:%S")
            failed.append(item)
            with open(FAILED_FILE, "w", encoding="utf-8") as f:
                json.dump(failed, f, ensure_ascii=False, indent=1)
        except (OSError, ValueError) as e:
            log(f"[-] Kon mislukt bericht niet bewaren: {e}")

    def counts(self):
        with self.lock:
            return len(self.items)


outbox = Outbox()


def make_id(*parts):
    h = hashlib.sha256()
    for p in parts:
        h.update(p if isinstance(p, bytes) else str(p).encode())
    return h.hexdigest()[:6]


def queue(soort, msg_id, fields, tekst=None, wacht_op=None):
    body = proto.build_body(fields, tekst)
    if outbox.add(soort, msg_id, body, wacht_op):
        extra = f" -> ACK nodig van {', '.join(wacht_op)}" if wacht_op else ""
        log(f"[>] In wachtrij voor 2 m: {soort} {msg_id} ({len(body)} tekens){extra}")


# ---------------------------------------------------------------------------
# 2 m: zenden en ACK's ontvangen
# ---------------------------------------------------------------------------

def on_frame(src, dst, info):
    parsed = proto.parse_info(info)
    if not parsed:
        return
    soort, msg_id, _, _, _ = parsed
    if soort == "ACK":
        outbox.acked(msg_id, src)


link = proto.KissLink(DIREWOLF_HOST, DIREWOLF_PORT, CALLSIGN, on_frame, log=log)


def sender_loop():
    while True:
        item = outbox.next_due()
        if not item or not link.connected.is_set():
            time.sleep(1)
            continue
        if outbox.give_up_if_exhausted(item["id"]):
            continue
        infos = proto.make_infos(item["soort"], item["id"], item["body"])
        if all(link.send_info(i) for i in infos):
            poging = item["pogingen"] + 1
            extra = f" (poging {poging})" if item["ack"] and poging > 1 else ""
            delen = f", {len(infos)} delen" if len(infos) > 1 else ""
            log(f"[→] 2 m: {item['soort']} {item['id']}{delen}{extra}")
            outbox.sent(item["id"])
            time.sleep(MIN_PAUZE)
        else:
            time.sleep(5)


threading.Thread(target=sender_loop, daemon=True).start()


# ---------------------------------------------------------------------------
# Reticulum / LXMF
# ---------------------------------------------------------------------------

rns = RNS.Reticulum()
if not getattr(rns, "is_connected_to_shared_instance", True):
    # rnsd draait (nog) niet: niet zelf de RNodes openen, maar stoppen; systemd probeert het zo opnieuw
    log("[!] Reticulum (rnsd) draait nog niet; de brug stopt en probeert het over 10 s opnieuw.")
    os._exit(1)

if os.path.exists(IDENTITY_FILE):
    identity = RNS.Identity.from_file(IDENTITY_FILE)
    log("[+] Identiteit van dit steunpunt ingeladen.")
else:
    identity = RNS.Identity()
    identity.to_file(IDENTITY_FILE)
    log("[+] Nieuwe identiteit voor dit steunpunt aangemaakt (eigen adres).")

def ruim_kapotte_ratchets():
    """Een ratchet-bestand dat leeg of half is (stroom weg tijdens het schrijven) laat de brug
    bij elke start crashen. Zet zo'n bestand opzij; Reticulum maakt een nieuw en het steunpunt
    announcet direct na de start, zodat de telefoons de nieuwe sleutel krijgen."""
    import RNS.vendor.umsgpack as umsgpack
    weg = []
    for map_ in (os.path.join(storage_path, "lxmf", "ratchets"),):
        if not os.path.isdir(map_):
            continue
        for naam in os.listdir(map_):
            pad = os.path.join(map_, naam)
            if not os.path.isfile(pad) or ".kapot-" in naam or naam.endswith(".tmp"):
                continue
            try:
                with open(pad, "rb") as f:
                    data = f.read()
                if not data:
                    raise ValueError("leeg bestand")
                umsgpack.unpackb(data)
            except Exception as fout:
                kapot = pad + ".kapot-" + time.strftime("%Y%m%d-%H%M%S")
                try:
                    os.replace(pad, kapot)
                    weg.append(naam)
                    log(f"[!] Beschadigd ratchet-bestand opzij gezet ({str(fout) or type(fout).__name__}): {kapot}")
                except OSError as e2:
                    log(f"[-] Kon beschadigd ratchet-bestand niet opzij zetten: {pad} ({e2})")
    if weg:
        log("[i] Waarschijnlijk viel de stroom weg tijdens het schrijven. Nieuwe sleutels worden gemaakt en direct ge-announced.")
    return weg


ruim_kapotte_ratchets()
lxmf_router = LXMF.LXMRouter(identity=identity, storagepath=storage_path)
try:
    my_destination = lxmf_router.register_delivery_identity(identity, display_name=STEUNPUNT_NAAM)
except OSError as fout:
    # Vangnet als de controle hierboven iets mist: bestand opzij en nog één keer proberen
    if "ratchet" not in str(fout).lower():
        raise
    m = re.search(r"([0-9a-f]{32})", str(fout))
    pad = os.path.join(storage_path, "lxmf", "ratchets", (m.group(1) if m else "") + ".ratchets")
    if m and os.path.exists(pad):
        os.replace(pad, pad + ".kapot-" + time.strftime("%Y%m%d-%H%M%S"))
        log(f"[!] Ratchet-bestand onleesbaar, opzij gezet: {pad}")
    my_destination = lxmf_router.register_delivery_identity(identity, display_name=STEUNPUNT_NAAM)


def stuur_lxmf(dest_hash, tekst, afgeleverd=None, mislukt=None, wacht=0):
    """Stuurt een kort LXMF-bericht naar een telefoon (via LoRa).
    afgeleverd/mislukt: optioneel, aangeroepen als de telefoon het bericht wel/niet heeft gekregen.
    wacht: seconden wachten voor het versturen (om een reeks berichten te spreiden)."""
    def _run():
        if wacht:
            time.sleep(wacht)
        for i in range(45):
            ident = RNS.Identity.recall(dest_hash)
            if ident:
                break
            if i % 15 == 0:
                RNS.Transport.request_path(dest_hash)
            time.sleep(1)
        else:
            log(f"[-] Kan geen bericht sturen naar <{dest_hash.hex()}>: adres onbekend")
            if mislukt:
                mislukt(dest_hash.hex())
            return
        dest = RNS.Destination(ident, RNS.Destination.OUT, RNS.Destination.SINGLE, "lxmf", "delivery")
        m = LXMF.LXMessage(dest, my_destination, tekst, desired_method=LXMF.LXMessage.OPPORTUNISTIC)
        m.try_propagation_on_fail = False
        if afgeleverd:
            m.register_delivery_callback(lambda _m: afgeleverd(dest_hash.hex()))
        if mislukt:
            m.register_failed_callback(lambda _m: mislukt(dest_hash.hex()))
        lxmf_router.handle_outbound(m)
    threading.Thread(target=_run, daemon=True).start()


# ---------------------------------------------------------------------------
# Aanmelden en beheer
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Wie is er gehoord? (laatst gehoord, positie, accu) - alleen lokaal
# ---------------------------------------------------------------------------

def uit_beeld_na():
    if UIT_BEELD_MIN:
        return int(UIT_BEELD_MIN) * 60
    try:
        mx = int(netwerk().get("baken", {}).get("max_interval_s", 1800))
    except Exception:
        mx = 1800
    return max(15 * 60, int(mx * 1.5))


def duur_tekst(sec):
    m = int(sec // 60)
    if m < 60:
        return f"{m} min"
    return f"{m // 60} u {m % 60:02d}"


def accu_tekst(g):
    """'RNode 80%, tel. 45% (laadt)' - alleen wat bekend is."""
    delen = []
    if g.get("rbat") is not None:
        delen.append(f"RNode {g['rbat']}%")
    if g.get("tbat") is not None:
        delen.append(f"tel. {g['tbat']}%" + (" (laadt)" if g.get("tladen") else ""))
    return ", ".join(delen)


def is_laag(g):
    return ((g.get("rbat") is not None and g["rbat"] <= BATTERIJ_LAAG)
            or (g.get("tbat") is not None and g["tbat"] <= BATTERIJ_LAAG and not g.get("tladen")))


class Gehoord:
    def __init__(self):
        self.lock = threading.Lock()
        self.data = {}
        self.start = time.time()
        self._laatst_bewaard = 0
        try:
            with open(GEHOORD_FILE, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except (OSError, ValueError):
            self.data = {}

    def _save(self, nu=False):
        if not nu and time.time() - self._laatst_bewaard < 60:
            return
        try:
            tmp = GEHOORD_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f)
            os.replace(tmp, GEHOORD_FILE)
            self._laatst_bewaard = time.time()
        except OSError as e:
            log(f"[-] Kon {GEHOORD_FILE} niet bewaren: {e}")

    def gehoord(self, adr_hex, lat=None, lon=None, rbat=None, rssi=None, tbat=None, laden=None):
        terug = None
        with self.lock:
            g = self.data.setdefault(adr_hex, {})
            if g.get("uit_beeld"):
                terug = time.time() - g.get("t", time.time())
                g["uit_beeld"] = False
            g["t"] = time.time()
            if lat is not None and lon is not None:
                g["lat"], g["lon"] = lat, lon
            if rbat is not None:
                g["rbat"] = rbat
                if g.get("laag") and rbat > BATTERIJ_LAAG + 10:
                    g["laag"] = False
            if rssi is not None:
                g["rssi"] = rssi
            if tbat is not None:                      # accu van de telefoon (telemetrie van de app)
                g["tbat"] = tbat
                g["tladen"] = 1 if laden else 0
                if g.get("tlaag") and (laden or tbat > BATTERIJ_LAAG + 10):
                    g["tlaag"] = False
            self._save()
        if terug is not None:
            naam = whitelist_entries().get(adr_hex) or adr_hex[:8]
            log(f"[+] {naam} weer gehoord (na {duur_tekst(terug)})")
            naar_beheerders(f"{STEUNPUNT_NAAM}: {naam} weer gehoord (na {duur_tekst(terug)} stilte).")

    def controleer(self):
        """Waarschuwt de beheerders bij 'uit beeld' en lage accu. Eén keer per voorval."""
        wl = whitelist_entries()
        grens = uit_beeld_na()
        nu = time.time()
        meldingen = []
        with self.lock:
            for adr, naam in wl.items():
                g = self.data.get(adr)
                if not g or "t" not in g:
                    continue
                naam = naam or adr[:8]
                # na een herstart van de brug telt de wachttijd vanaf de start
                stil = nu - max(g["t"], self.start)
                if stil > grens and not g.get("uit_beeld"):
                    g["uit_beeld"] = True
                    waar = f", laatst bij {g['lat']:.5f}, {g['lon']:.5f}" if "lat" in g else ""
                    bat = accu_tekst(g)
                    bat = f", {bat}" if bat else ""
                    meldingen.append(f"{STEUNPUNT_NAAM}: {naam} niet meer gehoord sinds "
                                     f"{time.strftime('%H:%M', time.localtime(g['t']))}{waar}{bat}.")
                if g.get("rbat") is not None and g["rbat"] <= BATTERIJ_LAAG and not g.get("laag"):
                    g["laag"] = True
                    meldingen.append(f"{STEUNPUNT_NAAM}: accu RNode van {naam} is {g['rbat']}%.")
                if (g.get("tbat") is not None and g["tbat"] <= BATTERIJ_LAAG and not g.get("tladen")
                        and not g.get("tlaag")):
                    g["tlaag"] = True
                    meldingen.append(f"{STEUNPUNT_NAAM}: accu telefoon van {naam} is {g['tbat']}%.")
            if meldingen:
                self._save(nu=True)
        for m in meldingen:
            log("[!] " + m)
            naar_beheerders(m)

    def overzicht(self):
        """Tekst voor LIJST: wie aandacht nodig heeft bovenaan."""
        wl = whitelist_entries()
        grens = uit_beeld_na()
        nu = time.time()
        rijen = []
        with self.lock:
            for adr, naam in wl.items():
                naam = naam or adr[:8]
                g = self.data.get(adr, {})
                if "t" not in g:
                    rijen.append((2, 10 ** 9, f"{naam}: nog niet gehoord"))
                    continue
                stil = nu - g["t"]
                tekst = f"{naam}: {duur_tekst(stil)}"
                if accu_tekst(g):
                    tekst += ", " + accu_tekst(g)
                prio = 3
                if is_laag(g):
                    tekst += " LAAG"
                    prio = 1
                if stil > grens:
                    tekst += f" UIT BEELD (laatst {time.strftime('%H:%M', time.localtime(g['t']))})"
                    prio = 0
                rijen.append((prio, stil, tekst))
        rijen.sort(key=lambda r: (r[0], -r[1] if r[0] < 2 else r[1]))
        return [r[2] for r in rijen]

    def aantal_gehoord(self):
        grens = uit_beeld_na()
        nu = time.time()
        wl = whitelist_entries()
        with self.lock:
            return sum(1 for adr in wl if nu - self.data.get(adr, {}).get("t", 0) <= grens)

    def aantal_laag(self):
        wl = whitelist_entries()
        with self.lock:
            return sum(1 for adr in wl if is_laag(self.data.get(adr, {})))


gehoord = Gehoord()


class Aanmeldingen:
    def __init__(self):
        self.lock = threading.Lock()
        self.data = {"volgende_nr": 1, "open": {}, "code": None}
        try:
            with open(AANMELD_FILE, "r", encoding="utf-8") as f:
                self.data.update(json.load(f))
        except (OSError, ValueError):
            pass
        self.fout_gemeld = {}

    def _save(self):
        tmp = AANMELD_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, AANMELD_FILE)

    def code(self):
        return (self.data.get("code") or AANMELDCODE).strip()

    def set_code(self, nieuw):
        with self.lock:
            self.data["code"] = nieuw.strip()
            self._save()

    def nieuw(self, adr, naam, telefoonnaam):
        with self.lock:
            for nr, a in self.data["open"].items():
                if a["adr"] == adr:
                    return int(nr), False
            nr = self.data["volgende_nr"]
            self.data["volgende_nr"] += 1
            self.data["open"][str(nr)] = {"adr": adr, "naam": naam, "telefoon": telefoonnaam,
                                          "tijd": time.strftime("%Y-%m-%d %H:%M")}
            self._save()
            return nr, True

    def pak(self, nr):
        with self.lock:
            a = self.data["open"].pop(str(nr), None)
            if a:
                self._save()
            return a

    def lijst(self):
        with self.lock:
            return dict(self.data["open"])


aanmeldingen = Aanmeldingen()


# ---------------------------------------------------------------------------
# Bericht aan alle vrijwilligers (ALLEN)
# ---------------------------------------------------------------------------

ALLEN_MAX = 300          # tekens; een kort bericht past in één LoRa-pakket
ALLEN_SPREIDING = 3      # seconden tussen de berichten, zodat de LoRa-band niet volloopt


class Rondzending:
    """De laatste rondzending: tekst, wie hem kreeg en wie (nog) niet. Wordt bewaard voor de beheerpagina."""

    def __init__(self):
        self.lock = threading.Lock()
        try:
            with open(RONDZENDING_FILE, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except (OSError, ValueError):
            self.data = {}

    def _bewaar(self):
        try:
            tmp = RONDZENDING_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False)
            os.replace(tmp, RONDZENDING_FILE)
        except OSError as e:
            log(f"[-] Kon {RONDZENDING_FILE} niet bewaren: {e}")

    def start(self, tekst, door, ontvangers):
        """ontvangers: {adres: naam}. Geeft het aantal ontvangers."""
        with self.lock:
            self.data = {"tekst": tekst, "door": door, "t": int(time.time()),
                         "ontv": {a: {"naam": n or a[:8], "st": "wacht"} for a, n in ontvangers.items()}}
            self._bewaar()
        return len(ontvangers)

    def zet(self, adr, status):
        with self.lock:
            o = self.data.get("ontv", {}).get(adr)
            if o is None or o["st"] == "ok":          # 'afgeleverd' blijft afgeleverd
                return
            o["st"] = status
            self._bewaar()

    def samenvatting(self):
        """Eén regel voor LIJST, of '' als er (vandaag) niets is rondgestuurd."""
        with self.lock:
            d = self.data
            if not d.get("ontv") or time.time() - d.get("t", 0) > 24 * 3600:
                return ""
            ontv = d["ontv"].values()
            ok = sum(1 for o in ontv if o["st"] == "ok")
            niet = [o["naam"] for o in ontv if o["st"] != "ok"]
            t = f"Bericht aan allen ({time.strftime('%H:%M', time.localtime(d['t']))}): ontvangen door {ok} van {len(d['ontv'])}"
            return t + (". Nog niet: " + ", ".join(sorted(niet)) if niet else ".")


rondzending = Rondzending()


class Berichten:
    """De laatste berichten aan één vrijwilliger (AAN), met of ze zijn aangekomen. Voor de beheerpagina."""
    MAX = 15

    def __init__(self):
        self.lock = threading.Lock()
        try:
            with open(BERICHTEN_FILE, "r", encoding="utf-8") as f:
                self.lijst = json.load(f)
        except (OSError, ValueError):
            self.lijst = []

    def _bewaar(self):
        try:
            tmp = BERICHTEN_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.lijst, f, ensure_ascii=False)
            os.replace(tmp, BERICHTEN_FILE)
        except OSError as e:
            log(f"[-] Kon {BERICHTEN_FILE} niet bewaren: {e}")

    def nieuw(self, adr, naam, tekst, door):
        with self.lock:
            bid = f"{int(time.time() * 1000)}"
            self.lijst.insert(0, {"id": bid, "t": int(time.time()), "adr": adr, "naam": naam, "tekst": tekst,
                                  "door": door, "st": "wacht"})
            del self.lijst[self.MAX:]
            self._bewaar()
            return bid

    def zet(self, bid, status):
        with self.lock:
            for b in self.lijst:
                if b["id"] == bid and b["st"] != "ok":
                    b["st"] = status
                    self._bewaar()


berichten = Berichten()


def zoek_ontvanger(arg):
    """'Liesbeth de Haan Ga naar de Brink' -> (adres, naam, tekst, fout).
    Eerst de langste volledige naam, dan een unieke voornaam (of begin van het adres, min. 6 tekens).
    Een dubbele punt na de naam mag ook: 'Liesbeth: Ga naar de Brink'."""
    wl = whitelist_entries()                                   # {adres: naam}
    arg = " ".join(arg.split())
    if ":" in arg:
        wie, tekst = (x.strip() for x in arg.split(":", 1))
        kandidaten = [(wie, tekst)]
    else:
        woorden = arg.split(" ")
        kandidaten = [(" ".join(woorden[:k]), " ".join(woorden[k:])) for k in range(len(woorden) - 1, 0, -1)]
        if not kandidaten:                                     # alleen een naam, geen tekst
            kandidaten = [(arg, "")]
    # 1. volledige naam (langste eerst)
    for wie, tekst in kandidaten:
        hits = [(a, n) for a, n in wl.items() if n and n.lower() == wie.lower()]
        if len(hits) == 1 and tekst:
            return hits[0][0], hits[0][1], tekst, ""
        if len(hits) > 1:
            return None, None, "", f"Meerdere vrijwilligers heten '{wie}'. Gebruik het begin van het adres (zie LIJST)."
    # 2. voornaam of begin van het adres
    wie, tekst = kandidaten[-1] if ":" not in arg else kandidaten[0]
    if not tekst:
        return None, None, "", "Geen tekst. Voorbeeld: AAN Liesbeth Ga naar de Brink"
    z = wie.lower()
    hits = [(a, n) for a, n in wl.items()
            if (n and (n.lower().split(" ")[0] == z or n.lower().startswith(z + " "))) or (len(z) >= 6 and a.startswith(z))]
    if len(hits) == 1:
        return hits[0][0], hits[0][1] or hits[0][0][:8], tekst, ""
    if len(hits) > 1:
        return None, None, "", ("Welke bedoel je: " + ", ".join(n or a[:8] for a, n in hits) +
                                "? Gebruik de volledige naam, bijv. AAN " + (hits[0][1] or hits[0][0][:8]) + ": tekst")
    return None, None, "", f"Niemand gevonden voor '{wie}'. Stuur LIJST voor de namen."


def stuur_aan_een(adr, naam, tekst, door, melder=None):
    """Bericht aan één vrijwilliger. melder: adres (bytes) van de beheerder die bericht krijgt of het aankwam."""
    tekst = " ".join(tekst.split())
    if not tekst:
        return False, "Geen tekst."
    if len(tekst) > ALLEN_MAX:
        return False, f"Te lang ({len(tekst)} tekens, max. {ALLEN_MAX}). Maak het bericht korter."
    bid = berichten.nieuw(adr, naam, tekst, door)

    def afgeleverd(_a):
        berichten.zet(bid, "ok")
        if melder:
            stuur_lxmf(melder, f"Afgeleverd bij {naam}.")

    def mislukt(_a):
        berichten.zet(bid, "mislukt")
        if melder:
            stuur_lxmf(melder, f"Niet aangekomen bij {naam} (RNode uit of buiten bereik?). Probeer het later opnieuw.")
    try:
        stuur_lxmf(bytes.fromhex(adr), f"Bericht van {STEUNPUNT_NAAM}: {tekst}", afgeleverd=afgeleverd, mislukt=mislukt)
    except ValueError:
        berichten.zet(bid, "mislukt")
        return False, f"Adres van {naam} klopt niet."
    log(f"[>] Bericht aan {naam} door {door}: {tekst}")
    return True, f"Bericht aan {naam} verstuurd. Je hoort of het aankomt."


def stuur_aan_allen(tekst, door, behalve=None):
    """Stuurt tekst naar alle aangemelde vrijwilligers. Geeft (ok, antwoord voor de beheerder)."""
    tekst = " ".join(tekst.split())
    if not tekst:
        return False, "Geen tekst. Voorbeeld: ALLEN Einde oefening, bedankt allemaal!"
    if len(tekst) > ALLEN_MAX:
        return False, f"Te lang ({len(tekst)} tekens, max. {ALLEN_MAX}). Maak het bericht korter."
    ontvangers = {a: n for a, n in whitelist_entries().items() if a != behalve}
    if not ontvangers:
        return False, "Er zijn geen aangemelde vrijwilligers."
    n = rondzending.start(tekst, door, ontvangers)
    bericht = f"{STEUNPUNT_NAAM} aan alle vrijwilligers: {tekst}"
    for i, adr in enumerate(sorted(ontvangers)):
        try:
            stuur_lxmf(bytes.fromhex(adr), bericht, afgeleverd=lambda a: rondzending.zet(a, "ok"),
                       mislukt=lambda a: rondzending.zet(a, "mislukt"), wacht=i * ALLEN_SPREIDING)
        except ValueError:
            rondzending.zet(adr, "mislukt")
    log(f"[>] Bericht aan alle vrijwilligers ({n}) door {door}: {tekst}")
    duur = f" Dat duurt ongeveer {max(1, n * ALLEN_SPREIDING // 60)} min." if n * ALLEN_SPREIDING >= 60 else ""
    return True, f"Verstuurd naar {n} vrijwilliger{'s' if n != 1 else ''}.{duur} Stuur LIJST om te zien wie het heeft ontvangen."
BEHEER_HELP = ("Opdrachten: JA <nr> | NEE <nr> | WACHT (open aanmeldingen) | "
               "LIJST (aangemeld, laatst gehoord, accu) | AF <naam> | CODE (toon) | CODE <nieuw> | "
               "ALLEN <tekst> (bericht aan alle vrijwilligers) | AAN <naam> <tekst> (aan één vrijwilliger)")


def is_beheerder(hash_bytes):
    return hash_bytes.hex() in {_norm_hash(b) for b in BEHEERDERS}


def naar_beheerders(tekst):
    if not BEHEERDERS:
        log("[!] Geen BEHEERDERS ingesteld: aanmelding kan niet worden goedgekeurd!")
    for b in BEHEERDERS:
        stuur_lxmf(bytes.fromhex(_norm_hash(b)), tekst)


def handle_aanmelden(src, telefoonnaam, tekst):
    parts = tekst.strip().split(None, 2)
    code = parts[1] if len(parts) > 1 else ""
    naam = (parts[2].strip() if len(parts) > 2 else "") or telefoonnaam or "onbekend"
    h = src.hex()
    if code.upper() != aanmeldingen.code().upper():
        log(f"[x] Aanmelding met onjuiste code van {telefoonnaam or h}")
        if time.time() - aanmeldingen.fout_gemeld.get(h, 0) > 600:
            aanmeldingen.fout_gemeld[h] = time.time()
            stuur_lxmf(src, f"{STEUNPUNT_NAAM}: onjuiste aanmeldcode. Controleer de kaart.")
        return
    if h in whitelist_entries():
        stuur_lxmf(src, f"U bent al aangemeld bij {STEUNPUNT_NAAM}.")
        return
    nr, nieuw = aanmeldingen.nieuw(h, naam, telefoonnaam)
    log(f"[?] AANMELDING #{nr}: {naam} ({telefoonnaam or '-'}) <{h}> wacht op goedkeuring")
    if nieuw:
        naar_beheerders(f"Aanmelding #{nr}: {naam} (telefoon {telefoonnaam or '-'}, adres {h[:8]}). "
                        f"Antwoord JA {nr} of NEE {nr}")
    stuur_lxmf(src, f"Aanmelding ontvangen door {STEUNPUNT_NAAM}. "
                    f"De beheerder van het steunpunt keurt deze zo goed (nr {nr}).")


def maak_beheerder(adr_hex, naam):
    """Voegt een beheerder toe (in het geheugen en in steunpunt_instellingen.json)."""
    global BEHEERDERS
    if adr_hex not in BEHEERDERS:
        BEHEERDERS = BEHEERDERS + [adr_hex]
    try:
        try:
            with open(INSTELLINGEN_FILE, "r", encoding="utf-8") as f:
                inst = json.load(f)
        except FileNotFoundError:
            inst = {}
        lijst = [b for b in inst.get("beheerders", []) if (b.get("adres") if isinstance(b, dict) else b) != adr_hex]
        lijst.append({"adres": adr_hex, "naam": naam})
        inst["beheerders"] = lijst
        tmp = INSTELLINGEN_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(inst, f, ensure_ascii=False, indent=2)
        os.replace(tmp, INSTELLINGEN_FILE)
    except (OSError, ValueError) as e:
        log(f"[-] Kon beheerder niet bewaren in {INSTELLINGEN_FILE}: {e}")


def beslis_aanmelding(nr, ja, door, als_beheerder=False):
    """Goed- of afkeuren van aanmelding nr. Geeft (gelukt, tekst)."""
    a = aanmeldingen.pak(nr)
    if not a:
        return False, f"Aanmelding #{nr} bestaat niet (meer)."
    if ja:
        whitelist_add(a["adr"], a["naam"], door)
        extra = ""
        if als_beheerder:
            maak_beheerder(a["adr"], a["naam"])
            extra = " Je bent ook beheerder: je ontvangt nieuwe aanmeldingen en kunt JA/NEE, LIJST en CODE sturen."
        log(f"[+] Aanmelding #{nr} GOEDGEKEURD door {door}: {a['naam']} <{a['adr']}>"
            + (" als BEHEERDER" if als_beheerder else ""))
        stuur_lxmf(bytes.fromhex(a["adr"]), f"Aangemeld bij {STEUNPUNT_NAAM} als {a['naam']}. "
                                            f"Uw meldingen worden doorgegeven.{extra}")
        return True, f"#{nr} {a['naam']} aangemeld" + (" als beheerder." if als_beheerder else ".")
    log(f"[x] Aanmelding #{nr} AFGEWEZEN door {door}: {a['naam']} <{a['adr']}>")
    stuur_lxmf(bytes.fromhex(a["adr"]), f"Uw aanmelding bij {STEUNPUNT_NAAM} is niet goedgekeurd.")
    return True, f"#{nr} {a['naam']} afgewezen."


def meld_afgemeld(adr_hex):
    try:
        stuur_lxmf(bytes.fromhex(adr_hex), f"U bent afgemeld bij {STEUNPUNT_NAAM}. Uw berichten worden niet meer "
                                           f"doorgegeven. Opnieuw meedoen: meld aan met de kaart van het steunpunt.")
    except ValueError:
        pass


def verwerk_web_opdrachten():
    """Opdrachten van de beheerpagina (JA/NEE/BEHEERDER op een aanmelding)."""
    try:
        with open(OPDRACHTEN_FILE, "r", encoding="utf-8") as f:
            opdrachten = json.load(f)
        os.remove(OPDRACHTEN_FILE)
    except FileNotFoundError:
        return
    except (OSError, ValueError) as e:
        log(f"[-] Opdrachten van de beheerpagina onleesbaar: {e}")
        try: os.remove(OPDRACHTEN_FILE)
        except OSError: pass
        return
    for o in opdrachten if isinstance(opdrachten, list) else []:
        try:
            if o.get("soort") == "OPERATOR":
                vorige = f" (neemt over van {o.get('vorige')})" if o.get("vorige") else ""
                log(f"[i] Dienstdoende operator: {o.get('tekst', '?')}{vorige}")
                continue
            if o.get("soort") == "NIET_WACHTEN":
                log(f"[i] Beheerpagina: " + outbox.niet_meer_wachten(str(o.get("id", "")), str(o.get("call", ""))))
                continue
            if o.get("soort") == "AAN":
                adr = str(o.get("adres", "")).lower()
                naam = whitelist_entries().get(adr)
                if naam is None:
                    log(f"[i] Beheerpagina: bericht aan onbekend adres <{adr}> niet verstuurd")
                else:
                    ok, antwoord = stuur_aan_een(adr, naam or adr[:8], str(o.get("tekst", "")), "beheerpagina")
                    log(f"[i] Beheerpagina: {antwoord}")
                continue
            if o.get("soort") == "ALLEN":
                ok, antwoord = stuur_aan_allen(str(o.get("tekst", "")), "beheerpagina")
                log(f"[i] Beheerpagina: {antwoord}")
                continue
            if o.get("soort") == "AFGEMELD":
                _load_whitelist()
                meld_afgemeld(o.get("adr", ""))
                log(f"[x] Afgemeld via beheerpagina: <{o.get('adr', '')[:8]}>; telefoon wordt ingelicht")
                continue
            soort, nr = o.get("soort"), int(o.get("nr"))
            ok, tekst = beslis_aanmelding(nr, soort in ("JA", "BEHEERDER"), "beheerpagina", soort == "BEHEERDER")
            log(f"[i] Beheerpagina: {tekst}")
            if ok and soort != "BEHEERDER":
                naar_beheerders(f"{STEUNPUNT_NAAM}: {tekst} (via beheerpagina)")
        except Exception as e:
            log(f"[-] Opdracht van de beheerpagina mislukt: {o} ({e})")


def handle_beheer(src, tekst):
    """Geeft True als het een beheeropdracht was."""
    woorden = tekst.strip().split(None, 1)
    if not woorden:
        return False
    opdracht = woorden[0].upper()
    arg = woorden[1].strip() if len(woorden) > 1 else ""
    door = sender_name_for(src) or src.hex()[:8]

    if opdracht in ("JA", "NEE") and arg.lstrip("#").isdigit():
        nr = int(arg.lstrip("#"))
        ok, uitkomst = beslis_aanmelding(nr, opdracht == "JA", door)
        stuur_lxmf(src, uitkomst if ok else uitkomst + " Stuur WACHT voor de open lijst.")
        return True
    if opdracht == "WACHT":
        open_ = aanmeldingen.lijst()
        tekst = "; ".join(f"#{nr} {a['naam']}" for nr, a in sorted(open_.items(), key=lambda x: int(x[0])))
        stuur_lxmf(src, f"Open aanmeldingen: {tekst}" if tekst else "Geen open aanmeldingen.")
        return True
    if opdracht == "LIJST":
        rijen = gehoord.overzicht()
        if not rijen:
            stuur_lxmf(src, "Nog niemand aangemeld.")
        else:
            kop = f"{STEUNPUNT_NAAM}: {len(rijen)} aangemeld, {gehoord.aantal_gehoord()} gehoord " \
                  f"(uit beeld na {uit_beeld_na() // 60} min)"
            meer = f"\n... en nog {len(rijen) - 40}" if len(rijen) > 40 else ""
            rz = rondzending.samenvatting()
            stuur_lxmf(src, kop + "\n" + "\n".join(rijen[:40]) + meer + ("\n" + rz if rz else ""))
        return True
    if opdracht == "ALLEN":
        ok, antwoord = stuur_aan_allen(arg, door, behalve=src.hex())
        stuur_lxmf(src, antwoord)
        return True
    if opdracht == "AAN":
        adr, naam, tekst, fout = zoek_ontvanger(arg)
        if fout:
            stuur_lxmf(src, fout)
            return True
        ok, antwoord = stuur_aan_een(adr, naam, tekst, door, melder=src)
        stuur_lxmf(src, antwoord)
        return True
    if opdracht == "AF" and arg:
        weg = whitelist_remove(arg)
        if weg:
            log(f"[x] Afgemeld door {door}: " + ", ".join(f"{n} <{h}>" for h, n in weg))
            for h, _ in weg:
                meld_afgemeld(h)
            stuur_lxmf(src, "Afgemeld: " + ", ".join(n or h[:8] for h, n in weg))
        else:
            stuur_lxmf(src, f"Niemand gevonden voor '{arg}'. Stuur LIJST voor de namen.")
        return True
    if opdracht == "CODE":
        if arg:
            aanmeldingen.set_code(arg)
            log(f"[i] Aanmeldcode gewijzigd door {door}")
            stuur_lxmf(src, f"Nieuwe aanmeldcode: {arg}")
        else:
            stuur_lxmf(src, f"Huidige aanmeldcode: {aanmeldingen.code()}")
        return True
    if opdracht in ("HELP", "?"):
        stuur_lxmf(src, BEHEER_HELP)
        return True
    return False


# ---------------------------------------------------------------------------
# Berichten van telefoons verwerken
# ---------------------------------------------------------------------------

def verwerk(message):
    src = message.source_hash
    name = sender_name_for(src)
    try:
        content = message.content_as_string() or ""
    except Exception:
        content = ""
    tekst = content.strip()
    verified = bool(message.signature_validated)

    # Elk ondertekend bericht van een aangemelde telefoon telt als 'gehoord'
    if verified and src.hex() in whitelist_entries():
        tel0 = message_telemetry(message)
        gehoord.gehoord(src.hex(), tel0.get("lat"), tel0.get("lon"), None, _num(message.rssi),
                        tel0.get("bat"), tel0.get("laden"))

    # Beheer en aanmelden: alleen met geldige handtekening, gaat niet over 2 m
    if verified and is_beheerder(src) and handle_beheer(src, tekst):
        return
    if tekst.upper().startswith("AANMELDEN"):
        if verified:
            handle_aanmelden(src, name, tekst)
        else:
            log(f"[x] Aanmelding van <{src.hex()}> genegeerd: handtekening niet te controleren")
        return

    if not sender_allowed(src, name, "bericht"):
        meld_geweigerd(src, tekst, verified)
        return

    tel = message_telemetry(message)
    stats = parse_link_stats(content)
    gehoord.gehoord(src.hex(), tel.get("lat"), tel.get("lon"), stats.get("rbat"), _num(message.rssi),
                    tel.get("bat"), tel.get("laden"))

    base = [("van", name or "onbekend"), ("adr", src.hex()), ("ontv", int(time.time()))]
    if not verified:
        base.append(("onbevestigd", 1))
    sp = [("s_rssi", _num(message.rssi)), ("s_snr", _num(message.snr)), ("s_q", _num(message.q))]
    mhash = message.hash or os.urandom(8)

    # M/ETHANE: naar de disciplines uit GEMELD AAN, met locatie als die meegestuurd is
    if tekst.upper().startswith("M/ETHANE MELDING"):
        aan, wacht = route(gemeld_aan(content))
        if "lat" not in tel:
            # Locatie als leesbare regel van de app: "LOCATIE: 52.25512, 6.16057 (±6 m)"
            loc = lees_locatie_regel(content)
            if loc:
                tel = dict(tel, lat=loc[0], lon=loc[1], nauwk=loc[2])
        pos = [("lat", tel.get("lat")), ("lon", tel.get("lon")), ("nauwk", tel.get("nauwk"))]
        queue("MTH", make_id(mhash, "MTH"), base + [("aan", ",".join(aan))] + pos + sp, content, wacht)
        log(f"[<] M/ETHANE van {name or src.hex()} aan {', '.join(aan)}"
            + (f" (locatie {tel['lat']}, {tel['lon']})" if "lat" in tel else ""))
        return

    # Telemetrie (positie, batterij) + signaalwaarden van het baken
    fields = dict(tel)
    fields.update(stats)
    if fields:
        order = ["lat", "lon", "alt", "snelh", "richt", "nauwk", "tijd",
                 "bat", "laden", "rbat", "m_rssi", "m_snr", "m_q"]
        queue("GPS", make_id(mhash, "GPS"), base + [(k, fields.get(k)) for k in order] + sp)
        log(f"[<] Telemetrie van {name or src.hex()}: lat={fields.get('lat')} lon={fields.get('lon')} "
            f"rssi(mobiel)={fields.get('m_rssi')} rssi(hier)={_num(message.rssi)}")

    # Chatbericht: naar @genoemden, anders naar 'berichten_aan'
    if tekst and tekst != "." and not stats:
        labels = chat_adressen(tekst) or netwerk().get("berichten_aan", [])
        aan, wacht = route(labels)
        pos = [("lat", tel.get("lat")), ("lon", tel.get("lon"))]
        queue("MSG", make_id(mhash, "MSG"), base + [("aan", ",".join(aan))] + pos + sp, content, wacht)
        log(f"[<] Bericht van {name or src.hex()} aan {', '.join(aan)}: {tekst[:60]}")


_onbevestigd = {}
_geweigerd_gemeld = {}


def meld_geweigerd(src, tekst, verified):
    """Een niet (meer) aangemelde telefoon krijgt het als antwoord: anders denkt hij dat
    zijn bericht is doorgegeven (de app toont 'afgeleverd' zodra het steunpunt het ontvangt).
    M/ETHANE: altijd. Andere berichten: hoogstens eens per 10 minuten. Bakens: niets."""
    if not verified or not tekst or tekst == "." or parse_link_stats(tekst):
        return
    h = src.hex()
    mth = tekst.upper().startswith("M/ETHANE")
    if not mth and time.time() - _geweigerd_gemeld.get(h, 0) < 600:
        return
    if not mth:
        _geweigerd_gemeld[h] = time.time()
    stuur_lxmf(src, f"{STEUNPUNT_NAAM}: uw {'M/ETHANE-melding' if mth else 'bericht'} is NIET doorgegeven. "
                    f"Deze telefoon is niet (meer) aangemeld. Meld opnieuw aan met de kaart van het steunpunt.")
    log(f"[x] {'M/ETHANE' if mth else 'Bericht'} van niet-aangemelde <{h[:8]}> geweigerd; telefoon is ingelicht")


def lxmf_delivery_callback(message):
    try:
        if message.signature_validated:
            verwerk(message)
            return
        if message.unverified_reason == LXMF.LXMessage.SIGNATURE_INVALID:
            log(f"[x] Bericht met ONGELDIGE handtekening van <{message.source_hash.hex()}> genegeerd")
            return
        # Afzender nog onbekend: announce opvragen en daarna opnieuw controleren
        threading.Thread(target=_wacht_op_afzender, args=(message,), daemon=True).start()
    except Exception as e:
        log(f"[-] Fout in LXMF-verwerking: {e}")


def _wacht_op_afzender(message):
    src = message.source_hash
    log(f"[i] Afzender <{src.hex()}> nog onbekend; announce opgevraagd om de handtekening te controleren")
    for i in range(60):
        if i % 20 == 0:
            RNS.Transport.request_path(src)
        time.sleep(1)
        if RNS.Identity.recall(src) and message.packed:
            try:
                m2 = LXMF.LXMessage.unpack_from_bytes(message.packed)
                m2.rssi, m2.snr, m2.q = message.rssi, message.snr, message.q
                if m2.signature_validated:
                    verwerk(m2)
                else:
                    log(f"[x] Bericht van <{src.hex()}> heeft een ongeldige handtekening; genegeerd")
                return
            except Exception as e:
                log(f"[-] Opnieuw controleren mislukt: {e}")
                break
    if WHITELIST_MODE.strip().lower() == "aan":
        log(f"[x] Bericht van <{src.hex()}> genegeerd: afzender niet te controleren")
    else:
        log(f"[!] Afzender <{src.hex()}> niet te controleren; doorgegeven als 'onbevestigd'")
        verwerk(message)


lxmf_router.register_delivery_callback(lxmf_delivery_callback)


class AnnounceHandler:
    aspect_filter = "lxmf.delivery"

    def __init__(self):
        self.last = {}

    def received_announce(self, destination_hash, announced_identity, app_data):
        try:
            name = name_from_app_data(app_data)
            if name:
                remember_sender_name(destination_hash, name)
            else:
                name = sender_name_for(destination_hash)
            if destination_hash.hex() in whitelist_entries():
                gehoord.gehoord(destination_hash.hex())
            if destination_hash == my_destination.hash or ANN_DOORGEVEN_INTERVAL <= 0:
                return
            if WHITELIST_MODE.strip().lower() == "aan" and not (
                    destination_hash.hex() in whitelist_entries() or is_beheerder(destination_hash)):
                return
            now = time.time()
            key = destination_hash.hex()
            if now - self.last.get(key, 0) < ANN_DOORGEVEN_INTERVAL:
                return
            self.last[key] = now
            queue("ANN", make_id(destination_hash, int(now)),
                  [("van", name or "onbekend"), ("adr", key), ("ontv", int(now))])
        except Exception as e:
            log(f"[-] Fout in announce-verwerking: {e}")


RNS.Transport.register_announce_handler(AnnounceHandler())

netwerk()
_load_whitelist()
dest_hex = RNS.prettyhexrep(my_destination.hash)
log(f"[!] STEUNPUNT ACTIEF: '{STEUNPUNT_NAAM}' {dest_hex}, roepnaam {CALLSIGN}")
if _INSTELLINGEN_FOUT:
    log(f"[!] {INSTELLINGEN_FILE} kon niet gelezen worden ({_INSTELLINGEN_FOUT}); standaardwaarden gebruikt")
elif os.path.exists(INSTELLINGEN_FILE):
    log(f"    Instellingen uit {os.path.basename(INSTELLINGEN_FILE)}")
log(f"    Aanmeldcode: {aanmeldingen.code()} | beheerders: {len(BEHEERDERS)} | witte lijst: {WHITELIST_MODE}")
for _b in _BEHEERDERS_FOUT:
    log(f"[!] Ongeldig adres in BEHEERDERS genegeerd: {_b!r} (moet 32 tekens 0-9/a-f zijn)")
if not BEHEERDERS:
    log("[!] Er zijn nog geen BEHEERDERS ingesteld; aanmeldingen kunnen niet worden goedgekeurd.")

last_announce = 0
last_controle = time.time()
last_status = time.time() - STATUS_INTERVAL + 60 if STATUS_INTERVAL > 0 else 0
start = time.time()
try:
    while True:
        now = time.time()
        if now - last_announce >= ANNOUNCE_INTERVAL:
            lxmf_router.announce(my_destination.hash)
            last_announce = now
            log(f"[+] '{STEUNPUNT_NAAM}' announce verstuurd via LoRa")
        verwerk_web_opdrachten()
        if now - last_controle >= 60:
            last_controle = now
            try:
                gehoord.controleer()
            except Exception as e:
                log(f"[-] Fout bij controle vrijwilligers: {e}")
        if STATUS_INTERVAL > 0 and now - last_status >= STATUS_INTERVAL:
            last_status = now
            queue("STA", make_id(CALLSIGN, int(now)),
                  [("stp", CALLSIGN), ("naam", STEUNPUNT_NAAM), ("lat", LATITUDE), ("lon", LONGITUDE),
                   ("wachtrij", outbox.counts()), ("aangemeld", len(whitelist_entries())),
                   ("gehoord", gehoord.aantal_gehoord()), ("laag", gehoord.aantal_laag()),
                   ("uptime", int(now - start)), ("ontv", int(now))])
        time.sleep(1)
except KeyboardInterrupt:
    link.close()
    sys.exit(0)

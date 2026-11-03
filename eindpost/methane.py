"""
methane.py - M/ETHANE-meldingen uit Sideband herkennen en omzetten naar
een JSON-record voor MQTT (bijvoorbeeld voor een Node-RED dashboard).

Berichtformaat (een LXMF-bericht per hulpdienst):

    M/ETHANE MELDING 2026-10-02 19:23
    MELDCODE: 021923-4F
    GEMELD AAN: Brandweer, Ambulance
    M: ...
    E: ...   <- eerste E  = Exacte locatie   (code "e")
    T: ...
    H: ...
    A: ...
    N: ...
    E: ...   <- tweede E  = Hulpdiensten     (code "s")
"""

import json
import os
import re
import threading
import time
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python < 3.9
    ZoneInfo = None

HEADER = "M/ETHANE MELDING"
ONBEKEND = "onbekend"

# Volgorde zoals in het bericht. De twee E's worden op positie onderscheiden.
#   (letter in bericht, code in de app, sleutel in JSON, label voor op het scherm)
FIELD_ORDER = [
    ("M", "m", "groot_incident_tekst", "M - Groot incident?"),
    ("E", "e", "locatie",              "E - Exacte locatie"),
    ("T", "t", "soort_incident",       "T - Soort incident"),
    ("H", "h", "gevaren",              "H - Gevaren"),
    ("A", "a", "bereikbaarheid",       "A - Bereikbaarheid"),
    ("N", "n", "slachtoffers",         "N - Aantal slachtoffers"),
    ("E", "s", "hulpdiensten",         "E - Hulpdiensten"),
]

_HEADER_RE = re.compile(
    r"^\s*M/ETHANE\s+MELDING\s+(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})\s*$", re.I
)
_LINE_RE = re.compile(r"^\s*([A-Za-z][A-Za-z ]{0,20}?)\s*:\s?(.*)$")
_MELDCODE_RE = re.compile(r"^\d{6}-[0-9A-Fa-f]{2}$")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def is_methane(text):
    return bool(text) and text.lstrip().upper().startswith(HEADER)


def parse_methane(text):
    """Geeft een dict terug, of None als dit geen M/ETHANE-melding is."""
    if not is_methane(text):
        return None

    lines = text.replace("\r\n", "\n").replace("\r", "\n").strip().split("\n")
    result = {
        "meldcode": None,
        "meldcode_geldig": False,
        "gemeld_aan": None,
        "melding_tijd": None,   # naive datetime (lokale tijd van de melder)
        "velden": {},           # code -> tekst
    }

    hm = _HEADER_RE.match(lines[0])
    if hm:
        try:
            result["melding_tijd"] = datetime.strptime(
                f"{hm.group(1)} {hm.group(2)}", "%Y-%m-%d %H:%M"
            )
        except ValueError:
            pass

    next_idx = 0      # volgende verwachte positie in FIELD_ORDER
    current = None    # code van het veld waar vervolgregels bij horen

    for line in lines[1:]:
        lm = _LINE_RE.match(line)
        key = lm.group(1).strip().upper() if lm else None
        value = lm.group(2).strip() if lm else None

        if key == "MELDCODE":
            result["meldcode"] = value
            result["meldcode_geldig"] = bool(_MELDCODE_RE.match(value or ""))
            current = None
            continue
        if key == "GEMELD AAN":
            result["gemeld_aan"] = value
            current = None
            continue
        if key and next_idx < len(FIELD_ORDER) and key == FIELD_ORDER[next_idx][0]:
            code = FIELD_ORDER[next_idx][1]
            result["velden"][code] = value
            current = code
            next_idx += 1
            continue

        # Vrije tekst over meerdere regels: bij het vorige veld voegen
        if current and line.strip():
            prev = result["velden"].get(current) or ""
            result["velden"][current] = (prev + "\n" + line.strip()).strip()

    # Lege of ontbrekende velden -> "onbekend" (zelfde regel als de app)
    for _, code, _, _ in FIELD_ORDER:
        if not (result["velden"].get(code) or "").strip():
            result["velden"][code] = ONBEKEND
    if not (result["gemeld_aan"] or "").strip():
        result["gemeld_aan"] = ONBEKEND

    return result


def _groot_incident_status(m_text):
    t = (m_text or "").strip().lower()
    if t.startswith(("ja", "yes")):
        return "ja"
    if t.startswith(("nee", "no")):
        return "nee"
    return ONBEKEND


def _aantal_slachtoffers(n_text):
    if not n_text or n_text.strip().lower() == ONBEKEND:
        return None
    m = re.search(r"\d+", n_text)
    return int(m.group()) if m else None


# ---------------------------------------------------------------------------
# Meldcode-cache: herkent een herhaalde verzending (zelfde afzender +
# meldcode) zodat Node-RED die als update kan tonen in plaats van als
# nieuwe melding. Overleeft een herstart van de gateway.
# ---------------------------------------------------------------------------

class MeldcodeCache:
    def __init__(self, path, window_s=24 * 3600):
        self.path = path
        self.window_s = window_s
        self.lock = threading.Lock()
        self.data = {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except (FileNotFoundError, ValueError):
            self.data = {}

    def check(self, key):
        """Geeft (eerst_ontvangen_epoch, is_herhaling) terug."""
        now = time.time()
        with self.lock:
            # Oude regels opruimen: de meldcode bevat geen maand, dus
            # dezelfde code kan een maand later weer voorkomen.
            self.data = {k: v for k, v in self.data.items()
                         if isinstance(v, dict) and now - v.get("seen", 0) < self.window_s}
            if key in self.data:
                self.data[key]["seen"] = now
                self._save()
                return self.data[key].get("first", now), True
            self.data[key] = {"first": now, "seen": now}
            self._save()
            return now, False

    def _save(self):
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f)
            os.replace(tmp, self.path)
        except OSError as e:
            print(f"[-] METHANE: kon meldcode-cache niet opslaan: {e}")


# ---------------------------------------------------------------------------
# Record opbouwen voor MQTT
# ---------------------------------------------------------------------------

def build_record(parsed, afzender, ontvanger, rssi=None, snr=None,
                 tz_name="Europe/Amsterdam", cache=None):
    velden = parsed["velden"]
    nu = time.time()

    # Tijd van de melding: kopregel (lokale tijd melder), anders ontvangsttijd
    melding_epoch = nu
    tijd_bron = "ontvangst"
    if parsed["melding_tijd"] is not None:
        try:
            tz = ZoneInfo(tz_name) if ZoneInfo else timezone.utc
            melding_epoch = parsed["melding_tijd"].replace(tzinfo=tz).timestamp()
            tijd_bron = "melding"
        except Exception as e:
            print(f"[-] METHANE: kon tijd uit kopregel niet omzetten: {e}")

    meldcode = parsed["meldcode"] or f"ZONDER-CODE-{int(nu)}"

    herhaling = False
    eerst_ontvangen = nu
    if cache is not None:
        eerst_ontvangen, herhaling = cache.check(f"{afzender}|{meldcode}")

    groot = _groot_incident_status(velden["m"])

    record = {
        "type": "METHANE",
        "meldcode": meldcode,
        "meldcode_geldig": parsed["meldcode_geldig"],
        "herhaling": herhaling,

        # Tijden
        "timestamp": nu,                       # ontvangst (epoch s), zoals bij /gps en /message
        "eerst_ontvangen": eerst_ontvangen,    # epoch s van de eerste ontvangst van deze meldcode
        "melding_epoch": melding_epoch,        # epoch s uit de kopregel
        "melding_tijd": time.strftime("%Y-%m-%d %H:%M", time.localtime(melding_epoch)),
        "melding_iso": datetime.fromtimestamp(melding_epoch, timezone.utc).isoformat(),
        "tijd_bron": tijd_bron,

        # Afzender / radio
        "afzender": afzender,
        "ontvanger": ontvanger,
        "rssi": rssi,
        "snr": snr,

        # Samenvatting (handig voor kleuren/alarmen in Node-RED)
        "groot_incident": groot,               # "ja" / "nee" / "onbekend"
        "prioriteit": "hoog" if groot == "ja" else "normaal",
        "slachtoffers_aantal": _aantal_slachtoffers(velden["n"]),
        "onbekend_velden": sum(1 for v in velden.values() if v == ONBEKEND),
        "gemeld_aan": parsed["gemeld_aan"],
        "gemeld_aan_lijst": [d.strip() for d in parsed["gemeld_aan"].split(",")
                             if d.strip() and parsed["gemeld_aan"] != ONBEKEND],
    }

    # De zeven velden als losse sleutels: msg.payload.locatie, msg.payload.gevaren, ...
    for _, code, key, _ in FIELD_ORDER:
        record[key] = velden[code]

    # En als lijst in vaste volgorde, kant-en-klaar voor een tabel op het scherm
    record["regels"] = [
        {"letter": letter, "code": code, "label": label, "waarde": velden[code],
         "onbekend": velden[code] == ONBEKEND}
        for letter, code, _, label in FIELD_ORDER
    ]

    return record

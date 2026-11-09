#!/usr/bin/env python3
"""
noodnet_kaart.py - offline kaart voor de eindpost (meldingen op de kaart in Node-RED).

Downloadt eenmalig (met internet) de kaarttegels van de BRT-Achtergrondkaart van PDOK
(Kadaster, open data, CC BY 4.0) rond een plaats, zodat de kaart daarna zonder internet werkt.
Node-RED serveert de tegels op  http://<pi>:1880/noodnet-tegels/{z}/{x}/{y}.png
en de kaart zelf staat op       http://<pi>:1880/worldmap

    python3 noodnet_kaart.py --plaats Deventer --straal 10 --zoom 16
    python3 noodnet_kaart.py --midden 52.255,6.163 --straal 10
    python3 noodnet_kaart.py --status
"""

import argparse
import json
import math
import os
import shutil
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

MAP = os.path.dirname(os.path.abspath(__file__))
KAART_DIR = os.path.join(MAP, "kaart")
TEGELS = os.path.join(KAART_DIR, "tegels")
NIEUW = os.path.join(KAART_DIR, "tegels.nieuw")
INFO_FILE = os.path.join(KAART_DIR, "kaart.json")
VOORTGANG_FILE = os.path.join(KAART_DIR, "voortgang.json")

TEGEL_URL = "https://service.pdok.nl/brt/achtergrondkaart/wmts/v2_0/standaard/EPSG:3857/{z}/{x}/{y}.png"
ZOEK_URL = ("https://api.pdok.nl/bzk/locatieserver/search/v3_1/free?rows=1&fl=weergavenaam,centroide_ll,type"
            "&fq=type:(gemeente%20OR%20woonplaats)&q=")
AGENT = "Noodnet-eindpost/1.0 (+http://noodnet.ied.nl)"
BRON = "Kaart: Kadaster / PDOK, BRT-Achtergrondkaart (CC BY 4.0)"

# Grof overzicht van de regio rond het gebied (voor het uitzoomen): 3x de straal, min. 30 km
REGIO_FACTOR = 3
REGIO_MIN_KM = 30
REGIO_ZOOM = (8, 9)
MIN_ZOOM_GEBIED = 10
STRALEN = (5, 10, 15, 20, 25)          # km
ZOOMS = {15: "straten", 16: "straten en gebouwen (aanbevolen)", 17: "zeer gedetailleerd (veel tegels)"}
GEM_KB = 14                            # gemiddelde grootte van een tegel, om te schatten
PARALLEL = 4
MAX_TEGELS = 40000                     # netjes blijven tegenover PDOK (een gemeente is ruim genoeg)


# ---------------------------------------------------------------------------
# Rekenen met tegels (Web Mercator / slippy map)
# ---------------------------------------------------------------------------

def tegel_xy(lat, lon, z):
    lat = max(min(lat, 85.0511), -85.0511)
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
    return min(max(x, 0), n - 1), min(max(y, 0), n - 1)


def gebied(lat, lon, straal_km):
    """(zuid, west, noord, oost) van een vierkant rond (lat, lon)."""
    dlat = straal_km / 111.32
    dlon = straal_km / (111.32 * max(math.cos(math.radians(lat)), 0.01))
    return lat - dlat, lon - dlon, lat + dlat, lon + dlon


def tegels_in(bbox, zmin, zmax):
    z_, w, n_, o = bbox
    for z in range(zmin, zmax + 1):
        x1, y1 = tegel_xy(n_, w, z)
        x2, y2 = tegel_xy(z_, o, z)
        for x in range(x1, x2 + 1):
            for y in range(y1, y2 + 1):
                yield z, x, y


def alle_tegels(lat, lon, straal_km, max_zoom):
    gezien = set()
    regio = max(straal_km * REGIO_FACTOR, REGIO_MIN_KM)
    for t in tegels_in(gebied(lat, lon, regio), *REGIO_ZOOM):
        gezien.add(t)
    for t in tegels_in(gebied(lat, lon, straal_km), MIN_ZOOM_GEBIED, max_zoom):
        gezien.add(t)
    return sorted(gezien)


def schatting(lat, lon, straal_km, max_zoom):
    n = len(alle_tegels(lat, lon, straal_km, max_zoom))
    return n, round(n * GEM_KB / 1024)


# ---------------------------------------------------------------------------
# Plaats zoeken (PDOK Locatieserver)
# ---------------------------------------------------------------------------

def zoek_plaats(naam, timeout=15):
    """Geeft (weergavenaam, lat, lon) of gooit een ValueError met uitleg."""
    url = ZOEK_URL + urllib.parse.quote(naam.strip())
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    docs = (data.get("response") or {}).get("docs") or []
    if not docs:
        raise ValueError(f"Plaats '{naam}' niet gevonden. Probeer de naam van de gemeente of woonplaats.")
    d = docs[0]
    punt = d.get("centroide_ll", "")            # "POINT(6.16 52.25)"
    try:
        lon, lat = (float(v) for v in punt[punt.index("(") + 1:punt.index(")")].split())
    except (ValueError, IndexError):
        raise ValueError(f"Geen coördinaten gevonden voor '{naam}'.")
    return d.get("weergavenaam") or naam, lat, lon


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def _lees(pad, standaard=None):
    try:
        with open(pad, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return standaard


def _schrijf(pad, data):
    os.makedirs(os.path.dirname(pad), exist_ok=True)
    tmp = pad + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, pad)


def info():
    """Gegevens van de huidige offline kaart, of None."""
    return _lees(INFO_FILE)


def voortgang():
    """Voortgang van een download die bezig is (of net klaar/mislukt), of None."""
    v = _lees(VOORTGANG_FILE)
    if v and v.get("bezig") and time.time() - v.get("bijgewerkt", 0) > 120:
        v["bezig"] = False
        v["fout"] = v.get("fout") or "De download is onderbroken (Pi herstart?). Start hem opnieuw."
    return v


# ---------------------------------------------------------------------------
# Downloaden
# ---------------------------------------------------------------------------

def _haal(t, doel, oud):
    z, x, y = t
    pad = os.path.join(doel, str(z), str(x), f"{y}.png")
    # Tegel die we al hebben (van de vorige kaart) niet opnieuw downloaden
    bestaand = os.path.join(oud, str(z), str(x), f"{y}.png")
    if os.path.exists(bestaand) and os.path.getsize(bestaand) > 0:
        os.makedirs(os.path.dirname(pad), exist_ok=True)
        shutil.copyfile(bestaand, pad)
        return True
    url = TEGEL_URL.format(z=z, x=x, y=y)
    for poging in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": AGENT})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            if not data:
                raise OSError("lege tegel")
            os.makedirs(os.path.dirname(pad), exist_ok=True)
            with open(pad + ".tmp", "wb") as f:
                f.write(data)
            os.replace(pad + ".tmp", pad)
            return True
        except Exception:
            time.sleep(1 + 2 * poging)
    return False


def download(plaats, lat, lon, straal_km, max_zoom):
    tegels = alle_tegels(lat, lon, straal_km, max_zoom)
    totaal = len(tegels)
    staat = {"bezig": True, "plaats": plaats, "klaar": 0, "mislukt": 0, "totaal": totaal,
             "start": time.time(), "bijgewerkt": time.time(), "fout": ""}
    _schrijf(VOORTGANG_FILE, staat)
    shutil.rmtree(NIEUW, ignore_errors=True)
    os.makedirs(NIEUW, exist_ok=True)
    lock = threading.Lock()

    def een(t):
        ok = _haal(t, NIEUW, TEGELS)
        with lock:
            staat["klaar" if ok else "mislukt"] += 1
            if (staat["klaar"] + staat["mislukt"]) % 50 == 0:
                staat["bijgewerkt"] = time.time()
                _schrijf(VOORTGANG_FILE, staat)
        return ok

    with ThreadPoolExecutor(PARALLEL) as pool:
        list(pool.map(een, tegels))

    staat["bezig"] = False
    staat["bijgewerkt"] = time.time()
    # Veel mislukt (geen internet?): de oude kaart houden
    if staat["klaar"] < totaal * 0.9:
        staat["fout"] = (f"{staat['mislukt']} van {totaal} tegels konden niet gedownload worden. "
                         "Is er internet? De vorige kaart blijft staan.")
        _schrijf(VOORTGANG_FILE, staat)
        shutil.rmtree(NIEUW, ignore_errors=True)
        return False
    oud = os.path.join(KAART_DIR, "tegels.oud")
    shutil.rmtree(oud, ignore_errors=True)
    if os.path.isdir(TEGELS):
        os.replace(TEGELS, oud)
    os.replace(NIEUW, TEGELS)
    shutil.rmtree(oud, ignore_errors=True)
    _schrijf(INFO_FILE, {"plaats": plaats, "lat": round(lat, 6), "lon": round(lon, 6), "straal_km": straal_km,
                         "max_zoom": max_zoom, "zoom_start": 13, "aantal": staat["klaar"],
                         "mislukt": staat["mislukt"], "datum": time.strftime("%Y-%m-%d %H:%M"),
                         "bron": BRON, "gebied": gebied(lat, lon, straal_km)})
    _schrijf(VOORTGANG_FILE, staat)
    return True


def main():
    ap = argparse.ArgumentParser(description="Offline kaart (PDOK) voor de eindpost downloaden")
    ap.add_argument("--plaats", help="gemeente of woonplaats, bijv. Deventer")
    ap.add_argument("--midden", help="lat,lon in plaats van --plaats")
    ap.add_argument("--straal", type=int, default=10, help="km rond het midden (standaard 10)")
    ap.add_argument("--zoom", type=int, default=16, choices=sorted(ZOOMS), help="max. detail (standaard 16)")
    ap.add_argument("--schat", action="store_true", help="alleen het aantal tegels en de grootte tonen")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.status:
        print(json.dumps({"kaart": info(), "voortgang": voortgang()}, indent=1, ensure_ascii=False))
        return 0
    if not (1 <= a.straal <= 40):
        print("Straal moet tussen 1 en 40 km zijn."); return 1
    try:
        if a.midden:
            lat, lon = (float(v) for v in a.midden.split(","))
            plaats = a.plaats or f"{lat:.4f}, {lon:.4f}"
        elif a.plaats:
            plaats, lat, lon = zoek_plaats(a.plaats)
        else:
            print("Geef --plaats of --midden."); return 1
    except ValueError as ex:
        fout = str(ex)
    except OSError:
        fout = "Geen verbinding met PDOK. Is er internet? (netwerkkabel, of tijdelijk de thuis-wifi)"
    else:
        fout = ""
    if fout:
        _schrijf(VOORTGANG_FILE, {"bezig": False, "fout": fout, "bijgewerkt": time.time()})
        print(fout); return 1
    n, mb = schatting(lat, lon, a.straal, a.zoom)
    print(f"{plaats} ({lat:.4f}, {lon:.4f}), {a.straal} km, zoom t/m {a.zoom}: {n} tegels, ongeveer {mb} MB")
    if a.schat:
        return 0
    if n > MAX_TEGELS:
        fout = f"Te groot: {n} tegels (max. {MAX_TEGELS}). Kies een kleinere straal of minder detail."
        _schrijf(VOORTGANG_FILE, {"bezig": False, "fout": fout, "bijgewerkt": time.time()})
        print(fout); return 1
    ok = download(plaats, lat, lon, a.straal, a.zoom)
    v = voortgang() or {}
    print("Klaar." if ok else v.get("fout", "Mislukt."), f"({v.get('klaar', 0)} gelukt, {v.get('mislukt', 0)} mislukt)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

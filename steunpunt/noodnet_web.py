#!/usr/bin/env python3
"""
noodnet_web.py - beheerpagina van een Noodsteunpunt (Pi met FT-818).

Open in een browser op hetzelfde netwerk:   http://<naam-of-ip-van-de-pi>:8080

Wat je er kunt doen:
  - Status: draaien Direwolf, rnsd en de brug; wie is er gehoord; log
  - Steunpunt: naam, roepnaam, positie, aanmeldcode, beheerders, witte lijst
  - Netwerk: disciplines en eindposten, LoRa-instellingen, baken (per gemeente)
  - Vrijwilligers: wie is aangemeld, laatst gehoord, accu; afmelden
  - Kaart: aanmeldkaart maken en afdrukken

Instellingen komen in steunpunt_instellingen.json en noodnet_netwerk.json in
dezelfde map als steunpunt_brug.py. Na opslaan wordt de brug herstart.

Eenmalig een wachtwoord instellen:
    ~/rns-venv/bin/python noodnet_web.py --wachtwoord
Starten (normaal via de service noodnet-web):
    ~/rns-venv/bin/python noodnet_web.py [--poort 8080]

Alleen standaard-Python; RNS is optioneel (voor het tonen van het adres).
"""

import argparse
import base64
import getpass
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse, quote

import noodnet_radio as radio
import noodnet_beheer as beheer

MAP = os.path.dirname(os.path.abspath(__file__))
INST_FILE = os.path.join(MAP, "steunpunt_instellingen.json")
NET_FILE = os.path.join(MAP, "noodnet_netwerk.json")
WL_FILE = os.path.join(MAP, "witte_lijst.txt")
ONBEKEND_FILE = os.path.join(MAP, "onbekende_afzenders.txt")
BRUG_FILE = os.path.join(MAP, "steunpunt_brug.py")
KAART_SCRIPT = os.path.join(MAP, "maak_kaart.py")
KAART_HTML = os.path.join(MAP, "kaart_web.html")
WW_FILE = os.path.join(MAP, "web_wachtwoord.json")
LXMF_DIR = os.path.expanduser(os.environ.get("NOODNET_LXMF_DIR", "~/.reticulum/lxmf"))
GEHOORD_FILE = os.path.join(LXMF_DIR, "gehoord.json")
AANMELD_FILE = os.path.join(LXMF_DIR, "aanmeldingen.json")
WACHTRIJ_FILE = os.path.join(LXMF_DIR, "brug_wachtrij.json")
OPDRACHTEN_FILE = os.path.join(LXMF_DIR, "web_opdrachten.json")
ID_FILE = os.path.join(LXMF_DIR, "gateway.id")
RNS_CONFIG = os.path.expanduser(os.environ.get("NOODNET_RNS_CONFIG", "~/.reticulum/config"))

DIENSTEN = [("noodnet-rigctld", "CAT-besturing set (rigctld)"), ("direwolf", "Direwolf (2 m)"), ("rnsd", "Reticulum (LoRa)"), ("noodnet-brug", "Steunpunt-brug"),
            ("noodnet-download", "Downloadpagina (app)")]
SYSTEMCTL = os.environ.get("NOODNET_SYSTEMCTL", "systemctl")
SUDO = os.environ.get("NOODNET_SUDO", "sudo")
JOURNALCTL = os.environ.get("NOODNET_JOURNALCTL", "journalctl")

CSRF = secrets.token_urlsafe(24)
SCHRIJF_LOCK = threading.Lock()

STANDAARD_INST = {
    "steunpunt_naam": "", "roepnaam": "", "latitude": None, "longitude": None,
    "aanmeldcode": "", "witte_lijst_modus": "aan", "beheerders": [],
    "uit_beeld_min": None, "batterij_laag": 20,
}
ROEPNAAM_RE = re.compile(r"^[A-Z0-9]{3,6}(-([0-9]|1[0-5]))?$")
ADRES_RE = re.compile(r"^[0-9a-f]{32}$")
# ISM (ERC/REC 70-03): 433,05-434,79 MHz 10 mW e.r.p.; 869,40-869,65 MHz 500 mW e.r.p., 10% zendtijd
GRENZEN_LORA = {"433": (433050000, 434790000, 10), "868": (869400000, 869650000, 27)}


# ---------------------------------------------------------------------------
# Bestanden
# ---------------------------------------------------------------------------

def lees_json(pad, standaard=None):
    try:
        with open(pad, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return standaard


def schrijf_json(pad, data):
    tmp = pad + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, pad)


def brug_standaard(naam):
    """Leest NAAM = "waarde" uit steunpunt_brug.py (voor als er nog geen instellingen zijn)."""
    try:
        src = open(BRUG_FILE, encoding="utf-8").read()
    except OSError:
        return ""
    m = re.search(rf'^{naam}\s*=\s*"([^"]*)"', src, re.M)
    return m.group(1) if m else ""


def instellingen():
    inst = dict(STANDAARD_INST)
    opgeslagen = lees_json(INST_FILE)
    if isinstance(opgeslagen, dict):
        inst.update(opgeslagen)
    else:
        # eerste keer: overnemen wat nu in de brug staat
        inst["steunpunt_naam"] = brug_standaard("STEUNPUNT_NAAM")
        inst["roepnaam"] = brug_standaard("CALLSIGN")
        code = brug_standaard("AANMELDCODE")
        inst["aanmeldcode"] = "" if code == "WIJZIG-MIJ" else code
        inst["witte_lijst_modus"] = brug_standaard("WHITELIST_MODE") or "aan"
    a = lees_json(AANMELD_FILE, {}) or {}
    if a.get("code"):
        inst["aanmeldcode"] = a["code"]      # gewijzigd met CODE vanaf de telefoon
    return inst


def netwerk():
    return lees_json(NET_FILE, {}) or {}


def witte_lijst():
    """[(adres, naam, regel)]"""
    rijen = []
    try:
        with open(WL_FILE, encoding="utf-8") as f:
            for regel in f:
                kaal = regel.split("#", 1)[0].strip()
                if not kaal:
                    continue
                delen = kaal.split(None, 1)
                adr = delen[0].replace("<", "").replace(">", "").lower()
                if ADRES_RE.match(adr):
                    rijen.append((adr, delen[1].strip() if len(delen) > 1 else "", regel))
    except OSError:
        pass
    return rijen


def afmelden(adres):
    with SCHRIJF_LOCK:
        try:
            regels = open(WL_FILE, encoding="utf-8").readlines()
        except OSError:
            return False
        nieuw, weg = [], False
        for regel in regels:
            kaal = regel.split("#", 1)[0].strip()
            if kaal and kaal.split()[0].replace("<", "").replace(">", "").lower() == adres:
                nieuw.append("# afgemeld via beheerpagina " + time.strftime("%Y-%m-%d %H:%M") + ": " + regel.lstrip("# "))
                weg = True
            else:
                nieuw.append(regel)
        if weg:
            tmp = WL_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.writelines(nieuw)
            os.replace(tmp, WL_FILE)
        return weg


def toelaten(adres, naam, waarom="toegevoegd via beheerpagina"):
    """Zet een telefoon op de witte lijst (de brug leest het bestand vanzelf opnieuw in)."""
    with SCHRIJF_LOCK:
        if adres in {a for a, _, _ in witte_lijst()}:
            return False
        nieuw = not os.path.exists(WL_FILE)
        with open(WL_FILE, "a", encoding="utf-8") as f:
            if nieuw:
                f.write("# Witte lijst van dit steunpunt\n")
            f.write(f"{adres}   {naam}   # {waarom} {time.strftime('%Y-%m-%d %H:%M')}\n")
    wis_onbekend(adres)
    return True


def onbekenden():
    """[(adres, naam, gezien)] van telefoons die gehoord zijn maar niet op de witte lijst staan."""
    bekend = {a for a, _, _ in witte_lijst()}
    uit = []
    try:
        with open(ONBEKEND_FILE, encoding="utf-8") as f:
            for regel in f:
                delen = regel.split("#", 1)
                kaal = delen[0].strip()
                if not kaal:
                    continue
                stukken = kaal.split(None, 1)
                adr = stukken[0].lower()
                if not ADRES_RE.match(adr) or adr in bekend:
                    continue
                gezien = delen[1].strip().replace("gezien", "").strip() if len(delen) > 1 else ""
                uit.append((adr, stukken[1].strip() if len(stukken) > 1 else "", gezien))
    except OSError:
        pass
    return list(reversed(uit))


def wis_onbekend(adres):
    with SCHRIJF_LOCK:
        try:
            regels = open(ONBEKEND_FILE, encoding="utf-8").readlines()
        except OSError:
            return
        nieuw = [r for r in regels if not r.strip().lower().startswith(adres)]
        if len(nieuw) != len(regels):
            tmp = ONBEKEND_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.writelines(nieuw)
            os.replace(tmp, ONBEKEND_FILE)


_adres_cache = None


def steunpunt_adres():
    global _adres_cache
    if _adres_cache is None:
        try:
            import RNS
            ident = RNS.Identity.from_file(ID_FILE)
            _adres_cache = RNS.Destination.hash(ident, "lxmf", "delivery").hex() if ident else ""
        except Exception:
            _adres_cache = ""
    return _adres_cache


def rnodes_in_config():
    """RNode-interfaces uit ~/.reticulum/config: {naam: {sleutel: waarde}} (alleen niet-uitgecommentarieerd)."""
    uit, huidig = {}, None
    try:
        regels = open(RNS_CONFIG, encoding="utf-8").read().splitlines()
    except OSError:
        return None
    for r in regels:
        kaal = r.split("#", 1)[0].strip()
        if not kaal:
            continue
        m = re.match(r"^\[\[(.+)\]\]$", kaal)
        if m:
            huidig = {"_naam": m.group(1)}
            uit[m.group(1)] = huidig
            continue
        if kaal.startswith("["):
            huidig = None
            continue
        if huidig is not None and "=" in kaal:
            k, v = kaal.split("=", 1)
            huidig[k.strip().lower()] = v.strip()
    return {n: d for n, d in uit.items() if d.get("type", "").lower() == "rnodeinterface"
            and d.get("enabled", "yes").lower() in ("yes", "true", "1", "on")}


def vergelijk_radio(net):
    """Verschillen tussen het tabblad Netwerk (kaart) en de RNodes van deze Pi."""
    rnodes = rnodes_in_config()
    if rnodes is None:
        return [f"Kan {RNS_CONFIG} niet lezen; controle van de radio-instellingen overgeslagen."]
    lora = net.get("lora") or {}
    ifac_kaart = (net.get("ifac_netwerknaam") or "", net.get("ifac_wachtwoord") or "")
    verschil = []
    for band, r in lora.items():
        kandidaten = []
        for d in rnodes.values():
            try:
                f = int(float(d.get("frequency", 0)))
            except ValueError:
                continue
            if (band == "433" and 400e6 < f < 500e6) or (band == "868" and 800e6 < f < 1000e6):
                kandidaten.append((d, f))
        if not kandidaten:
            verschil.append(f"{band} MHz staat op de kaart, maar de Pi heeft geen (actieve) RNode op die band.")
            continue
        d, f = kandidaten[0]
        naam = d["_naam"]
        def getal_cfg(k):
            try:
                return int(float(d.get(k)))
            except (TypeError, ValueError):
                return None
        for titel, kaart, pi in (("frequentie", r.get("frequentie"), f), ("bandbreedte", r.get("bandbreedte"), getal_cfg("bandwidth")),
                                 ("SF", r.get("sf"), getal_cfg("spreadingfactor")), ("CR", r.get("cr"), getal_cfg("codingrate"))):
            if kaart != pi:
                verschil.append(f"{naam}: {titel} op de kaart is {kaart}, op de Pi {pi}. Telefoons en Pi horen elkaar dan niet.")
        ifac_pi = (d.get("network_name") or d.get("networkname") or "", d.get("passphrase") or d.get("pass_phrase") or "")
        if ifac_pi != ifac_kaart:
            if any(ifac_kaart) and not any(ifac_pi):
                verschil.append(f"{naam}: de kaart zet IFAC AAN ('{ifac_kaart[0]}'), maar op de Pi staat IFAC UIT. "
                                "Alle pakketten van de telefoons worden dan geweigerd.")
            elif any(ifac_pi) and not any(ifac_kaart):
                verschil.append(f"{naam}: op de Pi staat IFAC AAN ('{ifac_pi[0]}'), maar de kaart heeft geen IFAC.")
            else:
                verschil.append(f"{naam}: IFAC-netwerknaam of -wachtwoord op de kaart wijkt af van de Pi.")
    return verschil


def pas_rns_config_aan(net):
    """Zet frequentie/bandbreedte/SF/CR/IFAC van de RNodes van deze Pi gelijk aan het tabblad Netwerk.
    Zendvermogen van de Pi blijft ongemoeid. Geeft (gewijzigd, [meldingen])."""
    try:
        regels = open(RNS_CONFIG, encoding="utf-8").read().split("\n")
    except OSError as ex:
        return False, [f"Kan {RNS_CONFIG} niet lezen: {ex}"]
    # secties zoeken: [(naam, kop_index, eind_index)]
    secties, huidig = [], None
    for i, r in enumerate(regels):
        kaal = r.split("#", 1)[0].strip()
        m = re.match(r"^\[\[(.+)\]\]$", kaal)
        if m or (kaal.startswith("[") and not kaal.startswith("[[")):
            if huidig:
                secties.append((huidig[0], huidig[1], i))
            huidig = (m.group(1), i) if m else None
    if huidig:
        secties.append((huidig[0], huidig[1], len(regels)))

    def waarde(blok, sleutel):
        for r in blok:
            kaal = r.split("#", 1)[0].strip()
            if "=" in kaal and kaal.split("=", 1)[0].strip().lower() == sleutel:
                return kaal.split("=", 1)[1].strip()
        return None

    lora = net.get("lora") or {}
    ifac = (net.get("ifac_netwerknaam") or "", net.get("ifac_wachtwoord") or "")
    meldingen, gewijzigd = [], False
    gevonden = set()
    for naam, kop, eind in reversed(secties):           # van achter naar voren: indexen blijven kloppen
        blok = regels[kop + 1:eind]
        if (waarde(blok, "type") or "").lower() != "rnodeinterface":
            continue
        if (waarde(blok, "enabled") or "yes").lower() not in ("yes", "true", "1", "on"):
            continue
        try:
            f = int(float(waarde(blok, "frequency") or 0))
        except ValueError:
            continue
        band = "433" if 400e6 < f < 500e6 else ("868" if 800e6 < f < 1000e6 else None)
        if band not in lora:
            continue
        gevonden.add(band)
        r = lora[band]
        inspring = next((re.match(r"^(\s*)", x).group(1) for x in blok if x.strip() and not x.strip().startswith("#")), "    ")
        gewenst = {"frequency": str(r["frequentie"]), "bandwidth": str(r["bandbreedte"]),
                   "spreadingfactor": str(r["sf"]), "codingrate": str(r["cr"])}
        nieuw_blok, gezet = [], set()
        for x in blok:
            kaal = x.split("#", 1)[0].strip()
            sleutel = kaal.split("=", 1)[0].strip().lower() if "=" in kaal else None
            if sleutel in gewenst:
                if kaal.split("=", 1)[1].strip() != gewenst[sleutel]:
                    meldingen.append(f"{naam}: {sleutel} {kaal.split('=', 1)[1].strip()} -> {gewenst[sleutel]}")
                nieuw_blok.append(f"{inspring}{sleutel} = {gewenst[sleutel]}")
                gezet.add(sleutel)
            elif sleutel in ("network_name", "networkname", "passphrase", "pass_phrase"):
                continue                                  # IFAC wordt hieronder opnieuw gezet
            else:
                nieuw_blok.append(x)
        for k, v in gewenst.items():
            if k not in gezet:
                nieuw_blok.append(f"{inspring}{k} = {v}")
                meldingen.append(f"{naam}: {k} = {v} toegevoegd")
        oud_ifac = (waarde(blok, "network_name") or waarde(blok, "networkname") or "",
                    waarde(blok, "passphrase") or waarde(blok, "pass_phrase") or "")
        if any(ifac):
            # achteraan het blok, maar vóór lege regels en commentaar die bij de volgende sectie horen
            plek = len(nieuw_blok)
            while plek > 0 and (not nieuw_blok[plek - 1].strip() or nieuw_blok[plek - 1].strip().startswith("#")):
                plek -= 1
            nieuw_blok[plek:plek] = [f"{inspring}network_name = {ifac[0]}", f"{inspring}passphrase = {ifac[1]}"]
        if oud_ifac != ifac:
            meldingen.append(f"{naam}: IFAC " + ("aan ('" + ifac[0] + "')" if any(ifac) else "uit"))
        if nieuw_blok != blok:
            regels[kop + 1:eind] = nieuw_blok
            gewijzigd = True
    for band in lora:
        if band not in gevonden:
            meldingen.append(f"Geen actieve RNode voor {band} MHz in {RNS_CONFIG}: niet aangepast (poort moet met de hand).")
    if gewijzigd:
        kopie = RNS_CONFIG + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
        try:
            with open(kopie, "w", encoding="utf-8") as fk:
                fk.write(open(RNS_CONFIG, encoding="utf-8").read())
            tmp = RNS_CONFIG + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fo:
                fo.write("\n".join(regels))
            os.replace(tmp, RNS_CONFIG)
            meldingen.append(f"Reservekopie: {kopie}")
        except OSError as ex:
            return False, [f"Kon {RNS_CONFIG} niet schrijven: {ex}"]
    return gewijzigd, meldingen


def rnsd_start():
    """Starttijd van rnsd (unix), of None."""
    try:
        r = subprocess.run([SYSTEMCTL, "show", "rnsd", "-p", "ActiveEnterTimestamp", "--value", "--timestamp=unix"],
                           capture_output=True, text=True, timeout=5)
        w = r.stdout.strip().lstrip("@")
        return float(w) if w else None
    except Exception:
        return None


def rnsd_verouderd():
    """True als ~/.reticulum/config is gewijzigd nadat rnsd is gestart."""
    start = rnsd_start()
    try:
        gewijzigd = os.path.getmtime(RNS_CONFIG)
    except OSError:
        return False
    return start is not None and gewijzigd > start + 2


def html_radiocontrole(net):
    v = vergelijk_radio(net)
    if rnsd_verouderd():
        v.append("rnsd draait nog met een oudere versie van de radio-instellingen (de config is daarna gewijzigd). "
                 "Herstart Reticulum (LoRa) hieronder bij Diensten, en daarna de brug.")
    if not v:
        return ""
    return ("<div class='melding fout'><b>Kaart en radio van de Pi komen niet overeen.</b><ul style='margin:6px 0 0 18px;padding:0'>"
            + "".join(f"<li>{e(x)}</li>" for x in v) +
            f"</ul><div style='margin-top:6px'>Pas het tabblad Netwerk aan, of de RNodes in {e(RNS_CONFIG)} "
            "(daarna rnsd en de brug herstarten). Maak daarna een nieuwe kaart en scan die opnieuw.</div></div>")


# ---------------------------------------------------------------------------
# Diensten
# ---------------------------------------------------------------------------

def dienst_status(naam):
    try:
        r = subprocess.run([SYSTEMCTL, "is-active", naam], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() or "onbekend"
    except Exception:
        return "onbekend"


def herstart(naam):
    if naam not in [d for d, _ in DIENSTEN]:
        return False, "onbekende dienst"
    try:
        r = subprocess.run([SUDO, "-n", SYSTEMCTL, "restart", naam], capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            return True, ""
        return False, (r.stderr or r.stdout).strip()[:200]
    except Exception as e:
        return False, str(e)


def log_regels(n=60):
    try:
        r = subprocess.run([JOURNALCTL, "-u", "noodnet-brug", "-n", str(n), "--no-pager", "-o", "cat"],
                           capture_output=True, text=True, timeout=10)
        uit = r.stdout.strip()
        if not uit and r.stderr:
            return "Log niet leesbaar: " + r.stderr.strip()[:200] + \
                   "\n(Tip: sudo usermod -aG systemd-journal $USER en daarna opnieuw opstarten.)"
        return uit or "(nog geen logregels)"
    except Exception as e:
        return "Log niet beschikbaar: " + str(e)


# ---------------------------------------------------------------------------
# Vrijwilligers (zelfde regels als LIJST in de brug)
# ---------------------------------------------------------------------------

def uit_beeld_na(inst, net):
    if inst.get("uit_beeld_min"):
        return int(inst["uit_beeld_min"]) * 60
    try:
        mx = int((net.get("baken") or {}).get("max_interval_s", 1800))
    except (TypeError, ValueError):
        mx = 1800
    return max(15 * 60, int(mx * 1.5))


def duur(sec):
    m = int(sec // 60)
    return f"{m} min" if m < 60 else f"{m // 60} u {m % 60:02d}"


def vrijwilligers(inst, net):
    gehoord = lees_json(GEHOORD_FILE, {}) or {}
    grens = uit_beeld_na(inst, net)
    laag = int(inst.get("batterij_laag") or 20)
    nu = time.time()
    rijen = []
    for adr, naam, _ in witte_lijst():
        g = gehoord.get(adr, {})
        if "t" not in g:
            rijen.append({"adr": adr, "naam": naam or adr[:8], "stil": None, "status": "nooit", "prio": 2, "g": g})
            continue
        stil = nu - g["t"]
        status, prio = "ok", 3
        if ((g.get("rbat") is not None and g["rbat"] <= laag)
                or (g.get("tbat") is not None and g["tbat"] <= laag and not g.get("tladen"))):
            status, prio = "laag", 1
        if stil > grens:
            status, prio = "uit", 0
        rijen.append({"adr": adr, "naam": naam or adr[:8], "stil": stil, "status": status, "prio": prio, "g": g})
    rijen.sort(key=lambda r: (r["prio"], -(r["stil"] or 0) if r["prio"] < 2 else (r["stil"] or 0)))
    return rijen


# ---------------------------------------------------------------------------
# Controle van formulieren
# ---------------------------------------------------------------------------

def getal(tekst, soort=float):
    tekst = (tekst or "").strip().replace(",", ".")
    if not tekst:
        return None
    return soort(tekst)


def controleer_instellingen(f, oud):
    fouten = []
    inst = dict(oud)
    inst["steunpunt_naam"] = " ".join(f.get("steunpunt_naam", "").split())
    if not inst["steunpunt_naam"]:
        fouten.append("Vul de naam van het steunpunt in.")
    rn = f.get("roepnaam", "").strip().upper()
    if not ROEPNAAM_RE.match(rn):
        fouten.append("Roepnaam moet zijn als PD3PAM-1 (roepnaam, streepje, SSID 0-15).")
    inst["roepnaam"] = rn
    try:
        lat, lon = getal(f.get("latitude")), getal(f.get("longitude"))
        if (lat is None) != (lon is None):
            fouten.append("Vul breedtegraad én lengtegraad in, of laat beide leeg.")
        elif lat is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180):
            fouten.append("Positie klopt niet (breedte -90..90, lengte -180..180).")
        inst["latitude"] = round(lat, 6) if lat is not None else None
        inst["longitude"] = round(lon, 6) if lon is not None else None
    except ValueError:
        fouten.append("Positie: gebruik getallen, bijvoorbeeld 52.2551 en 6.1606.")
    code = f.get("aanmeldcode", "").strip()
    if len(code) < 4 or " " in code:
        fouten.append("Aanmeldcode: minstens 4 tekens, zonder spaties.")
    inst["aanmeldcode"] = code
    modus = f.get("witte_lijst_modus", "aan")
    inst["witte_lijst_modus"] = modus if modus in ("aan", "leren", "uit") else "aan"
    beheerders = []
    for i in range(10):
        adr = f.get(f"beh_adres_{i}", "").strip().lower().replace("<", "").replace(">", "").replace(":", "").replace(" ", "")
        naam = " ".join(f.get(f"beh_naam_{i}", "").split())
        if not adr and not naam:
            continue
        if not ADRES_RE.match(adr):
            fouten.append(f"Beheerder {naam or i + 1}: adres moet 32 tekens 0-9/a-f zijn.")
            continue
        beheerders.append({"adres": adr, "naam": naam})
    inst["beheerders"] = beheerders
    try:
        ub = getal(f.get("uit_beeld_min"), int)
        if ub is not None and not 10 <= ub <= 600:
            fouten.append("'Uit beeld na' moet tussen 10 en 600 minuten liggen (of leeg = automatisch).")
        inst["uit_beeld_min"] = ub
        bl = getal(f.get("batterij_laag"), int)
        if bl is None or not 5 <= bl <= 60:
            fouten.append("Accu-waarschuwing moet tussen 5 en 60% liggen.")
        inst["batterij_laag"] = bl if bl is not None else 20
    except ValueError:
        fouten.append("Gebruik hele getallen bij 'uit beeld na' en accu-waarschuwing.")
    return inst, fouten


def netwerk_naar_formulier(net):
    """Netwerkbestand -> dezelfde velden als het formulier op tabblad Netwerk (zodat dezelfde controles gelden)."""
    f = {"gemeente": str(net.get("gemeente") or ""),
         "frequentie_2m": f"{int(net.get('frequentie_2m') or radio.rig.STANDAARD_FREQ) / 1e6:.4f}",
         "ifac_naam": str(net.get("ifac_netwerknaam") or ""), "ifac_ww": str(net.get("ifac_wachtwoord") or "")}
    for i, (k, d) in enumerate(list((net.get("disciplines") or {}).items())[:12]):
        d = d if isinstance(d, dict) else {}
        f[f"d_sleutel_{i}"] = str(k)
        f[f"d_label_{i}"] = str(d.get("label") or k)
        f[f"d_posten_{i}"] = ", ".join(str(x) for x in (d.get("eindposten") or []))
    for k in net.get("vangnet") or []:
        f[f"vangnet_{k}"] = "on"
    for k in net.get("berichten_aan") or []:
        f[f"chat_{k}"] = "on"
    for band, r in (net.get("lora") or {}).items():
        if band in ("433", "868") and isinstance(r, dict):
            f[f"lora_{band}_aan"] = "on"
            f[f"lora_{band}_f"] = f"{(r.get('frequentie') or 0) / 1e6:.3f}"
            f[f"lora_{band}_bw"] = f"{(r.get('bandbreedte') or 0) / 1000:g}"
            f[f"lora_{band}_sf"], f[f"lora_{band}_cr"] = str(r.get("sf", "")), str(r.get("cr", ""))
            f[f"lora_{band}_p"] = str(r.get("vermogen_dbm", ""))
    bk = net.get("baken") or {}
    if bk:
        f["baken_min"] = str(int(bk.get("min_interval_s", 600) // 60))
        f["baken_max"] = str(int(bk.get("max_interval_s", 1800) // 60))
        f["baken_afstand"] = str(int(bk.get("afstand_m", 300)))
    return f


def controleer_netwerk(f, oud):
    fouten, waarschuwingen = [], []
    net = dict(oud)
    net["gemeente"] = " ".join(f.get("gemeente", "").split())
    hz, ff, ww = radio.rig.controleer_frequentie(f.get("frequentie_2m", ""))
    fouten += ff
    waarschuwingen += ww
    if hz:
        net["frequentie_2m"] = hz
    disciplines = {}
    for i in range(12):
        label = " ".join(f.get(f"d_label_{i}", "").split())
        sleutel = f.get(f"d_sleutel_{i}", "").strip().lower() or re.sub(r"[^a-z0-9]+", "", label.lower())
        if not label:
            continue
        if not sleutel:
            fouten.append(f"Discipline '{label}': geen geldige naam.")
            continue
        posten = [p.strip().upper() for p in re.split(r"[,\s]+", f.get(f"d_posten_{i}", "")) if p.strip()]
        for p in posten:
            if not ROEPNAAM_RE.match(p):
                fouten.append(f"{label}: '{p}' is geen geldige roepnaam (bijvoorbeeld PD3PAM-2).")
        disciplines[sleutel] = {"label": label, "eindposten": posten}
    if not disciplines:
        fouten.append("Er moet minstens één discipline zijn.")
    net["disciplines"] = disciplines
    net["vangnet"] = [k for k in disciplines if f.get(f"vangnet_{k}")]
    net["berichten_aan"] = [k for k in disciplines if f.get(f"chat_{k}")]
    if not any(disciplines[k]["eindposten"] for k in net["vangnet"]):
        waarschuwingen.append("Het vangnet heeft geen eindpost: meldingen voor disciplines zonder eindpost komen nergens aan.")
    if not net["berichten_aan"]:
        waarschuwingen.append("Er is niemand aangevinkt voor gewone berichten.")
    lora = {}
    for band in ("433", "868"):
        if not f.get(f"lora_{band}_aan"):
            continue
        try:
            fr = int(round(getal(f.get(f"lora_{band}_f")) * 1e6))
            bw = int(round(getal(f.get(f"lora_{band}_bw")) * 1000))
            sf, cr, p = getal(f.get(f"lora_{band}_sf"), int), getal(f.get(f"lora_{band}_cr"), int), getal(f.get(f"lora_{band}_p"), int)
        except (TypeError, ValueError):
            fouten.append(f"LoRa {band}: vul alle waarden in als getal.")
            continue
        lo, hi, pmax = GRENZEN_LORA[band]
        if not lo <= fr <= hi:
            fouten.append(f"LoRa {band}: {fr / 1e6:.3f} MHz ligt buiten de ISM-band ({lo / 1e6:.3f}-{hi / 1e6:.3f} MHz).")
        if p is not None and p > pmax:
            fouten.append(f"LoRa {band}: {p} dBm is meer dan toegestaan voor deze band (max {pmax} dBm e.r.p.).")
        if not (sf and 7 <= sf <= 12) or not (cr and 5 <= cr <= 8):
            fouten.append(f"LoRa {band}: SF moet 7-12 zijn en CR 5-8.")
        lora[band] = {"frequentie": fr, "bandbreedte": bw, "sf": sf, "cr": cr, "vermogen_dbm": p}
    if not lora:
        fouten.append("Zet minstens één LoRa-band aan.")
    net["lora"] = lora
    try:
        bmin, bmax, baf = getal(f.get("baken_min"), int), getal(f.get("baken_max"), int), getal(f.get("baken_afstand"), int)
        if bmin and bmax and baf:
            if bmin < 2 or bmax < bmin or bmax > 240 or baf < 50:
                fouten.append("Baken: minimaal 2 min, maximaal 240 min, maximum niet kleiner dan minimum, afstand vanaf 50 m.")
            net["baken"] = {"min_interval_s": bmin * 60, "max_interval_s": bmax * 60, "afstand_m": baf}
        else:
            net.pop("baken", None)
    except ValueError:
        fouten.append("Baken: gebruik hele getallen.")
    net["ifac_netwerknaam"] = f.get("ifac_naam", "").strip()
    net["ifac_wachtwoord"] = f.get("ifac_ww", "").strip()
    return net, fouten, waarschuwingen


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

e = html.escape

CSS = """
:root{--bg:#f6f7f9;--kaart:#fff;--tekst:#1b1f24;--zacht:#5b6470;--lijn:#dde1e6;--rood:#b3261e;--rood-z:#fbe9e7;
--groen:#1e7a3a;--groen-z:#e6f4ea;--oranje:#a85d00;--oranje-z:#fff3e0;--blauw:#1d4f91;--knop:#1d4f91}
@media (prefers-color-scheme:dark){:root{--bg:#14171b;--kaart:#1d2126;--tekst:#e8eaed;--zacht:#a0a8b3;--lijn:#30353c;
--rood-z:#3b1d1b;--groen-z:#16301f;--oranje-z:#3a2a12;--blauw:#8ab4f8;--knop:#3d6fb6}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tekst);font:16px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
header{background:var(--rood);color:#fff;padding:12px 16px}header b{font-size:18px}header span{opacity:.85;font-size:14px;margin-left:8px}
nav{display:flex;flex-wrap:wrap;gap:4px;padding:8px 12px;background:var(--kaart);border-bottom:1px solid var(--lijn);position:sticky;top:0}
nav a{padding:8px 12px;border-radius:8px;color:var(--tekst);text-decoration:none;font-weight:500}nav a.actief{background:var(--rood-z);color:var(--rood)}
main{max-width:880px;margin:0 auto;padding:16px}
section{background:var(--kaart);border:1px solid var(--lijn);border-radius:12px;padding:16px;margin-bottom:16px}
h2{margin:0 0 4px;font-size:18px}p.uitleg{margin:0 0 12px;color:var(--zacht);font-size:14px}
label{display:block;font-weight:600;margin:12px 0 4px}label small{font-weight:400;color:var(--zacht)}
input[type=text],input[type=number],input[type=password],select{width:100%;padding:10px;border:1px solid var(--lijn);border-radius:8px;background:var(--bg);color:var(--tekst);font-size:16px}
.rij{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media(max-width:560px){.rij{grid-template-columns:1fr}}
.rij3{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}@media(max-width:560px){.rij3{grid-template-columns:1fr 1fr}}
button,.knop{display:inline-block;padding:10px 18px;border:0;border-radius:8px;background:var(--knop);color:#fff;font-size:16px;font-weight:600;cursor:pointer;text-decoration:none}
button.licht{background:transparent;color:var(--blauw);border:1px solid var(--lijn)}button.gevaar{background:var(--rood)}
.balk{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}
.melding{padding:12px 14px;border-radius:8px;margin-bottom:12px}.ok{background:var(--groen-z);color:var(--groen)}
.fout{background:var(--rood-z);color:var(--rood)}.let{background:var(--oranje-z);color:var(--oranje)}
table{width:100%;border-collapse:collapse;font-size:15px}th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--lijn);vertical-align:middle}
th{color:var(--zacht);font-weight:600;font-size:13px}
.punt{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}.p-ok{background:var(--groen)}.p-uit{background:var(--rood)}.p-let{background:var(--oranje)}.p-grijs{background:var(--zacht)}
.mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px;word-break:break-all}
pre{background:var(--bg);border:1px solid var(--lijn);border-radius:8px;padding:10px;overflow:auto;max-height:420px;font-size:12.5px;white-space:pre-wrap}
.cijfers{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}.cijfer{border:1px solid var(--lijn);border-radius:10px;padding:10px 12px}
.cijfer b{display:block;font-size:22px}.cijfer span{color:var(--zacht);font-size:13px}
.vink{display:inline-flex;align-items:center;gap:6px;margin:4px 14px 4px 0;font-weight:400}
details summary{cursor:pointer;color:var(--blauw);font-weight:600;margin-top:8px}
"""

PAGINAS = [("status", "Status"), ("steunpunt", "Steunpunt"), ("radio", "Radio"), ("netwerk", "Netwerk"),
           ("vrijwilligers", "Vrijwilligers"), ("kaart", "Kaart"), ("backup", "Back-up")]


def pagina(actief, inhoud, inst, melding=""):
    nav = "".join(f'<a href="/{p}" class="{"actief" if p == actief else ""}">{t}</a>' for p, t in PAGINAS)
    naam = inst.get("steunpunt_naam") or "Noodsteunpunt"
    return f"""<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(naam)} - beheer</title>
<style>{CSS}</style></head><body>
<header><b>{e(naam)}</b><span>{e(inst.get('roepnaam') or '')} &middot; Noodnet beheer</span></header>
<nav>{nav}</nav><main>{melding}{inhoud}</main>{beheer.TIJD_SCRIPT % CSRF}</body></html>"""


def meldingen(ok=None, fouten=(), let=()):
    uit = ""
    if ok:
        uit += f'<div class="melding ok">{e(ok)}</div>'
    for f in fouten:
        uit += f'<div class="melding fout">{e(f)}</div>'
    for w in let:
        uit += f'<div class="melding let">{e(w)}</div>'
    return uit


def verborgen():
    return f'<input type="hidden" name="csrf" value="{CSRF}">'


def html_status(inst, net):
    rijen = ""
    for d, titel in DIENSTEN:
        st = dienst_status(d)
        kl = "p-ok" if st == "active" else ("p-let" if st in ("activating", "reloading") else "p-uit")
        tekst = {"active": "draait", "inactive": "staat uit", "failed": "GESTOPT MET FOUT",
                 "activating": "start op..."}.get(st, st)
        rijen += f"""<tr><td><span class="punt {kl}"></span>{e(titel)}</td><td>{e(tekst)}</td>
<td style="text-align:right"><form method="post" action="/herstart" style="margin:0">{verborgen()}
<input type="hidden" name="dienst" value="{e(d)}"><button class="licht" type="submit">Herstart</button></form></td></tr>"""
    vw = vrijwilligers(inst, net)
    gehoord = sum(1 for v in vw if v["status"] in ("ok", "laag"))
    uit = sum(1 for v in vw if v["status"] == "uit")
    laag = sum(1 for v in vw if v["status"] == "laag")
    a = lees_json(AANMELD_FILE, {}) or {}
    open_ = a.get("open", {})
    wr = lees_json(WACHTRIJ_FILE, {}) or {}
    items = wr.get("items", []) if isinstance(wr, dict) else (wr if isinstance(wr, list) else [])
    wachtrij = len(items)
    nu = time.time()
    traag = []
    for it in items:
        if it.get("soort") in ("MTH", "MSG", "OPR") and it.get("wacht_op") and nu - it.get("gemaakt", nu) > 300:
            wie = ", ".join(x for x in it["wacht_op"] if x != "*") or "een eindpost"
            soort = {"MTH": "M/ETHANE", "MSG": "bericht", "OPR": "operatorbericht"}[it["soort"]]
            tekst = (f"{wie} heeft een {soort} van {time.strftime('%H:%M', time.localtime(it.get('gemaakt', nu)))} "
                     f"nog niet bevestigd ({it.get('pogingen', 0)} keer verzonden). Staat die post aan en in bereik? "
                     f"Klopt de roepnaam op tabblad Netwerk?")
            knoppen = "".join(
                f'<form method="post" action="/niet_wachten" style="display:inline;margin:0">{verborgen()}'
                f'<input type="hidden" name="id" value="{e(it.get("id", ""))}"><input type="hidden" name="call" value="{e(c)}">'
                f'<button type="submit" class="licht" style="margin:4px 4px 0 0;padding:4px 10px;font-size:14px" '
                f'onclick="return confirm(\'Niet meer wachten op {e(c)}? Die post krijgt deze melding dan misschien nooit.\')">'
                f'Niet meer wachten op {e(c)}</button></form>' for c in it["wacht_op"] if c != "*")
            traag.append((tekst, knoppen))
    traag_html = ("<div class='melding let'><b>Nog niet bevestigd</b><ul style='margin:6px 0 0 18px;padding:0'>"
                  + "".join(f"<li>{e(t)}<br>{k}</li>" for t, k in traag) + "</ul></div>") if traag else ""
    klok, klokbron = beheer.tijd_tekst()
    adres = steunpunt_adres()
    open_html = ""
    if open_:
        def knop(nr, soort, tekst, kl=""):
            return (f'<form method="post" action="/aanmelding" style="display:inline;margin:0">{verborgen()}'
                    f'<input type="hidden" name="nr" value="{e(str(nr))}"><input type="hidden" name="soort" value="{soort}">'
                    f'<button type="submit" class="{kl}" style="margin:2px 0">{tekst}</button></form> ')
        rijen_o = ""
        for nr, v in sorted(open_.items(), key=lambda x: int(x[0])):
            rijen_o += (f"<tr><td>#{e(str(nr))}</td><td><b>{e(v.get('naam', ''))}</b><div style='color:var(--zacht);font-size:13px'>"
                        f"{e(v.get('telefoon') or '')} &middot; {e(v.get('tijd', ''))} &middot; <span class='mono'>{e(v.get('adr', '')[:8])}</span></div></td></tr>"
                        f"<tr><td></td><td style='border-bottom:1px solid var(--lijn)'>{knop(nr, 'JA', 'Goedkeuren')}"
                        f"{knop(nr, 'BEHEERDER', 'Goedkeuren als beheerder', 'licht')}{knop(nr, 'NEE', 'Afwijzen', 'gevaar')}</td></tr>")
        open_html = ("<section><h2>Wachten op goedkeuring</h2><p class='uitleg'>Controleer wie het is. "
                     "<b>Als beheerder</b> alleen voor de telefoon van de zendamateur zelf.</p>"
                     f"<table>{rijen_o}</table></section>")
    zonder_beheerder = ""
    if not inst.get("beheerders"):
        zonder_beheerder = ("<div class='melding let'><b>Nog geen beheerder.</b> Zo maak je je eigen telefoon beheerder: "
                            "vul eerst het tabblad Steunpunt in, maak op het tabblad Kaart de kaart, scan die QR-code met de "
                            "Noodnet-app en kies hier daarna <b>Goedkeuren als beheerder</b>.</div>")
    return f"""{zonder_beheerder}{html_radiocontrole(net)}{traag_html}
{beheer.html_operator(verborgen())}
<section><h2>Diensten</h2><p class="uitleg">Alles moet groen zijn. Herstart alleen als er iets hapert.</p>
<table>{rijen}{radio.html_set_kort()}</table></section>
<section><h2>Overzicht</h2><div class="cijfers">
<div class="cijfer"><b>{len(vw)}</b><span>aangemeld</span></div>
<div class="cijfer"><b>{gehoord}</b><span>gehoord</span></div>
<div class="cijfer"><b style="color:var(--rood)">{uit}</b><span>uit beeld</span></div>
<div class="cijfer"><b style="color:var(--oranje)">{laag}</b><span>accu laag</span></div>
<div class="cijfer"><b>{wachtrij}</b><span>in wachtrij 2 m</span></div></div>
<label>Adres van dit steunpunt</label><div class="mono">{e(adres) or 'nog onbekend (start de brug eerst)'}</div>
<label>Aanmeldcode</label><div>{e(inst.get('aanmeldcode') or '— niet ingesteld —')}</div>
<label>Tijd van de Pi</label><div>{e(klok)} <small style="color:var(--zacht)">({e(klokbron)})</small></div></section>
{open_html}
{radio.html_hotspot()}
<section><h2>Log van de brug</h2><p class="uitleg">De laatste regels; nieuwste onderaan. Ververs de pagina voor nieuwe regels.</p>
<pre>{e(log_regels())}</pre></section>
{beheer.html_pi_knoppen(verborgen())}"""


def html_steunpunt(inst, form=None):
    v = form or {}
    def w(k, std=""):
        if form is not None:
            return e(v.get(k, ""))
        x = inst.get(k)
        return e("" if x is None else str(x))
    beh = inst.get("beheerders") or []
    beh_rijen = ""
    aantal = max(3, len(beh) + 1)
    for i in range(min(aantal, 10)):
        if form is not None:
            adr, nm = v.get(f"beh_adres_{i}", ""), v.get(f"beh_naam_{i}", "")
        else:
            b = beh[i] if i < len(beh) else {}
            adr, nm = b.get("adres", ""), b.get("naam", "")
        beh_rijen += f"""<div class="rij"><input type="text" name="beh_naam_{i}" placeholder="Naam (bijv. Gert, PD3PAM)" value="{e(nm)}">
<input type="text" name="beh_adres_{i}" placeholder="LXMF-adres, 32 tekens" value="{e(adr)}" class="mono"></div><div style="height:8px"></div>"""
    modus = (v.get("witte_lijst_modus") if form is not None else inst.get("witte_lijst_modus")) or "aan"
    opties = "".join(f'<option value="{k}" {"selected" if k == modus else ""}>{t}</option>' for k, t in
                     [("aan", "Aan - alleen goedgekeurde telefoons (aanbevolen)"),
                      ("leren", "Leren - iedereen, onbekenden worden genoteerd (testen)"),
                      ("uit", "Uit - iedereen (alleen voor proeven)")])
    return f"""<form method="post" action="/steunpunt">{verborgen()}
<section><h2>Steunpunt</h2><p class="uitleg">Zo heet dit steunpunt in de app, op de kaart en bij de eindposten.</p>
<label>Naam van het steunpunt</label><input type="text" name="steunpunt_naam" value="{w('steunpunt_naam')}" placeholder="Steunpunt Deventer-Oost" required>
<label>Roepnaam op 2 m <small>met SSID, elk steunpunt een eigen SSID</small></label><input type="text" name="roepnaam" value="{w('roepnaam')}" placeholder="PD3PAM-1" required>
<label>Positie van het steunpunt <small>optioneel; staat op de kaart van de meldkamer</small></label>
<div class="rij"><input type="text" name="latitude" value="{w('latitude')}" placeholder="breedte, bijv. 52.2551" inputmode="decimal">
<input type="text" name="longitude" value="{w('longitude')}" placeholder="lengte, bijv. 6.1606" inputmode="decimal"></div>
<p class="uitleg">Tip: klik in Google Maps of OpenStreetMap met rechts op de plek en kopieer de coördinaten.</p></section>
<section><h2>Aanmelden</h2><p class="uitleg">Vrijwilligers melden zich aan met de code van de kaart. Na een wijziging: nieuwe kaarten maken.</p>
<label>Aanmeldcode</label><input type="text" name="aanmeldcode" value="{w('aanmeldcode')}" placeholder="bijv. K7M2" autocomplete="off">
<label>Wie mag melden</label><select name="witte_lijst_modus">{opties}</select></section>
<section><h2>Beheerders</h2><p class="uitleg">Telefoons van de zendamateur(s) die aanmeldingen goedkeuren (JA/NEE, LIJST, CODE).
<b>Makkelijkst:</b> scan de kaart met de Noodnet-app en kies op het tabblad Status <i>Goedkeuren als beheerder</i>;
dan komt de telefoon hier vanzelf bij. Met de hand kan ook: het adres staat in Sideband bij <i>Your address</i> (32 tekens).</p>
{beh_rijen}</section>
<section><h2>Bewaking</h2><p class="uitleg">De beheerders krijgen bericht als een vrijwilliger niet meer gehoord wordt of de accu van zijn RNode of telefoon bijna leeg is.</p>
<div class="rij"><div><label>Uit beeld na <small>minuten; leeg = automatisch (45)</small></label>
<input type="number" name="uit_beeld_min" value="{w('uit_beeld_min')}" min="10" max="600"></div>
<div><label>Accu-waarschuwing bij <small>% van de RNode</small></label>
<input type="number" name="batterij_laag" value="{w('batterij_laag')}" min="5" max="60"></div></div></section>
<div class="balk"><button type="submit">Opslaan en brug herstarten</button></div></form>"""


def html_netwerk(net, form=None):
    v = form or {}
    disc = list((net.get("disciplines") or {}).items())
    d_rijen = ""
    for i in range(len(disc) + 2):
        if form is not None:
            sl, lb, ps = v.get(f"d_sleutel_{i}", ""), v.get(f"d_label_{i}", ""), v.get(f"d_posten_{i}", "")
        elif i < len(disc):
            sl, d = disc[i]
            lb, ps = d.get("label", sl), ", ".join(d.get("eindposten", []))
        else:
            sl = lb = ps = ""
        d_rijen += f"""<tr><td><input type="hidden" name="d_sleutel_{i}" value="{e(sl)}">
<input type="text" name="d_label_{i}" value="{e(lb)}" placeholder="{'nieuwe discipline' if not sl else ''}"></td>
<td><input type="text" name="d_posten_{i}" value="{e(ps)}" placeholder="geen eindpost" class="mono"></td></tr>"""
    keuzes = [(k, d.get("label", k)) for k, d in disc]
    vang = set(net.get("vangnet") or [])
    chat = set(net.get("berichten_aan") or [])
    vang_html = "".join(f'<label class="vink"><input type="checkbox" name="vangnet_{e(k)}" {"checked" if k in vang else ""}>{e(l)}</label>' for k, l in keuzes)
    chat_html = "".join(f'<label class="vink"><input type="checkbox" name="chat_{e(k)}" {"checked" if k in chat else ""}>{e(l)}</label>' for k, l in keuzes)
    lora = net.get("lora") or {}
    lora_html = ""
    for band, titel in (("433", "433 MHz"), ("868", "868 MHz")):
        r = lora.get(band)
        if form is not None:
            aan = bool(v.get(f"lora_{band}_aan"))
            fv, bw, sf, cr, p = (v.get(f"lora_{band}_{k}", "") for k in ("f", "bw", "sf", "cr", "p"))
        else:
            aan = r is not None
            r = r or {}
            fv = f"{r['frequentie'] / 1e6:.3f}" if r.get("frequentie") else ("434.100" if band == "433" else "869.525")
            bw = f"{r['bandbreedte'] / 1000:g}" if r.get("bandbreedte") else "125"
            sf, cr = r.get("sf", 9 if band == "433" else 8), r.get("cr", 5)
            p = r.get("vermogen_dbm", 10 if band == "433" else 14)
        lora_html += f"""<label class="vink" style="font-weight:600"><input type="checkbox" name="lora_{band}_aan" {"checked" if aan else ""}>{titel}</label>
<div class="rij3"><div><small>Frequentie (MHz)</small><input type="text" name="lora_{band}_f" value="{e(str(fv))}" inputmode="decimal"></div>
<div><small>Bandbreedte (kHz)</small><input type="text" name="lora_{band}_bw" value="{e(str(bw))}" inputmode="decimal"></div>
<div><small>SF</small><input type="number" name="lora_{band}_sf" value="{e(str(sf))}" min="7" max="12"></div>
<div><small>CR</small><input type="number" name="lora_{band}_cr" value="{e(str(cr))}" min="5" max="8"></div>
<div><small>Vermogen (dBm)</small><input type="number" name="lora_{band}_p" value="{e(str(p))}" min="0" max="22"></div></div>"""
    bk = net.get("baken") or {}
    def bwaarde(k, std, deler=1):
        if form is not None:
            return e(v.get(k, ""))
        x = bk.get({"baken_min": "min_interval_s", "baken_max": "max_interval_s", "baken_afstand": "afstand_m"}[k])
        return e(str(int(x // deler)) if x else str(std))
    g = e(v.get("gemeente", "") if form is not None else net.get("gemeente", ""))
    ifn = e(v.get("ifac_naam", "") if form is not None else net.get("ifac_netwerknaam", ""))
    ifw = e(v.get("ifac_ww", "") if form is not None else net.get("ifac_wachtwoord", ""))
    return f"""{html_radiocontrole(net) if form is None else ""}<form method="post" action="/netwerk">{verborgen()}
<div class="melding let">Dit deel geldt voor de hele gemeente. Houd het bestand gelijk op alle steunpunten van {g or 'de gemeente'}, en maak na een wijziging nieuwe kaarten.</div>
<section><h2>Gemeente</h2><label>Naam van de gemeente</label><input type="text" name="gemeente" value="{g}">
<label>2 m-frequentie <small>MHz; voor alle steunpunten én eindposten van de gemeente. Afspreken met de buurgemeenten, zodat jullie elkaar niet storen.</small></label>
<input type="text" name="frequentie_2m" value="{e(v.get('frequentie_2m', '') if form is not None else radio.rig.mhz(net.get('frequentie_2m') or radio.rig.STANDAARD_FREQ).replace(' MHz', '').replace(',', '.'))}" inputmode="decimal" placeholder="144.925"></section>
<section><h2>Disciplines en eindposten</h2>
<p class="uitleg">Vul bij elke discipline de roepnaam van de eindpost in (bijv. PD3PAM-2), meerdere met een komma.
Zet hier <b>alleen</b> eindposten die echt draaien: een M/ETHANE wordt herhaald tot elke genoemde post bevestigt.</p>
<table><tr><th style="width:45%">Discipline</th><th>Eindpost(en)</th></tr>{d_rijen}</table>
<label>Vangnet <small>meldingen voor een discipline zonder eindpost gaan naar:</small></label>{vang_html}
<label>Gewone berichten <small>(zonder @naam) gaan naar:</small></label>{chat_html}</section>
<section><h2>LoRa-radio's</h2><p class="uitleg">Moet gelijk zijn aan de RNodes van het steunpunt. Komt op de kaart, zodat de app de RNode van de vrijwilliger goed instelt.
Houd je aan de ISM-regels: 433,05-434,79 MHz max 10 mW e.r.p.; 869,40-869,65 MHz max 500 mW e.r.p. en 10% zendtijd. Antennewinst telt mee.</p>{lora_html}</section>
<section><h2>Positiebaken van de app</h2><p class="uitleg">Hoe zuinig de app van een aangemelde vrijwilliger zijn positie stuurt.
Hoe ruimer, hoe minder zendtijd op LoRa en 2 m.</p>
<div class="rij3"><div><small>Bij verplaatsing hooguit elke (min)</small><input type="number" name="baken_min" value="{bwaarde('baken_min', 10, 60)}" min="2" max="240"></div>
<div><small>Anders levensteken elke (min)</small><input type="number" name="baken_max" value="{bwaarde('baken_max', 30, 60)}" min="5" max="240"></div>
<div><small>Verplaatsing vanaf (m)</small><input type="number" name="baken_afstand" value="{bwaarde('baken_afstand', 300)}" min="50"></div></div></section>
<section><details><summary>IFAC (gevorderd)</summary><p class="uitleg">Alleen invullen als IFAC op de RNodes aan staat. Dan staat het op de kaart en is de kaart VERTROUWELIJK.</p>
<div class="rij"><div><label>Netwerknaam</label><input type="text" name="ifac_naam" value="{ifn}" autocomplete="off"></div>
<div><label>Wachtwoord</label><input type="text" name="ifac_ww" value="{ifw}" autocomplete="off"></div></div></details></section>
{'' if os.path.exists(radio.RADIO_FILE) else '<label class="vink"><input type="checkbox" name="pas_rnodes_aan" checked>Ook de RNodes van deze Pi gelijkzetten (frequentie, bandbreedte, SF, CR, IFAC; zendvermogen blijft)</label>'}
<div class="balk"><button type="submit">Opslaan en herstarten</button></div></form>
{beheer.html_netwerk_delen(verborgen(), "steunpunt") if form is None else ""}"""


def html_onbekend_en_handmatig(inst):
    onb = onbekenden()
    modus = inst.get("witte_lijst_modus") or "aan"
    uitleg_modus = {"aan": "Deze telefoons worden nu geweigerd.",
                    "leren": "Modus 'leren': hun berichten worden nog doorgegeven, maar ze staan niet op de witte lijst.",
                    "uit": "De witte lijst staat uit: iedereen wordt doorgegeven."}.get(modus, "")
    if onb:
        rijen = ""
        for adr, naam, gezien in onb:
            rijen += f"""<tr><td><form method="post" action="/toelaten" style="margin:0;display:flex;gap:6px;flex-wrap:wrap;align-items:center">{verborgen()}
<input type="hidden" name="adres" value="{e(adr)}"><input type="text" name="naam" value="{e(naam)}" placeholder="naam" style="flex:1;min-width:140px">
<button type="submit">Toelaten</button></form>
<div style="color:var(--zacht);font-size:13px"><span class="mono">{e(adr)}</span> &middot; gezien {e(gezien)}</div></td>
<td style="text-align:right;vertical-align:top"><form method="post" action="/wis_onbekend" style="margin:0">{verborgen()}
<input type="hidden" name="adres" value="{e(adr)}"><button class="licht" type="submit">Wissen</button></form></td></tr>"""
        onb_html = f"""<section><h2>Onbekende telefoons ({len(onb)})</h2><p class="uitleg">Gehoord door dit steunpunt, maar niet aangemeld. {e(uitleg_modus)}
Laat alleen toe wie je kent; normaal meldt een vrijwilliger zich aan met de kaart.</p><table>{rijen}</table></section>"""
    else:
        onb_html = "<section><h2>Onbekende telefoons</h2><p class='uitleg'>Geen onbekende telefoons gehoord.</p></section>"
    hand = f"""<section><details><summary>Telefoon met de hand toevoegen</summary><p class="uitleg">Alleen voor uitzonderingen (bijv. een telefoon zonder Noodnet-app).
Het adres staat in Sideband bij <i>Your address</i>.</p><form method="post" action="/toelaten">{verborgen()}
<div class="rij"><div><label>Naam</label><input type="text" name="naam" required></div>
<div><label>LXMF-adres (32 tekens)</label><input type="text" name="adres" class="mono" required></div></div>
<div class="balk"><button type="submit">Toevoegen aan witte lijst</button></div></form></details></section>"""
    return onb_html + hand


def html_vrijwilligers(inst, net):
    vw = vrijwilligers(inst, net)
    if not vw:
        return "<section><h2>Vrijwilligers</h2><p>Nog niemand aangemeld.</p></section>" + html_onbekend_en_handmatig(inst)
    rijen = ""
    for r in vw:
        g = r["g"]
        if r["status"] == "nooit":
            punt, tijd = "p-grijs", "nog niet gehoord"
        else:
            punt = {"ok": "p-ok", "laag": "p-let", "uit": "p-uit"}[r["status"]]
            tijd = duur(r["stil"]) + " geleden"
            if r["status"] == "uit":
                tijd += " &middot; <b>uit beeld</b>"
        accu = "<br>".join(x for x in (
            f"RNode {g['rbat']}%" if g.get("rbat") is not None else "",
            f"tel. {g['tbat']}%" + (" (laadt)" if g.get("tladen") else "") if g.get("tbat") is not None else "") if x) or "–"
        waar = f'<a href="https://www.openstreetmap.org/?mlat={g["lat"]}&mlon={g["lon"]}#map=16/{g["lat"]}/{g["lon"]}" target="_blank">kaart</a>' if "lat" in g else "–"
        rijen += f"""<tr><td><span class="punt {punt}"></span>{e(r['naam'])}<div class="mono" style="color:var(--zacht)">{e(r['adr'][:8])}</div></td>
<td>{tijd}</td><td>{accu}</td><td>{waar}</td>
<td style="text-align:right"><form method="post" action="/afmelden" style="margin:0" onsubmit="return confirm('{e(r['naam'])} afmelden? Deze telefoon kan daarna niet meer melden tot opnieuw goedgekeurd.')">
{verborgen()}<input type="hidden" name="adres" value="{e(r['adr'])}"><button class="licht" type="submit">Afmelden</button></form></td></tr>"""
    return f"""<section><h2>Vrijwilligers</h2><p class="uitleg">Wie aandacht nodig heeft staat bovenaan. Uit beeld na {uit_beeld_na(inst, net) // 60} minuten stilte.
Ververs de pagina voor de laatste stand.</p>
<table><tr><th>Naam</th><th>Laatst gehoord</th><th>Accu</th><th>Positie</th><th></th></tr>{rijen}</table></section>""" + html_onbekend_en_handmatig(inst)


def html_qr_groot(inst, kaart_html):
    """Alleen de QR-code, schermvullend: om te scannen vanaf de telefoon van de beheerder."""
    import re as _re
    m = _re.search(r"<svg.*?</svg>", kaart_html, _re.S)
    svg = m.group(0) if m else "<p>QR-code niet gevonden: maak een nieuwe kaart.</p>"
    naam = inst.get("steunpunt_naam") or "Noodsteunpunt"
    return f"""<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>QR - {e(naam)}</title>
<style>html,body{{margin:0;background:#fff;color:#000;font-family:Arial,sans-serif;text-align:center}}
.qr svg{{width:min(92vw,78vh);height:min(92vw,78vh);display:block;margin:2vh auto}}
h1{{font-size:20px;margin:12px 8px 0}}p{{margin:4px 8px;font-size:15px}}a{{color:#1a5fb4}}</style></head><body>
<h1>{e(naam)}</h1><div class="qr">{svg}</div>
<p>Scan met de camera, of in de app: <b>Kaart van steunpunt scannen</b>.</p>
<p>Zet de helderheid van dit scherm hoog. <a href="/kaart">Terug</a></p></body></html>"""


def html_kaart(inst):
    bestaat = os.path.exists(KAART_HTML)
    gemaakt = time.strftime("%d-%m-%Y %H:%M", time.localtime(os.path.getmtime(KAART_HTML))) if bestaat else ""
    voorbeeld = f"""<section><h2>Huidige kaart</h2><p class="uitleg">Gemaakt {gemaakt}. Open hem en druk af op A5 of A6 (liefst in kleur), daarna lamineren.</p>
<div class="balk"><a class="knop" href="/kaart-qr">QR-code groot tonen</a>
<a class="knop" href="/kaart.html" target="_blank" style="background:transparent;color:var(--blauw);border:1px solid var(--lijn)">Kaart openen om af te drukken</a></div>
<p class="uitleg" style="margin-top:8px">Geen printer ter plekke? Tik op <b>QR-code groot tonen</b> en laat de vrijwilliger de code van jouw scherm scannen.</p>
<iframe src="/kaart.html" style="width:100%;height:520px;border:1px solid var(--lijn);border-radius:8px;margin-top:12px;background:#fff"></iframe></section>""" if bestaat else ""
    return f"""<section><h2>Aanmeldkaart</h2><p class="uitleg">De kaart bevat de QR-code die vrijwilligers scannen: adres van dit steunpunt,
aanmeldcode ({e(inst.get('aanmeldcode') or 'niet ingesteld')}), LoRa-instellingen en disciplines. Maak een nieuwe na elke wijziging van de code of het netwerk.</p>
<form method="post" action="/kaart">{verborgen()}<button type="submit">Nieuwe kaart maken</button></form></section>{voorbeeld}"""


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

def wachtwoord_ok(gebruiker, ww):
    data = lees_json(WW_FILE)
    if not data:
        return False
    try:
        zout = base64.b64decode(data["zout"])
        verwacht = base64.b64decode(data["hash"])
        poging = hashlib.pbkdf2_hmac("sha256", ww.encode(), zout, int(data.get("rondes", 200000)))
        return hmac.compare_digest(poging, verwacht) and gebruiker == data.get("gebruiker", "beheer")
    except Exception:
        return False


class Handler(BaseHTTPRequestHandler):
    server_version = "NoodnetWeb/1"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    def _auth(self):
        kop = self.headers.get("Authorization", "")
        if kop.startswith("Basic "):
            try:
                g, w = base64.b64decode(kop[6:]).decode().split(":", 1)
                if wachtwoord_ok(g, w):
                    return True
            except Exception:
                pass
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Noodnet steunpunt", charset="UTF-8"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("Inloggen vereist (gebruiker: beheer).".encode())
        return False

    def _stuur(self, tekst, code=200, soort="text/html; charset=utf-8"):
        data = tekst.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", soort)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.end_headers()
        self.wfile.write(data)

    def _terug(self, waar, melding=""):
        self.send_response(303)
        self.send_header("Location", waar + (("?m=" + quote(melding)) if melding else ""))
        self.end_headers()

    def do_GET(self):
        if not self._auth():
            return
        url = urlparse(self.path)
        pad = url.path.strip("/") or "status"
        m = parse_qs(url.query).get("m", [""])[0]
        inst, net = instellingen(), netwerk()
        teksten = {"opgeslagen": "Opgeslagen. De brug wordt herstart.", "herstart": "Dienst herstart.",
                   "afgemeld": "Afgemeld.", "kaart": "Nieuwe kaart gemaakt.",
                   "beslist": "Verwerkt. De telefoon krijgt bericht via de radio.",
                   "toegelaten": "Op de witte lijst gezet. De brug laat deze telefoon direct door.",
                   "gewist": "Uit de lijst van onbekende telefoons gehaald.",
                   "radio": "Radio-instellingen opgeslagen; Direwolf, Reticulum en de brug zijn herstart.",
                   "niet_wachten": "Het steunpunt wacht niet meer op de bevestiging van die post."}
        meld = meldingen(ok=teksten.get(m)) if m in teksten else ""
        if m.startswith("fout:"):
            meld = meldingen(fouten=[m[5:]])
        elif m.startswith("ok:"):
            meld = meldingen(ok=m[3:])
        if pad == "netwerk.json":
            net_nu = netwerk()
            data = json.dumps(net_nu, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{beheer.netwerk_export_naam(net_nu)}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if pad == "backup.zip":
            data, naam = beheer.maak_backup("steunpunt", inst.get("roepnaam", ""))
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{naam}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if pad == "backup":
            return self._stuur(pagina("backup", beheer.html_backup("steunpunt", verborgen()), inst, meld))
        if pad == "kaart-qr":
            try:
                kaart = open(KAART_HTML, encoding="utf-8").read()
            except OSError:
                return self._stuur("Nog geen kaart gemaakt.", 404, "text/plain; charset=utf-8")
            return self._stuur(html_qr_groot(inst, kaart))
        if pad == "kaart.html":
            try:
                return self._stuur(open(KAART_HTML, encoding="utf-8").read())
            except OSError:
                return self._stuur("Nog geen kaart gemaakt.", 404, "text/plain; charset=utf-8")
        if pad == "status":
            return self._stuur(pagina("status", html_status(inst, net), inst, meld))
        if pad == "steunpunt":
            return self._stuur(pagina("steunpunt", html_steunpunt(inst), inst, meld))
        if pad == "netwerk":
            return self._stuur(pagina("netwerk", html_netwerk(net), inst, meld))
        if pad == "vrijwilligers":
            return self._stuur(pagina("vrijwilligers", html_vrijwilligers(inst, net), inst, meld))
        if pad == "kaart":
            return self._stuur(pagina("kaart", html_radiocontrole(net) + html_kaart(inst), inst, meld))
        if pad == "radio":
            return self._stuur(pagina("radio", radio.html_radio("steunpunt", verborgen()), inst, meld))
        self._stuur("Niet gevonden", 404, "text/plain; charset=utf-8")

    def _formulier(self):
        lengte = min(int(self.headers.get("Content-Length", 0) or 0), 200000)
        ruw = self.rfile.read(lengte).decode("utf-8", "replace")
        return {k: v[-1] for k, v in parse_qs(ruw, keep_blank_values=True).items()}

    def do_POST(self):
        if not self._auth():
            return
        if urlparse(self.path).path.strip("/") == "terugzetten":
            return self._terugzetten()
        if urlparse(self.path).path.strip("/") == "netwerk_import":
            ingeladen, csrf, fout_imp = beheer.lees_netwerkbestand(self)
            if not hmac.compare_digest(csrf, CSRF):
                return self._terug("/netwerk", "fout:Formulier verlopen, probeer het opnieuw.")
            if fout_imp:
                return self._terug("/netwerk", "fout:" + fout_imp)
            f = dict(netwerk_naar_formulier(ingeladen), csrf=csrf)
            pad = "netwerk"
        else:
            f = self._formulier()
            pad = urlparse(self.path).path.strip("/")
        if not hmac.compare_digest(f.get("csrf", ""), CSRF):
            return self._terug("/status", "fout:Formulier verlopen, probeer het opnieuw.")
        inst, net = instellingen(), netwerk()

        if pad == "steunpunt":
            nieuw, fouten = controleer_instellingen(f, inst)
            if fouten:
                return self._stuur(pagina("steunpunt", html_steunpunt(inst, f), inst, meldingen(fouten=fouten)))
            roepnaam_anders = nieuw.get("roepnaam") != inst.get("roepnaam")
            with SCHRIJF_LOCK:
                schrijf_json(INST_FILE, nieuw)
                if roepnaam_anders and os.path.exists(radio.RADIO_FILE):
                    radio.maak_direwolf(nieuw["roepnaam"], radio.instellingen())
                    herstart("direwolf")
                a = lees_json(AANMELD_FILE)
                if isinstance(a, dict) and a.get("code") != nieuw["aanmeldcode"]:
                    a["code"] = nieuw["aanmeldcode"]       # gelijk houden met CODE vanaf de telefoon
                    schrijf_json(AANMELD_FILE, a)
            ok, fout = herstart("noodnet-brug")
            return self._terug("/steunpunt", "opgeslagen" if ok else "fout:Opgeslagen, maar herstart lukte niet: " + fout)

        if pad == "netwerk":
            nieuw, fouten, let = controleer_netwerk(f, net)
            if fouten:
                return self._stuur(pagina("netwerk", html_netwerk(net, f), inst, meldingen(fouten=fouten, let=let)))
            with SCHRIJF_LOCK:
                schrijf_json(NET_FILE, nieuw)
            radio_info, fouten_h = [], []
            if os.path.exists(radio.RADIO_FILE):
                # Poorten staan op tabblad Radio: Reticulum-config helemaal opnieuw maken met de banden van
                # dit tabblad. Dan maakt de volgorde (eerst Radio of eerst Netwerk) niet uit.
                try:
                    oud = open(radio.RNS_CONFIG, encoding="utf-8").read()
                except OSError:
                    oud = ""
                radio.maak_reticulum(radio.instellingen(), nieuw)
                nieuw_cfg = open(radio.RNS_CONFIG, encoding="utf-8").read()
                zonder_tijd = lambda t: "\n".join(x for x in t.split("\n") if not x.startswith("# Gemaakt door"))
                if zonder_tijd(oud) != zonder_tijd(nieuw_cfg) or rnsd_verouderd():
                    ok_r, fout_r = herstart("rnsd")
                    if not ok_r:
                        fouten_h.append("Radio-instellingen aangepast, maar rnsd herstarten lukte niet: " + fout_r)
                    radio_info.append("RNodes van deze Pi opnieuw ingesteld en Reticulum herstart.")
                    time.sleep(3)
                let = list(let) + radio.rnode_waarschuwingen(radio.instellingen(), nieuw)
            elif f.get("pas_rnodes_aan"):
                gewijzigd, radio_info = pas_rns_config_aan(nieuw)
                if gewijzigd or rnsd_verouderd():
                    ok_r, fout_r = herstart("rnsd")
                    if not ok_r:
                        fouten_h.append("Radio-instellingen aangepast, maar rnsd herstarten lukte niet: " + fout_r)
                    time.sleep(3)
            ok, fout = herstart("noodnet-brug")
            if not ok:
                fouten_h.append("Opgeslagen, maar herstart van de brug lukte niet: " + fout)
            if nieuw.get("frequentie_2m") != net.get("frequentie_2m"):
                if radio.rig.cat_actief(radio.instellingen()):
                    meld_set = radio.rig.zet_set(radio.instellingen(), nieuw["frequentie_2m"])
                    radio.rig.log(f"Nieuwe frequentie {radio.rig.mhz(nieuw['frequentie_2m'])} ingesteld" + (": " + "; ".join(meld_set) if meld_set else ""))
                    radio_info.append(f"Set (CAT) op {radio.rig.mhz(nieuw['frequentie_2m'])} gezet." + (" " + "; ".join(meld_set) if meld_set else ""))
                else:
                    let = list(let) + [f"Nieuwe 2 m-frequentie: zet de set op {radio.rig.mhz(nieuw['frequentie_2m'])}, en ook de eindposten (tabblad Instellingen)."]
            melding = meldingen(ok="Opgeslagen. Maak ook een nieuwe kaart (tabblad Kaart) en laat de telefoons die opnieuw scannen."
                                if not fouten_h else None, fouten=fouten_h, let=let)
            if radio_info:
                melding += "<div class='melding ok'><b>RNodes van deze Pi:</b><ul style='margin:6px 0 0 18px;padding:0'>" + \
                           "".join(f"<li>{e(x)}</li>" for x in radio_info) + "</ul></div>"
            return self._stuur(pagina("netwerk", html_netwerk(nieuw), inst, melding))

        if pad == "tijd":
            uit = beheer.tijd_van_telefoon(f.get("ms"))
            if uit:
                sys.stderr.write(uit + "\n")
            return self._stuur(uit or "ok", soort="text/plain; charset=utf-8")
        if pad == "set_nu":
            meld = radio.rig.zet_set(radio.instellingen())
            radio.rig.log("Set ingesteld via de beheerpagina" + (": " + "; ".join(meld) if meld else ""))
            uit = meldingen(fouten=meld) if meld else meldingen(ok="Set ingesteld op " + radio.rig.mhz(radio.rig.doelfrequentie()) + ".")
            return self._stuur(pagina("radio", uit + radio.html_radio("steunpunt", verborgen()), inst))
        if pad == "set_zoek":
            uitslag = radio.verwerk_zoek("steunpunt", inst.get("roepnaam"), herstart, verborgen())
            return self._stuur(pagina("radio", radio.html_radio("steunpunt", verborgen(), zoekuitslag=uitslag), inst))
        if pad == "set_kies":
            fouten, diensten = radio.kies_set("steunpunt", f, inst.get("roepnaam"), net)
            if fouten:
                return self._stuur(pagina("radio", meldingen(fouten=fouten) + radio.html_radio("steunpunt", verborgen()), inst))
            for d in diensten:
                herstart(d)
            time.sleep(4)
            return self._terug("/radio", "ok:CAT ingesteld; de set gaat naar de frequentie van de gemeente. Doe nu een Testuitzending.")
        if pad == "radiotest":
            return self._stuur(pagina("radio", radio.verwerk_test(inst.get("roepnaam"), f) +
                                      radio.html_radio("steunpunt", verborgen()), inst))
        if pad == "radio":
            fouten, diensten, r = radio.verwerk_radio("steunpunt", f, inst.get("roepnaam"), net)
            if fouten:
                return self._stuur(pagina("radio", radio.html_radio("steunpunt", verborgen(), dict(r, **f), fouten), inst))
            mis = []
            for d in diensten:
                ok, fout = herstart(d)
                if not ok:
                    mis.append(f"{d}: {fout}")
                if d == "rnsd":
                    time.sleep(4)
            waarsch = radio.rnode_waarschuwingen(r, net)
            if not mis and waarsch:
                return self._stuur(pagina("radio", meldingen(ok="Radio-instellingen opgeslagen; Direwolf, Reticulum en de brug zijn herstart.",
                                                             let=waarsch) + radio.html_radio("steunpunt", verborgen()), inst))
            return self._terug("/radio", "radio" if not mis else "fout:Opgeslagen, maar herstarten lukte niet: " + "; ".join(mis))

        if pad == "niet_wachten":
            mid, call = f.get("id", ""), f.get("call", "").upper()
            if not re.match(r"^[A-Za-z0-9]{2,16}$", mid) or not re.match(r"^[A-Z0-9]{3,6}(-([0-9]|1[0-5]))?$", call):
                return self._terug("/status", "fout:Ongeldige opdracht.")
            with SCHRIJF_LOCK:
                lijst = lees_json(OPDRACHTEN_FILE, []) or []
                lijst.append({"soort": "NIET_WACHTEN", "id": mid, "call": call, "tijd": int(time.time())})
                schrijf_json(OPDRACHTEN_FILE, lijst)
            for _ in range(10):
                time.sleep(0.5)
                if not os.path.exists(OPDRACHTEN_FILE):
                    break
            return self._terug("/status", "niet_wachten")

        if pad == "aanmelding":
            soort, nr = f.get("soort", ""), f.get("nr", "")
            if soort not in ("JA", "NEE", "BEHEERDER") or not nr.isdigit():
                return self._terug("/status", "fout:Ongeldige opdracht.")
            if dienst_status("noodnet-brug") != "active":
                return self._terug("/status", "fout:De brug draait niet; start die eerst (Herstart).")
            with SCHRIJF_LOCK:
                lijst = lees_json(OPDRACHTEN_FILE, []) or []
                lijst.append({"soort": soort, "nr": int(nr), "tijd": int(time.time())})
                schrijf_json(OPDRACHTEN_FILE, lijst)
            for _ in range(10):                 # even wachten tot de brug het heeft verwerkt
                time.sleep(0.5)
                if not os.path.exists(OPDRACHTEN_FILE):
                    break
            return self._terug("/status", "beslist" if not os.path.exists(OPDRACHTEN_FILE) else
                               "fout:De brug heeft de opdracht nog niet opgepakt; ververs zo de pagina.")

        if pad == "operator":
            ok, tekst, vorige = beheer.verwerk_operator(f)
            if not ok:
                return self._terug("/status", "fout:" + tekst)
            if vorige is None:                      # niet gewisseld (lijst aangepast of dezelfde operator)
                return self._terug("/status", "ok:" + tekst)
            sys.stderr.write(f"Operator: {beheer.operator_tekst()} (was {vorige.get('roepnaam') or '-'})\n")
            if dienst_status("noodnet-brug") == "active":       # in het log van de brug zetten
                with SCHRIJF_LOCK:
                    lijst = lees_json(OPDRACHTEN_FILE, []) or []
                    lijst.append({"soort": "OPERATOR", "tekst": beheer.operator_tekst(),
                                  "vorige": vorige.get("roepnaam", ""), "tijd": int(time.time())})
                    schrijf_json(OPDRACHTEN_FILE, lijst)
            return self._terug("/status", "ok:" + tekst)
        if pad == "pi":
            uit = beheer.pi_actie(f.get("actie", ""))
            if uit:
                sys.stderr.write(f"Pi {f.get('actie')} via de beheerpagina\n")
                return self._stuur(uit)
            return self._terug("/status", "fout:Ongeldige opdracht.")
        if pad == "herstart":
            ok, fout = herstart(f.get("dienst", ""))
            return self._terug("/status", "herstart" if ok else "fout:Herstart lukte niet: " + fout)

        if pad == "toelaten":
            adr = f.get("adres", "").strip().lower().replace("<", "").replace(">", "").replace(" ", "")
            naam = " ".join(f.get("naam", "").split()) or adr[:8]
            if not ADRES_RE.match(adr):
                return self._terug("/vrijwilligers", "fout:Adres moet 32 tekens 0-9/a-f zijn.")
            if not toelaten(adr, naam):
                return self._terug("/vrijwilligers", "fout:Deze telefoon staat al op de witte lijst.")
            return self._terug("/vrijwilligers", "toegelaten")

        if pad == "wis_onbekend":
            adr = f.get("adres", "").lower()
            if ADRES_RE.match(adr):
                wis_onbekend(adr)
            return self._terug("/vrijwilligers", "gewist")

        if pad == "afmelden":
            adr = f.get("adres", "").lower()
            if ADRES_RE.match(adr) and afmelden(adr):
                if dienst_status("noodnet-brug") == "active":   # brug licht de telefoon in
                    with SCHRIJF_LOCK:
                        lijst = lees_json(OPDRACHTEN_FILE, []) or []
                        lijst.append({"soort": "AFGEMELD", "adr": adr, "tijd": int(time.time())})
                        schrijf_json(OPDRACHTEN_FILE, lijst)
                return self._terug("/vrijwilligers", "afgemeld")
            return self._terug("/vrijwilligers", "fout:Niet gevonden.")

        if pad == "kaart":
            try:
                r = subprocess.run([sys.executable, KAART_SCRIPT, "--uit", KAART_HTML], cwd=MAP,
                                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
                                   env=dict(os.environ, PYTHONIOENCODING="utf-8"))
                if r.returncode != 0:
                    return self._terug("/kaart", "fout:" + (r.stderr or r.stdout).strip().splitlines()[-1][:200])
            except Exception as ex:
                return self._terug("/kaart", "fout:" + str(ex)[:200])
            return self._terug("/kaart", "kaart")

        self._stuur("Niet gevonden", 404, "text/plain; charset=utf-8")


def _terugzetten(self):
    lengte = int(self.headers.get("Content-Length", 0) or 0)
    if lengte > 60_000_000:
        return self._terug("/backup", "fout:Bestand is te groot.")
    data, velden = beheer.lees_upload(self.headers.get("Content-Type", ""), self.rfile.read(lengte))
    if not hmac.compare_digest(velden.get("csrf", ""), CSRF):
        return self._terug("/backup", "fout:Formulier verlopen, probeer het opnieuw.")
    if not data:
        return self._terug("/backup", "fout:Geen bestand gekozen.")
    ok, meld = beheer.zet_terug("steunpunt", data)
    if not ok:
        return self._terug("/backup", "fout:" + " ".join(meld))
    global _adres_cache
    _adres_cache = None
    r = radio.instellingen()
    try:
        inst = instellingen()
        radio.rig.schrijf_env(r)
        radio.maak_direwolf(inst.get("roepnaam"), r)
        if r.get("rnode_433") or r.get("rnode_868"):
            radio.maak_reticulum(r, netwerk())
    except Exception as ex:
        meld.append(f"Radio-instellingen niet opnieuw gemaakt: {ex}")
    for d in ("noodnet-rigctld", "direwolf", "rnsd", "noodnet-brug"):
        herstart(d)
        if d == "rnsd":
            time.sleep(4)
    inst = instellingen()
    return self._stuur(pagina("backup", meldingen(ok=" ".join(meld) + " Diensten herstart.") +
                              beheer.html_backup("steunpunt", verborgen()), inst))


Handler._terugzetten = _terugzetten


def stel_wachtwoord_in():
    print("Wachtwoord voor de beheerpagina (gebruiker: beheer)")
    w1 = getpass.getpass("Nieuw wachtwoord: ")
    w2 = getpass.getpass("Nog een keer: ")
    if w1 != w2 or len(w1) < 8:
        sys.exit("Niet gelijk, of korter dan 8 tekens. Niets gewijzigd.")
    zout = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", w1.encode(), zout, 200000)
    schrijf_json(WW_FILE, {"gebruiker": "beheer", "zout": base64.b64encode(zout).decode(),
                           "hash": base64.b64encode(h).decode(), "rondes": 200000})
    os.chmod(WW_FILE, 0o600)
    print("Opgeslagen in", WW_FILE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--poort", type=int, default=8080)
    ap.add_argument("--wachtwoord", action="store_true", help="wachtwoord instellen of wijzigen")
    args = ap.parse_args()
    if args.wachtwoord:
        return stel_wachtwoord_in()
    if not lees_json(WW_FILE):
        sys.exit("Stel eerst een wachtwoord in:  python noodnet_web.py --wachtwoord")
    radio.rig.start_bewaker(radio.instellingen, lambda t: print("Set: " + t, flush=True))
    server = ThreadingHTTPServer(("0.0.0.0", args.poort), Handler)
    print(f"Noodnet beheerpagina op http://0.0.0.0:{args.poort}  (gebruiker: beheer)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

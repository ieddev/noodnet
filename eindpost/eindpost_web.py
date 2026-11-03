#!/usr/bin/env python3
"""
eindpost_web.py - beheerpagina van een Noodnet-EINDPOST (Pi met 2 m-transceiver).

Open in een browser op hetzelfde netwerk:   http://<naam-of-ip-van-de-pi>:8080
  Status       diensten (Direwolf, ontvanger, Mosquitto, Node-RED), steunpunten, log
  Instellingen naam, roepnaam, disciplines, meelezen, MQTT
  Logboek      alle ontvangen meldingen per dag (lezen, CSV downloaden)
Het M/ETHANE-scherm zelf staat in Node-RED:  http://<pi>:1880/ui

Eenmalig een wachtwoord instellen:
    ~/noodnet-venv/bin/python eindpost_web.py --wachtwoord
"""

import argparse
import base64
import csv
import getpass
import hashlib
import hmac
import html
import io
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

MAP = os.path.dirname(os.path.abspath(__file__))
INST_FILE = os.path.join(MAP, "eindpost_instellingen.json")
SCRIPT_FILE = os.path.join(MAP, "ax25_to_mqtt.py")
LOGBOEK_DIR = os.path.join(MAP, "logboek")
WW_FILE = os.path.join(MAP, "web_wachtwoord.json")

DIENSTEN = [("direwolf", "Direwolf (2 m)"), ("noodnet-eindpost", "Ontvanger (ax25_to_mqtt)"),
            ("mosquitto", "MQTT (Mosquitto)"), ("nodered", "Node-RED (scherm)"), ("noodnet-download", "Startpagina (poort 80)")]
SYSTEMCTL = os.environ.get("NOODNET_SYSTEMCTL", "systemctl")
SUDO = os.environ.get("NOODNET_SUDO", "sudo")
JOURNALCTL = os.environ.get("NOODNET_JOURNALCTL", "journalctl")

CSRF = secrets.token_urlsafe(24)
SCHRIJF_LOCK = threading.Lock()
ROEPNAAM_RE = re.compile(r"^[A-Z0-9]{3,6}(-([0-9]|1[0-5]))?$")
DAG_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
BEKENDE_DISCIPLINES = [("brandweer", "Brandweer"), ("ambulance", "Ambulance"), ("politie", "Politie"),
                       ("waterschap", "Waterschap"), ("gemeente", "Gemeente")]
STANDAARD = {"eindpost_naam": "", "roepnaam": "", "disciplines": ["alle"], "meelezen": False,
             "toegestane_steunpunten": [], "mqtt_broker": "127.0.0.1", "mqtt_poort": 1883,
             "mqtt_gebruiker": "", "mqtt_wachtwoord": "", "log_posities": True}

e = html.escape


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


def script_standaard(naam):
    try:
        src = open(SCRIPT_FILE, encoding="utf-8").read()
    except OSError:
        return None
    m = re.search(rf'^{naam}\s*=\s*(.+)$', src, re.M)
    if not m:
        return None
    try:
        import ast
        return ast.literal_eval(m.group(1).split("#")[0].strip())
    except Exception:
        return None


def instellingen():
    inst = dict(STANDAARD)
    opgeslagen = lees_json(INST_FILE)
    if isinstance(opgeslagen, dict):
        inst.update(opgeslagen)
    else:
        for k, var in (("eindpost_naam", "EINDPOST_NAAM"), ("roepnaam", "CALLSIGN"), ("disciplines", "DISCIPLINES"),
                       ("meelezen", "MEELEZEN"), ("toegestane_steunpunten", "TOEGESTANE_STEUNPUNTEN")):
            w = script_standaard(var)
            if w is not None:
                inst[k] = w
    return inst


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
        return (True, "") if r.returncode == 0 else (False, (r.stderr or r.stdout).strip()[:200])
    except Exception as ex:
        return False, str(ex)


def log_regels(n=50):
    try:
        r = subprocess.run([JOURNALCTL, "-u", "noodnet-eindpost", "-n", str(n), "--no-pager", "-o", "cat"],
                           capture_output=True, text=True, timeout=10)
        uit = r.stdout.strip()
        if not uit and r.stderr:
            return "Log niet leesbaar: " + r.stderr.strip()[:200]
        return uit or "(nog geen logregels)"
    except Exception as ex:
        return "Log niet beschikbaar: " + str(ex)


def dagen():
    try:
        return sorted({f[:10] for f in os.listdir(LOGBOEK_DIR) if DAG_RE.match(f[:10])}, reverse=True)
    except OSError:
        return []


def csv_rijen(dag):
    pad = os.path.join(LOGBOEK_DIR, dag + ".csv")
    try:
        with open(pad, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f, delimiter=";"))
    except OSError:
        return []


# ---------------------------------------------------------------------------
# Gedeeld met de steunpunt-pagina: opmaak en wachtwoord
# ---------------------------------------------------------------------------

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




def stel_wachtwoord_in():
    print("Wachtwoord voor de beheerpagina van de eindpost (gebruiker: beheer)")
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




# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

PAGINAS = [("status", "Status"), ("instellingen", "Instellingen"), ("radio", "Radio"), ("logboek", "Logboek")]


def pagina(actief, inhoud, inst, melding=""):
    nav = "".join(f'<a href="/{p}" class="{"actief" if p == actief else ""}">{t}</a>' for p, t in PAGINAS)
    nav += '<a href="/scherm" target="_blank">M/ETHANE-scherm &#8599;</a>'
    naam = inst.get("eindpost_naam") or "Eindpost"
    return f"""<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(naam)} - beheer</title>
<style>{CSS}</style></head><body>
<header><b>{e(naam)}</b><span>{e(inst.get('roepnaam') or '')} &middot; Noodnet eindpost</span></header>
<nav>{nav}</nav><main>{melding}{inhoud}</main></body></html>"""


def meldingen(ok=None, fouten=()):
    uit = f'<div class="melding ok">{e(ok)}</div>' if ok else ""
    return uit + "".join(f'<div class="melding fout">{e(f)}</div>' for f in fouten)


def verborgen():
    return f'<input type="hidden" name="csrf" value="{CSRF}">'


def html_status(inst):
    rijen = ""
    for d, titel in DIENSTEN:
        st = dienst_status(d)
        kl = "p-ok" if st == "active" else ("p-let" if st in ("activating", "reloading") else "p-uit")
        tekst = {"active": "draait", "inactive": "staat uit", "failed": "GESTOPT MET FOUT",
                 "activating": "start op..."}.get(st, st)
        rijen += f"""<tr><td><span class="punt {kl}"></span>{e(titel)}</td><td>{e(tekst)}</td>
<td style="text-align:right"><form method="post" action="/herstart" style="margin:0">{verborgen()}
<input type="hidden" name="dienst" value="{e(d)}"><button class="licht" type="submit">Herstart</button></form></td></tr>"""
    vandaag = time.strftime("%Y-%m-%d")
    rij = csv_rijen(vandaag)
    mth = sum(1 for r in rij if r.get("soort") == "M/ETHANE")
    mth_mij = sum(1 for r in rij if r.get("soort") == "M/ETHANE" and r.get("voor_deze_post") == "ja")
    msg = sum(1 for r in rij if r.get("soort") == "BERICHT")
    steunpunten = {}
    for r in rij:
        if r.get("soort") == "STATUS":
            steunpunten[r.get("steunpunt")] = r
    sp_html = "".join(f"<tr><td>{e(r.get('van', ''))}<div class='mono' style='color:var(--zacht)'>{e(sp)}</div></td>"
                      f"<td>{e(r.get('tijd', '')[11:16])}</td><td>{e(r.get('tekst', '').split('leeft:')[-1].strip())}</td></tr>"
                      for sp, r in sorted(steunpunten.items()))
    sp_html = (f"<table><tr><th>Steunpunt</th><th>Laatst</th><th>Stand</th></tr>{sp_html}</table>" if sp_html else
               "<p>Vandaag nog geen statusbericht van een steunpunt ontvangen (komt elke 30 minuten).</p>")
    disc = ", ".join(inst.get("disciplines") or []) + (" + meelezen" if inst.get("meelezen") else "")
    return f"""
<section><h2>Diensten</h2><p class="uitleg">Alles moet groen zijn.</p><table>{rijen}</table></section>
<section><h2>Vandaag</h2><div class="cijfers">
<div class="cijfer"><b>{mth_mij}</b><span>M/ETHANE voor deze post</span></div>
<div class="cijfer"><b>{mth - mth_mij}</b><span>M/ETHANE meegelezen</span></div>
<div class="cijfer"><b>{msg}</b><span>berichten</span></div></div>
<label>Deze post</label><div>{e(inst.get('roepnaam') or '— roepnaam niet ingesteld —')} &middot; {e(disc)}</div></section>
<section><h2>Steunpunten</h2>{sp_html}</section>
{radio.html_hotspot()}
<section><h2>Log van de ontvanger</h2><pre>{e(log_regels())}</pre></section>"""


def html_instellingen(inst, form=None):
    v = form or {}
    def w(k):
        if form is not None:
            return e(v.get(k, ""))
        x = inst.get(k)
        if isinstance(x, list):
            return e(", ".join(x))
        return e("" if x is None else str(x))
    gekozen = set(v.get("_disc", []) if form is not None else (inst.get("disciplines") or []))
    alle = "alle" in gekozen
    disc_html = f'<label class="vink"><input type="checkbox" name="disc_alle" {"checked" if alle else ""}><b>Alle meldingen</b> (centrale meldkamer)</label><br>'
    disc_html += "".join(f'<label class="vink"><input type="checkbox" name="disc_{k}" {"checked" if k in gekozen else ""}>{t}</label>'
                         for k, t in BEKENDE_DISCIPLINES)
    andere = ", ".join(x for x in gekozen if x not in dict(BEKENDE_DISCIPLINES) and x != "alle")
    if form is not None:
        andere = v.get("disc_andere", "")
    meelezen = (bool(v.get("meelezen")) if form is not None else bool(inst.get("meelezen")))
    logpos = (bool(v.get("log_posities")) if form is not None else bool(inst.get("log_posities", True)))
    return f"""<form method="post" action="/instellingen">{verborgen()}
<section><h2>Deze eindpost</h2>
<label>Naam <small>bijv. Brandweer Deventer, Gemeentehuis</small></label><input type="text" name="eindpost_naam" value="{w('eindpost_naam')}" required>
<label>Roepnaam op 2 m <small>met SSID; zo bevestigt deze post (ACK). Moet ook in het Netwerk van de steunpunten staan.</small></label>
<input type="text" name="roepnaam" value="{w('roepnaam')}" placeholder="PD3PAM-2" required></section>
<section><h2>Welke meldingen</h2><p class="uitleg">Meldingen voor deze disciplines worden getoond én bevestigd.
Zelfde namen als op het tabblad Netwerk van de steunpunten.</p>
{disc_html}
<label>Andere disciplines <small>met komma's, bijv. rodekruis</small></label><input type="text" name="disc_andere" value="{e(andere)}">
<label class="vink" style="margin-top:12px"><input type="checkbox" name="meelezen" {"checked" if meelezen else ""}>Meelezen: ook meldingen voor anderen tonen (niet bevestigen)</label>
<label>Alleen deze steunpunten <small>roepnamen met komma's; leeg = alle</small></label>
<input type="text" name="toegestane_steunpunten" value="{w('toegestane_steunpunten')}" placeholder="leeg = alle steunpunten"></section>
<section><h2>Logboek</h2><label class="vink"><input type="checkbox" name="log_posities" {"checked" if logpos else ""}>Ook posities van vrijwilligers in het logboek (CSV)</label></section>
<section><details><summary>MQTT (gevorderd)</summary><p class="uitleg">Standaard de broker op deze Pi zelf (127.0.0.1). Node-RED moet dezelfde gebruiken.</p>
<div class="rij"><div><label>Broker</label><input type="text" name="mqtt_broker" value="{w('mqtt_broker')}"></div>
<div><label>Poort</label><input type="number" name="mqtt_poort" value="{w('mqtt_poort')}"></div></div>
<div class="rij"><div><label>Gebruiker</label><input type="text" name="mqtt_gebruiker" value="{w('mqtt_gebruiker')}" autocomplete="off"></div>
<div><label>Wachtwoord</label><input type="text" name="mqtt_wachtwoord" value="{w('mqtt_wachtwoord')}" autocomplete="off"></div></div></details></section>
<div class="balk"><button type="submit">Opslaan en ontvanger herstarten</button></div></form>"""


def html_logboek(dag=None):
    lijst = dagen()
    if not lijst:
        return "<section><h2>Logboek</h2><p>Nog niets ontvangen.</p></section>"
    dag = dag if dag in lijst else lijst[0]
    keuze = "".join(f'<a class="knop" style="margin:2px;{"" if d == dag else "background:transparent;color:var(--blauw);border:1px solid var(--lijn)"}" href="/logboek?dag={d}">{d}</a>' for d in lijst[:14])
    try:
        tekst = open(os.path.join(LOGBOEK_DIR, dag + ".txt"), encoding="utf-8").read()
    except OSError:
        tekst = "(geen meldingen of berichten op deze dag)"
    return f"""<section><h2>Logboek</h2><p class="uitleg">Alles wat deze post ontvangen heeft, per dag. Het tekstbestand bevat de meldingen
en berichten; het CSV-bestand alles (ook status en posities) voor Excel of een kaart achteraf.</p>{keuze}</section>
<section><h2>{e(dag)}</h2><div class="balk" style="margin-top:0">
<a class="knop" href="/download/{dag}.csv">CSV downloaden</a> <a class="knop" style="background:transparent;color:var(--blauw);border:1px solid var(--lijn)" href="/download/{dag}.txt">Tekst downloaden</a></div>
<pre style="max-height:none">{e(tekst)}</pre></section>"""


# ---------------------------------------------------------------------------
# Controle
# ---------------------------------------------------------------------------

def controleer(f, oud):
    fouten = []
    inst = dict(oud)
    inst["eindpost_naam"] = " ".join(f.get("eindpost_naam", "").split())
    if not inst["eindpost_naam"]:
        fouten.append("Vul de naam van de eindpost in.")
    rn = f.get("roepnaam", "").strip().upper()
    if not ROEPNAAM_RE.match(rn):
        fouten.append("Roepnaam moet zijn als PD3PAM-2 (roepnaam, streepje, SSID 0-15).")
    inst["roepnaam"] = rn
    disc = ["alle"] if f.get("disc_alle") else []
    disc += [k for k, _ in BEKENDE_DISCIPLINES if f.get(f"disc_{k}")]
    disc += [re.sub(r"[^a-z0-9]+", "", x.lower()) for x in f.get("disc_andere", "").split(",") if x.strip()]
    disc = list(dict.fromkeys(x for x in disc if x))
    if not disc:
        fouten.append("Kies minstens één discipline (of 'Alle meldingen').")
    inst["disciplines"] = disc
    inst["meelezen"] = bool(f.get("meelezen"))
    inst["log_posities"] = bool(f.get("log_posities"))
    sp = [x.strip().upper() for x in re.split(r"[,\s]+", f.get("toegestane_steunpunten", "")) if x.strip()]
    for x in sp:
        if not ROEPNAAM_RE.match(x):
            fouten.append(f"'{x}' is geen geldige roepnaam van een steunpunt.")
    inst["toegestane_steunpunten"] = sp
    inst["mqtt_broker"] = f.get("mqtt_broker", "").strip() or "127.0.0.1"
    try:
        inst["mqtt_poort"] = int(f.get("mqtt_poort") or 1883)
    except ValueError:
        fouten.append("MQTT-poort moet een getal zijn.")
    inst["mqtt_gebruiker"] = f.get("mqtt_gebruiker", "").strip()
    inst["mqtt_wachtwoord"] = f.get("mqtt_wachtwoord", "").strip()
    return inst, fouten


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "NoodnetEindpost/1"

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
        self.send_header("WWW-Authenticate", 'Basic realm="Noodnet eindpost", charset="UTF-8"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("Inloggen vereist (gebruiker: beheer).".encode())
        return False

    def _stuur(self, data, code=200, soort="text/html; charset=utf-8", bestandsnaam=None):
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", soort)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        if bestandsnaam:
            self.send_header("Content-Disposition", f'attachment; filename="{bestandsnaam}"')
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
        q = parse_qs(url.query)
        m = q.get("m", [""])[0]
        inst = instellingen()
        meld = ""
        if m == "opgeslagen":
            meld = meldingen(ok="Opgeslagen. De ontvanger wordt herstart.")
        elif m == "herstart":
            meld = meldingen(ok="Dienst herstart.")
        elif m == "radio":
            meld = meldingen(ok="Radio-instellingen opgeslagen; Direwolf is herstart.")
        elif m.startswith("fout:"):
            meld = meldingen(fouten=[m[5:]])
        if pad == "scherm":
            host = (self.headers.get("Host") or "localhost").split(":")[0]
            self.send_response(302)
            self.send_header("Location", f"http://{host}:1880/ui")
            self.end_headers()
            return
        if pad.startswith("download/"):
            naam = pad.split("/", 1)[1]
            if DAG_RE.match(naam[:10]) and naam[10:] in (".csv", ".txt"):
                try:
                    data = open(os.path.join(LOGBOEK_DIR, naam), "rb").read()
                    soort = "text/csv; charset=utf-8" if naam.endswith(".csv") else "text/plain; charset=utf-8"
                    return self._stuur(data, soort=soort, bestandsnaam=f"{(inst.get('roepnaam') or 'eindpost')}_{naam}")
                except OSError:
                    pass
            return self._stuur("Niet gevonden", 404, "text/plain; charset=utf-8")
        if pad == "status":
            return self._stuur(pagina("status", html_status(inst), inst, meld))
        if pad == "instellingen":
            return self._stuur(pagina("instellingen", html_instellingen(inst), inst, meld))
        if pad == "logboek":
            return self._stuur(pagina("logboek", html_logboek(q.get("dag", [None])[0]), inst, meld))
        if pad == "radio":
            return self._stuur(pagina("radio", radio.html_radio("eindpost", verborgen()), inst, meld))
        self._stuur("Niet gevonden", 404, "text/plain; charset=utf-8")

    def _formulier(self):
        lengte = min(int(self.headers.get("Content-Length", 0) or 0), 100000)
        ruw = self.rfile.read(lengte).decode("utf-8", "replace")
        return {k: v[-1] for k, v in parse_qs(ruw, keep_blank_values=True).items()}

    def do_POST(self):
        if not self._auth():
            return
        f = self._formulier()
        if not hmac.compare_digest(f.get("csrf", ""), CSRF):
            return self._terug("/status", "fout:Formulier verlopen, probeer het opnieuw.")
        pad = urlparse(self.path).path.strip("/")
        inst = instellingen()
        if pad == "instellingen":
            nieuw, fouten = controleer(f, inst)
            if fouten:
                f["_disc"] = [k for k, _ in BEKENDE_DISCIPLINES if f.get(f"disc_{k}")] + (["alle"] if f.get("disc_alle") else [])
                return self._stuur(pagina("instellingen", html_instellingen(inst, f), inst, meldingen(fouten=fouten)))
            with SCHRIJF_LOCK:
                schrijf_json(INST_FILE, nieuw)
                if nieuw.get("roepnaam") != inst.get("roepnaam") and os.path.exists(radio.RADIO_FILE):
                    radio.maak_direwolf(nieuw["roepnaam"], radio.instellingen())
                    herstart("direwolf")
            ok, fout = herstart("noodnet-eindpost")
            return self._terug("/instellingen", "opgeslagen" if ok else "fout:Opgeslagen, maar herstart lukte niet: " + fout)
        if pad == "radio":
            fouten, diensten, r = radio.verwerk_radio("eindpost", f, inst.get("roepnaam"))
            if fouten:
                return self._stuur(pagina("radio", radio.html_radio("eindpost", verborgen(), dict(r, **f), fouten), inst))
            ok, fout = herstart("direwolf")
            return self._terug("/radio", "radio" if ok else "fout:Opgeslagen, maar Direwolf herstarten lukte niet: " + fout)
        if pad == "herstart":
            ok, fout = herstart(f.get("dienst", ""))
            return self._terug("/status", "herstart" if ok else "fout:Herstart lukte niet: " + fout)
        self._stuur("Niet gevonden", 404, "text/plain; charset=utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--poort", type=int, default=8080)
    ap.add_argument("--wachtwoord", action="store_true", help="wachtwoord instellen of wijzigen")
    args = ap.parse_args()
    if args.wachtwoord:
        return stel_wachtwoord_in()
    if not lees_json(WW_FILE):
        sys.exit("Stel eerst een wachtwoord in:  python eindpost_web.py --wachtwoord")
    server = ThreadingHTTPServer(("0.0.0.0", args.poort), Handler)
    print(f"Noodnet eindpost-beheer op http://0.0.0.0:{args.poort}  (gebruiker: beheer)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

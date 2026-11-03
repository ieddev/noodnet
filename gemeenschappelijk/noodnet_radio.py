"""
noodnet_radio.py - gedeeld door de beheerpagina's van steunpunt en eindpost.

  - geluidskaarten en seriële poorten van deze Pi vinden
  - direwolf.conf maken (geluidskaart, PTT, roepnaam)
  - ~/.reticulum/config maken voor de RNodes van een steunpunt
  - status van de wifi-hotspot en de netwerkkabel

Alleen standaard-Python. Bestanden met instellingen staan in de map van het
script (~/noodnet); de gemaakte configuraties worden overschreven, met eerst
een reservekopie.
"""

import glob
import html
import json
import os
import re
import subprocess
import time

e = html.escape

MAP = os.path.dirname(os.path.abspath(__file__))
RADIO_FILE = os.path.join(MAP, "radio_instellingen.json")
DIREWOLF_CONF = os.path.join(MAP, "direwolf.conf")
HOTSPOT_FILE = os.path.join(MAP, "hotspot.json")
RNS_CONFIG = os.path.expanduser(os.environ.get("NOODNET_RNS_CONFIG", "~/.reticulum/config"))
ASOUND_CARDS = os.environ.get("NOODNET_ASOUND_CARDS", "/proc/asound/cards")
SERIAL_BY_ID = os.environ.get("NOODNET_SERIAL_BY_ID", "/dev/serial/by-id")
NMCLI = os.environ.get("NOODNET_NMCLI", "nmcli")

STANDAARD = {"geluidskaart": "", "ptt_poort": "", "ptt_methode": "RTS",
             "rnode_433": "", "rnode_868": "", "txpower_433": 10, "txpower_868": 14}


def lees(pad, standaard=None):
    try:
        with open(pad, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return standaard


def schrijf(pad, data):
    tmp = pad + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, pad)


def instellingen():
    r = dict(STANDAARD)
    r.update(lees(RADIO_FILE, {}) or {})
    return r


def reservekopie(pad):
    if os.path.exists(pad):
        kopie = pad + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
        with open(pad, "rb") as a, open(kopie, "wb") as b:
            b.write(a.read())
        return kopie
    return None


# ---------------------------------------------------------------------------
# Hardware vinden
# ---------------------------------------------------------------------------

def geluidskaarten():
    """[(id, beschrijving)] uit /proc/asound/cards, USB-kaarten eerst."""
    uit = []
    try:
        for regel in open(ASOUND_CARDS, encoding="utf-8"):
            m = re.match(r"^\s*(\d+)\s+\[(\S+)\s*\]:\s*(.*)$", regel)
            if m:
                uit.append((m.group(2), m.group(3).strip()))
    except OSError:
        pass
    uit.sort(key=lambda k: (0 if "USB" in k[1] else 1, k[0]))
    return uit


def seriele_poorten():
    """[(pad, korte naam)] uit /dev/serial/by-id (blijft gelijk na herstart, anders dan ttyUSB0)."""
    uit = []
    for pad in sorted(glob.glob(os.path.join(SERIAL_BY_ID, "*"))):
        naam = os.path.basename(pad)
        kort = re.sub(r"^usb-", "", naam)
        kort = re.sub(r"_[0-9A-Fa-f]{6,}", "", kort)
        try:
            doel = os.path.basename(os.path.realpath(pad))
        except OSError:
            doel = ""
        if "if00" in naam:
            kort += "  [poort A]"
        elif "if01" in naam:
            kort += "  [poort B]"
        uit.append((pad, f"{kort}  ({doel})" if doel else kort))
    return uit


def raad_aan(kaarten, poorten):
    """Eerste voorstel: USB-geluidskaart en (bij Yaesu SCU-17 / Icom) de standaardpoort voor PTT."""
    kaart = next((k for k, b in kaarten if "USB" in b or "CODEC" in k.upper()), kaarten[0][0] if kaarten else "")
    ptt = ""
    for pad, _ in poorten:
        n = os.path.basename(pad).lower()
        if "ic-9700" in n or "ic9700" in n or "ic-7" in n:   # Icom: poort A (if00), menu USB SEND = USB (A) RTS
            if "if00" in n or not ptt:
                ptt = pad
            continue
        if "cp2105" in n and "if01" in n and not ptt:       # Yaesu SCU-17: tweede poort = PTT
            ptt = pad
    return kaart, ptt


# ---------------------------------------------------------------------------
# Configuratie maken
# ---------------------------------------------------------------------------

def maak_direwolf(roepnaam, r):
    kaart = r.get("geluidskaart") or "CODEC"
    ptt = ""
    if r.get("ptt_poort") and r.get("ptt_methode") in ("RTS", "DTR"):
        ptt = f"PTT {r['ptt_poort']} {r['ptt_methode']}"
    elif r.get("ptt_poort") and r.get("ptt_methode", "").startswith("CAT:"):
        model = r["ptt_methode"].split(":", 1)[1]
        ptt = f"PTT RIG {model} {r['ptt_poort']} 19200"
    tekst = f"""# Gemaakt door de Noodnet-beheerpagina ({time.strftime('%Y-%m-%d %H:%M')}).
# Wijzig via de beheerpagina (tabblad Radio); met de hand wijzigen wordt overschreven.
ADEVICE plughw:CARD={kaart},DEV=0
ACHANNELS 1
CHANNEL 0
MYCALL {roepnaam or 'N0CALL'}
MODEM 1200
{ptt or '# geen PTT ingesteld (VOX van de set)'}
TXDELAY 30
TXTAIL 10
DWAIT 0
SLOTTIME 10
PERSIST 63
KISSPORT 8001
AGWPORT 0
"""
    reservekopie(DIREWOLF_CONF)
    with open(DIREWOLF_CONF, "w", encoding="utf-8") as f:
        f.write(tekst)


def maak_reticulum(r, net):
    """Volledige ~/.reticulum/config voor een steunpunt: transport aan, alleen de RNodes."""
    lora = (net or {}).get("lora") or {}
    ifac = ((net or {}).get("ifac_netwerknaam") or "", (net or {}).get("ifac_wachtwoord") or "")
    delen = [f"""# Gemaakt door de Noodnet-beheerpagina ({time.strftime('%Y-%m-%d %H:%M')}).
# Wijzig via de beheerpagina (tabbladen Radio en Netwerk).

[reticulum]
  enable_transport = Yes
  share_instance = Yes
  panic_on_interface_error = No

[logging]
  loglevel = 4

[interfaces]
"""]
    for band, titel in (("433", "RNode 433 MHz"), ("868", "RNode 868 MHz")):
        poort = r.get(f"rnode_{band}")
        l = lora.get(band)
        if not poort or not l:
            continue
        blok = f"""  [[{titel}]]
    type = RNodeInterface
    enabled = Yes
    port = {poort}
    frequency = {l['frequentie']}
    bandwidth = {l['bandbreedte']}
    txpower = {int(r.get(f'txpower_{band}') or l.get('vermogen_dbm') or 10)}
    spreadingfactor = {l['sf']}
    codingrate = {l['cr']}
    airtime_limit_long = 10
    airtime_limit_short = 33
"""
        if any(ifac):
            blok += f"    network_name = {ifac[0]}\n    passphrase = {ifac[1]}\n"
        delen.append(blok + "\n")
    os.makedirs(os.path.dirname(RNS_CONFIG), exist_ok=True)
    reservekopie(RNS_CONFIG)
    with open(RNS_CONFIG, "w", encoding="utf-8") as f:
        f.write("".join(delen))


# ---------------------------------------------------------------------------
# Hotspot en netwerk
# ---------------------------------------------------------------------------

def _uit(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return ""


def hotspot_status():
    h = lees(HOTSPOT_FILE, {}) or {}
    actief = _uit([NMCLI, "-t", "-f", "NAME,TYPE,DEVICE", "con", "show", "--active"])
    aan = _uit(["systemctl", "is-active", "noodnet-ap"]).strip() == "active"
    clients = 0
    st = _uit(["iw", "dev", "wlan0", "station", "dump"])
    if st:
        clients = st.count("Station ")
    kabel = ""
    for r in actief.splitlines():
        delen = r.split(":")
        if len(delen) >= 3 and delen[1] == "802-3-ethernet":
            kabel = delen[2]
    internet = "dev" in _uit(["ip", "route", "get", "1.1.1.1"])
    return {"aan": aan, "ssid": h.get("ssid", ""), "wachtwoord": h.get("wachtwoord", ""),
            "adres": "10.42.0.1", "clients": clients, "kabel": kabel, "internet": internet}


def html_hotspot():
    h = hotspot_status()
    if h["aan"]:
        kop = f"<span class='punt p-ok'></span><b>Hotspot aan</b> &middot; {h['clients']} apparaat/apparaten verbonden"
    else:
        kop = ("<span class='punt p-let'></span><b>Hotspot staat nu uit</b> - de Pi gebruikt een ander netwerk "
               "(bijvoorbeeld je thuis-wifi tijdens installeren of bijwerken). Na een herstart, of zodra dat netwerk "
               "wegvalt, gaat de hotspot binnen een minuut vanzelf aan.")
    net = "via de netwerkkabel" if h["kabel"] and h["internet"] else ("geen" if not h["internet"] else "ja")
    return f"""<section><h2>Wifi-hotspot</h2><p>{kop}</p>
<div class="rij"><div><label>Netwerknaam</label><div class="mono">{e(h['ssid'] or '-')}</div></div>
<div><label>Wachtwoord</label><div class="mono">{e(h['wachtwoord'] or '-')}</div></div></div>
<div class="rij"><div><label>Beheerpagina via de hotspot</label><div class="mono">http://{h['adres']}:8080</div></div>
<div><label>Internet</label><div>{e(net)}</div></div></div>
<p class="uitleg" style="margin-top:10px">Android meldt bij de hotspot "geen internet": kies dan <i>Verbonden blijven</i>.</p></section>"""


# ---------------------------------------------------------------------------
# Testuitzending (PTT + geluid controleren)
# ---------------------------------------------------------------------------

def testuitzending(roepnaam, lang=False, wacht=None):
    """Laat Direwolf een kort testbericht op 2 m uitzenden. Direwolf zet daarvoor
    de PTT aan, dus dit test PTT en geluid in een keer. Geeft (gelukt, [regels])."""
    import socket
    import noodnet_proto as proto
    if not roepnaam or roepnaam.upper().startswith("N0CALL"):
        return False, ["Stel eerst je eigen roepnaam in."]
    if _uit(["systemctl", "is-active", "direwolf"]).strip() != "active":
        return False, ["Direwolf draait niet. Kies hieronder de geluidskaart en sla op."]
    tekst = f"Noodnet test {roepnaam.upper()} - geen actie nodig"
    frames = [tekst] if not lang else [f"{tekst} ({i}/4) " + "-" * 150 for i in range(1, 5)]
    begin = time.time()
    try:
        with socket.create_connection(("127.0.0.1", 8001), timeout=5) as s:
            for t in frames:
                s.sendall(proto.kiss_encode(proto.ax25_ui(roepnaam, "TEST", t)))
            time.sleep(0.5)
    except (OSError, ValueError) as fout:
        return False, [f"Geen verbinding met Direwolf (poort 8001): {fout}"]
    time.sleep(wacht if wacht is not None else (7 if lang else 3))
    log = _uit(["journalctl", "-u", "direwolf", "--no-pager", "-o", "cat",
                "--since", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(begin - 1))])
    regels = [r.strip() for r in log.splitlines() if ">TEST" in r or "PTT" in r or "rror" in r]
    return True, regels[-8:]


def html_testuitzending(verborgen, r=None):
    r = r or instellingen()
    ptt = "Er is geen PTT-poort gekozen: de set moet dan op VOX staan." if not r.get("ptt_poort") else ""
    return f"""<section id="test"><h2>Testuitzending</h2><p class="uitleg">De Pi zendt een kort testbericht uit op 2 m
(AX.25, met jouw roepnaam). Kijk of de set op <b>zenden</b> gaat. Luister op een tweede ontvanger: je hoort een kort
packet-geluid. Klinkt dat vervormd of heel zacht, dan staat het geluidsniveau niet goed.
<b>Lang</b> houdt de zender ongeveer 5 seconden aan, zodat je vermogen en SWR kunt aflezen.</p>
{f'<div class="melding let">{e(ptt)}</div>' if ptt else ''}
<form method="post" action="/radiotest" class="balk" style="margin-top:0">{verborgen}
<button type="submit" name="duur" value="kort">Testuitzending (1 s)</button>
<button type="submit" name="duur" value="lang" class="licht">Lang (5 s)</button></form></section>"""


def html_testuitslag(gelukt, regels):
    if not gelukt:
        return "".join(f'<div class="melding fout">{e(r)}</div>' for r in regels)
    uit = ('<div class="melding ok">Testbericht naar Direwolf gestuurd. Ging de set op zenden? '
           'Zo niet: controleer de PTT-poort en PTT-methode hieronder.</div>')
    if regels:
        uit += '<section><h2>Direwolf meldt</h2><pre class="mono" style="white-space:pre-wrap">' + \
               e("\n".join(regels)) + "</pre></section>"
    return uit


# ---------------------------------------------------------------------------
# Tabblad Radio
# ---------------------------------------------------------------------------

def html_radio(rol, verborgen, r=None, fouten=()):
    r = r or instellingen()
    kaarten = geluidskaarten()
    poorten = seriele_poorten()
    voorstel_kaart, voorstel_ptt = raad_aan(kaarten, poorten)
    kaart = r.get("geluidskaart") or voorstel_kaart
    ptt = r.get("ptt_poort") if r.get("ptt_poort") is not None and r.get("_opgeslagen") else (r.get("ptt_poort") or voorstel_ptt)

    def opties(lijst, gekozen, leeg=None):
        uit = f'<option value="">{e(leeg)}</option>' if leeg else ""
        for waarde, tekst in lijst:
            uit += f'<option value="{e(waarde)}" {"selected" if waarde == gekozen else ""}>{e(tekst)}</option>'
        if gekozen and gekozen not in [w for w, _ in lijst]:
            uit += f'<option value="{e(gekozen)}" selected>{e(gekozen)} (niet gevonden!)</option>'
        return uit

    kaart_opties = opties([(k, f"{k} - {b}") for k, b in kaarten], kaart, "- kies -")
    poort_opties = opties(poorten, ptt, "Geen PTT-poort (VOX)")
    methode = r.get("ptt_methode") or "RTS"
    methode_opties = opties([("RTS", "RTS (SCU-17, IC-9700 'USB SEND = RTS', Digirig)"),
                             ("DTR", "DTR"), ("CAT:3081", "CAT - Icom IC-9700"),
                             ("CAT:1020", "CAT - Yaesu FT-817/818")], methode)
    fout_html = "".join(f'<div class="melding fout">{e(f)}</div>' for f in fouten)
    rnode = ""
    if rol == "steunpunt":
        rnode = f"""<section><h2>RNodes (LoRa)</h2><p class="uitleg">Kies voor elke RNode de USB-poort. Frequentie, SF, BW, CR en IFAC
komen van het tabblad Netwerk; hier alleen de poort en het zendvermogen van de Pi zelf.</p>
<label>RNode 433 MHz</label><select name="rnode_433">{opties(poorten, r.get('rnode_433', ''), 'Niet aangesloten')}</select>
<label>Zendvermogen 433 <small>dBm; max 10 mW e.r.p.</small></label><input type="number" name="txpower_433" value="{e(str(r.get('txpower_433', 10)))}" min="0" max="10">
<label>RNode 868 MHz</label><select name="rnode_868">{opties(poorten, r.get('rnode_868', ''), 'Niet aangesloten')}</select>
<label>Zendvermogen 868 <small>dBm; max 500 mW e.r.p. op 869,525 MHz</small></label><input type="number" name="txpower_868" value="{e(str(r.get('txpower_868', 14)))}" min="0" max="27">
<p class="uitleg" style="margin-top:8px">Weet je niet welke poort welke RNode is? Trek er één uit, ververs de pagina en kijk welke verdwijnt.</p></section>"""
    geen = "" if poorten else "<div class='melding let'>Geen USB-seriële apparaten gevonden. Zijn de set en de RNodes aangesloten en aan?</div>"
    return f"""{fout_html}{geen}<form method="post" action="/radio">{verborgen}
<section><h2>2 m-transceiver (Direwolf)</h2><p class="uitleg">De roepnaam komt van het tabblad {'Steunpunt' if rol == 'steunpunt' else 'Instellingen'}.
Na opslaan wordt Direwolf opnieuw gestart.</p>
<label>Geluidskaart van de set</label><select name="geluidskaart">{kaart_opties}</select>
<label>PTT-poort</label><select name="ptt_poort">{poort_opties}</select>
<label>PTT-methode</label><select name="ptt_methode">{methode_opties}</select>
<p class="uitleg" style="margin-top:8px">FT-818 met SCU-17: poort B (if01) met RTS. IC-9700: in de set <i>MENU &gt; SET &gt; Connectors &gt; USB SEND</i> op <b>USB (A) RTS</b> zetten en hier poort A (if00) met RTS kiezen. Daarna de knop Testuitzending.</p></section>
{rnode}
<div class="balk"><button type="submit">Opslaan en herstarten</button></div></form>
{html_testuitzending(verborgen, r)}"""


def verwerk_radio(rol, f, roepnaam, net=None):
    """Slaat op en maakt de configuraties. Geeft (fouten, [diensten om te herstarten])."""
    r = instellingen()
    fouten = []
    r["geluidskaart"] = f.get("geluidskaart", "").strip()
    r["ptt_poort"] = f.get("ptt_poort", "").strip()
    r["ptt_methode"] = f.get("ptt_methode", "RTS")
    r["_opgeslagen"] = True
    if not r["geluidskaart"]:
        fouten.append("Kies de geluidskaart van de set.")
    herstart = ["direwolf"]
    if rol == "steunpunt":
        r["rnode_433"] = f.get("rnode_433", "").strip()
        r["rnode_868"] = f.get("rnode_868", "").strip()
        try:
            r["txpower_433"] = int(f.get("txpower_433") or 10)
            r["txpower_868"] = int(f.get("txpower_868") or 14)
        except ValueError:
            fouten.append("Zendvermogen moet een heel getal zijn.")
        if r["txpower_433"] > 10:
            fouten.append("433 MHz: maximaal 10 dBm (10 mW e.r.p.).")
        if r["txpower_868"] > 27:
            fouten.append("868 MHz: maximaal 27 dBm (500 mW e.r.p.).")
        gebruikt = [p for p in (r["rnode_433"], r["rnode_868"], r["ptt_poort"]) if p]
        if len(gebruikt) != len(set(gebruikt)):
            fouten.append("Dezelfde poort is twee keer gekozen.")
        if not (r["rnode_433"] or r["rnode_868"]):
            fouten.append("Kies minstens één RNode-poort.")
        herstart = ["direwolf", "rnsd", "noodnet-brug"]
    if fouten:
        return fouten, [], r
    schrijf(RADIO_FILE, r)
    maak_direwolf(roepnaam, r)
    if rol == "steunpunt":
        maak_reticulum(r, net)
    return [], herstart, r

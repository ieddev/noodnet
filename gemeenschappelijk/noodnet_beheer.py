"""
noodnet_beheer.py - gedeeld door de beheerpagina's: back-up/terugzetten en de klok.

Back-up: een zip met alles wat een Pi uniek maakt. Bij een steunpunt hoort daar
de SLEUTEL bij (gateway.id): daarmee houdt het steunpunt na een herinstallatie
hetzelfde adres, zodat kaarten en aanmeldingen geldig blijven.
"""

import email
import html
import email.policy
import io
import json
import os
import subprocess
import time
import zipfile

MAP = os.path.dirname(os.path.abspath(__file__))
LXMF_DIR = os.path.expanduser(os.environ.get("NOODNET_LXMF_DIR", "~/.reticulum/lxmf"))
SUDO = os.environ.get("NOODNET_SUDO", "sudo")
DATE = os.environ.get("NOODNET_DATE", "/usr/bin/date")
TIMEDATECTL = os.environ.get("NOODNET_TIMEDATECTL", "timedatectl")
TIJD_FILE = os.path.join(MAP, "tijd_gezet.json")
OPERATOR_FILE = os.path.join(MAP, "operator.json")
OPERATOR_LOG = os.path.join(MAP, "operators.csv")
OPERATORS_FILE = os.path.join(MAP, "operators.json")     # bekende operators voor de keuzelijst
SYSTEMCTL = os.environ.get("NOODNET_SYSTEMCTL", "systemctl")   # net als herstart(): sudo zoekt het pad

# (map in de zip, pad op de Pi)
BESTANDEN = {
    "steunpunt": [
        ("noodnet/steunpunt_instellingen.json", os.path.join(MAP, "steunpunt_instellingen.json")),
        ("noodnet/noodnet_netwerk.json", os.path.join(MAP, "noodnet_netwerk.json")),
        ("noodnet/radio_instellingen.json", os.path.join(MAP, "radio_instellingen.json")),
        ("noodnet/witte_lijst.txt", os.path.join(MAP, "witte_lijst.txt")),
        ("noodnet/onbekende_afzenders.txt", os.path.join(MAP, "onbekende_afzenders.txt")),
        ("noodnet/operator.json", OPERATOR_FILE),
        ("noodnet/operators.csv", OPERATOR_LOG),
        ("noodnet/operators.json", OPERATORS_FILE),
        ("lxmf/gateway.id", os.path.join(LXMF_DIR, "gateway.id")),
        ("lxmf/aanmeldingen.json", os.path.join(LXMF_DIR, "aanmeldingen.json")),
        ("lxmf/gehoord.json", os.path.join(LXMF_DIR, "gehoord.json")),
        ("lxmf/sender_names.json", os.path.join(LXMF_DIR, "sender_names.json")),
    ],
    "eindpost": [
        ("noodnet/eindpost_instellingen.json", os.path.join(MAP, "eindpost_instellingen.json")),
        ("noodnet/radio_instellingen.json", os.path.join(MAP, "radio_instellingen.json")),
        ("noodnet/meldkamer_ontvangen.json", os.path.join(MAP, "meldkamer_ontvangen.json")),
        ("noodnet/operator.json", OPERATOR_FILE),
        ("noodnet/operators.csv", OPERATOR_LOG),
        ("noodnet/operators.json", OPERATORS_FILE),
    ],
}


def maak_backup(rol, roepnaam=""):
    """Geeft (bytes van de zip, bestandsnaam)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        info = {"rol": rol, "roepnaam": roepnaam, "gemaakt": time.strftime("%Y-%m-%d %H:%M"), "bestanden": []}
        for naam, pad in BESTANDEN.get(rol, []):
            if os.path.exists(pad):
                z.write(pad, naam)
                info["bestanden"].append(naam)
        if rol == "eindpost":
            logboek = os.path.join(MAP, "logboek")
            if os.path.isdir(logboek):
                for f in sorted(os.listdir(logboek)):
                    z.write(os.path.join(logboek, f), "noodnet/logboek/" + f)
                    info["bestanden"].append("noodnet/logboek/" + f)
        z.writestr("noodnet_backup.json", json.dumps(info, ensure_ascii=False, indent=2))
    naam = f"noodnet-backup-{rol}-{roepnaam or 'pi'}-{time.strftime('%Y%m%d-%H%M')}.zip"
    return buf.getvalue(), naam


def lees_upload(content_type, body, veld="bestand"):
    """Haalt een geüpload bestand uit een multipart/form-data-verzoek. Geeft (bytes, velden)."""
    msg = email.message_from_bytes(b"Content-Type: " + content_type.encode() + b"\r\n\r\n" + body,
                                   policy=email.policy.HTTP)
    data, velden = None, {}
    for deel in msg.iter_parts():
        naam = deel.get_param("name", header="content-disposition")
        if naam == veld:
            data = deel.get_payload(decode=True)
        elif naam:
            velden[naam] = (deel.get_payload(decode=True) or b"").decode("utf-8", "replace")
    return data, velden


def zet_terug(rol, data):
    """Zet een back-up terug. Geeft (gelukt, [meldingen])."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        info = json.loads(z.read("noodnet_backup.json"))
    except Exception:
        return False, ["Dit is geen Noodnet-back-up (zip met noodnet_backup.json)."]
    if info.get("rol") != rol:
        return False, [f"Deze back-up is van een {info.get('rol')}, deze Pi is een {rol}."]
    toegestaan = dict(BESTANDEN.get(rol, []))
    meld = [f"Back-up van {info.get('roepnaam') or '?'}, gemaakt {info.get('gemaakt')}."]
    for naam in z.namelist():
        if naam in toegestaan:
            doel = toegestaan[naam]
        elif rol == "eindpost" and naam.startswith("noodnet/logboek/") and "/" not in naam[16:] and naam[16:]:
            doel = os.path.join(MAP, "logboek", naam[16:])
        else:
            continue
        os.makedirs(os.path.dirname(doel), exist_ok=True)
        if os.path.exists(doel):
            os.replace(doel, doel + ".voor-terugzetten")
        with open(doel, "wb") as f:
            f.write(z.read(naam))
        if doel.endswith("gateway.id"):
            os.chmod(doel, 0o600)
            meld.append("Sleutel van het steunpunt teruggezet: het adres is weer hetzelfde, oude kaarten blijven geldig.")
    return True, meld


# ---------------------------------------------------------------------------
# Klok
# ---------------------------------------------------------------------------

def tijd_gesynchroniseerd():
    try:
        r = subprocess.run([TIMEDATECTL, "show", "-p", "NTPSynchronized", "--value"],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip() == "yes"
    except Exception:
        return False


def tijd_van_telefoon(ms):
    """Zet de klok van de Pi gelijk aan de telefoon als de Pi geen internettijd heeft
    en meer dan 60 s afwijkt. Geeft een korte tekst voor het log, of None."""
    try:
        telefoon = float(ms) / 1000.0
    except (TypeError, ValueError):
        return None
    if telefoon < 1.7e9:                     # onzin of voor 2023: negeren
        return None
    verschil = telefoon - time.time()
    if abs(verschil) < 60 or tijd_gesynchroniseerd():
        return None
    try:
        r = subprocess.run([SUDO, "-n", DATE, "-s", f"@{int(telefoon)}"], capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return "Klok zetten lukte niet: " + (r.stderr or r.stdout).strip()[:120]
    except Exception as e:
        return "Klok zetten lukte niet: " + str(e)
    with open(TIJD_FILE, "w", encoding="utf-8") as f:
        json.dump({"gezet": time.time(), "verschil_s": round(verschil)}, f)
    return f"Klok gelijkgezet met de telefoon (verschil {round(verschil)} s)"


def tijd_tekst():
    if tijd_gesynchroniseerd():
        bron = "internet (NTP)"
    else:
        try:
            t = json.load(open(TIJD_FILE, encoding="utf-8"))
            bron = "gelijkgezet met de telefoon van de beheerder om " + time.strftime("%H:%M", time.localtime(t["gezet"])) + \
                   ("" if time.strftime("%d-%m") == time.strftime("%d-%m", time.localtime(t["gezet"]))
                    else " op " + time.strftime("%d-%m", time.localtime(t["gezet"])))
        except (OSError, ValueError, KeyError):
            bron = "onzeker - open deze pagina op je telefoon, dan wordt de klok gelijkgezet"
    return time.strftime("%d-%m-%Y %H:%M"), bron


TIJD_SCRIPT = """<script>
try{fetch('/tijd',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
body:'csrf='+encodeURIComponent('%s')+'&ms='+Date.now()}).then(function(r){return r.text()}).then(function(t){
if(t&&t!=='ok'){var d=document.createElement('div');d.className='melding ok';d.textContent=t;
var m=document.querySelector('main');if(m)m.insertBefore(d,m.firstChild);}});}catch(e){}
</script>"""


def html_backup(rol, verborgen):
    sleutel = ("<p class='uitleg'><b>Let op:</b> in de back-up zit de <b>sleutel</b> van dit steunpunt. Bewaar hem veilig "
               "(niet mailen of delen). Met de sleutel houdt het steunpunt na een herinstallatie hetzelfde adres, "
               "zodat de kaarten en aanmeldingen geldig blijven.</p>") if rol == "steunpunt" else \
              "<p class='uitleg'>Met instellingen en het hele logboek.</p>"
    return f"""<section><h2>Back-up</h2>{sleutel}
<div class="balk" style="margin-top:0"><a class="knop" href="/backup.zip">Back-up downloaden</a></div></section>
<section><h2>Terugzetten</h2><p class="uitleg">Bijvoorbeeld na een nieuwe SD-kaart. Bestaande bestanden worden eerst
bewaard als <span class="mono">.voor-terugzetten</span>. Daarna worden de diensten herstart.</p>
<form method="post" action="/terugzetten" enctype="multipart/form-data">{verborgen}
<input type="file" name="bestand" accept=".zip" required style="margin:8px 0">
<div class="balk"><button type="submit" class="gevaar" onclick="return confirm('Back-up terugzetten en diensten herstarten?')">Terugzetten</button></div></form></section>"""


# ---------------------------------------------------------------------------
# Pi uitschakelen / herstarten
# ---------------------------------------------------------------------------

def html_pi_knoppen(verborgen):
    return f"""<section><h2>Raspberry Pi</h2><p class="uitleg">Haal nooit zomaar de stroom eraf: dan kan de SD-kaart
beschadigen. Schakel de Pi hier eerst uit en wacht tot het groene lampje niet meer knippert (± 20 seconden).</p>
<form method="post" action="/pi" class="balk" style="margin-top:0">{verborgen}
<button type="submit" name="actie" value="uit" class="gevaar" onclick="return confirm('Pi uitschakelen? Alles stopt. Daarna pas de stroom eraf halen.')">Pi uitschakelen</button>
<button type="submit" name="actie" value="herstart" class="licht" onclick="return confirm('Pi herstarten? Duurt ongeveer 2 minuten.')">Pi herstarten</button></form></section>"""


def pi_actie(actie):
    """Schakelt de Pi uit of herstart hem, 2 s na het antwoord aan de browser. Geeft html of None."""
    if actie not in ("uit", "herstart"):
        return None
    import threading

    def later():
        time.sleep(2)
        subprocess.run([SUDO, "-n", SYSTEMCTL, "poweroff" if actie == "uit" else "reboot"],
                       capture_output=True, timeout=30)
    threading.Thread(target=later, daemon=True).start()
    if actie == "uit":
        kop, tekst = "De Pi wordt uitgeschakeld", ("Wacht tot het groene lampje op de Pi niet meer knippert "
                                                   "(ongeveer 20 seconden). Daarna mag de stroom eraf.")
    else:
        kop, tekst = "De Pi wordt herstart", ("Over ongeveer 2 minuten is alles weer actief. "
                                              "Verbind daarna opnieuw met de hotspot en open deze pagina.")
    return f"""<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{kop}</title>
<style>body{{font-family:Arial,sans-serif;margin:0;padding:32px 16px;background:#f4f5f7;color:#1b1f24;text-align:center}}
h1{{font-size:24px}}p{{font-size:18px;max-width:520px;margin:12px auto}}</style></head>
<body><h1>{kop}</h1><p>{tekst}</p></body></html>"""


# ---------------------------------------------------------------------------
# Dienstdoende operator
# ---------------------------------------------------------------------------

import re as _re

ROEPNAAM_RE = _re.compile(r"^[A-Z0-9]{3,6}$")


def operator():
    """{'roepnaam', 'naam', 'sinds'} of {}."""
    try:
        with open(OPERATOR_FILE, encoding="utf-8") as f:
            o = json.load(f)
        return o if o.get("roepnaam") else {}
    except (OSError, ValueError):
        return {}


def operator_tekst(o=None):
    o = operator() if o is None else o
    if not o:
        return ""
    return o["roepnaam"] + (f" ({o['naam']})" if o.get("naam") else "")


def bekende_operators():
    """[{'roepnaam', 'naam'}], gesorteerd op roepnaam."""
    try:
        with open(OPERATORS_FILE, encoding="utf-8") as f:
            lijst = [o for o in json.load(f) if isinstance(o, dict) and ROEPNAAM_RE.match(o.get("roepnaam", ""))]
    except (OSError, ValueError, TypeError):
        lijst = []
    return sorted(lijst, key=lambda o: o["roepnaam"])


def _schrijf_operators(lijst):
    tmp = OPERATORS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sorted(lijst, key=lambda o: o["roepnaam"]), f, ensure_ascii=False, indent=1)
    os.replace(tmp, OPERATORS_FILE)


def _schoon(roepnaam, naam):
    roepnaam = (roepnaam or "").strip().upper().split("-")[0]   # SSID hoort bij het station, niet bij de operator
    naam = " ".join((naam or "").replace(";", " ").split())[:40]
    return roepnaam, naam


def voeg_operator_toe(roepnaam, naam=""):
    roepnaam, naam = _schoon(roepnaam, naam)
    if not ROEPNAAM_RE.match(roepnaam):
        return False, "Vul een roepnaam in, bijvoorbeeld PD3PAM."
    lijst = [o for o in bekende_operators() if o["roepnaam"] != roepnaam]
    oud = next((o for o in bekende_operators() if o["roepnaam"] == roepnaam), None)
    lijst.append({"roepnaam": roepnaam, "naam": naam or (oud or {}).get("naam", "")})
    _schrijf_operators(lijst)
    return True, f"{roepnaam} staat in de lijst met operators."


def verwijder_operator(roepnaam):
    roepnaam, _ = _schoon(roepnaam, "")
    if operator().get("roepnaam") == roepnaam:
        return False, f"{roepnaam} heeft nu dienst; laat eerst iemand anders de dienst overnemen."
    _schrijf_operators([o for o in bekende_operators() if o["roepnaam"] != roepnaam])
    return True, f"{roepnaam} uit de lijst met operators gehaald."


def zet_operator(roepnaam, naam=None):
    """Maakt roepnaam dienstdoende operator. Naam None: uit de lijst. Geeft (gelukt, melding, vorige)."""
    roepnaam, naam = _schoon(roepnaam, naam)
    if not ROEPNAAM_RE.match(roepnaam):
        return False, "Kies een operator, of voeg je eigen roepnaam toe.", {}
    bekend = next((o for o in bekende_operators() if o["roepnaam"] == roepnaam), None)
    if not naam and bekend:
        naam = bekend.get("naam", "")
    if not bekend or (naam and bekend.get("naam") != naam):
        voeg_operator_toe(roepnaam, naam)
    vorige = operator()
    if vorige.get("roepnaam") == roepnaam:
        return True, f"{operator_tekst(vorige)} had al dienst.", {"zelfde": True}
    nu = time.time()
    o = {"roepnaam": roepnaam, "naam": naam, "sinds": nu}
    tmp = OPERATOR_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=False)
    os.replace(tmp, OPERATOR_FILE)
    nieuw = not os.path.exists(OPERATOR_LOG)
    with open(OPERATOR_LOG, "a", encoding="utf-8") as f:
        if nieuw:
            f.write("tijd;roepnaam;naam;vorige\n")
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(nu))};{roepnaam};{naam};"
                f"{vorige.get('roepnaam', '')}\n")
    return True, f"Dienstdoende operator is nu {operator_tekst(o)}.", vorige


def verwerk_operator(f):
    """Formulier van het blok Dienstdoende operator. Geeft (gelukt, melding, vorige of None als er niet gewisseld is)."""
    actie = f.get("actie", "kies")
    if actie == "verwijder":
        ok, tekst = verwijder_operator(f.get("roepnaam"))
        return ok, tekst, None
    if actie == "nieuw":
        ok, tekst, vorige = zet_operator(f.get("roepnaam"), f.get("naam", ""))
    else:
        ok, tekst, vorige = zet_operator(f.get("roepnaam"))
    if not ok or vorige.get("zelfde"):
        return ok, tekst, None
    return ok, tekst, vorige


def operator_geschiedenis(n=10):
    try:
        with open(OPERATOR_LOG, encoding="utf-8") as f:
            regels = [r.rstrip("\n").split(";") for r in f.readlines()[1:] if r.strip()]
    except OSError:
        return []
    return regels[-n:][::-1]


def html_operator(verborgen):
    o = operator()
    bekend = bekende_operators()
    if o:
        huidig = (f"<b style='font-size:20px'>{html.escape(operator_tekst(o))}</b> "
                  f"<small style='color:var(--zacht)'>sinds {time.strftime('%d-%m %H:%M', time.localtime(o['sinds']))}</small>")
    else:
        huidig = "<span style='color:var(--oranje)'><b>Nog niemand.</b> Kies of voeg toe wie dienst heeft.</span>"
    opties = "".join(f'<option value="{html.escape(b["roepnaam"])}"{" selected" if b["roepnaam"] == o.get("roepnaam") else ""}>'
                     f'{html.escape(operator_tekst(b))}</option>' for b in bekend)
    kies = (f"""<form method="post" action="/operator" style="display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 0">{verborgen}
<input type="hidden" name="actie" value="kies"><select name="roepnaam" style="flex:1;min-width:180px">{opties}</select>
<button type="submit">Dienst overnemen</button></form>""" if bekend else "")
    nieuw = f"""<details{'' if bekend else ' open'} style="margin-top:8px"><summary>Nieuwe operator toevoegen</summary>
<form method="post" action="/operator" style="margin-top:6px">{verborgen}<input type="hidden" name="actie" value="nieuw">
<div style="display:flex;gap:8px;flex-wrap:wrap"><input name="roepnaam" placeholder="Roepnaam, bijv. PD3PAM" required
style="flex:1;min-width:150px;text-transform:uppercase" autocapitalize="characters">
<input name="naam" placeholder="Naam (mag leeg)" style="flex:1;min-width:150px">
<button type="submit">Toevoegen en dienst overnemen</button></div></form></details>"""
    beheren = ""
    if bekend:
        rijen = "".join(f"""<tr><td>{html.escape(operator_tekst(b))}</td><td style="text-align:right">
<form method="post" action="/operator" style="margin:0">{verborgen}<input type="hidden" name="actie" value="verwijder">
<input type="hidden" name="roepnaam" value="{html.escape(b['roepnaam'])}"><button type="submit" class="licht"
style="padding:4px 10px;font-size:14px">Uit de lijst</button></form></td></tr>""" for b in bekend)
        beheren = f"<details style='margin-top:6px'><summary>Operators beheren</summary><table>{rijen}</table></details>"
    gesch = operator_geschiedenis()
    wissels = ""
    if gesch:
        rijen = "".join(f"<tr><td class='mono'>{html.escape(r[0][5:16] if len(r[0]) >= 16 else r[0])}</td>"
                        f"<td>{html.escape(r[1])}{(' (' + html.escape(r[2]) + ')') if len(r) > 2 and r[2] else ''}</td></tr>"
                        for r in gesch)
        wissels = (f"<details style='margin-top:6px'><summary>Wissels bekijken</summary><table><tr><th>Vanaf</th>"
                   f"<th>Operator</th></tr>{rijen}</table><p class='uitleg'>Alle wissels staan in operators.csv en in "
                   f"het log/logboek.</p></details>")
    return f"""<section><h2>Dienstdoende operator</h2><div>{huidig}</div>{kies}{nieuw}{beheren}{wissels}
<p class="uitleg" style="margin-top:8px">Het station zendt altijd onder zijn eigen roepnaam. Hier leg je vast wie er
verantwoordelijk is; elke wissel wordt met tijd vastgelegd.</p></section>"""

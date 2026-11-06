"""
noodnet_rig.py - besturing van de 2 m-set via hamlib (rigctld), gedeeld door steunpunt en eindpost.

  rigctld (dienst noodnet-rigctld) is de enige die de CAT-poort opent. Direwolf (PTT RIG 2
  localhost:4532) en de beheerpagina praten via TCP met rigctld.

  - doelfrequentie: tabblad Netwerk (steunpunt) of Instellingen (eindpost)
  - set instellen: frequentie, datamode (PKTFM / FM-D), zendvermogen
  - bewaker: zet de set terug als iemand eraan draait (niet tijdens zenden)
  - Zoek mijn set: probeert bekende modellen/snelheden op de USB-poorten

Alleen standaard-Python.
"""

import json
import os
import re
import socket
import subprocess
import threading
import time

MAP = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(MAP, "rigctld.env")
LOG_FILE = os.path.join(MAP, "rig_log.json")
NET_FILE = os.path.join(MAP, "noodnet_netwerk.json")
EINDPOST_FILE = os.path.join(MAP, "eindpost_instellingen.json")
RIGCTL = os.environ.get("NOODNET_RIGCTL", "rigctl")
HOST, POORT = "127.0.0.1", int(os.environ.get("NOODNET_RIGCTLD_POORT", "4532"))

STANDAARD_FREQ = 144925000
PAKKET_MODES = {"PKTFM", "FM-D", "FMD", "DATA-FM", "FM-DATA"}

# (hamlib-nummer, merk, model, snelheden om te proberen). Gecontroleerd met Hamlib 4.5 (rigctl -l).
MODELLEN = [
    (3081, "Icom", "IC-9700", [115200, 19200, 9600]),
    (3085, "Icom", "IC-705", [115200, 19200, 9600]),
    (3070, "Icom", "IC-7100", [19200, 115200, 9600]),
    (3068, "Icom", "IC-9100", [19200, 115200, 9600]),
    (3044, "Icom", "IC-910", [19200, 9600]),
    (3071, "Icom", "ID-5100", [19200, 9600]),
    (1035, "Yaesu", "FT-991 / FT-991A", [38400, 9600, 4800]),
    (1041, "Yaesu", "FT-818", [38400, 9600, 4800]),
    (1020, "Yaesu", "FT-817", [38400, 9600, 4800]),
    (1022, "Yaesu", "FT-857", [38400, 9600, 4800]),
    (1043, "Yaesu", "FT-897D", [38400, 9600, 4800]),
    (1023, "Yaesu", "FT-897", [38400, 9600, 4800]),
    (1001, "Yaesu", "FT-847", [57600, 9600, 4800]),
    (2014, "Kenwood", "TS-2000", [57600, 9600, 38400]),
    (2034, "Kenwood", "TM-D710", [57600, 9600]),
    (2035, "Kenwood", "TM-V71", [57600, 9600]),
    (2042, "Kenwood", "TH-D74", [9600, 57600]),
    (2007, "Kenwood", "TS-790", [4800, 9600]),
]
MODEL_NAAM = {m: f"{merk} {naam}" for m, merk, naam, _ in MODELLEN}
SNELHEDEN = [4800, 9600, 19200, 38400, 57600, 115200]


# ---------------------------------------------------------------------------
# Instellingen
# ---------------------------------------------------------------------------

def _lees(pad):
    try:
        with open(pad, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def doelfrequentie():
    """2 m-frequentie van de gemeente in Hz (Netwerk op een steunpunt, Instellingen op een eindpost)."""
    for pad in (NET_FILE, EINDPOST_FILE):
        d = _lees(pad)
        if isinstance(d, dict) and d.get("frequentie_2m"):
            try:
                return int(d["frequentie_2m"])
            except (TypeError, ValueError):
                pass
    return STANDAARD_FREQ


def mhz(hz):
    return f"{hz / 1e6:.3f}".replace(".", ",") + " MHz"


def controleer_frequentie(tekst):
    """Tekst in MHz -> (Hz, [fouten], [waarschuwingen])."""
    try:
        hz = int(round(float(str(tekst).replace(",", ".").strip()) * 1e6))
    except (TypeError, ValueError):
        return None, ["2 m-frequentie: vul een getal in MHz in, bijvoorbeeld 144.925."], []
    if not 144000000 <= hz <= 146000000:
        return None, [f"2 m-frequentie: {mhz(hz)} ligt buiten de 2 m-band (144-146 MHz)."], []
    let = []
    if abs(hz - 144800000) < 12500:
        let.append("144,800 MHz is de APRS-frequentie: kies een andere.")
    elif not 144794000 <= hz <= 144990000:
        let.append(f"{mhz(hz)} ligt buiten het segment voor digitale modes (144,794-144,990 MHz) van het IARU-bandplan.")
    return hz, [], let


def cat_actief(r):
    return r.get("ptt_methode") == "CAT" and r.get("cat_model") and r.get("cat_poort")


def schrijf_env(r):
    """rigctld.env voor de dienst noodnet-rigctld; zonder CAT wordt het bestand verwijderd (dienst wacht dan)."""
    if cat_actief(r):
        tmp = ENV_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(f"MODEL={int(r['cat_model'])}\nPOORT={r['cat_poort']}\nBAUD={int(r.get('cat_baud') or 19200)}\n")
        os.replace(tmp, ENV_FILE)
    elif os.path.exists(ENV_FILE):
        os.remove(ENV_FILE)


# ---------------------------------------------------------------------------
# Praten met rigctld
# ---------------------------------------------------------------------------

def opdracht(cmd, timeout=4):
    """Stuurt één opdracht in het uitgebreide protocol (+). Geeft (ok, [regels])."""
    try:
        with socket.create_connection((HOST, POORT), timeout=timeout) as s:
            s.sendall(("+" + cmd + "\n").encode())
            data = b""
            eind = time.time() + timeout
            while time.time() < eind:
                try:
                    x = s.recv(4096)
                except socket.timeout:
                    break
                if not x:
                    break
                data += x
                if re.search(rb"RPRT -?\d+", data):
                    break
    except OSError as fout:
        return False, [f"geen verbinding met rigctld: {fout}"]
    regels = data.decode(errors="replace").strip().splitlines()
    m = re.search(r"RPRT (-?\d+)", regels[-1]) if regels else None
    return bool(m and m.group(1) == "0"), regels[1:-1] if m else regels


def _waarde(regels, sleutel=None):
    for r in regels:
        if sleutel and r.startswith(sleutel + ":"):
            return r.split(":", 1)[1].strip()
    return regels[0].strip() if regels and not sleutel else None


def status():
    """Live gegevens van de set. Geeft dict; 'fout' als rigctld niet antwoordt."""
    ok, f = opdracht("f")
    if not ok:
        return {"fout": "; ".join(f) or "geen antwoord van de set"}
    uit = {}
    try:
        uit["frequentie"] = int(float(_waarde(f, "Frequency")))
    except (TypeError, ValueError):
        return {"fout": "onverwacht antwoord: " + " ".join(f)}
    ok, m = opdracht("m")
    if ok:
        uit["mode"] = _waarde(m, "Mode")
    ok, t = opdracht("t")
    if ok:
        uit["ptt"] = _waarde(t, "PTT") == "1"
    for niveau, sleutel in (("STRENGTH", "s"), ("RFPOWER", "vermogen")):
        ok, v = opdracht("l " + niveau)
        if ok and v:
            try:
                uit[sleutel] = float(v[-1])
            except ValueError:
                pass
    return uit


def s_meter(db):
    """hamlib STRENGTH (dB t.o.v. S9) -> 'S7' of 'S9+10'."""
    if db is None:
        return "–"
    if db >= 0:
        return f"S9+{int(round(db / 10) * 10)}" if db >= 5 else "S9"
    return f"S{max(0, 9 + int(round(db / 6)))}"


def zet_set(r, freq=None):
    """Zet frequentie, datamode en (optioneel) vermogen. Geeft [meldingen]."""
    freq = freq or doelfrequentie()
    meld = []
    ok, t = opdracht("t")
    if ok and _waarde(t, "PTT") == "1":
        return ["De set zendt nu; probeer het zo opnieuw."]
    ok, uit = opdracht(f"F {freq}")
    if not ok:
        return ["Frequentie zetten lukte niet: " + " ".join(uit)]
    mode = r.get("cat_mode") or "PKTFM"
    ok, uit = opdracht(f"M {mode} 0")
    if not ok and mode != "FM":
        ok, uit = opdracht("M FM 0")
        if ok:
            meld.append("Deze set kent geen datamode via CAT; FM gekozen. Controleer of het geluid van USB komt.")
    if not ok:
        meld.append("Mode zetten lukte niet: " + " ".join(uit))
    if r.get("cat_vermogen"):
        ok, uit = opdracht(f"L RFPOWER {int(r['cat_vermogen']) / 100:.2f}")
        if not ok:
            meld.append("Vermogen zetten lukte niet (niet elke set kan dat via CAT).")
    return meld


def log(tekst):
    regels = _lees(LOG_FILE) or []
    regels.append([time.strftime("%d-%m %H:%M:%S"), tekst])
    tmp = LOG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(regels[-30:], f, ensure_ascii=False)
    os.replace(tmp, LOG_FILE)


def logregels(n=8):
    return (_lees(LOG_FILE) or [])[-n:][::-1]


def bewaak(r):
    """Staat de set niet (meer) op de gemeentefrequentie en datamode? Dan terugzetten. Geeft tekst of None."""
    if not cat_actief(r):
        return None
    st = status()
    if "fout" in st:
        return None
    if st.get("ptt"):
        return None
    doel = doelfrequentie()
    mode_goed = (st.get("mode") or "").upper() in PAKKET_MODES or (r.get("cat_mode") == "FM" and st.get("mode") == "FM")
    if abs(st["frequentie"] - doel) <= 100 and mode_goed:
        return None
    was = f"{mhz(st['frequentie'])} {st.get('mode') or '?'}"
    meld = zet_set(r, doel)
    tekst = f"Set stond op {was}; teruggezet naar {mhz(doel)}" + (f" ({'; '.join(meld)})" if meld else "")
    log(tekst)
    return tekst


def start_bewaker(lees_instellingen, schrijf_log=None, interval=60):
    """Achtergrondtaak in de beheerpagina: elke minuut controleren."""
    def lus():
        time.sleep(20)
        while True:
            try:
                uit = bewaak(lees_instellingen())
                if uit and schrijf_log:
                    schrijf_log(uit)
            except Exception as fout:        # nooit de beheerpagina laten vallen
                if schrijf_log:
                    schrijf_log(f"bewaker set: {fout}")
            time.sleep(interval)
    threading.Thread(target=lus, daemon=True, name="rig-bewaker").start()


# ---------------------------------------------------------------------------
# Zoek mijn set
# ---------------------------------------------------------------------------

def kandidaten(poortnaam):
    """Modellen om te proberen voor een USB-poort, op basis van de naam."""
    n = poortnaam.lower()
    for m, merk, naam, _ in MODELLEN:
        kern = naam.split()[0].lower()
        if kern in n or kern.replace("-", "") in n:
            return [m]
    if "cp2105" in n:                                     # Yaesu SCU-17 (FT-817/818) of FT-991 (Enhanced COM)
        return [1041, 1020, 1035, 1022, 1023]
    if "silicon_labs" in n or "cp210" in n:               # Icom-sets met ingebouwde USB
        return [3081, 3085, 3070, 3068, 3044]
    return [m for m, *_ in MODELLEN]


def probeer(model, poort, baud, timeout=4):
    """rigctl -m model -r poort -s baud f -> frequentie in Hz of None."""
    try:
        r = subprocess.run([RIGCTL, "-m", str(model), "-r", poort, "-s", str(baud),
                            "-C", "timeout=500,retry=0", "f"], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    try:
        hz = int(float(r.stdout.strip().splitlines()[0]))
    except (ValueError, IndexError):
        return None
    return hz if 1000000 <= hz <= 10000000000 else None


def zoek(poorten, max_seconden=90):
    """poorten: [(pad, label)]. Geeft (gevonden [(pad, model, baud, freq)], [meldingen])."""
    gevonden, meld, begin = [], [], time.time()
    snelheden = {m: b for m, _, _, b in MODELLEN}
    for pad, _ in poorten:
        for model in kandidaten(os.path.basename(pad)):
            for baud in snelheden.get(model, [19200, 9600]):
                if time.time() - begin > max_seconden:
                    meld.append("Zoeken gestopt na anderhalve minuut; kies de set eventueel zelf in de lijst.")
                    return gevonden, meld
                hz = probeer(model, pad, baud)
                if hz:
                    gevonden.append((pad, model, baud, hz))
                    break
            if gevonden and gevonden[-1][0] == pad:
                break
    return gevonden, meld


def wacht_en_zet(max_s=25):
    """Door direwolf.service bij het starten: bij CAT wachten tot rigctld antwoordt, dan de set instellen."""
    r = _lees(os.path.join(MAP, "radio_instellingen.json")) or {}
    if not cat_actief(r):
        return "geen CAT"
    eind = time.time() + max_s
    while time.time() < eind:
        ok, _ = opdracht("f", timeout=2)
        if ok:
            meld = zet_set(r)
            tekst = f"Set ingesteld op {mhz(doelfrequentie())}" + (f" ({'; '.join(meld)})" if meld else "")
            log(tekst)
            return tekst
        time.sleep(1)
    log("rigctld antwoordt niet: is de set aan en klopt de CAT-poort?")
    return "rigctld antwoordt niet"


if __name__ == "__main__":
    import sys
    if "--status" in sys.argv:
        print(status())
    if "--wacht" in sys.argv:
        print(wacht_en_zet())

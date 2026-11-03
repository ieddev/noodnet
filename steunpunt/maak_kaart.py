"""
maak_kaart.py - maakt de aanmeldkaart van dit Noodsteunpunt (om te lamineren).

Draai dit op de Pi van het steunpunt, in de map met steunpunt_brug.py:

    python maak_kaart.py

Het haalt zelf op:
  - naam en roepnaam van het steunpunt  (uit steunpunt_brug.py)
  - het adres van het steunpunt         (uit ~/.reticulum/lxmf/gateway.id)
  - de actuele aanmeldcode              (ook als die met CODE gewijzigd is)
  - LoRa-instellingen, IFAC, disciplines (uit noodnet_netwerk.json)

Resultaat: kaart_<steunpunt>.html. Open die in een browser en druk af
(op A5 of A6, liefst in kleur). Benodigd: pip install qrcode

Opties:  --code XYZ   andere aanmeldcode op de kaart zetten
         --adres HEX  adres opgeven (als RNS niet beschikbaar is)
"""

import argparse
import base64
import html
import io
import json
import os
import re
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BRUG = os.path.join(SCRIPT_DIR, "steunpunt_brug.py")
NETWERK = os.path.join(SCRIPT_DIR, "noodnet_netwerk.json")
LXMF_DIR = os.path.expanduser(os.environ.get("NOODNET_LXMF_DIR", "~/.reticulum/lxmf"))


INSTELLINGEN = os.path.join(SCRIPT_DIR, "steunpunt_instellingen.json")
_JSON_NAAM = {"STEUNPUNT_NAAM": "steunpunt_naam", "CALLSIGN": "roepnaam", "AANMELDCODE": "aanmeldcode"}


def config_waarde(naam, standaard=None):
    """Eerst steunpunt_instellingen.json (beheerpagina), anders NAAM = "..." uit steunpunt_brug.py."""
    try:
        with open(INSTELLINGEN, encoding="utf-8") as f:
            w = json.load(f).get(_JSON_NAAM.get(naam, ""), "")
        if w not in ("", None):
            return str(w)
    except (OSError, ValueError):
        pass
    try:
        src = open(BRUG, encoding="utf-8").read()
    except OSError:
        return standaard
    m = re.search(rf'^{naam}\s*=\s*"([^"]*)"', src, re.M)
    return m.group(1) if m else standaard


def adres_van_steunpunt():
    try:
        import RNS
        ident = RNS.Identity.from_file(os.path.join(LXMF_DIR, "gateway.id"))
        if ident is None:
            raise ValueError("geen identiteit gevonden")
        return RNS.Destination.hash(ident, "lxmf", "delivery").hex()
    except Exception as e:
        sys.exit(f"Kan het adres niet bepalen ({e}). Start steunpunt_brug.py eerst één keer, "
                 f"of geef het adres op met --adres.")


def actuele_code():
    try:
        with open(os.path.join(LXMF_DIR, "aanmeldingen.json"), encoding="utf-8") as f:
            code = json.load(f).get("code")
            if code:
                return code
    except (OSError, ValueError):
        pass
    return config_waarde("AANMELDCODE", "")


def mhz(hz):
    return f"{hz / 1e6:.3f} MHz"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code")
    ap.add_argument("--adres")
    ap.add_argument("--uit", help="bestandsnaam van de kaart (standaard kaart_<steunpunt>.html)")
    args = ap.parse_args()

    try:
        import qrcode
        import qrcode.image.svg
    except ImportError:
        sys.exit("De module 'qrcode' ontbreekt. Installeer met:  pip install qrcode")

    net = json.load(open(NETWERK, encoding="utf-8"))
    naam = config_waarde("STEUNPUNT_NAAM", "Steunpunt")
    call = config_waarde("CALLSIGN", "")
    adres = (args.adres or adres_van_steunpunt()).replace("<", "").replace(">", "").lower()
    code = args.code or actuele_code()
    if not code or code == "WIJZIG-MIJ":
        print("LET OP: de aanmeldcode is nog niet ingesteld (AANMELDCODE in steunpunt_brug.py).")

    lora = net.get("lora", {})
    radios = []
    for band in ("433", "868"):
        r = lora.get(band)
        if r:
            radios.append({"band": band, "f": r["frequentie"], "bw": r["bandbreedte"],
                           "sf": r["sf"], "cr": r["cr"], "p": r.get("vermogen_dbm")})
    ifac_naam = net.get("ifac_netwerknaam", "")
    ifac_ww = net.get("ifac_wachtwoord", "")
    disciplines = [[k, v.get("label", k)] for k, v in net.get("disciplines", {}).items()]

    # Inhoud van de QR-code (voor de "scan kaart"-knop in de app, fase 2)
    qr_data = {"v": 1, "g": net.get("gemeente", ""), "sp": naam, "a": adres, "c": code,
               "r": [{k: r[k] for k in ("band", "f", "bw", "sf", "cr", "p")} for r in radios],
               "d": disciplines}
    if ifac_naam or ifac_ww:
        qr_data["i"] = [ifac_naam, ifac_ww]
    # Optioneel: hoe zuinig de app posities stuurt (anders: 600 s / 1800 s / 300 m)
    bk = net.get("baken")
    if isinstance(bk, dict):
        try:
            qr_data["b"] = [int(bk.get("min_interval_s", 600)), int(bk.get("max_interval_s", 1800)),
                            int(bk.get("afstand_m", 300))]
        except (TypeError, ValueError):
            print("LET OP: 'baken' in noodnet_netwerk.json is onjuist en wordt overgeslagen.")
    # De QR-code is een link: de camera van de telefoon opent hem direct in Sideband
    js = json.dumps(qr_data, ensure_ascii=False, separators=(",", ":"))
    qr_tekst = "noodnet://kaart?d=" + base64.urlsafe_b64encode(js.encode("utf-8")).decode("ascii").rstrip("=")

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    qr.add_data(qr_tekst)
    qr.make(fit=True)
    buf = io.BytesIO()
    qr.make_image(image_factory=qrcode.image.svg.SvgPathImage).save(buf)
    svg = buf.getvalue().decode("utf-8")
    svg = re.sub(r"<\?xml[^>]*\?>", "", svg)
    svg = re.sub(r'(<svg[^>]*?)\swidth="[^"]*"', r"\1", svg, count=1)
    svg = re.sub(r'(<svg[^>]*?)\sheight="[^"]*"', r"\1", svg, count=1)

    e = html.escape
    radio_rijen = "".join(
        f"<tr><th>{e(r['band'])} MHz</th><td>{mhz(r['f'])} &nbsp;BW {r['bw'] // 1000} kHz &nbsp;"
        f"SF {r['sf']} &nbsp;CR {r['cr']}"
        + (f" &nbsp;max {r['p']} dBm" if r.get("p") is not None else "") + "</td></tr>"
        for r in radios)
    ifac_rij = (f"<tr><th>IFAC</th><td>netwerk <b>{e(ifac_naam)}</b><br>wachtwoord <b>{e(ifac_ww)}</b></td></tr>"
                if (ifac_naam or ifac_ww) else "")
    vertrouwelijk = '<div class="vertr">VERTROUWELIJK &ndash; niet achterlaten</div>' if (ifac_naam or ifac_ww) else ""
    hulp = ", ".join(e(lbl) for _, lbl in disciplines)

    page = f"""<!doctype html>
<html lang="nl"><head><meta charset="utf-8">
<title>Kaart {e(naam)}</title>
<style>
  @page {{ size: A5 landscape; margin: 8mm; }}
  body {{ font-family: Arial, Helvetica, sans-serif; color:#111; margin:0; }}
  .kaart {{ width:190mm; min-height:128mm; box-sizing:border-box; border:3px solid #c0392b;
           border-radius:6mm; padding:6mm 7mm; }}
  .kop {{ display:flex; justify-content:space-between; align-items:flex-start; border-bottom:2px solid #c0392b;
          padding-bottom:3mm; margin-bottom:4mm; }}
  .kop h1 {{ font-size:20pt; margin:0; }}
  .kop .sub {{ font-size:10pt; color:#555; margin-top:1mm; }}
  .code {{ text-align:right; }}
  .code .lab {{ font-size:9pt; color:#555; }}
  .code .val {{ font-size:22pt; font-weight:bold; letter-spacing:1px; font-family:monospace; }}
  .rij {{ display:flex; gap:7mm; }}
  .qr {{ width:62mm; flex:none; text-align:center; font-size:8pt; color:#555; }}
  .qr svg {{ width:62mm; height:62mm; }}
  table {{ border-collapse:collapse; font-size:10pt; width:100%; }}
  th {{ text-align:left; vertical-align:top; padding:1.2mm 3mm 1.2mm 0; white-space:nowrap; color:#333; }}
  td {{ padding:1.2mm 0; vertical-align:top; }}
  .adres {{ font-family:monospace; font-size:9.5pt; word-break:break-all; }}
  ol {{ margin:3mm 0 0 0; padding-left:5mm; font-size:9.5pt; line-height:1.35; }}
  .hand {{ margin-top:2mm; font-size:8pt; color:#555; }}
  .vertr {{ margin-top:3mm; background:#c0392b; color:#fff; font-weight:bold; text-align:center;
            padding:1.5mm; border-radius:2mm; font-size:10pt; }}
  .voet {{ margin-top:2mm; font-size:7.5pt; color:#777; }}
</style></head>
<body><div class="kaart">
  <div class="kop">
    <div><h1>{e(naam)}</h1>
      <div class="sub">Noodnet {e(net.get('gemeente', ''))} &middot; roepnaam {e(call)} &middot; meldingen naar: {hulp}</div></div>
    <div class="code"><div class="lab">AANMELDCODE</div><div class="val">{e(code)}</div></div>
  </div>
  <div class="rij">
    <div class="qr">{svg}<div>Scan met de camera van uw telefoon<br>en open de link in Sideband</div></div>
    <div style="flex:1">
      <table>
        {radio_rijen}
        {ifac_rij}
        <tr><th>Steunpunt</th><td>{e(naam)}<br><span class="adres">{e(adres)}</span></td></tr>
      </table>
      <ol>
        <li>Koppel de RNode via Bluetooth (samen met de zendamateur).</li>
        <li>Scan de QR-code met de camera en open de link in Sideband.</li>
        <li>Kies uw RNode (433 of 868 MHz), vul uw naam in en tik op <b>AANMELDEN</b>.</li>
        <li>Wacht tot bovenaan in het noodmeldscherm staat: &ldquo;Aangemeld bij {e(naam)}&rdquo;.</li>
      </ol>
      <div class="hand">Zonder scan: vul de waarden hierboven in onder <i>Connectivity &rarr; RNode</i>,
        voeg {e(naam)} toe als contact en stuur <b>AANMELDEN {e(code)} &lt;uw naam&gt;</b>.</div>
    </div>
  </div>
  {vertrouwelijk}
  <div class="voet">Gemaakt {time.strftime('%Y-%m-%d %H:%M')} &middot; code geldig tot de zendamateur een nieuwe instelt.</div>
</div></body></html>
"""
    bestand = args.uit or os.path.join(SCRIPT_DIR, "kaart_" + re.sub(r"[^A-Za-z0-9_-]+", "_", naam) + ".html")
    with open(bestand, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"Kaart gemaakt: {bestand}")
    print(f"QR-inhoud ({len(qr_tekst)} tekens): {qr_tekst}")


if __name__ == "__main__":
    main()

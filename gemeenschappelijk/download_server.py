#!/usr/bin/env python3
"""
download_server.py - openbare startpagina op poort 80 (zonder wachtwoord).

Wie met de hotspot verbonden is, opent  http://10.42.0.1  en ziet:
  - steunpunt: de Noodnet-app (APK) om te downloaden + korte uitleg
  - eindpost:  links naar het M/ETHANE-scherm en de app
De beheerpagina (poort 8080) blijft achter het wachtwoord.

De APK staat in ~/noodnet/download/noodnet.apk (zet bijwerken.sh daar neer).
"""

import html
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAP = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD = os.path.join(MAP, "download")
APK = os.path.join(DOWNLOAD, "noodnet.apk")
e = html.escape


def lees(naam, standaard=None):
    try:
        with open(os.path.join(MAP, naam), encoding="utf-8") as f:
            return json.load(f) if naam.endswith(".json") else f.read().strip()
    except (OSError, ValueError):
        return standaard


def pagina(host):
    rol = lees("rol", "steunpunt")
    if rol == "eindpost":
        inst = lees("eindpost_instellingen.json", {}) or {}
        naam = inst.get("eindpost_naam") or "Noodnet eindpost"
    else:
        inst = lees("steunpunt_instellingen.json", {}) or {}
        naam = inst.get("steunpunt_naam") or "Noodsteunpunt"
    roepnaam = inst.get("roepnaam", "")
    apk = ""
    if os.path.exists(APK):
        mb = os.path.getsize(APK) / 1e6
        versie = lees("download/versie.txt", "")
        apk = f"""<a class="knop" href="/noodnet.apk">Noodnet-app downloaden</a>
<p class="klein">{mb:.0f} MB{(' &middot; versie ' + e(versie)) if versie else ''}</p>
<ol><li>Tik op de knop en open het gedownloade bestand.</li>
<li>Sta toe dat de browser apps installeert (Android vraagt dit één keer).</li>
<li>Had je de gewone Sideband al? Maak eerst een backup (<i>Backup &amp; Keys</i>) en verwijder die app.</li>
<li>Open de app, koppel de RNode en scan de kaart van het steunpunt.</li></ol>"""
    else:
        apk = "<p>De app staat nog niet op dit apparaat. Vraag de zendamateur.</p>"
    extra = ""
    if rol == "eindpost":
        extra = f"""<a class="knop" href="http://{e(host)}:1880/ui">M/ETHANE-scherm openen</a>"""
    return f"""<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(naam)}</title>
<style>
body{{margin:0;font:17px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:#f6f7f9;color:#1b1f24}}
header{{background:#b3261e;color:#fff;padding:16px}}header b{{font-size:20px}}header div{{opacity:.85;font-size:14px}}
main{{max-width:560px;margin:0 auto;padding:16px}}section{{background:#fff;border:1px solid #dde1e6;border-radius:12px;padding:16px;margin-bottom:16px}}
.knop{{display:block;text-align:center;padding:16px;border-radius:10px;background:#1d4f91;color:#fff;font-weight:700;text-decoration:none;font-size:19px;margin:8px 0}}
.klein{{color:#5b6470;font-size:14px;text-align:center;margin:0}}ol{{padding-left:20px}}
@media (prefers-color-scheme:dark){{body{{background:#14171b;color:#e8eaed}}section{{background:#1d2126;border-color:#30353c}}}}
</style></head><body><header><b>{e(naam)}</b><div>Noodnet {e(roepnaam)}</div></header><main>
{('<section>' + extra + '</section>') if extra else ''}
<section><h2 style="margin-top:0">Noodnet-app</h2>{apk}</section>
<p class="klein">Beheer (zendamateur): <a href="http://{e(host)}:8080">http://{e(host)}:8080</a></p>
</main></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "Noodnet/1"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    def do_GET(self):
        host = (self.headers.get("Host") or "10.42.0.1").split(":")[0]
        if self.path.split("?")[0] == "/noodnet.apk" and os.path.exists(APK):
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.android.package-archive")
            self.send_header("Content-Disposition", 'attachment; filename="noodnet.apk"')
            self.send_header("Content-Length", str(os.path.getsize(APK)))
            self.end_headers()
            with open(APK, "rb") as f:
                while True:
                    blok = f.read(256 * 1024)
                    if not blok:
                        break
                    self.wfile.write(blok)
            return
        data = pagina(host).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    poort = int(sys.argv[1]) if len(sys.argv) > 1 else 80
    ThreadingHTTPServer(("0.0.0.0", poort), Handler).serve_forever()

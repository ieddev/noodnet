#!/usr/bin/env python3
"""Maakt docs/Noodnet-procedure.pdf uit docs/PROCEDURE.md.

Nodig op de pc waarop je hem maakt (niet op de Pi):
    pip install markdown qrcode pypdf playwright && playwright install chromium
Gebruik:
    python3 docs/pdf/maak_pdf.py
"""
import base64, datetime, io, os, re, subprocess, sys

import markdown
import qrcode
import qrcode.image.svg
from pypdf import PdfReader, PdfWriter
from playwright.sync_api import sync_playwright

HIER = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.dirname(HIER)
REPO = os.path.dirname(DOCS)
BRON = os.path.join(DOCS, "PROCEDURE.md")
UIT = os.path.join(DOCS, "Noodnet-procedure.pdf")

WEBSITE = "http://noodnet.ied.nl"
GITHUB_PROC = "https://github.com/ieddev/noodnet/blob/main/docs/PROCEDURE.md"

# Hoofdstukken die op een nieuwe bladzijde beginnen
NIEUWE_PAGINA = {"volgorde-bij-een-complete-nieuwe-opzet", "stap-4-instellen-via-de-beheerpagina",
                 "problemen-oplossen"}
# Schema's die bij een kopje horen
SCHEMA = {"noodsteunpunt": ("noodnet-noodsteunpunt.svg", "Opbouw van een Noodsteunpunt"),
          "eindpost": ("noodnet-eindpost.svg", "Opbouw van een Eindpost")}

MAANDEN = "januari februari maart april mei juni juli augustus september oktober november december".split()


def versie():
    try:
        h = subprocess.run(["git", "-C", REPO, "log", "-1", "--format=%h|%cs", "--", "docs/PROCEDURE.md"],
                           capture_output=True, text=True, check=True).stdout.strip()
        kort, datum = h.split("|")
        d = datetime.date.fromisoformat(datum)
    except Exception:
        kort, d = "", datetime.date.today()
    return "%d %s %d" % (d.day, MAANDEN[d.month - 1], d.year), kort


def qr_svg(tekst):
    img = qrcode.make(tekst, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=1)
    b = io.BytesIO(); img.save(b)
    return "data:image/svg+xml;base64," + base64.b64encode(b.getvalue()).decode()


def afbeelding(naam):
    with open(os.path.join(HIER, "afbeeldingen", naam), "rb") as fh:
        return "data:image/svg+xml;base64," + base64.b64encode(fh.read()).decode()


def inhoud(md_tekst, merktekens):
    # titel + inleiding (alles voor de eerste ---) apart houden
    md_tekst = re.sub(r"^# .*\n", "", md_tekst, count=1)
    md = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "sane_lists"],
                           extension_configs={"toc": {"permalink": False}})
    html = md.convert(md_tekst)
    hoofdstukken = []

    def kop(m):
        niveau, ident, tekst = m.group(1), m.group(2), m.group(3)
        klasse = ' class="nieuwe-pagina"' if ident in NIEUWE_PAGINA else ""
        merk = ""
        if niveau == "2":
            hoofdstukken.append((ident, re.sub("<[^>]+>", "", tekst)))
        uit = '<h%s id="%s"%s>%s%s</h%s>' % (niveau, ident, klasse, tekst, merk, niveau)
        if niveau == "3" and ident in SCHEMA:
            bestand, onderschrift = SCHEMA[ident]
            uit += ('<figure class="schema"><img src="%s" alt="%s"><figcaption>%s</figcaption></figure>'
                    % (afbeelding(bestand), onderschrift, onderschrift))
        return uit
    html = re.sub(r'<h([23]) id="([^"]+)">(.*?)</h\1>', kop, html)
    html = html.replace("<li>[ ] ", '<li class="vink"><span class="vakje"></span>')
    html = re.sub(r"<hr\s*/?>", "", html)
    return html, hoofdstukken


def invulblad():
    regels = [("Roepnaam en SSID van dit station", ""), ("Dit station is", "&#9744; Noodsteunpunt &nbsp;&nbsp; &#9744; Eindpost"),
              ("Hostnaam (voor ssh)", ""), ("Wifi van de hotspot", "Noodnet-"), ("Gemeente", ""),
              ("2 m-frequentie van de gemeente", "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;MHz"),
              ("Set en interface", ""), ("Besturing", "&#9744; CAT &nbsp;&nbsp; &#9744; RTS &nbsp;&nbsp; &#9744; DTR &nbsp;&nbsp; model / poort:"),
              ("RNode 433 MHz (poort)", ""), ("RNode 868 MHz (poort)", ""),
              ("Supervisor van de gemeente", ""), ("Versie netwerkbestand", ""), ("Laatste back-up gemaakt op", "")]
    rijen = "".join("<tr><th>%s</th><td>%s</td></tr>" % r for r in regels)
    posten = "".join("<tr><td>%s</td><td></td><td></td></tr>" % d for d in
                     ["Brandweer", "Politie", "Ambulance / GHOR", "Gemeente", "", ""])
    return """
<section class="invulblad">
<h2 id="mijn-station">Gegevens van mijn station</h2>
<p class="klein">Vul in met de hand en bewaar bij de set.</p>
<table class="invul">%s</table>
<h3>Eindposten in de gemeente</h3>
<table class="invul posten"><thead><tr><th>Discipline</th><th>Roepnaam eindpost</th><th>Plaats</th></tr></thead>%s</table>
<div class="let-op"><strong>Geen wachtwoorden op dit blad.</strong> Hotspot- en beheerwachtwoord, IFAC en de back-up
bewaar je apart en veilig. Raakt dit blad kwijt, dan kan niemand er iets mee.</div>
</section>""" % (rijen, posten)


CSS = """
@page { size: A4; margin: 18mm 16mm 20mm 16mm; }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: Inter, 'Segoe UI', Helvetica, Arial, sans-serif; color: #1d2530; font-size: 10pt; line-height: 1.45; margin: 0; }
a { color: #1d4f7a; text-decoration: none; }
code { font-family: 'DejaVu Sans Mono', Consolas, Menlo, monospace; font-size: 8.6pt; background: #eef1f4;
       padding: 0.5pt 3pt; border-radius: 3px; }
pre { background: #1d2530; color: #f4f6f8; padding: 8pt 10pt; border-radius: 5px; white-space: pre-wrap;
      word-break: break-all; break-inside: avoid; }
pre code { background: none; color: inherit; font-size: 9pt; padding: 0; }
h2 { font-size: 16pt; margin: 18pt 0 6pt; padding-bottom: 3pt; border-bottom: 2.5pt solid #c0392b;
     break-after: avoid; }
h3 { font-size: 12pt; margin: 14pt 0 4pt; color: #30363f; break-after: avoid; }
h2.nieuwe-pagina { break-before: page; margin-top: 0; }
p, li { orphans: 3; widows: 3; }
ul, ol { padding-left: 16pt; margin: 4pt 0 8pt; }
li { margin: 2pt 0; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 9pt; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
th, td { border: 0.6pt solid #c9d1db; padding: 4pt 6pt; vertical-align: top; text-align: left; }
thead th { background: #30363f; color: #fff; font-weight: 600; }
tbody tr:nth-child(even) td { background: #f4f6f8; }
tbody th { background: #f4f6f8; }
td:first-child { font-weight: 600; }
.merk { font-size: 1px; color: #fff; }
li.vink { list-style: none; margin-left: -14pt; }
.vakje { display: inline-block; width: 9pt; height: 9pt; border: 1pt solid #1d2530; border-radius: 2px;
         margin-right: 6pt; vertical-align: -1pt; }
figure.schema { margin: 6pt 0 10pt; text-align: center; break-inside: avoid; }
figure.schema img { width: 100%; max-height: 95mm; object-fit: contain; }
figcaption { font-size: 8.5pt; color: #5b6573; margin-top: 2pt; }
.klein { font-size: 9pt; color: #5b6573; }

/* voorblad */
.voorblad { height: 297mm; width: 210mm; position: relative; padding: 26mm 20mm; break-after: page;
            background: #1d2530; color: #f4f6f8; overflow: hidden; }
.voorblad .streep { position: absolute; left: 0; top: 0; bottom: 0; width: 8mm; background: #c0392b; }
.voorblad .label { font-size: 10pt; letter-spacing: 3pt; text-transform: uppercase; color: #e8a49c; }
.voorblad h1 { font-size: 46pt; line-height: 1.05; margin: 6mm 0 4mm; font-weight: 800; }
.voorblad .sub { font-size: 16pt; color: #c9d1db; max-width: 150mm; }
.voorblad .schema-voor { margin: 16mm -4mm 0; background: #fff; border-radius: 6px; padding: 5mm; }
.voorblad .schema-voor img { width: 100%; display: block; }
.voorblad .onder { position: absolute; left: 20mm; right: 20mm; bottom: 20mm; display: flex;
                   justify-content: space-between; align-items: flex-end; font-size: 9.5pt; color: #c9d1db; }
.voorblad .onder strong { color: #fff; }
.voorblad .qr { text-align: center; font-size: 8pt; }
.voorblad .qr img { width: 26mm; height: 26mm; background: #fff; padding: 1.5mm; border-radius: 3px; display: block;
                    margin-bottom: 2mm; }
.voorblad .qrs { display: flex; gap: 6mm; }

/* inhoud */
.inhoud h2 { margin-top: 0; }
.toc { list-style: none; padding: 0; margin: 4pt 0 0; font-size: 10.5pt; }
.toc li { display: flex; align-items: baseline; margin: 0; padding: 3.2pt 0; border-bottom: 0.5pt dotted #c9d1db; }
.toc li a { color: #1d2530; }
.toc li .nr { margin-left: auto; padding-left: 8pt; font-weight: 600; }
.inhoudsopgave { break-after: page; }
.inleiding p:first-child { font-size: 11pt; }
.let-op { border-left: 3pt solid #c0392b; background: #fbeeec; padding: 6pt 9pt; margin: 10pt 0; font-size: 9.5pt;
          break-inside: avoid; }
.invulblad { break-before: page; }
table.invul th { width: 42%; background: #f4f6f8; font-weight: 600; }
table.invul td { height: 22pt; font-weight: normal; color: #5b6573; background: #fff !important; }
table.posten th { background: #30363f; color: #fff; width: auto; }
table.posten td:first-child { font-weight: 600; color: #1d2530; }
"""


def bouw_html(merktekens, paginas=None):
    md_tekst = open(BRON, encoding="utf-8").read()
    datum, kort = versie()
    # inleiding = alles tot de eerste '---'
    kop_eind = md_tekst.index("\n---")
    inl_md, rest_md = md_tekst[:kop_eind], md_tekst[kop_eind:]
    inl_html, _ = inhoud(inl_md, False)
    rest_html, hoofdstukken = inhoud("# x\n" + rest_md, merktekens)
    hoofdstukken.append(("mijn-station", "Gegevens van mijn station"))

    toc = "".join('<li><a href="#%s">%s</a><span class="nr">%s</span></li>'
                  % (i, t, (paginas or {}).get(i, "")) for i, t in hoofdstukken)
    versietekst = "Versie %s%s" % (datum, (" &middot; %s" % kort) if kort else "")
    voorblad = """
<section class="voorblad"><div class="streep"></div>
<div class="label">Noodnet &middot; naslagwerk</div>
<h1>Een Noodsteunpunt<br>of Eindpost opzetten</h1>
<div class="sub">De procedure voor zendamateurs: installeren, instellen, testen en problemen oplossen. Leg dit naast je set.</div>
<div class="schema-voor"><img src="%s" alt="Zo loopt een melding"></div>
<div class="onder">
  <div><strong>Gert de Haan, PD3PAM</strong><br>%s<br>De nieuwste versie staat altijd op GitHub.</div>
  <div class="qrs">
    <div class="qr"><img src="%s" alt="">Website</div>
    <div class="qr"><img src="%s" alt="">Nieuwste procedure</div>
  </div>
</div></section>""" % (afbeelding("noodnet-overzicht.svg"), versietekst, qr_svg(WEBSITE), qr_svg(GITHUB_PROC))

    inleiding = """
<section class="inhoudsopgave inhoud"><h2>Inhoud</h2><ul class="toc">%s</ul></section>
<section class="inleiding inhoud"><h2>Voor je begint</h2>%s
<p class="klein">Website: <a href="%s">noodnet.ied.nl</a> &middot; nieuwste versie van deze procedure:
<a href="%s">github.com/ieddev/noodnet</a> &middot; Licentie: CC BY-SA 4.0.</p>
</section>""" % (toc, inl_html, WEBSITE, GITHUB_PROC)

    kop = "<!doctype html><html lang='nl'><head><meta charset='utf-8'><title>Noodnet - procedure</title><style>%s</style></head><body>" % CSS
    return (kop.replace("</style>", "@page { margin: 0; }</style>") + voorblad + "</body></html>",
            kop + "%s<main>%s</main>%s</body></html>" % (inleiding, rest_html, invulblad()), versietekst, hoofdstukken)


def naar_pdf(html, versietekst, pad, voettekst=True):
    voet = ("<div style='font-family:Helvetica,Arial,sans-serif;font-size:7.5pt;color:#5b6573;width:100%%;"
            "padding:0 16mm;display:flex;justify-content:space-between'>"
            "<span>Noodnet &middot; Noodsteunpunt of Eindpost opzetten &middot; %s</span>"
            "<span>pagina <span class='pageNumber'></span> van <span class='totalPages'></span></span></div>"
            % versietekst)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.set_content(html, wait_until="networkidle")
        pg.pdf(path=pad, format="A4", print_background=True, prefer_css_page_size=True,
               display_header_footer=voettekst, header_template="<span></span>", footer_template=voet)
        b.close()


def main():
    # voorblad zonder voettekst; de rest genummerd vanaf 1 (het voorblad telt niet mee)
    tijdelijk = UIT + ".tmp"
    _, html, vt, hoofdstukken = bouw_html(True)
    naar_pdf(html, vt, tijdelijk)
    # paginanummer per hoofdstuk: de eerste pagina (na de inhoud) met een regel die precies de kop is
    paginas, start = {}, 2
    bladen = [[re.sub(r"\W", "", r) for r in (b.extract_text() or "").splitlines()] for b in PdfReader(tijdelijk).pages]
    for ident, titel in hoofdstukken:
        for nr in range(start, len(bladen) + 1):
            if re.sub(r"\W", "", titel) in bladen[nr - 1]:
                paginas[ident] = start = nr
                break
    voor, html, vt, _ = bouw_html(False, paginas)
    naar_pdf(html, vt, tijdelijk)
    naar_pdf(voor, vt, tijdelijk + ".voor", voettekst=False)
    w = PdfWriter()
    for f in (tijdelijk + ".voor", tijdelijk):
        for blad in PdfReader(f).pages:
            w.add_page(blad)
    w.add_metadata({"/Title": "Noodnet - een Noodsteunpunt of Eindpost opzetten", "/Author": "Gert de Haan, PD3PAM"})
    with open(UIT, "wb") as fh:
        w.write(fh)
    os.remove(tijdelijk); os.remove(tijdelijk + ".voor")
    print("klaar:", UIT, "-", len(w.pages), "pagina's;", "inhoud:", paginas)


if __name__ == "__main__":
    main()

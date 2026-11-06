#!/usr/bin/env python3
"""Maakt de PDF-handleidingen in docs/ uit de MD-bestanden:
    PROCEDURE.md    -> Noodnet-procedure.pdf    (zendamateurs: steunpunt en eindpost)
    VRIJWILLIGER.md -> Noodnet-vrijwilliger.pdf (vrijwilligers: RNode en app)

Nodig op de pc waarop je hem maakt (niet op de Pi):
    pip install markdown qrcode pypdf playwright && playwright install chromium
Gebruik:
    python3 docs/pdf/maak_pdf.py                 (allebei)
    python3 docs/pdf/maak_pdf.py vrijwilliger    (alleen die)
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
WEBSITE = "http://noodnet.ied.nl"
GITHUB = "https://github.com/ieddev/noodnet/blob/main/docs/"

DOCUMENTEN = {
    "procedure": dict(
        bron="PROCEDURE.md", uit="Noodnet-procedure.pdf",
        label="Noodnet &middot; naslagwerk", titel="Een Noodsteunpunt<br>of Eindpost opzetten",
        voettitel="Noodsteunpunt of Eindpost opzetten",
        pdftitel="Noodnet - een Noodsteunpunt of Eindpost opzetten",
        sub="De procedure voor zendamateurs: installeren, instellen, testen en problemen oplossen. Leg dit naast je set.",
        voorblad="noodnet-overzicht.svg", qr2="Nieuwste procedure",
        # hoofdstukken die op een nieuwe bladzijde beginnen
        nieuwe_pagina={"volgorde-bij-een-complete-nieuwe-opzet",
                       "problemen-oplossen"},
        # afbeeldingen onder een kopje
        schema={"noodsteunpunt": ("noodnet-noodsteunpunt.svg", "Opbouw van een Noodsteunpunt"),
                "eindpost": ("noodnet-eindpost.svg", "Opbouw van een Eindpost")},
        inhoud_eigen_pagina=True, achterblad="invulblad_station"),
    "vrijwilliger": dict(
        bron="VRIJWILLIGER.md", uit="Noodnet-vrijwilliger.pdf",
        label="Noodnet &middot; voor vrijwilligers", titel="Melden met je<br>telefoon en RNode",
        voettitel="Handleiding voor vrijwilligers",
        pdftitel="Noodnet - handleiding voor vrijwilligers",
        sub="RNode klaarmaken, de app installeren, aanmelden bij het steunpunt en een M/ETHANE-melding doen.",
        voorblad="noodnet-vrijwilliger.svg", qr2="Nieuwste handleiding",
        nieuwe_pagina={"stap-4-aanmelden-bij-het-steunpunt", "problemen-oplossen"},
        schema={"stap-4-aanmelden-bij-het-steunpunt": ("noodnet-voorbeeldkaart.png",
                                                      "Zo ziet een aanmeldkaart eruit. Elk steunpunt heeft een eigen kaart.")},
        inhoud_eigen_pagina=False, achterblad="zakkaart"),
}
D = DOCUMENTEN["procedure"]   # het document dat nu gemaakt wordt

MAANDEN = "januari februari maart april mei juni juli augustus september oktober november december".split()


def versie():
    try:
        h = subprocess.run(["git", "-C", REPO, "log", "-1", "--format=%h|%cs", "--", "docs/" + D["bron"]],
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
    soort = "image/svg+xml" if naam.endswith(".svg") else "image/png"
    with open(os.path.join(HIER, "afbeeldingen", naam), "rb") as fh:
        return "data:%s;base64,%s" % (soort, base64.b64encode(fh.read()).decode())


def inhoud(md_tekst, merktekens):
    # titel + inleiding (alles voor de eerste ---) apart houden
    md_tekst = re.sub(r"^# .*\n", "", md_tekst, count=1)
    # GitHub accepteert sublijstjes met 3 spaties, Python-Markdown wil er 4
    md_tekst = re.sub(r"^   - ", "    - ", md_tekst, flags=re.M)
    md = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "sane_lists"],
                           extension_configs={"toc": {"permalink": False}})
    html = md.convert(md_tekst)
    hoofdstukken = []

    def kop(m):
        niveau, ident, tekst = m.group(1), m.group(2), m.group(3)
        klasse = ' class="nieuwe-pagina"' if ident in D["nieuwe_pagina"] else ""
        merk = ""
        if niveau == "2":
            hoofdstukken.append((ident, re.sub("<[^>]+>", "", tekst)))
        uit = '<h%s id="%s"%s>%s%s</h%s>' % (niveau, ident, klasse, tekst, merk, niveau)
        if ident in D["schema"]:
            bestand, onderschrift = D["schema"][ident]
            uit += ('<figure class="schema"><img src="%s" alt="%s"><figcaption>%s</figcaption></figure>'
                    % (afbeelding(bestand), onderschrift, onderschrift))
        return uit
    html = re.sub(r'<h([23]) id="([^"]+)">(.*?)</h\1>', kop, html)
    html = html.replace("<li>[ ] ", '<li class="vink"><span class="vakje"></span>')
    html = re.sub(r"<hr\s*/?>", "", html)
    # de verwijzing naar de PDF zelf hoort niet in de PDF
    html = re.sub(r"<p><strong>Afdrukken\?</strong>.*?</p>", "", html, flags=re.S)
    html = doortellen(html)
    # korte tabellen niet over twee pagina's verdelen; lange wel
    html = re.sub(r"<table>(.*?)</table>",
                  lambda m: ('<table class="heel">' if m.group(1).count("<tr") <= 9 else "<table>") + m.group(1) + "</table>",
                  html, flags=re.S)
    return html, hoofdstukken


def doortellen(html):
    """Een genummerde lijst die na een tabel verdergaat, telt door (zoals op GitHub bedoeld)."""
    uit, teller = [], 0
    for deel in re.split(r"(<ol>|</ol>|<h[23][^>]*>)", html):
        if deel == "<ol>":
            uit.append('<ol start="%d">' % (teller + 1) if teller else deel)
            continue
        if deel.startswith("<h"):
            teller = 0
        elif uit and uit[-1].startswith("<ol"):
            teller += len(re.findall(r"<li[ >]", deel))
        uit.append(deel)
    return "".join(uit)


def zakkaart():
    velden = [("M", "Groot incident?", "Ja/nee, en in één zin waarom"),
              ("E", "Exacte locatie", "Adres, kruispunt of herkenningspunt"),
              ("T", "Soort incident", "Brand, ongeval, instorting, ..."),
              ("H", "Gevaren", "Gas, vuur, verkeer, instortingsgevaar, ..."),
              ("A", "Bereikbaarheid", "Hoe kom je er, welke route is vrij"),
              ("N", "Aantal slachtoffers", "Aantal en hoe ernstig"),
              ("E", "Hulpdiensten", "Wie is er al, wie is er nog nodig")]
    rijen = "".join('<tr><td class="letter">%s</td><td><strong>%s</strong><br><span>%s</span></td></tr>' % v
                    for v in velden)
    gegevens = "".join("<tr><th>%s</th><td></td></tr>" % g for g in
                       ["Mijn naam", "Steunpunt", "Band van mijn RNode", "Naam van mijn RNode (bijv. RNode A8EB)",
                        "Beheerder (roepnaam)"])
    return """
<section class="invulblad zakkaart">
<h2 id="zakkaart">Zakkaart</h2>
<p class="klein">Knip uit langs de stippellijn, vouw dubbel en bewaar bij je telefoon of RNode.</p>
<div class="knip">
 <div class="kaartje">
  <div class="kaartkop">NOODMELDING M/ETHANE</div>
  <ol class="kort"><li>Rode knop <b>NOODMELDING M/ETHANE</b></li><li>Kies de hulpdienst(en)</li>
  <li>Vul in wat je weet</li><li><b>Mijn locatie meesturen</b> aan</li><li><b>VERSTUUR MELDING</b></li>
  <li>Wacht op <b>afgeleverd</b></li></ol>
  <table class="methane">%s</table>
 </div>
 <div class="kaartje">
  <div class="kaartkop">MIJN GEGEVENS</div>
  <table class="invul klein-invul">%s</table>
  <div class="kaartkop klein-kop">ONTHOUD</div>
  <ul class="kort"><li><b>Eigen veiligheid eerst.</b> Werkt 112 nog: bel 112.</li>
  <li>Antenne erop vóór je de RNode aanzet.</li><li>Telefoon en RNode opgeladen, powerbank mee.</li>
  <li><b>NIET doorgegeven</b>? Kies een andere weg en meld het de beheerder.</li>
  <li>Laat de QR-code van het steunpunt niet aan anderen zien.</li></ul>
 </div>
</div>
</section>""" % (rijen, gegevens)


def invulblad_station():
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
table.heel { break-inside: avoid; }
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
.inhoudsopgave.samen { break-after: auto; }
.inhoudsopgave.samen + .inleiding { margin-top: 14pt; }
figure.schema img[src^="data:image/png"] { max-height: 80mm; width: auto; max-width: 100%; }
.knip { display: flex; border: 1pt dashed #8a9199; }
.kaartje { width: 50%; padding: 8pt 10pt; font-size: 8.6pt; line-height: 1.3; }
.kaartje + .kaartje { border-left: 1pt dashed #8a9199; }
.kaartkop { background: #c0392b; color: #fff; font-weight: 800; letter-spacing: 1pt; padding: 4pt 6pt;
            border-radius: 3px; margin-bottom: 5pt; font-size: 9.5pt; }
.kaartkop.klein-kop { background: #30363f; margin-top: 8pt; }
ol.kort, ul.kort { margin: 0 0 6pt; padding-left: 13pt; }
ol.kort li, ul.kort li { margin: 1pt 0; }
table.methane { font-size: 8.2pt; margin: 0; }
table.methane td { padding: 2.5pt 4pt; background: #fff !important; font-weight: normal; }
table.methane td.letter { width: 16pt; text-align: center; font-weight: 800; font-size: 12pt; color: #c0392b;
                          vertical-align: middle; }
table.methane span { color: #5b6573; }
table.klein-invul { font-size: 8.2pt; margin: 0; }
table.klein-invul th { width: 46%; }
table.klein-invul td { height: 18pt; }
table.invul th { width: 42%; background: #f4f6f8; font-weight: 600; }
table.invul td { height: 22pt; font-weight: normal; color: #5b6573; background: #fff !important; }
table.posten th { background: #30363f; color: #fff; width: auto; }
table.posten td:first-child { font-weight: 600; color: #1d2530; }
"""


def bouw_html(merktekens, paginas=None):
    md_tekst = open(os.path.join(DOCS, D["bron"]), encoding="utf-8").read()
    datum, kort = versie()
    # inleiding = alles tot de eerste '---'
    kop_eind = md_tekst.index("\n---")
    inl_md, rest_md = md_tekst[:kop_eind], md_tekst[kop_eind:]
    inl_html, _ = inhoud(inl_md, False)
    rest_html, hoofdstukken = inhoud("# x\n" + rest_md, merktekens)
    achter = globals()[D["achterblad"]]()
    m = re.search(r'<h2 id="([^"]+)">([^<]+)</h2>', achter)
    hoofdstukken.append((m.group(1), m.group(2)))

    toc = "".join('<li><a href="#%s">%s</a><span class="nr">%s</span></li>'
                  % (i, t, (paginas or {}).get(i, "00")) for i, t in hoofdstukken)
    versietekst = "Versie %s%s" % (datum, (" &middot; %s" % kort) if kort else "")
    voorblad = """
<section class="voorblad"><div class="streep"></div>
<div class="label">%s</div>
<h1>%s</h1>
<div class="sub">%s</div>
<div class="schema-voor"><img src="%s" alt=""></div>
<div class="onder">
  <div><strong>Gert de Haan, PD3PAM</strong><br>%s<br>De nieuwste versie staat altijd op GitHub.</div>
  <div class="qrs">
    <div class="qr"><img src="%s" alt="">Website</div>
    <div class="qr"><img src="%s" alt="">%s</div>
  </div>
</div></section>""" % (D["label"], D["titel"], D["sub"], afbeelding(D["voorblad"]), versietekst, qr_svg(WEBSITE),
                       qr_svg(GITHUB + D["bron"]), D["qr2"])

    inleiding = """
<section class="inhoudsopgave inhoud%s"><h2>Inhoud</h2><ul class="toc">%s</ul></section>
<section class="inleiding inhoud"><h2>Voor je begint</h2>%s
<p class="klein">Website: <a href="%s">noodnet.ied.nl</a> &middot; nieuwste versie:
<a href="%s">github.com/ieddev/noodnet</a> &middot; Licentie: CC BY-SA 4.0.</p>
</section>""" % ("" if D["inhoud_eigen_pagina"] else " samen", toc, inl_html, WEBSITE, GITHUB + D["bron"])

    kop = "<!doctype html><html lang='nl'><head><meta charset='utf-8'><title>%s</title><style>%s</style></head><body>" % (D["pdftitel"], CSS)
    return (kop.replace("</style>", "@page { margin: 0; }</style>") + voorblad + "</body></html>",
            kop + "%s<main>%s</main>%s</body></html>" % (inleiding, rest_html, achter), versietekst, hoofdstukken)


def naar_pdf(html, versietekst, pad, voettekst=True):
    voet = ("<div style='font-family:Helvetica,Arial,sans-serif;font-size:7.5pt;color:#5b6573;width:100%%;"
            "padding:0 16mm;display:flex;justify-content:space-between'>"
            "<span>Noodnet &middot; %s &middot; %s</span>"
            "<span>pagina <span class='pageNumber'></span> van <span class='totalPages'></span></span></div>"
            % (D["voettitel"], versietekst))
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.set_content(html, wait_until="networkidle")
        pg.pdf(path=pad, format="A4", print_background=True, prefer_css_page_size=True,
               display_header_footer=voettekst, header_template="<span></span>", footer_template=voet)
        b.close()


def maak():
    UIT = os.path.join(DOCS, D["uit"])
    # voorblad zonder voettekst; de rest genummerd vanaf 1 (het voorblad telt niet mee)
    tijdelijk = UIT + ".tmp"
    _, html, vt, hoofdstukken = bouw_html(True)
    naar_pdf(html, vt, tijdelijk)
    # paginanummer per hoofdstuk: de eerste pagina (na de inhoud) met een regel die precies de kop is
    # (in de inhoudsopgave staat nu '00' achter elke kop, dus die regels tellen niet mee)
    paginas, start = {}, 1
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
    w.add_metadata({"/Title": D["pdftitel"], "/Author": "Gert de Haan, PD3PAM"})
    with open(UIT, "wb") as fh:
        w.write(fh)
    os.remove(tijdelijk); os.remove(tijdelijk + ".voor")
    print("klaar:", UIT, "-", len(w.pages), "pagina's;", "inhoud:", paginas)


def main():
    global D
    for naam in (sys.argv[1:] or DOCUMENTEN):
        D = DOCUMENTEN[naam]
        maak()


if __name__ == "__main__":
    main()

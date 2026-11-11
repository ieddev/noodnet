// Noodnet – technische presentatie (techniekavond), pptxgenjs, zelfde stijl als maak_presentatie.js
//
//   cd docs/presentatie && node maak_techniek.js   ->  Noodnet-techniek.pptx
//
// Alle technische waarden komen uit de code (noodnet_proto.py, steunpunt_brug.py, netwerken/voorbeeld.json).
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");
let applyTheme = null;
try { applyTheme = require(process.env.APPLY_THEME || "./apply_theme.js").applyTheme; } catch (e) { /* zonder thema */ }

const NAAM = "Gert de Haan, PD3PAM";
const THEME = {
  name: "Noodnet", headFontFace: "Calibri", bodyFontFace: "Calibri",
  colors: { dk1: "1D2530", lt1: "FFFFFF", dk2: "2B313A", lt2: "F4F6F8", accent1: "C0392B", accent2: "1E8449",
            accent3: "D35400", accent4: "2471A3", accent5: "5B6573", accent6: "F1C40F", hlink: "2471A3", folHlink: "5B6573" },
};
const HEX = THEME.colors;
const MONO = "Consolas";

async function icoon(Icon, kleur, px = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Icon, { color: "#" + kleur, size: px }));
  return "image/png;base64," + (await sharp(Buffer.from(svg)).png().toBuffer()).toString("base64");
}

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.title = "Noodnet – de techniek";
  pres.subject = "Reticulum en LXMF op LoRa, AX.25 op 2 meter: hoe Noodnet werkt";
  pres.author = NAAM;
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;

  pres.defineSlideMaster({
    title: "TITEL_DONKER", background: { color: C.text1 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.4, w: 6.4, h: 1.2, fontSize: 44, bold: true,
          color: C.background1, valign: "bottom", margin: 0 }, text: "" } },
      { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 2.75, w: 6.4, h: 0.8, fontSize: 20,
          color: C.background2, valign: "top", margin: 0 }, text: "" } },
    ],
  });
  pres.defineSlideMaster({
    title: "INHOUD", background: { color: C.background1 }, margin: [0.5, 0.5, 0.6, 0.5],
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9.0, h: 0.7, fontSize: 28, bold: true,
          color: C.text1, valign: "middle", margin: 0 }, text: "" } },
      { text: { text: "Noodnet · de techniek · " + NAAM, options: { x: 0.5, y: 5.25, w: 6, h: 0.25, fontSize: 10, color: C.accent5, margin: 0 } } },
    ],
    slideNumber: { x: 9.0, y: 5.25, w: 0.5, h: 0.25, fontSize: 10, color: C.accent5, align: "right" },
  });

  const I = {};
  const iconen = { tower: fa.FaBroadcastTower, check: fa.FaCheckCircle, lock: fa.FaLock, eye: fa.FaEye, users: fa.FaUsers,
    code: fa.FaCode, plug: fa.FaPlug, mobile: fa.FaMobileAlt, redo: fa.FaRedo, layer: fa.FaLayerGroup, key: fa.FaKey,
    qrcode: fa.FaQrcode, server: fa.FaServer, desktop: fa.FaDesktop, file: fa.FaFileCode, download: fa.FaDownload,
    exclam: fa.FaExclamationTriangle, puzzle: fa.FaPuzzlePiece, globe: fa.FaGlobeEurope, envelope: fa.FaEnvelope,
    github: fa.FaGithub, user: fa.FaUserCheck, bolt: fa.FaBolt };
  for (const [k, v] of Object.entries(iconen)) I[k] = await icoon(v, "FFFFFF");

  function rondIcoon(s, naam, x, y, d, kleur) {
    s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: kleur }, line: { color: kleur }, objectName: "cirkel " + naam });
    const m = d * 0.24;
    s.addImage({ data: I[naam], x: x + m, y: y + m, w: d - 2 * m, h: d - 2 * m, objectName: "icoon " + naam });
  }
  function tekst(s, t, o) { s.addText(t, Object.assign({ isTextBox: true, margin: 0, color: C.text1, fontSize: 14 }, o)); }
  function punten(s, lijst, o) {
    s.addText(lijst.map((p, j) => (typeof p === "string" ? { text: p, options: { bullet: true, breakLine: j < lijst.length - 1 } }
      : { text: p[0], options: Object.assign({ bullet: true, breakLine: j < lijst.length - 1 }, p[1]) })),
      Object.assign({ isTextBox: true, fontSize: 14, color: C.text1, valign: "top", paraSpaceAfter: 6, margin: 0 }, o));
  }
  function kaartjes(s, items, x0, y0, kolommen, bw, bh, gx, gy, fs = 12.5) {
    items.forEach(([ic, kop, t], i) => {
      const x = x0 + (i % kolommen) * (bw + gx), y = y0 + Math.floor(i / kolommen) * (bh + gy);
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: bw, h: bh, rectRadius: 0.1, fill: { color: C.background2 }, line: { color: C.background2 }, objectName: "kaart " + kop });
      rondIcoon(s, ic, x + 0.2, y + 0.2, 0.55, C.accent1);
      tekst(s, kop, { x: x + 0.9, y: y + 0.18, w: bw - 1.05, h: 0.35, fontSize: 15, bold: true, objectName: "kop " + kop });
      tekst(s, t, { x: x + 0.9, y: y + 0.55, w: bw - 1.05, h: bh - 0.65, fontSize: fs, valign: "top", objectName: "tekst " + kop });
    });
  }
  function tabel(s, rijen, o, kolw) {
    const kop = rijen[0].map(t => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: HEX.dk2 } } }));
    const rest = rijen.slice(1).map((r, i) => r.map((t, j) => ({ text: t, options: {
      fill: { color: i % 2 ? HEX.lt2 : "FFFFFF" }, bold: j === 0, fontFace: (o.mono || []).includes(j) ? MONO : undefined } })));
    s.addTable([kop, ...rest], Object.assign({ fontSize: 12, color: HEX.dk1, border: { type: "solid", pt: 0.5, color: "C9D1DB" },
      margin: [3, 5, 3, 5], colW: kolw, valign: "middle" }, o.opts));
  }
  function code(s, regels, x, y, w, h, fs = 10) {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.06, fill: { color: HEX.dk1 }, line: { color: HEX.dk1 }, objectName: "codeblok" });
    s.addText(regels.map((r, i) => ({ text: r[0], options: { color: r[1] || "E8ECEF", breakLine: i < regels.length - 1 } })),
      { isTextBox: true, x: x + 0.15, y: y + 0.1, w: w - 0.3, h: h - 0.2, fontFace: MONO, fontSize: fs, valign: "top", margin: 0,
        paraSpaceAfter: 3, objectName: "code" });
  }

  // ---------- 1. Titel ----------
  pres.addSection({ title: "Inleiding" });
  let s = pres.addSlide({ masterName: "TITEL_DONKER", sectionTitle: "Inleiding" });
  s.addText("Noodnet – de techniek", { placeholder: "title" });
  s.addText("Reticulum en LXMF op LoRa, AX.25 op 2 meter", { placeholder: "body" });
  rondIcoon(s, "tower", 7.3, 1.5, 2.0, C.accent1);
  tekst(s, NAAM, { x: 0.6, y: 4.2, w: 6, h: 0.35, fontSize: 14, bold: true, color: C.background1, objectName: "naam" });
  tekst(s, "Techniekavond · van een melding op straat tot het scherm van de hulpdienst", { x: 0.6, y: 4.6, w: 7, h: 0.35, fontSize: 13, color: C.background2, objectName: "ondertitel" });
  s.addNotes("Vanavond geen demonstratie met apparatuur, maar een kijkje onder de motorkap: welke protocollen Noodnet gebruikt, waarom juist deze, en hoe een melding van de telefoon van een vrijwilliger op het scherm van de hulpdienst komt.");

  // ---------- 2. Ontwerpeisen ----------
  s = pres.addSlide({ masterName: "INHOUD", sectionTitle: "Inleiding" });
  s.addText("Wat het moet kunnen", { placeholder: "title" });
  kaartjes(s, [
    ["bolt", "Geen infrastructuur", "Geen stroomnet, internet of mobiel netwerk. Alles op accu, met eigen wifi."],
    ["check", "Altijd bevestigd", "Elke melding wordt bevestigd door de ontvanger; anders wordt hij herhaald."],
    ["eye", "Leesbaar op 2 meter", "Geen versleuteling op de amateurband: iedereen met een packet-decoder kan meelezen."],
    ["user", "Alleen bevoegden", "Vrijwilligers melden zich aan en worden goedgekeurd. Anderen komen er niet in."],
    ["users", "Leek-proof", "Vrijwilliger: één app. Zendamateur: één installatie-opdracht en een webpagina."],
    ["code", "Open source", "Alles op GitHub (EUPL). Elke gemeente kan het zelf opzetten."]],
    0.5, 1.2, 3, 2.85, 1.85, 0.2, 0.2, 12);
  s.addNotes("Zes eisen waar alle keuzes uit volgen. Vooral de tweede en derde zijn bepalend: een melding moet aantoonbaar aankomen, en op de amateurband mag niets versleuteld worden.");

  // ---------- 3. Overzicht ----------
  pres.addSection({ title: "Architectuur" });
  s = pres.addSlide({ masterName: "INHOUD", sectionTitle: "Architectuur" });
  s.addText("Drie rollen, twee radionetten", { placeholder: "title" });
  s.addImage({ path: "overzicht.png", x: 0.5, y: 1.05, w: 8.9, h: 8.9 / 2.128, altText: "Overzicht: vrijwilligers melden via LoRa aan Noodsteunpunten; die zenden via 2 meter door naar Eindposten.", objectName: "schema overzicht" });
  s.addNotes("Links de vrijwilliger: Android-telefoon met een RNode via Bluetooth. In het midden het Noodsteunpunt van een zendamateur. Rechts de Eindpost bij de hulpdienst. Groen is LoRa in de ISM-banden, rood is 2 meter packet op de amateurband.");

  // ---------- 4. De keten ----------
  s = pres.addSlide({ masterName: "INHOUD", sectionTitle: "Architectuur" });
  s.addText("De keten, van telefoon tot scherm", { placeholder: "title" });
  const blok = [
    [0.4, "Telefoon", ["Noodnet-app", "(Sideband + patch)", "LXMF / Reticulum"]],
    [2.25, "Steunpunt (Pi)", ["rnsd + RNode(s)", "Noodnet-brug", "Direwolf (KISS)"]],
    [4.1, "2 m-set", ["1200 Bd AFSK", "PTT via CAT/RTS", "Hamlib rigctld"]],
    [5.95, "Eindpost (Pi)", ["Direwolf", "ax25_to_mqtt", "Mosquitto (MQTT)"]],
    [7.8, "Scherm", ["Node-RED", "M/ETHANE + kaart", "logboek"]]];
  blok.forEach(([x, kop, regels], i) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.5, w: 1.75, h: 1.45, rectRadius: 0.1,
      fill: { color: i === 2 ? "FBEEEC" : C.background2 }, line: { color: i === 2 ? HEX.accent1 : "C9D1DB", width: 1 }, objectName: "blok " + kop });
    tekst(s, kop, { x: x + 0.1, y: 1.6, w: 1.55, h: 0.35, fontSize: 14, bold: true, align: "center", objectName: "kop " + kop });
    tekst(s, regels.join("\n"), { x: x + 0.1, y: 2.0, w: 1.55, h: 0.9, fontSize: 11, align: "center", valign: "top", color: C.accent5, objectName: "regels " + kop });
  });
  const pijl = [[2.15, "BT +\nLoRa", HEX.accent2], [4.0, "KISS", HEX.accent5], [5.85, "2 m", HEX.accent1], [7.7, "MQTT", HEX.accent5]];
  pijl.forEach(([x, t, k], i) => {
    s.addShape(pres.shapes.RIGHT_ARROW, { x: x - 0.02, y: 2.22, w: 0.14, h: 0.3, fill: { color: k }, line: { color: k }, objectName: "pijl " + i });
  });
  const lagen = [
    ["Vrijwilliger ↔ steunpunt", "LoRa 434,100 / 869,525 MHz · Reticulum + LXMF · versleuteld, met afleverbewijs", HEX.accent2],
    ["Steunpunt ↔ eindpost", "2 m per gemeente · AX.25 UI-frames · leesbare tekst, roepnaam · eigen ACK", HEX.accent1],
    ["Op de eindpost", "MQTT-bericht per melding → Node-RED-dashboard, kaart (Worldmap) en logboek (txt/csv)", HEX.accent5]];
  lagen.forEach(([kop, t, k], i) => {
    const y = 3.4 + i * 0.55;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.4, y, w: 0.08, h: 0.4, fill: { color: k }, line: { color: k }, objectName: "streep " + i });
    tekst(s, [{ text: kop + "   ", options: { bold: true } }, { text: t }], { x: 0.6, y, w: 8.9, h: 0.4, fontSize: 12.5, valign: "middle", objectName: "laag " + i });
  });
  s.addNotes("Vijf schakels. De telefoon praat LXMF over Reticulum, via Bluetooth naar een RNode en via LoRa naar het steunpunt. Op het steunpunt draait rnsd met de RNodes, de Noodnet-brug die de berichten omzet, en Direwolf als packet-modem. Over 2 meter gaan gewone AX.25 UI-frames. Op de eindpost zet een klein programma de frames om naar MQTT; Node-RED toont ze.");

  // ---------- 5. Waarom twee netten ----------
  s = pres.addSlide({ masterName: "INHOUD", sectionTitle: "Architectuur" });
  s.addText("Waarom twee netten? De regels", { placeholder: "title" });
  tabel(s, [["", "LoRa (ISM-band)", "2 meter (amateurband)"],
            ["Wie zendt", "Iedereen, zonder licentie", "Alleen de zendamateur"],
            ["Versleuteling", "Toegestaan", "Niet toegestaan"],
            ["Identificatie", "Niet verplicht", "Roepnaam verplicht"],
            ["Vermogen / zendtijd", "433: 10 mW · 869,525: 500 mW, 10%", "Volgens de vergunning"],
            ["Bereik", "Enkele km (wijk)", "Tientallen km (gemeente)"]],
        { opts: { x: 0.5, y: 1.2, w: 9.0, fontSize: 13 } }, [2.3, 3.35, 3.35]);
  tekst(s, "Dus: de vrijwilliger (zonder licentie) op LoRa, versleuteld; de zendamateur brengt het als leesbare tekst onder zijn roepnaam over 2 meter.",
    { x: 0.5, y: 3.6, w: 9, h: 0.8, fontSize: 16, italic: true, color: C.accent1, objectName: "kernzin" });
  s.addNotes("Dit is de kern van het ontwerp. Vrijwilligers hebben geen licentie, dus zij zenden in de ISM-banden, waar versleuteling mag. Reticulum is daar ideaal voor. Op de amateurband mag niet versleuteld worden en moet de roepnaam erbij. Daarom geen Reticulum over 2 meter, maar een brug die er leesbare AX.25-frames van maakt. Wie meeluistert met een packet-decoder, kan alles lezen.");

  // ---------- 6. Reticulum & LXMF ----------
  pres.addSection({ title: "LoRa-kant" });
  s = pres.addSlide({ masterName: "INHOUD", sectionTitle: "LoRa-kant" });
  s.addText("Reticulum en LXMF in het kort", { placeholder: "title" });
  tekst(s, "Reticulum (RNS)", { x: 0.5, y: 1.15, w: 4.3, h: 0.4, fontSize: 18, bold: true, color: C.accent1, objectName: "kop RNS" });
  punten(s, ["Elke deelnemer heeft een identiteit (sleutelpaar: X25519 + Ed25519)",
             "Bestemmingen zijn hashes van 16 bytes; geen IP-adressen",
             "Announces maken bestemmingen bekend; paden leren vanzelf",
             "Bewijzen (proofs): de ontvanger bevestigt cryptografisch",
             "Interfaces: RNode (LoRa), TCP, serieel …",
             "IFAC: netwerknaam + wachtwoord; vreemde pakketten worden genegeerd"],
         { x: 0.5, y: 1.6, w: 4.3, h: 3.5, fontSize: 13 });
  tekst(s, "LXMF (berichten)", { x: 5.2, y: 1.15, w: 4.3, h: 0.4, fontSize: 18, bold: true, color: C.accent1, objectName: "kop LXMF" });
  punten(s, ["Berichtenlaag bovenop Reticulum, ondertekend en versleuteld",
             "Afleverbewijs: de telefoon ziet ‘afgeleverd’ als het steunpunt het heeft",
             "Velden voor telemetrie: positie, accu",
             "Kort bericht past in één LoRa-pakket (opportunistic)",
             "De app is Sideband 2.1.0 met een Noodnet-patch: meldscherm M/ETHANE, aanmelden met QR-kaart, baken"],
         { x: 5.2, y: 1.6, w: 4.3, h: 3.5, fontSize: 13 });
  s.addNotes("Reticulum is een netwerkstack zonder IP, gemaakt voor trage en onbetrouwbare verbindingen. Elke deelnemer heeft een sleutelpaar; adressen zijn hashes. Een ontvanger bewijst cryptografisch dat hij een pakket heeft gekregen. Met IFAC, een netwerknaam en wachtwoord, hoort een RNode alleen pakketten van ons eigen netwerk. LXMF is de berichtenlaag erbovenop, met afleverbewijs. De app is Sideband van Mark Qvist, met een kleine patch voor Noodnet.");

  // ---------- 7. LoRa-instellingen ----------
  s = pres.addSlide({ masterName: "INHOUD", sectionTitle: "LoRa-kant" });
  s.addText("LoRa-instellingen en het baken", { placeholder: "title" });
  tabel(s, [["Band", "Frequentie", "Bandbreedte", "SF", "CR", "Vermogen"],
            ["433", "434,100 MHz", "125 kHz", "9", "4/5", "10 dBm (10 mW)"],
            ["868", "869,525 MHz", "125 kHz", "8", "4/5", "14 dBm (max. 500 mW, 10% zendtijd)"]],
        { opts: { x: 0.5, y: 1.2, w: 9.0, fontSize: 13 } }, [0.9, 1.5, 1.4, 0.6, 0.7, 3.9]);
  punten(s, ["Een steunpunt heeft één of twee RNodes; vrijwilligers kiezen hun band bij het aanmelden",
             "De instellingen staan op de aanmeldkaart (QR) en in het netwerkbestand van de gemeente",
             "Baken van de app: positie + accu, bij verplaatsing ≥ 300 m (max. eens per 10 min), anders een levensteken per 30 min",
             "Positie bij een melding alleen als de vrijwilliger ‘Ik ben ter plaatse’ aanvinkt",
             "GPS in de app: eens per 30 s i.p.v. continu (accu)"],
         { x: 0.5, y: 2.45, w: 9.0, h: 2.6, fontSize: 13.5 });
  s.addNotes("De standaardwaarden uit het netwerkbestand. Op 433 MHz mogen we 10 milliwatt, op 869,525 tot 500 milliwatt met tien procent zendtijd. Het baken is zuinig: alleen bij verplaatsing, of af en toe een levensteken. Zo ziet de beheerder waar zijn vrijwilligers zijn, zonder de band vol te zetten.");

  // ---------- 8. Toegang ----------
  s = pres.addSlide({ masterName: "INHOUD", sectionTitle: "LoRa-kant" });
  s.addText("Toegang en beveiliging", { placeholder: "title" });
  kaartjes(s, [
    ["key", "IFAC op LoRa", "Netwerknaam en wachtwoord per gemeente. Zonder kan niemand op ons LoRa-net, ook niet met een eigen RNode."],
    ["qrcode", "Aanmeldkaart", "QR-code met aanmeldcode, LoRa-instellingen en IFAC. Kwijt? Nieuwe code; wie al is aangemeld merkt niets."],
    ["user", "Goedkeuring", "De beheerder keurt elke aanmelding goed (JA/NEE) vanaf zijn telefoon of de beheerpagina."],
    ["lock", "Ondertekend", "Beheeropdrachten alleen van goedgekeurde beheerders, met geldige LXMF-handtekening."],
    ["exclam", "Niet doorgegeven", "Een niet-aangemelde telefoon krijgt antwoord ‘NIET doorgegeven’; zijn melding gaat niet over 2 m."],
    ["eye", "Open op 2 m", "Op de amateurband niets versleuteld: controleerbaar voor iedereen, zoals de regels vragen."]],
    0.5, 1.2, 3, 2.85, 1.85, 0.2, 0.2, 11.5);
  s.addNotes("Drie sloten op de deur. IFAC houdt vreemde LoRa-apparaten buiten. De aanmeldkaart met QR-code is de sleutel voor nieuwe vrijwilligers. En de beheerder keurt elke aanmelding goed. Beheeropdrachten werken alleen vanaf goedgekeurde beheerders met een geldige handtekening. Wie niet is aangemeld, krijgt te horen dat zijn melding niet is doorgegeven, zodat hij een andere weg kiest.");

  // ---------- 9. Het 2 m-protocol ----------
  pres.addSection({ title: "2 m-kant" });
  s = pres.addSlide({ masterName: "INHOUD", sectionTitle: "2 m-kant" });
  s.addText("Het 2 m-protocol: NN1 in AX.25 UI-frames", { placeholder: "title" });
  code(s, [["NN1 <SOORT> <ID> <deel>/<totaal> <sleutel=waarde;…;tekst=…>", "F1C40F"]], 0.5, 1.15, 9.0, 0.42, 11);
  tabel(s, [["Soort", "Betekenis", "ACK?"],
            ["MTH", "M/ETHANE-melding", "ja, nooit opgeven"], ["MSG", "chatbericht", "ja"],
            ["GPS", "positie / telemetrie", "nee"], ["ANN", "telefoon in de lucht", "nee"],
            ["STA", "status steunpunt (elke 30 min)", "nee"], ["ACK", "bevestiging eindpost", "–"]],
        { opts: { x: 0.5, y: 1.75, w: 3.9, fontSize: 11 }, mono: [0] }, [0.75, 2.05, 1.1]);
  code(s, [
    ["PD3PAM-1>APZNN:NN1 MTH 3fa2c1 1/2 van=Jan;", "8FD18F"],
    ["  adr=5c57a1b2e4f09d3c;aan=brandweer,ambulance;", null],
    ["  lat=52.25503;lon=6.16305;nauwk=12;s_rssi=-97;", null],
    ["  s_snr=6.5;tekst=M/ETHANE MELDING\\nGEMELD AAN:", null],
    ["  Brandweer, Ambulance\\nM: Ja, meerdere wo", null],
    ["PD3PAM-1>APZNN:NN1 MTH 3fa2c1 2/2 ningen\\nE: Brink", "8FD18F"],
    ["  10, Deventer\\nT: Brand in woning\\nH: Rook …", null],
    ["", null],
    ["PD3PAM-2>APZNN:NN1 ACK 3fa2c1 1/1", "F5A9A0"]], 4.6, 1.75, 4.9, 2.55, 10);
  s.addNotes("Het protocol heet NN1. Elk frame is een gewoon AX.25 UI-frame naar APZNN, de experimentele bestemming, met leesbare tekst. Na NN1 komen de soort, een ID van zes tekens dat bij herhalingen gelijk blijft, en het deelnummer. Lange berichten worden in stukken van maximaal 200 bytes geknipt. Rechts een echte M/ETHANE in twee frames, en de bevestiging van de eindpost. Bij 1200 baud kost zo'n melding een paar seconden zendtijd.");

  // ---------- 10. Betrouwbaarheid ----------
  s = pres.addSlide({ masterName: "INHOUD", sectionTitle: "2 m-kant" });
  s.addText("Betrouwbaarheid: twee keer bevestigd", { placeholder: "title" });
  const stappen = [["Telefoon", HEX.dk2], ["Steunpunt", HEX.dk2], ["Eindpost", HEX.dk2]];
  stappen.forEach(([t, k], i) => {
    const x = 0.5 + i * 3.25;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.2, w: 2.3, h: 0.55, rectRadius: 0.08, fill: { color: k }, line: { color: k }, objectName: "stap " + t });
    tekst(s, t, { x, y: 1.2, w: 2.3, h: 0.55, fontSize: 15, bold: true, color: C.background1, align: "center", valign: "middle", objectName: "stap tekst " + t });
  });
  tekst(s, "① LXMF-afleverbewijs\n‘afgeleverd’ in de app", { x: 2.45, y: 1.85, w: 1.65, h: 0.5, fontSize: 11, align: "center", color: C.accent2, objectName: "bewijs 1" });
  tekst(s, "② NN1 ACK per eindpost", { x: 5.7, y: 1.85, w: 1.65, h: 0.5, fontSize: 11, align: "center", color: C.accent1, objectName: "bewijs 2" });
  [2.85, 6.1].forEach((x, i) => s.addShape(pres.shapes.RIGHT_ARROW, { x, y: 1.32, w: 0.85, h: 0.3,
    fill: { color: i ? HEX.accent1 : HEX.accent2 }, line: { color: i ? HEX.accent1 : HEX.accent2 }, objectName: "pijl bewijs " + i }));
  punten(s, ["Geen ACK? Herhalen na 30, 60, 120, 240 s, daarna elke 5 min (±25% spreiding tegen botsingen)",
             "M/ETHANE wordt nooit opgegeven en gaat altijd vóór ander verkeer",
             "Per discipline één of meer eindposten; het steunpunt houdt bij wie al bevestigde",
             "Discipline zonder eindpost? Dan naar het vangnet (bijv. gemeente)",
             "Eindpost herkent herhalingen aan het ID: niets dubbel op het scherm",
             "Wachtrij overleeft een herstart; de beheerder kan ‘niet meer wachten’ op een post die er niet is"],
         { x: 0.5, y: 2.5, w: 9.0, h: 2.6, fontSize: 14 });
  s.addNotes("De melding wordt twee keer bevestigd. Eerst krijgt de telefoon een LXMF-afleverbewijs van het steunpunt; de vrijwilliger ziet afgeleverd en hoeft niets meer te doen. Dan stuurt elke eindpost die de melding moet krijgen een ACK over 2 meter. Zolang die er niet is, herhaalt het steunpunt met een oplopende wachttijd en wat willekeurige spreiding, zodat twee steunpunten niet steeds tegelijk zenden. Een M/ETHANE wordt nooit opgegeven.");

  // ---------- 11. Software steunpunt & eindpost ----------
  pres.addSection({ title: "Software" });
  s = pres.addSlide({ masterName: "INHOUD", sectionTitle: "Software" });
  s.addText("Wat draait er op de Pi?", { placeholder: "title" });
  tekst(s, "Steunpunt", { x: 0.5, y: 1.15, w: 4.3, h: 0.4, fontSize: 18, bold: true, color: C.accent1, objectName: "kop steunpunt" });
  punten(s, ["Raspberry Pi 4/5, Raspberry Pi OS (Trixie)", "rnsd (gedeelde instantie) met 1–2 RNodes",
             "Noodnet-brug (Python): LXMF ↔ NN1, wachtrij, aanmeldingen, beheeropdrachten",
             "Direwolf als modem (KISS, poort 8001)", "Hamlib rigctld: frequentie, mode en vermogen via CAT, bewaakt",
             "Beheerpagina (Python) op poort 8080, via eigen hotspot (hostapd + dnsmasq, 10.42.0.1)",
             "Offline kaart (PDOK) met posities (Leaflet)"],
         { x: 0.5, y: 1.6, w: 4.3, h: 3.5, fontSize: 12.5 });
  tekst(s, "Eindpost", { x: 5.2, y: 1.15, w: 4.3, h: 0.4, fontSize: 18, bold: true, color: C.accent1, objectName: "kop eindpost" });
  punten(s, ["Raspberry Pi 4/5 met bureaublad", "Direwolf + rigctld, zelfde set-instellingen",
             "ax25_to_mqtt (Python): frames samenvoegen, ACK sturen, dubbele herkennen, logboek",
             "Mosquitto (MQTT) als doorgeefluik", "Node-RED: M/ETHANE-scherm (dashboard) en kaart (Worldmap)",
             "Beheerpagina op poort 8080, eigen hotspot", "Alles als systemd-diensten, met bewakers"],
         { x: 5.2, y: 1.6, w: 4.3, h: 3.5, fontSize: 12.5 });
  s.addNotes("Beide rollen draaien op een Raspberry Pi 4 of 5. Alles is gewone open-source software, aan elkaar geknoopt met een paar Python-programma's en systemd. Een Pi 3 is te zwak: de USB trekt de set plus twee RNodes niet.");

  // ---------- 12. Netwerkbestand ----------
  s = pres.addSlide({ masterName: "INHOUD", sectionTitle: "Software" });
  s.addText("Eén netwerkbestand per gemeente", { placeholder: "title" });
  code(s, [
    ["{ \"gemeente\": \"Gemeente Deventer\",", null],
    ["  \"disciplines\": {", null],
    ["    \"brandweer\": { \"eindposten\": [] },", null],
    ["    \"gemeente\":  { \"eindposten\": [\"PD3PAM-5\"] }, … },", null],
    ["  \"vangnet\": [\"gemeente\"],", null],
    ["  \"lora\": { \"433\": { \"frequentie\": 434100000, \"sf\": 9 … } },", null],
    ["  \"baken\": { \"min_interval_s\": 600, \"afstand_m\": 300 … },", null],
    ["  \"frequentie_2m\": 144925000,", "F1C40F"],
    ["  \"versie\": … }", "F1C40F"]], 0.5, 1.2, 5.7, 2.9, 9.5);
  punten(s, ["Een supervisor maakt het; elk steunpunt en elke eindpost laadt het (bestand of link)",
             "Wie meldt aan welke eindpost, met vangnet",
             "2 m-frequentie per gemeente op het 12,5 kHz-raster; buurgemeenten 25 kHz uit elkaar",
             "Versienummer: zo zie je of iedereen hetzelfde heeft",
             "IFAC zit er niet in de openbare versie in"],
         { x: 6.45, y: 1.2, w: 3.1, h: 3.9, fontSize: 12.5 });
  s.addNotes("Alles wat per gemeente verschilt, staat in één JSON-bestand: welke eindposten er zijn per discipline, het vangnet, de LoRa-instellingen en de 2 meter-frequentie. Een supervisor maakt het en deelt het; elke Pi laadt het met een paar tikken. Het IFAC-wachtwoord gaat apart, zodat het bestand openbaar kan.");

  // ---------- 13. Installatie ----------
  s = pres.addSlide({ masterName: "INHOUD", sectionTitle: "Software" });
  s.addText("Installeren en beheren zonder Linux-kennis", { placeholder: "title" });
  code(s, [["bash <(curl -sL https://raw.githubusercontent.com/ieddev/noodnet/main/installeer.sh)", "8FD18F"]], 0.5, 1.15, 9.0, 0.45, 11);
  kaartjes(s, [
    ["download", "Eén opdracht", "Kies steunpunt of eindpost; de rest gaat vanzelf. Bijwerken: noodnet-bijwerken."],
    ["plug", "Zoek mijn set", "Herkent de set via USB en zet CAT goed (o.a. Icom IC-9700/705/7100, Yaesu FT-991/817/857, Kenwood TS-2000)."],
    ["mobile", "Beheer met de telefoon", "Via de eigen wifi: status, radio, netwerk, vrijwilligers, kaart, back-up, uitzetten."],
    ["check", "Testplan en handleidingen", "Testplan om af te vinken; procedure, beheerder- en vrijwilligershandleiding als PDF."]],
    0.5, 1.8, 2, 4.4, 1.5, 0.2, 0.2, 12);
  s.addNotes("De installatie is één regel. Daarna gaat alles via de beheerpagina op de telefoon: radio instellen, met automatische herkenning van de set, het netwerkbestand laden, vrijwilligers goedkeuren. Er is een testplan met scenario's en er zijn handleidingen voor elke rol.");

  // ---------- 14. Grenzen ----------
  pres.addSection({ title: "Afsluiting" });
  s = pres.addSlide({ masterName: "INHOUD", sectionTitle: "Afsluiting" });
  s.addText("Eerlijk: de grenzen", { placeholder: "title" });
  punten(s, ["LoRa-bereik is enkele kilometers: genoeg steunpunten nodig, hoog opgesteld",
             "1200 baud is traag: prima voor korte, gestructureerde meldingen, niet voor bestanden of foto's",
             "Alleen Android; de app is afgeleid van Sideband (CC BY-NC-SA): gratis, nooit commercieel",
             "Positie alleen als de melder ter plaatse is; adressen worden (offline) niet omgezet naar de kaart",
             "Afhankelijk van mensen: getrainde vrijwilligers en bemande steunpunten",
             "Nog in de testfase: pilots moeten uitwijzen wat werkt"],
         { x: 0.5, y: 1.2, w: 9.0, h: 3.9, fontSize: 15, paraSpaceAfter: 9 });
  s.addNotes("Geen systeem doet alles. LoRa heeft een beperkt bereik, 1200 baud is traag, en de app werkt alleen op Android. Het belangrijkste: het blijft mensenwerk. De techniek zorgt dat een melding aankomt; de mensen zorgen dat er een goede melding is.");

  // ---------- 15. Naast andere systemen ----------
  s = pres.addSlide({ masterName: "INHOUD", sectionTitle: "Afsluiting" });
  s.addText("Naast andere systemen, niet in plaats van", { placeholder: "title" });
  kaartjes(s, [
    ["puzzle", "Een eigen niche", "Gestructureerde meldingen (M/ETHANE) van getrainde burgers naar de hulpdienst, met bevestiging."],
    ["layer", "Combineerbaar", "Spraaknet voor overleg, Winlink of APRS voor regionaal verkeer: Noodnet doet de laatste kilometer in de wijk."],
    ["code", "Bouwstenen delen", "Reticulum, Direwolf, Hamlib, Node-RED: wie die al gebruikt, herkent alles."],
    ["users", "Samen oefenen", "De waarde blijkt pas in een oefening met hulpdiensten en vrijwilligers."]],
    0.5, 1.2, 2, 4.4, 1.75, 0.2, 0.25, 12.5);
  s.addNotes("Noodnet hoeft niet te winnen van MeshCore, Winlink of een spraaknet. Elk heeft zijn eigen sterke kant. Noodnet richt zich op één ding: een gestructureerde melding van een getrainde burger, aantoonbaar bij de hulpdienst. Het combineert prima met een spraaknet voor overleg en met Winlink of APRS voor verkeer over grotere afstand.");

  // ---------- 16. Meedoen ----------
  s = pres.addSlide({ masterName: "TITEL_DONKER", sectionTitle: "Afsluiting" });
  s.addText("Vragen? Meedoen?", { placeholder: "title" });
  s.addText(NAAM, { placeholder: "body" });
  [["globe", "noodnet.ied.nl"], ["envelope", "ieddev@gmail.com"], ["github", "github.com/ieddev/noodnet (EUPL)"]].forEach(([ic, t], i) => {
    const y = 3.55 + i * 0.5;
    s.addImage({ data: I[ic], x: 0.6, y: y + 0.05, w: 0.3, h: 0.3, objectName: "icoon " + ic });
    tekst(s, t, { x: 1.1, y, w: 5.6, h: 0.4, fontSize: 16, color: C.background1, valign: "middle", objectName: "contact " + ic });
  });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 7.15, y: 1.55, w: 2.3, h: 2.3, rectRadius: 0.1, fill: { color: "FFFFFF" }, line: { color: "FFFFFF" }, objectName: "qr achtergrond" });
  s.addImage({ path: "qr-github.png", x: 7.25, y: 1.65, w: 2.1, h: 2.1, altText: "QR-code naar github.com/ieddev/noodnet", objectName: "qr github" });
  tekst(s, "Code, handleidingen en testplan", { x: 7.0, y: 3.95, w: 2.6, h: 0.3, fontSize: 11, color: C.background2, align: "center", objectName: "qr uitleg" });
  s.addNotes("Alles staat op GitHub: de software, de handleidingen en het testplan. Zendamateurs die een steunpunt of eindpost willen opzetten, zijn welkom. Scan de QR-code of kijk op de website.");

  await pres.writeFile({ fileName: "Noodnet-techniek.pptx" });
  if (applyTheme) await applyTheme("Noodnet-techniek.pptx", THEME);
  console.log("klaar");
})();

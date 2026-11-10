// Noodnet – presentatie voor gemeenten en hulpdiensten (pptxgenjs, gestructureerd)
//
//   cd docs/presentatie && node maak_presentatie.js
//   -> Noodnet-presentatie.pptx (daarna eventueel naar PDF met LibreOffice)
//
// Nodig: pptxgenjs, react, react-dom, react-icons, sharp (npm install ...).
// De thema-kleuren worden na het schrijven in het bestand gezet met apply_theme.js
// (pad via de omgevingsvariabele APPLY_THEME; zonder dat blijven de standaard Office-kleuren staan).
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");
let applyTheme = null;
try { applyTheme = require(process.env.APPLY_THEME || "./apply_theme.js").applyTheme; } catch (e) { /* zonder thema */ }

const NAAM = "Gert de Haan, PD3PAM";
const WEBSITE = "noodnet.ied.nl";
const EMAIL = "ieddev@gmail.com";
const GITHUB = "github.com/ieddev/noodnet";

const THEME = {
  name: "Noodnet",
  headFontFace: "Calibri",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1D2530", lt1: "FFFFFF", dk2: "2B313A", lt2: "F4F6F8",
    accent1: "C0392B", accent2: "1E8449", accent3: "D35400", accent4: "2471A3",
    accent5: "5B6573", accent6: "F1C40F", hlink: "2471A3", folHlink: "5B6573",
  },
};
const HEX = THEME.colors;

async function icoon(Icon, kleur, px = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Icon, { color: "#" + kleur, size: px }));
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9"; // 10 x 5.625
  pres.title = "Noodnet";
  pres.subject = "Noodnet: een noodnet van zendamateurs en getrainde vrijwilligers";
  pres.author = NAAM;
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;

  // ---------- Layouts ----------
  pres.defineSlideMaster({
    title: "TITEL_DONKER",
    background: { color: C.text1 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.55, w: 6.2, h: 1.1, fontSize: 48, bold: true,
          color: C.background1, valign: "bottom", margin: 0 }, text: "" } },
      { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 2.8, w: 6.2, h: 0.6, fontSize: 20,
          color: C.background2, valign: "top", margin: 0 }, text: "" } },
    ],
  });
  pres.defineSlideMaster({
    title: "INHOUD",
    background: { color: C.background1 },
    margin: [0.5, 0.5, 0.6, 0.5],
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9.0, h: 0.7, fontSize: 30, bold: true,
          color: C.text1, valign: "middle", margin: 0 }, text: "" } },
      { text: { text: "Noodnet · " + NAAM, options: { x: 0.5, y: 5.25, w: 5, h: 0.25, fontSize: 10, color: C.accent5, margin: 0 } } },
    ],
    slideNumber: { x: 9.0, y: 5.25, w: 0.5, h: 0.25, fontSize: 10, color: C.accent5, align: "right" },
  });

  // Iconen
  const I = {};
  const lijst = { bolt: fa.FaBolt, wifi: fa.FaWifi, signal: fa.FaSignal, tower: fa.FaBroadcastTower, check: fa.FaCheckCircle,
    battery: fa.FaCarBattery, comment: fa.FaCommentDots, code: fa.FaCode, users: fa.FaUsers, handshake: fa.FaHandshake,
    map: fa.FaMapMarkerAlt, run: fa.FaRunning, chat: fa.FaComments, mic: fa.FaMicrophoneAlt, arrow: fa.FaArrowRight,
    shield: fa.FaShieldAlt, envelope: fa.FaEnvelope, globe: fa.FaGlobeEurope, building: fa.FaBuilding,
    usercheck: fa.FaUserCheck, bell: fa.FaBell, mapped: fa.FaMapMarkedAlt, desktop: fa.FaDesktop };
  for (const [k, v] of Object.entries(lijst)) {
    I[k] = await icoon(v, "FFFFFF");
    I[k + "_rood"] = await icoon(v, HEX.accent1);
  }

  function rondIcoon(slide, naam, x, y, d, kleur) {
    slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: kleur }, line: { color: kleur }, objectName: "cirkel " + naam });
    const m = d * 0.24;
    slide.addImage({ data: I[naam], x: x + m, y: y + m, w: d - 2 * m, h: d - 2 * m, objectName: "icoon " + naam });
  }
  function tekst(slide, t, o) { slide.addText(t, Object.assign({ isTextBox: true, margin: 0, color: C.text1, fontSize: 14 }, o)); }
  function punten(slide, lijst, o) {
    slide.addText(lijst.map((p, j) => ({ text: p, options: { bullet: true, breakLine: j < lijst.length - 1 } })),
      Object.assign({ isTextBox: true, fontSize: 14, color: C.text1, valign: "top", paraSpaceAfter: 7, margin: 0 }, o));
  }

  // Een eenvoudig getekend kaartje (geen echte kaart): wegen, water en stippen
  function kaartje(slide, x, y, w, h, stippen, naam) {
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: "E9EDE4" },
      line: { color: "C9D1DB", width: 1 }, objectName: "kaartje " + naam });
    slide.addShape(pres.shapes.LINE, { x: x + 0.15, y: y + h * 0.78, w: w - 0.3, h: -h * 0.35, line: { color: "A9C8E8", width: 7 }, objectName: "water " + naam });
    [[0.08, 0.30, 0.84, 0.05], [0.10, 0.62, 0.80, -0.10], [0.35, 0.08, 0.10, 0.84], [0.70, 0.10, -0.12, 0.80]].forEach(([a, b, c, d], i) =>
      slide.addShape(pres.shapes.LINE, { x: x + a * w, y: y + b * h, w: c * w, h: d * h, line: { color: "FFFFFF", width: 4 }, objectName: `weg ${i} ${naam}` }));
    stippen.forEach(([sx, sy, kleur, d, vorm, label], i) => {
      const cx = x + sx * w, cy = y + sy * h;
      slide.addShape(vorm === "vierkant" ? pres.shapes.RECTANGLE : pres.shapes.OVAL,
        { x: cx - d / 2, y: cy - d / 2, w: d, h: d, fill: { color: kleur }, line: { color: "FFFFFF", width: 1.5 }, objectName: `stip ${i} ${naam}` });
      if (label) tekst(slide, label, { x: cx + d / 2 + 0.04, y: cy - 0.11, w: 1.3, h: 0.22, fontSize: 9, bold: vorm === "vierkant",
        color: C.text1, objectName: `label ${i} ${naam}` });
    });
  }

  // ---------- 1. Titel ----------
  pres.addSection({ title: "Inleiding" });
  let s = pres.addSlide({ masterName: "TITEL_DONKER", sectionTitle: "Inleiding" });
  s.addText("Noodnet", { placeholder: "title" });
  s.addText("Als alles uitvalt, komen meldingen toch aan", { placeholder: "body" });
  rondIcoon(s, "tower", 7.3, 1.6, 2.0, C.accent1);
  tekst(s, NAAM, { x: 0.6, y: 4.2, w: 6, h: 0.35, fontSize: 14, bold: true, color: C.background1, objectName: "naam" });
  tekst(s, "Een noodnet van zendamateurs en getrainde vrijwilligers", { x: 0.6, y: 4.6, w: 7, h: 0.35, fontSize: 14, color: C.background2, objectName: "ondertitel" });
  s.addNotes("Noodnet zorgt dat meldingen uit de wijken bij de hulpdiensten aankomen, ook als stroom, internet en het mobiele netwerk zijn uitgevallen. Het is een initiatief van zendamateurs, samen met getrainde vrijwilligers.");

  // ---------- 2. Het probleem ----------
  s = pres.addSlide({ masterName: "INHOUD", sectionTitle: "Inleiding" });
  s.addText("Als alles uitvalt, zijn de hulpdiensten blind", { placeholder: "title" });
  const probl = [["bolt", "Geen stroom", "Bij een grote storing valt de stroom in hele wijken weg."],
                 ["wifi", "Geen internet", "Zonder stroom valt ook internet weg, en daarmee e-mail en apps."],
                 ["signal", "Geen mobiel netwerk", "Zendmasten hebben maar een paar uur noodstroom; daarna is er geen bereik."]];
  probl.forEach(([ic, kop, t], i) => {
    const x = 0.5 + i * 3.1;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.3, w: 2.8, h: 2.75, rectRadius: 0.12, fill: { color: C.background2 }, line: { color: C.background2 }, objectName: "kaart " + kop });
    rondIcoon(s, ic, x + 0.3, 1.55, 0.8, C.accent1);
    tekst(s, kop, { x: x + 0.3, y: 2.55, w: 2.3, h: 0.4, fontSize: 18, bold: true, objectName: "kop " + kop });
    tekst(s, t, { x: x + 0.3, y: 3.0, w: 2.3, h: 0.95, fontSize: 14, valign: "top", objectName: "tekst " + kop });
  });
  tekst(s, "Juist dan moeten de hulpdiensten weten wat er in de wijken gebeurt.", { x: 0.5, y: 4.35, w: 9, h: 0.45, fontSize: 18, italic: true, color: C.accent1, objectName: "kernzin" });
  s.addNotes("Bij een langdurige stroomstoring vallen stroom, internet en mobiel netwerk vrijwel tegelijk weg. Zendmasten hebben meestal maar een beperkte noodstroom. De hulpdiensten weten dan niet meer wat er in de wijken speelt: waar brand is, waar gewonden zijn, welke wegen geblokkeerd zijn.");

  // ---------- 3. Bestaande oplossingen ----------
  s = pres.addSlide({ masterName: "INHOUD", sectionTitle: "Inleiding" });
  s.addText("Bestaande oplossingen schieten tekort", { placeholder: "title" });
  const kolom = [
    ["chat", "Mesh-netwerken", "bijv. MeshCore", ["Gemaakt voor chat tussen mensen", "Geen garantie dat een melding aankomt", "Raakt verstopt als iedereen zendt"], false],
    ["mic", "Spraaknet", "2 m en 70 cm", ["Elke melding verstaan en overschrijven", "Fouten door slechte verstaanbaarheid", "Alle druk bij de zendamateur"], false],
    ["check", "Noodnet", "digitaal, met bevestiging", ["Tekst komt letterlijk aan", "Elke melding bevestigd, anders herhaald", "Triage door getrainde vrijwilligers"], true]];
  kolom.forEach(([ic, kop, sub, pnt, hl], i) => {
    const x = 0.5 + i * 3.1;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.25, w: 2.8, h: 3.75, rectRadius: 0.12,
      fill: hl ? { color: C.accent1, transparency: 88 } : { color: C.background2 }, line: hl ? { color: C.accent1, width: 1.5 } : { color: C.background2 }, objectName: "kolom " + kop });
    rondIcoon(s, ic, x + 0.3, 1.5, 0.7, hl ? C.accent1 : C.accent5);
    tekst(s, kop, { x: x + 1.15, y: 1.52, w: 1.6, h: 0.38, fontSize: 18, bold: true, objectName: "kop " + kop });
    tekst(s, sub, { x: x + 1.15, y: 1.9, w: 1.6, h: 0.3, fontSize: 12, color: C.accent5, objectName: "sub " + kop });
    punten(s, pnt, { x: x + 0.25, y: 2.5, w: 2.4, h: 2.3, paraSpaceAfter: 8, objectName: "punten " + kop });
  });
  s.addNotes("Er zijn twee soorten initiatieven. Mesh-netwerken zoals MeshCore zijn laagdrempelig, maar gemaakt voor chat en niet voor gegarandeerde noodmeldingen; bij veel verkeer raken ze verstopt. Spraaknetten via 2 meter en 70 centimeter zijn beproefd, maar alle druk ligt bij de zendamateur, en fouten door slechte verstaanbaarheid liggen op de loer. Noodnet combineert het beste: digitaal, met bevestiging, en het werk ligt bij de mensen die daarvoor getraind zijn.");

  // ---------- 4. Overzicht ----------
  pres.addSection({ title: "Hoe het werkt" });
  s = pres.addSlide({ masterName: "INHOUD", sectionTitle: "Hoe het werkt" });
  s.addText("Zo loopt een melding", { placeholder: "title" });
  s.addImage({ path: "overzicht.png", x: 0.5, y: 1.05, w: 8.9, h: 8.9 / 2.128, altText: "Overzicht: vrijwilligers met telefoon en RNode melden via LoRa aan Noodsteunpunten; die zenden via 2 meter door naar Eindposten bij brandweer, gemeentehuis en ziekenhuis.", objectName: "schema overzicht" });
  s.addNotes("Links de vrijwilligers met hun telefoon en een kleine LoRa-zender. In het midden de Noodsteunpunten van zendamateurs. Rechts de Eindposten bij de hulpdiensten. Groen is LoRa, vrij te gebruiken frequenties over enkele kilometers. Rood is de 2 meter-amateurband, over grotere afstanden; elke gemeente heeft een eigen frequentie. De Eindpost bevestigt elke melding; zonder bevestiging herhaalt het steunpunt.");

  // ---------- 5. Drie stappen ----------
  s = pres.addSlide({ masterName: "INHOUD", sectionTitle: "Hoe het werkt" });
  s.addText("In drie stappen van de wijk naar de hulpdienst", { placeholder: "title" });
  const stap = [["run", "De vrijwilliger meldt", "Verkent de situatie, doet de eerste triage en stuurt een M/ETHANE-melding met telefoon en LoRa-zender."],
                ["tower", "Het steunpunt zendt door", "Een zendamateur op accu vangt de melding op en zendt hem via 2 meter door, leesbaar en met roepnaam."],
                ["building", "De Eindpost toont", "Bij de hulpdienst staat de melding meteen op het scherm, op de kaart en in het logboek. De ontvangst wordt bevestigd."]];
  stap.forEach(([ic, kop, t], i) => {
    const x = 0.5 + i * 3.1;
    rondIcoon(s, ic, x + 0.95, 1.3, 0.9, C.accent1);
    tekst(s, String(i + 1), { x: x + 0.1, y: 1.35, w: 0.7, h: 0.8, fontSize: 44, bold: true, color: C.accent1, objectName: "nummer " + (i + 1) });
    tekst(s, kop, { x, y: 2.45, w: 2.8, h: 0.45, fontSize: 18, bold: true, align: "center", objectName: "kop stap " + (i + 1) });
    tekst(s, t, { x: x + 0.1, y: 2.95, w: 2.6, h: 1.6, fontSize: 14, valign: "top", objectName: "tekst stap " + (i + 1) });
    if (i < 2) s.addImage({ data: I.arrow_rood, x: x + 2.85, y: 1.6, w: 0.3, h: 0.3, objectName: "pijl " + (i + 1) });
  });
  tekst(s, "Zonder stroomnet, internet of mobiel netwerk.", { x: 0.5, y: 4.65, w: 9, h: 0.4, fontSize: 16, italic: true, color: C.accent1, objectName: "kernzin" });
  s.addNotes("Stap 1: de vrijwilliger. Stap 2: het Noodsteunpunt. Stap 3: de Eindpost bij de hulpdienst. Elke schakel werkt zonder stroomnet, internet of mobiel netwerk.");

  // ---------- 6-8. Onderdelen ----------
  pres.addSection({ title: "De onderdelen" });
  function onderdeel(titel, beeld, ratio, alt, kop, pnt, notitie, beeldLinks) {
    const sl = pres.addSlide({ masterName: "INHOUD", sectionTitle: "De onderdelen" });
    sl.addText(titel, { placeholder: "title" });
    const bw = 5.6, bh = bw / ratio, bx = beeldLinks ? 0.4 : 3.95;
    sl.addImage({ path: beeld, x: bx, y: 1.25, w: bw, h: bh, altText: alt, objectName: "schema " + titel });
    const tx = beeldLinks ? 6.25 : 0.5;
    tekst(sl, kop, { x: tx, y: 1.25, w: 3.25, h: 0.7, fontSize: 16, bold: true, italic: true, color: C.accent1, valign: "top", objectName: "kernzin" });
    punten(sl, pnt, { x: tx, y: 2.0, w: 3.25, h: 3.1, fontSize: 13, paraSpaceAfter: 6, objectName: "punten" });
    sl.addNotes(notitie);
  }
  onderdeel("Het Noodsteunpunt", "noodsteunpunt.png", 1.974,
    "Schema van een Noodsteunpunt: 2 meter-transceiver en twee RNodes aan een Raspberry Pi, op een 12 V-accu, met een eigen wifi-hotspot.",
    "Het knooppunt tussen de straat en de hulpdiensten",
    ["Draagbaar station van een zendamateur, op een accu", "Ontvangt de vrijwilligers via LoRa (433 en 868 MHz)",
     "Zendt door via 2 meter: leesbaar, met roepnaam", "Herhaalt elke melding tot de hulpdienst bevestigt",
     "Ziet op een kaart waar de vrijwilligers zijn", "Beheer via de telefoon, met eigen wifi"],
    "Een Noodsteunpunt bestaat uit de eigen 2 meter-set van de zendamateur, een Raspberry Pi en een of twee RNodes, op een accu. Het ontvangt de meldingen van de vrijwilligers en zendt ze door. Alleen aangemelde en goedgekeurde vrijwilligers kunnen melden. De zendamateur beheert alles via zijn telefoon, zonder internet, en ziet op een offline kaart waar zijn vrijwilligers zijn.", true);
  onderdeel("De Eindpost bij de hulpdienst", "eindpost.png", 1.967,
    "Schema van een Eindpost: 2 meter-transceiver aan een Raspberry Pi, met een monitor voor het M/ETHANE-scherm en een eigen wifi-hotspot.",
    "Waar de meldingen aankomen",
    ["Bij brandweer, gemeentehuis of ziekenhuis", "Elke melding meteen groot op het scherm", "Op een tweede scherm: de meldingen op de kaart",
     "Logboek per dag, te downloaden", "Personeel hoeft niets te bedienen", "Werkt op noodstroom of accu"],
    "De Eindpost staat bij de hulpdienst. De meldingen verschijnen vanzelf op een scherm, en op een tweede scherm op de kaart. Alles gaat in een logboek voor de evaluatie achteraf. Het personeel kijkt alleen; een zendamateur bemant de post. Een dienst kan meerdere Eindposten hebben, bijvoorbeeld de hoofdkazerne en een dependance.", false);
  onderdeel("De vrijwilliger in de wijk", "vrijwilliger.png", 1.974,
    "Schema: Android-telefoon via Bluetooth gekoppeld aan een RNode, die via LoRa een Noodsteunpunt bereikt; vier stappen van kaart scannen tot melden.",
    "De ogen en oren van de hulpdiensten",
    ["Getraind in calamiteiten en eerste triage", "Eigen Android-telefoon met de Noodnet-app", "Kleine LoRa-zender (RNode), geen licentie nodig",
     "Aanmelden met de kaart van het steunpunt", "Zelf ter plaatse? Dan gaat de GPS-positie mee", "Eigen veiligheid gaat altijd voor"],
    "De vrijwilliger heeft kennis van calamiteiten, bijvoorbeeld EHBO, BHV of ervaring bij een hulpdienst. Met een Android-telefoon en een RNode meldt hij bij het dichtstbijzijnde steunpunt. Aanmelden gaat met een QR-kaart van het steunpunt, en de beheerder keurt goed. Is hij zelf bij het incident, dan vinkt hij 'Ik ben ter plaatse' aan en gaat zijn positie mee; meldt hij iets van een afstand, dan niet, zodat de hulpdienst niet naar de verkeerde plek gaat. Noodnet is een aanvulling op 112, geen vervanging.", true);

  // ---------- 9. M/ETHANE ----------
  s = pres.addSlide({ masterName: "INHOUD", sectionTitle: "De onderdelen" });
  s.addText("Wat de hulpdienst ziet: M/ETHANE", { placeholder: "title" });
  const me = [["M", "Groot incident?", "ja: rode kop op het scherm"], ["E", "Exacte locatie", "plus GPS als de melder ter plaatse is"],
              ["T", "Type incident", "brand, instorting, ongeval"], ["H", "Gevaren", "gas, instortingsgevaar, water"],
              ["A", "Bereikbaarheid", "welke route is vrij"], ["N", "Slachtoffers", "aantal en ernst"],
              ["E", "Hulpdiensten", "wie is er al ter plaatse"]];
  me.forEach(([l, kop, t], i) => {
    const rij = i < 4 ? 0 : 1, kol = i < 4 ? i : i - 4;
    const x = 0.5 + kol * 2.3 + (rij ? 1.15 : 0), y = 1.25 + rij * 1.75;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 2.1, h: 1.5, rectRadius: 0.1, fill: { color: C.background2 }, line: { color: C.background2 }, objectName: "tegel " + kop });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.15, y: y + 0.15, w: 0.6, h: 0.6, rectRadius: 0.08, fill: { color: C.text2 }, line: { color: C.text2 }, objectName: "letterblok " + kop });
    tekst(s, l, { x: x + 0.15, y: y + 0.15, w: 0.6, h: 0.6, fontSize: 26, bold: true, color: C.background1, align: "center", valign: "middle", objectName: "letter " + kop });
    tekst(s, kop, { x: x + 0.82, y: y + 0.2, w: 1.25, h: 0.5, fontSize: 13, bold: true, valign: "middle", objectName: "kop " + kop });
    tekst(s, t, { x: x + 0.15, y: y + 0.85, w: 1.85, h: 0.55, fontSize: 12, color: C.accent5, valign: "top", objectName: "uitleg " + kop });
  });
  s.addNotes("M/ETHANE is de vaste vorm die hulpdiensten kennen. De vrijwilliger vult die in de app in; bij de Eindpost verschijnt hij precies zo op het scherm. Een groot incident valt meteen op met een rode kop. Is de vrijwilliger zelf ter plaatse, dan staan zijn GPS-coördinaten erbij.");

  // ---------- 10. Meldingen op de kaart (eindpost) ----------
  pres.addSection({ title: "Overzicht" });
  s = pres.addSlide({ masterName: "INHOUD", sectionTitle: "Overzicht" });
  s.addText("Meldingen op de kaart", { placeholder: "title" });
  kaartje(s, 0.5, 1.25, 4.6, 3.55, [
    [0.22, 0.30, "1F5FA8", 0.18, "rond", "13:05"], [0.78, 0.22, "1F5FA8", 0.18, "rond", "13:20"],
    [0.30, 0.74, "1F5FA8", 0.18, "rond", "13:41"], [0.84, 0.70, "1F5FA8", 0.18, "rond", ""],
    [0.55, 0.48, "D00000", 0.34, "rond", ""]], "eindpost");
  s.addShape(pres.shapes.OVAL, { x: 0.5 + 0.55 * 4.6 - 0.42, y: 1.25 + 0.48 * 3.55 - 0.42, w: 0.84, h: 0.84,
    fill: { color: "FF0000", transparency: 82 }, line: { color: "D00000", width: 2 }, objectName: "cirkel nieuwste" });
  tekst(s, "NIEUW 14:02 · Brand", { x: 0.5 + 0.55 * 4.6 + 0.3, y: 1.25 + 0.48 * 3.55 - 0.14, w: 1.4, h: 0.26, fontSize: 10, bold: true,
    color: C.accent1, fill: { color: "FFFFFF" }, objectName: "label nieuwste" });
  tekst(s, "Op een tweede scherm bij de hulpdienst", { x: 5.45, y: 1.25, w: 4.05, h: 0.4, fontSize: 16, bold: true, italic: true, color: C.accent1, objectName: "kernzin" });
  punten(s, ["De nieuwste melding groot en rood; de kaart schuift er vanzelf naartoe",
             "De 10 meldingen daarvoor in het blauw", "Tik op een melding voor de hele M/ETHANE",
             "Alleen meldingen van vrijwilligers die zelf ter plaatse zijn",
             "Offline kaart van het Kadaster: werkt zonder internet"],
         { x: 5.45, y: 1.8, w: 4.05, h: 3.1, objectName: "punten kaart eindpost" });
  s.addNotes("Op een tweede scherm bij de Eindpost staan de meldingen op een kaart. De nieuwste melding valt op: groot, rood en met een cirkel, en de kaart schuift er vanzelf naartoe. De tien meldingen daarvoor staan in het blauw. Alleen meldingen waarbij de vrijwilliger zelf ter plaatse was, hebben een positie. De kaart is de BRT-Achtergrondkaart van het Kadaster, die de Eindpost eenmalig downloadt; daarna werkt hij zonder internet.");

  // ---------- 11. De beheerder houdt overzicht (steunpunt) ----------
  s = pres.addSlide({ masterName: "INHOUD", sectionTitle: "Overzicht" });
  s.addText("Het steunpunt houdt overzicht over de vrijwilligers", { placeholder: "title" });
  kaartje(s, 5.4, 1.25, 4.1, 3.55, [
    [0.48, 0.47, "1F5FA8", 0.24, "vierkant", "Steunpunt"], [0.24, 0.26, "2E7D32", 0.2, "rond", "Anna"],
    [0.78, 0.30, "2E7D32", 0.2, "rond", "Bram"], [0.70, 0.78, "E67E00", 0.2, "rond", "Liesbeth"],
    [0.18, 0.70, "C00000", 0.2, "rond", "Jan"]], "steunpunt");
  const beh = [["usercheck", "Aanmelden", "De beheerder keurt nieuwe vrijwilligers goed, vanaf zijn telefoon."],
               ["bell", "Waarschuwingen", "Bericht als iemand uit beeld raakt of zijn accu bijna leeg is."],
               ["mapped", "Posities", "Iedereen op de kaart: groen actief, oranje accu laag, rood uit beeld."],
               ["comment", "Berichten", "Aan één vrijwilliger of aan allen, met bevestiging dat het aankwam."]];
  beh.forEach(([ic, kop, t], i) => {
    const y = 1.25 + i * 0.9;
    rondIcoon(s, ic, 0.5, y + 0.05, 0.62, C.accent1);
    tekst(s, kop, { x: 1.3, y, w: 3.8, h: 0.32, fontSize: 16, bold: true, objectName: "kop " + kop });
    tekst(s, t, { x: 1.3, y: y + 0.32, w: 3.8, h: 0.5, fontSize: 12.5, valign: "top", objectName: "tekst " + kop });
  });
  s.addNotes("De beheerder van het steunpunt, meestal de zendamateur zelf, houdt overzicht over zijn vrijwilligers. Hij keurt aanmeldingen goed vanaf zijn telefoon. Hij krijgt bericht als iemand niet meer gehoord wordt of zijn accu bijna leeg is, met de laatst bekende plek. Op een offline kaart ziet hij waar iedereen is. En hij kan berichten sturen aan één vrijwilliger, bijvoorbeeld 'ga naar de Brink', of aan allen, bijvoorbeeld 'einde oefening'. Hij hoort of het bericht is aangekomen.");

  // ---------- 12. Waarom het werkt ----------
  pres.addSection({ title: "Verder" });
  s = pres.addSlide({ masterName: "INHOUD", sectionTitle: "Verder" });
  s.addText("Waarom het werkt", { placeholder: "title" });
  const waarom = [["battery", "Onafhankelijk", "Op accu, met eigen wifi en een offline kaart. Geen stroomnet, internet of mobiel netwerk nodig."],
                  ["check", "Zeker", "Elke melding wordt bevestigd. Zonder bevestiging herhaalt het steunpunt hem."],
                  ["comment", "Zonder misverstanden", "Wat de vrijwilliger typt, komt letterlijk aan, in de vaste M/ETHANE-vorm."],
                  ["code", "Open", "Software (EUPL) en handleidingen staan vrij op GitHub. Elke gemeente kan meedoen."]];
  waarom.forEach(([ic, kop, t], i) => {
    const x = 0.5 + (i % 2) * 4.6, y = 1.25 + Math.floor(i / 2) * 1.9;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 4.4, h: 1.65, rectRadius: 0.1, fill: { color: C.background2 }, line: { color: C.background2 }, objectName: "kaart " + kop });
    rondIcoon(s, ic, x + 0.25, y + 0.35, 0.85, C.accent1);
    tekst(s, kop, { x: x + 1.3, y: y + 0.25, w: 2.95, h: 0.4, fontSize: 18, bold: true, objectName: "kop " + kop });
    tekst(s, t, { x: x + 1.3, y: y + 0.68, w: 2.95, h: 0.85, fontSize: 14, valign: "top", objectName: "tekst " + kop });
  });
  s.addNotes("Vier redenen. Onafhankelijk: alles werkt op accu, met een eigen wifi en een offline kaart. Zeker: geen melding gaat verloren, want zonder bevestiging wordt herhaald. Zonder misverstanden: geen overschrijven van spraak. Open: de software is vrij beschikbaar onder de Europese open-sourcelicentie EUPL, dus elke gemeente kan het overnemen.");

  // ---------- 13. Samen verder ----------
  s = pres.addSlide({ masterName: "INHOUD", sectionTitle: "Verder" });
  s.addText("Samen verder: wat we van de gemeente vragen", { placeholder: "title" });
  const vraag = [["handshake", "Kennismaking", "met de hulpdiensten en de veiligheidsregio: past Noodnet in de crisisplannen?"],
                 ["building", "Plaats voor Eindposten", "bij gemeentehuis en hulpdiensten: noodstroom en ruimte voor een antenne."],
                 ["users", "Vrijwilligers", "helpen werven en trainen, bijvoorbeeld via EHBO, BHV of het Rode Kruis."],
                 ["map", "Oefenen", "een gezamenlijke oefening om het netwerk in de eigen gemeente te testen."]];
  vraag.forEach(([ic, kop, t], i) => {
    const y = 1.2 + i * 0.95;
    rondIcoon(s, ic, 0.5, y, 0.7, C.accent1);
    tekst(s, [{ text: kop + "  ", options: { bold: true, fontSize: 18 } }, { text: t, options: { fontSize: 14 } }],
      { x: 1.4, y, w: 8.1, h: 0.7, valign: "middle", objectName: "vraag " + kop });
  });
  s.addNotes("Wat Noodnet van de gemeente nodig heeft. Een kennismaking met de hulpdiensten en de veiligheidsregio. Een plek voor de Eindposten, met noodstroom en ruimte voor een antenne. Hulp bij het werven en trainen van vrijwilligers. En een gezamenlijke oefening. De zendamateurs brengen hun eigen apparatuur en kennis mee.");

  // ---------- 14. Contact ----------
  s = pres.addSlide({ masterName: "TITEL_DONKER", sectionTitle: "Verder" });
  s.addText("Meer weten?", { placeholder: "title" });
  s.addText(NAAM, { placeholder: "body" });
  const contact = [["globe", WEBSITE], ["envelope", EMAIL], ["code", GITHUB]];
  contact.forEach(([ic, t], i) => {
    const y = 3.55 + i * 0.5;
    s.addImage({ data: I[ic], x: 0.6, y: y + 0.05, w: 0.3, h: 0.3, objectName: "icoon " + ic });
    tekst(s, t, { x: 1.1, y, w: 6, h: 0.4, fontSize: 16, color: C.background1, valign: "middle", objectName: "contact " + ic });
  });
  rondIcoon(s, "tower", 7.3, 1.6, 2.0, C.accent1);
  s.addNotes("Vragen? Op de website staat de uitleg, op GitHub de software en de complete handleidingen. Zendamateurs, vrijwilligers en gemeenten die willen meedoen, kunnen contact opnemen via de website of per e-mail.");

  await pres.writeFile({ fileName: "Noodnet-presentatie.pptx" });
  if (applyTheme) await applyTheme("Noodnet-presentatie.pptx", THEME);
  else console.log("Let op: apply_theme.js niet gevonden; thema-kleuren niet toegepast.");
  console.log("klaar");
})();

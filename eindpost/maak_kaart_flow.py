#!/usr/bin/env python3
"""Maakt kaart_flow.json: de Node-RED-flow 'Noodnet kaart' (meldingen op een offline kaart).

De flow zelf staat in kaart_flow.json; dit script is alleen om hem leesbaar te onderhouden.
    python3 maak_kaart_flow.py   ->  kaart_flow.json
"""
import json
import os

HIER = os.path.dirname(os.path.abspath(__file__))
TAB = "nn_kaart_tab"
BROKER = "49a287c308869fb8"          # dezelfde MQTT-broker als het M/ETHANE-scherm

# ---------------------------------------------------------------------------
# JavaScript in de function-nodes
# ---------------------------------------------------------------------------

JS_TEGEL = r"""// Kaarttegel van de offline kaart: /noodnet-tegels/{z}/{x}/{y}.png
const p = msg.req.params || {};
const z = Number(p.z), x = Number(p.x), y = Number(String(p.y || "").replace(/\.png$/, ""));
if (![z, x, y].every(Number.isInteger) || z < 0 || z > 20 || x < 0 || y < 0) {
    msg.statusCode = 400; msg.payload = "";
    return [null, msg];
}
msg.filename = env.get("HOME") + "/noodnet/kaart/tegels/" + z + "/" + x + "/" + y + ".png";
return [msg, null];
"""

JS_TEGEL_OK = r"""msg.headers = {"Content-Type": "image/png", "Cache-Control": "max-age=3600"};
delete msg.filename;
return msg;
"""

JS_TEGEL_404 = r"""// Tegel bestaat niet (buiten het gedownloade gebied): leeg antwoord
msg.statusCode = 404;
msg.payload = "";
msg.headers = {"Content-Type": "text/plain"};
return msg;
"""

JS_INFO_PAD = r"""msg.filename = env.get("HOME") + "/noodnet/kaart/kaart.json";
return msg;
"""

JS_INFO = r"""// kaart.json (van de beheerpagina: tabblad Posities) inlezen.
// Is er een nieuwe kaart gedownload, dan de open kaarten naar het nieuwe midden sturen.
let k = msg.payload;
if (typeof k !== "object" || k === null || typeof k.lat !== "number") k = null;
const oud = flow.get("kaart_info") || null;
flow.set("kaart_info", k);
if (!k) { node.status({fill: "yellow", shape: "ring", text: "nog geen offline kaart"}); return null; }
node.status({fill: "green", shape: "dot", text: k.plaats + ", " + k.straal_km + " km, " + k.aantal + " tegels"});
if (oud && oud.datum !== k.datum) {
    return {payload: {command: {lat: k.lat, lon: k.lon, zoom: k.zoom_start || 13}}};
}
return null;
"""

JS_GEEN_INFO = r"""flow.set("kaart_info", null);
node.status({fill: "yellow", shape: "ring", text: "nog geen offline kaart"});
return null;
"""

JS_KAART = r"""// Meldingen op de kaart.
//  - M/ETHANE-melding met positie (MQTT): op de kaart. De nieuwste is groot en rood, met een
//    rode cirkel; de 10 meldingen daarvoor zijn kleinere blauwe markers.
//  - {action:"connected"} van de kaart (een scherm opent de kaart): alles opnieuw sturen.
//  - topic "wis": kaart leegmaken.
// Alleen meldingen waarbij de vrijwilliger 'Ik ben ter plaatse' aanvinkte, hebben een positie.
const MAX = 11;
const LAAG = "Meldingen";
const KAARTNAAM = "Offline kaart";

let lijst = flow.get("kaart_meldingen") || [];
const k = flow.get("kaart_info") || null;

function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g,
        c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
}
// Naam van de marker: uniek, en staat bovenaan de popup
function sleutel(m) { return "Melding " + m.meldcode + " \u00b7 " + (m.afzender_naam || String(m.afzender || "").slice(0, 8)); }
function moment(m) { return m.eerst_ontvangen || m.timestamp || 0; }
function tijd(m) { return String(m.melding_tijd || "").slice(11, 16); }
function kort(m) {
    const s = (m.soort_incident && m.soort_incident !== "onbekend") ? String(m.soort_incident) : "";
    return s.length > 32 ? s.slice(0, 32) + "…" : s;
}
function popup(m, nieuwste) {
    let h = '<div style="font-size:15px;max-width:360px">';
    if (nieuwste) h += '<div style="color:#c00000;font-weight:bold">NIEUWSTE MELDING</div>';
    h += '<b>' + esc(m.melding_tijd) + '</b> &middot; ' + esc(m.meldcode);
    if (m.groot_incident === "ja") {
        h += '<div style="background:#c00000;color:#fff;font-weight:bold;padding:2px 6px;margin:4px 0">GROOT INCIDENT</div>';
    }
    h += '<table style="border-collapse:collapse;margin-top:4px">';
    for (const r of (m.regels || [])) {
        const kleur = r.onbekend ? "#888" : "#000";
        h += '<tr><td style="padding:2px 6px;font-weight:bold;vertical-align:top">' + esc(r.letter) +
             '</td><td style="padding:2px 6px;color:' + kleur + '">' + esc(r.waarde) + '</td></tr>';
    }
    h += '</table><div style="color:#555;margin-top:6px;font-size:13px">Positie van de melder (ter plaatse)';
    if (m.accuracy_m) h += ', &plusmn;' + Math.round(m.accuracy_m) + ' m';
    h += '<br>Gemeld door ' + esc(m.afzender_naam || m.afzender) + ' via ' + esc(m.steunpunt_naam || m.ontvanger || "?");
    h += '<br>Voor: ' + esc(m.gemeld_aan) + (m.voor_mij === false ? ' (meegelezen)' : '') + '</div></div>';
    return h;
}
function marker(m, i) {
    const nieuw = (i === 0);
    const tekst = tijd(m) + (kort(m) ? " · " + kort(m) : "");
    const p = {
        name: sleutel(m), lat: m.latitude, lon: m.longitude, layer: LAAG,
        icon: nieuw ? "exclamation-triangle" : "exclamation",
        iconColor: nieuw ? "#d00000" : "#1f5fa8",
        popup: popup(m, nieuw), ttl: 0, draggable: false, contextmenu: ""
    };
    if (nieuw) p.label = "NIEUW " + tekst; else p.tooltip = tekst;
    return p;
}
function cirkel(m) {
    if (!m) return {name: "nieuwste-cirkel", deleted: true};
    return {name: "nieuwste-cirkel", lat: m.latitude, lon: m.longitude, layer: LAAG,
            radius: Math.max(Number(m.accuracy_m) || 0, 60), color: "#d00000", fillColor: "#ff0000",
            fillOpacity: 0.18, weight: 3, clickable: false, ttl: 0};
}
function basiskaart() {
    const c = {};
    if (k) {
        c.map = {name: KAARTNAAM, url: "/noodnet-tegels/{z}/{x}/{y}.png",
                 opt: {maxNativeZoom: k.max_zoom || 16, maxZoom: 19, minZoom: 8, attribution: k.bron || ""}};
        c.layer = KAARTNAAM;
        c.lat = k.lat; c.lon = k.lon; c.zoom = k.zoom_start || 13;
    } else {
        c.showdialog = "<h2>Nog geen offline kaart</h2><p>Download de kaart eenmalig op de beheerpagina " +
                       "van de eindpost (tabblad <b>Posities</b>, met internet). De meldingen staan wel al op de kaart.</p>";
    }
    // Recente melding (laatste 3 uur): daar beginnen
    const n = lijst[0];
    if (n && Date.now() / 1000 - moment(n) < 3 * 3600) { c.lat = n.latitude; c.lon = n.longitude; c.zoom = 15; }
    return {payload: {command: c}};
}

// --- Kaart leegmaken -------------------------------------------------------
if (msg.topic === "wis") {
    const uit = lijst.map(m => ({payload: {name: sleutel(m), deleted: true}}));
    uit.push({payload: cirkel(null)});
    flow.set("kaart_meldingen", []);
    node.status({});
    return [uit];
}

// --- Een scherm opent de kaart: alles naar dat scherm ----------------------
if (msg.payload && msg.payload.action === "connected") {
    const sid = msg._sessionid;
    const uit = [basiskaart()];
    lijst.forEach((m, i) => uit.push({payload: marker(m, i)}));
    if (lijst.length) uit.push({payload: cirkel(lijst[0])});
    uit.forEach(u => { if (sid) u._sessionid = sid; });
    return [uit];
}

// --- Nieuwe of herhaalde M/ETHANE-melding ----------------------------------
const m = msg.payload;
if (!m || m.type !== "METHANE") return null;
if (typeof m.latitude !== "number" || typeof m.longitude !== "number") {
    node.status({fill: "grey", shape: "ring", text: m.meldcode + ": zonder positie, niet op de kaart"});
    return null;
}
const idx = lijst.findIndex(x => sleutel(x) === sleutel(m));
if (idx >= 0) lijst[idx] = m; else lijst.push(m);
lijst.sort((a, b) => moment(b) - moment(a));
const weg = lijst.slice(MAX);
lijst = lijst.slice(0, MAX);
flow.set("kaart_meldingen", lijst);

const uit = weg.map(x => ({payload: {name: sleutel(x), deleted: true}}));
lijst.forEach((x, i) => uit.push({payload: marker(x, i)}));
uit.push({payload: cirkel(lijst[0])});
// Naar de nieuwe melding schuiven (niet bij een herhaling of het bewaarde bericht na een herstart)
if (idx < 0 && !msg.retain && sleutel(lijst[0]) === sleutel(m)) {
    uit.push({payload: {command: {lat: m.latitude, lon: m.longitude, zoom: 15}}});
}
node.status({fill: "red", shape: "dot", text: "nieuwste: " + m.meldcode + " " + tijd(m) + " (" + lijst.length + " op de kaart)"});
return [uit];
"""

# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def node(id_, type_, x, y, wires=None, **kw):
    n = {"id": id_, "type": type_, "z": TAB, "x": x, "y": y}
    n.update(kw)
    if wires is not None:
        n["wires"] = wires
    return n


def func(id_, name, code, x, y, wires, outputs=1):
    return node(id_, "function", x, y, wires, name=name, func=code, outputs=outputs, timeout=0, noerr=0,
                initialize="", finalize="", libs=[])


flow = [
    {"id": TAB, "type": "tab", "label": "Noodnet kaart", "disabled": False,
     "info": "Meldingen op een offline kaart (tweede scherm): http://<pi>:1880/worldmap\n\n"
             "De kaart download je op de beheerpagina van de eindpost (tabblad Posities). "
             "Alleen meldingen met 'Ik ben ter plaatse' hebben een positie."},
    node("nn_kaart_uitleg", "comment", 230, 40, name="Meldingen op de kaart: http://<pi>:1880/worldmap",
         info="Nieuwste melding: groot, rood, met cirkel. De 10 daarvoor: blauw.\n"
              "Kaart: tabblad Posities op de beheerpagina (poort 8080)."),

    # Meldingen
    node("nn_kaart_mqtt", "mqtt in", 170, 120, [["nn_kaart_func"]], name="M/ETHANE van gateway",
         topic="reticulum/tbeam/methane/laatste", qos="1", datatype="json", broker=BROKER, nl=False, rap=False,
         rh=0, inputs=0),
    node("nn_kaart_in", "worldmap in", 150, 180, [["nn_kaart_connected"]], name="kaart geopend", path="/worldmap",
         events="connect"),
    node("nn_kaart_connected", "switch", 330, 180, [["nn_kaart_func"]], name="connected?", property="payload.action",
         propertyType="msg", rules=[{"t": "eq", "v": "connected", "vt": "str"}], checkall="true", repair=False,
         outputs=1),
    node("nn_kaart_wis", "inject", 150, 240, [["nn_kaart_func"]], name="Wis kaart", props=[{"p": "topic", "vt": "str"}],
         repeat="", crontab="", once=False, onceDelay=0.1, topic="wis"),
    func("nn_kaart_func", "Meldingen op de kaart", JS_KAART, 560, 160, [["nn_kaart_map"]]),
    node("nn_kaart_map", "worldmap", 810, 160, [], name="Noodnet - meldingen", lat="52.255", lon="6.163", zoom="13",
         layer="", cluster="", maxage="", usermenu="hide", layers="hide", panit="false", panlock="false",
         zoomlock="false", hiderightclick="true", coords="none", showgrid="false", showruler="false",
         allowFileDrop="false", path="/worldmap", overlist="", maplist="", mapname="", mapurl="", mapopt="",
         mapwms=False),

    # kaart.json
    node("nn_kaart_info_tik", "inject", 160, 320, [["nn_kaart_info_pad"]], name="elke 30 s",
         props=[{"p": "payload"}], repeat="30", crontab="", once=True, onceDelay="2", topic="", payload="",
         payloadType="date"),
    func("nn_kaart_info_pad", "pad kaart.json", JS_INFO_PAD, 350, 320, [["nn_kaart_info_lees"]]),
    node("nn_kaart_info_lees", "file in", 540, 320, [["nn_kaart_info_json"]], name="lees kaart.json",
         filename="filename", filenameType="msg", format="utf8", chunk=False, sendError=False, encoding="utf8",
         allProps=False),
    node("nn_kaart_info_json", "json", 710, 320, [["nn_kaart_info_func"]], name="", property="payload", action="obj",
         pretty=False),
    func("nn_kaart_info_func", "kaart bijgewerkt?", JS_INFO, 880, 320, [["nn_kaart_map"]]),
    node("nn_kaart_info_catch", "catch", 540, 380, [["nn_kaart_info_geen"]], name="geen kaart.json",
         scope=["nn_kaart_info_lees", "nn_kaart_info_json"], uncaught=False),
    func("nn_kaart_info_geen", "nog geen kaart", JS_GEEN_INFO, 730, 380, [[]]),

    # Tegels serveren
    node("nn_kaart_http", "http in", 170, 460, [["nn_kaart_tegel"]], name="", url="/noodnet-tegels/:z/:x/:y",
         method="get", upload=False, swaggerDoc=""),
    func("nn_kaart_tegel", "tegelpad", JS_TEGEL, 370, 460, [["nn_kaart_tegel_lees"], ["nn_kaart_antw"]], outputs=2),
    node("nn_kaart_tegel_lees", "file in", 560, 440, [["nn_kaart_tegel_ok"]], name="lees tegel",
         filename="filename", filenameType="msg", format="", chunk=False, sendError=False, encoding="none",
         allProps=False),
    func("nn_kaart_tegel_ok", "png", JS_TEGEL_OK, 740, 440, [["nn_kaart_antw"]]),
    node("nn_kaart_tegel_catch", "catch", 560, 520, [["nn_kaart_tegel_404"]], name="tegel ontbreekt",
         scope=["nn_kaart_tegel_lees"], uncaught=False),
    func("nn_kaart_tegel_404", "404", JS_TEGEL_404, 740, 520, [["nn_kaart_antw"]]),
    node("nn_kaart_antw", "http response", 910, 480, [], name="", statusCode="", headers={}),
]

# Zelfde MQTT-broker als het M/ETHANE-scherm (wordt bij het samenvoegen overgeslagen als hij er al is)
flow.append({"id": "49a287c308869fb8", "type": "mqtt-broker", "name": "Lokaal (deze Pi)", "broker": "127.0.0.1", "port": "1883", "clientid": "", "autoConnect": True, "usetls": False, "protocolVersion": "4", "keepalive": "60", "cleansession": True, "autoUnsubscribe": True, "birthTopic": "", "birthQos": "0", "birthRetain": "False", "birthPayload": "", "birthMsg": {}, "closeTopic": "", "closeQos": "0", "closeRetain": "False", "closePayload": "", "closeMsg": {}, "willTopic": "", "willQos": "0", "willRetain": "False", "willPayload": "", "willMsg": {}, "userProps": "", "sessionExpiry": ""})

if __name__ == "__main__":
    uit = os.path.join(HIER, "kaart_flow.json")
    with open(uit, "w", encoding="utf-8") as f:
        json.dump(flow, f, ensure_ascii=False, indent=1)
    print("geschreven:", uit, len(flow), "nodes")

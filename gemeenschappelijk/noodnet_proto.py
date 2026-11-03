"""
noodnet_proto.py - leesbaar 2m-protocol tussen Steunpunt (Pi) en Meldkamer.

Gedeeld door steunpunt_brug.py (Pi) en ax25_to_mqtt.py (Meldkamer-PC).
Alleen standaard-Python, geen extra modules nodig.

Over 2 meter gaan gewone AX.25 UI-frames met de roepnaam van de zender
in de kop en LEESBARE tekst als inhoud. Er wordt niets versleuteld.

Inhoud van een frame (info-veld):

    NN1 <SOORT> <ID> <deel>/<totaal> <tekst>

    NN1    : herkenning + protocolversie
    SOORT  : MSG  chatbericht
             MTH  M/ETHANE-melding
             GPS  positie/telemetrie
             ANN  announce (telefoon is in de lucht)
             STA  status van het steunpunt (hartslag)
             ACK  ontvangstbevestiging van de Meldkamer
    ID     : 6 tekens, uniek per bericht (herhalingen houden hetzelfde ID)
    deel   : lange berichten worden opgesplitst, bv. 1/3, 2/3, 3/3

De tekst bestaat uit sleutel=waarde-paren, gescheiden door ';'. Vrije tekst
staat altijd als laatste in 'tekst=' en mag alles bevatten. Een nieuwe regel
wordt als \\n geschreven, zodat het hele frame op één regel leesbaar blijft.

Voorbeeld zoals iedereen het met een packet-decoder ziet:

    PD3PAM-1>APZNN:NN1 GPS 3fa2c1 1/1 van=MOB-433;adr=5c57...;lat=52.25123;lon=6.16012;bat=87
    PD3PAM-2>APZNN:NN1 ACK 3fa2c1 1/1
"""

import socket
import threading
import time

PROTO = "NN1"
TOCALL = "APZNN"          # AX.25-bestemming (APZ = experimenteel)
SOORTEN = ("MSG", "MTH", "GPS", "ANN", "STA", "ACK")
# Voor deze soorten stuurt de Meldkamer een ACK terug en herhaalt het
# Steunpunt tot die ACK binnen is. De rest wordt één keer verzonden.
ACK_SOORTEN = ("MSG", "MTH")

# Maximale lengte van de tekst per frame (bytes). AX.25 staat 256 toe;
# met de kop "NN1 MTH 3fa2c1 10/12 " erbij blijven we daar ruim onder.
MAX_DEEL = 200


# ---------------------------------------------------------------------------
# KISS
# ---------------------------------------------------------------------------

FEND, FESC, TFEND, TFESC = 0xC0, 0xDB, 0xDC, 0xDD


def kiss_encode(ax25_frame, port=0):
    out = bytearray([FEND, (port & 0x0F) << 4])
    for b in ax25_frame:
        if b == FEND:
            out += bytes([FESC, TFEND])
        elif b == FESC:
            out += bytes([FESC, TFESC])
        else:
            out.append(b)
    out.append(FEND)
    return bytes(out)


class KissDecoder:
    """Haalt complete AX.25-frames uit een KISS-bytestroom."""

    def __init__(self):
        self.buf = bytearray()
        self.in_frame = False
        self.escape = False

    def feed(self, data):
        frames = []
        for b in data:
            if b == FEND:
                if self.in_frame and len(self.buf) > 1:
                    cmd = self.buf[0]
                    if cmd & 0x0F == 0x00:          # alleen dataframes
                        frames.append(bytes(self.buf[1:]))
                self.buf = bytearray()
                self.in_frame = True
                self.escape = False
                continue
            if not self.in_frame:
                continue
            if self.escape:
                if b == TFEND:
                    self.buf.append(FEND)
                elif b == TFESC:
                    self.buf.append(FESC)
                self.escape = False
            elif b == FESC:
                self.escape = True
            else:
                self.buf.append(b)
        return frames


# ---------------------------------------------------------------------------
# AX.25 UI-frames
# ---------------------------------------------------------------------------

def _split_call(call):
    call = call.strip().upper()
    if "-" in call:
        base, ssid = call.split("-", 1)
        ssid = int(ssid)
    else:
        base, ssid = call, 0
    if not (1 <= len(base) <= 6) or not (0 <= ssid <= 15):
        raise ValueError(f"Ongeldige roepnaam: {call}")
    return base, ssid


def _encode_addr(call, last, command):
    base, ssid = _split_call(call)
    out = bytearray((ord(c) << 1) for c in base.ljust(6))
    b = 0x60 | (ssid << 1)
    if command:
        b |= 0x80
    if last:
        b |= 0x01
    out.append(b)
    return bytes(out)


def _decode_addr(raw):
    base = "".join(chr(b >> 1) for b in raw[:6]).strip()
    ssid = (raw[6] >> 1) & 0x0F
    return f"{base}-{ssid}" if ssid else base


def ax25_ui(src, dest, info):
    """Bouwt een AX.25 UI-frame (zonder digipeaters)."""
    if isinstance(info, str):
        info = info.encode("utf-8")
    return (_encode_addr(dest, last=False, command=True)
            + _encode_addr(src, last=True, command=False)
            + bytes([0x03, 0xF0]) + info)


def ax25_parse(frame):
    """Geeft (bron, bestemming, info) terug, of None als het geen UI-frame is."""
    addrs = []
    i = 0
    while i + 7 <= len(frame):
        addrs.append(frame[i:i + 7])
        last = frame[i + 6] & 0x01
        i += 7
        if last:
            break
    else:
        return None
    if len(addrs) < 2 or i + 2 > len(frame):
        return None
    control, pid = frame[i], frame[i + 1]
    if control & 0xEF != 0x03 or pid != 0xF0:
        return None
    return _decode_addr(addrs[1]), _decode_addr(addrs[0]), frame[i + 2:]


# ---------------------------------------------------------------------------
# Leesbare inhoud: sleutel=waarde;...;tekst=<vrije tekst>
# ---------------------------------------------------------------------------

def _esc(text):
    return (text.replace("\\", "\\\\")
                .replace("\r\n", "\n").replace("\r", "\n")
                .replace("\n", "\\n"))


def _unesc(text):
    out, i = [], 0
    while i < len(text):
        c = text[i]
        if c == "\\" and i + 1 < len(text):
            n = text[i + 1]
            out.append("\n" if n == "n" else n)
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _clean_value(v):
    # Waarden (geen vrije tekst) mogen geen ';' of regeleinden bevatten
    return str(v).replace(";", ",").replace("\n", " ").replace("\r", " ").strip()


def build_body(fields, tekst=None):
    """fields: lijst van (sleutel, waarde); None-waarden worden overgeslagen."""
    parts = [f"{k}={_clean_value(v)}" for k, v in fields if v is not None and v != ""]
    if tekst is not None:
        parts.append("tekst=" + _esc(tekst))
    return ";".join(parts)


def parse_body(body):
    """Geeft een dict terug; vrije tekst staat onder 'tekst'."""
    result = {}
    tekst = None
    if body.startswith("tekst="):
        tekst, body = body[6:], ""
    else:
        idx = body.find(";tekst=")
        if idx >= 0:
            tekst, body = body[idx + 7:], body[:idx]
    for part in body.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            result[k.strip()] = v.strip()
    if tekst is not None:
        result["tekst"] = _unesc(tekst)
    return result


# ---------------------------------------------------------------------------
# Frames opbouwen en lezen
# ---------------------------------------------------------------------------

def _chunks(text, max_bytes):
    """Knipt tekst in stukken van max_bytes bytes (UTF-8), zonder tekens te breken."""
    if text == "":
        return [""]
    chunks, cur, cur_len = [], [], 0
    for ch in text:
        n = len(ch.encode("utf-8"))
        if cur_len + n > max_bytes and cur:
            chunks.append("".join(cur))
            cur, cur_len = [], 0
        cur.append(ch)
        cur_len += n
    if cur:
        chunks.append("".join(cur))
    return chunks


def make_infos(soort, msg_id, body, max_deel=MAX_DEEL):
    """Geeft de info-velden (str) voor één bericht, opgesplitst indien nodig."""
    if soort not in SOORTEN:
        raise ValueError(soort)
    stukken = _chunks(body, max_deel)
    n = len(stukken)
    return [f"{PROTO} {soort} {msg_id} {i}/{n} {s}" if s else f"{PROTO} {soort} {msg_id} {i}/{n}"
            for i, s in enumerate(stukken, 1)]


def parse_info(info):
    """Leest een info-veld. Geeft (soort, id, deel, totaal, tekst) of None."""
    if isinstance(info, (bytes, bytearray)):
        try:
            info = info.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if not info.startswith(PROTO + " "):
        return None
    parts = info.split(" ", 4)
    if len(parts) < 4:
        return None
    _, soort, msg_id, deel = parts[:4]
    tekst = parts[4] if len(parts) == 5 else ""
    if soort not in SOORTEN or "/" not in deel:
        return None
    try:
        i, n = (int(x) for x in deel.split("/", 1))
    except ValueError:
        return None
    if not (1 <= i <= n <= 99):
        return None
    return soort, msg_id, i, n, tekst


class Reassembler:
    """Voegt opgesplitste berichten weer samen (per afzender + ID)."""

    def __init__(self, timeout=600):
        self.timeout = timeout
        self.pending = {}

    def add(self, src, soort, msg_id, i, n, tekst, now):
        # oude, onvolledige berichten opruimen
        for k in [k for k, v in self.pending.items() if now - v["t"] > self.timeout]:
            del self.pending[k]
        if n == 1:
            return tekst
        key = (src, soort, msg_id)
        entry = self.pending.setdefault(key, {"n": n, "delen": {}, "t": now})
        entry["delen"][i] = tekst
        entry["t"] = now
        if len(entry["delen"]) == entry["n"]:
            del self.pending[key]
            return "".join(entry["delen"][k] for k in range(1, n + 1))
        return None


# ---------------------------------------------------------------------------
# Verbinding met Direwolf (KISS over TCP)
# ---------------------------------------------------------------------------

class KissLink:
    """Houdt een KISS-TCP-verbinding met Direwolf open en maakt opnieuw
    verbinding als die wegvalt.

    on_frame(bron, bestemming, info_bytes) wordt aangeroepen voor elk
    ontvangen UI-frame.
    """

    def __init__(self, host, port, mycall, on_frame, log=print):
        self.host, self.port = host, port
        self.mycall = mycall
        self.on_frame = on_frame
        self.log = log
        self.sock = None
        self.lock = threading.Lock()
        self.running = True
        self.connected = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        warned = False
        while self.running:
            try:
                s = socket.create_connection((self.host, self.port), timeout=10)
                s.settimeout(None)
                with self.lock:
                    self.sock = s
                self.connected.set()
                warned = False
                self.log(f"[+] Direwolf: verbonden met {self.host}:{self.port}")
                dec = KissDecoder()
                while self.running:
                    data = s.recv(4096)
                    if not data:
                        raise ConnectionError("verbinding gesloten door Direwolf")
                    for frame in dec.feed(data):
                        parsed = ax25_parse(frame)
                        if parsed:
                            try:
                                self.on_frame(*parsed)
                            except Exception as e:
                                self.log(f"[-] Fout bij verwerken frame: {e}")
            except Exception as e:
                self.connected.clear()
                with self.lock:
                    if self.sock:
                        try:
                            self.sock.close()
                        except OSError:
                            pass
                    self.sock = None
                if self.running and not warned:
                    self.log(f"[!] Direwolf niet bereikbaar ({e}); blijf het elke 5 s proberen...")
                    warned = True
                time.sleep(5)

    def send_info(self, info):
        """Zendt één UI-frame met deze info-tekst. Geeft True bij succes."""
        frame = kiss_encode(ax25_ui(self.mycall, TOCALL, info))
        with self.lock:
            if not self.sock:
                return False
            try:
                self.sock.sendall(frame)
                return True
            except OSError as e:
                self.log(f"[-] Direwolf: zenden mislukt: {e}")
                return False

    def close(self):
        self.running = False
        with self.lock:
            if self.sock:
                try:
                    self.sock.close()
                except OSError:
                    pass

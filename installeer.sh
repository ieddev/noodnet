#!/bin/bash
# =============================================================================
#  Noodnet - installatie en bijwerken van een Noodsteunpunt of Eindpost
#
#  Op een verse Raspberry Pi (gebruiker 'noodnet', internet via wifi of kabel):
#
#     bash <(curl -sL https://raw.githubusercontent.com/ieddev/noodnet/main/installeer.sh)
#
#  Nog een keer draaien = bijwerken (instellingen blijven bewaard).
#  Opnieuw alle vragen beantwoorden:   ... installeer.sh --opnieuw
# =============================================================================
set -e
REPO="https://github.com/ieddev/noodnet"
RAW="https://raw.githubusercontent.com/ieddev/noodnet/main"
BRON="$HOME/noodnet-bron"
DOEL="$HOME/noodnet"
VENV="$HOME/noodnet-venv"
GEBRUIKER="$(id -un)"

rood()  { printf '\033[1;31m%s\033[0m\n' "$*"; }
groen() { printf '\033[1;32m%s\033[0m\n' "$*"; }
stap()  { printf '\n\033[1;34m== %s\033[0m\n' "$*"; }

# ---------------------------------------------------------------------------
# 0. Bootstrap: haal de nieuwste versie van GitHub en start die
# ---------------------------------------------------------------------------
if [ "${NOODNET_UIT_BRON:-0}" != "1" ]; then
  [ "$(id -u)" = "0" ] && { rood "Start dit NIET met sudo, maar als gebruiker noodnet."; exit 1; }
  stap "Noodnet ophalen van GitHub"
  if ! command -v git >/dev/null 2>&1; then sudo apt-get update -qq && sudo apt-get install -y -qq git; fi
  if [ -d "$BRON/.git" ]; then
    git -C "$BRON" fetch -q origin main && git -C "$BRON" reset -q --hard origin/main
  else
    git clone -q "$REPO" "$BRON"
  fi
  echo "   versie: $(git -C "$BRON" log -1 --format='%h %cd' --date=format:'%Y-%m-%d %H:%M')"
  NOODNET_UIT_BRON=1 exec bash "$BRON/installeer.sh" "$@"
fi

# ---------------------------------------------------------------------------
# 1. Vragen (alleen bij de eerste installatie of met --opnieuw)
# ---------------------------------------------------------------------------
OPNIEUW=0; [ "$1" = "--opnieuw" ] && OPNIEUW=1
mkdir -p "$DOEL"
ROL="$(cat "$DOEL/rol" 2>/dev/null || true)"
NIEUW=0
if [ -z "$ROL" ] || [ "$OPNIEUW" = "1" ]; then
  NIEUW=1
  clear || true
  cat <<'TXT'
 ===========================================================
   NOODNET - installatie
 ===========================================================
   1 = Noodsteunpunt  (Pi + 2 m-set + RNodes; doorgeefluik)
   2 = Eindpost       (Pi + 2 m-set + scherm bij een hulpdienst)
TXT
  while true; do
    read -r -p "   Wat wordt deze Pi? [1/2]: " k
    case "$k" in 1) ROL=steunpunt; break;; 2) ROL=eindpost; break;; esac
  done
  [ "$GEBRUIKER" = "noodnet" ] || rood "   Let op: je bent '$GEBRUIKER', de handleiding gaat uit van 'noodnet'. Het werkt wel."
  while true; do
    read -r -p "   Roepnaam met SSID van deze Pi (bijv. PD3PAM-1): " RN
    RN="$(echo "$RN" | tr '[:lower:]' '[:upper:]' | tr -d ' ')"
    [[ "$RN" =~ ^[A-Z0-9]{3,6}-([0-9]|1[0-5])$ ]] && break
    rood "   Gebruik roepnaam-streepje-SSID, bijvoorbeeld PD3PAM-1"
  done
  echo
  echo "   De Pi maakt een eigen wifi-hotspot 'Noodnet-$RN'."
  while true; do
    read -r -p "   Wachtwoord voor die hotspot (min. 8 tekens, Enter = zelf laten kiezen): " HPW
    [ -z "$HPW" ] && HPW="$(tr -dc 'a-hjkmnp-z2-9' </dev/urandom | head -c 10)"
    [ ${#HPW} -ge 8 ] && break
    rood "   Minstens 8 tekens."
  done
  echo "   Hotspot-wachtwoord: $HPW   (schrijf dit op; staat ook op de beheerpagina)"
fi
echo "$ROL" > "$DOEL/rol"

# ---------------------------------------------------------------------------
# 2. Pakketten
# ---------------------------------------------------------------------------
export DEBIAN_FRONTEND=noninteractive
APT_OPT=(-y -qq -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold)
stap "Raspberry Pi OS bijwerken (update + upgrade; de eerste keer kan dit 10-20 minuten duren)"
sudo apt-get update -qq
sudo -E apt-get full-upgrade "${APT_OPT[@]}"
sudo apt-get autoremove -y -qq || true

stap "Pakketten installeren"
PAKKETTEN="git python3-venv direwolf alsa-utils iw curl hostapd dnsmasq-base rfkill libhamlib-utils"
[ "$ROL" = "eindpost" ] && PAKKETTEN="$PAKKETTEN mosquitto mosquitto-clients"
sudo -E apt-get install "${APT_OPT[@]}" $PAKKETTEN
sudo usermod -aG dialout,audio,plugdev,systemd-journal "$GEBRUIKER" || true

# Logboek bewaren tussen herstarts (max. 64 MB), zodat een probleem na een herstart terug te zien is
# met: journalctl -b -1
if [ ! -f /etc/systemd/journald.conf.d/noodnet.conf ]; then
  sudo install -d -m 0755 /etc/systemd/journald.conf.d
  printf '[Journal]\nStorage=persistent\nSystemMaxUse=64M\n' | sudo tee /etc/systemd/journald.conf.d/noodnet.conf >/dev/null
  sudo install -d -m 2755 -g systemd-journal /var/log/journal
  sudo systemctl restart systemd-journald || true
fi

stap "Python-omgeving"
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
if [ "$ROL" = "steunpunt" ]; then
  "$VENV/bin/pip" install -q rns lxmf qrcode
else
  "$VENV/bin/pip" install -q paho-mqtt
fi

# ---------------------------------------------------------------------------
# 3. Programma's kopiëren (instellingen en gegevens blijven staan)
# ---------------------------------------------------------------------------
stap "Noodnet-programma's naar $DOEL"
cp "$BRON"/gemeenschappelijk/*.py "$BRON"/gemeenschappelijk/*.sh "$DOEL"/
mkdir -p "$DOEL/leaflet" && cp "$BRON"/gemeenschappelijk/leaflet/* "$DOEL/leaflet/"   # kaart (tabblad Posities)
cp "$BRON/$ROL"/*.py "$DOEL"/
cp "$BRON/$ROL"/*.sh "$DOEL"/ 2>/dev/null || true
chmod +x "$DOEL/hotspot.sh" "$DOEL/hotspot_bewaker.sh"
mkdir -p "$DOEL/download"
if [ "$ROL" = "steunpunt" ]; then
  [ -f "$DOEL/noodnet_netwerk.json" ] || cp "$BRON/steunpunt/noodnet_netwerk.voorbeeld.json" "$DOEL/noodnet_netwerk.json"
fi
git -C "$BRON" log -1 --format='%h %cd' --date=format:'%Y-%m-%d' > "$DOEL/versie.txt"

if [ "$NIEUW" = "1" ]; then
  if [ "$ROL" = "steunpunt" ] && [ ! -f "$DOEL/steunpunt_instellingen.json" ]; then
    printf '{\n  "steunpunt_naam": "Noodsteunpunt %s",\n  "roepnaam": "%s",\n  "witte_lijst_modus": "aan",\n  "beheerders": []\n}\n' "$RN" "$RN" > "$DOEL/steunpunt_instellingen.json"
  fi
  if [ "$ROL" = "eindpost" ] && [ ! -f "$DOEL/eindpost_instellingen.json" ]; then
    printf '{\n  "eindpost_naam": "Eindpost %s",\n  "roepnaam": "%s",\n  "disciplines": ["alle"],\n  "mqtt_broker": "127.0.0.1"\n}\n' "$RN" "$RN" > "$DOEL/eindpost_instellingen.json"
  fi
fi

# Eerste direwolf.conf (daarna via de beheerpagina, tabblad Radio)
if [ ! -f "$DOEL/direwolf.conf" ]; then
  RN_NU="$("$VENV/bin/python" -c "import json,sys;print(json.load(open('$DOEL/${ROL}_instellingen.json')).get('roepnaam','N0CALL'))" 2>/dev/null || echo N0CALL)"
  (cd "$DOEL" && "$VENV/bin/python" -c "
import noodnet_radio as r
k, p = r.raad_aan(r.geluidskaarten(), r.seriele_poorten())
inst = r.instellingen(); inst.update(geluidskaart=k, ptt_poort=p)
r.maak_direwolf('$RN_NU', inst)
print('   direwolf.conf: geluidskaart', k or '?', '| PTT', p or 'geen (later kiezen op tabblad Radio)')")
fi

# Steunpunt: Reticulum zonder RNodes tot de poorten gekozen zijn (tabblad Radio)
if [ "$ROL" = "steunpunt" ] && [ ! -f "$HOME/.reticulum/config" ]; then
  (cd "$DOEL" && "$VENV/bin/python" -c "
import json, noodnet_radio as r
r.maak_reticulum(r.instellingen(), json.load(open('noodnet_netwerk.json')))
print('   Reticulum-config gemaakt; RNode-poorten kies je op de beheerpagina (tabblad Radio).')")
fi

# ---------------------------------------------------------------------------
# 4. Eindpost: Mosquitto, Node-RED, scherm
# ---------------------------------------------------------------------------
if [ "$ROL" = "eindpost" ]; then
  stap "MQTT (alleen lokaal)"
  sudo install -m 0644 "$BRON/eindpost/mosquitto_noodnet.conf" /etc/mosquitto/conf.d/noodnet.conf
  sudo systemctl enable -q mosquitto && sudo systemctl restart mosquitto

  stap "Node-RED (de eerste keer 5-15 minuten)"
  if ! command -v node-red >/dev/null 2>&1; then
    NR_TMP=$(mktemp)
    if curl -fsSL "https://raw.githubusercontent.com/node-red/linux-installers/master/deb/update-nodejs-and-nodered" -o "$NR_TMP" \
        && head -1 "$NR_TMP" | grep -q '^#!'; then
      bash "$NR_TMP" --confirm-install --confirm-pi
    else
      rood "   Node-RED kon niet gedownload worden. Draai dit script later opnieuw."
    fi
    rm -f "$NR_TMP"
  fi
  if command -v node-red >/dev/null 2>&1; then
    mkdir -p "$HOME/.node-red"
    (cd "$HOME/.node-red" && npm install --no-fund --no-audit --silent node-red-dashboard >/dev/null 2>&1) || true
    # Meldingen op de kaart (tweede scherm): Worldmap
    (cd "$HOME/.node-red" && npm install --no-fund --no-audit --silent node-red-contrib-web-worldmap >/dev/null 2>&1) \
      || rood "   Worldmap (kaart) kon niet geïnstalleerd worden; draai noodnet-bijwerken later opnieuw."
    if [ ! -s "$HOME/.node-red/flows.json" ]; then
      cp "$BRON/eindpost/methane_scherm_flow.json" "$HOME/.node-red/flows.json"
      echo "   M/ETHANE-scherm in Node-RED gezet."
    fi
    # Kaartflow erbij zetten als hij er nog niet in staat (bestaande flows blijven ongemoeid)
    python3 - "$HOME/.node-red/flows.json" "$BRON/eindpost/kaart_flow.json" <<'PY3'
import json, shutil, sys
pad, nieuw = sys.argv[1], sys.argv[2]
try:
    flows = json.load(open(pad, encoding="utf-8"))
except (OSError, ValueError):
    print("   Let op: flows.json van Node-RED niet leesbaar; kaartflow niet toegevoegd."); sys.exit(0)
kaart = json.load(open(nieuw, encoding="utf-8"))
TAB = "nn_kaart_tab"
had_tab = any(n.get("id") == TAB for n in flows)
# Het tabblad 'Noodnet kaart' altijd vervangen door de nieuwste versie (andere flows blijven ongemoeid)
oud = [n for n in flows if n.get("id") == TAB or n.get("z") == TAB]
if had_tab and sorted(json.dumps(n, sort_keys=True) for n in oud) == \
        sorted(json.dumps(n, sort_keys=True) for n in kaart if n.get("id") == TAB or n.get("z") == TAB):
    sys.exit(0)                                  # al de nieuwste
shutil.copyfile(pad, pad + ".voor-kaart")
flows = [n for n in flows if not (n.get("id") == TAB or n.get("z") == TAB)]
ids = {n.get("id") for n in flows}
flows += [n for n in kaart if n.get("id") not in ids]
json.dump(flows, open(pad, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("   Kaart met meldingen in Node-RED " + ("bijgewerkt." if had_tab else "gezet (tabblad 'Noodnet kaart')."))
PY3
    # Meldingenlijst van het M/ETHANE-scherm bewaren over een herstart (flow-context op de SD-kaart)
    NR_SET="$HOME/.node-red/settings.js"
    if [ ! -f "$NR_SET" ]; then          # settings.js ontstaat bij de eerste start
      sudo systemctl start nodered
      for _ in $(seq 60); do [ -f "$NR_SET" ] && break; sleep 1; done
    fi
    if [ -f "$NR_SET" ] && ! grep -qE '^[[:space:]]*contextStorage[[:space:]]*:' "$NR_SET"; then
      cp "$NR_SET" "$NR_SET.voor-noodnet"
      python3 - "$NR_SET" <<'PY2'
import re, sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
s, n = re.subn(r"(module\.exports\s*=\s*\{)",
               r'\1\n    // Noodnet: meldingenlijst bewaren over een herstart\n'
               r'    contextStorage: { default: { module: "localfilesystem", config: { flushInterval: 5 } } },\n',
               s, count=1)
if n:
    open(p, "w", encoding="utf-8").write(s)
    print("   Node-RED bewaart de meldingenlijst nu ook na een herstart.")
else:
    print("   Let op: settings.js van Node-RED niet herkend; meldingenlijst wordt niet bewaard.")
PY2
    fi
    sudo systemctl enable -q nodered && sudo systemctl restart nodered
  fi

  if [ -d /usr/share/xsessions ] || [ -d /usr/share/wayland-sessions ]; then
    stap "Scherm: M/ETHANE-scherm na het opstarten"
    mkdir -p "$HOME/.config/autostart"
    cp "$BRON/eindpost/noodnet-kiosk.desktop" "$HOME/.config/autostart/"
    sudo raspi-config nonint do_boot_behaviour B4 2>/dev/null || true   # automatisch inloggen op het bureaublad
    sudo raspi-config nonint do_blanking 1 2>/dev/null || true          # scherm niet uitzetten
  fi
fi

# ---------------------------------------------------------------------------
# 5. App (APK) voor de downloadpagina
# ---------------------------------------------------------------------------
stap "Noodnet-app voor de downloadpagina"
if curl -fsSL "$REPO/releases/latest/download/noodnet.apk" -o "$DOEL/download/noodnet.apk.nieuw"; then
  mv "$DOEL/download/noodnet.apk.nieuw" "$DOEL/download/noodnet.apk"
  curl -fsSL "$REPO/releases/latest/download/versie.txt" -o "$DOEL/download/versie.txt" 2>/dev/null || true
  echo "   app opgehaald ($(du -h "$DOEL/download/noodnet.apk" | cut -f1))"
else
  rm -f "$DOEL/download/noodnet.apk.nieuw"
  echo "   (nog geen app op GitHub gevonden; later opnieuw bijwerken)"
fi

# ---------------------------------------------------------------------------
# 6. Diensten, rechten, wachtwoord
# ---------------------------------------------------------------------------
stap "Diensten"
plaats() { sed -e "s#@GEBRUIKER@#$GEBRUIKER#g" -e "s#@MAP@#$DOEL#g" -e "s#@VENV@#$VENV#g" "$1" \
             | sudo tee "/etc/systemd/system/$(basename "$1")" >/dev/null; }
for f in "$BRON"/gemeenschappelijk/diensten/*.service "$BRON"/gemeenschappelijk/diensten/*.timer "$BRON/$ROL"/diensten/*.service; do plaats "$f"; done
# Bijwerken vanaf de beheerpagina: script van root (niet door de gebruiker te wijzigen); een achtergebleven
# tijdelijke sudo-regel (stroom eraf tijdens bijwerken) wordt bij het opstarten opgeruimd
sudo install -d -m 0755 /usr/local/lib/noodnet
# (via een tijdelijke naam + mv: dit script kan zelf het bijwerken uitvoeren dat nu loopt)
sudo install -m 0755 -o root -g root "$BRON/gemeenschappelijk/diensten/noodnet-bijwerken.sh" /usr/local/lib/noodnet/.noodnet-bijwerken.sh.nieuw
sudo mv -f /usr/local/lib/noodnet/.noodnet-bijwerken.sh.nieuw /usr/local/lib/noodnet/noodnet-bijwerken.sh
sudo install -m 0755 -o root -g root "$BRON/gemeenschappelijk/diensten/noodnet-wifi.sh" /usr/local/lib/noodnet/.noodnet-wifi.sh.nieuw
sudo mv -f /usr/local/lib/noodnet/.noodnet-wifi.sh.nieuw /usr/local/lib/noodnet/noodnet-wifi.sh
sudo rm -f /etc/systemd/system/noodnet-bijwerken-thuiswifi.service    # vervangen door noodnet-wifi@
# Adres op de thuis-wifi onthouden (handig bij 'Hotspot tijdelijk uitschakelen')
THUISADRES=$(ip -4 -o addr show dev wlan0 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | grep -v '^10\.42\.0\.' | head -1)
if [ -n "$THUISADRES" ]; then sudo mkdir -p /var/lib/noodnet; echo "$THUISADRES" | sudo tee /var/lib/noodnet/thuiswifi-adres >/dev/null; fi
echo "r /etc/sudoers.d/noodnet-bijwerken-tijdelijk" | sudo tee /etc/tmpfiles.d/noodnet-bijwerken.conf >/dev/null
if [ "$ROL" = "steunpunt" ]; then
  DIENSTEN="noodnet-rigctld direwolf rnsd noodnet-brug noodnet-web noodnet-download"; WEB="noodnet_web.py"
else
  DIENSTEN="noodnet-rigctld direwolf noodnet-eindpost noodnet-eindpost-web noodnet-download mosquitto nodered"; WEB="eindpost_web.py"
fi
SC="$(command -v systemctl)"
REGEL="$GEBRUIKER ALL=(root) NOPASSWD:"; EERSTE=1
for d in $DIENSTEN; do [ $EERSTE = 1 ] && EERSTE=0 || REGEL="$REGEL,"; REGEL="$REGEL $SC restart $d"; done
REGEL="$REGEL, $(command -v date) -s *"      # klok gelijkzetten met de telefoon van de beheerder
REGEL="$REGEL, $SC poweroff, $SC reboot"     # knoppen Pi uitschakelen/herstarten op de beheerpagina
REGEL="$REGEL, $SC start --no-block noodnet-bijwerken"   # knop Noodnet bijwerken
REGEL="$REGEL, $SC start --no-block noodnet-wifi@thuiswifi, $SC start --no-block noodnet-wifi@hotspot"   # hotspot tijdelijk uit / weer aan
TMP=$(mktemp); echo "$REGEL" > "$TMP"
sudo visudo -cf "$TMP" >/dev/null && sudo install -m 0440 "$TMP" /etc/sudoers.d/noodnet; rm -f "$TMP"
sudo rm -f /etc/sudoers.d/noodnet-web /etc/sudoers.d/noodnet-eindpost

sudo systemctl daemon-reload
for d in $DIENSTEN; do
  case "$d" in mosquitto|nodered) continue;; esac
  sudo systemctl enable -q "$d"
done
sudo systemctl enable -q --now noodnet-hotspot.timer   # bewaker: hotspot aan als de wifi nergens mee verbonden is

if [ ! -f "$DOEL/web_wachtwoord.json" ]; then
  stap "Wachtwoord voor de beheerpagina (gebruiker: beheer)"
  until (cd "$DOEL" && "$VENV/bin/python" "$WEB" --wachtwoord); do rood "   Probeer opnieuw."; done
fi

# Opdracht om later bij te werken
sudo tee /usr/local/bin/noodnet-bijwerken >/dev/null <<EOB
#!/bin/bash
exec bash <(curl -sL $RAW/installeer.sh) "\$@"
EOB
sudo chmod +x /usr/local/bin/noodnet-bijwerken

# ---------------------------------------------------------------------------
# 7. Hotspot (als laatste; actief na herstart)
# ---------------------------------------------------------------------------
if [ "$NIEUW" = "1" ]; then
  stap "Wifi-hotspot"
  bash "$DOEL/hotspot.sh" installeer "Noodnet-$RN" "$HPW"
else
  stap "Wifi-hotspot (hostapd)"
  bash "$DOEL/hotspot.sh" repareer || rood "   Hotspot bijwerken mislukt: zie hierboven."   # o.a. oude NM-hotspot omzetten naar hostapd
fi

if [ "$NIEUW" = "1" ]; then
  stap "Klaar"
  groen "   Herstart nu de Pi:  sudo reboot"
  cat <<TXT

   Na het opstarten:
   - verbind je telefoon met wifi  Noodnet-$RN  (wachtwoord: $HPW)
   - beheerpagina:   http://10.42.0.1:8080   (gebruiker: beheer)
       -> tabblad Radio: geluidskaart, PTT$( [ "$ROL" = steunpunt ] && echo " en RNode-poorten") kiezen
   - startpagina en app-download:  http://10.42.0.1
   - heb je een back-up van een eerdere installatie? tabblad Back-up -> Terugzetten
   - maak anders na het instellen meteen een back-up (tabblad Back-up)
   - ssh werkt via de hotspot:  ssh $GEBRUIKER@10.42.0.1
   Internet (voor bijwerken) daarna via een netwerkkabel, of tijdelijk:  ~/noodnet/hotspot.sh thuiswifi
   Bijwerken:  noodnet-bijwerken
TXT
else
  stap "Bijwerken: diensten herstarten"
  for d in $DIENSTEN; do sudo systemctl restart "$d" 2>/dev/null || true; [ "$d" = rnsd ] && sleep 3; done
  groen "   Bijgewerkt naar $(cat "$DOEL/versie.txt"). Instellingen zijn bewaard."
  if [ -f /var/run/reboot-required ]; then
    rood "   Er is een nieuwe kernel of systeembibliotheek geïnstalleerd: herstart de Pi (sudo reboot)."
  fi
fi

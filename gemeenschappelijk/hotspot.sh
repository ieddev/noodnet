#!/bin/bash
# Wifi-hotspot van een Noodnet-Pi: hostapd + dnsmasq (niet via NetworkManager).
#
# Waarom niet NetworkManager: op Raspberry Pi OS Trixie (Debian 13) start de
# NM-hotspot wel, maar telefoons kunnen niet koppelen (brcmfmac: "key setting
# validation failed"). Met hostapd werkt dezelfde wifi-chip wel. Getest 3-11-2026.
#
#   hotspot.sh installeer <netwerknaam> <wachtwoord>  hotspot instellen; aan na elke herstart
#   hotspot.sh repareer       na bijwerken: oude NM-hotspot omzetten, configuratie vernieuwen
#   hotspot.sh aan            hotspot nu aanzetten
#   hotspot.sh thuiswifi      tijdelijk de gewone wifi (voor updates; tot de volgende herstart)
#   hotspot.sh status
# Adres van de Pi op de hotspot: 10.42.0.1. Telefoons krijgen 10.42.0.10 - 10.42.0.100.
set -e
MAP="$(cd "$(dirname "$0")" && pwd)"
CONF=/etc/noodnet/hostapd.conf
JSON="$MAP/hotspot.json"

veld() { python3 -c "import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])" "$JSON" "$1"; }

schrijf_conf() {          # hostapd.conf maken uit hotspot.json
  local SSID PSK TMP
  SSID="$(veld ssid)"; PSK="$(veld wachtwoord)"
  TMP=$(mktemp)
  cat > "$TMP" <<EOF
# Gemaakt door ~/noodnet/hotspot.sh - niet met de hand aanpassen
interface=wlan0
driver=nl80211
ssid=$SSID
country_code=NL
ieee80211d=1
hw_mode=g
channel=6
ieee80211n=1
wmm_enabled=1
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
wpa_passphrase=$PSK
EOF
  sudo install -d -m 0755 /etc/noodnet
  sudo install -m 0600 "$TMP" "$CONF"
  rm -f "$TMP"
}

oude_nm_hotspot_weg() {   # NM-hotspot van eerdere versies opruimen
  if nmcli -t -f NAME con show 2>/dev/null | grep -qx noodnet-ap; then
    sudo nmcli con delete noodnet-ap >/dev/null 2>&1 || true
    echo "   Oude NetworkManager-hotspot verwijderd (vervangen door hostapd)."
  fi
}

andere_wifi_niet_automatisch() {
  nmcli -t -f NAME,TYPE con show 2>/dev/null | awk -F: '$2=="802-11-wireless"{print $1}' | while read -r n; do
    if [ "$(nmcli -g connection.autoconnect con show "$n" 2>/dev/null)" = "yes" ]; then
      sudo nmcli con modify "$n" connection.autoconnect no || true
      echo "   wifi '$n': niet meer automatisch (gebruik 'hotspot.sh thuiswifi' voor updates)"
    fi
  done
}

wlan_bij_ander_netwerk() {   # true als NetworkManager wlan0 nu met een wifi-netwerk verbonden heeft
  [ "$(nmcli -t -f DEVICE,STATE dev 2>/dev/null | awk -F: '$1=="wlan0"{print $2}')" = "connected" ]
}

case "$1" in
  installeer)
    SSID="$2"; PSK="$3"
    [ ${#PSK} -ge 8 ] && [ ${#PSK} -le 63 ] || { echo "Wachtwoord moet 8 tot 63 tekens zijn"; exit 1; }
    sudo raspi-config nonint do_wifi_country NL 2>/dev/null || true
    sudo rfkill unblock wifi 2>/dev/null || true
    python3 - "$JSON" "$SSID" "$PSK" <<'PY'
import json, sys
json.dump({"ssid": sys.argv[2], "wachtwoord": sys.argv[3]}, open(sys.argv[1], "w"), indent=2)
PY
    chmod 600 "$JSON"
    schrijf_conf
    oude_nm_hotspot_weg
    andere_wifi_niet_automatisch
    sudo systemctl disable -q --now hostapd 2>/dev/null || true     # de standaard-hostapd niet gebruiken
    sudo systemctl daemon-reload
    sudo systemctl enable -q noodnet-ap noodnet-dhcp
    echo "   Hotspot '$SSID' ingesteld; aan na de volgende herstart (adres 10.42.0.1)."
    ;;
  repareer)
    [ -f "$JSON" ] || { echo "   Geen hotspot.json: hotspot nog niet ingesteld."; exit 0; }
    schrijf_conf
    oude_nm_hotspot_weg
    andere_wifi_niet_automatisch
    sudo systemctl disable -q --now hostapd 2>/dev/null || true
    sudo systemctl daemon-reload
    sudo systemctl enable -q noodnet-ap noodnet-dhcp
    # Niet herstarten als hij al draait (misschien zit je er via ssh op).
    if ! systemctl is-active -q noodnet-ap && ! wlan_bij_ander_netwerk; then
      sudo systemctl start noodnet-ap noodnet-dhcp && echo "   Hotspot aangezet."
    fi
    ;;
  aan)
    sudo systemctl start noodnet-ap noodnet-dhcp ;;
  thuiswifi)
    n=$(nmcli -t -f NAME,TYPE con show | awk -F: '$2=="802-11-wireless"{print $1; exit}')
    [ -n "$n" ] || { echo "Geen andere wifi bekend. Voeg toe met: sudo nmtui"; exit 1; }
    echo "Hotspot gaat uit, verbinden met '$n' (tot de volgende herstart)..."
    sudo systemctl stop noodnet-dhcp noodnet-ap
    sudo ip addr flush dev wlan0 || true
    sudo nmcli dev set wlan0 managed yes
    sleep 3
    sudo nmcli con up "$n" ;;
  status|"")
    if systemctl is-active -q noodnet-ap; then
      echo "Hotspot aan: $(veld ssid 2>/dev/null)"
      iw dev wlan0 station dump 2>/dev/null | grep -c "^Station" | sed 's/^/Verbonden apparaten: /'
    else
      echo "Hotspot uit"; nmcli -t -f DEVICE,STATE,CONNECTION dev | grep '^wlan0' || true
    fi ;;
  *)
    echo "Gebruik: $0 installeer <naam> <wachtwoord> | repareer | aan | thuiswifi | status"; exit 1 ;;
esac

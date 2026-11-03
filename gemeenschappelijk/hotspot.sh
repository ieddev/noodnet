#!/bin/bash
# Wifi-hotspot van een Noodnet-Pi (NetworkManager, Raspberry Pi OS Bookworm).
#   hotspot.sh installeer <netwerknaam> <wachtwoord>  hotspot aanmaken; altijd aan na opstarten
#   hotspot.sh aan                                    hotspot nu aanzetten
#   hotspot.sh thuiswifi                              tijdelijk de gewone wifi (voor updates; tot herstart)
#   hotspot.sh status
#   hotspot.sh repareer                               instellingen voor de wifi-chip van de Pi (PMF uit, WPA2)
# Adres van de Pi op de hotspot: 10.42.0.1
set -e
MAP="$(cd "$(dirname "$0")" && pwd)"
case "$1" in
  installeer)
    SSID="$2"; PSK="$3"
    [ ${#PSK} -ge 8 ] || { echo "Wachtwoord moet minstens 8 tekens zijn"; exit 1; }
    sudo raspi-config nonint do_wifi_country NL 2>/dev/null || true
    sudo nmcli radio wifi on || true
    sudo nmcli con delete noodnet-ap >/dev/null 2>&1 || true
    sudo nmcli con add type wifi ifname wlan0 con-name noodnet-ap autoconnect yes ssid "$SSID" \
      802-11-wireless.mode ap 802-11-wireless.band bg 802-11-wireless.channel 6 802-11-wireless.powersave 2 \
      ipv4.method shared ipv4.addresses 10.42.0.1/24 ipv6.method disabled \
      wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PSK" connection.autoconnect-priority 100 >/dev/null
    # Wifi-chip van de Pi (brcmfmac): in hotspot-modus geen PMF; alleen WPA2 (RSN/CCMP).
    # Zonder dit: "802.1X supplicant took too long to authenticate" (Raspberry Pi OS Trixie).
    "$0" repareer
    # Andere wifi-netwerken niet meer automatisch: de hotspot heeft altijd voorrang
    nmcli -t -f NAME,TYPE con show | awk -F: '$2=="802-11-wireless" && $1!="noodnet-ap"{print $1}' | while read -r n; do
      sudo nmcli con modify "$n" connection.autoconnect no || true
      echo "   wifi '$n': niet meer automatisch (gebruik 'hotspot.sh thuiswifi' voor updates)"
    done
    printf '{\n  "ssid": "%s",\n  "wachtwoord": "%s"\n}\n' "$SSID" "$PSK" > "$MAP/hotspot.json"
    chmod 600 "$MAP/hotspot.json"
    echo "   Hotspot '$SSID' ingesteld; actief na de volgende herstart (adres 10.42.0.1)."
    ;;
  repareer)
    nmcli -t -f NAME con show | grep -qx noodnet-ap || exit 0
    sudo nmcli con modify noodnet-ap wifi-sec.pmf disable wifi-sec.proto rsn \
      wifi-sec.pairwise ccmp wifi-sec.group ccmp
    ;;
  aan)
    sudo nmcli con up noodnet-ap ;;
  thuiswifi)
    n=$(nmcli -t -f NAME,TYPE con show | awk -F: '$2=="802-11-wireless" && $1!="noodnet-ap"{print $1; exit}')
    [ -n "$n" ] || { echo "Geen andere wifi bekend. Voeg toe met: sudo nmtui"; exit 1; }
    echo "Hotspot gaat uit, verbinden met '$n' (tot de volgende herstart)..."
    sudo nmcli con up "$n" ;;
  status|"")
    nmcli -t -f NAME,TYPE,DEVICE con show --active ;;
  *)
    echo "Gebruik: $0 installeer <naam> <wachtwoord> | aan | thuiswifi | status"; exit 1 ;;
esac

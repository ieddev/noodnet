#!/bin/bash
# Wifi van de Pi wisselen vanaf de beheerpagina (dienst noodnet-wifi@<actie>, draait als root).
#   thuiswifi     hotspot tijdelijk uit, verbinden met de bekende thuis-wifi (bijv. om bij te werken)
#   hotspot       thuis-wifi verbreken, hotspot weer aan
#   hotspot_later hotspot over 1 minuut weer aan (na het bijwerken)
# Vangnetten: lukt de thuis-wifi niet, dan meteen terug naar de hotspot; na 60 minuten op thuis-wifi
# gaat de hotspot hoe dan ook weer aan; na een herstart is de hotspot er altijd (/run is dan leeg).
STAND=/run/noodnet-thuiswifi          # bestaat zolang de thuis-wifi bewust aan staat (naam erin)
LOG=/var/log/noodnet-wifi.log
TERUG=noodnet-hotspot-terug
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >>"$LOG"; logger -t noodnet "wifi: $*"; }
chmod 0644 "$LOG" 2>/dev/null

hotspot_aan() {
  local WIFI
  WIFI="$(cat "$STAND" 2>/dev/null)"
  systemctl stop "$TERUG.timer" >/dev/null 2>&1
  [ -n "$WIFI" ] && nmcli con down "$WIFI" >/dev/null 2>&1
  nmcli dev set wlan0 managed no >/dev/null 2>&1
  rm -f "$STAND"
  systemctl start noodnet-ap && sleep 3 && systemctl restart noodnet-dhcp
  if systemctl is-active -q noodnet-ap; then log "hotspot weer aan"
  else log "hotspot starten lukte niet; de bewaker probeert het binnen een minuut opnieuw"; fi
}

later() {       # $1 = wachttijd, bijv. 1min of 60min
  systemctl stop "$TERUG.timer" >/dev/null 2>&1
  systemd-run -q --collect --unit="$TERUG" --on-active="$1" /bin/bash "$0" hotspot >/dev/null 2>&1
}

case "$1" in
  thuiswifi)
    WIFI=$(nmcli -t -f NAME,TYPE con show | awk -F: '$2=="802-11-wireless"{print $1; exit}')
    [ -n "$WIFI" ] || { log "FOUT: geen thuis-wifi bekend"; exit 0; }
    echo "$WIFI" > "$STAND"; chmod 0644 "$STAND"         # bewaker laat wlan0 nu met rust
    log "hotspot uit, verbinden met thuis-wifi '$WIFI'"
    later 60min                                          # vangnet
    systemctl stop noodnet-dhcp noodnet-ap
    ip addr flush dev wlan0 2>/dev/null
    nmcli dev set wlan0 managed yes
    sleep 4
    if nmcli -w 60 con up "$WIFI" >/dev/null 2>&1; then
      ADRES=$(ip -4 -o addr show dev wlan0 | awk '{print $4}' | cut -d/ -f1 | head -1)
      log "verbonden met '$WIFI': $ADRES"
      mkdir -p /var/lib/noodnet && echo "$ADRES" > /var/lib/noodnet/thuiswifi-adres && chmod 0644 /var/lib/noodnet/thuiswifi-adres
    else
      log "FOUT: verbinden met '$WIFI' lukte niet; hotspot weer aan"
      hotspot_aan
    fi ;;
  hotspot)
    hotspot_aan ;;
  hotspot_later)
    [ -f "$STAND" ] || exit 0
    log "hotspot gaat over 1 minuut weer aan"
    later 1min ;;
  *)
    echo "Gebruik: $0 thuiswifi | hotspot | hotspot_later"; exit 1 ;;
esac
exit 0

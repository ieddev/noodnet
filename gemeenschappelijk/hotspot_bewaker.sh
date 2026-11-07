#!/bin/bash
# Bewaker van de Noodnet-hotspot (draait als root, via noodnet-hotspot.timer, elke minuut).
#  - Hotspot uit en wlan0 niet bewust met een ander netwerk verbonden (hotspot.sh thuiswifi)?
#    Dan gaat de hotspot weer aan.
#  - Hotspot aan? Dan controleren of hij ook echt bruikbaar is: wlan0 in AP-modus, adres 10.42.0.1,
#    NetworkManager blijft eraf, IP-uitdeling (dnsmasq) draait. Zo niet: herstellen.
#    (Gezien op een Pi 4 met Trixie: na de eerste herstart was de hotspot zichtbaar, maar de
#    beheerpagina niet bereikbaar; na nog een start wel. Dit herstelt dat binnen een minuut.)
[ -f /etc/noodnet/hostapd.conf ] || exit 0
systemctl is-enabled -q noodnet-ap 2>/dev/null || exit 0
meld() { logger -t noodnet "hotspot: $*"; echo "hotspot: $*"; }

if systemctl is-active -q noodnet-ap; then
  # Even wachten als hostapd net (opnieuw) gestart is
  SINDS=$(systemctl show -p ActiveEnterTimestampMonotonic --value noodnet-ap 2>/dev/null)
  NU=$(awk '{printf "%d", $1 * 1000000}' /proc/uptime)
  [ -n "$SINDS" ] && [ "$SINDS" -gt 0 ] && [ $((NU - SINDS)) -lt 30000000 ] && exit 0

  NM=$(nmcli -t -f DEVICE,STATE dev 2>/dev/null | awk -F: '$1=="wlan0"{print $2}')
  if [ -n "$NM" ] && [ "$NM" != "unmanaged" ]; then
    meld "NetworkManager had wlan0 weer ($NM): losgemaakt, hotspot opnieuw gestart"
    nmcli dev set wlan0 managed no 2>/dev/null || true
    systemctl restart noodnet-ap; sleep 3; systemctl restart noodnet-dhcp
    exit 0
  fi
  if ! iw dev wlan0 info 2>/dev/null | grep -q "type AP"; then
    meld "wlan0 niet in AP-modus: hotspot opnieuw gestart"
    systemctl restart noodnet-ap; sleep 3; systemctl restart noodnet-dhcp
    exit 0
  fi
  if ! ip -4 addr show dev wlan0 2>/dev/null | grep -q "inet 10\.42\.0\.1/"; then
    meld "adres 10.42.0.1 ontbrak op wlan0: teruggezet"
    ip addr add 10.42.0.1/24 dev wlan0 2>/dev/null || true
    systemctl restart noodnet-dhcp
    exit 0
  fi
  if ! systemctl is-active -q noodnet-dhcp; then
    meld "IP-uitdeling (dnsmasq) liep niet: gestart"
    systemctl restart noodnet-dhcp
  fi
  exit 0
fi

STATUS=$(nmcli -t -f DEVICE,STATE dev 2>/dev/null | awk -F: '$1=="wlan0"{print $2}')
case "$STATUS" in
  connected|connecting*) exit 0 ;;     # thuiswifi: zo laten tot de herstart
esac
systemctl start noodnet-ap noodnet-dhcp && meld "opnieuw aangezet (wlan0 was: ${STATUS:-onbekend})"
exit 0

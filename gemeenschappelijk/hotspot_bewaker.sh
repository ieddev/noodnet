#!/bin/bash
# Bewaker van de Noodnet-hotspot (draait als root, via noodnet-hotspot.timer, elke minuut).
# Staat de hotspot uit en is de wifi niet bewust met een ander netwerk verbonden
# (hotspot.sh thuiswifi), dan gaat de hotspot weer aan.
[ -f /etc/noodnet/hostapd.conf ] || exit 0
systemctl is-enabled -q noodnet-ap 2>/dev/null || exit 0
if systemctl is-active -q noodnet-ap; then
  systemctl is-active -q noodnet-dhcp || systemctl start noodnet-dhcp
  exit 0
fi
STATUS=$(nmcli -t -f DEVICE,STATE dev 2>/dev/null | awk -F: '$1=="wlan0"{print $2}')
case "$STATUS" in
  connected|connecting*) exit 0 ;;     # thuiswifi: zo laten tot de herstart
esac
systemctl start noodnet-ap noodnet-dhcp && logger -t noodnet "hotspot opnieuw aangezet (wlan0 was: ${STATUS:-onbekend})"
exit 0

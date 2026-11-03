#!/bin/bash
# Bewaker van de Noodnet-hotspot (draait als root, via noodnet-hotspot.timer, elke minuut).
# Is de wifi nergens mee verbonden, dan gaat de hotspot aan. Is de wifi bewust met een
# ander netwerk verbonden (hotspot.sh thuiswifi), dan blijft dat zo.
nmcli -t -f NAME con show 2>/dev/null | grep -qx noodnet-ap || exit 0
STATUS=$(nmcli -t -f DEVICE,STATE dev 2>/dev/null | awk -F: '$1=="wlan0"{print $2}')
case "$STATUS" in
  connected|connecting*|"connected (externally)") exit 0 ;;
esac
nmcli radio wifi on >/dev/null 2>&1
nmcli con up noodnet-ap >/dev/null 2>&1 && logger -t noodnet "hotspot opnieuw aangezet (wlan0 was: ${STATUS:-onbekend})"
exit 0

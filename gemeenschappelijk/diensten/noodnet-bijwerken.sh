#!/bin/bash
# Noodnet bijwerken op de achtergrond (knop op de beheerpagina, dienst noodnet-bijwerken).
# Draait als root (geïnstalleerd in /usr/local/lib/noodnet, niet door de gebruiker te wijzigen) en
# start de gewone installatie als de Noodnet-gebruiker. Omdat sudo bij die gebruiker een wachtwoord
# kan vragen, krijgt hij alleen zolang het bijwerken duurt sudo zonder wachtwoord; dat wordt daarna
# weggehaald (en bij een stroomstoring tijdens het bijwerken bij de volgende start, via tmpfiles.d).
# Altijd de code van GitHub (ieddev/noodnet), nooit wat er lokaal in de bronmap is veranderd.
#
# Met als derde argument 'thuiswifi' (dienst noodnet-bijwerken-thuiswifi): eerst de hotspot uit en
# verbinden met de bekende thuis-wifi, na afloop (ook bij een fout) de hotspot weer aan. Vangnet: een
# timer zet de hotspot na 45 minuten hoe dan ook terug, en na een herstart is hij er altijd.
U="$1"; MAP="$2"; MODUS="$3"
MERK=/run/noodnet-bijwerken-thuiswifi          # zolang dit bestaat laat de hotspot-bewaker wlan0 met rust
WIFI=""
LOG=/var/log/noodnet-bijwerken.log
SUD=/etc/sudoers.d/noodnet-bijwerken-tijdelijk
REPO=https://github.com/ieddev/noodnet
[ "$(id -u)" = 0 ] || { echo "Moet als root draaien."; exit 1; }
THUIS="$(getent passwd "$U" | cut -d: -f6)"
[ -n "$U" ] && [ -d "$THUIS" ] || { echo "Onbekende gebruiker: $U"; exit 1; }
BRON="$THUIS/noodnet-bron"

hotspot_terug() {
  [ -f "$MERK" ] || return 0
  echo "-- Thuis-wifi verbreken, hotspot weer aan"
  [ -n "$WIFI" ] && nmcli con down "$WIFI" >/dev/null 2>&1
  nmcli dev set wlan0 managed no >/dev/null 2>&1
  rm -f "$MERK"
  systemctl stop noodnet-hotspot-terug.timer >/dev/null 2>&1
  systemctl start noodnet-ap && sleep 3 && systemctl restart noodnet-dhcp
  if systemctl is-active -q noodnet-ap; then echo "   Hotspot is weer aan (10.42.0.1)."
  else echo "   Hotspot starten lukte niet; de bewaker probeert het binnen een minuut opnieuw."; fi
}
trap 'rm -f "$SUD" "$SUD.tmp"; hotspot_terug >>"$LOG" 2>&1' EXIT   # vangnet; normaal al gedaan

naar_thuiswifi() {
  WIFI=$(nmcli -t -f NAME,TYPE con show | awk -F: '$2=="802-11-wireless"{print $1; exit}')
  if [ -z "$WIFI" ]; then
    echo "FOUT: deze Pi kent geen thuis-wifi. Gebruik een netwerkkabel, of USB-tethering met je telefoon."
    return 1
  fi
  echo "-- Hotspot uit, verbinden met thuis-wifi '$WIFI'"
  touch "$MERK"
  # Vangnet als dit script onverwacht stopt: na 45 minuten de hotspot hoe dan ook terug
  systemctl stop noodnet-hotspot-terug.timer >/dev/null 2>&1
  systemd-run -q --collect --unit=noodnet-hotspot-terug --on-active=45min /bin/bash -c \
    "rm -f $MERK; nmcli dev disconnect wlan0; nmcli dev set wlan0 managed no; systemctl start noodnet-ap; sleep 3; systemctl restart noodnet-dhcp" \
    >/dev/null 2>&1 || true
  systemctl stop noodnet-dhcp noodnet-ap
  ip addr flush dev wlan0 2>/dev/null
  nmcli dev set wlan0 managed yes
  sleep 4
  if ! nmcli -w 60 con up "$WIFI" >/dev/null 2>&1; then
    echo "FOUT: verbinden met '$WIFI' lukte niet (buiten bereik, of wachtwoord gewijzigd?)."
    return 1
  fi
  for i in $(seq 1 30); do
    if git ls-remote -q "$REPO" refs/heads/main >/dev/null 2>&1; then echo "   Verbonden, internet werkt."; return 0; fi
    sleep 2
  done
  echo "FOUT: verbonden met '$WIFI', maar geen internet."
  return 1
}

als() { runuser -u "$U" -- env HOME="$THUIS" USER="$U" LOGNAME="$U" \
          PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin "$@"; }

{
  echo "== START $(date '+%Y-%m-%d %H:%M:%S') (via de beheerpagina)"
  echo "$U ALL=(ALL) NOPASSWD: ALL" > "$SUD.tmp"; chmod 0440 "$SUD.tmp"
  if ! visudo -cf "$SUD.tmp" >/dev/null; then echo "FOUT: tijdelijke sudo-regel ongeldig."; echo "== EINDE 2"; exit 0; fi
  mv "$SUD.tmp" "$SUD"
  if [ "$MODUS" = thuiswifi ] && ! naar_thuiswifi; then hotspot_terug; echo "== EINDE 4"; exit 0; fi
  if [ ! -d "$BRON/.git" ]; then
    rm -rf "$BRON"
    als git clone -q "$REPO" "$BRON" || { echo "FOUT: ophalen van GitHub mislukt (internet?)."; hotspot_terug; echo "== EINDE 3"; exit 0; }
  fi
  als git -C "$BRON" remote set-url origin "$REPO"
  if ! { als git -C "$BRON" fetch -q origin main && als git -C "$BRON" reset -q --hard origin/main; }; then
    echo "FOUT: ophalen van GitHub mislukt (internet?)."; hotspot_terug; echo "== EINDE 3"; exit 0
  fi
  echo "   versie: $(als git -C "$BRON" log -1 --format='%h %cd' --date=format:'%Y-%m-%d %H:%M')"
  ( cd "$THUIS" && als env NOODNET_UIT_BRON=1 bash "$BRON/installeer.sh" </dev/null )
  RC=$?
  hotspot_terug
  echo "== EINDE $RC"
} >"$LOG" 2>&1
chmod 0644 "$LOG"
exit 0

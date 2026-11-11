#!/bin/bash
# Noodnet bijwerken op de achtergrond (knop op de beheerpagina, dienst noodnet-bijwerken).
# Draait als root (geïnstalleerd in /usr/local/lib/noodnet, niet door de gebruiker te wijzigen) en
# start de gewone installatie als de Noodnet-gebruiker. Omdat sudo bij die gebruiker een wachtwoord
# kan vragen, krijgt hij alleen zolang het bijwerken duurt sudo zonder wachtwoord; dat wordt daarna
# weggehaald (en bij een stroomstoring tijdens het bijwerken bij de volgende start, via tmpfiles.d).
# Altijd de code van GitHub (ieddev/noodnet), nooit wat er lokaal in de bronmap is veranderd.
U="$1"; MAP="$2"
LOG=/var/log/noodnet-bijwerken.log
SUD=/etc/sudoers.d/noodnet-bijwerken-tijdelijk
REPO=https://github.com/ieddev/noodnet
[ "$(id -u)" = 0 ] || { echo "Moet als root draaien."; exit 1; }
THUIS="$(getent passwd "$U" | cut -d: -f6)"
[ -n "$U" ] && [ -d "$THUIS" ] || { echo "Onbekende gebruiker: $U"; exit 1; }
BRON="$THUIS/noodnet-bron"
trap 'rm -f "$SUD" "$SUD.tmp"' EXIT

als() { runuser -u "$U" -- env HOME="$THUIS" USER="$U" LOGNAME="$U" \
          PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin "$@"; }

{
  echo "== START $(date '+%Y-%m-%d %H:%M:%S') (via de beheerpagina)"
  echo "$U ALL=(ALL) NOPASSWD: ALL" > "$SUD.tmp"; chmod 0440 "$SUD.tmp"
  if ! visudo -cf "$SUD.tmp" >/dev/null; then echo "FOUT: tijdelijke sudo-regel ongeldig."; echo "== EINDE 2"; exit 0; fi
  mv "$SUD.tmp" "$SUD"
  if [ ! -d "$BRON/.git" ]; then
    rm -rf "$BRON"
    als git clone -q "$REPO" "$BRON" || { echo "FOUT: ophalen van GitHub mislukt (internet?)."; echo "== EINDE 3"; exit 0; }
  fi
  als git -C "$BRON" remote set-url origin "$REPO"
  if ! { als git -C "$BRON" fetch -q origin main && als git -C "$BRON" reset -q --hard origin/main; }; then
    echo "FOUT: ophalen van GitHub mislukt (internet?)."; echo "== EINDE 3"; exit 0
  fi
  echo "   versie: $(als git -C "$BRON" log -1 --format='%h %cd' --date=format:'%Y-%m-%d %H:%M')"
  ( cd "$THUIS" && als env NOODNET_UIT_BRON=1 bash "$BRON/installeer.sh" </dev/null )
  echo "== EINDE $?"
} >"$LOG" 2>&1
chmod 0644 "$LOG"
exit 0

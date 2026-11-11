#!/bin/bash
# Noodnet bijwerken op de achtergrond (knop op de beheerpagina, dienst noodnet-bijwerken).
# Doet hetzelfde als 'noodnet-bijwerken' via ssh; het verslag komt in ~/noodnet/bijwerken.log.
LOG="$HOME/noodnet/bijwerken.log"
{
  echo "== START $(date '+%Y-%m-%d %H:%M:%S') (via de beheerpagina)"
  if ! sudo -n true 2>/dev/null; then
    echo "FOUT: sudo vraagt om een wachtwoord voor gebruiker $(id -un)."
    echo "Werk deze Pi bij via ssh met: noodnet-bijwerken"
    echo "== EINDE 2"; exit 0
  fi
  if [ -f "$HOME/noodnet-bron/installeer.sh" ]; then
    bash "$HOME/noodnet-bron/installeer.sh" </dev/null
  else
    bash <(curl -fsSL https://raw.githubusercontent.com/ieddev/noodnet/main/installeer.sh) </dev/null
  fi
  echo "== EINDE $?"
} >"$LOG" 2>&1
exit 0

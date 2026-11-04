#!/bin/bash
# Wacht (max. 120 s) tot rnsd zijn gedeelde instantie aanbiedt, zodat de brug
# niet te vroeg start. Bij een ontbrekende RNode doet rnsd er langer over.
for _ in $(seq 120); do
  if ss -xlp 2>/dev/null | grep -q 'rns/' || ss -ltn 2>/dev/null | grep -q ':37428 '; then
    sleep 2; exit 0
  fi
  sleep 1
done
echo "rnsd biedt na 120 s nog geen gedeelde instantie aan" >&2
exit 0      # toch starten; de brug stopt zelf als er geen rnsd is

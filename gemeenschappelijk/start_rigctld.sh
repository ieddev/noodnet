#!/bin/bash
# Start rigctld voor de 2 m-set als CAT is gekozen op het tabblad Radio (rigctld.env).
# Zonder CAT wacht deze dienst gewoon (dan blijft hij 'actief', maar doet niets).
MAP="$(cd "$(dirname "$0")" && pwd)"
ENV="$MAP/rigctld.env"
if [ ! -f "$ENV" ]; then
  echo "CAT niet ingesteld (tabblad Radio): rigctld wordt niet gebruikt."
  exec sleep infinity
fi
# shellcheck disable=SC1090
. "$ENV"
if [ ! -e "$POORT" ]; then
  echo "CAT-poort $POORT niet gevonden; is de set aangesloten en aan? Opnieuw over 10 s."
  sleep 10; exit 1
fi
echo "rigctld: model $MODEL, poort $POORT, $BAUD baud"
exec rigctld -m "$MODEL" -r "$POORT" -s "$BAUD" -T 127.0.0.1 -t 4532

# Netwerkbestanden per gemeente

Hier staat per gemeente het **netwerkbestand** van Noodnet: de 2 m-frequentie, de disciplines met de
roepnamen van de eindposten, en de LoRa-instellingen. De supervisor van de gemeente beheert het.

**Alleen bestanden ZONDER IFAC** (tabblad Netwerk → *Exporteren zonder IFAC*). Deze map is openbaar.
Gebruikt je gemeente IFAC (aanbevolen: dan kan niemand anders met een RNode en de app op jullie
LoRa-netwerk), geef het IFAC-wachtwoord dan apart, via een vertrouwelijk kanaal, aan de beheerders van
de steunpunten. Zij vullen het één keer in op het tabblad Netwerk (*IFAC*); bij het ophalen van een
bestand zonder IFAC blijft hun eigen IFAC staan.

| Bestand | Voor wie |
|---|---|
| `voorbeeld.json` | Zendamateurs elders in het land die willen testen: inladen en op het tabblad Netwerk aanpassen aan de eigen gemeente (naam, frequentie, roepnamen van de eindposten). |
| `deventer.json` | Deelnemers in Deventer (beheerd door PD3PAM). |

## Bestand toevoegen of bijwerken (supervisor)

1. Op je steunpunt: tabblad **Netwerk** → instellen → **Opslaan** → **Exporteren zonder IFAC**.
2. Hernoem het bestand naar de gemeente, in kleine letters: `deventer.json`.
3. Op GitHub: open deze map → **Add file → Upload files** → bestand kiezen → **Commit changes**.
   (Bijwerken: hetzelfde, met dezelfde naam; het oude bestand wordt vervangen.)

## Gebruiken (iedereen in de gemeente)

Op elk steunpunt (tabblad **Netwerk**) en elke eindpost (tabblad **Instellingen**), bij *Ophalen*:

    https://github.com/ieddev/noodnet/blob/main/netwerken/deventer.json

Daarna is vóór een oefening of inzet één tik op **Opnieuw ophalen** genoeg (de Pi heeft dan internet
nodig). Controleer op het tabblad **Status** dat iedereen dezelfde versie heeft.

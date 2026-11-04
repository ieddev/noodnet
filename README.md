# Noodnet

Een off-grid noodnet voor de regio: vrijwilligers melden met een telefoon en een
**RNode** via LoRa (ISM-banden) bij een **Noodsteunpunt**. Daar zet een zendamateur
de melding **leesbaar** door over **2 m** (AX.25, onder eigen roepnaam) naar de
**eindposten** van de hulpdiensten.

```
telefoon + RNode ──LoRa 433/868──► NOODSTEUNPUNT (Pi + 2 m-set + RNodes)
                                         │  leesbaar AX.25, 144,925 MHz
                                         ▼
                                   EINDPOST (Pi + 2 m-set + scherm)  ── M/ETHANE-scherm, logboek
```

Op de amateurband gaat niets versleuteld: het steunpunt pakt de melding uit en
zendt hem als gewone tekst. Op een eindpost draait geen Reticulum.

**Achtergrond en visie:** [ieddev.ddns.net](http://ieddev.ddns.net) (PD3PAM).
De installatie en de procedure op deze GitHub-pagina zijn leidend.

## Installeren

1. Zet met de **Raspberry Pi Imager** een image op een SD-kaart
   - Noodsteunpunt: *Raspberry Pi OS Lite (64-bit)*
   - Eindpost: *Raspberry Pi OS (64-bit)* met bureaublad (voor het scherm)
   - Bij *OS-instellingen bewerken*: gebruiker **noodnet**, SSH aan, je wifi,
     tijdzone Europe/Amsterdam
2. Start de Pi, log in (`ssh noodnet@<naam>.local`) en typ:

```bash
bash <(curl -sL https://raw.githubusercontent.com/ieddev/noodnet/main/installeer.sh)
```

3. Beantwoord de vragen (soort Pi, roepnaam, wachtwoorden) en herstart.
4. Verbind je telefoon met de wifi **Noodnet-&lt;roepnaam&gt;** en open
   **http://10.42.0.1:8080**. Kies op het tabblad **Radio** de geluidskaart, PTT
   (en bij een steunpunt de RNode-poorten).

Bijwerken: `noodnet-bijwerken` (instellingen blijven bewaard).

De volledige procedure staat in [docs/PROCEDURE.md](docs/PROCEDURE.md).

## Testen

Zie [docs/TESTPLAN.md](docs/TESTPLAN.md): scenario's voor aanmelden, beheer en melden.

## Inhoud

| Map | Wat |
|---|---|
| `installeer.sh` | Installeert en werkt bij (beide soorten Pi) |
| `gemeenschappelijk/` | 2 m-protocol, radio/hotspot-module, startpagina met app-download, diensten |
| `steunpunt/` | Brug LoRa → 2 m, beheerpagina, aanmeldkaart |
| `eindpost/` | Ontvanger 2 m → MQTT + logboek, beheerpagina, Node-RED M/ETHANE-scherm |
| `app/` | Patch op Sideband 2.1.0 (M/ETHANE, kaart, QR-scanner, baken) en bouwinstructie |
| `docs/` | Procedure |

De app (APK) staat bij de [Releases](../../releases) en wordt door de
installatie op elke Pi gezet, zodat vrijwilligers hem ter plekke via de hotspot
kunnen downloaden.

# Noodnet

Een off-grid noodnet voor de regio: vrijwilligers melden met een telefoon en een
**RNode** via LoRa (ISM-banden) bij een **Noodsteunpunt**. Daar zet een zendamateur
de melding **leesbaar** door over **2 m** (AX.25, onder eigen roepnaam) naar de
**eindposten** van de hulpdiensten.

```
telefoon + RNode ──LoRa 433/868──► NOODSTEUNPUNT (Pi + 2 m-set + RNodes)
                                         │  leesbaar AX.25, 2 m (per gemeente)
                                         ▼
                                   EINDPOST (Pi + 2 m-set + scherm)  ── M/ETHANE-scherm, logboek
```

Op de amateurband gaat niets versleuteld: het steunpunt pakt de melding uit en
zendt hem als gewone tekst. Op een eindpost draait geen Reticulum.

**Achtergrond en visie:** [noodnet.ied.nl](http://noodnet.ied.nl) (PD3PAM).
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

De volledige procedure staat in [docs/PROCEDURE.md](docs/PROCEDURE.md), en om af te drukken
als PDF: [docs/Noodnet-procedure.pdf](docs/Noodnet-procedure.pdf).

Voor **vrijwilligers** (RNode en app, aanmelden en melden) is er een aparte, korte handleiding:
[docs/VRIJWILLIGER.md](docs/VRIJWILLIGER.md), ook als PDF met zakkaart:
[docs/Noodnet-vrijwilliger.pdf](docs/Noodnet-vrijwilliger.pdf).

Voor de **beheerder** van een steunpunt (opdrachten via de app, beheerpagina, begin en einde van een inzet)
is er een korte handleiding: [docs/BEHEERDER.md](docs/BEHEERDER.md), ook als PDF met zakkaart:
[docs/Noodnet-beheerder.pdf](docs/Noodnet-beheerder.pdf).

## Testen

Zie [docs/TESTPLAN.md](docs/TESTPLAN.md): scenario's voor aanmelden, beheer en melden. Om af te drukken
en af te vinken: [docs/Noodnet-testplan.pdf](docs/Noodnet-testplan.pdf).

## Inhoud

| Map | Wat |
|---|---|
| `installeer.sh` | Installeert en werkt bij (beide soorten Pi) |
| `gemeenschappelijk/` | 2 m-protocol, radio/hotspot-module, startpagina met app-download, diensten |
| `steunpunt/` | Brug LoRa → 2 m, beheerpagina, aanmeldkaart |
| `eindpost/` | Ontvanger 2 m → MQTT + logboek, beheerpagina, Node-RED M/ETHANE-scherm |
| `app/` | Patch op Sideband 2.1.0 (M/ETHANE, kaart, QR-scanner, baken) en bouwinstructie |
| `docs/` | Procedure, handleidingen voor vrijwilliger en beheerder (ook als PDF), testplan; `docs/pdf/maak_pdf.py` maakt de PDF's opnieuw |

De app (APK) staat bij de [Releases](../../releases) en wordt door de
installatie op elke Pi gezet, zodat vrijwilligers hem ter plekke via de hotspot
kunnen downloaden.

## Licentie en openheid

Noodnet is open en blijft open. Wat geldt voor welk deel:

| Deel | Licentie |
|---|---|
| De Noodnet-code (installatie, brug, beheerpagina's, scripts, Node-RED-flow) | [EUPL-1.2](LICENSE), de open-sourcelicentie van de Europese Unie, ook officieel in het Nederlands |
| `app/` (de patch op Sideband) | [CC BY-NC-SA 4.0](app/LICENSE), dezelfde licentie als Sideband zelf |
| `docs/` (procedure, testplan) en de teksten en schema's op de website | [CC BY-SA 4.0](docs/LICENSE) |

Wat dat in gewone taal betekent:

- Iedereen mag Noodnet gebruiken, aanpassen en doorgeven. Wie een aangepaste versie
  verspreidt, geeft de broncode daarvan ook vrij, onder dezelfde licentie.
- De app mag **nooit tegen betaling** worden verspreid of gebruikt, ook niet aan een
  gemeente of hulpdienst. Gratis uitdelen (zoals via het steunpunt) mag wel.

### Waar Noodnet op voortbouwt

Noodnet maakt geen eigen versie van Reticulum of Sideband na. Het gebruikt de
officiële pakketten, ongewijzigd, zoals de makers ze verspreiden:

- [Reticulum](https://reticulum.network) (RNS) en [LXMF](https://github.com/markqvist/lxmf)
  van Mark Qvist, onder de *Reticulum License*. Die staat veel toe, met twee extra
  voorwaarden die ook gelden voor wie Noodnet draait: niet gebruiken in systemen die
  bedoeld zijn om mensen schade te doen, en niet gebruiken om datasets voor AI of
  machine learning te maken.
- [Sideband](https://github.com/markqvist/Sideband) van Mark Qvist, onder
  CC BY-NC-SA 4.0. De Noodnet-app is Sideband met een kleine patch erop
  (zie [app/BOUWEN.md](app/BOUWEN.md)); alle eer voor de app zelf gaat naar Sideband.
- [Direwolf](https://github.com/wb2osz/direwolf) (GPL-2.0),
  [Hamlib](https://hamlib.github.io) (LGPL/GPL), Mosquitto (EPL/EDL) en Node-RED
  (Apache-2.0). Die worden bij de installatie uit de gewone pakketbronnen gehaald.

### Hoe Noodnet gemaakt is

Gert de Haan, PD3PAM, heeft Noodnet ontworpen, de keuzes gemaakt en alles in de
praktijk getest op echte sets en Raspberry Pi's. Een groot deel van de code en
documentatie is in samenwerking met een AI-assistent (Claude, van Anthropic)
geschreven. Elke wijziging is door hem beoordeeld en getest.

Noodnet bevat geen code van Reticulum of Sideband die door AI is herschreven of
nagebouwd: het gebruikt alleen hun openbare programmeerinterface, of
(bij de app) een kleine, herkenbare patch op de echte broncode.

Vragen of opmerkingen over de licentie? Neem contact op via
[noodnet.ied.nl/contact](http://noodnet.ied.nl).

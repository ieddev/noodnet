# Noodnet - een Noodsteunpunt of Eindpost opzetten

Deze procedure is voor zendamateurs die een **Noodsteunpunt** of een **Eindpost**
willen inrichten met hun eigen transceiver. Voorkennis van Linux is niet nodig.
Reken op ongeveer een uur, waarvan de meeste tijd wachten.

| | Noodsteunpunt | Eindpost |
|---|---|---|
| Doel | Doorgeefluik: vrijwilligers (LoRa) naar 2 m | Ontvangt meldingen bij een hulpdienst |
| Raspberry Pi | Pi 4 of 5 (Pi 3B+ kan ook) | Pi 4 of 5 |
| Image | Raspberry Pi OS **Lite** (64-bit) | Raspberry Pi OS (64-bit) **met bureaublad** |
| Radio | 2 m-set met USB-geluid + PTT (bijv. FT-818 met SCU-17) | 2 m-set met USB-geluid + PTT (bijv. IC-9700) |
| LoRa | 1 of 2 RNodes via USB (433 en/of 868 MHz) | – |
| Scherm | Niet nodig | Monitor via HDMI (of een pc/telefoon via de hotspot) |
| Voeding | Accu (12 V) voor set én Pi; voor de Pi een goede 5 V-omvormer (Pi 5: 5 A) | Noodstroom van de hulpdienst, of accu |
| Overig | SD-kaart 32 GB | SD-kaart 32 GB |

Getest met Raspberry Pi OS **Trixie** (Debian 13), november 2026.

Frequenties: 2 m **144,925 MHz** (AX.25 1200 baud). LoRa **434,100 MHz** en
**869,525 MHz** (ISM). Op de amateurband gaat alles **leesbaar** en onder je eigen
roepnaam.

---

## Stap 1 - SD-kaart maken

1. Installeer de **Raspberry Pi Imager** op je pc (raspberrypi.com/software).
2. Kies het **apparaat** (bijv. Raspberry Pi 5).
3. Kies het **besturingssysteem**:
   - Noodsteunpunt: *Raspberry Pi OS (other) → Raspberry Pi OS Lite (64-bit)*
   - Eindpost: *Raspberry Pi OS (64-bit)*
4. Kies de **SD-kaart**.
5. Klik op **Volgende → Instellingen bewerken** en vul in:

| Tabblad | Instelling | Waarde |
|---|---|---|
| Algemeen | Hostnaam | `noodnet-<roepnaam>-<ssid>`, bijv. `noodnet-pd3pam-1` |
| | Gebruikersnaam | **noodnet** |
| | Wachtwoord | zelf kiezen (en bewaren) |
| | Wifi | je **thuis-wifi** (alleen nodig tijdens de installatie) |
| | Land wifi | NL |
| | Tijdzone / toetsenbord | Europe/Amsterdam / us |
| Diensten | SSH | **aan**, met wachtwoord |

6. **Opslaan → Ja** en wachten tot de kaart klaar is.

## Stap 2 - Aansluiten en opstarten

1. SD-kaart in de Pi.
2. Sluit de **2 m-set** aan met de USB-kabel (geluid + PTT) en zet de set aan.
3. Noodsteunpunt: sluit de **RNode(s)** aan via USB.
4. Eindpost: sluit de **monitor** aan.
5. Voeding erop. De eerste start duurt een paar minuten.

## Stap 3 - Installeren

1. Log vanaf je pc in op de Pi:
   - Windows: open *PowerShell*; Mac/Linux: open *Terminal*
   - typ: `ssh noodnet@noodnet-pd3pam-1.local` (jouw hostnaam) en je wachtwoord
2. Typ (of plak) precies deze regel en druk op Enter:

```bash
bash <(curl -sL https://raw.githubusercontent.com/ieddev/noodnet/main/installeer.sh)
```

3. Beantwoord de vragen:

| Vraag | Antwoord |
|---|---|
| Wat wordt deze Pi? | **1** = Noodsteunpunt, **2** = Eindpost |
| Roepnaam met SSID | bijv. `PD3PAM-1` (elke Pi een eigen SSID) |
| Wachtwoord hotspot | min. 8 tekens, of Enter voor een gekozen wachtwoord - **schrijf het op** |
| Wachtwoord beheerpagina | min. 8 tekens, twee keer - **schrijf het op** |

4. Wacht tot **Klaar** verschijnt (Eindpost: Node-RED duurt 5-15 minuten extra).
5. Herstart: `sudo reboot`

Na de herstart maakt de Pi een eigen wifi-netwerk: **Noodnet-PD3PAM-1**. Dat werkt
ook zonder stroomnet en zonder internet. Je thuis-wifi gebruikt de Pi niet meer.

## Stap 4 - Instellen via de beheerpagina

1. Verbind je **telefoon** met de wifi *Noodnet-&lt;roepnaam&gt;*.
   Android meldt "geen internet": kies **Verbonden blijven**.
2. Open in de browser: **http://10.42.0.1:8080** - gebruiker **beheer**.

### Noodsteunpunt

| Tabblad | Wat doen |
|---|---|
| **Steunpunt** | Naam van het steunpunt, aanmeldcode (min. 4 tekens), *Wie mag melden* = **Aan**. Opslaan. |
| **Radio** | Geluidskaart van de set, PTT-poort (+ RTS), RNode-poort voor 433 en/of 868, zendvermogen. Opslaan. |
| **Netwerk** | Gemeente, disciplines met de roepnaam van hun eindpost, LoRa-instellingen. Gelijk houden op alle steunpunten van de gemeente. Opslaan. |
| **Kaart** | *Nieuwe kaart maken*. |
| **Status** | Alles groen? Geen rode melding? |

**Jezelf beheerder maken** (zonder iets over te typen):

1. Installeer de Noodnet-app: open **http://10.42.0.1** en tik op *Noodnet-app downloaden*.
2. Koppel in de app je RNode (Bluetooth).
3. Open het M/ETHANE-scherm en tik op **Kaart van steunpunt scannen**. Scan de
   QR-code op het tabblad *Kaart* (op een tweede scherm, of afgedrukt).
4. Kies de band van je RNode en tik **Aanmelden**.
5. Tabblad **Status** → *Wachten op goedkeuring* → **Goedkeuren als beheerder**.

Daarna krijg jij de aanmeldingen van vrijwilligers en kun je vanaf je telefoon
`LIJST`, `JA <nr>`, `NEE <nr>` en `CODE <nieuw>` sturen.

**Kaart afdrukken:** tabblad Kaart → *Kaart openen om af te drukken* (A5/A6,
lamineren). Staat er IFAC op, dan is de kaart **VERTROUWELIJK**.

### Eindpost

| Tabblad | Wat doen |
|---|---|
| **Instellingen** | Naam van de post, roepnaam (= die van de installatie), disciplines (of *Alle meldingen*), eventueel meelezen. Opslaan. |
| **Radio** | Geluidskaart van de set, PTT-poort (+ RTS). Opslaan. |
| **Status** | Alles groen? |

Laat daarna de beheerder van elk steunpunt in de gemeente jouw roepnaam
toevoegen: tabblad **Netwerk** → bij de juiste discipline. Meerdere posten van
dezelfde dienst (bijv. een hoofdkazerne en een dependance) kan: zet beide
roepnamen bij die discipline, met een komma ertussen. Een M/ETHANE-melding wordt
dan herhaald tot **beide** posten hebben bevestigd.

Het **M/ETHANE-scherm** opent na het opstarten vanzelf op de monitor. Ook te
bekijken op een andere pc of telefoon via de hotspot: **http://10.42.0.1:1880/ui**.

## Stap 5 - Testen

- [ ] Status: alle diensten groen, hotspot aan
- [ ] Steunpunt: een telefoon meldt zich aan met de kaart en wordt goedgekeurd
- [ ] Steunpunt: `LIJST` vanaf de beheertelefoon geeft antwoord
- [ ] Een M/ETHANE-melding komt aan op de eindpost (scherm + logboek)
- [ ] Het steunpunt toont *bevestigd* (ACK) van de eindpost in het log
- [ ] Na een herstart werkt alles weer vanzelf

## Back-up maken (belangrijk!)

Maak na het instellen meteen een back-up: beheerpagina → tabblad **Back-up** →
*Back-up downloaden*. Bewaar het bestand veilig (niet mailen of delen).

- **Noodsteunpunt:** in de back-up zit de **sleutel** van het steunpunt. Daarmee
  houdt het steunpunt na een nieuwe SD-kaart **hetzelfde adres**: de gedrukte
  kaarten en de aangemelde vrijwilligers blijven geldig. Zonder back-up krijgt
  het steunpunt een nieuw adres en moet iedereen opnieuw aanmelden.
- **Eindpost:** instellingen en het hele logboek.

**Terugzetten** (bijv. na een nieuwe SD-kaart): eerst gewoon installeren (stap 1-3),
dan tabblad **Back-up** → bestand kiezen → *Terugzetten*. Daarna nog een keer
tabblad **Radio** controleren (andere USB-poorten?).

## De klok

Een Pi zonder internet weet na het aanzetten de tijd niet. Open daarom na het
opstarten even de beheerpagina op je **telefoon**: de Pi neemt dan automatisch de
tijd van je telefoon over (als hij meer dan een minuut afwijkt). Op het tabblad
Status staat *Tijd van de Pi* met de bron.

## Bijwerken

Sluit de Pi met een **netwerkkabel** aan op internet (of tijdelijk thuis-wifi:
`~/noodnet/hotspot.sh thuiswifi`) en typ:

```bash
noodnet-bijwerken
```

Instellingen, aanmeldingen en het logboek blijven bewaard. De nieuwste app
wordt meteen op de downloadpagina gezet.

## Problemen oplossen

| Probleem | Oplossing |
|---|---|
| Telefoon ziet wifi *Noodnet-…* niet | Pi herstarten. Wacht 2 minuten na het aanzetten. |
| Telefoon ziet de wifi wel, maar verbinden mislukt | Wachtwoord goed? Staat in `~/noodnet/hotspot.json`. Controle: `~/noodnet/hotspot.sh status` en `journalctl -u noodnet-ap -n 30`. |
| Beheerpagina opent niet | Op de hotspot? Adres **http://10.42.0.1:8080**. Mobiele data even uit. |
| Direwolf rood | Tabblad Radio: juiste geluidskaart? Set aan en via USB aangesloten? |
| Set zendt niet | Tabblad Radio: PTT-poort en RTS. IC-9700: menu *USB SEND* op RTS. SCU-17: tweede poort (if01). |
| Rode melding *Kaart en radio komen niet overeen* | Tabblad Netwerk opslaan met het vinkje *RNodes gelijkzetten* aan. Nieuwe kaart maken en opnieuw scannen. |
| Vrijwilligers komen niet door | Status: staan ze bij *Onbekende telefoons*? Laten aanmelden met de kaart. `rnstatus`: IFAC-overtredingen? → IFAC op kaart en Pi gelijk. |
| Steunpunt blijft herhalen | De roepnaam van de eindpost op het tabblad Netwerk klopt niet, of de eindpost staat uit. |
| Tijd in het logboek klopt niet | Open de beheerpagina op je telefoon: de Pi neemt de tijd over. |
| Status: *Nog niet bevestigd* | Die eindpost staat uit, is buiten bereik, of de roepnaam klopt niet. Het steunpunt blijft M/ETHANE herhalen tot elke genoemde eindpost bevestigt. |

## Veiligheid

- `gateway.id` (de sleutel van het steunpunt) nooit delen of kopiëren.
- Hotspot- en beheerwachtwoord alleen voor de zendamateur(s).
- Poort 8080 nooit naar internet openzetten.
- Het logboek van een eindpost bevat namen en locaties (AVG): de hulpdienst is eigenaar.

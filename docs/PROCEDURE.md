# Noodnet - een Noodsteunpunt of Eindpost opzetten

Deze procedure is voor zendamateurs die een **Noodsteunpunt** of een **Eindpost**
willen inrichten met hun eigen transceiver. Voorkennis van Linux is niet nodig.
Reken op ongeveer een uur, waarvan de meeste tijd wachten.

Achtergrond en visie op het noodnet: [noodnet.ied.nl](http://noodnet.ied.nl).

**Afdrukken?** Deze procedure staat ook als PDF-naslagwerk (A4) in
[Noodnet-procedure.pdf](Noodnet-procedure.pdf), met achterin een invulblad voor je eigen station.

| | Noodsteunpunt | Eindpost |
|---|---|---|
| Doel | Doorgeefluik: vrijwilligers (LoRa) naar 2 m | Ontvangt meldingen bij een hulpdienst |
| Raspberry Pi | **Pi 4 of 5** (geen Pi 3: de USB is te zwak voor set + 2 RNodes) | Pi 4 of 5 |
| Image | Raspberry Pi OS **Lite** (64-bit) | Raspberry Pi OS (64-bit) **met bureaublad** |
| Radio | 2 m-set met USB-geluid + PTT (bijv. FT-818 met SCU-17) | 2 m-set met USB-geluid + PTT (bijv. IC-9700) |
| LoRa | 1 of 2 RNodes via USB (433 en/of 868 MHz) | – |
| Scherm | Niet nodig | Monitor via HDMI (of een pc/telefoon via de hotspot) |
| Voeding | Accu (12 V) voor set én Pi; voor de Pi een goede 5 V-omvormer (Pi 5: 5 A) | Noodstroom van de hulpdienst, of accu |
| Overig | SD-kaart 32 GB | SD-kaart 32 GB |

Getest met Raspberry Pi OS **Trixie** (Debian 13), november 2026.

Frequenties: 2 m **per gemeente afgesproken** (standaard 144,925 MHz; AX.25 1200 baud). LoRa **434,100 MHz** en
**869,525 MHz** (ISM). Op de amateurband gaat alles **leesbaar** en onder je eigen
roepnaam.

---

## Volgorde bij een complete nieuwe opzet

1. **RNodes flashen**: alle RNodes, van het steunpunt én van de vrijwilligers (zie hieronder).
2. **Eindpost**: stap 1 t/m 4 (Eindpost). Noteer de roepnaam, bijv. `PD3PAM-5`.
3. **Noodsteunpunt**: stap 1 t/m 4 (Noodsteunpunt). Zet op tabblad **Netwerk** de roepnaam
   van de eindpost bij de juiste discipline. Maak de kaart.
4. **Radio testen**: op beide Pi's tabblad Radio → *Testuitzending*. Kijk op de andere Pi bij
   *Gehoorde stations* (niveau rond 50). Stel zo nodig de schuifbalken bij.
5. **Beheerder**: jouw eigen telefoon aanmelden en goedkeuren als beheerder (stap 4).
6. **Vrijwilligers**: de telefoons aanmelden (stap 6) en goedkeuren.
7. **Testen**: stap 5.

Telefoons die eerder met een ander steunpunt werkten: app verwijderen (of *Instellingen →
Apps → Noodnet → Opslag → Gegevens wissen*) en opnieuw installeren. Dan krijgen ze een nieuw ID.

---

## Vooraf - RNodes flashen

Een RNode is een klein LoRa-bordje (bijv. LilyGO T-Beam, T3S3 of Heltec) met de RNode-firmware
erop. Een nieuw bordje flash je eenmalig. Dat geldt voor de RNodes van het steunpunt én voor die
van de vrijwilligers.

1. Open op een pc in **Chrome of Edge** de webflasher: **https://rmap.world/flasher/**
   (Firefox werkt alleen met een extra instelling).
2. Sluit het bordje aan met een USB-kabel die **data** doorgeeft (veel kabels kunnen alleen laden).
3. Kies je bordje in de galerij en de **juiste band**: **433** of **868 MHz**, gelijk aan het bordje
   en de antenne.
4. Kies als firmware de officiële **RNode Firmware** (van Mark Qvist), de nieuwste versie.
5. Nieuw bordje: eerst **Full erase**. Dan **Connect** → **Flash now**, en wacht tot het klaar is.

Stel daarna **niets** in bij de LoRa-parameters of de TNC-modus: Noodnet stelt de RNode zelf in
(steunpunt: tabblad Radio en Netwerk; telefoon: de aanmeldkaart). Een bordje dat al RNode-firmware
heeft, hoef je niet opnieuw te flashen.

De webflasher is een gemeenschapsproject (niet van Noodnet of Reticulum zelf). Liever zonder
website: op de Pi, met internet, kan het ook met `rnodeconf --autoinstall`.

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
   - gebruik liever de hostnaam dan een IP-adres: dan raakt ssh de Pi's niet door elkaar
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
| **Radio** | Geluidskaart van de set. *Besturing*: **CAT** als je set in de lijst staat (of tik *Zoek mijn set*), anders RTS/DTR met de PTT-poort. RNode-poort voor 433 en/of 868 (heb je er maar één: de andere op *Niet aangesloten*), zendvermogen. Opslaan. Dan **Testuitzending**: gaat de set op zenden? Zendniveau met de schuifbalk zo dat het packet-geluid schoon klinkt (begin bij 50%). |
| **Netwerk** | Gemeente, **2 m-frequentie**, disciplines met de roepnaam van hun eindpost, LoRa-instellingen. Gelijk houden op alle steunpunten van de gemeente: één persoon vult dit in en deelt het met **Exporteren**; de anderen **Inladen**. Opslaan. |
| **Kaart** | *Nieuwe kaart maken*. |
| **Status** | Alles groen? Geen rode melding? Vul *Dienstdoende operator* in. |

**Jezelf beheerder maken** (zonder iets over te typen):

1. Installeer de Noodnet-app: open **http://10.42.0.1** en tik op *Noodnet-app downloaden*.
   Op de telefoon heet de app **Noodnet** (een eerdere versie heette nog *Sideband*).
2. Koppel in de app je RNode (Bluetooth).
3. Open het M/ETHANE-scherm en tik op **Kaart van steunpunt scannen**. Scan de
   QR-code op het tabblad *Kaart* (op een tweede scherm, of afgedrukt).
4. Kies de band van je RNode en tik **Aanmelden**.
5. Tabblad **Status** → *Wachten op goedkeuring* → **Goedkeuren als beheerder**.

Daarna krijg jij de aanmeldingen van vrijwilligers en kun je vanaf je telefoon
`LIJST`, `JA <nr>`, `NEE <nr>` en `CODE <nieuw>` sturen. Alle opdrachten en een zakkaart staan in de korte
[handleiding voor de beheerder](BEHEERDER.md) (*Noodnet-beheerder.pdf*).

**Kaart afdrukken:** tabblad Kaart → *Kaart openen om af te drukken* (A5/A6,
lamineren). Ter plekke zonder printer: **QR-code groot tonen** en van je telefoonscherm laten scannen. Staat er IFAC op, dan is de kaart **VERTROUWELIJK**.

### Eindpost

| Tabblad | Wat doen |
|---|---|
| **Instellingen** | Naam van de post, roepnaam (= die van de installatie), **2 m-frequentie**, disciplines (of *Alle meldingen*), eventueel meelezen. Opslaan. Heb je het netwerkbestand van de gemeente: onderaan **Inladen** (neemt frequentie en disciplines over). |
| **Radio** | Geluidskaart van de set. *Besturing*: **CAT** als je set in de lijst staat (of *Zoek mijn set*), anders RTS/DTR met de PTT-poort. Opslaan. Dan **Testuitzending**: gaat de set op zenden? Zendniveau met de schuifbalk zo dat het packet-geluid schoon klinkt (begin bij 50%). |
| **Kaart** | Eenmalig, **met internet**: vul de gemeente in, kies gebied (bijv. 10 km) en detail (16), en klik **Kaart downloaden** (een paar minuten). Zie *Meldingen op de kaart* hieronder. |
| **Status** | Alles groen? Vul *Dienstdoende operator* in. |

Laat daarna de beheerder van elk steunpunt in de gemeente jouw roepnaam
toevoegen: tabblad **Netwerk** → bij de juiste discipline. Meerdere posten van
dezelfde dienst (bijv. een hoofdkazerne en een dependance) kan: zet beide
roepnamen bij die discipline, met een komma ertussen. Een M/ETHANE-melding wordt
dan herhaald tot **beide** posten hebben bevestigd.

Het **M/ETHANE-scherm** opent na het opstarten vanzelf op de monitor. Ook te
bekijken op een andere pc of telefoon via de hotspot: **http://10.42.0.1:1880/ui**.

### Meldingen op de kaart (tweede scherm)

Meldingen waarbij de vrijwilliger *Ik ben ter plaatse* aanvinkte, komen ook op een kaart: de
**nieuwste groot en rood** (met een rode cirkel en het label *NIEUW*), de **10 daarvoor in het
blauw**. Tik of klik op een marker voor de hele M/ETHANE. Bij een nieuwe melding schuift de kaart
er vanzelf naartoe. Meldingen zonder positie staan alleen op het M/ETHANE-scherm.

1. **Offline kaart downloaden** (eenmalig, met internet): beheerpagina → tabblad **Kaart** →
   gemeente, gebied en detail → **Kaart downloaden**. De kaart is de BRT-Achtergrondkaart van het
   Kadaster (PDOK, open data, CC BY 4.0). Daarna werkt hij zonder internet. Opnieuw downloaden
   (ander gebied) mag; de oude kaart blijft werken tot de nieuwe binnen is.
2. **Kaart openen**: **http://localhost:1880/worldmap/** op de Pi zelf, of
   **http://10.42.0.1:1880/worldmap/** op een laptop of tablet via de hotspot.
3. **Tweede monitor** (Pi 4 of 5 hebben twee HDMI-poorten): open op het bureaublad Chromium met
   het kaartadres, sleep het venster naar het tweede scherm en druk **F11** (schermvullend).

De kaart leegmaken kan in de Node-RED-editor: tabblad *Noodnet kaart* → knop **Wis kaart**.

## Stap 5 - Testen

- [ ] Status: alle diensten groen, hotspot aan
- [ ] Radio → *Testuitzending*: de set gaat op zenden, op een tweede ontvanger hoor je packet-geluid
- [ ] Steunpunt: elke telefoon meldt zich aan met de kaart en wordt goedgekeurd (stap 6)
- [ ] Steunpunt: `LIJST` vanaf de beheertelefoon geeft antwoord
- [ ] Een M/ETHANE-melding komt aan op de eindpost (scherm + logboek)
- [ ] Het steunpunt toont *bevestigd* (ACK) van de eindpost in het log
- [ ] Na een herstart werkt alles weer vanzelf

## Stap 6 - Telefoons van vrijwilligers

Geef vrijwilligers de **handleiding voor vrijwilligers** mee ([VRIJWILLIGER.md](VRIJWILLIGER.md),
of afgedrukt: *Noodnet-vrijwilliger.pdf*, met zakkaart).

Per telefoon, in de buurt van het steunpunt:

1. Verbind met de wifi *Noodnet-&lt;roepnaam van het steunpunt&gt;* (wachtwoord van de hotspot).
2. Open **http://10.42.0.1** en tik op *Noodnet-app downloaden*. Android vraagt toestemming
   om apps uit deze bron te installeren: toestaan, dan installeren. Op de telefoon heet de app **Noodnet**.
3. Open de app en koppel de RNode van de vrijwilliger (Bluetooth).
4. Open het M/ETHANE-scherm → **Kaart van steunpunt scannen** → scan de kaart. Geen gedrukte kaart?
   Beheerder: beheerpagina → tabblad **Kaart** → **QR-code groot tonen**, en laat scannen van je scherm.
   Alleen tonen aan wie zich mag aanmelden: de QR-code bevat de aanmeldcode.
5. Kies de band van de RNode (433 of 868) en tik **Aanmelden**.
6. De beheerder krijgt de aanmelding op zijn telefoon met een nummer: antwoord `JA <nr>`.
   Of op de beheerpagina: tabblad **Status** → *Wachten op goedkeuring* → **Goedkeuren**.
7. De telefoon krijgt bericht dat hij is goedgekeurd. Daarna kan hij melden.

Na het aanmelden mag de telefoon van de hotspot af: melden gaat via de RNode.

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

## 2 m-frequentie en CAT

**Frequentie per gemeente.** Elke gemeente kiest een eigen 2 m-frequentie, in overleg met de
buurgemeenten, zodat jullie elkaar niet storen (binnen het segment voor digitale modes van het
bandplan; niet 144,800, dat is APRS). Die staat op het tabblad **Netwerk** van elk steunpunt en
op **Instellingen** van elke eindpost.

**Netwerkbestand (supervisor).** Eén persoon, de supervisor, stelt in overleg met de gemeente het
tabblad Netwerk in (frequentie, disciplines en eindposten, LoRa) en tikt **Exporteren**. Dat bestand
gaat naar iedereen die meedoet:
- **rondsturen** (mail, app, USB-stick) → op elk steunpunt (tabblad Netwerk) en elke eindpost
  (tabblad Instellingen) **Inladen**; of
- **op GitHub of de website zetten** → daar **Ophalen** met de link. De Pi onthoudt de link: vóór
  een oefening is één tik op **Opnieuw ophalen** genoeg (de Pi heeft dan wel internet nodig).

Elk bestand heeft een **versie** (datum, tijd, door wie). Op het tabblad **Status** van elke Pi staat
welke versie hij heeft: controleer bij het begin van een oefening of iedereen dezelfde heeft.

Staat er **IFAC** in, dan zijn er twee knoppen: **Exporteren zonder IFAC** (mag openbaar, bijv. op
GitHub; wie hem inlaadt houdt zijn eigen IFAC) en **Exporteren compleet** (vertrouwelijk). Geef het
IFAC-wachtwoord alleen via een vertrouwelijk kanaal door.

**CAT (hamlib).** Staat je set in de lijst op het tabblad Radio, kies dan *CAT*. De Pi:
- zet de set op de frequentie van de gemeente, in de **datamode** (FM-D / PKT), zodat het geluid
  van USB komt;
- schakelt de zender via CAT (geen RTS/DTR of menu *USB SEND* nodig);
- zet desgewenst het zendvermogen, in watt (blijf binnen je vergunning);
- zet de set **terug** als iemand eraan draait (binnen een minuut; nooit tijdens het zenden).
Weet je model, poort of snelheid niet: **Zoek mijn set**.

Instellingen in de set voor CAT (getest met de IC-9700):

| IC-9700-menu | Instelling |
|---|---|
| SET > Connectors > USB SEND | **OFF** (anders kan de set gaan zenden zodra de Pi de poort opent) |
| SET > Connectors > MOD Input > DATA MOD | **USB** |
| SET > Connectors > CI-V > CI-V Address | standaard (A2h) |
| SET > Connectors > CI-V > CI-V USB Port | **Unlink from [REMOTE]** |
| SET > Connectors > CI-V > CI-V USB Baud Rate | Auto of 115200 |
| Band | 2 m op de **MAIN**-band |

Yaesu FT-817/818 met SCU-17: CAT gaat via **poort A** (Zoek mijn set vindt die); poort B (PTT) is
dan niet meer nodig. Het vermogen kan de FT-817/818 niet via CAT instellen of doorgeven: stel het
op de set zelf in en laat het veld *Zendvermogen* leeg.

**Vóór Zoek mijn set:** zet PTT via RTS/DTR in de set uit (IC-9700: *USB SEND* = OFF) en zorg voor
een goede antenne of dummyload. Opent de Pi een poort waarop PTT via RTS staat, dan kan de set kort
gaan zenden.

Staat je set er niet bij, gebruik dan RTS/DTR (bijv. met een Digirig) en zet de frequentie met de
hand; de Pi toont welke.

## Dienstdoende operator en aflossen

Het station zendt altijd onder de roepnaam die bij de installatie is ingesteld; die verander je
niet. Wie op dat moment verantwoordelijk is, leg je vast op tabblad **Status** →
*Dienstdoende operator*: kies jezelf in de keuzelijst en tik **Dienst overnemen**. De eerste keer:
*Nieuwe operator toevoegen* (roepnaam en naam); daarna sta je in de keuzelijst.
Doe dit bij het begin van je dienst en bij elke aflossing. Elke wissel komt met tijd in het log
(steunpunt) en in het logboek (eindpost); bij elke melding in het logboek staat wie dienst had.

## Uitzetten

Haal nooit zomaar de stroom eraf: de SD-kaart kan dan beschadigen. Beheerpagina → tabblad
**Status** → onderaan **Pi uitschakelen**. Wacht tot het groene lampje op de Pi niet meer
knippert (± 20 seconden); daarna mag de stroom eraf.

Wil je ook beschermd zijn tegen een onverwachte stroomstoring (accu leeg, kabel los), gebruik
dan een **UPS-HAT** op de Pi.

## Problemen oplossen

| Probleem | Oplossing |
|---|---|
| Telefoon ziet wifi *Noodnet-…* niet | Pi herstarten. Wacht 2 minuten na het aanzetten. |
| Telefoon ziet de wifi wel, maar verbinden mislukt | Wachtwoord goed? Staat in `~/noodnet/hotspot.json`. Controle: `~/noodnet/hotspot.sh status` en `journalctl -u noodnet-ap -n 30`. |
| ssh: *REMOTE HOST IDENTIFICATION HAS CHANGED* | Normaal na een nieuwe SD-kaart of bij een andere Pi op hetzelfde adres (via de hotspot is dat altijd 10.42.0.1). Op je pc: `ssh-keygen -R 10.42.0.1` (of het adres/de hostnaam die je gebruikt), dan opnieuw inloggen en **yes** typen. |
| Kaart is grijs of leeg | Is de offline kaart gedownload (tabblad **Kaart**)? Buiten het gedownloade gebied is de kaart grijs: download een groter gebied. Geen markers: alleen meldingen met *Ik ben ter plaatse* hebben een positie. |
| Beheerpagina opent niet | Op de hotspot? Adres **http://10.42.0.1:8080** (een naam werkt niet, alleen het adres). Mobiele data even uit. Net opgestart: wacht 2 minuten; de Pi controleert de hotspot elke minuut en zet hem zo nodig zelf opnieuw goed. Lukt het daarna nog niet: stroom eraf en erop, en bekijk na het inloggen wat er misging met `journalctl -b -1 -t noodnet -u noodnet-ap -u noodnet-dhcp`. |
| Direwolf rood | Tabblad Radio: juiste geluidskaart? Set aan en via USB aangesloten? |
| Direwolf rood nadat een USB-stekker (bijv. RNode) eruit of erin ging | Vooral op een Pi 3: de USB loopt vast en de geluidskaart van de set geeft fouten. USB-kabel van de set even uit en in, of de Pi herstarten. Liever een Pi 4/5; RNodes niet in- of uitpluggen terwijl het steunpunt in gebruik is. |
| Set zendt niet | Tabblad Radio → *Testuitzending*. Met CAT: staat *Set (CAT)* op Radio/Status groen? Zonder CAT: PTT-poort en RTS (IC-9700: menu *USB SEND* op RTS; SCU-17: poort B). |
| *Set (CAT): geen verbinding* | Set aan? USB-kabel? Juiste CAT-poort en snelheid? Tik *Zoek mijn set*. Icom: CI-V-adres op standaard, *CI-V USB Port* niet gekoppeld aan REMOTE. |
| Set springt terug naar een andere frequentie | Dat is de bewaker: de Pi houdt de set op de frequentie van de gemeente (tabblad Netwerk/Instellingen). Andere frequentie nodig? Pas die daar aan. |
| Rode melding *Kaart en radio komen niet overeen* | Tabblad Netwerk nog een keer opslaan (de RNodes worden dan gelijkgezet). Nieuwe kaart maken en opnieuw scannen. |
| RNode niet gevonden (Radio: geen poort, Status rood) | Andere USB-kabel (één die data doorgeeft). Nog steeds niet: flash de RNode opnieuw (zie *Vooraf - RNodes flashen*), let op de juiste band. |
| Vrijwilligers komen niet door | Status: staan ze bij *Onbekende telefoons*? Laten aanmelden met de kaart. `rnstatus`: IFAC-overtredingen? → IFAC op kaart en Pi gelijk. |
| Steunpunt blijft herhalen | De roepnaam van de eindpost op het tabblad Netwerk klopt niet, of de eindpost staat uit. |
| Packets komen slecht door | Tabblad Radio → *Gehoorde stations*: ideaal rond 50. Eén station afwijkend: dat station past zijn zendniveau aan. Te laag/hoog: schuifbalk Ontvangstniveau. Bij de ander niets: Zendniveau iets omhoog; vervormd: omlaag. |
| Kaart kwijt of in verkeerde handen | Nieuwe aanmeldcode: vanaf de beheertelefoon `CODE <nieuwe code>` (of tabblad Steunpunt). Daarna tabblad **Kaart** → *Nieuwe kaart maken*. Ter plekke geen printer: **QR-code groot tonen** op je telefoon en laten scannen. Oude kaarten vernietigen. Aangemelde telefoons merken niets; een onbekende telefoon die al was aangemeld haal je eraf met `AF <naam>`. |
| Tijd in het logboek klopt niet | Open de beheerpagina op je telefoon: de Pi neemt de tijd over. |
| Status: *Nog niet bevestigd* | Die eindpost staat uit, is buiten bereik, of de roepnaam klopt niet. Het steunpunt blijft M/ETHANE herhalen tot elke genoemde eindpost bevestigt. Bestaat die post niet (tikfout) of komt hij niet meer: eerst de roepnaam op tabblad Netwerk verbeteren, dan op Status **Niet meer wachten op …**. |

## Veiligheid

- `gateway.id` (de sleutel van het steunpunt) nooit delen of kopiëren.
- De **QR-code** (kaart of *QR-code groot tonen*) bevat de aanmeldcode, en het IFAC-wachtwoord als dat aan staat. Laat hem alleen zien aan vrijwilligers die zich mogen aanmelden. Laat je telefoon met de QR-code niet onbeheerd liggen. Kaart kwijt: zie *Problemen oplossen*.
- Hotspot- en beheerwachtwoord alleen voor de zendamateur(s).
- Poort 8080 nooit naar internet openzetten.
- Het logboek van een eindpost bevat namen en locaties (AVG): de hulpdienst is eigenaar.

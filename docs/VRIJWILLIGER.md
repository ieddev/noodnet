# Noodnet - handleiding voor vrijwilligers

Als vrijwilliger ben je de ogen en oren van de hulpdiensten in je wijk. Bij een calamiteit meld je
wat je ziet, met je eigen **Android-telefoon** en een kleine LoRa-zender: de **RNode**. Daarvoor is
geen mobiel netwerk en geen internet nodig. Je melding gaat naar het dichtstbijzijnde
**Noodsteunpunt**, en de zendamateur daar zorgt dat hij bij de hulpdienst aankomt.

Je hebt geen zendlicentie en geen technische kennis nodig. Reken voor de eerste keer op een half
uur.

**Afdrukken?** Deze handleiding staat ook als PDF in [Noodnet-vrijwilliger.pdf](Noodnet-vrijwilliger.pdf),
met achterin een zakkaart.

| Wat heb je nodig | Toelichting |
|---|---|
| Android-telefoon | Met Bluetooth en GPS. Een iPhone werkt niet. |
| RNode | Een klein LoRa-bordje met antenne en eigen accu, bijv. een LilyGO T-Beam. Vaak krijg je die van de beheerder. |
| USB-kabel en powerbank | Om de RNode en je telefoon op te laden. |
| Aanmeldkaart | De kaart van het steunpunt met een QR-code. Geen kaart? De beheerder kan de QR-code op zijn scherm laten zien. |

**Eigen veiligheid gaat altijd voor.** Noodnet is een aanvulling op 112, geen vervanging. Werkt 112
nog, bel dan 112.

---

## Stap 1 - De RNode klaarmaken

**Heb je de RNode van de beheerder gekregen? Dan is dit al gedaan: ga door naar stap 2.**

Een nieuwe RNode moet je eenmalig *flashen*: de RNode-software erop zetten.

1. Schroef **altijd eerst de antenne** op de RNode, voordat je hem aanzet.
2. Open op een pc in **Chrome of Edge** de webflasher: **https://rmap.world/flasher/**
3. Sluit de RNode aan met een USB-kabel die **data** doorgeeft (veel kabels kunnen alleen laden).
4. Kies je bordje in de galerij en de **juiste band**: **433** of **868 MHz**, gelijk aan het bordje
   en de antenne.
5. Kies als software de officiële **RNode Firmware** (van Mark Qvist), de nieuwste versie.
6. Nieuw bordje: eerst **Full erase**. Dan **Connect** → **Flash now**, en wacht tot het klaar is.
7. Zet in de webflasher **Bluetooth aan**.

Stel verder **niets** in (geen frequentie, geen TNC-modus): dat doet de app straks zelf, met de kaart
van het steunpunt.

## Stap 2 - De app installeren

De app installeer je bij het steunpunt, via de wifi van het steunpunt:

1. Verbind je telefoon met de wifi **Noodnet-…** van het steunpunt. Het wachtwoord krijg je van de
   beheerder. Meldt de telefoon "geen internet": kies **Verbonden blijven**.
2. Open in de browser **http://10.42.0.1** en tik op **Noodnet-app downloaden**.
3. Android vraagt of je apps uit deze bron mag installeren: **toestaan**, dan **installeren**.
4. Op je telefoon heet de app **Noodnet**. (Een eerdere versie heette nog *Sideband*; dat is dezelfde app.)
5. Open de app. Vraagt hij om toestemming voor Bluetooth, locatie of meldingen: **toestaan**.

Vooraf thuis installeren kan ook: download de nieuwste APK van
**https://github.com/ieddev/noodnet/releases**.

## Stap 3 - De RNode koppelen via Bluetooth

1. Antenne erop, en zet de RNode aan.
2. Zet de RNode in **koppelmodus**: houd de knop op de RNode **langer dan 5 seconden** ingedrukt
   en laat dan los. Op het schermpje verschijnt de koppelmodus met een **code**.
3. In de app: menu (☰) → **Hardware** → **RNode** → **Pair New Device**. Vindt de app niets: ga naar
   de **Bluetooth-instellingen** van je telefoon → nieuw apparaat koppelen → kies **RNode …** en typ
   de code van het schermpje.
4. Terug in de app, bij **Hardware** → **RNode**: zet **Connect using Bluetooth** aan.
   Heb je een nieuwer bordje met een ESP32-S3- of nRF-chip (bijv. LilyGO T3S3, T-Beam Supreme,
   Heltec V3/V4, RAK)? Zet dan ook **Device requires BLE** aan. Bij een T-Beam v1.2 niet.

Vul bij de RNode verder niets in: de frequentie en de andere instellingen komen van de kaart.

## Stap 4 - Aanmelden bij het steunpunt

Dit doe je één keer per steunpunt, in de buurt van het steunpunt.

1. Open de app. Tik op de grote rode knop **NOODMELDING M/ETHANE**
   (of: menu ☰ → **Noodmelding**).
2. Tik op **KAART VAN STEUNPUNT SCANNEN** → **Kaart scannen**, en scan de QR-code van de kaart
   (of van het scherm van de beheerder). De eerste keer moet de scanner van Google nog worden
   gedownload: lukt het niet meteen, probeer het dan na een minuut opnieuw.
3. De app laat zien bij welk steunpunt je je aanmeldt. Werkt het steunpunt op twee banden, dan vraagt
   de app: *Welke RNode heeft u gekregen?* Kies **433** of **868 MHz**, gelijk aan je RNode.
4. Vul **je naam** in en tik op **AANMELDEN**. De app stelt de RNode in en zoekt het steunpunt.
5. Je ziet *Aanmelding verstuurd*, en bovenaan het meldscherm *Wacht op goedkeuring door de
   zendamateur*. De beheerder van het steunpunt keurt je aanmelding goed.
6. Is dat gebeurd, dan staat er bovenaan het meldscherm **Aangemeld bij …**. Je kunt nu melden.

Na het aanmelden mag je van de wifi af: melden gaat via de RNode.

De QR-code bevat de aanmeldcode van het steunpunt. Laat hem niet aan anderen zien, en maak er geen foto
van om door te sturen.

## Stap 5 - Een melding doen (M/ETHANE)

1. Tik op **NOODMELDING M/ETHANE**.
2. **Kies wie je wilt waarschuwen**: tik op een hulpdienst, of op **ALLE DIENSTEN**. Meer dan één mag.
3. **Vul in wat je weet.** Leeg laten mag; liever een korte melding dan geen melding.

| Veld | Wat vul je in |
|---|---|
| **M** - Groot incident? | Ja/nee, en in één zin waarom |
| **E** - Exacte locatie | Adres, kruispunt of herkenningspunt |
| **T** - Soort incident | Brand, ongeval, instorting, ... |
| **H** - Gevaren | Gas, vuur, verkeer, instortingsgevaar, ... |
| **A** - Bereikbaarheid | Hoe kom je er, welke route is vrij |
| **N** - Aantal slachtoffers | Aantal en hoe ernstig |
| **E** - Hulpdiensten | Wie is er al, wie is er nog nodig |

4. **Ben je zelf bij het incident?** Vink dan **Ik ben ter plaatse: stuur mijn positie mee** aan. De
   hulpdienst ziet dan precies waar je bent. Meld je iets wat je van een afstand ziet of hoort, laat het
   vinkje dan uit: anders gaat de hulpdienst naar de verkeerde plek. Het vinkje staat altijd uit als je
   het meldscherm opent, en gaat na elke melding weer uit.
5. Tik op **VERSTUUR MELDING** en bevestig.
6. In het gesprek met het steunpunt zie je de status. Staat hij op **afgeleverd** (*Delivered*), dan
   heeft het steunpunt je melding. Het steunpunt geeft hem door aan de hulpdienst en herhaalt hem tot
   de hulpdienst hem heeft bevestigd. Jij hoeft niets meer te doen.

Krijg je het antwoord **NIET doorgegeven**? Dan ben je (nog) niet aangemeld bij dit steunpunt, of je
bent afgemeld. Kies een andere weg om je melding te doen, en meld het bij de beheerder.

## Onderweg

- Laat de app aan staan. Je telefoon laat zich af en toe kort horen bij het steunpunt, met je positie
  en de accustand van je RNode en telefoon. Zo weet de beheerder wie er actief is.
- Laad je telefoon en RNode op tijd op en neem een powerbank mee. Raakt een accu bijna leeg, dan krijgt
  de beheerder een waarschuwing.
- Slecht bereik? Ga hoger staan of naar buiten, en houd de antenne rechtop. Het bereik is enkele
  kilometers, minder tussen hoge gebouwen.
- Stop je ermee, of ga je naar huis? Laat het de beheerder weten.

## Problemen oplossen

| Probleem | Oplossing |
|---|---|
| App installeren lukt niet | Sta installeren uit deze bron toe (Android vraagt dat). Of download de app vooraf van GitHub. |
| Wifi van het steunpunt verbreekt steeds | Kies **Verbonden blijven** als Android "geen internet" meldt. Zet mobiele data even uit. |
| RNode niet te vinden bij koppelen | RNode aan en in koppelmodus (knop langer dan 5 seconden)? Probeer via de Bluetooth-instellingen van de telefoon. Nieuwer bordje: **Device requires BLE** aan. |
| Scannen lukt niet | Wacht een minuut (de scanner wordt gedownload) en probeer opnieuw. Of scan met een andere app, kopieer de tekst en tik op **Uit klembord**. |
| *Steunpunt niet bereikbaar* | Is de RNode aan en gekoppeld? Ben je binnen bereik? Probeer het dichter bij het steunpunt: **Opnieuw aanmelden**. |
| Er blijft *Wacht op goedkeuring* staan | De beheerder heeft je nog niet goedgekeurd. Vraag het hem. |
| Melding blijft hangen, niet *afgeleverd* | RNode aan, accu vol, binnen bereik? Ga hoger staan of dichter naar het steunpunt. De app probeert het opnieuw. |
| Antwoord *NIET doorgegeven* | Je bent niet (meer) aangemeld. Meld je opnieuw aan met de kaart, of neem contact op met de beheerder. |

## Privacy

Het steunpunt en de hulpdienst zien je naam, je meldingen en (als je die meestuurt) je positie. Die
staan in het logboek van de hulpdienst. Berichten tussen je telefoon en het steunpunt zijn versleuteld.
Meer hierover: de pagina *Disclaimer en privacy* op [noodnet.ied.nl](http://noodnet.ied.nl).

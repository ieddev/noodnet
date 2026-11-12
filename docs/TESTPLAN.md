# Noodnet - testplan aanmelden en melden

Volg de scenario's in deze volgorde. Vink af wat werkt en noteer wat anders gaat dan
verwacht (wat je zag, op welke telefoon, hoe laat). Telefoons: **B** = beheerder,
**V1**, **V2** = vrijwilligers.

De kolom **Waar** zegt welk apparaat je erbij nodig hebt, in de volgorde waarin het gebeurt:
**App** = de Noodnet-app op telefoon B, V1 of V2 · **SP** = steunpunt (beheerpagina) ·
**EP** = eindpost (beheerpagina, M/ETHANE-scherm of kaart). Een pijl (→) betekent: hier doe je
iets, daar zie je het resultaat.

**Afdrukken?** Dit testplan staat ook als afvinklijst (A4 liggend, met een kolom voor opmerkingen) in
[Noodnet-testplan.pdf](Noodnet-testplan.pdf).

Handig tijdens het testen: beheerpagina tabblad **Status** (log onderaan) open op een pc
via de hotspot.

## A. Aanmelden

| # | Waar | Scenario | Hoe | Verwacht | OK |
|---|---|---|---|---|---|
| A1 | App B, SP | Beheerder aanmelden | B: kaart scannen, *Aanmelden*. Beheerpagina → Status → **Goedkeuren als beheerder** | B krijgt bericht "Aangemeld … Je bent ook beheerder" | ☐ |
| A2 | App V1 → App B | Vrijwilliger, goedkeuren vanaf telefoon | V1: kaart scannen, *Aanmelden* | V1: "Aanmelding ontvangen (nr X)". B: "Aanmelding #X … Antwoord JA X of NEE X". B stuurt `JA X` → V1: "Aangemeld" | ☐ |
| A3 | App V2, SP | Goedkeuren via beheerpagina | V2 aanmelden; beheerpagina → Status → **Goedkeuren** | V2: "Aangemeld". B krijgt bericht "(via beheerpagina)" | ☐ |
| A4 | App V2 → App B | Twee keer op Aanmelden tikken | V2 (nog niet goedgekeurd) tikt twee keer | Zelfde nummer; B krijgt maar **één** bericht | ☐ |
| A5 | App V1 | Al aangemeld, nog eens aanmelden | V1 meldt opnieuw aan | V1: "U bent al aangemeld" | ☐ |
| A6 | App B → App V2 | Afwijzen | Nieuwe aanmelding van V2 (na AF, zie A9); B stuurt `NEE X` | V2: "niet goedgekeurd". Daarna opnieuw aanmelden kan | ☐ |
| A7 | App B, App V2 | Verkeerde aanmeldcode | B stuurt `CODE TEST123`; V2 meldt aan met de **oude** kaart | V2: "onjuiste aanmeldcode"; B krijgt niets. Daarna terugzetten: `CODE <oude code>` | ☐ |
| A8 | App → SP | Onbekende telefoon meldt | Telefoon die **niet** is aangemeld stuurt een M/ETHANE-melding | Wordt **niet** doorgezet; telefoon krijgt "NIET doorgegeven"; staat op beheerpagina bij *Onbekende telefoons* | ☐ |
| A9 | App B (of SP) → App V2 | Afmelden | B stuurt `AF <naam van V2>` (of beheerpagina → Vrijwilligers → Afmelden) | B: "Afgemeld: …". V2: "U bent afgemeld" | ☐ |
| A9b | App V2 | Afgemelde telefoon meldt toch | V2 stuurt een M/ETHANE-melding en een gewoon bericht | Niet doorgezet. V2 krijgt terug: "… is NIET doorgegeven … niet (meer) aangemeld" | ☐ |
| A10 | App V2, SP, App B | Aanmelding blijft na herstart | V2 meldt aan, **niet** goedkeuren; steunpunt herstarten (`sudo reboot`); daarna `JA X` | Werkt; nummer is bewaard | ☐ |

## B. Beheeropdrachten (vanaf telefoon B)

| # | Waar | Opdracht | Verwacht | OK |
|---|---|---|---|---|
| B1 | App B | `HELP` | Lijst met opdrachten | ☐ |
| B2 | App B | `WACHT` | Open aanmeldingen, of "Geen open aanmeldingen" | ☐ |
| B3 | App B | `LIJST` | Aangemelde telefoons, laatst gehoord, accu | ☐ |
| B4 | App B | `CODE` | Huidige aanmeldcode | ☐ |
| B4a | App B, SP | `CODE <nieuwe code>` | B: "Nieuwe aanmeldcode: …". Beheerpagina (Status en Steunpunt) toont de nieuwe code. Aangemelde telefoons blijven aangemeld; nieuwe aanmelding met de oude kaart: "onjuiste aanmeldcode". Tabblad Kaart → nieuwe kaart maken: staat de nieuwe code op? Daarna eventueel terugzetten | ☐ |
| B5 | App B | `JA 999` (bestaat niet) | "bestaat niet (meer)" | ☐ |
| B6 | App V1 → EP | Opdracht vanaf V1 (geen beheerder), bijv. `LIJST` | Geen beheerantwoord; het gaat als gewoon bericht naar de eindpost | ☐ |
| B7 | App B → App V1, V2 | `ALLEN Testbericht aan allen` (V1 en V2 aan, B zelf ook aangemeld) | B: "Verstuurd naar 2 vrijwilligers…". V1 en V2 krijgen "<steunpunt> aan alle vrijwilligers: Testbericht aan allen" (B zelf niet). Het gaat **niet** over 2 m | ☐ |
| B7a | App B | Daarna `LIJST` | Onderaan: "Bericht aan allen (hh:mm): ontvangen door 2 van 2." | ☐ |
| B7b | App B | V2 uit, opnieuw `ALLEN …`, na een paar minuten `LIJST` | "ontvangen door 1 van 2. Nog niet: V2" | ☐ |
| B7c | SP → App | Beheerpagina → Vrijwilligers → *Bericht aan alle vrijwilligers* | Groene melding; V1 en V2 (en B) krijgen het; onder het veld staat wie het heeft ontvangen (pagina verversen) | ☐ |
| B7d | App B | `ALLEN` zonder tekst, en een tekst van meer dan 300 tekens | Uitleg terug, er wordt niets verstuurd | ☐ |
| B8 | App B → App V1 | `AAN <voornaam V1> Testbericht` | Alleen V1 krijgt "Bericht van <steunpunt>: Testbericht"; B krijgt *verstuurd* en daarna *Afgeleverd bij …* | ☐ |
| B8a | App B | V2 uit; `AAN <naam V2> hallo` | B krijgt na een tijd *Niet aangekomen bij …* | ☐ |
| B8b | App B | Twee vrijwilligers met dezelfde voornaam; `AAN <voornaam> hallo` | B krijgt *Welke bedoel je: …*; er wordt niets verstuurd | ☐ |
| B8c | SP → App V1 | Beheerpagina: Posities → tik op V1 → *Bericht sturen* | Vrijwilligers opent met V1 bij *Aan*; versturen; V1 krijgt het; onder *Berichten aan één vrijwilliger* staat *afgeleverd* | ☐ |

## C. Melden

| # | Waar | Scenario | Verwacht | OK |
|---|---|---|---|---|
| C1 | App V1 → EP, SP | V1 stuurt M/ETHANE via **433** | Eindpost: scherm + logboek. Steunpunt log: bevestigd (ACK) | ☐ |
| C2 | App V2 → EP, SP | V2 stuurt M/ETHANE via **868** | Idem | ☐ |
| C3 | App → EP | Groot incident: bij **M** "Ja, …" | Kop **rood** met "– GROOT INCIDENT"; knippert (zoals elke nieuwe melding) | ☐ |
| C3b | App → EP | Geen groot incident: bij **M** "Nee, …" | Kop **oranje**; knippert ook | ☐ |
| C4 | EP uit, App V1 → SP | Eindpost uit (of Direwolf stoppen), V1 meldt | Steunpunt blijft herhalen; na 5 min op Status: *Nog niet bevestigd* | ☐ |
| C5 | EP → SP | Eindpost weer aan | Melding komt alsnog aan, ACK, waarschuwing weg | ☐ |
| C6 | SP, App V1 → EP | Twee posten bij één discipline. Tabblad **Netwerk**: zet bij *Gemeentehuis* `PD3PAM-5, PD3PAM-9` (PD3PAM-9 bestaat niet) en sla op. V1 meldt aan *Gemeentehuis* | PD3PAM-5 bevestigt; steunpunt blijft herhalen voor PD3PAM-9. Na 5 min op Status: *Nog niet bevestigd* door PD3PAM-9, met knop **Niet meer wachten op PD3PAM-9** → melding uit de wachtrij. Daarna PD3PAM-9 weer weghalen op tabblad Netwerk | ☐ |
| C7 | App → EP | Melding met lange tekst (veel slachtoffers/locatie) | Komt compleet aan (meerdere delen samengevoegd) | ☐ |
| C8 | App → EP | Melding met *Ik ben ter plaatse: stuur mijn positie mee* aangevinkt | Bij *E - Exacte locatie* staat onder de tekst **Positie melder (ter plaatse): 52.xxxxx, 6.xxxxx (± .. m)**; in de lijst *Melder ter plaatse* | ☐ |
| C8a | App → EP | Na C8 het meldscherm opnieuw openen; en een melding zonder het vinkje | Vinkje staat weer **uit**. Melding zonder vinkje: geen positie op het scherm | ☐ |
| C9 | App (2 SP) → EP | (Met 2 steunpunten) V van SP1 en V van SP2 melden tegelijk aan dezelfde eindpost | Beide komen aan, eventueel één tot 1 min later; geen dubbele regels op het scherm | ☐ |
| C10 | App | Typen in de app: bij **E** "Holterweg thv 12", een paar letters weghalen en verbeteren, dan **T** en **H** aantikken en invullen | T en H bevatten alleen wat je daar zelf typt (niets uit E). Ook bij *Uw naam* bij het aanmelden | ☐ |
| C11 | App | App-naam en versie | Op de telefoon heet de app **Noodnet**; nieuwe APK installeert over de oude heen, aanmelding blijft | ☐ |

## D. Gehoord en uit beeld

| # | Waar | Scenario | Verwacht | OK |
|---|---|---|---|---|
| D1 | App V1 → App B | V1 uitzetten of RNode loskoppelen | Na de ingestelde tijd (*uit beeld na*, tabblad Steunpunt): B krijgt "niet meer gehoord sinds …"; `LIJST` toont het | ☐ |
| D2 | App B | V1 weer aan | B krijgt "weer gehoord (na … stilte)" | ☐ |
| D3 | App B | Accu van een RNode laag (als je dat kunt nabootsen) | Waarschuwing aan B | ☐ |
| D4 | SP | Met internet: steunpunt → tabblad **Posities** → gemeente, 10 km, detail 16 → **Kaart downloaden** | *Kaart gedownload* met aantal tegels | ☐ |
| D5 | SP | Zonder internet: tabblad **Posities** | Kaart van de gemeente; elke vrijwilliger met positie als stip met naam: groen actief, oranje accu laag, rood uit beeld. Tik: laatst gehoord, accu, coördinaten | ☐ |
| D6 | SP | Tabblad **Vrijwilligers** → *op de kaart* bij V1 | Posities opent ingezoomd op V1 met zijn gegevens | ☐ |
| D7 | SP | Posities → *Steunpunt op de kaart aanwijzen* → op een plek tikken → bevestigen | *Steunpunt geplaatst op …*; blauw vierkant met naam en roepnaam; dezelfde coördinaten staan op tabblad **Steunpunt** | ☐ |

## E. Storingen

| # | Waar | Scenario | Verwacht | OK |
|---|---|---|---|---|
| E1b | EP | Eindpost herstarten (`sudo reboot`) | M/ETHANE-scherm toont na het opstarten de laatste melding én de lijst met eerdere meldingen | ☐ |
| E1 | SP | Steunpunt herstarten | Na ± 2 min alles groen, hotspot aan, aanmeldingen bewaard | ☐ |
| E2 | SP | Een RNode losmaken en terugzetten | Status toont het; na terugzetten werkt de band weer (zo nodig `rnsd` herstarten op Status) | ☐ |
| E2b | SP | Pi uit, één RNode eruit, Pi aan | Na ± 2 min: rnsd en brug groen, steunpunt werkt op de overgebleven band | ☐ |
| E2c | SP | Stroom eraf (stekker eruit) terwijl het steunpunt draait, daarna weer aan | Brug start vanzelf; staat er een beschadigd bestand, dan in het log "Beschadigd ratchet-bestand opzij gezet" en daarna gewoon groen | ☐ |
| E3 | SP, EP | Pi zonder internet opstarten, beheerpagina op telefoon openen | Klok wordt gelijkgezet; tijd in het logboek klopt | ☐ |
| E4 | App | Telefoon buiten bereik van LoRa, melding versturen, dan terug in bereik | Noteer wat de app doet (blijft hij proberen? komt hij alsnog aan?) | ☐ |

## F. Eindpost

| # | Waar | Scenario | Verwacht | OK |
|---|---|---|---|---|
| F1 | EP | Eindpost herstarten (knop *Pi herstarten*) met monitor | M/ETHANE-scherm opent vanzelf schermvullend; scherm gaat niet op zwart na 10 min | ☐ |
| F2 | EP | Telefoon/laptop op de hotspot: **http://10.42.0.1:1880/ui** | Zelfde M/ETHANE-scherm als op de monitor | ☐ |
| F3 | EP | Tabblad **Logboek** | Meldingen van vandaag; downloaden als .txt en .csv; CSV opent in Excel/LibreOffice | ☐ |
| F4 | EP | Tabblad **Status** → *Steunpunten* | Het steunpunt staat erbij met laatst gehoord, aangemeld, wachtrij | ☐ |
| F5 | App → EP | Eindpost alleen voor één discipline (Instellingen: bijv. alleen *Gemeentehuis*). Melding aan een **andere** discipline | Eindpost toont niets en bevestigt niet; steunpunt wacht niet op deze post | ☐ |
| F6 | App → EP | Idem, maar *meelezen* aan | Melding komt in het logboek als *meelezen*; eindpost bevestigt **niet** | ☐ |
| F7 | App V1 → EP | Gewoon bericht (chat) van V1. Zonder @ gaat het naar de discipline(s) bij *Berichten aan* (tabblad Netwerk); met `@Gemeentehuis` in de tekst naar die discipline | Komt in het logboek van die eindpost; steunpunt krijgt ACK | ☐ |
| F8 | EP | Knop *Wis scherm en lijst* in Node-RED (editor) | Scherm en lijst leeg; logboek blijft compleet | ☐ |
| F9 | EP | Back-up downloaden (tabblad Back-up), daarna terugzetten | Instellingen en logboek terug | ☐ |
| F10 | EP ↔ SP | Radio → Testuitzending en niveaus | Set zendt; steunpunt toont de eindpost bij *Gehoorde stations*, niveau rond 50 (en andersom) | ☐ |
| F11 | EP | Met internet: tabblad **Posities** → gemeente, 10 km, detail 16 → **Kaart downloaden** | Voortgang loopt op; daarna *Kaart gedownload* met het aantal tegels en de datum | ☐ |
| F12 | EP | Zonder internet: **http://10.42.0.1:1880/worldmap/** (laptop/telefoon op de hotspot) | Kaart van de gemeente zichtbaar, ook ingezoomd tot straatniveau | ☐ |
| F13 | App → EP | V1 stuurt een M/ETHANE **met** *Ik ben ter plaatse* | Op de kaart: rode marker *NIEUW hh:mm · soort* met rode cirkel; kaart schuift ernaartoe; klik toont de hele M/ETHANE | ☐ |
| F14 | App → EP | Daarna een tweede melding met positie, en een derde **zonder** | Tweede wordt de rode; de eerste wordt blauw. De derde staat niet op de kaart (wel op het M/ETHANE-scherm) | ☐ |
| F15 | EP | Eindpost herstarten, kaart opnieuw openen | Dezelfde markers staan er weer | ☐ |
| F16 | EP | Kaart downloaden zonder internet | Melding *Geen verbinding met PDOK…*; de vorige kaart blijft werken | ☐ |

## G. Dienstdoende operator

| # | Waar | Scenario | Verwacht | OK |
|---|---|---|---|---|
| G1 | SP | Steunpunt: Status → *Nieuwe operator toevoegen* (roepnaam + naam) | Groene melding; log van de brug: "Dienstdoende operator: …" | ☐ |
| G2 | SP | Tweede operator toevoegen; daarna aflossen via de **keuzelijst** | Log: "… (neemt over van …)"; Status blijft compact (wissels ingeklapt onder *Wissels bekijken*) | ☐ |
| G2b | SP | *Operators beheren* → een operator uit de lijst halen (niet degene met dienst) | Verdwijnt uit de keuzelijst; wie dienst heeft kan niet verwijderd worden | ☐ |
| G3 | EP | Eindpost: operator invullen, daarna een M/ETHANE ontvangen | Logboek: regel OPERATOR; bij de melding "dienstdoende operator: …" | ☐ |
| G4 | SP, EP | Back-up maken en terugzetten | Operator en lijst met wissels terug | ☐ |

## H. Frequentie, CAT en netwerkbestand

| # | Waar | Scenario | Verwacht | OK |
|---|---|---|---|---|
| H1 | SP | Steunpunt, tabblad Netwerk: 2 m-frequentie kiezen in de keuzelijst (bijv. 144,950) | Opgeslagen; zonder CAT: melding "zet de set op …"; met CAT: set gaat mee | ☐ |
| H2 | SP, EP | Keuzelijst openen (steunpunt én eindpost → Instellingen) | Alleen 144,8125 t/m 144,9875 in stappen van 12,5 kHz; geen 144,800; huidige frequentie geselecteerd | ☐ |
| H3 | SP → EP | Netwerk → **Exporteren**, op de eindpost (Instellingen) **Inladen** | Eindpost neemt frequentie en zijn eigen disciplines over | ☐ |
| H4 | SP | Zelfde bestand op een tweede steunpunt **Inladen** | Tabblad Netwerk gelijk aan het eerste steunpunt | ☐ |
| H5 | SP, EP | Radio → **Zoek mijn set** (IC-9700 aan) | IC-9700 gevonden met poort en snelheid → **Gebruiken** | ☐ |
| H6 | SP, EP | Na *Gebruiken*: tabblad Radio | *Set (CAT)*: frequentie van de gemeente ✓, mode FM-D | ☐ |
| H7 | SP, EP | Testuitzending met CAT | Set gaat op zenden (PTT via CAT), packet-geluid schoon | ☐ |
| H8 | SP, EP | Aan de VFO draaien, 1 minuut wachten | Set staat weer op de gemeentefrequentie; bij *Laatste acties* "teruggezet" | ☐ |
| H9 | SP, EP | Zendvermogen 25 (watt) invullen en opslaan | Set op 25 W (op de set en bij *Vermogen*); opslaan zonder foutmelding | ☐ |
| H10 | SP, EP | Pi herstarten met CAT | Set na het opstarten vanzelf op frequentie en mode | ☐ |
| H12 | SP | Netwerk met IFAC: **Exporteren zonder IFAC**, op een ander steunpunt inladen | Geen IFAC in het bestand; het andere steunpunt houdt zijn eigen IFAC | ☐ |
| H13 | EP | Bestand op GitHub/website zetten; op de eindpost **Ophalen** met de link | Frequentie en disciplines overgenomen; daarna knop *Opnieuw ophalen* | ☐ |
| H14 | SP, EP | Status op alle Pi's | Overal dezelfde *Netwerkinstellingen: … versie … door …* | ☐ |
| H11 | SP | FT-818 + SCU-17 (steunpunt): Zoek mijn set | FT-818 gevonden; PTT en frequentie werken (of: terug naar RTS als het niet lukt) | ☐ |
| H15 | SP, EP | Zonder internet: Status → **Controleren op nieuwe versie** | Rode melding *Geen verbinding met GitHub…*; niets veranderd | ☐ |
| H16 | SP, EP | Met netwerkkabel: **Controleren op nieuwe versie** | *Er is een nieuwe versie* of *Je hebt al de nieuwste versie* | ☐ |
| H17 | SP | Steunpunt met een M/ETHANE in de wachtrij (eindpost uit): Controleren | Rode waarschuwing over de wachtrij boven de knop | ☐ |
| H18 | SP, EP | **Nu bijwerken**, pagina openhouden | Verslag loopt mee; pagina valt even weg en komt terug; *Klaar: bijgewerkt naar versie …*; rechtsboven de nieuwe versie | ☐ |
| H19 | SP | Na H18 (steunpunt): wachtrij uit H17 | Melding gaat na het bijwerken verder en wordt bevestigd zodra de eindpost aan is | ☐ |
| H20 | SP, EP | Zonder kabel: Status → **Hotspot tijdelijk uitschakelen** | Uitlegpagina met naam thuis-wifi en het adres (….local:8080 en/of vorige keer); wachtrij-waarschuwing als er een M/ETHANE wacht | ☐ |
| H21 | SP, EP | **Hotspot uit, thuis-wifi aan**; telefoon op thuis-wifi, adres openen | Status: groen *Thuis-wifi actief* met het adres van de Pi; **Controleren** en **Nu bijwerken** werken; daarna *De hotspot schakelt over 1 minuut weer in*; na ± 1 min is Noodnet-… er weer | ☐ |
| H21a | SP, EP | Hotspot uit, dan **Hotspot nu weer aanzetten** (zonder bij te werken) | Hotspot binnen een halve minuut terug | ☐ |
| H22 | SP, EP | Thuis-wifi uit (router uit), dan **Hotspot uit, thuis-wifi aan** | Binnen ± 2 min is de hotspot terug | ☐ |
| H23 | SP, EP | USB-tethering met de telefoon (telefoon op de wifi van de Pi), dan **Controleren op nieuwe versie** | Pi heeft internet; bijwerken werkt zoals H18 | ☐ |

## Notities

-

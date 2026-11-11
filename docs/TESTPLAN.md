# Noodnet - testplan aanmelden en melden

Volg de scenario's in deze volgorde. Vink af wat werkt en noteer wat anders gaat dan
verwacht (wat je zag, op welke telefoon, hoe laat). Telefoons: **B** = beheerder,
**V1**, **V2** = vrijwilligers.

**Afdrukken?** Dit testplan staat ook als afvinklijst (A4 liggend, met een kolom voor opmerkingen) in
[Noodnet-testplan.pdf](Noodnet-testplan.pdf).

Handig tijdens het testen: beheerpagina tabblad **Status** (log onderaan) open op een pc
via de hotspot.

## A. Aanmelden

| # | Scenario | Hoe | Verwacht | OK |
|---|---|---|---|---|
| A1 | Beheerder aanmelden | B: kaart scannen, *Aanmelden*. Beheerpagina → Status → **Goedkeuren als beheerder** | B krijgt bericht "Aangemeld … Je bent ook beheerder" | ☐ |
| A2 | Vrijwilliger, goedkeuren vanaf telefoon | V1: kaart scannen, *Aanmelden* | V1: "Aanmelding ontvangen (nr X)". B: "Aanmelding #X … Antwoord JA X of NEE X". B stuurt `JA X` → V1: "Aangemeld" | ☐ |
| A3 | Goedkeuren via beheerpagina | V2 aanmelden; beheerpagina → Status → **Goedkeuren** | V2: "Aangemeld". B krijgt bericht "(via beheerpagina)" | ☐ |
| A4 | Twee keer op Aanmelden tikken | V2 (nog niet goedgekeurd) tikt twee keer | Zelfde nummer; B krijgt maar **één** bericht | ☐ |
| A5 | Al aangemeld, nog eens aanmelden | V1 meldt opnieuw aan | V1: "U bent al aangemeld" | ☐ |
| A6 | Afwijzen | Nieuwe aanmelding van V2 (na AF, zie A9); B stuurt `NEE X` | V2: "niet goedgekeurd". Daarna opnieuw aanmelden kan | ☐ |
| A7 | Verkeerde aanmeldcode | B stuurt `CODE TEST123`; V2 meldt aan met de **oude** kaart | V2: "onjuiste aanmeldcode"; B krijgt niets. Daarna terugzetten: `CODE <oude code>` | ☐ |
| A8 | Onbekende telefoon meldt | Telefoon die **niet** is aangemeld stuurt een M/ETHANE-melding | Wordt **niet** doorgezet; telefoon krijgt "NIET doorgegeven"; staat op beheerpagina bij *Onbekende telefoons* | ☐ |
| A9 | Afmelden | B stuurt `AF <naam van V2>` (of beheerpagina → Vrijwilligers → Afmelden) | B: "Afgemeld: …". V2: "U bent afgemeld" | ☐ |
| A9b | Afgemelde telefoon meldt toch | V2 stuurt een M/ETHANE-melding en een gewoon bericht | Niet doorgezet. V2 krijgt terug: "… is NIET doorgegeven … niet (meer) aangemeld" | ☐ |
| A10 | Aanmelding blijft na herstart | V2 meldt aan, **niet** goedkeuren; steunpunt herstarten (`sudo reboot`); daarna `JA X` | Werkt; nummer is bewaard | ☐ |

## B. Beheeropdrachten (vanaf telefoon B)

| # | Opdracht | Verwacht | OK |
|---|---|---|---|
| B1 | `HELP` | Lijst met opdrachten | ☐ |
| B2 | `WACHT` | Open aanmeldingen, of "Geen open aanmeldingen" | ☐ |
| B3 | `LIJST` | Aangemelde telefoons, laatst gehoord, accu | ☐ |
| B4 | `CODE` | Huidige aanmeldcode | ☐ |
| B4a | `CODE <nieuwe code>` | B: "Nieuwe aanmeldcode: …". Beheerpagina (Status en Steunpunt) toont de nieuwe code. Aangemelde telefoons blijven aangemeld; nieuwe aanmelding met de oude kaart: "onjuiste aanmeldcode". Tabblad Kaart → nieuwe kaart maken: staat de nieuwe code op? Daarna eventueel terugzetten | ☐ |
| B5 | `JA 999` (bestaat niet) | "bestaat niet (meer)" | ☐ |
| B6 | Opdracht vanaf V1 (geen beheerder), bijv. `LIJST` | Geen beheerantwoord; het gaat als gewoon bericht naar de eindpost | ☐ |
| B7 | `ALLEN Testbericht aan allen` (V1 en V2 aan, B zelf ook aangemeld) | B: "Verstuurd naar 2 vrijwilligers…". V1 en V2 krijgen "<steunpunt> aan alle vrijwilligers: Testbericht aan allen" (B zelf niet). Het gaat **niet** over 2 m | ☐ |
| B7a | Daarna `LIJST` | Onderaan: "Bericht aan allen (hh:mm): ontvangen door 2 van 2." | ☐ |
| B7b | V2 uit, opnieuw `ALLEN …`, na een paar minuten `LIJST` | "ontvangen door 1 van 2. Nog niet: V2" | ☐ |
| B7c | Beheerpagina → Vrijwilligers → *Bericht aan alle vrijwilligers* | Groene melding; V1 en V2 (en B) krijgen het; onder het veld staat wie het heeft ontvangen (pagina verversen) | ☐ |
| B7d | `ALLEN` zonder tekst, en een tekst van meer dan 300 tekens | Uitleg terug, er wordt niets verstuurd | ☐ |
| B8 | `AAN <voornaam V1> Testbericht` | Alleen V1 krijgt "Bericht van <steunpunt>: Testbericht"; B krijgt *verstuurd* en daarna *Afgeleverd bij …* | ☐ |
| B8a | V2 uit; `AAN <naam V2> hallo` | B krijgt na een tijd *Niet aangekomen bij …* | ☐ |
| B8b | Twee vrijwilligers met dezelfde voornaam; `AAN <voornaam> hallo` | B krijgt *Welke bedoel je: …*; er wordt niets verstuurd | ☐ |
| B8c | Beheerpagina: Posities → tik op V1 → *Bericht sturen* | Vrijwilligers opent met V1 bij *Aan*; versturen; V1 krijgt het; onder *Berichten aan één vrijwilliger* staat *afgeleverd* | ☐ |

## C. Melden

| # | Scenario | Verwacht | OK |
|---|---|---|---|
| C1 | V1 stuurt M/ETHANE via **433** | Eindpost: scherm + logboek. Steunpunt log: bevestigd (ACK) | ☐ |
| C2 | V2 stuurt M/ETHANE via **868** | Idem | ☐ |
| C3 | Groot incident: bij **M** "Ja, …" | Kop **rood** met "– GROOT INCIDENT"; knippert (zoals elke nieuwe melding) | ☐ |
| C3b | Geen groot incident: bij **M** "Nee, …" | Kop **oranje**; knippert ook | ☐ |
| C4 | Eindpost uit (of Direwolf stoppen), V1 meldt | Steunpunt blijft herhalen; na 5 min op Status: *Nog niet bevestigd* | ☐ |
| C5 | Eindpost weer aan | Melding komt alsnog aan, ACK, waarschuwing weg | ☐ |
| C6 | Twee posten bij één discipline. Tabblad **Netwerk**: zet bij *Gemeentehuis* `PD3PAM-5, PD3PAM-9` (PD3PAM-9 bestaat niet) en sla op. V1 meldt aan *Gemeentehuis* | PD3PAM-5 bevestigt; steunpunt blijft herhalen voor PD3PAM-9. Na 5 min op Status: *Nog niet bevestigd* door PD3PAM-9, met knop **Niet meer wachten op PD3PAM-9** → melding uit de wachtrij. Daarna PD3PAM-9 weer weghalen op tabblad Netwerk | ☐ |
| C7 | Melding met lange tekst (veel slachtoffers/locatie) | Komt compleet aan (meerdere delen samengevoegd) | ☐ |
| C8 | Melding met *Ik ben ter plaatse: stuur mijn positie mee* aangevinkt | Bij *E - Exacte locatie* staat onder de tekst **Positie melder (ter plaatse): 52.xxxxx, 6.xxxxx (± .. m)**; in de lijst *Melder ter plaatse* | ☐ |
| C8a | Na C8 het meldscherm opnieuw openen; en een melding zonder het vinkje | Vinkje staat weer **uit**. Melding zonder vinkje: geen positie op het scherm | ☐ |
| C9 | (Met 2 steunpunten) V van SP1 en V van SP2 melden tegelijk aan dezelfde eindpost | Beide komen aan, eventueel één tot 1 min later; geen dubbele regels op het scherm | ☐ |
| C10 | Typen in de app: bij **E** "Holterweg thv 12", een paar letters weghalen en verbeteren, dan **T** en **H** aantikken en invullen | T en H bevatten alleen wat je daar zelf typt (niets uit E). Ook bij *Uw naam* bij het aanmelden | ☐ |
| C11 | App-naam en versie | Op de telefoon heet de app **Noodnet**; nieuwe APK installeert over de oude heen, aanmelding blijft | ☐ |

## D. Gehoord en uit beeld

| # | Scenario | Verwacht | OK |
|---|---|---|---|
| D1 | V1 uitzetten of RNode loskoppelen | Na de ingestelde tijd (*uit beeld na*, tabblad Steunpunt): B krijgt "niet meer gehoord sinds …"; `LIJST` toont het | ☐ |
| D2 | V1 weer aan | B krijgt "weer gehoord (na … stilte)" | ☐ |
| D3 | Accu van een RNode laag (als je dat kunt nabootsen) | Waarschuwing aan B | ☐ |
| D4 | Met internet: steunpunt → tabblad **Posities** → gemeente, 10 km, detail 16 → **Kaart downloaden** | *Kaart gedownload* met aantal tegels | ☐ |
| D5 | Zonder internet: tabblad **Posities** | Kaart van de gemeente; elke vrijwilliger met positie als stip met naam: groen actief, oranje accu laag, rood uit beeld. Tik: laatst gehoord, accu, coördinaten | ☐ |
| D6 | Tabblad **Vrijwilligers** → *op de kaart* bij V1 | Posities opent ingezoomd op V1 met zijn gegevens | ☐ |
| D7 | Posities → *Steunpunt op de kaart aanwijzen* → op een plek tikken → bevestigen | *Steunpunt geplaatst op …*; blauw vierkant met naam en roepnaam; dezelfde coördinaten staan op tabblad **Steunpunt** | ☐ |

## E. Storingen

| # | Scenario | Verwacht | OK |
|---|---|---|---|
| E1b | Eindpost herstarten (`sudo reboot`) | M/ETHANE-scherm toont na het opstarten de laatste melding én de lijst met eerdere meldingen | ☐ |
| E1 | Steunpunt herstarten | Na ± 2 min alles groen, hotspot aan, aanmeldingen bewaard | ☐ |
| E2 | Een RNode losmaken en terugzetten | Status toont het; na terugzetten werkt de band weer (zo nodig `rnsd` herstarten op Status) | ☐ |
| E2b | Pi uit, één RNode eruit, Pi aan | Na ± 2 min: rnsd en brug groen, steunpunt werkt op de overgebleven band | ☐ |
| E2c | Stroom eraf (stekker eruit) terwijl het steunpunt draait, daarna weer aan | Brug start vanzelf; staat er een beschadigd bestand, dan in het log "Beschadigd ratchet-bestand opzij gezet" en daarna gewoon groen | ☐ |
| E3 | Pi zonder internet opstarten, beheerpagina op telefoon openen | Klok wordt gelijkgezet; tijd in het logboek klopt | ☐ |
| E4 | Telefoon buiten bereik van LoRa, melding versturen, dan terug in bereik | Noteer wat de app doet (blijft hij proberen? komt hij alsnog aan?) | ☐ |

## F. Eindpost

| # | Scenario | Verwacht | OK |
|---|---|---|---|
| F1 | Eindpost herstarten (knop *Pi herstarten*) met monitor | M/ETHANE-scherm opent vanzelf schermvullend; scherm gaat niet op zwart na 10 min | ☐ |
| F2 | Telefoon/laptop op de hotspot: **http://10.42.0.1:1880/ui** | Zelfde M/ETHANE-scherm als op de monitor | ☐ |
| F3 | Tabblad **Logboek** | Meldingen van vandaag; downloaden als .txt en .csv; CSV opent in Excel/LibreOffice | ☐ |
| F4 | Tabblad **Status** → *Steunpunten* | Het steunpunt staat erbij met laatst gehoord, aangemeld, wachtrij | ☐ |
| F5 | Eindpost alleen voor één discipline (Instellingen: bijv. alleen *Gemeentehuis*). Melding aan een **andere** discipline | Eindpost toont niets en bevestigt niet; steunpunt wacht niet op deze post | ☐ |
| F6 | Idem, maar *meelezen* aan | Melding komt in het logboek als *meelezen*; eindpost bevestigt **niet** | ☐ |
| F7 | Gewoon bericht (chat) van V1. Zonder @ gaat het naar de discipline(s) bij *Berichten aan* (tabblad Netwerk); met `@Gemeentehuis` in de tekst naar die discipline | Komt in het logboek van die eindpost; steunpunt krijgt ACK | ☐ |
| F8 | Knop *Wis scherm en lijst* in Node-RED (editor) | Scherm en lijst leeg; logboek blijft compleet | ☐ |
| F9 | Back-up downloaden (tabblad Back-up), daarna terugzetten | Instellingen en logboek terug | ☐ |
| F10 | Radio → Testuitzending en niveaus | Set zendt; steunpunt toont de eindpost bij *Gehoorde stations*, niveau rond 50 (en andersom) | ☐ |
| F11 | Met internet: tabblad **Posities** → gemeente, 10 km, detail 16 → **Kaart downloaden** | Voortgang loopt op; daarna *Kaart gedownload* met het aantal tegels en de datum | ☐ |
| F12 | Zonder internet: **http://10.42.0.1:1880/worldmap/** (laptop/telefoon op de hotspot) | Kaart van de gemeente zichtbaar, ook ingezoomd tot straatniveau | ☐ |
| F13 | V1 stuurt een M/ETHANE **met** *Ik ben ter plaatse* | Op de kaart: rode marker *NIEUW hh:mm · soort* met rode cirkel; kaart schuift ernaartoe; klik toont de hele M/ETHANE | ☐ |
| F14 | Daarna een tweede melding met positie, en een derde **zonder** | Tweede wordt de rode; de eerste wordt blauw. De derde staat niet op de kaart (wel op het M/ETHANE-scherm) | ☐ |
| F15 | Eindpost herstarten, kaart opnieuw openen | Dezelfde markers staan er weer | ☐ |
| F16 | Kaart downloaden zonder internet | Melding *Geen verbinding met PDOK…*; de vorige kaart blijft werken | ☐ |

## G. Dienstdoende operator

| # | Scenario | Verwacht | OK |
|---|---|---|---|
| G1 | Steunpunt: Status → *Nieuwe operator toevoegen* (roepnaam + naam) | Groene melding; log van de brug: "Dienstdoende operator: …" | ☐ |
| G2 | Tweede operator toevoegen; daarna aflossen via de **keuzelijst** | Log: "… (neemt over van …)"; Status blijft compact (wissels ingeklapt onder *Wissels bekijken*) | ☐ |
| G2b | *Operators beheren* → een operator uit de lijst halen (niet degene met dienst) | Verdwijnt uit de keuzelijst; wie dienst heeft kan niet verwijderd worden | ☐ |
| G3 | Eindpost: operator invullen, daarna een M/ETHANE ontvangen | Logboek: regel OPERATOR; bij de melding "dienstdoende operator: …" | ☐ |
| G4 | Back-up maken en terugzetten | Operator en lijst met wissels terug | ☐ |

## H. Frequentie, CAT en netwerkbestand

| # | Scenario | Verwacht | OK |
|---|---|---|---|
| H1 | Steunpunt, tabblad Netwerk: 2 m-frequentie kiezen in de keuzelijst (bijv. 144,950) | Opgeslagen; zonder CAT: melding "zet de set op …"; met CAT: set gaat mee | ☐ |
| H2 | Keuzelijst openen (steunpunt én eindpost → Instellingen) | Alleen 144,8125 t/m 144,9875 in stappen van 12,5 kHz; geen 144,800; huidige frequentie geselecteerd | ☐ |
| H3 | Netwerk → **Exporteren**, op de eindpost (Instellingen) **Inladen** | Eindpost neemt frequentie en zijn eigen disciplines over | ☐ |
| H4 | Zelfde bestand op een tweede steunpunt **Inladen** | Tabblad Netwerk gelijk aan het eerste steunpunt | ☐ |
| H5 | Radio → **Zoek mijn set** (IC-9700 aan) | IC-9700 gevonden met poort en snelheid → **Gebruiken** | ☐ |
| H6 | Na *Gebruiken*: tabblad Radio | *Set (CAT)*: frequentie van de gemeente ✓, mode FM-D | ☐ |
| H7 | Testuitzending met CAT | Set gaat op zenden (PTT via CAT), packet-geluid schoon | ☐ |
| H8 | Aan de VFO draaien, 1 minuut wachten | Set staat weer op de gemeentefrequentie; bij *Laatste acties* "teruggezet" | ☐ |
| H9 | Zendvermogen 25 (watt) invullen en opslaan | Set op 25 W (op de set en bij *Vermogen*); opslaan zonder foutmelding | ☐ |
| H10 | Pi herstarten met CAT | Set na het opstarten vanzelf op frequentie en mode | ☐ |
| H12 | Netwerk met IFAC: **Exporteren zonder IFAC**, op een ander steunpunt inladen | Geen IFAC in het bestand; het andere steunpunt houdt zijn eigen IFAC | ☐ |
| H13 | Bestand op GitHub/website zetten; op de eindpost **Ophalen** met de link | Frequentie en disciplines overgenomen; daarna knop *Opnieuw ophalen* | ☐ |
| H14 | Status op alle Pi's | Overal dezelfde *Netwerkinstellingen: … versie … door …* | ☐ |
| H11 | FT-818 + SCU-17 (steunpunt): Zoek mijn set | FT-818 gevonden; PTT en frequentie werken (of: terug naar RTS als het niet lukt) | ☐ |
| H15 | Zonder internet: Status → **Controleren op nieuwe versie** | Rode melding *Geen verbinding met GitHub…*; niets veranderd | ☐ |
| H16 | Met netwerkkabel: **Controleren op nieuwe versie** | *Er is een nieuwe versie* of *Je hebt al de nieuwste versie* | ☐ |
| H17 | Steunpunt met een M/ETHANE in de wachtrij (eindpost uit): Controleren | Rode waarschuwing over de wachtrij boven de knop | ☐ |
| H18 | **Nu bijwerken**, pagina openhouden | Verslag loopt mee; pagina valt even weg en komt terug; *Klaar: bijgewerkt naar versie …*; rechtsboven de nieuwe versie | ☐ |
| H19 | Na H18 (steunpunt): wachtrij uit H17 | Melding gaat na het bijwerken verder en wordt bevestigd zodra de eindpost aan is | ☐ |
| H20 | Zonder kabel: Status → **Bijwerken via thuis-wifi** | Naam van je thuis-wifi staat erbij; uitlegpagina met de 4 stappen (en wachtrij-waarschuwing als er een M/ETHANE wacht) | ☐ |
| H21 | **Nu bijwerken via …**, na een kwartier weer met Noodnet-… verbinden, /bijwerken openen | Hotspot is terug; verslag toont *Verbonden, internet werkt*, het bijwerken en *Hotspot is weer aan*; *Klaar* | ☐ |
| H22 | Thuis-wifi uit (router uit) en H21 herhalen | Binnen ± 2 min is de hotspot terug; verslag: *verbinden … lukte niet* (code 4) | ☐ |
| H23 | USB-tethering met de telefoon (telefoon op de wifi van de Pi), dan **Controleren op nieuwe versie** | Pi heeft internet; bijwerken werkt zoals H18 | ☐ |

## Notities

-

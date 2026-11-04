# Noodnet - testplan aanmelden en melden

Volg de scenario's in deze volgorde. Vink af wat werkt en noteer wat anders gaat dan
verwacht (wat je zag, op welke telefoon, hoe laat). Telefoons: **B** = beheerder,
**V1**, **V2** = vrijwilligers.

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
| B5 | `JA 999` (bestaat niet) | "bestaat niet (meer)" | ☐ |
| B6 | Opdracht vanaf V1 (geen beheerder), bijv. `LIJST` | Geen beheerantwoord; het gaat als gewoon bericht naar de eindpost | ☐ |

## C. Melden

| # | Scenario | Verwacht | OK |
|---|---|---|---|
| C1 | V1 stuurt M/ETHANE via **433** | Eindpost: scherm + logboek. Steunpunt log: bevestigd (ACK) | ☐ |
| C2 | V2 stuurt M/ETHANE via **868** | Idem | ☐ |
| C3 | Groot incident (prioriteit hoog) | Rode kop op het scherm, knippert | ☐ |
| C4 | Eindpost uit (of Direwolf stoppen), V1 meldt | Steunpunt blijft herhalen; na 5 min op Status: *Nog niet bevestigd* | ☐ |
| C5 | Eindpost weer aan | Melding komt alsnog aan, ACK, waarschuwing weg | ☐ |
| C6 | Discipline met twee eindpost-roepnamen (één bestaat niet) | Blijft herhalen tot beide bevestigen; waarschuwing voor de ontbrekende | ☐ |
| C7 | Melding met lange tekst (veel slachtoffers/locatie) | Komt compleet aan (meerdere delen samengevoegd) | ☐ |

## D. Gehoord en uit beeld

| # | Scenario | Verwacht | OK |
|---|---|---|---|
| D1 | V1 uitzetten of RNode loskoppelen | Na de ingestelde tijd (*uit beeld na*, tabblad Steunpunt): B krijgt "niet meer gehoord sinds …"; `LIJST` toont het | ☐ |
| D2 | V1 weer aan | B krijgt "weer gehoord (na … stilte)" | ☐ |
| D3 | Accu van een RNode laag (als je dat kunt nabootsen) | Waarschuwing aan B | ☐ |

## E. Storingen

| # | Scenario | Verwacht | OK |
|---|---|---|---|
| E1 | Steunpunt herstarten | Na ± 2 min alles groen, hotspot aan, aanmeldingen bewaard | ☐ |
| E2 | Een RNode losmaken en terugzetten | Status toont het; na terugzetten werkt de band weer (zo nodig `rnsd` herstarten op Status) | ☐ |
| E3 | Pi zonder internet opstarten, beheerpagina op telefoon openen | Klok wordt gelijkgezet; tijd in het logboek klopt | ☐ |
| E4 | Telefoon buiten bereik van LoRa, melding versturen, dan terug in bereik | Noteer wat de app doet (blijft hij proberen? komt hij alsnog aan?) | ☐ |

## Notities

-

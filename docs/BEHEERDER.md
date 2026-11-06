# Noodnet - beheer van een Noodsteunpunt (kort)

Dit is de korte handleiding voor de **beheerder** van een Noodsteunpunt: de zendamateur die het
steunpunt bemant, of iemand die hij daarvoor aanwijst. Hierin staat wat je tijdens een inzet doet:
vrijwilligers goedkeuren, in de gaten houden wie er actief is, en het steunpunt aan en uit zetten.
Het opzetten van een steunpunt staat in de volledige procedure (*Noodnet-procedure.pdf*).

**Afdrukken?** Deze handleiding staat ook als PDF in [Noodnet-beheerder.pdf](Noodnet-beheerder.pdf),
met achterin een zakkaart.

Je kunt het steunpunt op twee manieren beheren:

| Hoe | Waar | Wat kan het |
|---|---|---|
| **Berichten** vanuit de Noodnet-app, via je RNode | Overal binnen LoRa-bereik van het steunpunt | Aanmeldingen goedkeuren, lijst van vrijwilligers, afmelden, aanmeldcode, bericht aan allen |
| **Beheerpagina** via de wifi van het steunpunt | Vlak bij het steunpunt | Alles: status, dienstdoende operator, kaart en QR-code, radio, uitzetten |

Je krijgt ook zelf berichten van het steunpunt: nieuwe aanmeldingen, en waarschuwingen als een
vrijwilliger niet meer gehoord wordt of zijn accu bijna leeg is.

---

## Beheerder worden (eenmalig)

Je telefoon wordt beheerder door hem aan te melden en op de beheerpagina als beheerder goed te keuren.

1. Maak je telefoon en RNode klaar zoals een vrijwilliger: app installeren, RNode koppelen
   (zie de *handleiding voor vrijwilligers*).
2. Meld je aan met de kaart: rode knop **NOODMELDING M/ETHANE** → **KAART VAN STEUNPUNT SCANNEN**
   → band kiezen, naam invullen → **AANMELDEN**.
3. Verbind je telefoon met de wifi **Noodnet-…** van het steunpunt en open **http://10.42.0.1:8080**
   (gebruiker **beheer**).
4. Tabblad **Status** → *Wachten op goedkeuring* → **Goedkeuren als beheerder**.

Er kunnen meer beheerders zijn, bijvoorbeeld voor een aflossing. Elke beheerder krijgt dezelfde
berichten.

## Opdrachten via de app

Open in de app het gesprek met het steunpunt (in de lijst *Conversations*, onder de naam van het
steunpunt). Typ een opdracht en verstuur hem. Hoofdletters zijn niet nodig. Het antwoord komt in
hetzelfde gesprek.

| Opdracht | Wat gebeurt er | Voorbeeld |
|---|---|---|
| `WACHT` | Toont de aanmeldingen die op goedkeuring wachten, met hun nummer | `WACHT` |
| `JA <nr>` | Keurt aanmelding nummer *nr* goed; de vrijwilliger krijgt bericht | `JA 3` |
| `NEE <nr>` | Wijst aanmelding nummer *nr* af | `NEE 4` |
| `LIJST` | Wie is aangemeld, wanneer laatst gehoord, accustand | `LIJST` |
| `AF <naam>` | Meldt een vrijwilliger af; zijn meldingen worden daarna niet meer doorgegeven | `AF Jan` |
| `CODE` | Toont de huidige aanmeldcode | `CODE` |
| `CODE <nieuw>` | Zet een nieuwe aanmeldcode (bijv. als een kaart kwijt is) | `CODE ZOMER26` |
| `ALLEN <tekst>` | Stuurt een bericht naar alle aangemelde vrijwilligers van dit steunpunt | `ALLEN Einde oefening, bedankt!` |
| `HELP` | Toont alle opdrachten | `HELP` |

Controleer bij een aanmelding wie het is voordat je `JA` stuurt. Twijfel je: stuur `NEE`, of laat de
aanmelding even staan.

**Bericht aan allen.** Met `ALLEN` gaat je tekst (max. 300 tekens) naar elke aangemelde vrijwilliger,
één voor één met een paar seconden ertussen: bij twintig vrijwilligers duurt het ongeveer een minuut.
Jij krijgt terug naar hoeveel vrijwilligers het gaat. Stuur daarna `LIJST`: onderaan staat wie het
bericht heeft ontvangen en wie nog niet (RNode uit of buiten bereik). Het bericht gaat alleen naar de
vrijwilligers van dit steunpunt.

Na een nieuwe aanmeldcode werken de oude kaarten niet meer om je aan te melden. Wie al is aangemeld,
merkt er niets van. Maak dan op de beheerpagina een nieuwe kaart (tabblad **Kaart**).

## Berichten die je krijgt

| Bericht | Wat betekent het | Wat doe je |
|---|---|---|
| *Aanmelding #3: Jan (telefoon …). Antwoord JA 3 of NEE 3* | Iemand meldt zich aan met de kaart | Controleer wie het is, dan `JA 3` of `NEE 3` |
| *Jan niet meer gehoord sinds 14:20, laatst bij 52.25…, 6.16…* | De telefoon van Jan is een tijd stil | Probeer contact op te nemen; de positie is waar hij het laatst was |
| *accu RNode van Jan is 15%* (of *accu telefoon*) | Een accu is bijna leeg | Vraag Jan om op te laden of te wisselen |
| *Jan weer gehoord (na 25 min stilte)* | Jan is terug in beeld | - |
| *… (via beheerpagina)* | Iemand heeft iets op de beheerpagina gedaan, bijv. een aanmelding goedgekeurd | Ter informatie |

## Op de beheerpagina

Verbind met de wifi **Noodnet-…** van het steunpunt en open **http://10.42.0.1:8080**. Meldt Android
"geen internet": kies **Verbonden blijven**.

| Wat wil je | Waar |
|---|---|
| Is alles in orde? | Tabblad **Status**: alles groen, geen rode melding |
| Dienst overnemen of aflossen | **Status** → *Dienstdoende operator* → kies jezelf → **Dienst overnemen** |
| Aanmelding goedkeuren of afwijzen | **Status** → *Wachten op goedkeuring* |
| Wie is actief, accu's, afmelden | Tabblad **Vrijwilligers** (ook *Onbekende telefoons*) |
| Bericht aan alle vrijwilligers | **Vrijwilligers** → *Bericht aan alle vrijwilligers*; daaronder zie je wie het heeft ontvangen |
| Vrijwilliger laten aanmelden zonder printer | **Kaart** → **QR-code groot tonen** en laat scannen van je scherm |
| Melding blijft *Nog niet bevestigd* | **Status**: die eindpost staat uit of is buiten bereik. Bestaat hij niet: **Niet meer wachten op …** |
| Radio controleren | Tabblad **Radio** → *Gehoorde stations* en *Testuitzending* |
| Steunpunt uitzetten | **Status** → onderaan **Pi uitschakelen** |

## Begin en einde van een inzet

**Begin:**

- [ ] Antennes op de set en de RNodes, dan alles aanzetten. Wacht 2 minuten.
- [ ] Beheerpagina openen op je telefoon: de Pi neemt dan de tijd van je telefoon over.
- [ ] **Status**: alles groen. Bij *Netwerkinstellingen* dezelfde versie als de andere steunpunten.
- [ ] **Dienst overnemen** als dienstdoende operator.
- [ ] In de app: `LIJST` en `WACHT`.

**Einde:**

- [ ] Laat de vrijwilligers weten dat het steunpunt stopt: `ALLEN Einde oefening, bedankt allemaal!`
- [ ] `LIJST`: heeft iedereen het bericht ontvangen?
- [ ] Beheerpagina → **Status** → **Pi uitschakelen**. Wacht tot het groene lampje op de Pi niet meer
      knippert (± 20 seconden); dan pas de stroom eraf.

## Als iets niet werkt

| Probleem | Oplossing |
|---|---|
| Geen antwoord op een opdracht | Ben je beheerder (stap *Beheerder worden*)? RNode aan en gekoppeld, binnen bereik? Probeer het vlak bij het steunpunt. |
| *Niemand gevonden voor …* bij `AF` | Gebruik de naam zoals hij in `LIJST` staat. |
| Vrijwilliger kan niet melden (*NIET doorgegeven*) | Staat hij in `LIJST`? Zo niet: opnieuw laten aanmelden met de kaart en goedkeuren. |
| Kaart kwijt of in verkeerde handen | `CODE <nieuw>`, dan op de beheerpagina **Kaart** → *Nieuwe kaart maken*. Een onbekende telefoon afmelden met `AF <naam>`. |
| Beheerpagina opent niet | Op de wifi van het steunpunt? Adres **http://10.42.0.1:8080**. Mobiele data even uit. |
| Iets anders | Zie *Problemen oplossen* in de volledige procedure. |

Laat de beheertelefoon niet onbeheerd liggen: met deze telefoon kun je vrijwilligers goedkeuren en
afmelden. Zet er een schermvergrendeling op.

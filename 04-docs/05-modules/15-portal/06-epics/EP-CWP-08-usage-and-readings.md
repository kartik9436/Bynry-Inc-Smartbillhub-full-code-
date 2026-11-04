# EP-CWP-08 — Usage, readings and equipment

**Module:** portal (reads metering) · **Wave:** release 2 (self-read: 3) ·
**Screens:** CWP-033 … CWP-037 · CWP-078 · **Status:** draft

## Scope

**In:** usage over twelve or twenty-four months, every reading with how it was taken, the
customer's own reading, the equipment at the property, and the high-usage alert that has
no trigger.

**Out:** the bill the readings feed (`EP-CWP-07`), disputing a reading (`EP-CWP-11`).

⚠ **ONE OF THESE IS THE PORTAL'S MOST VALUABLE WRITE.** For a utility with one or two
staff, **a self-read that arrives on time is a walk somebody did not have to make.**

⚠ **AND IT MUST GO THROUGH THE VALIDATION THAT ALREADY EXISTS.** Read validation with
high and low thresholds, rollover handling and estimation runs on staff-entered readings
today. **A customer read that skipped the thresholds would be a route into billing that
nobody checked.**

## Capability matrix

| Screen | Search | Filters | Default sort | Sortable | Columns | Row actions | Bulk | Export |
|---|---|---|---|---|---|---|---|---|
| CWP-033 | — | 12 months · 24 months | Period | — | — | — | — | CSV |
| CWP-034 | — | — | Taken desc | Taken | Taken · Reading · Used since · How · On which bill | View · Query (icons) | — | — |
| CWP-035 | — | — | — | — | — | — | — | — |
| CWP-037 | — | — | — | — | Equipment · Serial · Where · Fitted · Last read · Status | — | — | — |

---
id: US-CWP-040
epic: EP-CWP-08
module: portal
screens: [CWP-033]
wave: 2
status: ready
blocked_by: []
depends_on: [US-CWP-023]
journeys: [J36]
rules: [BR-CWP-073, BR-CWP-095]
golden_tests: []
finance_calc: none
---
### US-CWP-040 — Usage, and the services that are not measured say so

**1 · Details** — As **a customer**, I want **my usage over a year**, so that **I can see
whether this month is unusual**.

Three tiles — this period with a comparison to the same month last year, the daily
average with a plain-English band, and when the next reading is due. A twelve or
twenty-four month chart. Then a per-service summary. A CSV export. A tip slot.

⚠ **NOT EVERY SERVICE IS MEASURED, AND THE SCREEN HAS TO SAY SO RATHER THAN DRAW AN EMPTY
CHART.** Sewer is priced as a **share of water**; trash is priced on **the cart at the
kerb**. Of the eleven services this product bills, only some produce a reading — the rest
are charged on equipment recorded at the unit, **and a portal that pretends otherwise
will be asked where the missing graph is.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-073` | Unmeasured services say what they are billed on; **no empty chart** | CONFIRMED — blueprint `P19` |
| Inherited | Consumption always carries its unit — including on a chart axis | hard rule 3 |
| `BR-CWP-095` | One tip, on and in season, or no slot at all | CONFIRMED — `CP-32` |
| `BR-CWP-010` | Scoped to the account in the switcher | CONFIRMED — blueprint §20 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | A water account with twelve months of reads | `4,820 gal` this period, *18% above last August*, daily average `155 gal`, next reading due *2–6 Sep* |
| TC-2 | The chart | Twelve bars, **the axis labelled in gallons**, highest and lowest marked — `3,050 gal` lowest, `4,820 gal` highest |
| TC-3 · **negative** | The sewer panel | Reads *"Billed on: Water used · Not separately metered"* — ⚠ **no chart and no zero series** |
| TC-4 · **negative** | The trash panel | Reads *"Billed on: Your 96 gal cart · Not measured"* |
| TC-5 · **negative** | A **trash-only** account | ⚠ No chart on the screen at all, and the screen still makes sense |
| TC-6 · **negative** | An account with **one** month of history | No year-on-year comparison offered — ⚠ not a comparison against nothing |
| TC-7 · **tenant isolation** | Usage with a Pine Hill session | Pine Hill reads only |
| TC-8 | Switch to 24 months | Twenty-four bars from the same source, no re-computation of the unit |
| TC-9 | CSV export | Every row carries its unit as a column, not in a header only |
| TC-10 | The in-season tip | *"Watering before 10am loses less to evaporation"* shows in September (Jun–Sep) and is **gone on 1 October** |

**4 · Test Data** — Water: this period `4,820 gal`, 18% above last August; daily average
`155 gal` (*household of three: typical*); this year `48,120 gal`, last year `44,900
gal`; lowest month `3,050 gal`, highest `4,820 gal`. Sewer: billed on water used, not
separately metered. Trash: billed on a `96 gal` cart, not measured. Next reading window
2–6 Sep. Tip *"Watering before 10am loses less to evaporation"*, Usage, Jun–Sep, on.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| This period | CWP-033 | prototype-extracted | monthly consumption per service | numeric + unit | computed-display | ⚠ Unit always |
| Comparison | CWP-033 | prototype-extracted | same month last year | percentage | computed-display | Displayed to 0 dp as a percentage of usage, not money |
| Daily average | CWP-033 | prototype-extracted | consumption ÷ days in period | numeric + unit | computed-display | — |
| Next reading due | CWP-033 | prototype-extracted | read window for the route | date range | reference-data | Absent when no window is open |
| Billed on | CWP-033 | prototype-extracted | the service's pricing basis | text | reference-data | ⚠ Drives whether a chart exists |

**6 · Acceptance** — **Given** an account with water, sewer and trash, **when** usage
opens, **then** water has a twelve-month chart with gallons on the axis, sewer says it is
billed on water used and draws nothing, and trash says it is billed on a `96 gal` cart
and draws nothing.

**7 · Finance Calculation** — N/A. Usage is not money. ⚠ **But the sewer panel's
"billed on water used" is the one place a customer learns why two charges move
together**, and that sentence is worth more than a chart.

**8 · Open Questions** — None.

---
id: US-CWP-041
epic: EP-CWP-08
module: portal
screens: [CWP-034]
wave: 2
status: ready
blocked_by: []
depends_on: [US-CWP-040]
journeys: [J39]
rules: [BR-CWP-071, BR-CWP-072, BR-CWP-069]
golden_tests: []
finance_calc: none
---
### US-CWP-041 — Every reading, how it was taken, and why one was corrected

**1 · Details** — As **a customer**, I want **each reading with how you got it**, so that
**"you estimated and overcharged me" never has to be a phone call**.

A table: taken, reading, used since, **how it was taken**, and which bill it fed. Methods
read plainly — *Read by a meter reader*, *ESTIMATED then corrected*, *You sent it in*. A
note: *an estimated reading is our best guess when nobody could get to the meter. The
next real reading corrects it, and you are never charged twice for the same water.*

⚠ **HOW A READING WAS TAKEN IS AS IMPORTANT AS THE NUMBER.** The product already records
the method on every read, including estimation, and estimates are trued up by the next
actual reading. **Showing that plainly is what prevents the most common dispute in
metered billing.**

⚠ **AND A CORRECTION SHOWS ITS REASON AND ITS SIZE** — *"estimated 144,600, corrected to
144,130 when the meter was read on 3 July — you were not charged twice"*.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-071` | The method is shown as prominently as the number, estimation included | CONFIRMED — blueprint `P20` |
| `BR-CWP-072` | Why a read was corrected, and by how much | CONFIRMED — `CP-55` |
| `BR-CWP-069` | A superseded read must not leave the customer charged twice | CONFIRMED — blueprint §11 Figure 6 |
| Inherited | Readings carry their unit | hard rule 3 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Four readings on the water meter | Each with its method in words and the bill it fed |
| TC-2 | The estimated row | Reads **ESTIMATED then corrected**, and opening it gives *"estimated 144,600, corrected to 144,130 when the meter was read on 3 July — you were not charged twice"* |
| TC-3 | A customer-submitted row | Reads *"You sent it in"* |
| TC-4 · **negative** | A read still awaiting review | Reads *"You sent it in · awaiting review"* and its *on which bill* column is **empty**, not a guess |

⚠ **TC-4 IS HALF BUILT AS OF 2026-09-04 (`CR-068` wave H), AND THE MISSING HALF IS SCHEMA RATHER
THAN SCOPE.** The **empty bill cell** is live and asserted: `meter_reads` carries no invoice
reference at all, so the portal matches a reading's date against the ISSUED bill whose period covers
it, and a reading no bill covers shows nothing rather than the nearest one. The **`· awaiting
review` suffix is NOT built**, because `meter_read.review_state` and `meter_read.source = 'portal'`
are declared as **GAP** columns in `US-CWP-042` §5 and that story is wave 3 — *no row in this
product can hold either value today*, so a screen rendering the suffix would be rendering a state
nothing sets (hard-won law 2). It arrives with `US-CWP-042`, and the boundary is in the decision log
for 2026-09-04.
| TC-5 · **negative** | A **superseded** submitted read | Shown as superseded, and ⚠ **assert no bill charged both it and its replacement** |
| TC-6 · **negative** | An account with no reads | An empty state naming what will fill it |
| TC-7 · **tenant isolation** | The list with a Pine Hill session | Pine Hill reads only |
| TC-8 | A **rollover** — the dial passing its maximum | Used-since is computed through the rollover, not as a negative |
| TC-9 · **negative** | Any reading cell | ⚠ Carries its unit in the used-since column — `4,820 gal`, never `4,820` |

**4 · Test Data** — 31 Aug 2026 `153,040`, `4,820 gal` since, read by a meter reader,
`BL-2608-0141`. 31 Jul `148,220`, `4,090 gal`, reader, `BL-2607-0139`. 30 Jun `144,130`,
`3,760 gal`, **estimated then corrected** (estimated `144,600`, corrected to `144,130` on
3 Jul), `BL-2606-0147`. 31 May `140,370`, `3,410 gal`, **you sent it in**,
`BL-2605-0131`. 26 rows in total. A rollover case at `999,900` → `000,400`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Taken | CWP-034 | prototype-extracted | `meter_read.read_on` | date | system-derived | — |
| Reading | CWP-034 | prototype-extracted | `meter_read.value` | numeric | system-derived | The dial figure |
| Used since | CWP-034 | prototype-extracted | consumption between reads | numeric + unit | computed-display | ⚠ Through a rollover, never negative |
| How it was taken | CWP-034 | prototype-extracted | `meter_read.method` + new `source` | enum | system-derived | ⚠ Plain English, never a code |
| On which bill | CWP-034 | prototype-extracted | the invoice it fed | text | system-derived | Empty while awaiting review |
| Correction | CWP-034 | prototype-extracted | `ReadCorrection` | — | system-derived | Its reason **and** its size |

**6 · Acceptance** — **Given** a meter whose June reading was estimated and corrected in
July, **when** the readings list opens, **then** that row says so, opening it explains
the correction with both figures and states the customer was not charged twice, and a
submitted read awaiting review shows no bill against it.

**7 · Finance Calculation** — N/A. Consumption between reads is existing, tested
arithmetic; this screen reads it. ⚠ **The true-up that stops double-charging is the
finance-relevant behaviour, and it already exists** — this story makes it visible.

**8 · Open Questions** — None.

---
id: US-CWP-042
epic: EP-CWP-08
module: portal
screens: [CWP-035, CWP-078]
wave: 3
status: draft            # was `blocked`; OQ-1393 ruled 2026-09-04 — accepted, validated, flagged when it objects, AND flagged as the customer's on every reading
blocked_by: []
depends_on: [US-CWP-041]
journeys: [J39]
rules: [BR-CWP-067, BR-CWP-069, BR-CWP-070, BR-CWP-074]   # BR-CWP-068 SUPERSEDED by BR-CWP-074; BUILT 2026-10-17 (DEF-CWP-10175) — CWP-035 at /usage/submit, POST portal/accounts/{id}/readings/send, source customer
golden_tests: []
finance_calc: none
---
### US-CWP-042 — Send your own reading: one validation, two sources

**1 · Details** — As **a customer**, I want **to send my own reading**, so that **nobody
has to walk to my meter** — and as **the utility**, I want **it checked exactly as our
own reader's would be**.

Which meter, the date read, the dial figure, an optional photo (held — TC-11). Live feedback against the
account's own history. A *what happens to it* panel: *you send it held, not billed yet ·
we check it, same rules as our own readers · it goes on your next bill, or we ring you if
it looks odd.*

⚠ **THE VALIDATION SHOWN IS THE PRODUCT'S OWN, NOT SOMETHING INVENTED FOR THE PORTAL.**
High and low thresholds, rollover handling and estimation already exist and run on
staff-entered readings. **A customer-submitted read must go through exactly the same
rules or it becomes a second, weaker path into billing.**

⚠ **AND IT LANDS AWAITING REVIEW, NOT IN A BILL RUN.**

⚠ **NOT BLOCKED — `OQ-1393` WAS RULED ON 2026-09-04, AND THE ANSWER IS NOT THE ONE
THIS PARAGRAPH USED TO GIVE (`DEF-CWP-4194`, amended 2026-09-06).** This body said
*"BLOCKED ON `OQ-1393`: whether a submitted read may go straight onto a bill. The
blueprint assumes review. Build the submission, the validation call and the review
state; stub the straight-through path."* **Every clause of that is now wrong**, and it
survived because the frontmatter was corrected and the body was not — the split
`CLAUDE.md` warns about, where only the status is treated as authoritative and the
instructions rot underneath it. **There is nothing here to stub.**

The PO chose **option (b)** and added a requirement no option offered, verbatim:

> *"we accept the reading - and then run the validation and flag it if any issue;
> **you will also ahve to flag that this reading is reacievd from Cosnumer**"*

**So there are TWO flags and they are different facts.** A **validation** flag — *this
figure looks wrong* — raised only when the check objects, which is the `158,940` case
below. And a **provenance** flag — *this figure came from the customer* — raised on
**every** customer reading including the ones that pass cleanly, because a reading that
validates perfectly is still one the utility did not take, and a clerk settling a
disputed bill months later needs to know which it was.

⚠ **THE PROVENANCE FLAG IS A FOURTH VALUE ON A SIGNED LIST, AND THAT IS THE REAL WORK
THIS RULING CREATED.** `apps/metering/models.py` declares
`READ_SOURCES = ("ami", "manual", "import")` and B2 `meter_source` names the same
three. The customer's own reading is **not `manual`** — manual means a person the
utility SENT, which is precisely the distinction the flag exists to preserve. The
catalogues already carry `portal.readings.how.self_read` (*You sent it in*) in all
eleven languages and **no row in this product can wear it today**, which a browser
confirmed on 2026-09-06.

**What (b) buys, so nobody re-litigates it:** option (a) — always review — would have
put a clerk in front of every self-read, which removes the reason to offer self-reading
at all. A passing reading no longer waits for a human; a flagged one still does.

⚠ **AND THE BLUEPRINT'S OWN FIGURE HERE WAS WRONG AND IT CORRECTED ITSELF.** `5,900
gallons in two days` against a stated `155 gal/day` is **about nineteen times usual, not
eight** — its §26 lists the repair. **Use nineteen.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-067` | The **same** validation service as a staff read — one validation, two sources | CONFIRMED — `CP-19`; blueprint §11 Figure 6 |
| `BR-CWP-068` | Lands `awaiting_review`, on no bill until a clerk clears it | CONFIRMED — `CP-19` |
| `BR-CWP-069` | A later real read supersedes it and the customer is not charged twice | CONFIRMED — blueprint §11 Figure 6 |
| `BR-CWP-070` | A failing reading is **not refused** — it is shown what it implies and may be sent anyway | CONFIRMED — blueprint `P21` |
| `BR-CWP-074` | A reading is ACCEPTED, then validated, then flagged twice — a validation flag only when the check objects, a provenance flag on every customer reading | **CONFIRMED 2026-09-04** — `OQ-1393` closed, option (b) plus the provenance requirement. ⚠ Needs a FOURTH `meter_source`; B2 names three (`DEF-CWP-4194`) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Submit `153,300` two days after `153,040` | Accepted, lands `awaiting_review`, appears on `CWP-034` as *"You sent it in · awaiting review"* |
| TC-2 | Submit `158940` | ⚠ Warned: *"that is 5,900 gallons in two days — about **nineteen** times your usual"*, and **it can still be sent** |
| TC-3 · **negative** | The submitted `158940` | ⚠ Appears on **no bill** until a clerk clears it. Assert the next bill run excludes it |
| TC-4 · **negative** | A reading **lower** than the last one | The low threshold fires with a plain sentence; it is not silently accepted as a rollover |
| TC-5 | A genuine rollover | Handled by the existing rollover logic, ⚠ **not by a new branch in the portal** |
| TC-6 · **negative** | Submit outside the read window | Refused, naming the window |
| TC-7 · **negative** | A tenant with self-read **switched off** | The screen is unreachable **and** the endpoint refuses (`CR-068` `R8` — off for a new tenant) |
| TC-8 · **negative** | A later real read of `153,190` on the same period | ⚠ The submitted read is **superseded**, and **no bill charges both** |
| TC-9 · **tenant isolation** | Submit against a meter on another tenant's premises | Refused |
| TC-10 | A reading that PASSES validation | ⚠ **AMENDED 2026-09-06.** This read *"Call the straight-to-bill path → `NotImplementedError(\"OQ-1393\")`"* and there is no such stub to write: `OQ-1393` was ruled on 2026-09-04. A passing reading goes through **without** waiting for a clerk, and still carries the provenance flag that says the customer sent it |
| TC-11 | Attach a photo | ⚠ **Held — consumer upload is a signed deferral** (PO 2026-08-08, DF-4; `CR-068` §2b; `US-CWP-064`): the `PhotoPicker` renders its sentence and **no file input**, and a posted file is refused. After a re-sign: stored through the existing document store with its allow-list, and NO malware scan (SUPERSEDED (PO 2026-09-22 / 2026-09-23 → no malware scan on upload), `DEF-SHL-6347`) — *a read with a picture is one a clerk can settle in seconds instead of scheduling a visit*, which is the case for the re-sign (this row read as built until 2026-09-03 — `DEF-CWP-3611`) |

**4 · Test Data** — Meter *Water · front · serial `88-40219`*. Last reading `153,040` on
31 Aug. Expected now about `153,300`. Daily average `155 gal`. Submitted high reading
`158940` → `5,900 gal` in two days ≈ **19×** usual. Read window open until 6 September.
Superseding real read `153,190`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Which meter | CWP-035 | prototype-extracted | `asset` assigned to the unit | uuid FK | user-input | ⚠ Shown by **serial**, never by id |
| Date read | CWP-035 | prototype-extracted | `meter_read.read_on` | date | user-input | Within the window |
| The dial figure | CWP-035 | prototype-extracted | `meter_read.value` | numeric | user-input | ⚠ Through the **existing** validation service |
| Photo | CWP-035 | prototype-extracted | **none until the upload deferral is re-signed** (then `meter_read.evidence_document_id`) | uuid FK | user-input | ⚠ No route, no control — a held picker with its sentence (`DEF-CWP-3611`) |
| Source | — | GAP | `meter_read.source = portal` | enum | system-derived | New column |
| Review state | — | GAP | `meter_read.review_state` | enum | system-derived | `awaiting_review` on arrival |

**6 · Acceptance** — **Given** a customer standing at their meter with the window open,
**when** they send a figure nineteen times their usual, **then** they are told what it
implies, may send it anyway, it lands awaiting review, and no bill charges it until a
clerk clears it — and a later real reading supersedes it without charging both.

**7 · Finance Calculation** — N/A directly. ⚠ **But this is a route into billing**, so
the story is only done when a test proves a superseded submitted read is excluded from
the bill run. That is the finance-relevant assertion.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-1393` | Does a customer-submitted reading go straight onto a bill, or wait for review? | ~~`CP-19`, this story~~ — blocks nothing | Product Owner | **CLOSED 2026-09-04 — option (b)**, plus a provenance flag on every customer reading. See §1 |

---
id: US-CWP-043
epic: EP-CWP-08
module: portal
screens: [CWP-037]
wave: 2
status: ready
blocked_by: []
depends_on: [US-CWP-023]
journeys: [J36]
rules: [BR-CWP-073]
golden_tests: []
finance_calc: none
---
### US-CWP-043 — Meters and equipment at the property

**1 · Details** — As **a customer**, I want **to know which meter is mine**, so that **I
can read the right one and tell you when something is damaged**.

Equipment, serial, where it is fitted, when it was fitted, last read, status. A note:
*something damaged, buried or leaking? Tell us rather than touching it — the meter
belongs to the utility.*

⚠ **A SMALL SCREEN THAT ANSWERS A REAL QUESTION.** Assets, sub-meters and behind-the-meter
devices are already modelled with their serials, locations and maintenance history — **and
a trash cart is genuinely one of them**, because some services are billed on equipment at
the unit rather than on any reading.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-073` | Equipment is what unmeasured services are billed on | CONFIRMED — blueprint `P19`, `P23` |
| B14 rule 31 | Shown by **serial**, never by database id | CONFIRMED — B14 |
| — | The customer is told not to touch it, and given a reporting route | CONFIRMED — blueprint `P23` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | A property with three items | Water meter `88-40219`, refuse cart `C-11840`, backflow device `BF-2210`, each with where and status |
| TC-2 | The refuse cart | Listed as equipment. ⚠ It has **no last read** and that cell is empty, not zero |
| TC-3 | The backflow device | Reads **TEST DUE NOV** from the existing maintenance cadence |
| TC-4 · **negative** | A sub-meter belonging to another unit | ⚠ Absent. Only equipment assigned to **this** unit |
| TC-5 · **negative** | Any identifier on screen | ⚠ A **serial**, never a row id |
| TC-6 · **tenant isolation** | The list with a Pine Hill session | Pine Hill assets only |
| TC-7 | *Report a problem* | Routes into the request surface, pre-filled with the equipment |
| TC-8 · **negative** | A property with no recorded equipment | An empty state, not a blank table |

**4 · Test Data** — Water meter `88-40219`, front boundary box, fitted Mar 2021, last
read 31 Aug 2026, IN SERVICE. Refuse cart `C-11840`, rear alley, fitted Jan 2024, no last
read, IN SERVICE. Backflow device `BF-2210`, front boundary box, fitted Mar 2021, no last
read, TEST DUE NOV. A sub-meter on unit B that must not appear.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Equipment | CWP-037 | prototype-extracted | `asset.kind` | enum | reference-data | Plain English |
| Serial | CWP-037 | prototype-extracted | `asset.serial` | text | system-derived | ⚠ The visible identifier |
| Where fitted, Fitted | CWP-037 | prototype-extracted | `asset_assignment.location`, `fitted_on` | text, date | system-derived | — |
| Last read | CWP-037 | prototype-extracted | latest `meter_read` | date | computed-display | Empty for unread equipment |
| Status | CWP-037 | prototype-extracted | `asset.status` + maintenance cadence | enum | computed-display | *TEST DUE NOV* from the cadence |

**6 · Acceptance** — **Given** a property with a meter, a cart and a backflow device,
**when** the equipment screen opens, **then** all three are listed by serial with where
they are fitted, the cart has no last read, the device shows its test due, and nothing
belonging to another unit appears.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-CWP-044
epic: EP-CWP-08
module: portal
screens: [CWP-036]
wave: 0
status: blocked
blocked_by: []
depends_on: [US-CWP-040]
journeys: []
rules: [BR-CWP-093]
golden_tests: []
finance_calc: none
---
### US-CWP-044 — Your usage looks high

**1 · Details** — As **a customer**, I want **to be told when my usage changes**, so that
**a leak does not become a bill**.

*"Since 25 August you have used about twice your normal daily amount."* A fourteen-day
daily chart with the change marked. Then what it usually is — a running toilet at 4,000
gallons a month, an irrigation timer, a dripping tap, visitors. Then two routes: send a
reading, ask for a visit.

⚠ **BLOCKED, AND NOT ON A QUESTION — ON A MISSING TRIGGER.** *"This alert has no trigger
in the product today. The event is declared in the notification catalogue and nothing
ever fires it."* The only comparison the product makes is a **read-validation threshold**
that flags a reading for a clerk, **which is a different question from "this household's
use has changed".**

⚠ **AND FIRING IT NEEDS READINGS MORE OFTEN THAN ONCE A MONTH.** On a monthly-read utility
**this alert can only ever fire at billing time**, and the wording has to be honest about
that. **The blueprint calls it a good candidate to defer until reads arrive more often.**

**Drawn because the event already exists in name and needs a decision, not because it is
nearly built.** Wave 0 — deliberately unscheduled.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-093` | With no alert, there is no screen and no link | CONFIRMED — blueprint §16 |
| — | A trigger, a baseline and a cadence | **PROPOSED and unscheduled** — none exists. `CP-29` |
| — | ⚠ The alert must never be worded as though it fires daily on a monthly-read utility | CONFIRMED — blueprint `P22` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Seed an alert directly | The screen renders with the fourteen-day chart and the change marked at 25 August |
| TC-2 · **negative** | ⚠ No trigger exists | Assert **nothing fires it**. This test documents the gap rather than passing over it |
| TC-3 · **negative** | A monthly-read account | ⚠ The copy must not promise daily detection. Assert the wording names billing time |
| TC-4 · **negative** | The read-validation threshold fires | ⚠ It must **not** produce this alert. They are different questions and conflating them is the defect |
| TC-5 · **negative** | No alert on the account | The screen and its message row are absent |
| TC-6 · **tenant isolation** | A seeded alert | Scoped to one tenant |

**4 · Test Data** — Fourteen days of daily use with the step at 25 August, roughly
doubling from about `155 gal` to about `310 gal`. A monthly-read account for TC-3.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Daily series | CWP-036 | prototype-extracted | daily consumption | numeric + unit | computed-display | ⚠ Requires sub-monthly reads |
| Baseline | CWP-036 | GAP | **this account's own history** | numeric | computed-display | ⚠ **Not** a validation threshold |
| Trigger, cadence | — | GAP | **none** | — | — | ⚠ Unscheduled |

**6 · Acceptance** — **Given** an alert seeded directly, **when** the screen opens,
**then** it charts fourteen days against the account's own history with the change marked
— and no code path in the product fires it, which this story records rather than hides.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None to route. ⚠ **This is a scope decision, not a question**:
whether to defer until reads arrive more often. Recorded here and in the module overview
rather than put to the Product Owner as though we could not decide it ourselves.

# B19 · CR-031 — THE SERVICE REQUEST CAPTURE FORM (REQ-03)

**Status:** DRAFT — extracted from PO screenshots, 2026-08-24. **Nothing in this
document decides an open question.**
**Source:** ten screenshots of `REQ-03.1` … `REQ-03.6`, provided by the PO in the
working session of 2026-08-24, against `claude.ai/design` build
`SMARTBillHub.dc.html`. ⚠ **Those screenshots are NOT in the repo** — this text is
the only record of them here, which is the DEF-631 / decision-D5 hazard again.
**Read with:** `12-governance/11-change-requests.md` → **CR-031** (the PO's written
spec, verbatim) and `04-docs/02-decisions/18-cr030-onboarding-design.md` §5.3.

---

## 0 · Why this is a separate document

CR-031 captured the PO's SR workflow **in words**. These screenshots are the same
feature **drawn**, and they do not agree with the words in four places. Recording
them together in B18 would bury the disagreements inside a 2,400-line document
that is already being corrected in place. They are here, in one place, so the W4
lane reads the conflicts before it reads the layout.

**The wizard is `REQ-03`, six steps, and it is the STAFF capture form** — the
banner reads `CAPTURING FOR A CUSTOMER` and names the clerk. `See the customer's
view` in the same banner implies the applicant-facing render (B18's **S85**) is
the SAME object with a different chrome, not a second form.

---

## 1 · The frame, on every step

| Element | Content |
|---|---|
| Banner | `CAPTURING FOR A CUSTOMER` · **channel dropdown** · `Billing clerk: A. Reed` · `See the customer's view` |
| Channel values seen | `Customer portal` · `Physical form` |
| Kicker | `NEW SERVICE REQUEST` |
| Title | `Capture a service request.` |
| Sub-line | *"Five steps · the request is created and numbered when the fee is collected."* ⛔ **wrong twice — see §6** |
| Header action | `Save as draft` (secondary, top right) |
| Stepper | `1 Customer` · `2 Connection` · `3 Addresses & property` · `4 Documents` · `5 Fees` · `6 Check & submit` |
| Footer | `Cancel` / `← Back` · *"Step N of 6 · nothing is created until you submit."* · next-step primary naming the NEXT step |
| Screen ids | `REQ-03.1` … `REQ-03.6` |

**The footer primary names its destination** (`Connection →`, `Addresses &
property →`, `Fees →`, `Check & submit →`), never a generic *Next*.

---

## 2 · Step 1 · Customer `REQ-03.1`

* **`Applying as`** — segmented control, two values: **`A person`** · **`A business`**.
* `Full name` **\*** · `Email` **\*** · `Phone` **\*** — three across.
* **`Social Security Number`** **\*** — with help text, quoted exactly:
  > *"Stored encrypted and shown to staff as the last four digits only. Used to
  > match you against any account you have held before."*
* **`Co-applicant`** panel, badge `Optional · contact only`:
  > *"A co-applicant can be contacted about this request and the account. They
  > carry no liability for the bill, so we do not need their SSN or their
  > documents."*
  Checkbox: `Add a co-applicant`.

⛔ **THE SSN IS THE MOST CONSEQUENTIAL THING IN THESE SCREENSHOTS.** It is a
required field, it carries an on-screen promise of encryption, and it is a
government identifier. See **§6.1** — it is a blocker, not a detail.

⚠ **`A business` is drawn and its consequence is not.** A business has no SSN; it
has an EIN/TIN. The screenshots only ever show the person branch, so what the
identity field becomes for a business is **not recorded and must not be guessed**.

---

## 3 · Step 2 · Connection `REQ-03.2`

| Field | Value shown | Help |
|---|---|---|
| `Customer category` **\*** | `Residential` | *"A home somebody lives in"* |
| `Sub-category` **\*** | `Single family` | *"5 options for residential · sets which plans are eligible"* |
| `Connection date` **\*** | `09/15/2026` | *"When they want service to begin."* |

**Seven category chips** below the dropdown, the chosen one in the accent:
`Residential` · `Commercial` · `Industrial` · `Agricultural` · `Institutional` ·
`Municipal` · `Builder or developer`. ⛔ **Four are seeded — see §6.3.**

**`UTILITY SERVICES REQUESTED`** — *"Everything we supply is listed. Step 3
confirms what is actually available at the address given."*

**Ten cards**, badge letter + name + description, two selected:

| Badge | Name | Description |
|---|---|---|
| **E** | Electricity ✅ | Power to the property |
| **W** | Water ✅ | Mains water supply |
| **G** | Gas | Mains gas supply |
| **S** | Sewer | Waste water — usually billed with your water |
| **T** | ~~Rubbish collection~~ → **Trash** | Bins collected from the property. ⚠ **STAMPED 2026-08-24 (DEF-636, BR-RAT-118): r10 draws `Rubbish collection` and the product calls it `Trash`. PO verbatim: *"We call trash"*. The drawing is kept struck through rather than deleted, so the divergence stays readable.** |
| **D** | Storm water | Drainage from hard surfaces |
| **O** | Solar | You generate power and sell what you do not use |
| **B** | Broadband | Internet over our network |
| **H** | Heating | Heat supplied from a shared plant |
| **Y** | Battery | You store power at the property |

✅ **The ten match CLAUDE.md's ten exactly.** ⛔ **Four of the badge letters do not
match what the product ships, and one name does not either — §6.4, §6.5.**

---

## 4 · Step 3 · Addresses & property `REQ-03.3`

**`Service address`**, right-labelled *"Where service is needed"*:
`Address` **\*** = `14 Willow Bend` · `Unit, flat or suite` (*"If there is one"*).

**The unresolved-address branch**, drawn in an accent-bordered panel:
> *"We don't have this address on record yet. Tell us a bit more:"*
> `Plot or parcel number` (*"If known"*) · `What is being built` (*"A house, a
> shop, 25 flats…"*)

**`CHECK` callout:**
> *"We do not serve this address yet, so we cannot confirm which of the requested
> services are available. That is settled at review."*

**`Billing address`** — checkbox `Same as the service address` (checked).

**`Property details`** — six radios:

| Option | Description |
|---|---|
| `Standalone · owner occupied` ✅ | The applicant owns and lives in it |
| `Rental · tenant applying` | They rent it; the landlord owns it |
| `Rental · landlord applying` | They own it and rent it out |
| `Multi-unit building` | Several units under one premise |
| `Under construction` | Not yet occupied |
| `Vacant land` | Nothing built there yet |

⚠ **THIS RECONCILES CR-031 WITH B18's BR-CUS-071, and it is good news.** B18
proposed *"the system classifies"*; CR-031 ruled *"the clerk decides"*. The
screens show **both, doing different jobs**: the system RESOLVES the address and
adapts the form (and step 6 records *"What the lookup found"* on the request), and
the clerk DECIDES the outcome afterwards. They are not in conflict — the
resolution is evidence, the decision is a judgment. **BR-CUS-071 as worded is
still wrong** (it says the system decides move-in vs new connection vs refusal)
and CR-031 §4 already records that.

---

## 5 · Step 4 · Documents `REQ-03.4`

Panel `Documents`, right-labelled **`2 needed · 1 optional`** — a computed count.

| Document | Badge | Description |
|---|---|---|
| `Photo ID` | **Needed** | Driving licence, passport or state ID |
| `Proof of address` | **Needed** | A recent bill or letter addressed to the applicant |
| `Anything else` | **Optional** | Whatever the applicant brought that helps |

Each is a file input. **`NOT BLOCKING` callout:**
> *"A missing document does not stop the request being created. It is verified at
> review, and the request shows as waiting on documents until then."*

✅ **THIS ANSWERS HALF OF OQ-351** — the *behaviour* is now ruled: a missing
document never blocks creation; it is verified at review and the request sits in
`waiting on documents`. That is a rule, and it is exactly the `WAITING ON` column
B18 §5.3.2 draws on the list.
⛔ **The other half is still open:** three documents are drawn where B18 designed
eight types, and nothing on screen says whether the list is **tenant-configurable
or fixed**. `2 needed · 1 optional` being computed hints at a configured list but
does not establish one. **OQ-351 stays open.**

---

## 6 · Step 5 · Fees `REQ-03.5`

Panel `Fees`, badge **`$130.00 to invoice`**.

| Fee | Code | Basis | Rate | Qty | Amount |
|---|---|---|---:|---:|---:|
| Application processing fee<br>*"From the residential category chosen at step 2"* | `CC-REQFEE` | per request | $25.00 | 1 | **$25.00** |
| Expedited handling | `CC-EXPED` | per request | $60.00 | 1 | **$60.00** |
| Meter test on request | `CC-METERT` | per meter | $45.00 | 1 | **$45.00** |
| | | | | **`To collect`** | **$130.00** |

`25.00 + 60.00 + 45.00 = 130.00` ✅ — the screen's arithmetic ties.

Add row: `Choose a fee…` + `+ Add to the list`, with a green confirmation
*"✓ Meter test on request added to the list · total is now $130.00"*. Each row
carries a `⊘` glyph (remove or waive — **not determined from a picture**).

> *"Fees are charged for processing and are not refunded if the request is
> refused. They are separate from any connection quote, which is raised after
> review."*

### 6a · `When is it being paid?` — two branches, and they differ on when the SR exists

**`Collect later`** · badge **`Invoice on creation`**
> *"The request is created now and the fee is raised as an invoice. Review cannot
> approve it until the fee is settled."*
`Due by` **\*** = `09/07/2026` · `How will they pay` = `Invoice sent by email`
> **`FEE OUTSTANDING`** — *"The request will show $130.00 outstanding until it is
> paid, and the review step lists the unpaid fee as a blocking condition. Nothing
> is refused — it simply cannot be approved yet."*

⛔ **THE LAST SENTENCE OF THAT QUOTE IS SUPERSEDED, 2026-09-21** — PO, verbatim:
*"make application fees optional - so that we can approve it"*. The request DOES
show the $130.00 outstanding and the review step DOES list it; what is no longer
true is that it *"cannot be approved yet."* The quote is left standing because
it is the design's own words and this file is the record of them — the amendment
is `BR-CUS-090` clause (1), dated, and it is what a lane builds from.

⛔⛔ **SUPERSEDED 2026-09-23 — THE FEE GATES APPROVAL AGAIN (`OQ-CUS-12617` CLOSED, `DEF-CUS-6420`).** PO, verbatim: *"we already told you - either fee is paid or waived - no other condition"*. Approve waits until the application fee is **paid in full or waived**; a part payment holds it on the REMAINDER (quoted $130.00, taken $25.00 → *✗ Fee · $105.00 unpaid*, Approve off). A utility with no fee lines is untouched, and the counter still accepts a short payment and never refuses — the desk half of `BR-CUS-090` stands. The paragraph above is kept as the record of 2026-09-21.

**`Collect now`** · badge **`Ready to collect`**
> *"The fee is taken before the request is created, and the receipt number appears
> on the confirmation."*
`How is it being paid?` **\*** — four radios:

| Option | Description |
|---|---|
| `Card` | Taken now, at the counter or in the portal |
| `Cash` ✅ | Counter only · a receipt is printed |
| `Cheque` | Recorded now, cleared later |
| **`Waive the fee`** | **A reason is required and recorded against your name** |

✅ Waiver-with-a-reason, as B18 §4.6 proposed, and the reason is attributed to the
clerk.

---

## 7 · Step 6 · Check & submit `REQ-03.6`

Title `Check and submit`, sub-line **"2 fields left blank. None of them stop the
request being created."** — a computed count that repeats step 4's posture.

Every section carries an `Edit step N` link back. Sections and badges seen:
`Customer` · `Co-applicant` (badge `None added`) · `Connection` · `Service
address` (badge **`Not on record`**) · `Billing address`.

Notable rows:
* **`Social Security Number` → `••• ••• • 4471 · stored encrypted`** — the
  last-four render, and the encryption claim repeated at the point of submission.
* `Utility services requested → Electricity, Water`
* **`What the lookup found` → *"We don't have this address on record yet…"*** —
  **the resolver's verdict is STORED ON THE REQUEST**, not merely rendered.
* `Plot or parcel → Not supplied` · `What is being built → Not supplied` — blanks
  are shown as blanks, never omitted.

---

## 8 · WHAT THESE SCREENS CONTRADICT — every one filed, none resolved here

| # | Conflict | Filed |
|---|---|---|
| 8.1 | **The SSN promises encryption the product cannot deliver.** OQ-016 is CLOSED — *"app-layer encryption for high-sensitivity columns"* (PO R6) — and there is **no encryption helper anywhere in `06-backend/`**. `apps/tenancy/services.py` records the precedent in its own docstring: *"ein stored as plain 9 digits for now — the OQ-016 ruling (app-layer encryption)"*. Building this screen as drawn puts *"stored encrypted"* in front of a customer over a plaintext column. ⛔ **BLOCKER.** | DEF-632 |
| 8.2 | **The header says five steps; the stepper, the footers and the screen ids all say six.** | DEF-633 |
| 8.3 | **The header says the request is *"created and numbered when the fee is collected"* — true for `Collect now`, FALSE for `Collect later`,** whose own copy says *"the request is created now and the fee is raised as an invoice"*. And every footer says *"nothing is created until you submit."* Three statements, one screen, about the moment an SR number exists. **This decides idempotency, drafts, and what an invoice is attached to.** ⛔ **BLOCKER.** | DEF-634 |
| 8.4 | **Seven customer categories are drawn; four account types are seeded** (`residential`, `commercial`, `industrial`, `government`). `Agricultural`, `Institutional`, `Municipal` and `Builder or developer` do not exist, and `government` maps to none of them cleanly. B2 r5 #12's four are SIGNED. | DEF-635 |
| 8.5 | **Four service badge letters disagree with what ships.** Prototype: `D` storm water, `O` solar, `H` heating, `Y` battery. Shipped `SERVICE_BADGES`: `St`, `So`, `Th`, `Ba` — two-character, added by OQ-273 *after* r10 was drawn. The Accounts list (CR-030 W2) already renders the shipped letters, so the two screens would label the same service differently. | DEF-636 |
| 8.6 | ✅ **CLOSED 2026-08-24 — `Trash`.** PO verbatim: *"We call trash"*. Signed as **BR-RAT-118**, which closes the badge half (`St`/`So`/`Th`/`Ba`, not r10's `D`/`O`/`H`/`Y`) on the same sentence and states the general form: where r10 and the product NAME the same thing differently the product wins; where they LAY OUT or SEQUENCE it differently r10 still wins. Nothing divergent ever shipped — the code already imported `serviceBadge()` and rendered `rating.service.<code>`. | DEF-636 → **CLOSED** |
| 8.7 | **`A business` is drawn with no business identity field.** SSN is required and a business has none. | recorded in §2 |
| 8.8 | **The `⊘` glyph on a fee row is not determinable from a picture** — remove, or waive-with-reason? B18 §4.6 says waivers need a reason; the `Waive the fee` payment option already provides one path. | recorded in §6 |

---

## 9 · What is UNBLOCKED and can be built now

Everything that does not touch the SSN, the numbering moment, or the category
vocabulary:

* the six-step frame, stepper, footers, `Save as draft`, and the
  name-your-destination primaries;
* step 1 minus the SSN field — name, email, phone, `Applying as`, the co-applicant
  panel;
* step 2's connection date, the ten service cards **using the SHIPPED badge
  letters** until 8.5 is ruled;
* step 3 entire — service address, the unresolved-address branch, the `CHECK`
  callout, billing-address-same-as, and the six property types;
* step 4 entire — the three documents and the **NOT BLOCKING** rule, which is
  ruled behaviour;
* step 5's fee table, add-a-fee, the two payment-timing branches and the four
  payment methods — **as a quote only**; B18 §4.6's *"never posts to the ledger"*
  stands until the numbering moment is settled;
* step 6 entire — the review, the `Edit step N` links, the blank-count sub-line,
  the stored `What the lookup found`.

**Not buildable until ruled:** the SSN field (8.1), whatever depends on when the
number is allocated (8.3), and the category list (8.4).

---

## 10 · What this document does NOT do

It does not resolve any open question, ratify any rule, or assign screen ids
beyond the `REQ-03.n` the prototype itself carries. It does not renumber
B18 §6.4's proposals — that was done separately (`BR-CUS-084…089`). It records
what was drawn and what that contradicts, so the W4 lane starts from evidence
rather than from a summary of a picture nobody else can open.

---

## 11 · Step 6 continued, and the confirmation `REQ-03.sent`

*Added 2026-08-24 from four further screenshots, same session.*

### 11.1 · The rest of `REQ-03.6`

| Section | Badge | Rows |
|---|---|---|
| `Property` | — | `Property type` → *Standalone · owner occupied* · **`What that means`** → *"The applicant owns and lives in it"* |
| `Documents` | `2 needed · 1 optional` | Photo ID → **`Needed · attached`** · Proof of address → **`Needed · attached`** · Anything else → **`Optional · not attached`** |
| `Fees` | **`$130.00 to collect`** (green) | `Lines` → *Application processing fee, Expedited handling, Meter test on request* · `Total` → **$130.00** · **`When`** → **"Collected before the request is created"** · `Method` → **Cash** |

⚠ The property type's **description is echoed on the review**, not just its label —
so the wording *"The applicant owns and lives in it"* is a stored or derived fact
the review renders, not decoration.

### 11.2 · `REQ-03.sent` — the confirmation

* Kicker `SERVICE REQUEST CREATED`, then the number, very large, in the accent:
  **`SR-26-0056`**
* *"Quote this number whenever you contact us about this request."*

**`Form fee`** panel, badge **`Collected`** (green):

| Row | Value |
|---|---|
| `Amount` | **$25.00** |
| `Method` | Cash |
| **`Receipt`** | **`RCP-26-4471`** |

**`Acknowledgement email`** panel, badge **`Sent automatically`**:

> **Your service request SR-26-0056**
> *"We have received your application for service at 14 Willow Bend. Your
> reference is SR-26-0056. We will review it within two working days and contact
> you if anything is missing. **Nothing is charged and no service changes until we
> have confirmed what is needed.**"*
> — footnote: *"Sent to the email captured at step 1 the moment the request was
> created."*

**`WHAT HAPPENS NEXT`**, four lines, verbatim:
> · A billing clerk reviews the request and verifies the documents.
> · **We search for any account you have held before, and check for anything
>   outstanding on it.**
> · We decide what this becomes — a new connection, a move-in, **or one of the
>   other job types**.
> · If there are charges to pay, we send a quote before any work starts.

Actions: `Print receipt` · `Capture another` · **`Open the request`** (primary).

### 11.3 · What these four screens SETTLE

✅ **BR-CUS-079 is confirmed as drawn.** The acknowledgement is sent
`Sent automatically`, to the email captured at step 1, *"the moment the request
was created"* — exactly the PO's ruling, and it carries the SR number.

✅ **DEF-634 is resolved FOR THE `Collect now` BRANCH.** Step 6 states
*"Collected before the request is created"* and the confirmation shows the number
existing beside a collected fee. Order: **collect → create → number → email.** The
header sub-line is true here. ⛔ `Collect later` is still unreconciled — its own
copy says the request is created first.

✅ **Number formats:** `SR-26-0056` for requests, `RCP-26-4471` for receipts.

⚠ **The request fans out to MORE THAN THREE outcomes.** *"a new connection, a
move-in, **or one of the other job types**"* is customer-facing copy, and CR-031
named three (move-in · new connect · refusal). This supports B18 §5.3's finding
that the `TYPE` column draws five. **The number of outcomes is still unruled.**

⚠ **A prior-account ARREARS CHECK is new.** *"We search for any account you have
held before, and check for anything outstanding on it."* The identity match was
already designed (BR-CUS-089); checking the OLD account's balance at review is
not, and it has obvious consequences for what a clerk may refuse on.

### 11.4 · What these four screens CONTRADICT

| # | Conflict | Filed |
|---|---|---|
| 11.a | ⛔ **THE FEE AMOUNTS DISAGREE — $130.00 vs $25.00.** Step 5 totals `$130.00` and step 6 repeats *"$130.00 to collect · Collected before the request is created · Cash"*. The confirmation's `Form fee` reads **Amount $25.00, Collected**, receipt `RCP-26-4471`. $25.00 is `CC-REQFEE` ALONE; the $60.00 expedited handling and $45.00 meter test have vanished. **A customer paid cash at a counter — the screens do not agree whether they handed over $130 or $25**, and one receipt number is printed for whichever it was. | DEF-637 |
| 11.b | ⛔ **THE ACKNOWLEDGEMENT EMAIL TELLS THE CUSTOMER *"Nothing is charged"* ON A SCREEN SHOWING THEIR CASH FEE COLLECTED.** Customer-facing, provably false at the moment it is sent, and it is the FIRST thing the applicant receives. | DEF-637 |
| 11.c | The receipt number `RCP-26-4471` ends in the same four digits as the SSN `452-88-4471` shown two steps earlier. Prototype copy-paste, almost certainly — but a receipt number that echoes an identifier's last four would be an information leak if it were real, and a seed lane copying these fixtures would reproduce it. | recorded here |

---

## 12 · `REQ-01` — the Requests tab, and `REQ-02` — the request detail

*Added 2026-08-24 from a further batch, same session. The document is now the
whole request surface: the list, the detail, the capture wizard, the receipt.*

### 12.1 · `REQ-01` — the list

✅ **THE EIGHT-TAB STRIP CR-030 W2 BUILT IS CONFIRMED, WITH SUPERSCRIPT COUNTS:**
`Accounts · Requests⁴² · New Connect⁷ · Move-ins³ · Move-outs⁵ · Transfers² ·
Disconnects⁹ · Imports`. Header carries `Export` and `+ New request`.

**KPI strip**, five, exactly as B18 §5.3.1 designed it: `OPEN 42` *not yet turned
into a job* · `WAITING ON CUSTOMER 6` *documents or a deposit* · `OLDEST WAITING
15 days` *SR-26-0039 · waiting on documents* · `APPROVED, NOT STARTED 4` *no job
opened yet* · `REFUSED THIS MONTH 3` *with a reason on record*.

Search *"Request #, name, address, phone, or email…"* · segments
`All` · **`Open`** · `Waiting on customer` · `Approved` · `Closed` · `+ Filter` · column
selector. Columns `REQUEST · TYPE · APPLICANT · ADDRESS · RECEIVED · AGE ·
WAITING ON · STATE`. Pager *"Showing 1–8 of 42 (filtered from 118)"*. Footnote
*"Sorted by age, oldest first — the oldest thing waiting is the thing to look
at."*

| Request | Type | Applicant | Address | Age | Waiting on | State |
|---|---|---|---|---|---|---|
| SR-26-0039 | `MOVE-IN` | Osei, Grace | 3450 Oak Ridge Dr | **15d** | documents | `More info needed` |
| SR-26-0043 | `NEW CONNECTION` | Ridge Property LLC | 500 Main St · 25 units | **11d** | — | `In fulfilment` |
| SR-26-0047 | `TRANSFER` | Park, Jenna | 901 Hillside → 2201 Cedar | 5d | — | `Under review` |
| SR-26-0042 | `NEW CONNECTION` | Okonkwo, David | 14 Willow Bend (new plot) | 4d | payment | `Under review` |
| SR-26-0048 | `DISCONNECT` | Ridge Coffee Co. | 500 Main · 200 | 3d | third party | `Under review` |
| SR-26-0045 | `MOVE-IN` | Kwan, Michael | 88 Pine Vista | 2d | — | `Approved` |
| SR-26-0044 | `MOVE-IN` | Alvarez, Rosa | 1408 Elm St · Unit A | 1d | — | `Submitted` |
| SR-26-0046 | `MOVE-OUT` | Thompson, R. | 88 Pine Vista | 0d | scheduled date | `Submitted` |

✅ **THE AGE THRESHOLD IS SEVEN DAYS — PO ruling 2026-08-25, closing D4.**
`15d` and `11d` are accent; `5d` and below are not, so the drawing bounded it
to **6–11 days** and nothing derived it. The PO chose **7 — one week**, which
B18 had proposed and which no document had authority to confirm. → **BR-CUS-106**.
Both drawn rows keep their meaning under it.

### 12.2 · `REQ-02` — the detail

Back link `← Requests`. Header: `REQUEST SR-26-0039` + `More info needed` + chip
**`NOT YET CLASSIFIED`** · `Osei, Grace` · *"3450 Oak Ridge Dr · served, and the
unit is vacant"* · *"Received Aug 08 by walk-in · logged by A. Reed"*.

Three metric columns: `AGE 15 days` *Service starts Sep 15* · `QUOTE —` *unpaid* ·
`WAITING ON Documents` *since Aug 21*.

Actions: **`Decide what this is →`** (primary) · `Ask for more` · `Refuse`
(danger). Below: **`Save & exit`** and **`Park — waiting on ▾`**, with
*"A request rarely settles in one sitting. Leave it and it keeps its place."*
Seven-glyph icon rail. Six tabs: `Applicant · Location & services · Documents ·
Fees · Decision · History`.

**The Park modal** — *"Park this — what are you waiting for?"*: `Waiting on` **\***
(dropdown) · `Note` (*"Anything the next person needs to know"*) · `Remind me on`
(date) · *"Everything entered stays. The request shows as waiting in the list, and
the note goes on its timeline."* · `Cancel` / `Park ✓`.

✅ **THIS IS THE PO'S SAVE-AND-EXIT REQUIREMENT, DRAWN — and it is TWO controls,
not one.** `Save & exit` leaves quietly; `Park` records WHAT is being waited for,
a note and a reminder date, and surfaces on the list's `WAITING ON` column. CR-031
statement 9 asked for save-and-exit; the prototype answers with both.

### 12.3 · The six detail tabs

**Applicant** — Name · Phone · Email · **`ID` → `•••• ••••• 4471`** · Language ·
**`Acting for` → Self** · **`Date of birth` → Mar 1988** · Postal address ·
`Person or company` → Person. Beside it **`Customer match`** badged **`Strong`**:
matched customer `CUS-00218`, **`Matched on` → ID number and date of birth**,
`Accounts held` → 1 closed account, **`Deposit available` → $153.50 on the closed
account**, and *"Only a strong match may move money. This one qualifies, so the
$153.50 deposit can be carried across."*

✅ Confirms **BR-CUS-089** (money moves only on `strong`). ⚠ **Two fields the
capture form never asked for: `Date of birth` and `Acting for`** — and the match
is made ON the date of birth, so it is not optional. ⚠ The detail labels it **`ID`**,
not `Social Security Number`.

**Location & services** — `Address as given` → *14 Willow Bend, Springfield* ·
**`Resolved to` → No premise record** · **`Consequence` → This becomes a new
connection** · `Plot reference` → PL-2026-0884 · `Property type` → Single
residential · `Units` → 1. Footnote: *"The address as the applicant gave it is
kept verbatim and never overwritten by the resolved record."*
✅ **BR-CUS-070 confirmed as drawn.**

**Documents** — *"2 of 3 verified"*; columns `DOCUMENT · WHAT IT PROVES ·
UPLOADED · VERIFIED` with `View / Verify / Reject`. A **fourth document type**
appears: **`Deed or site plan` — "Shows they may build on the plot"**, `Not yet
checked`. `Attach another` accepts anything sent later.
> **`BLOCKING`** — *"1 document still to verify. Approval is blocked until
> somebody checks each one — attaching a file is not the same as verifying it."*

✅ **THIS COMPLETES OQ-351's BEHAVIOUR HALF, and it is TWO GATES, not one:**
attaching never blocks CREATION (REQ-03.4); **verifying blocks APPROVAL**. And the
document list is **contextual** — a new connection asks for a deed that a move-in
does not — which is evidence for a configured rather than fixed list, though
still not proof of *tenant*-configurable. **OQ-351 stays open on that half.**

**Fees** — `Application fees` badged `Outstanding`: ONE line, `Application
processing fee · CC-REQFEE · $25.00 · Outstanding · Invoiced · —`, with *"Taken at
capture, for processing the application. Not refunded if the request is
refused."* Then `Connection quote` badged **`Not raised`** — *"A quote is raised
after review, once you know what work the request actually needs. Nothing is
priced yet."*
> **`SEPARATE`** — *"The quote prices the work itself and is raised after review.
> It is not the application fee, and settling one does not settle the other."*

⚠ **THIS SHARPENS DEF-637 RATHER THAN CLOSING IT.** The detail shows **$25.00
only** — so the confirmation's $25 was right and the capture's $130 is the
outlier. But the capture form let a clerk add `Expedited handling` and `Meter test
on request` INTO the same `Fees` panel and totalled them as one figure to collect.
Either those two are quote lines that the capture step should not be collecting,
or the detail's `Application fees` panel is incomplete. **Still a ruling.**

**Decision** — the heart of it, and it matches CR-031 exactly:
* `Existing customer` badged `Nothing outstanding` — a search (*"by name, SSN,
  phone, email or account number"*), a result row `CUS-00907 · A-11024 · Active ·
  Nothing owed · STRONG account number · Linked ✓`, and **`CLEAR`** — *"Linked to
  CUS-00907 on a strong match, with nothing outstanding on A-11024. Nothing here
  blocks approval."* ✅ **The prior-account arrears check, drawn.**
* `Document verification` — the same three, with ✓ ⊘ ⊞ actions.
* **`What we know`**, right-labelled *"The application never asked what kind of
  job this is — that is decided here"*: `What they said` → *"I'm moving into
  somewhere"* · `What the address lookup found` → **"Served, and the unit is
  vacant"**.
* **`WHAT SHOULD THIS BECOME?`** — *"Nothing is preselected. Approving creates
  real service and real charges, so the decision is made deliberately."*

| Option | Badge | Reason given |
|---|---|---|
| New connection | `Not possible` | There is already a premise record at this address — service exists here |
| **Move-in** | **`Fits the evidence`** | The unit is served and vacant, so somebody is taking over service that already exists |
| Move-out | `Not possible` | The applicant holds no live account at this address, so there is nothing to close |
| Transfer | `Not possible` | A transfer moves a live account between two of your addresses. There is no live account here |
| Disconnect | `Not possible` | **A customer asking to end service is a move-out… A disconnect leaves the account open and accruing, and is only ever started by collections, never from a customer request** |

* `Conditions` *"4 of 5 conditions clear"* — ✓ `No blocking arrears` · —
  `Eligibility evidence` *None claimed — does not block* · and the refusal
  *"Cannot approve yet — documents verified: 2 of 3 — check the rest before
  approving."*
* `Commit` badged `Nothing picked` — *"Pick what this becomes before approving.
  Until then there is no job to start."* `Approve` · `Ask for more` · `Refuse`,
  with *"Refusing keeps the request and its reason on record. The chain ends at
  the application — no job is created and there is nothing to follow."*
* `Manual close` badged `Rarely needed` — *"A request closes on its own when the
  job it created finishes. Close it by hand only when the job will never run…"*
  Reason required.

**History** — `Add a note` badged **`Internal · never shown to the customer`**,
a note-type dropdown, then `History and notes` *"This request only · newest
first"* mixing `Note` and `System` rows, each stamped date · time · actor.

### 12.4 · What this batch SETTLES

| ✅ | |
|---|---|
| **FIVE outcomes, not three** | The decision offers New connection · Move-in · Move-out · Transfer · Disconnect, and the list's `TYPE` column draws all five. CR-031 named three; the confirmation hedged *"or one of the other job types"*. **This is the answer, and it is drawn twice.** |
| **The system suggests, the clerk decides** | *"Nothing is preselected"*, one option badged `Fits the evidence`, the rest `Not possible` **with a reason each**. Exactly CR-031's ruling and exactly what B19 §4 predicted. BR-CUS-071 as worded stays wrong. |
| **OQ-351's behaviour half, complete** | Attaching never blocks creation; **verifying blocks approval**. Two gates. |
| **BR-CUS-070 · BR-CUS-089 · the arrears check** | All three drawn as designed or ruled. |
| **Save-and-exit is TWO controls** | `Save & exit` and `Park — waiting on` (reason + note + reminder). |

### 12.5 · What this batch CONTRADICTS or leaves open

| # | Item | Filed |
|---|---|---|
| 12.a | ⛔ **A `DISCONNECT` REQUEST EXISTS IN THE LIST AND THE DECISION SAYS IT CANNOT.** `SR-26-0048 · DISCONNECT · Ridge Coffee Co.` sits in the Requests tab, while the decision panel says a disconnect *"is only ever started by collections, never from a customer request."* Both are drawn. One is wrong. | DEF-638 |
| 12.b | **Two applicant fields the capture form never collects — `Date of birth` and `Acting for`** — and the customer match is made ON the date of birth (*"Matched on: ID number and date of birth"*), so it is load-bearing, not decorative. | DEF-638 |
| 12.c | The detail labels the identifier **`ID`** where the capture form says **`Social Security Number`**. Given DEF-632, the generic label may be the safer one. | DEF-638 |
| 12.d | `AGE` accent threshold. ✅ **RULED 2026-08-25 — SEVEN DAYS. D4 IS CLOSED.** Put to the PO with the bound and the consequence — the drawing shows `15d` and `11d` accented and `5d` plain, so the line sat anywhere in 6–11 and nothing derived it — and the PO chose **7, one week**. → **BR-CUS-106**. The two drawn rows keep their meaning under it (11d still accents, 5d still does not), which is why 7 was the reading put first. | ✅ CLOSED → BR-CUS-106 |
| 12.e | The History tab shows *"Quote raised — 5 charge lines totalling —, unpaid"* — the total renders as a literal em-dash. | DEF-638 |
| 12.f | The `Location & services` tab shows `14 Willow Bend` while the header of the same request shows `3450 Oak Ridge Dr` — two different requests' data across tabs of one screenshot set. Prototype artefact, recorded so a lane does not model it as one record. | recorded |

---

## 13 · ⚠ WHAT THE PO RULED ON 2026-08-24, AND WHICH SENTENCES ABOVE ARE NOW FALSE

**Added 2026-08-24 by the CR-031 W4 surface lane, after the rulings landed.**
Sections 1–12 were written the same morning, BEFORE the PO answered. **Five of
the contradictions they record are now RULED**, so several sentences above are
stale by design. This section is the stamp: read it before you build from
anything in §1–§12.

**The authority is `04-docs/05-modules/03-customers/02-business-rules.md`
(BR-CUS-090 · 091 · 092 · 093 · 094 · 095), not this document.** Nothing here
decides anything; it says which drawn sentence lost.

| Ruling | What it settles | The sentences above that are now FALSE |
|---|---|---|
| **BR-CUS-093** — *"At creation — every draft is numbered"* | Closes **DEF-634**. The request is created AND numbered the moment the clerk opens the form, so a number can be quoted down the phone while the form is half-filled. | **§1's footer copy** — *"Step N of 6 · nothing is created until you submit"* is FALSE and becomes ***"Step N of 6 · saved as draft SR-26-0048"***. **§1's header copy** — *"the request is created and numbered when the fee is collected"* — **comes out entirely**. **§6a** no longer describes two branches that disagree about when the SR exists: it exists first, both times. |
| **BR-CUS-094** — *"Expand the signed list to seven"* | Closes **DEF-635**. Seven real categories; `government` becomes LEGACY, unselectable on new records and lawful everywhere else. **No row is re-labelled by guess.** | **§3's** note that four of the seven chips are unseeded. The contract is `04-docs/03-contracts/customers-service-request.md` §1. |
| **BR-CUS-095** — *"Settings grows a checklist … We ship with nothing ticked"* | Closes **OQ-351**. `(request_type × document_type) → required`, tenant-scoped, shipping ENTIRELY UNTICKED. | **§5's** *"The other half is still open … OQ-351 stays open."* It is closed. §5's behaviour half — attaching never blocks creation — is UNCHANGED and joined, not replaced. |
| **BR-CUS-090** — *"we acept it and in finance we will reconcile … accept it and mark it as cash"* | Closes **DEF-637**. Both screens were right about their own half: **$130.00 quoted, $25.00 collected, $105.00 outstanding**, receipt `RCP-26-4471`. A shortfall is an open fee balance — never a refusal at the desk, never a silent waiver. | **§6's** framing of `$130.00` vs `$25.00` as an unresolved contradiction. **§11.2's** acknowledgement copy — *"Nothing is charged and no service changes until we have confirmed what is needed"* — **may not be printed where a fee WAS taken**; there, the sentence states the amount, the method and the receipt number. Where none was taken it may stand. |
| **BR-CUS-091** — *"Yes customer can request it"* | Closes **§12.5 row 12.a / DEF-638 12.a**. The LIST was right. | **§12.3's decision-panel reason** — *"a disconnect … is only ever started by collections, never from a customer request"* — is **WITHDRAWN** and the control is enabled. |
| **BR-CUS-092** — *"we have to take SSn and Driver lience and follow PII rules"* | Rules **DEF-632** capturable, and records the offered law-override as DECLINED-AS-UNNECESSARY (OQ-016 was already closed on app-layer encryption). | ⛔ **NOT BUILT, and §2's `stored encrypted` promise stays OFF the screen** until clause (b)'s app-layer encryptor exists. Clause (d) is explicit: a false security promise over a government identifier is worse than an absent one. |

### 13.1 · What the withdrawal of the disconnect reason does NOT take with it

⚠ **The reason is withdrawn; the DISTINCTION it drew is still true and is now
contract.** A **move-out** closes the account and settles the deposit
(BR-CUS-030). A **disconnect** leaves it **open and accruing** (BR-MET-105's base
charge keeps running). *"the capture form must not quietly convert one into the
other; the clerk picks the outcome and the request records which was picked."*
They carry different child kinds and nothing maps between them.

### 13.2 · One consequence §12.5 could not have anticipated

**BR-CUS-091 makes the service request the front door for COLLECTIONS-INITIATED
work as well as customer-initiated work.** A request may now originate from
STAFF, so `channel` distinguishes them (`staff_collections`) and the
**applicant-identity fields are not required on a staff-raised disconnect** —
`applicant_name` is nullable for exactly that case, and `address_as_given` stays
required either way. There is no service request about nowhere.

### 13.3 · What is STILL open after this batch

**OQ-355** (the fifth approval condition — the panel prints *"4 of 5"* and four
are nameable) · **OQ-356** (the verdict for undrawn evidence combinations — and
it now carries one more `possible` row, because the withdrawn disconnect reason
left that badge blank rather than filling it) · **OQ-357** (the `⊘` glyph:
remove, or waive with a reason — BR-CUS-090 settled how much was COLLECTED
against the quote and said nothing about this) · **§12.5 rows 12.b–12.f**, none
of which was raised with the PO in this batch.

---

## 14 · ⚠ WHAT THE MOVE-IN SCREENS (MVI-01 / MOV-01) SAY ABOUT THE IDENTIFIER

**Added 2026-08-24 by the CR-031 W4 surface lane, from PO screenshots supplied
mid-session.** These are the PO's own drawing, so **they are authoritative over
§2 and §12.5 where they differ.** Recorded here BEFORE any code is written
against them (hard-won law 10: a reply that explains something the repo does not
say is a context leak).

### 14.1 · The identifier is `ID type` + `ID number`, ONE column with a type

MOV-01 step 2's *"create a new customer"* panel draws:

| Field | Control | Drawn value |
|---|---|---|
| `ID type` | SELECT | `Driver's licence` |
| `ID number` | text | placeholder *"Number as printed"* |

…and the customer search results render the stored value as **`DL ••••4417`** —
a **type prefix plus the last four**, never the full value.

**So the product's own established shape is ONE identifier column with a TYPE
beside it, masked to last four on every read.** That has three consequences:

1. ⛔ **Do NOT build an `ssn` column and a separate `drivers_licence` column.**
   The shape is `identifier_type` + `identifier` (encrypted) + a blind index, so
   an SSN and a driving licence are the **same field with different types** —
   which is also the only shape under which BR-CUS-092(c)'s *"every read path
   renders last four only"* is one rule rather than one per document.
2. ✅ **This settles §12.5 row 12.c / DEF-638 clause (3).** The request detail
   labelled the field `ID` and the capture form called it `Social Security
   Number`. The move-in screen shows `ID` **with a type** is the house pattern,
   so **the generic label wins** and `Social Security Number` is the wrong label,
   not merely an inconsistent one.
3. **BR-CUS-092 is unchanged by this.** Clause (b) still requires the app-layer
   encryptor before any value is stored, and clause (d) still keeps *"stored
   encrypted"* off the screen until it is live. What MVI-01/MOV-01 change is the
   **SHAPE** of the column that will eventually exist, not whether it may exist
   yet.

### 14.2 · `Date of birth` is real and IS collected

MOV-01 step 2 draws **`Date of birth` (MM/DD/YYYY)** on the same panel. That
closes the open half of **§12.5 row 12.b / DEF-638 clause (2)**: the request
detail matches on date of birth and the six-step capture form had no field for
it, which read as a phantom. **It is not a phantom — the CUSTOMER model is
expected to carry it**, and the request's `Customer match` panel is matching on
a customer field rather than on a request field.

⚠ **Still not built here.** `service_requests` carries no `date_of_birth` and the
matcher is still refused by name, because the field belongs to the customer
entity and the automatic matcher additionally needs the identifier (14.1) that
BR-CUS-092(b) gates.

### 14.3 · ⚠ A THIRD CATEGORY VOCABULARY — and the lane's reading is that it is a DIFFERENT AXIS

MOV-01's same panel draws **`Customer type *`** as three chips: **Individual ·
Business · Government**. That is a third vocabulary beside BR-CUS-094's seven
(Residential · Commercial · Industrial · Agricultural · Institutional ·
Municipal · Builder or developer) and the four originally seeded.

**BR-CUS-094 is built exactly as ruled — it is the signed one — and nothing here
resolves the overlap by choosing.** What the code says, for whoever files this:

**The evidence that they are two different axes, and that there is therefore no
conflict about the seven:**

| | legal-person type | consumer category / tariff class |
|---|---|---|
| lives on | the **customer** — `customers.kind` (`person | company`, B2 r9 #1), mirrored on the request as `applicant_kind` (`person | business`, REQ-03.1's *"Applying as"*) | the **account** — `accounts.account_type_id` → `account_types` (B2 r5 #12 [D5] → BR-CUS-094) |
| drawn on | MOV-01 step 2's *"create a new customer"* panel, beside `ID type` and `Date of birth` | REQ-03.2's `Customer category` + `Sub-category` |
| cardinality | one per customer | one per ACCOUNT — one customer may hold several, each categorised differently |
| load-bearing on | who the legal party is | **PRICE** — the sub-category help says the category *"sets which plans are eligible"*, and BR-CUS-094 makes the seven *"REAL categories a plan can be priced for"* |
| kind of thing | a legal person | a place or a use |

A church is **Institutional** (category) *and* an organisation (legal person);
both are true at once, which is what two axes means. And *"Individual"* is not a
tariff class — nothing can be priced for it as distinct from *Residential*.

**So the lane's reading is: `Customer type` is the LEGAL-PERSON axis — the
already-signed `customers.kind` — drawn with a third value, and it is NOT the
account category. Two fields, no conflict.**

⚠ **BUT THERE IS A NARROWER, REAL DEFECT AND IT SHOULD BE FILED:**

1. **The word `Government` names two different concepts in one product**, and we
   are actively retiring one of them. If `customers.kind` gains `government`,
   then `Government` is simultaneously a **live** legal-person type and a
   **legacy** account category. The human act BR-CUS-094 requires — deciding,
   per record, whether a legacy `government` ACCOUNT is really Municipal or
   really Institutional — is made harder by a `Government` chip sitting live on
   the customer panel, because it reads as the answer and it is not one.
2. **`customers.kind` is two values today (`person | company`) and MOV-01 draws
   three.** Either the customer-kind vocabulary gains a third value, or the
   account category is leaking onto the customer panel. That is not derivable
   from a picture and no lane picks it.

---

## 15 · ⚠ THE MOVE-OUT SCREENS (MVO-01 / MOV-01), AND THE ONE CONTROL ON THEM THAT MUST NOT BE BUILT

Captured 2026-08-24 from the PO's screenshots, with their own ruling attached.
This is W5 material and W5 has not started — which is exactly why it is written
down now. **The next agent reads the repo, not this conversation** (hard-won law
10), and the ruling below is the kind that is invisible in a drawing.

### 15.1 · ⛔ THE `Scenario` PANEL IS A PROTOTYPE DEVICE, NOT PRODUCT UI

The move-out prototype opens with a panel headed **`Scenario`**, sub-titled
*"Drives every screen below — the states a clerk actually meets"*, holding two
segmented controls:

| | |
|---|---|
| **HOW THE ACCOUNT IS METERED** | `Standalone` · `Sub-metered` · `Has sub-accounts` |
| **HOW THE MONEY LANDS** | `Settled` · `Refund due` · `Short by` · `Refusal · other debt` · `Refusal · excess` |

**PO ruling 2026-08-24, verbatim: _"this is only for reference not for design"_.**

So it is a **reviewer's switch** — the mechanism that lets one static prototype
show five money outcomes and three metering shapes without five separate files.
**It does not exist in the product**, and no story, screen id or test may treat
it as a control. A clerk does not choose "how the money lands"; the account's
balance and deposit decide it.

⚠ **WHY THIS NEEDED A RULING AT ALL, AND WHY IT IS RECORDED RATHER THAN
ASSUMED.** Every other panel in that file IS the design — this repo's standing
instruction is that where A1–A17 contradict the prototype, **the prototype
wins**. A lane applying that rule faithfully would have built the switcher: it
is drawn, it is styled like the rest, and nothing inside the drawing marks it as
scaffolding. The only thing that distinguishes it is this sentence.

✅ **WHAT THE PANEL IS STILL GOOD FOR — do not discard it.** It enumerates the
states W5 must handle, which is more than the prose does: **three metering
shapes × five money outcomes**, and both refusal branches (`other debt`,
`excess`) are outcomes a wizard must be able to REACH and explain. Read it as a
test matrix, never as a screen.

### 15.2 · `MVO-01` — the Move-outs tab

Five KPI tiles, each with the sentence that makes it legible: **OPEN 5**
*customers leaving* · **LEAVING THIS WEEK 1** *within 7 days of today* · **FINAL
READS DUE 2** *nothing settles without one* · **SHORTFALLS TO DECIDE 1** *the
deposit does not cover it* · **REFUNDS TO PAY 1** *money leaving the building*.

Columns: `ACCOUNT · CUSTOMER · UNIT · MOVE-OUT DATE · STEP · FINAL READ ·
SETTLEMENT · STATE`. Search offers *"Customer, account #, unit, address, or
request #…"* — note it searches by **request #**, which is BR-CUS-080's
`origin_service_request_id` surfacing on a list.

**`FINAL READ`** is a three-state fact, not a date: `taken` · `due` ·
`estimated`. **`SETTLEMENT`** carries the money outcome in words —
`refunded $88.40` · `refund $11.20` · `settles exactly` · **`SHORT $175.20`** in
the accent · `—`. The screen's own footnote is the rule: *"A shortfall is shown
in the accent because it needs a decision — nothing settles itself."*

### 15.3 · The move-out wizard, and TWO CONFLICTS TO RESOLVE BEFORE BUILDING

Header: *"Close an account and settle what's owed."* / *"Six steps · final bill,
deposit, and what happens to the unit."* Steps: **1 Find account · 2 Date & final
reads · 3 Settle the money · 4 The shortfall · 5 What happens next · 6 Review &
close**. Step 1 asks *"Which account is moving out?"* and shows, beside the
chosen account, **`b · Its relationships`** — *"This account holds its own meters
directly … so the close affects only this customer."*

⛔ **CONFLICT 1 — SIX STEPS OR FOUR?** The wizard says **"Six steps"** and draws
six. `MVO-01`'s `STEP` column counts to **four** on every row (`4 of 4`, `3 of
4`, `2 of 4`, `1 of 4`). Both are in the same PO screenshot set. This decides
what the list's progress bar means and whether a row can reopen the wizard at
its furthest incomplete step, so it is not cosmetic. **Not resolved here.**

⚠ **CONFLICT 2 — STEP 4 IS CONDITIONAL, AND THE LIST HAS NO WAY TO SAY SO.**
With the money `Settled`, step 4 renders **`Shortfall · skipped`**, greyed. So
the six are not always six — which may be the whole of conflict 1, or may be
separate. A skipped step must not read as an incomplete one on either surface.

⚠ **AND THE MOVE-OUT WIZARD HAS NO `Save & exit` AND NO `Park — waiting on`**,
where the move-in wizard (MOV-01) draws both. Only `Cancel`. That contradicts
W5 task 5.1 — *"Park & resume on **every** wizard"* — and the CR-031 amendment
in which the PO asked for save-and-exit. Either the drawing is behind that
ruling or move-out is deliberately different because a half-closed account
holds a unit nobody else can take. **Not resolved here.**

### 15.4 · Step 1's four panels, and what the PO confirmed about them

PO, 2026-08-24: *"When we select Sub meter - relationship panel changes"*. So
the `Scenario` switch drives panels **b–d**, and that is the second half of
§15.1's ruling: the SWITCH is scaffolding, but **the panels it switches between
are all real states** the product must render from the account's actual shape.

**`a · The account`** — the plain facts, with its status pill.
**`b · Its relationships`** — a pill (`Standalone`) and one sentence, e.g.
*"This account holds its own meters directly. Nothing else measures through them
and no other account depends on them, so the close affects only this customer."*
**`c · Same customer`** — *Holds 3 other accounts*, as `ACCOUNT · UNIT · STATUS ·
BALANCE`: `A-11968 · 77 Cedar Ct · 91d overdue · $948.20` · `A-12180 · 310 Oak ·
Unit 2 · Current · $0.00` · `A-09984 · 88 Willow · Unit 4 · In credit ·
−$61.40`. **This panel is not decoration** — it is the evidence a clerk needs
for BR-CUS-054/BR-PAY-014's offset question, and it shows a credit and an
arrear on the same customer at once.
**`d · The premise`** — `Owner / manager on record: Ridge Property LLC` · `Units
total 3` · `Units occupied 2 of 3` · **`Common-area account MA-1408 · master`**.

### 15.5 · ⛔ THE OWNER IS FREE TEXT, AND THAT COLLIDES WITH TODAY'S OQ-350 RULING

Panel **d** carries its own warning, and it is the most consequential sentence
on the screen:

> *"Owner is free text on the premise record, not an account. That limits where
> a shortfall can be sent."*

⚠ **READ THAT AGAINST `BR-MET-105`, RULED BY THE PO EARLIER THE SAME DAY:** base
charges on an empty unit **accrue to the owner / landlord** (*"(a) the
owner/landlord"*, closing OQ-350). And `BR-CUS-083` bills a developer for
connection charges **through a master account** (OQ-349).

**A charge cannot be sent to free text.** So either the owner becomes a real
party — an account, or a customer record the premise points at — or
`BR-MET-105` has nowhere to post and OQ-350's ruling cannot be built as
written. `MA-1408 · master` on the same panel shows the shape that DOES work:
the common-area account is a real master account. Filed as **DEF-650**.

### 15.6 · Four `CHECK` advisories — each is a rule, not a note

Step 1 raises these before the wizard will continue, and each names a real
consequence a clerk must know BEFORE choosing a move-out date:

1. **Payment plan** — *"An active payment plan runs on this account — 4 of 9
   instalments paid. Closing it accelerates the remaining balance onto the final
   bill."* Closing accelerates; the plan does not survive the account.
2. **Open cycle** — *"A billing cycle is in progress … The final bill will
   prorate the open period rather than wait for it to close."* Move-out prorates
   forward; it never waits for the cycle.
3. **Dispute** — *"Dispute DSP-2210 is unresolved — $48.00 of the current balance
   is contested. **Settle or withdraw the dispute before refunding a deposit.**"*
   A contested balance BLOCKS a refund. That is a money rule and it is not in any
   signed document yet.
4. **`NOT CLOSED`** — *"An already-closed account cannot be moved out again —
   reopen it or raise a correction instead."* Consistent with BR-CUS-030.

⚠ **NONE OF THE FOUR IS A SIGNED RULE TODAY.** They are drawn, they are
specific, and the third moves money. They need ratifying before W5 builds step 1,
not after.

### 15.7 · ✅ THESE PANELS USE THE SHARED EXPAND/COLLAPSE

PO ruling 2026-08-24: *"We wil use expand and collapes in for these panels - as
required"*. The component exists — `07-frontend/src/components/Disclosure.tsx`,
built to the PO's earlier instruction (*"build it in Tailwind"*, *"under each
expand - detials of that are is displayed"*). **Reuse it; do not write a second
one.**

⚠ **AND ITS ONE RULE DECIDES WHAT MAY COLLAPSE HERE: collapsing never hides a
headline fact, only the derivation.** On this screen that is not a style
preference, it is a safety property. A clerk about to close an account must see
**`91d overdue · $948.20`** on a sibling account and **`6 sub-accounts beneath
it`** whether or not they opened the panel. So:

| Panel | Collapsed must still show | May hide |
|---|---|---|
| `b · Its relationships` | the pill — `Standalone` / `6 sub-accounts beneath it` | the per-row table |
| `c · Same customer` | *Holds 3 other accounts*, and that one is overdue | the account rows |
| `d · The premise` | `Units occupied 2 of 3`, the common-area account | owner, unit counts |

**The `CHECK` and `BLOCKED` advisories never collapse.** They are the reason the
step exists.

### 15.8 · ⚠ `Has sub-accounts` — a parent with open children is WARNED, not blocked

⚠⚠ **ITEM 1 BELOW IS SUPERSEDED BY PO RULING 2026-09-20 (`OQ-CUS-12515`, option (b)).**
This heading read *"CANNOT be moved out"* and this sentence read *"it is a hard
block rather than a warning"* until that ruling. PO, verbatim: *"option B - give a
warning and allow it; if owner has sold the property to new owner then we are
transfering all libalities and ownership to new owner"* — **where a property is
SOLD the act is a TRANSFER, which carries the account, its liabilities and its
ownership to the new owner with the tenants untouched beneath it, so the case this
block protected against already has its own flow.** The live rule is `BR-CUS-1082`;
read that row, not this capture. **Items 2 and 3 below are untouched and still
stand.** The disclaimer at the foot of this section is what sent the question to the
PO in the first place, and it was right to.

The third metering shape, as the PO walked it on 2026-08-24:

> **`BLOCKED`** — *"This account is the parent of 6 sub-accounts that are still
> open. Closing it would leave them measuring against a meter with no account
> behind it. Close or reassign the sub-accounts first."*

`b · Its relationships` carries the pill **`6 sub-accounts beneath it`** and
lists them: `SUB-ACCOUNT · UNIT · SUB-METER · BALANCE · STATUS` — `A-11441 Unit B
S-4022-2 $88.10 Current` … `A-11444 Unit E S-4022-5 $310.40 30d past` …
`A-11446 Irrigation S-4022-7 $28.90 Current`. Panel `a` shows the parent's own
`Services` as **`Water M-4022 · parent of 6 sub-meters`**.

**Three things this settles for W5:**
1. ~~A move-out is **refused**, not warned, while any child is open — and the
   refusal names the count and offers the two ways out (close them, or reassign).~~
   ⚠ **SUPERSEDED 2026-09-20 (`OQ-CUS-12515`, option (b)): the move-out COMMITS and
   the clerk is WARNED.** The count is still named — `2 sub-accounts are still open.`
   — and the two ways out are no longer offered, because there is nothing the clerk
   must do first (B14 rule 33: the instruction half of that sentence was removed from
   all eleven catalogues). See `BR-CUS-1082`.
2. The sub-accounts' **balances and ageing are shown**, because "close them
   first" is a different job if one is 30 days past due.
3. `Irrigation` sits in the UNIT column beside real units — so a sub-account may
   hang off a **purpose** rather than a unit, which the move-in screens also
   showed (`S-4022-1 · SERVES Irrigation`).

⚠ **THIS IS NOT IN ANY SIGNED RULE.** BR-CUS-030 says closing is a flow, not a
status flip; nothing says a parent is blocked by its children. It needs
ratifying before W5 builds step 1.

✅ **IT WAS RATIFIED — AND THE ANSWER WAS NO (2026-09-20, `OQ-CUS-12515`, option
(b)).** This disclaimer did its job: the refusal was built as a lane judgment, the
question was asked, and the PO declined it. **Kept verbatim rather than deleted,
because a section that says of itself that it is unsigned is exactly what a later
lane needs to see before citing it as law.**

### 15.9 · STEP 3 · **THE FIVE MONEY LANDINGS** — PO 2026-08-24: *"At step 3 - llok at all variations based on scenarios"*

The `Scenario` panel's second switch is **`HOW THE MONEY LANDS`**, and it has five
positions: **`Settled` · `Refund due` · `Short by` · `Refusal · other debt` ·
`Refusal · excess`**. Step 3 is a **different screen in each**, not one screen with
a different number. The PO walked all five and this is what each holds.

⚠ **REMEMBER §15.2: the `Scenario` panel itself is NOT built** — *"this is only for
reference not for design"*. What is built is the five OUTCOMES; the switch is the
prototype's way of showing them on one page.

#### 15.9.0 · What is IDENTICAL in all five

Two columns, always, and they are the same two components everywhere:

**Left — `Final bill · prorated to Aug 14`**, tagged `14 of 31 days`. Columns
`LINE · USAGE · AMOUNT`. Rows carry the unit inline in the USAGE column
(`284 kWh`, `1.82 kgal`) — CLAUDE.md rule 3 satisfied by the table, not by prose.
Footer row `Final bill`.

**Right — two stacked panels.** `Everything outstanding` (Prior balance + Final
bill → a red total) and `What is applied against it` (Deposit held · Deposit
interest · Unapplied credit on this account · a fourth row that VARIES → a red
total). The right column is the settlement, the left is the bill. **The names are
the rule:** `Everything outstanding` is BR-CUS-025 as amended on 2026-08-12
(*"everything outstanding"*, not just the final bill) spelled on screen.

Then a **verdict panel** at the foot, with a badge, whose content is the whole
difference between the five.

#### 15.9.1 · The five, side by side

| # | Money lands | Heading on screen | Outstanding | Applied | Verdict figure | Badge | Step 4 |
|---|---|---|---|---|---|---|---|
| 1 | `Settled` | *Settled — nothing owed either way* | — | — | — | — | skipped |
| 2 | `Refund due` | (refund panel) | **$94.45** | **$153.50** | Net after settlement **−$59.05** | `Refund` | skipped |
| 3 | `Short by` | *Short — the deposit did not cover it.* | **$324.24** | **$153.50** | **Short by $170.74** | `Needs a decision` | **`4 · The shortfall`, live** |
| 4 | `Refusal · other debt` | *Refund refused — the credit goes elsewhere first.* | **$94.45** | **$153.50** | Net after settlement **−$59.05**, refused | `Refused` | `4 · Shortfall · skipped` |
| 5 | `Refusal · excess` | *Needs a decision — the deposit exceeds everything owed.* | **$140.38** | **$153.50** | Net after settlement **−$13.12** | `Escalate` | `4 · Shortfall · skipped` |

⚠ **STEP 4 IS CONDITIONAL, AND THE STEP BAR SAYS SO IN WORDS.** It renders
`4 · The shortfall` live and red in case 3, and `4 · Shortfall · skipped` greyed in
cases 4 and 5. **This is direct evidence for DEF-648 reading (b)** — the wizard is
six steps of which one is conditional — but it does not settle it, because a
greyed-and-labelled step is still a step the bar draws. The list's four-segment bar
still cannot address it.

#### 15.9.2 · The bill CHANGES between scenarios — and the tax base moves with it

This is the part that is easy to miss, and it is billing math rather than layout.

**Case 2 / 4 (`$94.45`)** — Electric base `$8.35` · Electric usage `284 kWh`
`$38.94` · Water base `$5.42` · Water usage `1.82 kgal` `$5.82` · Sewer base
`$3.61` · **`Late fee · Jul cycle`, marked `not taxable`, `$28.05`** ·
`Tax & franchise fees · 6.85% of $62.14` `$4.26`.

**Case 3 (`$181.94`)** — the same five service lines, then **`Senior discount ·
25%` `−$15.54`** · **`Payment plan · remaining accelerated`, marked
`already taxed`, `$132.15`** · `Tax & franchise fees · 6.85% of $46.60` `$3.19`.

Both foot exactly:
- `8.35 + 38.94 + 5.42 + 5.82 + 3.61 = 62.14` → `62.14 × 6.85% = 4.2566 → $4.26` ✔
  `62.14 + 28.05 + 4.26 = $94.45` ✔
- `62.14 − 15.54 = 46.60` → `46.60 × 6.85% = 3.1921 → $3.19` ✔
  `62.14 − 15.54 + 132.15 + 3.19 = $181.94` ✔

**Three rules are stated by that arithmetic**, and the USAGE column labels two of
them in words rather than leaving them to be inferred:

1. **`not taxable`** on the late fee — this is **B4.2, already CONFIRMED**: *"tax
   base = usage + base charge only (fees and late charges are NOT taxed)"*. The
   prototype and the signed rule agree.
2. **`already taxed`** on the accelerated payment-plan balance — consistent with
   the same rule (the instalments were taxed when originally billed), and it says
   so on the line rather than silently omitting it.
3. ⚠ **THE DISCOUNT REDUCES THE TAX BASE — AND NO SIGNED RULE SAYS IT DOES.**
   `62.14 − 15.54 = 46.60` is only true if the senior discount comes off BEFORE
   tax. B4.2 defines the base as *usage + base charge only*; it is silent on
   discounts, and B4 is ❄️ **FROZEN**, so this cannot be settled by editing it.
   The difference is real money: taxing $62.14 instead of $46.60 is **$1.07** more
   on this one bill. Filed as **DEF-652**.

#### 15.9.3 · Case 2 · `Refund due` — and the ONE conditional sub-step

Verdict panel, badge `Refund`: *"After the final bill of $94.45 is met, $59.05
remains from the deposit and interest of $153.50. The customer has no other debt
with us, so it is refunded."*

⚠ **The second sentence is a PRECONDITION, not a courtesy** — it is exactly what
case 4 falsifies. A refund is only reachable after checking the customer's OTHER
accounts.

Below it, a second panel appears **in this case only**, badged **`Only when money
goes back`**:

> **`Refund · conditional step`** — `METHOD`: **`ACH` | `Mailed cheque` | `Carry to
> new account`**, helper *"ACH reuses the bank details on file. A cheque needs a
> forwarding address."* Beside it `FORWARDING ADDRESS`: `Street *` (placeholder
> *"Where to send the cheque and final notices"*), `City`, `State` (`TX`
> prefilled), `ZIP`. Footer: **`Amount to send  $59.05`**.

**Four things this settles for W5:** the three refund methods are a closed
vocabulary; `Carry to new account` is a method, so a refund can become an opening
credit on the customer's NEXT account without money moving; the forwarding address
is required **for the cheque method only** (the `*` is on Street, and the helper
names the condition); and the panel is **mounted conditionally** — it must not
render at all in the other four cases.

#### 15.9.4 · Case 3 · `Short by` — the only case that opens step 4

`What is applied against it` carries a fourth row that the others do not:
**`Credit on A-09984` → `Available · $61.40`**. It is **shown and NOT applied** —
`324.24 − 153.50 = 170.74`, and $61.40 is nowhere in that. In cases 2 and 5 the
same row reads **`Not applied`**.

⚠ **THAT IS A DELIBERATE RESTRAINT AND IT NEEDS A RULE.** A credit sitting on
another of the same customer's accounts is surfaced to the clerk but never swept
automatically, even when it would cut a shortfall by a third. Contrast case 4,
where a **debt** on another account IS acted on. **Credits do not travel by
themselves; debts do.** Nothing signed says this.

Verdict panel, badge `Needs a decision`: *"Everything outstanding is $324.24. The
deposit and interest of $153.50 leave $170.74 unrecovered. That balance has to go
somewhere before the account can close."* Sub-heading under the step title:
*"Step 4 decides where the remaining balance goes. **It cannot be skipped.**"*
Primary button changes to **`Continue → The shortfall`**.

This is **BR-CUS-082** (ruled this morning, OQ-346) with a screen at last: a debt
that survives closure is still chased. The prototype adds *where does it go* as a
mandatory decision rather than a background consequence.

#### 15.9.5 · Case 4 · `Refusal · other debt` — a credit is seized for a sibling account

Fourth applied row: **`Debt on A-11968` → `Owed $948.20 · takes priority`**.

Verdict panel, badge `Refused`: *"This customer owes $948.20 on account 11902, 91
days overdue. The $59.05 credit here goes there first — no refund. What remains on
11902 after the transfer is $889.15, still in collections."*
Two buttons: **`Transfer the credit →`** (primary) and **`Override · refund
anyway`** (secondary).

`948.20 − 59.05 = 889.15` ✔

**What this settles:** cross-account debt takes priority over a refund; the refusal
is **overridable by the clerk**, so it is a strong default and not a block; and the
prose states the AFTER figure, so the clerk sees that transferring does not clear
the sibling account.

⚠ **THE PANEL NAMES TWO DIFFERENT ACCOUNTS FOR ONE DEBT.** The applied row says
**`A-11968`**; the prose says **`account 11902`**, twice. One of them is wrong and
the money moves to whichever the code picks. Filed as **DEF-651**.

#### 15.9.6 · Case 5 · `Refusal · excess` — and it contradicts a rule signed this morning

`Everything outstanding` is **$140.38** (`Prior balance $45.93` + `Final bill
$94.45`); applied is `$153.50`; **`Net after settlement −$13.12`**.

Verdict panel, badge `Escalate`: *"The deposit and interest ($153.50) exceed
everything owed ($140.38). This case needs a decision before it can be settled —
an open dispute of $48.00 means the amount owed may still move."* Four radios:

- `Refund the excess to the customer`
- `Hold the excess pending the open dispute DSP-2210`
- `Apply the excess to A-11968 and refund the remainder`
- `Escalate to Finance for a decision`

⚠ **READ THAT AGAINST `BR-CUS-081`, CONFIRMED BY THE PO ON 2026-08-24 — TODAY.**
That rule says, with its own worked figure (deposit **$153.50** against owed
**$142.30** → *settle the $142.30 and refund $11.20*): a closing balance the
deposit more than covers **is settled and the difference is refunded**. It states
no condition. This screen has the identical shape — `$153.50` against `$140.38` →
`$13.12` — and instead of refunding it **escalates**, because a dispute is open.

**The screen may well be right** — an open dispute means the owed figure can still
move, and §15.6 advisory 3 already says *"Settle or withdraw the dispute before
refunding a deposit"*. But BR-CUS-081 as signed has no dispute carve-out, and a
rule confirmed this morning cannot be narrowed by reading a prototype. Filed as
**DEF-653**.

### 15.10 · STEP 5 · *"What happens when this account closes."*

Sub-heading: *"Six things change. One of them is a decision only you can make."*
Six panels; the starred one is the decision.

**`Premises` · `1408 Elm St`** — `Units occupied after this  1 of 3` ·
`Owner / manager  Ridge Property LLC` · **`Common-area account  MA-1408 ·
unaffected`**. Advisory, tagged `FREE TEXT`: *"The owner is a name on the premise
record, not an account. Nothing can be billed or transferred to them until they
exist as an account."* — **that is DEF-650 restated by the prototype itself, on a
second screen.**

**`★ Unit · the decision`**, badge `Vacant · base charges only`. *"What should unit
U-10432-A do after Sarah leaves? Each choice bills differently."* Four radios, each
with its monthly price on the right:

| Choice | Price | Description |
|---|---|---|
| **`Vacant · base charges only`** (selected) | **$30.50/mo** | *"Service stays live with no occupant. Base charges bill to the master account MA-1408 so the connection is kept ready."* |
| `Vacant · service off, no billing` | **$0.00/mo** | *"Service is disconnected at the unit. Nothing bills to anyone, and a reconnect fee applies to the next occupant."* |
| `Landlord-billed · between tenants` | **$30.50/mo + usage** | *"Ridge Property LLC carries base charges and any usage while the unit is empty — cleaning, showings, works."* |
| `Occupied · owner-billed` | **$30.50/mo + usage** | *"The owner occupies or holds the unit themselves. It never enters a vacant state."* |

Consequence line: *"Silver Creek keeps billing $30.50 a month to master account
MA-1408 until someone moves in. Usage is zero but the connection stays live."*

⚠ **THIS IS `BR-MET-105` MADE BUILDABLE — AND IT IS OPTION (b) OF DEF-650's
PROPOSAL, ALREADY DRAWN.** BR-MET-105 (PO 2026-08-24, OQ-350) says empty-unit base
charges *"accrue to the owner / landlord"* at **$30.50/month**, and DEF-650 filed
that free text cannot be billed. **The default choice here posts to `MA-1408`, a
real master account** — which is exactly the resolution DEF-650 proposed. But the
third and fourth choices post to `Ridge Property LLC`, which is the free text
again. **So the four choices are not equally buildable today**: two work, two need
the owner to become a party first. That is a direct input to the DEF-650 ruling and
is written here so the PO can settle both at once.

**`Assets`** — *"Every meter and device at the unit"*, `ASSET · KIND · SERVICE ·
WHAT HAPPENS TO IT`:

| Asset | Kind | Svc | What happens |
|---|---|---|---|
| `M-4021` | Meter · electric | E | Stays at the unit · final read taken, then idle until the next move-in |
| `M-4022` | Meter · water (parent) | W | Stays with Ridge Property LLC · resumes billing the full volume |
| `M-4023` | Net meter · electric | E | Stays · export credit stops accruing, **unbanked credit of $4.10 is forfeited on close** |
| `S-4022-1` | Sub-meter · water | W | Stops being deducted from M-4022 · reverts to the owner from the next cycle |
| `BF-1180` | Backflow preventer | W | Test overdue 41 days · obligation reverts to the owner, notice reissued to them |
| `PV-0442` | Solar array · 6.4 kW | E | Stays · interconnection agreement follows the premise, not the account |
| `CM-2204` | Comms module | E | Stays live · continues reporting so vacancy reads keep coming in |

Two advisories: `DEDUCTION ENDS` (*"Sub-meter S-4022-1 stops being deducted from
parent M-4022. From the next cycle that usage bills to Ridge Property LLC."*) and
`REVERTS` (*"The backflow test on BF-1180, overdue 41 days, reverts to the owner.
Silver Creek's notice goes to Ridge Property LLC, not to Sarah."*).

⚠ **`M-4023` TAKES $4.10 OF CUSTOMER MONEY AND NO RULE PERMITS IT.** A banked solar
export credit is value the customer generated; *"forfeited on close"* is a
confiscation policy stated in a table cell. Nothing in B4, the rating rules or the
customers rules says what happens to an unbanked export credit at closure — and
note the row directly above settles a deposit down to the cent and the panel beside
it argues over $13.12. Filed as **DEF-654**.

⚠ **`PV-0442` states a genuinely useful rule in passing:** the interconnection
agreement **follows the premise, not the account**, so it survives every move-out.
Not signed anywhere.

**`Plans, rates & discounts`** — `Plan on the unit  Residential Standard v3 ·
stays` · `What bills against it  Base charges to MA-1408` · `Senior discount · 25%
Ends with the account` · **`Budget billing  Trued up on the final bill`**. Footnote:
*"The plan belongs to the unit and survives the move-out. The discount belonged to
Sarah and does not."*

**That footnote is BR-CUS-029 as superseded on 2026-08-11** (*"the plan lives once,
on `units.rate_plan_id`"*) and **BR-CUS-014 scenario 5** (the unit keeps its last
plan as next-tenant prefill), in one sentence a clerk can read. The **discount /
plan split** — plan is the unit's, discount is the person's — is the useful new
part, and `Budget billing · Trued up on the final bill` is a billing obligation W5
must hand to W3.

**`Payments`**, badge `Autopay cancelled` — `Autopay · ACH Chase ••••4021
Cancelled on close` · `Scheduled payment · Sep 1  Cancelled` · `Payment plan · 4 of
9 paid  Closed · nothing outstanding` · `Unapplied credit  $0.00` · **`Open dispute
DSP-2210  $48.00 · must be resolved`**. Advisory tagged `EXPLICIT`: *"Autopay is
cancelled, not paused. If the final bill is unpaid nothing will be collected
automatically — the shortfall decision in step 4 is the only recovery path."*

⚠ **That advisory is the DEF-644 pattern from the other direction.** The account
tab's `Autopay on` pill needed a qualifier because autopay records a promise it
never charges; here the wizard states the mirror consequence at the moment it
matters. Both are the same missing fact told where the mistake would be made.

⚠ **`Payment plan · 4 of 9 paid → Closed · nothing outstanding` reads against
§15.6 advisory 1**, which says closing **accelerates** the remaining instalments
onto the final bill — and case 3's bill line `Payment plan · remaining accelerated
$132.15` shows exactly that. So `nothing outstanding` is TRUE only *after* the
acceleration is billed. In this screenshot the scenario is `Refusal · excess`,
whose bill carries no acceleration line, so the two may simply be different
scenarios. **Unverified across variants — do not build the label as a constant.**

**`Collections & notices`**, badge `All stopped` — `Dunning  Stops on close` ·
`Disconnect notice · issued Aug 2  Cancelled` · `Medical hold  Ends with the
account` · **`Credit reporting  Not reported`**.

⚠ **`Dunning · Stops on close` IS ONLY LAWFUL IN THIS SCENARIO.** BR-CUS-030's
stop-at-close clause was **superseded on 2026-08-24 for the closed-with-balance
case** (BR-CUS-082): a debt surviving closure is still chased and the ladder
restarts at tier 1. This screenshot is `Refusal · excess`, where nothing is owed —
so `Stops on close` is correct here and would be **wrong** under `Short by`. The
badge `All stopped` likewise. **W5 must drive this panel from the money landing;
it is not a constant.** Recorded as a build constraint rather than a defect,
because only one variant was captured.

⚠ **`Medical hold · Ends with the account`** — a consumer protection ending at
closure, stated nowhere else. And **`Credit reporting · Not reported`** is a policy
position (this product does not report to bureaux) that no signed document holds.

### 15.11 · STEP 6 · *"Read it back, then close."*

Sub-heading: *"This ends Sarah's service at 1408 Elm St · Unit A. **It cannot be
undone from here — a reopen is a separate action.**"* — the immutability of the
commit stated to the clerk, consistent with hard rule 4.

Four read-back panels, each ending in a red emphasised row:

| `Account` | | `Money` | |
|---|---|---|---|
| Account | `A-10432 · Miller, Sarah` | Everything outstanding | `$140.38` |
| Unit | `1408 Elm St · Unit A` | Deposit + interest applied | `−$153.50` |
| Move-out date | `Aug 14, 2026` | Excess held | `−$13.12` |
| **Metering** | **`Sub-metered under M-4022`** | **Disposition** | **`Excess $13.12 pending decision`** |

| `Unit & assets` | | `After close` | |
|---|---|---|---|
| Unit becomes | `Vacant · base charges only` | Autopay | `Cancelled` |
| Billing on the unit | `Base charges to MA-1408` | Dunning | `Stops on close` |
| Sub-meter deduction | `Ends · returns to M-4022` | Forwarding address | `Optional` |
| **Backflow obligation** | **`Reverts to Ridge Property LLC`** | **Account status** | **`Active → Closed`** |

**`What we'll send`**, badge `5 of 6 selected` — six messages, each individually
togglable:

| Message | Channel | Selected | Description |
|---|---|---|---|
| `Final bill` | PDF + email | ✔ | Prorated charges through Aug 14 |
| `Account closed confirmation` | Email | ✔ | What was settled and what was not |
| `Deposit refund notice` | Email | ✗ | Method, amount, and when to expect it |
| `Shortfall demand letter` | Post | ✔ | **Only when a balance remains after the deposit** |
| `Notice to the owner` | Email | ✔ | Sub-meter deduction ends, backflow reverts |
| `Move-out SMS` | SMS | ✔ | Final read and closing balance in one message |

⚠ **THE SELECTION IS INTERNALLY INCONSISTENT IN THIS SCREENSHOT** and it shows why
the panel must be scenario-driven: this is `Refusal · excess`, where **money is
owed BACK** — yet `Deposit refund notice` is UNTICKED and `Shortfall demand
letter` is TICKED, and the latter's own description says *"Only when a balance
remains after the deposit"*, which is the opposite of this scenario. Whether the
six default from the money landing or are simply free toggles is not stated
anywhere. **W5 must default them from the outcome**; drawn as-is they would post a
demand letter to a customer owed $13.12.

`ON CLOSE` advisory, and it is the best single summary of what the commit does:
*"Account A-10432 moves to Closed, the final bill of $94.45 is issued, the $13.12
excess is held pending a decision, unit U-10432-A becomes vacant · base charges
only, autopay and the Sep 1 scheduled payment are cancelled, the S-4022-1 deduction
ends, and the 5 selected messages go out."*

Two commit buttons: **`Close & start move-in →`** and **`Close account`** (danger
tier, per B14). ⚠ **`Close & start move-in` chains the two wizards** — the vacancy
this move-out creates is the premise the next move-in fills, and the prototype
offers to walk straight into it. That is a flow W5 must build, not a link.

### 15.12 · What steps 3/5/6 hand to W5, as a list

1. **Five money landings**, one step-3 screen each, driven by one derived outcome —
   `settled · refund_due · short · refused_other_debt · refused_excess`.
2. **Step 4 is conditional** and the step bar renders it greyed-and-named when
   skipped. (Still does not resolve DEF-648.)
3. **Three refund methods**, closed vocabulary; forwarding address required for
   the cheque only; the refund sub-panel mounts in one scenario.
4. **Credits do not travel, debts do** — a sibling credit is shown and never
   applied; a sibling debt seizes the refund, overridably.
5. **The tax base moves with discounts** — unsigned, ❄️ frozen file, **DEF-652**.
6. **Steps 5 and 6 are scenario-driven too** — the collections panel, the payment
   -plan label and the six outgoing messages are all wrong as constants.
7. **Four vacancy dispositions**, two of which need the owner to be a real party
   (DEF-650) before they can post anything.
8. **Seven asset dispositions**, one of which forfeits customer money (**DEF-654**).

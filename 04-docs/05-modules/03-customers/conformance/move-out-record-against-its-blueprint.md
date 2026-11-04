# The MOVE-OUT RECORD, against its blueprint drawing

**Step 1 of the measure-before-you-build process. THIS FILE ENDS WITH NOTHING BUILT.**

| | |
|---|---|
| Screen | the MOVE-OUT record — `/:tenant/moves/:ref`, e.g. `/brazosbend/moves/MVO-26-0088` |
| Component | `07-frontend/src/features/customers/MoveRecordPage.tsx` (1,221 lines; serves BOTH move kinds) |
| Reads | `GET /moves/{ref}` (`06-backend/apps/customers/move_record_reads.py`) · `GET /accounts/{id}/close-impact` (`move_out_settlement.settlement_for`) |
| Drawing | `05-prototype/02 Accounts Menu Blueprint.pdf` — **p117 lower frame → p118 upper frame** (the record) · **p118 lower frame → p119 top** (the commit dialog) |
| Measured | 2026-09-20, against branch `claude/kind-wozniak-rl0uzt` at `934ada177` |
| Method | B14 **rule 42** — every page below was rendered to PNG and READ AS AN IMAGE (`10-scripts/pdf/pdf_render.py` at scale 2, plus crop renders at 3.2×–9× for the settlement figures and the page-break rows). Extracted text was used ONLY as an index to find pages. **The PRODUCT half was then read the same way** — the live screen was opened in Chromium at 1440×1100 and screenshotted (`/brazosbend/moves/MVO-26-0001`), because hard-won law 6 is the only check in this repo that reads rendered output, and it corrected one row of this table and added two more. |
| Standing constraint | **PO 2026-09-20, verbatim: *"we will not make changes to drawing"*.** The blueprint stands as drawn; the PRODUCT changes. Where the drawing contradicts a signed UI rule, **B14 rule 38** decides and the deviation is RECORDED here rather than silently taken either way. |

---

## 0 · WHERE THE MOVE-OUT RECORD IS ACTUALLY DRAWN — AND THE CITATION THAT IS STALE

**This was the first question, because the code's own answer is wrong.**

`MoveRecordPage.tsx` cites **p074** twelve times — lines 3, 9, 57, 86, 509, 658,
672, 686, 748, 766, 950 and 1207 — including its Trace block (*"blueprint `02
Accounts Menu Blueprint.pdf` p074"*) and its Lifecycle block (*"packet:
blueprint p074"*). **p074 was rendered. It is the MOVE-IN WIZARD** — step 5
`Deposit` (*"Take the deposit now"*, `What the customer pays today`) and step 6
`Review` at `/brazosbend/accounts/a-10432/move-in?step=6`. It draws no record
page of any kind.

Measured, by rendering every candidate:

| Page | What is actually drawn there |
|---|---|
| p073–p076 | the move-in wizard (steps 1–6) |
| **p077** | ⬅ **the MOVE-IN record** — *"The move-in, opened · MVI-26-0114 · `/brazosbend/moves/mvi-26-0114` · Proposed"*, title `Miller, Sarah` |
| p116 | the move-out **wizard**, step 6 `Review & close` |
| p117 upper | the move-outs **LIST** — `/brazosbend/accounts?tab=move-outs` |
| **p117 lower → p118 upper** | ⬅ **the MOVE-OUT record** — *"The move-out, opened · MVO-26-0088 · `/brazosbend/moves/mvo-26-0088` · Proposed"*, title `Okafor, D.` |
| **p118 lower → p119 top** | ⬅ **the commit dialog** — *"Tie the shortfall back — and what it does to the landlord"* |
| p041–p046 | the **complaints** wizard (its step 2 is also called *"What happened"*) |
| p135 | the **disconnect** wizard |

**So the p074 citation is stale in two directions at once:** the move-IN record
this component also serves is p077, and the move-OUT half it was later extended
to serve is p117–p118. It never dangled — p074 is a real page of the same
blueprint about the same flow — which is why no id-existence check and no
reviewer caught it. **That is `DEF-2804`'s exact shape**: a real reference read
for a different real reference.

⚠ **A LATER WAVE ALREADY FOUND p118 AND DID NOT GO BACK.** The same file cites
p118 correctly seventeen times (the settlement box, `WHERE IT COULD GO`, `Unit
now`, the `Moved out` chip) and p077 three times. So the file holds the right
page numbers and the wrong ones side by side, and the Trace and Lifecycle
blocks — the two a next lane reads FIRST — are the wrong ones.

**Filed as `DEF-CUS-6000`.** The repair is a citation sweep, not a code change.

---

## 1 · THE AUDIT TABLE

**Verdicts** — `matches` · `differs` · `deliberate absence` · `drawing is stale`.
**Severity** — `HIGH` a clerk cannot do something the record is for · `MED` a
clerk is told something untrue or is missing a fact the server holds · `LOW`
cosmetic or documentary · `—` no defect.

Every **stated absence** is classed **(a)** correct and deliberate, with its
ruling · **(b)** the server has the fact and the screen does not read it ·
**(c)** nothing in the product knows the fact yet. **A row marked (a) is not a
difference and is not counted as one.**

### 1.1 · Identity and the page itself

| § | Drawing (page) | Product | Verdict | Sev |
|---|---|---|---|---|
| Address | `/brazosbend/moves/mvo-26-0088` (p117) | `/:tenant/moves/:ref` → `/brazosbend/moves/MVO-26-0088`; `MOVE_RECORD_ROUTE = "/moves/:ref"`, mounted `App.tsx:1002` | **matches** | — |
| Placement | top-level `/moves/…`, not under `/accounts/` (p117) | same, and the reason is in the code (`moveRecordPath`) | **matches** | — |
| The caption's *TODAY* note | *"no move-out record page exists, and nothing in the product ties a shortfall back to a landlord"* (p117, p118) | the page EXISTS (built 2026-09-19, `b2517cbc5`); **nothing ties a shortfall back** | **drawing is stale** — first half only; the second half is still true | LOW |
| Page citation | — | `MoveRecordPage.tsx` says p074 twelve times | **differs** — §0; `DEF-CUS-6000` | MED |

### 1.2 · The header

| § | Drawing (p117) | Product | Verdict | Sev |
|---|---|---|---|---|
| Breadcrumb | `Accounts / Move-outs / MVO-26-0088` in the top bar | ⚠ **THERE IS NO BREADCRUMB.** The top bar carries a search box, a help icon and a bell, and nothing else — measured in a browser on `MVO-26-0001`, 2026-09-20 | **differs** | MED |
| Back link, label | `← The register` | `← The register` (`customers.moveRecord.back`) | matches the drawing; **B14 rule 1** says a `←` NAMES where it exits to, and ratification 8 (2026-09-20) settles it as `← Move-outs` | **differs (rule wins)** | MED |
| Back link, destination | the move-outs list | ✅ **FIXED 2026-09-20 (`DEF-CUS-5996`, `059996559`, 2.317.2)** — `moveRegisterPath()` reads the record's own `kind` and asks `parkedHomePath()`, the map a park, a discard and a resume already share, so no second tab map exists to drift. The not-found state has no `kind` and reads the `MVO-`/`MVI-` prefix instead. This row read *"hardcoded `/accounts?tab=move-ins`"* until then | **matches** | — ⚠ **THE LABEL IS STILL `← The register` AND IS `DEF-CUS-5997`** — see the row above; the destination was fixed first, deliberately. |
| Kicker | `MOVE-OUT MVO-26-0088` | `{kind} {move_no}`, uppercase, tracking-wide | **matches** | — |
| Title | `Okafor, D.` — the customer's name | `record.title`; 32px carried by `PageHeader` (**rule 40**) | **matches** | — |
| Status chips | `Completed` · `Short by $186.40` · `Moved out 01/28/2026` — **THREE, and no register chip** | on `MVO-26-0001` in a browser: `Completed` · **`1 register unread`** · `Moved out 07/31/2026` | **differs** — see the two rows below | — |
| …the shortfall chip | `Short by $186.40` | `Short by` is spliced in at index 1 only when `landing === "short"`; on `MVO-26-0001` the settlement is incomplete so it is absent — correctly | matches the drawing when there IS one — and **ratification 6 moves the figure OUT of the status row** into the KPIs | **differs (ruling wins)** | MED |
| …the register chip | ⚠ **the drawing draws NO register chip on a move-out.** p077 draws `1 register estimated` on the MOVE-IN record and p117 draws none | **`1 register unread` renders on the move-out.** The chip block is built unconditionally from `record.chips.unread_registers` and is not gated on `kind` | **differs** — a move-IN chip on a move-OUT, the same family of defect as the move-IN labels that `f2a0167f8` fixed | MED |
| Address line | 🏠 `1408 Elm Street · Unit A` | same, walked from `premises` (hard rule 8) | **matches** | — |
| Header actions | **TWO**: `Open the account` (boxed) · `Tie the shortfall back` (grey) | **TWO**, in a browser, left to right: `Open the customer` · `Open the account`, both the same outlined tier. **No shortfall commit anywhere on the screen.** | **differs** — the drawing's only decision control is absent | **HIGH** |
| Button grammar | neither drawn control carries `→` or `✓` | same | the drawing contradicts **B14 rule 4** (`Verb →` navigates, `Verb ✓` commits). **Rule 38 → the rule wins** | **differs (rule wins)** | MED |
| `Open the request →` | **not drawn at all** | not served, not rendered | **differs** — ratification 7 requires it where the move came from a request | MED — see §2.3 |

### 1.3 · `WHAT HAPPENED`

The drawing's six rows against the product's six. **They are not the same six.**

| Row | Drawing (p117/p118) | Product | Verdict | Sev |
|---|---|---|---|---|
| `Account closed` | `A-10432` | `account_no`, relabelled `Account closed` on a move-out | **matches** | — |
| `Unit` | `1408 Elm Street · Unit A` | same | **matches** | — |
| `Moved out on` | `01/28/2026` | same, tenant zone + format | **matches** | — |
| `Final read` | `Taken · 01/28/2026` | **absent from this section.** A separate `Final reads` PANEL lists registers | **differs** | MED |
| `Unit now` | `Vacant · standby off` | `Not recorded` | **deliberate absence (c)** — `UNIT_NOW_NOT_SERVED`: no field on either endpoint; occupancy counts units without saying what THIS unit is. Ratification 6 says **LEAVE** | — |
| `Reason` | **not drawn** | `Not asked` / `Not given`, move-out only | **differs — a deliberate ADDITION**, PO 2026-09-20 option A, eight days after the drawing | — |
| `Committed by` | `S. Ortiz · 01/28/2026 15:12` | `S. Ortiz · 01/28/2026` — **no time of day** | **differs** — the clock is a format, not a figure, so rule 37 does not excuse it | LOW |

### 1.4 · The money — `HOW THE MONEY LANDED`

| § | Drawing (p118) | Product | Verdict | Sev |
|---|---|---|---|---|
| Heading | `HOW THE MONEY LANDED` | `Money landed` | **differs** — rule 33 caps a heading at 3 words. Deliberate | — |
| Shape | bordered box · `Settlement` · `Closing balance` · `Deposit applied` · heavy rule · `Short by` | identical, three lines | **matches** | — |
| Figures | `$336.40` · `$150.00` · `$186.40` | served from `close-impact`, never derived here | **matches** — **rule 37**: the drawn figures are illustrations, a different number is not a defect | — |
| Box border | drawn in the ACCENT (red) | `border-neutral-300` | **differs — already correct.** Ratification 6: *"neutral border, not accent — a shortfall is a fact, not an error"* | — |
| `Short by` figure | black, bold | `text-warning-700` | **differs** — the same ratified reasoning applies to the figure as to the border | LOW |
| No settlement yet | not drawn — the drawing shows a FINISHED one | `The final bill is not stated.` (the SERVER's own gap, `gaps[0]`) | **deliberate absence (a)** — `$0.00` would state a settlement nobody ran (rule 37) | — |
| Deposit interest | not drawn on the record | not rendered | **deliberate absence (a)** — PO ruled interest is computed AT SETTLEMENT; a `$0.00` here would be WRONG rather than empty | — |

### 1.5 · The options — `WHERE IT COULD GO`

| § | Drawing (p117/p118) | Product | Verdict | Sev |
|---|---|---|---|---|
| Heading | `WHERE IT COULD GO` | `Options` | **differs** — rule 33's 3-word cap. Deliberate | — |
| Red rationale callout | ~55 words above the table | absent | **deliberate (a)** — rule 33: RATIONALE is **zero words on screen**. Ratification 6 says DELETE. **Already done** | — |
| `Nothing is preselected.` note | drawn (p118) | absent | **deliberate (a)** — same rule | — |
| Rows | **THREE**: `Follow the customer` · `Tie back to the master` · `Write it off` | **FOUR**, from the server: `collect`, `payment_plan`, `write_off`, `transfer` | **differs** — the server is the source (`SHORTFALL_PATHS`); the drawing is one row short. Hiding a lawful path is worse | LOW |
| `What it means` wording | 8–12 words per row | ≤ 6 words per row (`'The debt stays theirs.'`, `'Their ladder restarts.'`) | **differs — already correct.** Ratification 6's *"cut to 6"* is **already done**; the ratified row's reading of the product was stale | — |
| The target account | `A-10001 · Elm Street Holdings LLC` drawn INSIDE the `Tie back to the master` row | `unit_falls_to {available, account_no, reason}` **is served and is not rendered anywhere** | **differs — absence class (b)** | MED |
| `Not open here` | not drawn | rendered for `enabled:false`; the server's reason rides as a `title` | **(b)** — the server HAS the reason. `BR-SHL-025` wants disabled-with-its-reason; rule 33 wants rationale off screen. A live tension, §2.4 | MED |
| **Actionable?** | the table is a GLOSSARY; the ACT is a header button opening a dialog (p118) | **a glossary and nothing else. Nothing on this screen writes.** | **differs** | **HIGH** |

### 1.6 · The commit dialog (p118 lower → p119)

| § | Drawing | Product | Verdict | Sev |
|---|---|---|---|---|
| Existence | modal `Tie $186.40 back`, sub *"A-10432 closes; somebody else starts being chased"* | **nothing** | **differs** | **HIGH** |
| `WHERE IT WOULD GO` | `Amount` · `From` · `To` · `Why that account` | — | **differs** — every one of the four is served (`shortfall`, `account_no`, `unit_falls_to`, the owner/master `br_ref`) | MED |
| *"The target is resolved by the server and cannot be typed"* | drawn as a note | — | **matches the product's design**: `shortfall_decision` posts to `available[0]` and never accepts a typed account | — |
| `WHAT THIS WILL DO` | four `THEN`/`WHAT` rows, 8–12 words each | — | the drawing contradicts **rule 33** (a CONSEQUENCE ≤ 6 words per sentence, **at most two**). **Rule 38 → the rule wins** | MED |
| Footer | `Cancel` · `Tie it back to A-10001` | — | a footer's button ORDER is CONSTRUCTION → **rule 38**, the shared `ConfirmDialog` wins | LOW |
| ⚠ *"Now: `$186.40` moves to A-10001 and A-10432 settles at zero"* | drawn as a stated consequence | — | **THE DRAWING STATES A CONSEQUENCE THE PRODUCT CANNOT HONOUR** — see §2.1 | **HIGH** |

### 1.7 · Things ratified that the drawing does not draw

| § | Drawing | Product | Verdict | Sev |
|---|---|---|---|---|
| Tabs | **none drawn** | none | **matches the drawing.** Ratification 6 ADDS them — a product change, not a drawing correction | — |
| KPI tiles | **none drawn** | none | **matches the drawing.** Ratification 6 ADDS three (`Closing balance` · `Deposit applied` · `Short by`) | — |
| The in-flight state | **not drawn anywhere in this blueprint** | rendered, with one action `Resume` | **not drawn** — the action grid's in-flight row has no drawing to be checked against, and that is the finding | — |

⚠ **AND IT COULD NOT BE WALKED EITHER.** The beta holds exactly **two** move
records (`MVO-26-0001`, `MVI-26-0001`) and **one** parked draft, whose `flow` is
`move_in`. **There is no parked move-OUT on the beta**, so the in-flight arm of
the action grid has neither a drawing nor a live case — it is proved by the
table-driven test alone, and this is said here rather than left for a reader to
assume a browser confirmed it.

### 1.8 · B14 rule 31 — are the account numbers ids?

**No. Both are lawful user-facing references, and this was measured rather than assumed.**

- `A-10432` on screen is `accounts.account_no`, served by `move_record_reads` as
  `_fact(getattr(account, "account_no", None), …)` (line 744).
- `A-10001` is `unit_falls_to.account_no`, from `move_out_settlement`.
- The uuid (`doors.account.value.account_id`) is served **only** to build the
  URL — `accountDetailPath(...)` — and is never a field's visible value.

**Rule 31 is satisfied.** ✅

---

## 2 · THE FINDINGS THAT CHANGE WHAT GETS BUILT

### 2.1 ⚠ THE DRAWN CONSEQUENCE IS NOT TRUE, AND IT IS ON A MONEY PATH

p118 draws the dialog promising, as the first thing that happens **Now**:

> `$186.40 moves to A-10001 and A-10432 settles at zero`

**It does not, and it cannot today.** `move_out_settlement.shortfall_decision`
records the decision, its resolved target, its actor and its amount, writes the
`audit_log` row — and writes **no journal line at all**:

```
"posting": {"posted": False, "oq": "OQ-1250", …}
```

`OQ-1250` — *which two ledger accounts does a departing tenant's balance move
between?* — is **OPEN — non-blocking** on the register today. An account balance
is the ledger's own sum over posted journal lines (`DEF-127`), so **a transfer
nobody posts is a transfer that did not happen.** Neither balance moves.

⚠ **SUPERSEDED 2026-10-14 (`CR-185-BRC10`).** The PO closed `OQ-1250` → (a)
(D5, *"option 1; property is always under landload agreement"*). On the
`transfer` path the decision now POSTS one entry through the ledger posting
service — DR AR (owner account) / CR AR (tenant account) — and returns
`posting: {posted: true, entry_id, …}`. The tenant's balance falls and the
owner's rises by the residue; total AR is unchanged. The consequence dialog now
says *"$186.40 moves to A-10001 now."* (the first half of p118's sentence) and
still not *"settles at zero"*.

**Building the drawn sentence would be hard-won law 1 on a money path** — a
screen claiming a guarantee that is not the guarantee — and the clerk would be
the one who found out. So the consequence preview states what the act
**actually** does, within rule 33's two-sentences-of-six. The drawing is not
changed; the product does not lie.

### 2.2 ⚠ ONE ACT, TWO NAMES — AND THE DRAWING CARRIES BOTH

Ratification 7 finding (a), and it is the DRAWING's own inconsistency, not ours:

- p117 header control: **`Tie the shortfall back`**
- p118 options row: **`Tie back to the master`**
- p119 dialog footer: **`Tie it back to A-10001`**
- product catalogue today: **`Tie to master`** (`customers.moveRecord.path.transfer`)

Four spellings of one act. **One verb must win, in all eleven catalogues** — the
discipline B14 rule 34 applies to *Recorded* / *In the books*.

### 2.3 ⚠ `Open the request →` CAN NEVER APPEAR TODAY, AND THAT IS A SECOND DEFECT

Ratification 7: `Open the request →` appears **only** where the move-out came
from a service request; where it did not, it is **ABSENT rather than greyed** —
deliberately different from `BR-SHL-025`'s disabled-with-reason.

Measured, two layers:

1. `MoveRecord.request_id` **exists** (`moves.py:310`, nullable, indexed
   `ix_move_records_request`).
2. `move_record_reads.py` contains the string `request` **zero times** — no door
   is served. **(b)**
3. And the scenario suite already says the column is never filled on a move-out:
   `E3 · raised from a SERVICE REQUEST — and the wizard never sends the link ·
   wizard_sends_service_request_id: wanted True, PostgreSQL holds False` — RED
   in both columns, before this lane started.

**So a correctly-built `Open the request →` would be absent on 100% of move-outs
until E3 is fixed.** That is the honest rendering and it is what ratification 7
asks for; it is recorded here so the next reader does not mistake a correct
absence for a dead control. **Filed as `DEF-CUS-6001`** against the wizard's
missing link.

### 2.4 `Not open here` VS `BR-SHL-025`

`BR-SHL-025` (signed): a control this state cannot honour is DISABLED WITH ITS
REASON, never hidden. B14 rule 33: RATIONALE is zero words on screen. Today the
screen resolves this by showing a 3-word absence and hiding the server's
sentence in a `title` — which a touch or keyboard user never sees, the exact
fault ratification 3 names on the capture screen.

**Reading taken, and it is a lane judgment recorded rather than a question
re-asked:** the server's `reason` is ENGINEERING PROSE addressed to us (*"this
address has no owner account to post to. BR-MET-105a makes the owner a real
party…"*, 60+ words with two rule ids in it). Rule 32 forbids a rule id in
clerk-facing copy outright. So the control is **disabled and carries a
clerk-facing reason of its own**, ≤ 6 words, keyed per path — `BR-SHL-025`'s
requirement honoured, rule 33's cap honoured, and the engineering sentence stays
in the `title` and the register where it belongs.

### 2.5 HOW THE AUDIT MOVES THE RATIFIED ROWS

Three rows of ratification 6 read the product as it was **before** the waves of
2026-09-19/20 landed. The measured finding wins:

| Ratified row | Its reading of "product today" | **Measured today** | Effect |
|---|---|---|---|
| *Options · 10–12 word "what it means" rows → cut to 6* | 10–12 words | **already ≤ 6** — `'The debt stays theirs.'` (4), `'Their ladder restarts.'` (3), `'Needs a supervisor and reason.'` (5) | **NO WORK.** Done. |
| *Options · ~60-word rationale paragraph → DELETE* | on screen | **not rendered** — it is a code comment, correctly | **NO WORK.** Done. |
| *Money · one sentence, no figures → the three-line settlement* | one sentence | **the three-line settlement is built** and served | **NO WORK.** Done. |
| *Money · neutral border, not accent* | accent | **border is already `border-neutral-300`** | **PARTIAL** — only the `Short by` figure's `text-warning-700` remains. |
| *Header · chips: Completed · Moved out* | two chips | **three** — `Short by $X` is spliced in at index 1 | the ruling still stands: it MOVES to the KPIs. |

**Nothing in the audit contradicts ratification 7's action grid.** It is built as
ratified, with the two additions ratification 7 itself names (one verb, one
consequence preview) and the honest-consequence correction of §2.1.

---

## 3 · EVERY STATED ABSENCE ON THE LIVE SCREEN, CLASSED

| On screen | Class | Why |
|---|---|---|
| `Unit now` → **Not recorded** | **(c)** | no field on `/moves/{ref}` or `close-impact`; occupancy counts units without saying what THIS unit is |
| `Reason` → **Not asked** | **(a)** | the close predates the column; the server distinguishes it from **Not given** (asked, skipped) and the screen uses two labels |
| **The final bill is not stated.** | **(a)** | the SERVER's own `gaps[0]`; `$0.00` would state a settlement nobody ran (rule 37) |
| **No meter on this unit** | **(a)** | `UNIT_HAS_NO_METERS`, `BR-MET-037 · BR-AST-028` — a configuration fact about the unit |
| **Not open here** | **(b)** | the server serves `reason` per path; the screen shows 3 words and hides it in a `title` — §2.4 |
| **No customer linked** | **(a)** | PO: *"Open the customer - if requried otherwise we will ahev to link to exisitng one"*; linking is its own work |
| Deposit interest — **absent entirely** | **(a)** | PO ruled interest is computed AT SETTLEMENT. `$0.00` here would be WRONG, not empty |
| `Open the request →` — **absent** | **(b)** + a defect | `request_id` exists, is not served, and is never written — §2.3 |

**Five of the eight are (a). None of the five is a difference and none is counted as one.**

---

## 3.5 · THE LIVE SCREEN, VERBATIM — `/brazosbend/moves/MVO-26-0001`, 2026-09-20

Recorded so the next reader measures against a transcript rather than against
this file's prose. Chromium 1440×1100, `v2.317.0` in the rail, signed in as
Dana Whitfield.

```
← The register
MOVE-OUT MVO-26-0001
Rosa Pemberton
[Completed] [1 register unread] [Moved out 07/31/2026]     [Open the customer] [Open the account]
🏠 301 Mill Pond Ln · Apt 102

What happened                                 Money landed
  Account closed      AC-2026-00042             The final bill is not stated.
  Unit                301 Mill Pond Ln · Apt 102
  Moved out on        07/31/2026              Options
  Unit now            Not recorded              Option              What it means
  Reason              Not asked                 Follow the customer The debt stays theirs.
  Committed by        Dana Whitfield · 09/17/2026   Payment plan        They pay it over time.
                                                  Write it off        Needs a supervisor and reason.
Final reads                                       Tie to master       Their ladder restarts.
  REGISTER      READING          READ DATE   HOW                      Not open here
  E-5041·total  700.000000 kWh   07/28/2026  Read
  SM-7041       —                            Not estimated
  W-5041·total  7.000000 kgal    07/28/2026  Read
```

**Four things this transcript settles that no code reading could:** there is no
breadcrumb · the amber chip on a move-out reads `1 register unread` · the two
doors render `Open the customer` first · and the Options table orders
`Tie to master` LAST where the drawing puts it SECOND.

---

## 4 · THE BASELINE, MEASURED BEFORE ANYTHING WAS BUILT

`./10-scripts/move_out_scenarios.sh`, 2026-09-20, on `934ada177`:

```
complete with NO final bill stated ................. 5 of 27
complete WITH the final bill stated ................ 20 of 27
9 failed, 46 passed in 216.29s
```

Red before this lane started, and **none of them caused by it**: `L2`, `L4`,
`L5`, `D3` (all `open_disputes_not_readable`), `SH4` (`supervisor_role`), `R2`
(`DEF-CUS-5933`), `E3` (`wizard_sends_service_request_id`, §2.3).

**The beta is untouched** — counted by the script itself, before and after:
`accounts 78 · move records 2 · payments 74 · journal lines 751 · invoices 92 ·
parked drafts 1`, identical in both columns.

---

## 5 · WHAT STEP 2 BUILDS (not built by this file)

1. The **KPI row** — `Closing balance` · `Deposit applied` · `Short by`; the
   shortfall leaves the chip row.
2. The **action grid** of ratification 7, by state × whether the shortfall is
   placed, using the kit's four tiers.
3. The **shortfall commit**, through the EXISTING
   `POST /accounts/{id}/settle-shortfall` → `move_out_settlement.shortfall_decision`.
   **No second settlement path is written.**
4. The **consequence preview** (rule 11), stating what the act actually does — §2.1.
5. **One verb** for the transfer, in all eleven catalogues — §2.2.
6. The **`Final read` row** in `What happened`.
7. **Tabs**, matching the request detail's pattern.

**NOT in scope, and why:** the back-link destination (lines 495, 661) — **a
sibling lane owns it**. The `p074` citation sweep — `DEF-CUS-6000`, a separate
change. `E3`'s missing `request_id` — `DEF-CUS-6001`, the wizard's fault.

---

## 6 · HARD-RULE CLEARANCE FOR THE MONEY THE BUILD WIRES

Read before writing a line of it, and every one checked against the code:

| Rule | Verdict |
|---|---|
| **4 · financial immutability** | ✅ `shortfall_decision`'s own docstring: *"A NEW ROW, NEVER AN EDIT"*. It UPDATEs no invoice, no payment and no journal entry. |
| **5 · ledger** | ✅ ⚠ AMENDED 2026-10-14 (`CR-185-BRC10`, OQ-1250 → a): on `transfer` the SERVER posts ONE AR→AR entry through `apps/ledger/balance_transfer.py` → `posting.post` (the sole writer); this screen still writes nothing itself. Collect and payment plan post nothing. It read *"writes no journal line at all — `posting.posted: false`, `OQ-1250`"* until then. |
| **7 · audit** | ✅ `_audit(actor, "account.move_out.shortfall_decided", account.id, after=decision)`. |
| **2 · money** | ✅ served as `{stored, display}`; the screen reads `display` and **never re-rounds**. |
| 🔒 sensitive path | the settlement module is already `HUMAN-REVIEW-PENDING`; this build adds a CALLER, not a rule. |

**Nothing the build wires would UPDATE an issued invoice, payment or journal
entry.** If that changes, it stops and returns to the PO.

---

<!-- lifecycle -->
**status:** MEASURED — step 1 complete, nothing built.
**measured by:** the move-out record conformance lane, 2026-09-20, on `934ada177`.
**rendered:** p041–p046, p073–p077, p114–p120 at scale 2; p117/p118 cropped at
3.2×, p117/p118 page-break rows at 9× — **all read as images (B14 rule 42)**.

---

## 7 · WHAT STEP 2 ACTUALLY BUILT — appended 2026-09-20, after the build

**This section was written AFTER the rebuild, so the audit above stays the
measurement it was and this stays the outcome.** Commits `8cd893e14` (the
grid) and `35c594075` (the currency fix, the question and the record).

### 7.1 · Built

| § | What landed | Where |
|---|---|---|
| The action grid | `moveRecordActions()` — a PURE function, so the table-driven proof reads the grid rather than a second copy | `moveRecordActions.ts` |
| The rendering | six controls at the ratified tiers, rule 4's markers appended in one place | `moveRecordActionBar.tsx` |
| The commit | `POST /accounts/{id}/settle-shortfall` → `shortfall_decision`, through `settleShortfall`, the caller the wizard already publishes. **No second settlement path.** | `moveRecordActionBar.tsx` |
| The consequence preview | B14 rule 11, inside rule 33's two sentences of six — and it does NOT say what p118 says (§2.1) | 11 catalogues |
| One verb | the header control and the options row read ONE catalogue key | `moveActionLabelKey` |
| The outcome as a fact | the four options become a sentence once one is chosen, with five words saying a reload forgets it | `MoveOutMoney` |

### 7.2 · Deliberately NOT built, each with its reason

| Not built | Why |
|---|---|
| The back-link LABEL (`← Move-outs`) | a sibling lane landed the DESTINATION fix (`059996559`) and left the copy to `DEF-CUS-5997`. Not this lane's. |
| KPI tiles · the `Final read` row · tabs | ratified in §6 and **not reached** — the action grid was the heart and took the time. They remain open and are listed in §5 above. |
| The `p074` citation sweep | `DEF-CUS-6000`, a separate change touching twelve comment lines. |
| `move_records.request_id` | `DEF-CUS-6001` — the wizard's fault, and scenario `E3`'s. |

### 7.3 · What moved in the ratified rows, and why

Nothing in §7's action grid moved. Two clauses of it could not be built as
written, and BOTH are the audit's measurement winning over a reading of one
screenshot:

1. **`Open the account →` on the in-flight row is never emitted.** No in-flight
   move HAS an account — the server says so by name,
   `NO_ACCOUNT_UNTIL_IT_COMPLETES` — so the row renders two controls, not three.
   A third would open nothing (hard-won law 2's mirror).
2. **`Completed · short, decided` has nothing to read it from.**
   `shortfall_decision` answers `persisted: false`. The arm is built and is
   driven by what this clerk just did; a reload honestly returns to
   `undecided`, and the screen says so in five words. `OQ-CUS-12516`.

### 7.4 · A DEFECT THE SEVENTY GREEN TESTS DID NOT SEE

The dialog title rendered **`Tie 186.40 back?`** — a money figure with no
currency, on a money commit. Found by opening the page, not by any check.
Fixed through `formatMoney` (the same formatter the cells use) with a case that
fails on the bare number, proved red first. **Hard-won law 6 earned its place
again**, and it is worth recording that the miss was structural rather than
careless: every other figure on this screen goes through `MoneyCell`, and a
dialog TITLE is the one place on it that is a plain string.

### 7.5 · Measured after the build

* `./10-scripts/move_out_scenarios.sh` — **5 of 27 · 20 of 27**, IDENTICAL to
  the before run, the same nine rows red in the same columns. Correct: no
  backend code changed.
* The beta, counted by the script in both runs: **78 accounts · 2 move records ·
  74 payments · 751 journal lines · 92 invoices · 1 parked draft** — unchanged.
* Front end: **70 green** across three suites, every mutation shown red under
  `vitest run` first.
* In a browser at 1440, **B14 rule 6 measured on RENDERED OUTPUT**:
  `Write it off ✓` has `rgba(0, 0, 0, 0)` at rest and `rgb(168, 22, 0)` on
  hover — the outlined-fills-on-hover danger tier, read with `getComputedStyle`
  rather than asserted from a class name.
* The POST a browser actually sent: `{"path":"transfer"}`, once, to
  `/accounts/{id}/settle-shortfall`. **Intercepted and fulfilled in the browser,
  so nothing reached the beta.**

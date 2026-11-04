# CR-094-BRC01 · step 1 lane 5 — money on an account, and the request queue

**Five screens: 13 `S23` change plan · 14 `S24` payment plan · 15 `S68` account
import · 16 `S83` requests list · 17 `S84` request detail.**
**Drawn at pages 132–148 of `05-prototype/02 Accounts Menu Blueprint.pdf`**, pinned
at commit `033981d4f39f4b3e703639c074df1f8df7082a6d`, `sha256` begins
`c8d596bb505f5020ce4b9474`. Remedies §10 pages 150–206; specification register §12
pages 207–209.

**Step 1 classifies. It fixed nothing.** No product code was changed by this lane.
The only files it adds are this document and its walkthrough.

---

## 0 · HOW THIS WAS READ, AND WHAT THAT IS WORTH

**Pages 132–148, 152–155 and 207–209 were read as IMAGES at scale 2**, never from
the text layer. The blueprint's own §3a measures that layer as unsafe for anything
carrying a number — **every digit extracts as `&`**, 8 of 21 specification ids drop,
and the wireframes are vector art and absent entirely. Prose was taken from the text
layer where it is reliable (and used only to *locate* sections); **every figure,
label, id and count below was read off a rendered page or off the running product.**

**The product was booted and driven.** PostgreSQL 16 on `:5432` (334 migrations,
`migrate --check` clean), Django on `127.0.0.1:8610`, the front end built with
`vite build` at HEAD and served by `server.mjs` on `:8611` with `API_PROXY_TARGET`
pointed at the backend — the same-origin shape the product ships. Signed in as
`dana@brazosbendutilities.com` on tenant `brazosbend`, Chromium at 1280×900. **The
version badge read `v2.237.10` on every page**; the blueprint audits `2.234.15`.

**Nothing was seeded.** The fixture already held what this lane needed and that was
checked rather than assumed: account `A-10432` with a balance of `247.300000`,
account `AC-2026-00011` carrying a live payment plan, **two finished import runs
with rejected rows** (`RUN-2814` 1,251 in / 1,247 loaded / 4 rejected, and
`RUN-2822` 312 / 310 / 2), and eight service requests across six states. The brief
anticipated that an import could not be judged without a rejecting run; one existed,
so none was made.

The walkthrough is **`10-scripts/cr094_lane5_walkthrough.mjs`**. Screenshots, full
page text and `measurements.json` are written beside it under the session scratchpad.

### What this lane did NOT do, stated rather than blurred

* **It did not open pages 75–85.** Screens 16 and 17 are drawn *with the flow that
  fills them* — the six-step capture wizard in §03 — which is **lane 3's page
  range**, and the CR splits lanes by pages so no two read the same ones. Page 141
  gives these two screens a trace block and no wireframe. **So this lane's as-built
  record for 16 and 17 stands on its own browser measurements and on p141; it makes
  no claim about how they are drawn.**
* **It did not reach the change-plan cost preview.** Step 2 was reached and read;
  `Show what it costs` stayed disabled after filling `#effective_on`, because the
  *On a date I choose* radio must be chosen first and the probe did not click it.
  The preview's precision is therefore settled **at the code level and not in a
  browser** — see §1.3. What would settle it in a browser is one more click.
* **It did not drive any wizard to a write.** Nothing was committed against a
  tenant.

---

## 1 · SCREEN 13 — CHANGE PLAN WIZARD · `S23` · `/:tenant/accounts/:accountId/change-plan`

Drawn p132–133. Three steps in the code. **Trace: `ChangePlanWizard.tsx`, reached
from one door — the `S21` icon rail's ⇄ *Change plan*.**

### 1.1 · As drawn (p132–133)

| | |
|---|---|
| step 1 | `Pick a plan` · sub-line `Step 1 of 3 · Plan` |
| step 2 | `When does it take effect?` · `Step 2 of 3 · Effective` |
| step 3 | `Confirm the change` · `Step 3 of 3 · Confirm` |
| addresses | `…/change-plan?step=1`, `?step=2`, `?step=3` |
| step 1 fields | `New plan` (select, `Choose a published plan`) · checkbox `I understand this drops Water` |
| step 1 rail | `Current plan` = `Residential Standard · current` · `Current base` = `$30.50 / mo` |
| step 2 fields | `Effective` (`Immediately` / **`Next cycle`** selected / `A date I choose`) · `Effective on *` = `01/10/2026` |
| step 2 preview | `Current base $30.50` · `New base $42.00` · `Base delta +$11.50` · `Net impact +$11.50 / mo` |
| step 3 fields | `Reason` · `Notify the customer` (ticked) · `Log eligibility proof` |

**The drawing carries its own stated absences, quoted:**

> **NO STEPPER IS RENDERED** — *"The three steps exist in the code and no rail is
> drawn for them, so the running screen shows only the form — only the form and a
> disabled Continue. The three names below are the code's model of this flow, kept
> here because a build would start from them."*

> **DEPOSIT DIFFERENTIAL** — *"The deposit is not worked out again in this version.
> The amount set at move-in stands."*

And p145, in the document's own words, leaves the stepper unresolved on purpose:

> *"And two steppers could not be confirmed at all. Change plan and Payment plan
> draw three steps each in §06; the running product shows **no rail** on either
> entry screen, only a disabled Continue. Either the rail appears once the first
> choice is made, or the drawn stepper is wrong. This document does not know which,
> and says so rather than guessing."*

### 1.2 · As built, measured at `2.237.10`

**Step 1**, on `A-10432`. Page title `Change plan`, **computed `font-size: 32px`** —
B14 rule 40, which landed this morning, is honoured here.

```
Current plan            Sample — Residential
Services at this unit   electric · water
1 · Pick the new plan
  Industrial            $180.00  base per month   Drops water
  Residential Standard   $20.00  base per month
  Sample — Commercial    $63.00  base per month
  Sample — Industrial   $195.00  base per month
  Sample — Residential   $20.00  base per month   Current
  Small Commercial       $15.00  base per month   Drops electric
Continue                                          (disabled)
```

**Step 2**, reached by clicking a plan and `Continue`:

```
2 · Effective date and what it costs
When it takes effect
  Immediately · At the start of the next cycle · On a date I choose
  "Only a date can be used today. Nothing in the product can yet say which day
   the next billing cycle begins, so those two options are shown and cannot be
   picked."
New plan starts on*
  "A date inside a period already billed is refused: bills already sent are
   never repriced."
Show what it costs (disabled)     Back     Continue (disabled)
```

**Picking a plan that drops a service** (`Small Commercial`, which drops electric)
adds the checkbox **`I have told the customer this ends electric.`** and `Continue`
stays disabled until it is ticked. That is **B14 rule 11** — a form writing service
state showing its consequence before its commit button — present and working, and
worth recording because the rule is unenforced by any gate.

### 1.3 · The three things that differ, and their routing

**(a) THE STEPPER QUESTION IS SETTLED, AND THE DRAWN STEPPER IS WRONG.**
Measured `0` rail nodes at step 1 **and at step 2 after the first choice was made**
— so the rail does not appear once a choice is made, which was the reading the
blueprint could not rule out. The words `Plan`, `Effective` and `Confirm` appear
nowhere on the page and the product never prints `Step n of 3`. The only progress
cue is the panel heading, `1 · Pick the new plan` → `2 · Effective date and what it
costs`.

**The mechanism, and it is exact:** `CHANGE_PLAN_STEPS` (`ChangePlanWizard.tsx:130`)
has **two readers in the whole repository** — its own type alias on the next line,
and `AccountActions.test.tsx:369`, which asserts the array equals
`["plan","effective","confirm"]`. Nothing renders it. `PAYMENT_PLAN_STEPS` is the
same shape with `PaymentPlanWizard.test.tsx:201`. **Nine sibling wizards in
`features/customers/` import `components/WizardFrame`, which owns the rail; these two
are the only two that do not.** → **`DEF-CUS-5071`, MAINTENANCE.**

**(b) `?step=2` AND `?step=3` DO NOT EXIST.** Both render step 1. The step is
component state (`useState<ChangePlanStep>("plan")`, line 242), so the three
addresses the blueprint's trace block names are not addresses at all, and a refresh
or a shared link returns the clerk to step 1. → folded into **`DEF-CUS-5070`**.

**(c) THE DRAWN STEP-2 RADIO IS SELECTABLE AND THE BUILT ONE IS NOT.** The drawing
shows `Next cycle` chosen; the product disables both `Immediately` and *at the start
of the next cycle* with a quoted reason. The drawing is an audit claiming to be
as-built. → **`DEF-CUS-5070`**.

### 1.4 · Money on this screen — **CORRECT**

Every money figure rendered two decimals: `$180.00 · $20.00 · $63.00 · $195.00 ·
$20.00 · $15.00`. A search of the whole rendered page for four-or-more decimal
places returned **nothing**. At the code level this is structural rather than lucky:
**all 11 money call sites in `ChangePlanWizard.tsx` go through `MoneyCell`** (lines
449, 670, 676, 682, 706, 716, 761, 775 and neighbours), which is why the unreached
preview can be reported as correct by construction.

---

## 2 · SCREEN 14 — PAYMENT PLAN WIZARD · `S24` · `/:tenant/accounts/:accountId/payment-plan`

Drawn p134–135. Three steps: `Terms · Schedule · Agreement`.

### 2.1 · As drawn (p134–135)

| drawn | |
|---|---|
| step 1 | `Terms` · `Step 1 of 3 · Terms` |
| step 1 fields | `Balance to spread *` `$612.75` · `Down payment` `$112.75` · `Instalments *` `5` · `Cadence` `Monthly` · `First due *` `01/10/2026` · `Take by autopay` · `Suspend late fees while the plan runs` ✓ · `Suspend disconnect while the plan runs` ✓ |
| step 1 notes | *"The arrears position, not the current bill."* · *"The current bill is still due alongside the plan — the screen says so."* |
| step 2 | `The schedule` — `# / DUE / AMOUNT / LEFT`, five rows of `$100.00` running `$400.00 → $0.00`; `Progress 0 of 5 paid`; *"The remainder lands on the FINAL row, never spread across the others."* |
| step 3 | `The agreement` — `Email SMS Print`, `Signed on 09/24/2026`, `Record signature` ✓ |
| step 3 note | *"Queued only — notifications has no send path, so the channel records intent."* |
| rules cited | `BR-CUS-043 · 044 · B4.4 (2dp half-up, remainder on the final)` |

Every figure above is an **illustration** under B14 rule 37 and is recorded, not
built to. They are internally consistent — `612.75 − 112.75 = 500.00 = 5 × 100.00` —
which is worth saying only because it means the drawing was reasoned, not sketched.

### 2.2 · As built, measured on `A-10432` (an account with no plan)

Page title `Payment plan` at **32px**. `Balance owed $247.30`. One heading:
**`Step 1 · Amount and term`**. Eight labels, character for character:

```
Balance to spread*          "It cannot be more than the account owes."
Down payment                "Record the money itself through Record payment;
                             this is the amount the schedule is built on."
Instalments*
How often                    Monthly · Every two weeks · Weekly
First instalment due*       "It must fall after today."
Charge instalments to the method on file
Suspend late fees on these arrears while the plan is current
Suspend disconnection while the plan is current
Continue                                                      (disabled)
```

### 2.3 · What differs

**(a) NO RAIL, SAME AS 13** — `0` rail nodes, no `Terms`/`Schedule`/`Agreement`
anywhere on the page, no `Step 1 of 3`. → **`DEF-CUS-5071`**.

**(b) FIVE OF THE EIGHT DRAWN LABELS ARE NOT THE PRODUCT'S.** The **order** is the
drawing's, which is what makes it read as observed; the **words** are not:

| drawn | built |
|---|---|
| `Cadence` | `How often` |
| `First due *` | `First instalment due*` |
| `Take by autopay` | `Charge instalments to the method on file` |
| `Suspend late fees while the plan runs` | `Suspend late fees on these arrears while the plan is current` |
| `Suspend disconnect while the plan runs` | `Suspend disconnection while the plan is current` |

→ **`DEF-CUS-5070`**, and it is the sharpest instance in it: a lane building this
screen from the drawing would rename five live controls.

**(c) THE LAST THREE LABELS BREAK B14 RULE 33** — a LABEL is capped at **3 words,
no sentence**. Counted: `Charge instalments to the method on file` = **7**,
`Suspend late fees on these arrears while the plan is current` = **11**, `Suspend
disconnection while the plan is current` = **7**. **No defect is filed for this** and
the reason is deliberate: rule 33's status column reads *"NOT ENFORCED for these five
kinds"*, the 606 strings already over the cap sit in a shrink-only baseline, and the
cap *"binds every NEW or CHANGED string from today"* — these are not new. **It is
recorded here so that whoever changes one of these three is bound by it.** The
drawing's own versions are over the cap too (7 words), so this is not a divergence.

### 2.4 · Money on this screen — **CORRECT**

`$247.30` — two decimals. `PaymentPlanWizard.tsx` imports `MoneyCell, formatMoney`
and carries no raw money interpolation.

### 2.5 · One stated absence, still true, and NOT a defect

`customers.paymentPlan.queueOnly` — the drawn *"Queued only — notifications has no
send path"*. The blueprint's §08 rotting-holds table grades it **`STILL TRUE —
notifications has no tables.`** It is a registered refusal and is left alone. *A held
control and a broken control look identical on screen*; this one is held.

---

## 3 · THE MONEY DEFECT — SIX DECIMALS ON THE SCREEN THAT TAKES MONEY

**This is `ACC-S13` in the blueprint, and it was checked rather than re-discovered.**
It belongs to screen 02's Record payment modal and is assigned here because this lane
is the money lane; lane 2 owns the screen.

### 3.1 · Measured, in a browser, on `A-10432`

| where | what it renders |
|---|---|
| accounts list and account header | **`$247.30`** |
| Record payment modal, balance line | **`247.300000 USD`** |
| Record payment modal, amount box, pre-filled | **`247.300000`** |

The same figure, on the same account, in the same session, one click apart.

### 3.2 · The two lines, at HEAD

```
AccountActions.tsx:321   {props.balance !== null ? `${props.balance} ${props.currency}` : <Dash />}
AccountActions.tsx:234   const [amount, setAmount] = useState(props.balance ?? "");
```

The file **imports neither `MoneyCell` nor `formatMoney`.** Checked across all seven
component files behind this lane's five screens plus `AccountActions.tsx`: it is the
**only one** with a raw money interpolation and no `MoneyCell` import.

### 3.3 · Why it reads as deliberate, and why the pre-fill is the half that bites

`formatMoney`'s fallback for an amount it cannot parse is, at
`MoneyCell.tsx:184`, ``return `${amount} ${currency}` `` — **byte-identical to what
line 321 hard-codes.** So the modal permanently renders the formatter's *error path*
in place of its normal one, and a reviewer sees a shape the codebase genuinely
contains elsewhere.

**The pre-filled value is what a clerk submits when they accept the default**, so a
six-decimal string is what reaches `POST /accounts/{id}/payments` on the common path.

### 3.4 · What the rule says, and what is NOT broken

Hard rule 2, PO re-sign 2026-08-22, verbatim: ***"MOney 4 decimal, percentage 6
decimal , display both 2 decimal"***. **Storage is lawful and is not the finding** —
`accounts.balance` is `DecimalField(max_digits=18, decimal_places=6)`, and hard rule 2
says in terms that *"existing 18,6 columns stay lawful containers"*. DRF serialises
that column at its declared precision, so `"247.300000"` on the wire is correct too.
**Only the display half is broken, and it is broken in exactly two lines.**

**Routing: MAINTENANCE.** A clerk can record a payment today; the screen shows the
wrong thing while doing it. → **`DEF-CUS-5008`, high.**

---

## 4 · SCREEN 15 — ACCOUNT IMPORT · `S68` · `/:tenant/accounts/import`

Drawn p136–140. Five stages, returns to `?tab=imports`.

### 4.1 · As drawn (p136–140)

Five stages `1 Extract · 2 Transform · 3 Validate · 4 Load **WRITES** · 5 Result`,
drawn as a rail on every stage. Stage 1 `Where is the file?` over a tab strip
`File SFTP API Manual Device`, fields `Drop a file` = `accounts-2026-09.csv` and
`Batch label *` = `Cutover — wave 1`, right rail `Encoding detected UTF-8` and
*"Migration order: premises → units + plans → assets → ACCOUNTS → opening reads."*
Stage 3 `Dry run` — `Will load 1,904 rows · Loads, with a warning 62 rows · Blocked —
will not load 34 rows`. Stage 4 `Commit` — `Rows to load 1,966` behind `I have
checked the dry run`. Stage 5 `The receipt` — `Rows in 2,000 · Loaded 1,966 ·
Rejected 34 · Duration 41s`, a rejected-row table, `Roll back` and `Back to imports`.

The register tab is drawn at p140: `RUNS 3 · ROWS LOADED 1,297 · REJECTED 1,225 ·
LAST RUN 05/04/2026`, three rows, footer `1–3 of 3`.

### 4.2 · As built, stage 1, measured

**The rail IS rendered here**, unlike screens 13 and 14:

```
WORKFLOW · ACCOUNTS · CSV
Extract, transform, validate, load.              (h1, 32px)
"Five stages · nothing is written until you commit at stage four."
  1 Extract   2 Transform   3 Validate   4 Load WRITES   5 Result
STAGE 1 OF 5 · EXTRACT
Where is the data coming from?
  Upload a file          CSV, fixed-width, BAI2, XLSX
  Pull from a server     Bank, lockbox, vendor drop
                         "Not switched on yet. Upload a file instead."
  Head-end or partner    AMI, payment processor
                         "Not switched on yet. Upload a file instead."
  Key it in              Small batches, corrections
                         "Not switched on yet. Upload a file instead."
Mapping template · Encoding & delimiter · Loads into · Batch label (audit trail)
Insert new only · Insert & update
```

Against the drawing: different `h1`, different heading, `STAGE` where the drawing
says `Step`, **four source cards where the drawing shows a five-item tab strip**,
three of the four held with a reason the drawing does not show at all, and the write
mode on stage 1 rather than stage 3. → **`DEF-CUS-5070`**.

**This is the document and not drift, and that was proved rather than argued:**
`git diff --stat 2824c2e5..HEAD` over `07-frontend/src/features/customers/` and
`06-backend/apps/customers/` is **6 files, +79 −25** — five rule-40 heading matchers
and `UnitPricingPanel.tsx`. `AccountImportWorkflow.tsx` did not move.

### 4.3 · The Imports tab, measured — and the finding is a *placement*, not an absence

KPI strip: `Runs 4 · since migration` · `Rows loaded 1,645 · across all runs` ·
`Rejected 6 · across all runs` · `Last run 08/01/2026 09:18 · autopay_enrolments.csv`.
Internally consistent: `310 + 1,247 + 88 + 0 = 1,645` and `2 + 4 + 0 + 0 = 6`.

| run | file | in | loaded | rejected | status | row action offered |
|---|---|---|---|---|---|---|
| `RUN-2822` | `autopay_enrolments.csv` | 312 | 310 | **2** | Loaded | **Roll back this run** |
| `RUN-2814` | `customer_accounts_migration.csv` | 1,251 | 1,247 | **4** | Loaded | **Roll back this run** |
| `RUN-2801` | `contact_updates.csv` | 88 | 88 | 0 | Loaded | Roll back this run |
| `IMP-260912-02` | `smoke-accounts.csv` | 3 | **0** | **0** | File read | **Fix the rejected rows**, *disabled* |

⚠ **THE HELD CONTROL IS ON THE WRONG ROWS.** `AccountImportsTab.tsx:227` is
`row.status === "loaded" ? rollback : fixRows` — the two branches are mutually
exclusive and the `rejected` count plays no part. A run finishes `loaded` whether or
not it rejected anything (`IMPORT_RUN_STATUSES` has no `rejected` value at all), so:

* **the two runs that DO have rejected rows are offered no fix path, held or
  otherwise**;
* **the run offered `Fix the rejected rows` has zero rejected rows and has not
  finished.**

A clerk looking at `RUN-2814` — 4 rows lost — sees only `Roll back this run`.
→ **`DEF-CUS-5009`, MAINTENANCE.**

### 4.4 · `ACC-S9` — reopening a finished run · **BUILD**

The registers were checked before this was classified, because the brief warns that a
held control and a broken one look identical. **The blueprint's §08 grades it
`ACC-S9`, and its own verdict is `No ruling. A specification.`** Nothing in
`02-decision-log.md`, `01-open-questions.md` or `11-change-requests.md` defers it.

The product's own copy, verbatim, and it is the only thing it says:

> *"Reopening a finished run is not switched on yet. Correct the file and import it
> again."*

`ACC-S9`'s target, quoted from p148 and p208:

> *"On a run reading **1,966 loaded · 34 rejected**, a **FIX ROWS** action opens
> those 34 with their reasons; correcting and re-committing them moves the run to
> **2,000 loaded · 0 rejected**."*

**Can a user do this today? No. → BUILD (r11).** Its dependency is already named in
the code: `AccountImportsTab.tsx`'s own exceptions note records that the inline fix
is `PATCH /imports/{run}/rows/{n}` and *"lives on the workflow's own stage 3"*, and
that *"a table row cannot re-enter a stage"*. ⚠ **`DEF-CUS-5009` must be fixed as
part of that build, not before it** — otherwise the fix is to move a hold onto the
right rows, and the hold rots the day the build lands. **Write the test that fires
when the hold expires in the same commit** (hard-won law 2).

---

## 5 · SCREEN 16 — SERVICE REQUESTS LIST · `S83` · `/:tenant/requests`

Drawn with the capture wizard at p75–85 (lane 3's pages — not opened here). Page 141
gives its trace block: four doors, no tabs of its own, embedded at
`/accounts?tab=requests` with `ownsUrl=false`, and *"the request number is plain
text, not a link, so drill-in is via the eye icon only."*

### 5.1 · As built, measured

Page title `Requests.` — **with a full stop.** KPI strip:

```
OPEN 6                   Not yet turned into a job
WAITING ON CUSTOMER 4    Documents or a deposit
OLDEST WAITING 15d       SR-26-0001 · documents
APPROVED, NOT STARTED 0  No job opened yet
REFUSED THIS MONTH 0     With a reason on record
```

Columns: `REQUEST · TYPE · APPLICANT · ADDRESS · RECEIVED · CHANNEL · AGE ·
WAITING ON · STATE · ACTIONS`. Six rows, footer `1–6 of 6`, one filter chip reading
`All`, and a `Filter ▾` dropdown. **No column is sortable** — the file says why at
line 159: `list_queryset` accepts no `sort` param, so a sort control would offer an
ordering the request cannot ask for.

### 5.2 · Two things checked and found NOT to be defects

**(a) `APPROVED, NOT STARTED` reads `0` while `SR-26-0006` is `approved`.** Correct:
the tile counts `state=approved AND outcome_ref IS NULL`, and `SR-26-0006` carries
`outcome_ref = 'A-12048'`. Honest.

**(b) Six rows over eight requests.** Correct and deliberate: the list defaults to
segment `open` = `(draft, submitted, under_review, more_info)`. `SR-26-0002`
(`in_fulfilment`) and `SR-26-0006` (`approved`) belong to the `approved` segment.

### 5.3 · The chip says `All` and the server is asked for `open` · **MAINTENANCE**

The one network call the page makes is
`GET /api/brazosbend/service-requests?segment=open&page=1&per=50`, while the chip on
screen reads **`All`** with `aria-pressed="true"`.

**Two defaults, each written correctly, never compared:**
`SERVICE_REQUEST_SEGMENTS` (`serviceRequestEndpoints.ts:95`) begins with `"all"`, so
the FilterBar shows `All` when nothing is chosen; `segmentFromState`
(`ServiceRequestsListPage.tsx:295`) independently falls back to `"open"`.

The footer is honest for the segment served, so nothing on screen contradicts
anything else — **the screen is internally consistent and says the wrong thing.**
→ **`DEF-CUS-5011`.**

### 5.4 · The list opens on the OLDEST · ⚠ **A COLLISION — AND IT IS ALREADY ASKED, AS `OQ-CUS-1790`**

Measured: `SR-26-0001` (received 08/28, `15d`) is row 1 and `SR-26-0008` (received
09/12, `0d`) is row 6. **Oldest first.**

It is deliberate and its reason is recorded twice — `service_request_reads.py:212`
and `ServiceRequestsListPage.tsx:156`, both quoting B19 §12.1:

> *"Sorted by age, oldest first — the oldest thing waiting is the thing to look at."*

And it collides head-on with **`BR-CUS-1046`**, ruled by the PO on 2026-09-10 and
landed in this repository two days ago as `7dbd15d82`:

> *"Whenever any account is created **or any entry is created in the system**, it
> automatically sorts it by the alphabetical order. It should always sort it by the
> creation order. **The new newly created entries should always show on the top.**"*

`ACC-S11` reads that sentence as reaching *"every list in the product that opens on a
name"* — this one opens on a **date**, ascending, which is the same ruling breached
in a different dress. But an SLA work queue is the one list where oldest-first is the
argument, and **resolving it means choosing between a PO ruling and a PO-approved
design intent.** The prime directive forbids that.

⚠ **AND IT IS ALREADY ASKED — `OQ-CUS-1790`, minted the same day by this CR's lane
1, OPEN.** Before minting anything this lane grepped `01-open-questions.md` and
`02-decision-log.md` for the subject, which is what hard-won law 13 requires and what
it exists to prevent: *"a person answering the same question twice from memory will
eventually answer it DIFFERENTLY."* `OQ-CUS-1790` names **Requests first among six**,
quotes the very footnote this screen prints — *"Sorted by age, oldest first — the
oldest thing waiting is the thing to look at."* — cites the same `BR-CUS-1046`, and
offers the PO three answers with their costs. **So no question was minted here.**

**What this lane adds to it is corroboration and one figure**: the collision was
reached independently, from the request queue rather than from the register, and on
this fixture it means the request received **today** (`SR-26-0008`, `0d`) is the
**last** row on the page while the one received on 28 August (`15d`) is the first.
`OQ-CUS-1790` is the row to watch; nothing here is built on it.

---

## 6 · SCREEN 17 — SERVICE REQUEST DETAIL · `S84` · `/:tenant/requests/:requestId`

### 6.1 · As built, measured on `SR-26-0006`

Page title `SR-26-0006` — a business number, not a database id, so **B14 rule 31 is
not breached.** Header `SR-26-0006 · Approved · Kwan, Michael · 88 Pine Vista ·
Move-in`. Six tabs: `Applicant · Location & services · Documents · Fees · Decision ·
History`. Header controls: `Save & exit`, `Park — waiting on ▾`, `Decide what this
is →`.

**The five outcomes** are the Decision tab's `What should this become?` group, and
they are real controls with per-option verdicts:

| outcome | state on this request |
|---|---|
| New connection | disabled |
| **Move-in** | enabled · `Fits the evidence` |
| Move-out | disabled |
| Transfer | disabled |
| Disconnect | enabled |

Then `Approve` / `Refuse`. Lifecycle actions available from `approved` also include
`Open the job` (`route`) and `Close by hand` (`manual_close`).

Two pieces of copy worth keeping, verbatim:

> *"Nothing is preselected. Approving creates real service and real charges, so the
> decision is made deliberately."*

> *"A move-out closes the account and settles the deposit. A disconnect leaves the
> account open and still accruing its standing charge. They are different things…"*

`Fees` tab: `Application fees` and `Connection quote`, both `0.00` — **two decimals.**

### 6.2 · Eight refusal keys reach the clerk as dotted keys · **MAINTENANCE**

⚠ **Four raw i18n keys are printed as literal text on the Decision tab**, three of
them as the *reason a control is disabled*:

```
WHAT THE ADDRESS LOOKUP FOUND
  customers.serviceRequest.lookup.servedAndVacant
New connection   customers.serviceRequest.verdict.newConnection.premiseExists
Move-out         customers.serviceRequest.verdict.moveOut.noAccountHere
Transfer         customers.serviceRequest.verdict.transfer.noLiveAccount
```

Counted across the source: the service layer can emit **eight** such keys —
`lookup.{noPremiseRecord, servedAndOccupied, servedAndVacant}` and
`verdict.{newConnection.premiseExists, newConnection.noPremiseRecord,
moveIn.servedAndVacant, moveOut.noAccountHere, transfer.noLiveAccount}`. **All eight
are declared in 0 of the 11 catalogues**, and no
`customers.serviceRequest.verdict.*` or `.lookup.*` key exists at all.

**Why nothing saw it.** The keys are built server-side as f-strings from a
`_REASON_KEY` prefix (`service_request.py:299` and `:329–354`), so no grep for a
literal key in the front end finds them, and `G32`'s `message_key` resolution — which
CLAUDE.md already records as *"reporting zero over a scope it silently excludes"* —
cannot see them either. B14 rule 32 bans a rule id or internal code in clerk-facing
copy; an internal dotted key standing in for *why you may not do this* is the worst
place for one. → **`DEF-CUS-5010`, high.**

### 6.3 · `ACC-S20` and `ACC-S21` · **BUILD**

Both are in §12 at p209 and both touch this lane's screens.

* **`ACC-S20`** — *"Every wizard's work has a queue, and the register's ten tabs are
  where they land."* Screens `01`. Its own words: *"What is missing is not data: it
  is that this document never drew where a clerk goes after pressing Submit."* This
  lane confirms the queue tab exists and is populated; the gap is a drawing, and the
  drawing belongs to lane 1's screen.
* **`ACC-S21`** — *"Each queued record opens onto its own page, and the request's
  five outcomes are the link between them."* Screens `01 · 02`. Done looks like:
  *"A clerk can answer what happened, what is it waiting on, and what has still not
  been done from the record itself — including the cases where **completed does not
  mean finished**."* The five outcomes exist as controls (§6.1); what does not exist
  is the link from an approved request to the job it raised, in both directions.
  **Routing: BUILD** — a clerk cannot do this today.

⚠ `ACC-S21`'s own claim that *"the job names the request it came from"* is
**partly built already**: `service_requests.outcome_ref` carries `A-12048` on
`SR-26-0006` and `CON-26-0117` on `SR-26-0002`. A step-2 lane should start from that
column rather than propose one.

---

## 7 · §12, THE SPECIFICATION REGISTER — AND A COUNT THAT DOES NOT ADD UP

The CR's §3b asks step 1 to settle whether the cover's **10** or the register's
**21** is right. Read end to end at p207–209, **the answer is neither, and the
difference matters to a lane looking one of them up.**

**Twenty-one ids are minted. The §12 table lists seventeen.** Missing rows:
**`ACC-S11`, `ACC-S12`, `ACC-S13`** (all three have cards at p153) and **`ACC-S19`**
(card at p148). §12 opens by promising *"One row per commitment, no exceptions. Every
commitment appears both here and as a card in the section that owns it"* — the
promise holds in one direction only.

**`ACC-S13` is this lane's, and it is one of the four with no register row** — the
money defect. A lane reading §12 for its work would not find it.

Recorded here rather than filed: the count is a property of the whole document and
four lanes are reading it. **Whoever consolidates step 1 should carry this forward.**

---

## 8 · EVERY STATED ABSENCE THIS LANE SAW, QUOTED

| screen | the product's own words | verdict |
|---|---|---|
| 13 step 2 | *"Only a date can be used today. Nothing in the product can yet say which day the next billing cycle begins, so those two options are shown and cannot be picked."* | **honest** — names what it waits on |
| 13 step 2 | *"A date inside a period already billed is refused: bills already sent are never repriced."* | **honest** — a rule, not a gap |
| 14 step 3 | *"Queued only — notifications has no send path, so the channel records intent."* | **STILL TRUE** — notifications has no tables (blueprint §08) |
| 15 stage 1 ×3 | *"Not switched on yet. Upload a file instead."* | **honest** — and it names the alternative, which is what rule 33 asks of an instruction |
| 15 Imports tab | *"Reopening a finished run is not switched on yet. Correct the file and import it again."* | **no ruling defers it → `ACC-S9`, a specification**, and the hold is on the wrong rows (`DEF-CUS-5009`) |
| 17 Decision | *"Nothing matches an applicant to an existing customer automatically. Search for them and link them yourself, so the person whose deposit or arrears may follow them is one somebody has actually identified."* | **honest**, and over rule 33's instruction cap |
| 17 Decision | *"The application never asked what kind of job this is — that is decided here."* | **honest** |
| 13/14 drawn | *"NO STEPPER IS RENDERED …"* (the blueprint's own) | **TRUE, and now settled** — the rail never appears (`DEF-CUS-5071`) |
| 13 drawn | *"The deposit is not worked out again in this version. The amount set at move-in stands."* | a hold with a clock in it — **`ACC-S6`'s shape**; not re-checked here |

---

## 9 · FINDINGS, ROUTED

> ⚠ **STAMPED 2026-09-12 — ROW 1 IS CLOSED AND THIS TABLE STILL READS AS OPEN.**
> `DEF-CUS-5008` is closed **`duplicate`**: it and lane 2's `DEF-CUS-4999` are
> the same two lines of `AccountActions.tsx`, found twice by two step-1 lanes an
> hour apart. Both were repaired by `CR-094-BRC01` step 2 wave B and shipped as
> **`2.237.11`** — the modal now reads **`$247.30`** and pre-fills **`247.30`**
> on `A-10432`, the account measured in §3.1. **§2.4's *money on this screen is
> CORRECT* still holds**; it was always the modal and never the screen.
> The repair is **`CR-094-wave-b-step2.md`** in this folder.
> **Rows 2–7 are UNTOUCHED by that wave** and stand as written.

> ⚠ **STAMPED AGAIN 2026-09-12 — ROWS 2, 3, 4 AND 7 ARE NOW CLOSED `fixed`,
> AND THIS TABLE WOULD STILL HAVE READ AS OPEN.** `CR-094-BRC01` step 2 wave D
> shipped them as **`2.239.4`**: `DEF-CUS-5009` (the import fix now sits on the
> runs that HAVE rejected rows, and `ACC-S9`'s hold ships with the test that
> fires when it is built), `DEF-CUS-5010` (eight keys in all eleven catalogues,
> and the stored `lookup_found` key resolved at two of its three render sites),
> `DEF-CUS-5011` (the chip reads `Show: Open` and `All` means all) and
> `DEF-CUS-5071` (both wizards on the shared `WizardFrame`, so 10 of 11).
> The repair is **`CR-094-wave-d-step2.md`** in this folder.
>
> **Rows 5, 6, 8, 9, 10, 11 and 12 are UNTOUCHED** and stand as written —
> `DEF-GOV-5012`, `DEF-CUS-5070`, the two `ACC-S` builds, `OQ-CUS-1790` and the
> two recorded-not-filed notes.
>
> ⚠ **AND §6.2's COUNT OF EIGHT WAS RIGHT AND INCOMPLETE.** Wave D's own
> whole-tab assertion — *no internal code anywhere in the rendered Decision
> tab*, rather than *is this key declared* — found **four more dotted keys on
> the same tab**, from this file's own test fixture rather than from the
> product: `DEF-CUS-5064`. The eight were the eight; the tab had more.

| # | finding | route | row |
|---|---|---|---|
| 1 | Record payment shows and pre-fills **six decimals** of money; hard rule 2's display half | **MAINTENANCE** | `DEF-CUS-5008` · high |
| 2 | `Fix the rejected rows` is offered only on runs with **no** rejected rows | **MAINTENANCE** | `DEF-CUS-5009` · medium |
| 3 | **Eight** refusal keys declared in **0 of 11** catalogues reach the clerk as dotted keys | **MAINTENANCE** | `DEF-CUS-5010` · high |
| 4 | The requests chip says `All`; the server is asked for `segment=open`; 6 of 8 shown | **MAINTENANCE** | `DEF-CUS-5011` · medium |
| 5 | `CLAUDE.md` says the tooling cannot read a module-tagged id; all six named tools can | **MAINTENANCE** | `DEF-GOV-5012` · medium |
| 6 | The blueprint draws 13, 14 and 15 as as-built and its labels, radios and `?step=` addresses are not the product's | **MAINTENANCE** | `DEF-CUS-5070` · medium |
| 7 | 13 and 14 are the only 2 of 11 wizards with no step rail; the step const is read by a test and nothing else | **MAINTENANCE** | `DEF-CUS-5071` · medium |
| 8 | **Reopening a finished import run to fix its rejected rows** | **BUILD** (`ACC-S9`) | no ruling defers it |
| 9 | **A request's five outcomes link to the job they raise, both ways** | **BUILD** (`ACC-S21`) | `outcome_ref` already carries half of it |
| 10 | The requests list opens on the **oldest**, against `BR-CUS-1046` | ⚠ **PO — collision** | **already asked: `OQ-CUS-1790`** (lane 1, OPEN). Nothing re-asked — law 13 |
| 11 | Three payment-plan labels exceed B14 rule 33's 3-word cap | recorded, not filed | §2.3(c) — unenforced, pre-existing |
| 12 | §12 lists 17 of the 21 minted `ACC-S` ids | recorded, not filed | §7 — belongs to the consolidation |

**Nothing here resolves an open question by choosing a value, and nothing files a
registered refusal as a defect** — `customers.paymentPlan.queueOnly` and the three
import source holds were checked against the register and left alone.

---

## 10 · WHAT WOULD SETTLE WHAT THIS LANE COULD NOT

* **The change-plan cost preview's rendered precision.** Click *On a date I choose*,
  fill `#effective_on`, press `Show what it costs`, and read the four preview rows.
  Expected correct: all 11 money sites in that file go through `MoneyCell`.
* **How screens 16 and 17 are drawn.** Pages 75–85, which are lane 3's.
* **Whether the oldest-first queue order stands.** `OQ-CUS-1790`, and only the PO.

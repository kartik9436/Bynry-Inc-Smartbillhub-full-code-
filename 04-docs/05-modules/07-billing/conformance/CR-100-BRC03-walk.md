# Billing — THE WALK. Every screen a clerk can reach, opened with real rows behind it

`CR-100-BRC03` step 1 · walked 2026-09-14 · product version **`v2.261.4`** ·
branch `claude/eager-johnson-r0k88b`

**Step 1 measures and classifies. Nothing here was fixed.** No `.tsx` and no `.py` was
edited by this lane. What it did write: sample data into the demo tenant (named below), three
defect rows, and this file.

---

## ⛔ THE HEADLINE: the blueprint could open 4 of 15 screens. This walk opened all 15.

The blueprint's own cover states what its author could not do:

> **"Partial, front end only.** Chromium 1194 via Playwright against a `vite` dev server at
> 1440×1100. **No backend** — Django is not installed in this environment and there is no
> PostgreSQL, by the user's decision. **So no real row ever reached a screen, and every
> data-shape behaviour went unwalked."**
> **"SCREENS ACTUALLY SEEN: 4 of 15… With nothing stubbed, zero — with three boot reads
> stubbed, four rendered and six threw."**

Measured here, against a live PostgreSQL 16 with a real seeded tenant:

| | Blueprint's walk | **This walk** |
|---|---|---|
| Screens opened | **4 of 15** | **15 of 15** |
| Addresses opened | not stated | **20 of 20**, at **two** widths = **40 of 40** |
| Screens that threw | **6** | **0** |
| Uncaught page errors | not counted | **0**, across all 40 |
| HTTP 4xx/5xx during the walk | n/a (no backend) | **0**, across all 40 |
| Console errors | not counted | **1 distinct**, `net::ERR_CONNECTION_RESET`, on every page; not traced to any billing read |
| Screens with real rows behind them | **0** | **8** (see the table) |
| Widths walked | 1440 only | **1280 and 1440** |

**Every one of the six screens that threw for the blueprint renders here.** That is not a
change in the product — it is what a backend does. It means the blueprint's §09 walk findings
are evidence about a *stubbed front end*, not about this product, and none of them should be
carried forward without being re-walked. **That re-walk is this file.**

---

## ⛔ BILLING HAD NO DATA, AND THAT WAS THE FIRST FINDING

Measured at the start of this lane, with `app.tenant_id` set (RLS `FORCE` is on — a count
taken without it reads **0 for every table** and is the trap this lane fell into once before
writing anything down):

| Table | At lane start | After the repair below |
|---|---|---|
| `invoices` | **0** | **92** |
| `invoice_lines` | **0** | **732** |
| `bill_runs` | **0** | **3** |
| `accounts` | **0** | **72** |
| `customers` | **0** | **49** |
| `payments` | **0** | **74** |
| `meter_reads` | 24 | 516 |

⚠ **`accounts` WAS 0. YOU CANNOT BILL AN ACCOUNT THAT DOES NOT EXIST**, so "run a bill run
against the 24 reads" was not reachable: there was nothing to bill them *to*. The 24 reads
sat against 20 service points and 12 assets with no account, no customer and no agreement
anywhere on the tenant.

**The cause is not a product defect and is worth stating precisely, because the next lane
will hit it too.** `seed_demo` — the command that made this tenant — says so in its own
docstring: *"Reads, customers, bills and payments still grow with their own lanes… nothing
here fakes them."* It seeds W0+W1 only. **The command that seeds the rest is
`manage.py load_sample_data --tenant brazosbend`**, and it had never been run against this
tenant.

**What this lane ran, verbatim:**

```
DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub \
DJANGO_SETTINGS_MODULE=config.settings.local \
python3.12 manage.py load_sample_data --tenant brazosbend
```

**1606 rows written, 1 block declined.** Every row goes through the owning module's own
service seam — this is the product's own repair path (`BR-TEN-064`), not a fixture written by
this lane. The two billed cycles it produced (June, 46 bills; July, 45 bills) are what put
real money on the screens below.

⚠ **THE ONE BLOCK THAT DID NOT LOAD IS AN HONEST REFUSAL AND IS NOT A DEFECT.** The command
named it rather than reporting a clean sweep:

> `NOT  One cheque covering three properties of one customer (CR-059 CS-12)  0 row(s)
> [SD-PRECONDITION]` — *"no multi-property cheque was recorded: one of the landlord's three
> properties owes nothing, so a cheque covering all three would be a cheque for less than it
> claims and the tender's own sum check would refuse it… NOT worked around by typing an
> amount: `BR-PAY-1127` makes the parts and the total one arithmetic fact."*

**Also repaired, and it is an environment fault the next lane will hit:** the SPA server was
running with **no `API_PROXY_TARGET`**, so it defaulted to `http://backend:8000`, which does
not resolve in this container. **Every `/api/*` call through `:8080` answered
`502 {"detail":"API unreachable at http://backend:8000: ENOTFOUND"}`** while the SPA itself
served `200`. A walk started in that state would have recorded fifteen broken screens and
every one of those findings would have been false. Restarted with
`API_PROXY_TARGET=http://127.0.0.1:8000`; `dist/` was already current (0 source files newer
than the build), so no rebuild was needed.

---

## What was walked, and how

* **Chromium 1194** via `playwright-core`, resolved through the `createRequire` +
  `resolveChromium()` block copied from `10-scripts/render-checks/`.
* Signed in as `dana@brazosbendutilities.com` (System Admin) at each width, against
  `http://127.0.0.1:8080`, tenant `brazosbend`.
* Per address: page errors, console errors and every HTTP response ≥ 400 captured **verbatim**;
  `h1`; table row count; count of money cells matching `$n.nn`; count of our own bill numbers
  (`BL-YYMM-NNNNNN`) and account numbers (`AC-YYYY-NNNNN`) in the rendered text; a full-page
  screenshot.
* Scripts and raw results are in SCRATCH: `billing-walk.mjs`, `billing-overflow.mjs`,
  `billing-shots/walk-results.json`, and **40 screenshots** in `billing-shots/`.

⚠ **WHY THE ROW AND MONEY COUNTS ARE THERE RATHER THAN A PASS/FAIL.** A screen that opens and
renders an empty table is indistinguishable from a screen that opens and renders a full one,
if all you record is "it opened". **An empty table is not a table that matched.** Every row
below therefore says what actually reached the screen, and the screens where nothing did are
marked **UNJUDGED** rather than counted as a pass.

---

## The 15 screens, walked

Seven route patterns serve them. `rows` / `$` / `bill#` are what rendered at **1440**; the
1280 figures were **identical on every screen** (see the width section).

| # | Screen | Address | Opened | rows | $ | bill# | Real data? |
|---|---|---|---|---|---|---|---|
| 1 | All bills · `BIL-01` | `/brazosbend/billing` | ✅ | 50 | 50 | 50 | **YES** — 50 of 92 bills, paged |
| 1b | All bills, second address | `/brazosbend/billing/all` | ✅ | 50 | 50 | 50 | **YES** — identical to #1 |
| 2 | One-time bill · `BIL-01.one-time` | `/brazosbend/billing/one-time` | ✅ | 0 | 0 | 0 | form, not a list — **JUDGED** |
| 3 | Budget Bills · `BIL-01.budget` | `/brazosbend/billing/budget` | ✅ | 0 | 0 | 0 | form + *"Nobody is on budget billing"* — **UNJUDGED populated** |
| 4 | Fix a bill · `BIL-01.fix` | `/brazosbend/billing/fix` | ✅ | **51** | 51 | 50 | **YES** — a real bill list to correct from |
| 5 | Past billing runs · `BIL-01.history` | `/brazosbend/billing/history` | ✅ | **0** | 0 | 0 | ⛔ **DEF-BIL-5230** — 3 runs exist and it refuses |
| 6 | Run bills 1 · Pick the cycle · `BIL-02` | `/brazosbend/billing/run?step=1` | ✅ | **3** | 0 | 0 | **YES** — the 3 past runs, at the foot |
| 7 | Run bills 2 · Check what we found | `…?step=2` | ✅ | 0 | 0 | 0 | **UNJUDGED** — needs a run in progress |
| 8 | Run bills 3 · Review accounts | `…?step=3` | ✅ | 0 | 0 | 0 | **UNJUDGED** — needs a run in progress |
| 9 | Run bills 4 · See the totals | `…?step=4` | ✅ | 0 | 0 | 0 | **UNJUDGED** — needs a run in progress |
| 10 | Run bills 5 · Confirm & sign off | `…?step=5` | ✅ | 0 | 0 | 0 | **UNJUDGED** — needs a run in progress |
| 11 | Run bills 6 · Send them out | `…?step=6` | ✅ | 0 | 0 | 0 | **UNJUDGED** — needs a run in progress |
| 12 | Waiting to be billed · `BIL-06` | `/brazosbend/billing/pending` | ✅ | 0 | 0 | 0 | empty state is **TRUE** — see below |
| 13 | Print bills · `BIL-07` | `/brazosbend/billing/print` | ✅ | 0 | 0 | 0 | **YES** — reads *"91 bills · about 1.1 seconds"* |
| 14 | Bill detail · `BIL-05` | `/brazosbend/billing/bills/{id}` | ✅ | 2 | 4 | 1 | **YES** |
| 15 | Bill document · `BIL-05.document` | `…/{id}/document` | ✅ | 9 | 0 | 4 | **YES** — the frozen document, in full |

**The bill detail's four tabs**, walked separately because the blueprint draws each as its own
entry and they are the only screens the PO has ever seen with real data:

| Tab | Address | Opened | rows | $ | Real data? |
|---|---|---|---|---|---|
| Document (default) | `?tab=document` | ✅ | 2 | 4 | **YES** |
| Charges | `?tab=lines` | ✅ | **17** | **29** | **YES** — the full charge table |
| Corrections | `?tab=chain` | ✅ | 0 | 0 | **UNJUDGED** — this bill has no correction |
| Audit | `?tab=audit` | ✅ | 1 | 0 | **YES** — one recorded event |

### Counts, as asked

* **Screens opened: 15 of 15.** Addresses opened: **20 of 20**. At **both** widths: **40 of 40**.
* **Screens that threw: 0.** Uncaught page errors: **0**. Failed HTTP requests: **0**.
* **Screens with real rows behind them: 8** — All bills (×2 addresses), Fix a bill, Run step 1,
  Print bills, Bill detail, Bill document, Charges tab, Audit tab.
* **Screens I could NOT judge: 7** — the five middle run-wizard steps (2–6), Budget Bills in its
  populated state, and the Corrections tab. **Each is named with its reason below.**
* **Defects filed: 3** — `DEF-BIL-5230`, `DEF-BIL-5231`, `DEF-BIL-5232`.

---

## What I could NOT judge, and exactly why

**Say plainly what you did not see.** These are absences of evidence, not passes.

1. **Run-wizard steps 2–6 (five screens).** Each opened, drew its own heading, its step
   number (`Step 4 of 6 · What broke`) and the six-step rail — so the **routing, the phase map
   and the chrome are judged and correct**. What is **not** judged is every one of them with a
   run in flight: a run must be *started* from step 1 and carried forward, and starting one is
   a **write** on the money path. Step 1 of this lane's brief forbids that, so it was not done.
   **A step-2 lane must drive a real run through all six steps before any of these five is
   called conforming.**
2. **Budget Bills, populated.** The screen renders its enrol form and its list, and the list
   says *"Nobody is on budget billing."* `load_sample_data` seeds a **payment plan** (5 rows)
   but no budget-billing enrolment, so the populated list has still never been seen by anybody.
3. **The Corrections tab.** The bill walked (`BL-2608-000058`) has no correction, so the tab
   correctly renders nothing. **One corrected invoice does exist on this tenant** (`invoices`
   holds 91 `issued` + **1 `corrected`**) — walking the tab on *that* bill is a cheap and
   worthwhile next step, and this lane did not do it.
4. **The pending queue with rows in it.** Its empty state is **TRUE, not broken** — verified
   twice over: `GET /billing/pending?as_of=2026-09-14` answers
   `counts: {pending:0, escalated:0, prepare:0, breaks:0}`, and all three bill runs report
   `held: 0`. So the screen is right to say *"0 waiting"*. **The populated queue is unwalked.**
5. **Print bills, actually built.** The screen reads the real corpus (*"91 bills · about 1.1
   seconds"*, and 91 is exactly the issued count) and lists the fourteen manifest columns. The
   **Build the print set** button was not pressed — it is a write. `10-scripts/render-checks/
   cr053-print-bills.mjs` already exists to do exactly that and should be run by a step-2 lane.

---

## The money path — walked, and it ties out exactly

**This is the largest thing the blueprint's author could not check at all**, and the bar is
different here, so it was checked against the database rather than eyeballed.

Bill **`BL-2608-000058`**, account `AC-2026-00011`, Kaya Kowalski, service period
2026-07-01 – 2026-07-31. Rendered by the **frozen document** screen (#15) and by the **Charges**
tab, and compared line-for-line with `invoice_lines` and `invoices` in PostgreSQL:

| Line | Qty | Unit | Rate | Amount | Arithmetic |
|---|---|---|---|---|---|
| electric usage tier 1 (0-500 kWh) | 500 | kWh | 0.110000 | 55.00 | 500 × 0.11 = 55.00 ✅ |
| electric usage tier 2 (500-1000 kWh) | 500 | kWh | 0.135000 | 67.50 | 500 × 0.135 = 67.50 ✅ |
| electric usage tier 3 (1000+ kWh) | 2300 | kWh | 0.160000 | 368.00 | 2300 × 0.16 = 368.00 ✅ |
| electric base charge | — | — | — | 12.00 | flat ✅ |
| water usage tier 1 (0-5 kgal) | 5 | kgal | 4.240000 | 21.20 | 5 × 4.24 = 21.20 ✅ |
| water usage tier 2 (5-15 kgal) | 10 | kgal | 6.890000 | 68.90 | 10 × 6.89 = 68.90 ✅ |
| water usage tier 3 (15+ kgal) | 16 | kgal | 8.480000 | 135.68 | 16 × 8.48 = 135.68 ✅ |
| water base charge | — | — | — | 8.00 | flat ✅ |
| Tax Local | — | — | 0.020000 | 14.73 | 736.28 × 0.02 = 14.7256 → **14.73** ✅ |

* Electric rolls to **502.50**; the Charges tab's *What each service cost* prints **$502.50**. ✅
* Water rolls to **233.78**; the tab prints **$233.78**. ✅
* Subtotal 502.50 + 233.78 = **736.28** = `invoices.subtotal` `736.280000`. ✅
* Total 736.28 + 14.73 = **751.01** = `invoices.total` `751.010000`, and **`sum(invoice_lines.amount)` = 751.010000**. ✅
* The Charges tab's *Amount due* panel reads Previous balance `$0.00` · Payments received
  `$0.00` · Current charges `$751.01` · **Total due `$751.01`**. ✅

**Hard rules, checked on what actually rendered:**

* **Rule 2 (money 4 dp, percentages 6 dp, both DISPLAY 2).** Stored `NUMERIC(18,6)` — a lawful
  container per the rule's own carve-out — and every money figure on both screens displays to
  exactly **2**. Currency travels as `USD` beside each amount on the document, never assumed. ✅
* **Rule 3 (consumption always with an explicit unit).** Every usage line carries `kWh` or
  `kgal` on screen and in the row. **No unitless quantity anywhere.** ✅
* **Rule 4 (issued bills take no UPDATE/DELETE).** *Cancel this bill* is rendered and
  **permanently disabled**, which is the blueprint's `NONE — PERMANENTLY DISABLED` and is the
  rule working. ✅
* **Rule 8 (an address lives on `premises` and nowhere else).** The document prints
  *Service address `121 Silver Creek Rd, Silver Creek, TX 78611`* and *Unit `Unit 1`* — the
  unit refining the premises **by label**, the address **derived by walking**. ✅

⚠ **ONE OBSERVATION, DELIBERATELY NOT CALLED A DEFECT.** The document prints unit **rates** to
4 dp (`0.1100`, `4.2400`) while money displays to 2. Hard rule 2 governs money and percentages;
a per-unit price is neither, and **B4 is ❄️ FROZEN** — so a step-2 lane should confirm the
intended display precision **against B4** rather than against this file. This lane changed no
figure and asserts none.

---

## Both staff widths — 1280 and 1440

⚠ **1280 FINDINGS ARE PRODUCT FINDINGS, NOT DRIFT.** The blueprint says so on p2: *"**Desktop
only, on purpose.** Every wireframe here is one 1440-wide window scaled to fit its box as a
unit, never reflowed."* **There is no 1280 drawing to diff against.** The product must still
work there, so it was walked; nothing below is a difference from any drawing.

**Result: clean at 1280.** Two independent measurements:

1. **No horizontal overflow.** A separate measurement (`billing-overflow.mjs`) over **16
   addresses** — the 15 screens plus the Charges tab — at both widths, **32 measurements, 32
   clean, 0 overflowing**. It asked two questions per page, and **only one of them turned out to
   be worth anything**:
   * **`documentElement.scrollWidth > clientWidth`** — reported equal on all 32.
     ⚠ **DO NOT QUOTE THIS HALF. IT IS A CHECK THAT CANNOT FAIL ON THIS APP.** Proved, not
     assumed: re-run at **420px**, where a desktop-only layout must overflow, it *still* reported
     `scrollW=420 clientW=420`. Something clips the document, so `scrollWidth` never grows and
     this test would report clean on a page spilling off the screen. **It is law 7's *incapable
     of failing* shape and it is recorded here so nobody cites it as evidence.**
   * **Count of elements whose right edge passes the viewport's** — **0 on all 32.**
     **This is the half that carries the result, and it was proved able to go RED first**: the
     same 420px run reported **`wideEls=1288`**, naming `div.shell-search`, `input`,
     `a.shell-help` and `svg` at `right=466`/`right=498`. So a zero here is a real zero.
   * **So the claim, stated exactly: on the check that can fail, no billing screen put a single
     element past the viewport at 1280 or at 1440.** Log: `SCRATCH/overflow.log`.
2. **No content is dropped.** Rendered body text is **byte-for-byte the same length at 1280 and
   at 1440 on all 20 addresses**, and every table row count is identical. The layout reflows;
   nothing is hidden, truncated or lost.

**So: zero 1280 defects.** Recorded as a measurement rather than an adjective — the numbers are
in `billing-shots/walk-results.json` and `overflow.log`.

⚠ **AND THE MOST USEFUL THING THIS SECTION PRODUCED IS THE FLAW IT FOUND IN ITS OWN CHECK.**
Half of the overflow test was proved, by running it at a width where it MUST fire, to be
incapable of firing at all. It had already returned 32 green results by then, and every one of
them would have been quoted as evidence. **A check whose green nobody has tried to make red is
not a result** — `CLAUDE.md` law 7, and the habit that caught it is that law's second question:
*what would make this check pass wrongly?* **Anyone extending this walk should red-prove their
measurement at a width, a tenant or a row count where it has to fail, before reporting its
green.**

---

## The three defects, filed before they are cited anywhere

### `DEF-BIL-5230` — Past billing runs refuses over an endpoint that answers · **high** · `built-not-wired`

**Seen.** `/brazosbend/billing/history` renders a single grey panel and nothing else — the
smallest body of any billing screen (586 characters):

> **Past billing runs**
> *"Past billing runs list every run with what it produced and who signed it off.
> **It arrives with the billing run work.**"*

**The billing run work has arrived.** `GET /billing/runs` answered, in this walk:

```
RUN-0002  2026-07-01→2026-07-31  accounts 45  bills_issued 45  held 0  status draft
(null)    2026-06-01→2026-06-30  accounts  1  bills_issued  1  held 0  status issuing
RUN-0001  2026-06-01→2026-06-30  accounts 46  bills_issued 46  held 0  status draft
```

Every field the panel says it is waiting for — *what it produced*, *who signed it off* — is in
that payload or beside it. **And the product already draws these three runs six pixels away:**
the run wizard's step 1 renders a `PAST BILLING RUNS` table with exactly **3 rows**, under the
same tab strip.

**This is hard-won law 2's mirror — a refusal with a clock in it that rotted.** `CLAUDE.md`
names the mechanism exactly: *"a rule with a clock in it… correct the day it is written, and it
rots silently on the day the screen arrives, because landing a screen and releasing the thing
that pointed at it are two acts and only the first feels like the work."* **Nothing could have
caught it**: the panel is static, so every test that mounts it asserts the refusal copy and goes
green *because* the refusal is still there.

### `DEF-BIL-5231` — the header roll-up blanks on five of six tabs · **medium** · `wrong-logic`

**Seen, one click apart, on the same screen:**

| Address | What the header reads |
|---|---|
| `/brazosbend/billing` | *Bills lifetime **92** · Out this cycle Not counted yet · Unresolved from the last run **0*** |
| `/brazosbend/billing/fix` | *Bills lifetime **Not counted yet** · Out this cycle Not counted yet · Unresolved from the last run **Not counted yet*** |

Same header, same tenant, same 92 bills. It blanks on **one-time**, **budget**, **fix**,
**history** and the run wizard.

**The mechanism**, `BillsListPage.tsx:987`:

```
const rollupQuery = useQuery({
  …
  enabled: active === BILLING_TAB_ALL,
});
```

The roll-up rides on the list request, and the list request is only issued on the All-bills tab.
**The header is drawn by `PageHeader` above the tab strip — it belongs to the screen, not to a
tab** — so a clerk watches a figure they were just shown turn into *"Not counted yet"*.

⚠ **AND THE COPY MAKES A CLAIM THAT IS FALSE HERE.** The component's own comment says the
absence means *"we have not counted"* and that this *"is the true one until `GET /invoices`
answers"*. On these five tabs `GET /invoices` is never **asked**. The server answers
`count: 92` on request. The screen tells the clerk the counting has not happened when what has
not happened is the question.

**Escape:** every tab's suite mounts its own tab; nothing compares the header across two of them.

### `DEF-BIL-5232` — Budget Bills asks the clerk to paste a database id · **high** · `design-divergence`

**Seen.** `/brazosbend/billing/budget`, the *Put a customer on budget billing* card:

> **Account**  ·  placeholder: *"**Paste the account's id from its detail page**"*

**B14 rule 31**, ratified by the PO in the words *"no Databse ID on screen - that is a rule"*.
This is past displaying an id: **a UUID is the value the screen instructs a clerk to go and
fetch by hand and type in.**

**And the capability already exists in the same feature folder, one tab away.**
`/brazosbend/billing/one-time` renders, for the same job:

> **Search for the customer** — *"Type at least two characters of a name, account number or
> address."*
> **Customer account\*** — a `Choose an account` select.

**Escape:** no gate in this repo reads rendered output, and B14 rule 31 is RATIFIED and
UNENFORCED. Nothing could have caught it. **The cheapest place to have seen it was the sibling
tab six pixels away that does the same job properly.**

---

## Confirmations — things that are RIGHT, recorded so nobody re-opens them

**A walk that reports only faults tells the next lane nothing about what it can rely on.**

1. **The bill document renders in full, with a checksum.** File name
   `bill/2026/08/AC-2026-00011-BL-2608-000058.html`, size `8.1 KB`, a printed SHA. It states
   *"This is the bill as it was issued on 9/14/2026, 6:14:22 AM. **It has not been rebuilt.**"*
   and separately *"Rebuilt below from this bill's frozen data."* — **the snapshot and the
   re-render are distinguished on screen**, which is the whole point of a frozen document.
2. **The bill detail carries four tabs — Document · Charges · Corrections · Audit — and no
   fifth.** The blueprint's entry **02.5 (`Sent`) is marked `ENTIRELY NEW`**, and this walk
   **confirms it is unbuilt.** That is a build item correctly described, not drift.
3. **`Cancel this bill` is disabled and `Fix this bill` is not** — immutability (hard rule 4)
   expressed as an affordance rather than as an error after the click.
4. **The pending queue's empty state is true**, verified against the endpoint and against
   `held: 0` on all three runs. It is not a broken read.
5. ⚠ **THE 25,000 CEILING ON PRINT BILLS IS LAWFUL AND MUST NOT BE RE-OPENED.** The screen
   prints *"This system builds up to 25000 bills in one go"*, which is below **T5's 40,000**,
   so it looks like an `NFR-5` breach and **is not one.** `MAX_BILLS_PER_PRINT_SET_DEFAULT` and
   `MAX_ACCOUNTS_PER_RUN_DEFAULT` are **deployment settings an operator overrides, with `0` to
   switch the ceiling off entirely** — and `12-governance/02-decision-log.md` (2026-09-01)
   already rules on exactly this, naming it *"a SOFT limit an operator can lift, which is
   exactly what 'design must not hard-limit' permits"* and **"THE COUNTER-EXAMPLE, DONE
   CORRECTLY"**. Recorded here so no later lane files it as a defect and re-asks a settled
   question (hard-won law 13).
   ⚠ **The one thing that IS worth a step-2 eye: the DEFAULT is 25,000 and the top of the
   in-scope tier is 40,000**, so a T5 utility meets it on its first run and must be told to
   change a setting. That is a default-calibration question, not a cap question, and it is
   **not** re-asking the 2026-09-01 ruling.

---

## Copy-budget observations — measured, not filed

**B14 rule 32** gives a screen a description budget of one sentence per section; **rule 33**
caps an instruction at **6 words per sentence** and puts **RATIONALE at ZERO WORDS ON SCREEN**.
Billing's screens carry a great deal of on-screen rationale. Examples, quoted:

* All bills: *"Past-due is not worked out on this deployment, so no bill below is marked past
  due. Whether a bill is paid comes from payments and today's date comes from the utility's own
  clock; until both are wired the server answers 'unknown' for every issued bill."*
* Print bills: a four-bullet *"Before you send this"* block of roughly 200 words, explaining
  CASS/NCOA, why two columns are empty, and what the product does not post.
* Budget Bills: a *"Three things this screen does not do"* panel.
* Run step 1: *"This cycle has no days-to-pay set, so a due date cannot be worked out. Set it on
  the cycle first."*

**Deliberately NOT filed as defects by this lane.** Every one of these is a *stated absence*,
and the blueprint is a **redesign** that redraws these screens end to end — so the words are very
likely already settled by a drawing this lane did not diff against. **Filing them now would
convert a redesign decision into a defect register entry.** They are recorded here so the step-2
lane building each screen rules on them **against the drawing**, and can see the measurement
without re-taking it.

---

## What a step-2 lane should do first

1. **Drive one real bill run through all six wizard steps.** It is the single biggest unwalked
   surface — **five of the seven UNJUDGED screens** are behind it, and the run engine, the
   breaks list and the five-fact sign-off gate have never been seen with rows in them.
2. **Open the Corrections tab on the one `corrected` invoice on this tenant**, not on the bill
   this walk used.
3. **Run `10-scripts/render-checks/cr053-print-bills.mjs`** and open the archive — Print bills
   was judged by what it *says*, never by what it *hands over*.
4. **`DEF-BIL-5230` is the cheapest real fix in the module** — the endpoint answers, the shape
   is already rendered by the run wizard's step 1, and the change is to stop refusing.

## What this file is not

It is not a diff against the drawings — **no drawing was opened by this lane** and no screen
here is called conforming or non-conforming to one. It is a record of **what the product does
today with real rows behind it**, which is the thing the blueprint explicitly could not
establish. Where it contradicts the blueprint's §09 walk findings, **this file was taken
against a running backend and §09 was not.**

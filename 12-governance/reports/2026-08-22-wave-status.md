# Wave status — 2026-08-22 (answers the PO's "wave status?")

**The wave plan itself was presented in chat on 2026-08-21 and never written
into the repo — that was a Law-10 leak, closed by this file.** Sixteen lanes
(W1–W15 + W9a), formed to close CR-020..025 and the findings around them, as
independent as the dependency structure allowed. The PO's standing
instructions over them, verbatim: *"Can you complete all waves on your own -
without asking question to me?"* · *"Ensure all functionalities is tested form
web walkthorugh"* · *"W1 to w14 - all waves - most of the answer you need are
in repo … i want you to complete all waves"* · *"without me"*.

| Wave | What it was | Status 2026-08-22 |
|---|---|---|
| W1 | The import backend — WFL-01 stages 4–5: load, receipt, rollback, run table | **DONE.** First real run found six engine defects (DEF-540..547), all fixed, pins inverted. CR-023 closed 2.31.0. |
| W2 | The import screen — stage 4/5 UI, receipt, run table mounted | **DONE.** Walked in Chromium end-to-end; commit → receipt → rollback point → run table, 0 5xx. |
| W3 | Common areas + unplanned units (BR-MET-101/100) | **DONE.** Migration 0016 backfill; "3 + common" derived from two server numbers; No-plan chip + `f.plan` filter. |
| W4 | CR-024 closure — the unit move | **DONE.** SCW-U-001 moved P-00001 → P-91001 in a real browser; both guards (future date, account acknowledgement) proved live. CR-024 closed 2.31.0. |
| W5 | The gates that missed all of this | **DONE.** G14 re-pointed at r10 with column-heading (169) + explainer (9) ratchets; G40 unmounted-components (baseline 1); G32 refusal keys; G35 version lockstep. |
| W6 | Eligibility becomes real | **CLOSED BY RULING** — PO: *"dont refuse … keep flexibility"*; eligibility stays ADVISORY, the predicate engine is won't-build (CR-022 closed). |
| W7 | Taxes on a plan — staff attach taxes/fees | **DONE.** BR-RAT-113, add-only, migration 0022; mandated-tax detach refused by name and the detach question back to the PO. CR-021 closed. |
| W8 | Contracts on plans | **HELD by the PO** — *"Cr20 - hold on dont proceed"*. Nothing built; rollback free. |
| W9 | The three pricing gaps | **UNBLOCKED AND MOSTLY DONE (2026-08-22) — the PO ruled all three.** **BR-RAT-116** closed OQ-331: a service-scoped tax prices on its own services' lines and a whole-bill discount never shrinks that base — the refusal retired, **$0.89** on the worked bill, golden untouched. **DEF-519 closed:** money stores 4 decimals, percentages 6, both display 2 (PO re-sign; CLAUDE.md hard rule 2 amended, the sweep now asserts the ratified precisions). **BR-RAT-114** (mid-period split, the **$21.00** contract) is building in its own lane now. |
| W9a | The discount stage onto the bill path (DEF-502) | **DONE.** Eight-stage pipeline, R6-before-R7, `discount_treatment` per tax; golden 33/33 before and after. |
| W10 | Engine cutover | **PARTIAL.** Step 5 (size + city-limits into the pricing call) done. Step 1 (recurring/auto_apply) is PO-blocked — it needs a ruling nobody has given. |
| W11 | Journey fixtures (CR-014 — 305 journeys, fixtures missing) | **PARTIAL (2026-08-22), coverage 2 → 16 → 30 → 43 of 52 (+7 refusing by name, 2 not reached).** ROUND 3: **DEF-570** — all four group-4 seeders below were counted as BUILT and had never been RUN (`TypeError: ensure_maple_creek_cohort() takes 1 positional argument but 2 were given`); fixed, and guarded by a signature contract test that reads the builder names out of the seeder's own source. T4-19 (two issued bills due **Mon Sep 28** / **Fri Oct 23** — +70 days, ten whole weeks, the only shift that preserves a weekday), T7-14 (trailing average BILLED at 97.41 + a real back-bill draft at **292.23 = 300.0%**) and T5-04 (a THIRD tenant `maple-ridge`, CAD, proved unreachable from tenant A **under `sbh_rls_probe` — the ORM version was vacuous, because this suite connects as a superuser**) now seed. **The four that needed cohorts of their own are BUILT too — 33 → 37**: T4-11 (WE-1 taxable **221.90** → tax **20.97**, four authority lines), T4-07 (WE-10's **v3 45.10 / v4 47.84** version chain, sewer as percent-of-water), T4-04 (WE-12's four services, every rate checked against its workbook line → **96.26 → 9.10 → 105.36**) and T5-18 (a demand register in **kW** with the cycle deliberately unread). Each names what it cannot seed: WE-1's $5.00 late line (no path assesses a late fee), BR-MET-049's completeness (not built), T4-07's step-1 replay. **Group 6's finance-period family (T5-08 · T5-09 · T6-09) lands too — 37 → 40** on one cohort: June 2026 CLOSED with a recorded export batch, July the earliest OPEN period, and a refusal that protects LE-1's 2026-06-30 cutover entry from auto-forwarding out of a signed book. **DEF-576** filed and fixed on the way: T7-14 had claimed OCTOBER, the month OQ-333's ruling moves the LE-1 book into, and seed_j19 refused — *'the fixture month October 2026 already holds 2 posted entries'*. The durable half is the **fixture-month calendar** plus a cross-cohort test that asserts the OQ-333 destination stays empty. **SEVEN journeys now REFUSE BY NAME** (T4-10 · T4-17 · T4-18 · T5-27 · T5-28 · T7-07 · T7-12) — the surface does not exist — and `--check` counts them APART: *activated 52 · with a WORKING fixture 43 · refusing BY NAME 7 · without any seeder 2*. Counting a refusal as coverage would be DEF-108 in the scoreboard, and a test reads that figure off `--check`'s own output rather than recomputing it. Three of the seven CORRECT the round-2 record: T4-10's *'no template language variants'* was too broad (notification templates have a full category × language axis; the BILL document is what lacks one), and T4-18/T7-12 were filed as DEF-556 dating problems when nothing in the product assesses a late fee onto a bill at all. **Group 5's notification queues land — 40 → 43**: 340 accounts, **680** queued rows, a **2,000**-row drop = four hand-offs at batch size 500. The cohort asserts `held == 0` because `outbound_messages.held` is BR-PAY-018 PAPER SUPPRESSION and not quiet hours — reading the journeys' *'queued-and-held'* as the column would have seeded 680 permanently-suppressed rows and made T7-16 permanently false while every count looked right. **DEF-577** filed: the `unit` number series stood at 102 while units up to U-00420 existed, so creating a unit raises `duplicate key … (unit_no)=(U-00102)` — *Add unit fails on any tenant that has ever imported or been sample-seeded*. CR-014's first story done — all 50 fixture paragraphs read and grouped into six cohort groups (progress record + continuation in the CR). **Group 1** (the flat money ride) BUILT: issued bill proved = 97.41 with four tax lines, live `BL-2608-000049`. **Group 2 UNBLOCKED by OQ-333's ruling** (PO: _"Chang the month if required"_) — J19/J5 stop refusing: the LE-1 book moves its month (+3 → Oct 2026) only where July is already taken, the shift rides one seam so no signed figure is retyped, and the seeder refuses unless the book still foots at **598.69**. **Group 3: 10 of 21** (T4-01 02 03 12 15 16 21 · T5-14 19 · T7-15), each with a dated fixture amendment. **Group 4: 4 of 5** (T4-22 · T7-09 · T5-21 · T5-22) — tenants PROVISIONED through the real service, never constructed. 22 tests, red-proved four ways. Three bugs found in cohort code that had never been RUN (a dead `.account` attribute in two READY checks; an Asset's unit read off a column the product does not have; T4-02 comparing 0.00 to 0.00 and passing). Two defects filed: **DEF-563** (T5-19's paragraph quotes TAMPER $500 against the PO's ruled $250 — a fixture may not settle a doc conflict by overwriting the ruled side) and **DEF-566** (the shared harness stubs an IMPLEMENTED identity seam, so several hundred tests run against a tenant with no owner). Remaining after round 3: **TWO journeys with no seeder — J24 (1,124 accounts) and T5-05 (1,240 invoices)**, not reached and not blocked: both are the 340-account cohort's shape an order of magnitude larger, and the honest statement is that the round ran out of room rather than out of a way. Seven more REFUSE by name and need a story, not a fixture. |
| W12 | Signup is broken (CR-017 pt 2) | **PARTIAL.** The two production breakages the PO reported are fixed (DEF-532 whole-app 404 after a bare `/premises` back link; DEF-533 sign-out stranded on the wrong tenant's signin with lying copy). DEF-539 (signup draft lost on any reload) filed, fix pending. The deployed-signup evidence itself needs the PO's deployed environment — blocked on a deploy, said once here, not re-asked. |
| W13 | Notifications last mile (CR-009's blocker) | **DONE.** SET-12D's cards became editors; OQ-332 minted for the variant half. |
| W14 | Tailwind (CR-018 — the remaining hand-written CSS files) | **ROUND 1 DONE (2026-08-22).** 12 stylesheets migrated and deleted, 13 commits, **zero visual change and zero defects filed** — G31 declared classes **875 → 811**, ceiling lowered in every removing commit; full frontend suite 1,992 passed. Three deletions were dead code that never reached a browser (a never-imported stylesheet, two zero-caller classes), each said out loud. **Remaining: 24 stylesheets (~7,900 lines)**, of which 3 are blocked on OQ-279's shape (migrating them moves pixels or writes banned arbitrary values) and MoneyCell needs its own pass (class names are load-bearing in ~60 e2e locators). The ordered remainder is written into the CR-018 note. |
| W15 | CR-016 leftovers | **MOSTLY DONE (2026-08-22).** Five defects cleared: **DEF-343** the selected template chip styled NOTHING (`.btn-secondary.active` was never declared — selection now speaks the kit's variant vocabulary, measured accent-filled vs transparent in Chromium); **DEF-344** `.met-danger` deleted, its rest pixels were the kit's danger variant and its hover is now B14 rule 6's; **DEF-352** row-action icons stopped wrapping 2×2, measured 176×32 on one line. **DEF-342 and DEF-345 closed as already-fixed** by earlier commits nobody had closed the rows for. **DEF-307/318 likewise** — their eleven missing keys had been added by the 219-string sweep. Left: DEF-510 (per-list search prompts — needs a `TableConfig` field) and DEF-349 (the shell's second icon vocabulary). |
| — | DEF-527 · adopt r10's explainer copy | **DONE (2026-08-22).** The finding under the finding: r10 never removed the explainers — it restyled them, and G14's extractor only knew r9's spelling, so it reported nine divergences over seven sentences r10 does draw. Extractor fixed, four sentences adopted byte-exact from r10 (three already matched), translated into all ten other catalogues, **ratchet 9 → 2**, proven to bite. The residue of 2 is r10 drawing a KPI grid and no prose on two assets tabs — dropping those explainers is a structure change (BR-SHL-044), so it is the PO's call, printed on every gate run. |
| — | **Master accounts** (OQ-314's second half, PO-ruled this session) | **BACKEND DONE (2026-08-22).** `accounts.kind='master'` — a new column, not a fifth account-type row, because a master account still has a consumer category. `POST /accounts/master` creates it active-and-attached in one transaction; the row anchors on the premises' first common-area unit and covers the rest through `service_agreements`, the same linkage every account uses, no new table. Refuses by name: a non-common-area unit, a deactivated or occupied one, a unit another master already covers, a plan-less common area. MA-1408 is one row with two open agreements = the ruled **$69.60**. 9 new tests, customers suite 132 passed, golden 33/33, isolation 44 passed. **Remaining: the screen half, and bill assembly** — `gather` prices the anchor's services only, so pricing every covered unit onto ONE document is billing-lane work over the linkage now in place. |
| — | **CR-026** · 50k–100k-row imports (raised this session) | **FIRST HALF SHIPPED, second half queued.** ⚠ The cap found by implementing it: BR-MET-038's CONFIRMED **10,000-row cap would have refused every file the PO described** — raised to 100,000 (the PO's own largest number; a cap stays, because an unbounded upload is a denial-of-service door). Writes batched at 1,000 rows. **Measured on 50,000 real rows through the real stages on live Postgres, rolled back after:** extract **6.8s** · transform **77.9s** · validate **50.8s** · dry-run 1.9s · load **101.5s** — 239s total, so three stages still blow a web-request timeout and the background-job half is confirmed by figures rather than argued. |

**Also closed while walking the waves:** CR-025 (stage-1 sample CSV, fast
path, 2.32.0) — and its walkthrough caught two production defects, both fixed
the same commit: DEF-553 (`Accept: text/csv` 400-refused by DRF negotiation
before ANY CSV view ran — S28's *Download the template* had never worked) and
DEF-552 (stage 5's *Roll back this run* still disabled a day after the engine
could honour it; live now on WFL-01 and the run table, and the walkthrough
clicked it: *"Rolled back. 1 reversed · 0 kept"*).

## The seven rulings of 2026-08-22, and what they closed

The PO answered every open question put to them in one round. Each is in the
decision log verbatim with its worked figure; three are already in code.

| Ruling | Figure shown | Landed as |
|---|---|---|
| A bill **splits** at a mid-period rate/plan change | 10 kgal, $2.00 → $2.20 mid-period = **$21.00** | `BR-RAT-114` — lane building |
| Money stores **4** decimals, percentages **6**, display **2** | $0.123456 vs $0.1235 on 100,000 gal = **$12.3456 vs $12.35** | hard rule 2 amended; DEF-519 closed |
| A mandated tax **may** be detached — floor is one tax standing | Texas 6.25% alone on a $100 bill = **$6.25**, refuses; with a city fee, either may go | `BR-RAT-115` — built |
| A tax's base is **service charge + base fees** | electric-only 1.5% on the discounted bill = **$0.89** | `BR-RAT-116` — built, OQ-331 closed |
| **Build master accounts**, in the accounts table | MA-1408 = $41.20 + $28.40 = **$69.60** | `BR-CUS-068` — backend done |
| Table headers stay **12px** | one pixel, product-wide | OQ-267 closed, nothing moved |
| CR-020 contracts stay **held** | — | unchanged |

## What still needs the PO

* ~~**OQ-333 (W11's finding).**~~ **RULED 2026-08-22 and BUILT the same day** —
  PO verbatim: _"Chang the month if required"_. Of the three options put (own
  E2E tenant · re-date the sample slice · move the fixture month) the PO took
  the third, the only one touching no signed figure. J19/J5 now seed: the LE-1
  book moves to October 2026 **where July is already taken, and stays in July
  where it is not**; LE-1's 553.69, its 598.69 and every frozen B5 figure are
  exactly where finance signed them, and the demo tenant is unchanged.
* **BR-RAT-115's scope**, flagged in the review ledger: the floor guards
  *mandated* detaches only; detaching an explicit attachment stays lawful, as
  it already shipped. Raised rather than decided by inference.
* **Two assets explainers** (DEF-527's residue): r10 draws a KPI grid and no
  prose there, so dropping the sentences is a structure change.

**Versions this session:** 2.30.4 → 2.31.0 (CR-023 + CR-024 closed) → 2.32.0
(CR-025 closed) → 2.32.1 (DEF-539) → **2.33.0** (master accounts, W11's
cohort, W14 round 1). Bars at last run: golden **33 PASS / 0 FAIL** with all
8 self-test guards biting; the new backend suites 13/13, customers 132,
isolation 44; frontend **1,992 passed**; G31 875 → 811; G14 explainer ratchet
9 → 2. G15 i18n-parity stays RED at HEAD from other lanes' untranslated
values (1,085 in de.json alone) — not this session's, and every key this
session added is translated in all eleven catalogues.

---

# FINAL STATE — 2026-08-22, end of session (tip `07001ab`, **v2.35.0**)

**Thirteen closed · two part-done and unblocked · one held by the PO.** Bars at
close: frontend **2,007 passed / 118 files**, golden **33 PASS / 0 FAIL** with
all 8 self-test guards biting, `tsc` and `eslint` clean, G31 **0 undeclared**,
G35 lockstep at 2.35.0, G40 at baseline. G15/G18 remain red from work that
predates this session and is named in their own rows.

| Wave / CR | Status | Where it ended |
|---|---|---|
| W1 · Import backend | **CLOSED** | CR-023 @ 2.31.0 |
| W2 · Import screen | **CLOSED** | walked end-to-end |
| W3 · Common areas | **CLOSED** | migration 0016 |
| W4 · Unit move | **CLOSED** | CR-024 @ 2.31.0 |
| W5 · The gates | **CLOSED** | G14 → r10, G40, G32, G35 |
| W6 · Eligibility | **CLOSED by ruling** | advisory, never refuses |
| W7 · Taxes on a plan | **CLOSED** | CR-021; floor widened by the PO's second pass |
| W8 · Contracts on plans | **HELD — PO** | untouched, rollback free |
| W9 · Pricing gaps | **CLOSED** | all three ruled and built |
| W9a · Discounts | **CLOSED** | eight-stage pipeline |
| W10 · Engine cutover | **CLOSED** | BR-RAT-117; found DEF-561 — no charge code reached a bill by EITHER route |
| W11 · Journey fixtures | **PART DONE** | **37 of 52**; the rest itemised with reasons, two describe surfaces the product does not have |
| W12 · Signup | **DONE bar a deploy** | 3 breakages fixed; deployed evidence needs the PO's environment |
| W13 · Notifications | **CLOSED** | SET-12D editors |
| W14 · Tailwind | **PART DONE, unblocked** | 17 stylesheets gone, G31 **875 → 673**; **OQ-337** now holds the remaining five |
| W15 · CR-016 leftovers | **CLOSED** | all seven defects; the last three fixed with browser measurements |
| CR-025 · Sample CSV | **CLOSED** @ 2.32.0 | caught two production defects |
| CR-026 · Big imports | **CLOSED** @ 2.35.0 | 12,000 rows through a real worker; Commit wait **92s → ~2s** |
| Master accounts | **CLOSED** | backend · screens · **the $69.60 bill** |
| DEF-527 · Explainer copy | **CLOSED** | ratchet 9 → 2 |

## The nine PO rulings of this session, and what each one cost to find

Every one is in `02-decision-log.md` verbatim with its worked figure. **Three
of them exposed defects that were invisible until someone tried to implement
them**, which is the argument for building a ruling the same day it is made:

* the import cap — a CONFIRMED 10,000-row limit **would have refused every
  file the PO described** (`CR-026`);
* charge codes — the PO was told a code lands "only if a plan names it", and
  **neither route reached a bill** (`DEF-561`);
* the tax floor — its first version would have refused a detach that removes
  no money at all (`$6.25` either side), caught by an existing test.

## What is open, and who owns it

| | Owner |
|---|---|
| `OQ-337` — name 1.6 / 1.7 / 1.9, or snap them | **PO** — unblocks 5 stylesheets, moves nothing |
| `CR-020` contracts on plans — resume or stay parked | **PO** |
| `DEF-573` — the public "Start free" CTA renders the wrong colour and size, and always has | eng, needs the PO's priority |
| `DEF-574` — two icon strokes, two hamburger sizes | needs a ruling, then a visual walk |
| `DEF-567` — a ratified test figure is red under DEFAULT settings | CR-023's lane |
| `DEF-510` wiring — 14 list screens, one line each | eng; three need a ruling for want of an r10 precedent |
| the human review of CR-026's five statements | **PO** — a human step, and the closure says so |

⚠ **TWO DEPLOY COUPLINGS, both proved by a stale database this session:** the
CR-026 code reads `import_run_progress` and the master-account code reads
`accounts.kind`, so **a deployment that ships either without its migration
fails on every import and on the dashboard respectively.** Both are stated in
their own rollback sections; this is the summary a release reads.

# CR-013 · Plans & Rates — the design, for review and ratification (2026-08-19)

**Why this document exists.** The PO asked, verbatim: *"how many stories, BR, tC, test
data etc - whata re you doing - how are you going to design it - i want to see as product
manager what is your thinking and then enginnering lead what youa re going to do - if you
show me in detail, we can review and ratify it if any issues"*.

So this is written in two voices, deliberately. **Part A is the product argument** — what
the objects are for and how the product decides which of many configured rates applies to
one customer. **Part B is the engineering plan** — schema, stories, business rules, test
cases and data. Part A must be right before Part B matters, so Part A is first and
carries all the worked numbers.

**Nothing here is ratified.** Where a decision is needed it is marked **⟦PO⟧** and
carries its options with figures.

---

## A0 · THE PROMISE THIS DESIGN MUST KEEP (PO, 2026-08-19) — read before judging any choice below

> *"we need to design plans and rates correctly it will be heart of billing and
> configurations. rates are configurable and utility can manage any complex scenarios and
> confgure by themself and also keep records and changes from coompliance point of view is
> what we are promising to Utility user ; hence our design should be robost"*

**Three promises, and each one is testable — so each is written here as the test it must
pass, not as an aspiration.**

**1 · SELF-SERVICE.** *"utility can manage any complex scenarios and configure by
themself"*. The target customer is a 1–2 staff utility with no vendor on call. **The test:
every scenario in A4 — and every structure in part 1 — must be reachable through the
wizards by a person who has never seen the schema.** Concretely, that forbids three things
this design must never fall back on: a rate that only a migration can set, a combination
that needs support to unlock, and a validation refusal that names a field the operator
cannot see. It is also why part 1's *live plain-words read-back of the formula* is not
decoration — it is the only way an operator confirms the maths they just typed is the maths
they meant.

**2 · ANY COMPLEX SCENARIO.** Not *our* scenarios. The six structures (Flat · Tiered · TOU
· Seasonal · Demand+energy · Base only) times connection sizes, seasons, customer classes,
jurisdictions and enrolments is a very large space, and A4 shows three selectors each
moving the answer independently. **The test: the resolution chain must be TOTAL over that
space** — every combination either prices or refuses with a sentence, and *"the product
cannot express that"* is a defect, not an answer.

**3 · COMPLIANCE — THE RECORD IS THE PRODUCT.** *"keep records and changes from compliance
point of view is what we are promising"*. This is the promise that constrains the design
most, and it is why several choices below look conservative:

* **Every issued bill must re-price to the identical figure, forever**, from the versions
  in force for its service period. That single sentence is why DEF-276 —
  `invoice_lines.tariff_version_id` written as NULL on every line ever issued — is the
  highest-priority item in the plan and blocks the claim outright until fixed.
* **Rate history is an audit artefact** (part 4), so in-place edits of an active version are
  refused *even for System Admin*, and a historic typo is corrected by a documented
  correction version carrying a reason.
* **Approval must record what the approver was shown** — which is why A7.6 computes the
  impact figures at SUBMIT and stores them on the version rather than recomputing at
  approval. A figure that moved in between makes the signature cover something nobody saw.
* **A remittance report must recompute identically for any past period**, which is why bills
  store the tax version id, the base amount and the exemptions applied (part 4) rather than
  re-deriving them from today's configuration.

**Robustness here means refusing, not coping.** Every place this design chooses to raise an
exception instead of picking a sensible default — a blank base, a missing schedule, an
ambiguous size row — is that choice: a utility that is told *"this size is not priced"* fixes
it in a minute; a utility silently billed $0.00 finds out in an audit.

---

# PART A · THE PRODUCT ARGUMENT

## A1 · The real problem is RESOLUTION, not configuration

The PO put it exactly: *"we are setting all these rates, but in real only one rate will be
applicable or two or 3 based on how many services; billing logic has to pic up dynamically
which rate to apply out of these many that are set"*.

Silver Creek's catalogue holds **31 priced objects**. A single bill uses a handful. **The
product's core job is the narrowing, and the narrowing is what has to be provably
correct.**

> **⚠ COUNTED FROM THE SEED, 2026-08-19 (PO: *"we have increase this number check out seed
> data"*).** This line read *"7 rate schedules · 13 charge codes · 5 discounts · 6 taxes"*
> — transcribed from r10's fixture summary, not measured. The CR-010 lane counted the live
> seeded tenant: **5 plans · 6 rate schedules · 23 charge codes · 0 discounts · 2 tax rates
> over 5 jurisdictions = 31 priced objects**, and a tenant provisioned at HEAD gets **34**,
> because the five ruled Texas tax rates now seed. **Charge codes went 13 → 23**, which is
> the increase the PO was pointing at.
>
> Two of those numbers change what can be built, not just what is printed. **Discounts are
> ZERO because there is no discounts table in this product at all** (see the R6 note in
> §A2), and that removes a line from two of §A4's four scenarios. The narrowing argument is
> otherwise unaffected — a bigger catalogue makes it stronger.

**The design principle this whole CR rests on:** resolution is a **deterministic narrowing
chain**, not a search. Each step returns **exactly one answer or refuses to bill**. There
is no "best match", no fallback, no default. Ambiguity is a defect that the plan's own
validation gates prevent at activation time — never something the bill run resolves by
picking.

**The seven selectors**, and every one of them comes from somewhere specific:

| # | Selector | Lives on | Chosen when |
|---|---|---|---|
| 1 | **Plan** | the unit (the account derives its plan from the unit) | at move-in / plan change |
| 2 | **Service** | the plan's service set | at plan design |
| 3 | **Effective date** | the service period end date | at run time |
| 4 | **Connection size** | the meter on the unit | at meter install/exchange |
| 5 | **Customer class** | the account | at account creation |
| 6 | **Jurisdiction** | the **premises** (inside/outside city, county) | at premises creation |
| 7 | **Enrolment** | the account (discounts, exemption certificates) | per customer, with proof |

Note **6 is on the premises and 5 is on the account** — they are different objects and a
naive implementation puts both in one place. r10 says it plainly: *"the premise's
jurisdiction flag (inside / outside city) and the account's customer class select which
rows fire."*

## A2 · The resolution chain, in order

> ### ⚠ AMENDED 2026-08-19 — R5 WAS ONE STEP AND IS NOW TWO (PO ruling; EP-RAT-15 lane)
>
> **What this section said until this date**, verbatim, and it was wrong:
>
> ```
> R5  premises jurisdiction → OUTSIDE-CITY MULTIPLIER on base and variable
> ```
>
> That single line folded **two unrelated factors** into one step. **The PO
> corrected it, verbatim:** *"R5 · multiplier from the premises - multiple will
> come form meter; insight city outside city will come from premises and you
> will ahve to add rate cahnges in base charges and rates"* (decision log
> 2026-08-19, *"SIX RULINGS AND ONE CORRECTION OF MINE"*).
>
> | | **Meter multiplier** | **Outside-city factor** |
> |---|---|---|
> | Comes from | **the METER** (the asset) | **the PREMISES** (its jurisdiction flag) |
> | What it is | a metering fact — a CT/PT ratio, a ×10 register | a pricing fact — the utility charges more outside the city limits |
> | What it scales | **the QUANTITY**, before any price is applied | **the MONEY** — base charges *and* rates |
> | Where | **R3b**, before the tiers are walked | **R5**, after pricing |
>
> **Why the conflation is dangerous rather than untidy:** a ×10 register reading
> **62** is **620 kWh**, which lands in **tier 2**; **62** never leaves tier 1.
> Applying the multiplier to the money afterwards prices 62 kWh at tier-1 rates
> and then multiplies by ten — a different, wrong number that looks entirely
> plausible on the document. And the second half of the ruling — *"you will have
> to add rate changes in base charges and rates"* — makes the outside-city factor
> touch **both**, so no implementation applies it to the base alone.
>
> The chain below is the corrected one. `apps/rating/resolution.py` implements it
> and `06-backend/tests/test_cr013_resolution_chain.py` tests the two factors
> **apart**, because a suite that only asserted "the bill got bigger" would pass
> with them swapped.

```
R1  account → unit → PLAN VERSION in force on the service-period end date
R2  plan version → exactly one RATE SCHEDULE VERSION per service     [gate: 1 per service]
R3  meter connection size → the SIZE ROW of each bound schedule      [no row ⇒ REFUSE]
R3b METER MULTIPLIER → billable QUANTITY            (quantity, BEFORE pricing) [unstated ⇒ REFUSE]
R4  plan → CHARGE CODES whose service matches (or Any)
        ∧ whose customer class includes the account's class
        ∧ resolved at the meter's size row                            [no amount ⇒ REFUSE]
R5  PREMISES jurisdiction → factor on base charges AND rates
                                                       (money, AFTER pricing) [unstated ⇒ REFUSE]
R6  account ENROLMENTS → discounts, in stated precedence order, before taxes
R7  taxes whose jurisdiction matches the premises
        ∧ whose services include this line's service
        ∧ whose customer class includes the account's
        applied to lines whose charge code is taxable                 [attach, never chosen]
```

**R3 and R4 refuse rather than default.** That is DEF-277's lesson made into law: a blank
base means *this size is not served*, and billing $0.00 for a size the utility refuses to
serve is a silent wrong answer, not a partial one.

**R3b and R5 refuse too, and each for its own reason.** An unstated meter multiplier is
not 1 (BR-MET-056 stores the factor *used*; a ×10 register whose multiplier nobody
recorded bills a tenth of the consumption). An unrecorded premises where the tenant prices
by jurisdiction is not "inside city" — the factor changes every line, so a guess is a wrong
bill and not a partial one. A tenant who configures **no** factor never consults the
premises at all, so nobody's bills are refused for a flag they never needed.

> ### ⚠ R6 HAS NOTHING TO READ — AMENDED 2026-08-19
>
> **There is no discounts table in this product.** Not *"none seeded"*: the table
> does not exist, and the CR-010 lane counted **zero discounts** on the live
> seeded tenant. CR-013 part 3 (**EP-RAT-12**, about nine stories) owns the
> discount object, the enrolment table, verification, recertification and budget
> exhaustion.
>
> So R6 stays exactly where it is in the order — **before taxes** — and resolves
> to a result that says it is **unmodelled**, never to an empty list. *"This
> product cannot express discounts"* and *"this customer has none"* are different
> facts, and a bill built on the second while the first is true is wrong by a
> discount. It is the same distinction this CR draws everywhere else between an
> em-dash and a printed `$0.00`.
>
> **This changes two of the four §A4 totals** — see the amendment note there.

## A3 · WHERE THE BASE CHARGE LIVES — resolved

The PO ruled: *"it can be in charge code (C) - we can pick up from there"*.

**So: the charge code owns the base amount. One source of truth.** The rate schedule owns
usage math only — tiers, TOU windows, seasons, demand, minimum bill, rounding.

**But r10 draws a `Base / mo` column on RAT-02's rate matrix**, and that column is genuinely
useful — an operator setting tier rates wants to see the base beside them. The resolution:

> **One source, two surfaces.** `BASE-W` (the charge code) owns the amount and is the only
> place it can be edited. RAT-02's matrix **displays** it read-only, attributed —
> `$12.00 · from BASE-W` — with the cell linking to the charge code. The schedule's edit
> mode does not include it. This preserves the drawing and removes the duplication.

**⚠ The failure this prevents, worked.** If both objects carried a base for a 5/8″
residential electric account at 620 kWh:

```
usage 620 kWh × $0.118            =  $73.16
base from the schedule            =  $18.50
base from BASE-E                  =  $18.50
bill                                $110.16     ← base charged twice
```

That is **$23,069.50 per month** across 1,247 connections, and no test catches it, because
both rows are individually correct and only the *rule* makes the total wrong.

**A validation gate enforces the single source:** activating a rate schedule whose service
has no active base charge code — where the plan expects one — is refused, naming the
service. That is CR-013 part 5 step 4's *"flags a bound schedule with no base charge for
that service"*, moved from a warning to a gate.

## A4 · FOUR SCENARIOS, RUN — what resolution actually selects

Same catalogue every time. **The point is how differently the same 31 objects narrow.**

> ### ⚠ AMENDED 2026-08-19 — TWO OF THESE FOUR TOTALS ARE NOT REACHABLE TODAY (EP-RAT-15 lane)
>
> All four arithmetics below were re-derived independently while building the
> fixtures and **all four foot exactly as printed**. Nothing here is a correction
> of the maths. What changed is what the PRODUCT can express:
>
> | | printed here (shown to the PO) | reachable at HEAD | what stands between them |
> |---|---|---|---|
> | **S1** | **$195.60** | **$196.37** | PAPERLESS −$1.00 (no discounts table — EP-RAT-12) · Water Conservation +$0.25 (BR-RAT-036's per-unit tax form is unbuilt) |
> | **S2** | **$286.55** | **$287.32** | the same two |
> | **S3** | **$2,072.71** | **$2,072.71** | — asserted to the cent |
> | **S4** | **$126.19** | **$126.19** | — asserted to the cent |
>
> **Removing the discount is not a subtraction**, which is why S1 is $196.37 and
> not $194.60: the discount sat in the taxable base, so Bexar County moves
> **$3.78 → $3.80** (2.00% × $189.90) and S2's moves **$5.60 → $5.62** (2.00% ×
> $280.85). The City Franchise Fee does **not** move, because its base is the
> electric lines and the discount was never part of them.
>
> **The printed figures stay in this document, verbatim.** They are what the PO
> was shown and they are what these scenarios must produce once EP-RAT-12 and the
> per-unit tax form land. `06-backend/tests/test_cr013_a4_scenarios.py` pins BOTH
> numbers and names every object standing between them, so a scenario cannot
> quietly lose a line and still look right.
>
> **One figure in this section was wrong in the CODE, not in the document.** The
> City Franchise Fee is *"1.5% · Electric only"* and §A4 works it as 1.5% of the
> **electric lines** — $1.82 on S1's $121.10, $21.39 on S3's $1,426.00. The
> engine had no way to express a per-service tax BASE, so "electric only" could
> only be an applicability condition and the fee was computed over the whole
> bill: **$2.83** on S1, **$28.41** on S3 — the city taxing the customer's water
> at its electric franchise rate. `TaxRule.applies_to_services` was added to the
> seam and to `compute_tax` on 2026-08-19 to close it. **No frozen B5 figure
> moves**: every golden fixture states one rate over one combined base, and the
> harness still reads 33/33. ⚠ **That is the DOCUMENT check, not the engine one
> (DEF-2846, 2026-09-01)** — the harness recomputes B4/B5's own figures and
> imports no application code, so it cannot go red when the engine drifts. The
> engine-verified set is `06-backend/tests/golden/`: 14 of the 61 signed GTs.
> `GT-10` (tax base) is one of the 14, so this change IS covered by an engine
> test; most of the range is not.

### S1 · Residential Standard · inside city · 5/8″ water, 1φ 100A electric, sewer · 840 kWh, 11 kgal

```
BASE-E    electric base @ 1φ 100A                 $18.50
USAGE-E   500 kWh × 0.11                          $55.00
USAGE-E   340 kWh × 0.14                          $47.60
BASE-W    water base @ 5/8"                       $12.00
USAGE-W   4 kgal × 3.20                           $12.80
USAGE-W   6 kgal × 4.80                           $28.80
USAGE-W   1 kgal × 7.20                            $7.20
BASE-S    sewer base (flat everywhere)             $8.00
          subtotal                                $189.90
PAPERLESS enrolled                                 −$1.00
          taxable base                            $188.90
          TX State Utility 6.25%      — not applicable (residential exempt)
          Bexar County 2.00%                        $3.78
          PUC fee $0.85 flat (electric)             $0.85
          City Franchise 1.50% (electric only)      $1.82
          Water Conservation $0.25/kgal, Tier 3     $0.25
          TOTAL                                   $195.60
```
**Resolved: 3 of 7 schedules · 5 of 13 charge codes · 4 of 6 taxes.**

### S2 · The SAME account, outside city limits (61 accounts today)

```
BASE-E  $18.50 × 1.5 = $27.75    USAGE-E  ×1.5 = $82.50 + $71.40
BASE-W  $12.00 × 1.5 = $18.00    USAGE-W  ×1.5 = $19.20 + $43.20 + $10.80
BASE-S  $8.00 (flat everywhere — the multiplier does NOT touch sewer)
        subtotal $280.85 · less PAPERLESS $1.00 → taxable base $279.85
        Bexar 2.00% $5.60 · PUC $0.85 · Conservation $0.25
        City Franchise 1.50%  — NOT APPLICABLE, outside city limits
        TOTAL  $286.55
```
**Two things change at once, in opposite directions:** the multiplier raises the bill 48%,
and the franchise fee **disappears**. An implementation that treats "outside city" as one
flag with one consequence gets one of the two wrong. **Resolved: 3 schedules · 5 charge
codes · 3 of 6 taxes** — a different three from S1.

### S3 · Small Commercial · 2″ water, 3-phase TOU electric · 12,000 kWh, 48 kgal

```
BASE-E   @ 3φ                                      $34.00
USAGE-E  2,400 kWh on-peak × 0.22                 $528.00
USAGE-E  9,600 kWh off-peak × 0.09                $864.00
BASE-W   @ 2"                                      $64.00
CAP-W    capacity @ 2" (commercial only)          $120.00
USAGE-W  10 kgal × 4.10 (summer season)            $41.00
USAGE-W  38 kgal × 6.40                           $243.20
         taxable base                           $1,894.20
         TX State Utility 6.25%    APPLIES        $118.39   ← residential-exempt, not commercial
         Bexar County 2.00%                        $37.88
         PUC fee $0.85 flat                         $0.85
         City Franchise 1.50% (electric)           $21.39
         Water Conservation        — not applicable (seasonal schedule has no Tier 3)
         TOTAL                                  $2,072.71
```
**Class changed the tax set, not just the rates.** `CAP-W` appears because the class is
Commercial; TX State appears for the same reason. **Resolved: 2 schedules · 5 charge codes
· 4 of 6 taxes.**

### S4 · Residential Electric-only (well-water homes) · 840 kWh

```
BASE-E $18.50 + USAGE-E $102.60 = $121.10
Bexar $2.42 · PUC $0.85 · Franchise $1.82 · TOTAL $126.19
```
**Resolved: 1 of 7 schedules · 2 of 13 charge codes · 3 of 6 taxes.**

### What the four prove

| | S1 | S2 | S3 | S4 |
|---|---|---|---|---|
| schedules used | 3 | 3 | 2 | 1 |
| charge codes | 5 | 5 | 5 | 2 |
| taxes fired | 4 | **3** | 4 | 3 |
| what moved it | — | premises jurisdiction | customer class | service count |

**Three different selectors each changed the answer on their own.** That is why the chain
must be ordered and total — and it is why the test matrix in Part B is built by *selector*,
not by screen.

## A5 · ⟦PO⟧ THE SCENARIO THE CATALOGUE CANNOT ANSWER — Fire line standby

r10's RAT-01 draws `Fire line standby · Flat · 4 sizes · **— plans** · **22 accounts**`.
A schedule bound to **no plan** and yet billing **22 accounts**. Every other row resolves
through R1→R2 (account → plan → schedule); this one cannot, because there is no plan in
the chain.

Part 1 calls its status *"Standby — availability-only pricing"*. So the product needs one
of:

* **(a)** a plan that carries only the fire-line schedule (22 accounts move onto it) —
  keeps R1→R2 total, costs a plan that exists for a technicality;
* **(b)** a **service-level attachment** that bypasses the plan: the premises has a fire
  line, so the fire-line schedule applies — a second, parallel resolution path;
* **(c)** treat the fire line as a **charge code** (`FIRE` already exists at
  `$14.00–$118.00/mo`, per line size) and delete the schedule — one path, and the drawing
  already has both.

**Recommendation: (c).** `FIRE` is already drawn as a charge code with per-line-size rows,
it needs no usage math (it is availability, not consumption), and it keeps exactly one
resolution path. **(b) is the dangerous one** — a second path that bypasses the plan is
how an account gets billed for something its plan does not contain.

## A6 · ⟦PO⟧ CAN A PLAN OVERRIDE A PRICE? (unchanged from the r10 read-out)

Still open, still the largest question in the CR: part 5 says a plan *"may not override a
rate, add an ad-hoc amount, or exclude a statutory tax"*, and r10 draws per-plan overrides,
waivers, and `+ Apply` / `Mark exempt` buttons on taxes, calling them *"recorded as a plan
exception"*. **The resolution chain above is written for the CR text (no overrides).** If
plan exceptions are ratified, R4/R6/R7 each gain a per-plan override lookup and every
scenario above needs re-running. **This is the single biggest fork in the build.**

## A7 · APPROVAL — where it sits in the workflow

The PO ruled 2026-08-19 that approval is a real gate again. **Placed precisely:**

```
DRAFT ──edit freely──▶ DRAFT
  │
  └─ submit ──▶ PENDING APPROVAL ──approve──▶ SCHEDULED ──effective date──▶ ACTIVE
                      │                                                      │
                      └─ reject ──▶ DRAFT (with reason)          supersede──▶ SUPERSEDED
```

**Six rules, and each answers a question the specs left implicit:**

1. **The gate is on ACTIVATION, never on editing.** A draft is freely editable by anyone
   who may author. Nothing bills from a draft (already law).
2. **Submitting FREEZES the version.** A pending version cannot be edited — editing it
   returns it to DRAFT and clears the approval, because an approval covers what was shown
   (the sign-off rule, applied to the product).
3. **The approver is System Admin** (PO 2026-08-19: *"whenever you see owner consider it as
   system admin"*).
4. **⟦PO⟧ May the submitter approve their own filing?** Silver Creek has 1–2 staff, so
   requiring a second person can make the product unusable for its target customer. Options:
   **(a)** allow self-approval, log it as such — the CR gains an audit trail and no
   deadlock; **(b)** forbid it — correct for a 6-person utility and a hard block for a
   2-person one. **Recommendation: (a)**, with the audit row naming that submitter and
   approver were the same person, so an auditor can see it.
5. **A pending activation appears in the dashboard To-do as `review`** — the PO's own words.
   This is CR-012's To-do panel, so the two CRs meet here.
6. **The impact figures are computed at SUBMIT and stored on the version**, not recomputed
   at approval. An approver must see the numbers the submitter saw; a figure that moved
   between submit and approve makes the signature cover something that was never shown.

## A8 · ⟦PO⟧ THE SECOND-APPROVAL THRESHOLD FOR DISCOUNTS

Four options were put to the PO with figures; **option 3 is recommended and is designed
here pending ratification**: the threshold measures **the budget cap typed on the
discount**, because part 3 step 4 already asks for one, so the figure exists at the moment
of approval and is a **commitment rather than a forecast**.

* One Settings field: **"Second approval required above a discount budget of $X"**,
  default **$10,000**.
* **A discount with NO budget cap always requires the second approval** — unbounded is the
  largest commitment there is.
* Against Silver Creek's catalogue: SENIOR (≈$12,312/yr) and CAP (≈$11,400/yr) would each
  need a second approval; PAPERLESS (≈$7,332) and AUTOPAY (≈$2,383) would not.

## A9 · WHAT THE ACCOUNT MUST CARRY THAT IT DOES NOT TODAY

The PO asked directly: *"do we need to capture any other field on accounts"*. **Yes — two
new relationships, not fields.** Both are required by the specs and neither exists:

1. **Discount enrolment** (part 3). *"Plan attachment makes a discount available, not
   granted"* — so a plan carrying SENIOR does not discount anybody. The account needs:
   which discount, enrolled when, **verification status**, **proof documents**,
   **recertification due date**, lapse behaviour, and lifetime subsidy to date. Without
   this table, either nobody gets a discount or everybody on the plan does — and the second
   is a wrong bill for every account on it.
2. **Tax exemption certificate** (part 4). An exemption is *"a category with a certificate
   and an expiry"*, not a boolean — and *"expired certificates reinstate the tax on the next
   run with no exception raised"*, which is only expressible if the expiry date is stored.

**Two fields also need confirming rather than assuming** — the account's **customer class**
(selector 5) and the premises' **jurisdiction flags** (selector 6). Both are read by the
chain on every line of every bill; Part B's first task is to verify they exist and are
populated, not to assume it.

---

# PART B · THE ENGINEERING PLAN

## B1 · Scope, honestly sized

**16 screens**: 5 landings (PLN-01 + 4 tabs) · 5 detail views (RAT-02, PLN-02, and the one
shell serving charge/tax/discount) · 5 wizards (RAT-03 5-step, CHG-02 3-step, DIS-02 5-step,
TAX-02 4-step, PLN-03 8-step) · PLN-04 (change an account's plan, 3-step).

**Built already** (~8,250 backend lines, 17 frontend files): tier contiguity, TOU 24h
coverage, season coverage, 6-decimal storage, line-level rounding, draft-cannot-bill,
version immutability, the plan and rate wizards in earlier form. **This CR upgrades that;
it does not start from zero.**

## B2 · Seven epics

| Epic | Covers | Stories | New BRs | TCs |
|---|---|---|---|---|
| **EP-RAT-10** Rate schedules | RAT-01 table, RAT-02 detail (5 tabs incl. Billing rules), RAT-03 5 steps, Standby status, Duplicate, derived UoM, impact analysis | 9 | 11 | 34 |
| **EP-RAT-11** Charge codes | CHG-01 columns + hidden GL/outside-city, detail, CHG-02 3 steps, **base-charge ownership**, waiver policy, 5 types | 7 | 9 | 26 |
| **EP-RAT-12** Discounts | DIS-01, detail incl. Enrolled accounts + Budget & usage, DIS-02 5 steps, **enrolment table**, recertification, budget exhaustion | 9 | 12 | 31 |
| **EP-RAT-13** Taxes & fees | TAX-01 + rate calendar, detail incl. Rate history + Remittance + Exemptions, TAX-02 4 steps, **premises scope**, **certificates**, compounding | 8 | 13 | 29 |
| **EP-RAT-14** Plans | PLN-01, PLN-02 (8 tabs incl. Base rates), PLN-03 8 steps, PLN-04, pending-component surfacing | 10 | 10 | 33 |
| **EP-RAT-15** Resolution engine | the R1–R7 chain, refuse-don't-default, the four scenarios as fixtures, `tariff_version_id` on every line (DEF-276) | 6 | 8 | 27 |
| **EP-RAT-16** Approval & versioning | submit/approve/reject, freeze-on-submit, dashboard To-do `review`, second approval, correction versions | 6 | 9 | 22 |
| | **TOTAL** | **55** | **72** | **202** |

**These counts are estimates from the specs, not a promise.** They are given because the
PO asked for them; the honest reading is *"about 55 stories and about 200 test cases"*, and
the first epic authored will tell us how far off the ratio is.

## B3 · Schema — what changes

**New tables (7):**
`discount_enrolments` · `discount_enrolment_documents` · `tax_exemption_certificates` ·
`tax_premises_scopes` · `charge_code_amounts` (per-size rows) · `approval_requests` ·
`rate_calendar_entries` (scheduled statutory changes).

> ### ⚠ CORRECTED 2026-08-20 — THIS LIST OMITTED PER-SIZE TIER RATES (DEF-360)
>
> The line below reads *"+minimum bill per size"* and says nothing about tier
> rates, so **building §B3 exactly as written still could not price r10's 2″
> water row**: every other size prices tiers at `3.20 / 4.80 / 7.20`, and 2″
> prices them at `3.45 / 5.10 / 7.70`. A per-size tier cannot be derived from a
> base, a multiplier or the size — only a row on the schedule can state it.
>
> **Three columns of r10's matrix vary by size, not one**: `base` (the CHARGE
> CODE's, per BR-RAT-088), `min` and the `tier` prices (both the SCHEDULE's).
> The gap was invisible because the whole per-size discussion was framed around
> the BASE — §A3, DEF-277, the per-size base-rate ruling — and once "per size"
> is attached to the base, a per-size TIER reads as a contradiction rather than
> a requirement.
>
> **Built in CR-013 P1** (migration `rating/0010_cr013_p1_size_axis`):
> `charge_code_amounts` · **`rate_size_rows`** (the minimum bill per size) ·
> **`rate_tiers.size_class`**, nullable, where NULL means *every size* so every
> tier written before P1 prices exactly as it did.

**Altered (7):** `tariff_versions` (+status incl. Standby, +docket ref, +uom derived,
+minimum bill per size — **now `rate_size_rows`, see the correction above**) ·
**`rate_tiers` (+`size_class`, DEF-360)** · `charges` (+5-type enum, +waiver policy, +internal description,
+outside-city multiplier) · `discounts` (+budget cap, +exhaustion behaviour, +precedence,
+floor) · `taxes` (+authority, +filing frequency, +due-date rule, +liability GL,
+compounding order, +discount treatment) · `plans` (+`closed_to_new_enrolment`) ·
**`invoice_lines` (+`tariff_version_id` populated — DEF-276)**.

**🔒 Sensitive paths touched** (CLAUDE.md): rating math, money rounding, migration
ordering. Every file flagged `HUMAN-REVIEW-PENDING` with a row in the review ledger, per
G7.

## B4 · The test strategy — built by SELECTOR, not by screen

This is the part that matters, and it comes straight from A4: **three different selectors
each changed the answer on their own**, so the test matrix is the cross-product of the
selectors, not a list of screens.

**Tier 1 · The resolution matrix (the golden set).** Every combination of:
`service count {1,2,3}` × `class {Res, Comm, Indl}` × `jurisdiction {in-city, out-city,
out-county}` × `structure {flat, tiered, TOU, seasonal, demand, base-only}` × `enrolment
{none, one discount, stacked}`. Not all 972 — the **27 that change an outcome**, with S1–S4
above as the first four, each pinned to its printed total to the cent.

**Tier 2 · The refusals.** Each of these must RAISE, not default: no schedule for a service
on the date · size not in the schedule · blank base (DEF-277) · two schedules claiming one
service · effective date inside a closed period · tier gap · TOU not covering 24h · season
not covering the year · a compounding cycle · automatic enrolment with mandatory proof.
**Every one proved RED first** (hard-won law 7).

**Tier 3 · Immutability and versioning.** An issued bill re-priced from its stored version
ids returns the identical figure; editing an active object creates a version and never
touches the old one; a historic version is read-only forever.

**Tier 4 · The browser walkthrough** — the PO's closure bar. 16 screens, each walked. **⚠
Evidence by route + heading text, not screen ID**: r10's own ID mapping is broken for every
detail view and every wizard (see the read-out §2), so screen-ID evidence will not line up.

**Test data.** One seeded tenant is not enough for Tier 1 — the matrix needs an
out-of-county premises, a commercial account with a 2″ meter, an industrial demand account,
a fire-line premises, an account with two stacked discounts, and an expired exemption
certificate. **6 new fixture accounts**, each existing to make one selector reachable.

## B5 · Build order — resolution first

1. **EP-RAT-15 first, before any screen.** The engine is what makes every screen mean
   something, and DEF-276 (`tariff_version_id` always NULL) must be fixed before anything
   claims reproducibility.
2. **EP-RAT-11 (charge codes)** next, because base-charge ownership is settled and every
   other object references it.
3. **EP-RAT-10, EP-RAT-13** in parallel (rate schedules, taxes) — independent surfaces.
4. **EP-RAT-12 (discounts)** — needs the enrolment table, which nothing else blocks.
5. **EP-RAT-14 (plans)** last of the objects: it composes all four.
6. **EP-RAT-16 (approval)** threaded through — but its *state machine* lands with EP-RAT-15
   so every object inherits one implementation.

## B6 · The decisions this plan is waiting on

| ⟦PO⟧ | Where | Blocks |
|---|---|---|
| Plan exceptions — can a plan override a price or exempt a tax? | A6 | R4/R6/R7, all of EP-RAT-14, and re-running every scenario |
| Fire line standby — plan, parallel path, or charge code? | A5 | EP-RAT-15's totality claim |
| Second-approval threshold — option 3 as designed? | A8 | EP-RAT-12, EP-RAT-16 |
| May a submitter approve their own filing? | A7.4 | EP-RAT-16 |
| The existing `0.00` base rows — not served, or free? | DEF-277 | the charge-code migration |

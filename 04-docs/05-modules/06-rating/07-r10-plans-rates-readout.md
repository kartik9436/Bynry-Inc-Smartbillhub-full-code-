# r10 · Plans & Rates — the drawing, read out (2026-08-19)

**Why this file exists.** The PO instructed: *"you should look at r10 creens carefully
to understand every aspect of of change"* (2026-08-19). CR-013's five specs were
written FROM this drawing, so anything the drawing shows and the prose omits is lost
unless it is written down. This is that read-out. **Source:**
`05-prototype/r10-2026-08-16/SMARTBillHub.dc.html` (11,477 lines), line numbers cited
throughout.

**Authority order, unchanged:** B14 and the signed decisions win; then CR-013's five
parts (`12-governance/11-change-requests.md`); then this drawing. Where the drawing and
CR-013 disagree, **the disagreement is recorded here and the CR text governs** — except
where the PO rules otherwise. Nothing in this file is a decision.

---

## 1 · THE CONFLICT THAT NEEDS A RULING — the plan CAN price, in the drawing

CR-013 part 5 states the rule the whole CR rests on:

> *"A plan composes; it does not price — it may not override a rate, add an ad-hoc
> amount, or exclude a statutory tax. Different pricing means a different component."*

And part 4: taxes attach *"automatically by jurisdiction and service, never by plan"*.
And part 5 again: taxes in the plan wizard are *"read-only by design"*.

**r10 draws the opposite, in four places, and gives the mechanism a name.**

| Where | What r10 draws | Line |
|---|---|---|
| PLN-03 step 5 · Taxes | buttons **`+ Apply`** and **`Mark exempt`** per tax, plus a **per-plan rate override input** tagged `customized` | 2820-2860, data 10787 |
| PLN-03 step 4 · Charges | a **per-plan amount override input**, tooltip *"Amount on this plan — recorded as a plan exception; the catalog is untouched"*; a **waive** button, tooltip *"Waived: stays on the bill struck through at $0.00. Remove: never appears."* | 2740-2800 |
| PLN-03 step 6 · Discounts | a **per-plan value override** on each attached discount | 10805 |
| PLN-02 · Charges tab | the result rendered: `CONN · ~~$85.00~~ $0.00` with tag **`Waived`**, under column heads **`Catalog · 5/8"`** vs **`On this plan`** | 1061-1074 |

**The drawing legitimises it with a concept the CR never uses: `recorded as a plan
exception`.** PLN-02's header KPI counts them — **`Exceptions 2`, sub `1 waiver · 1 tax
exemption`** — and PLN-03 step 8 lists them from five generated templates (10740-10747):

```
Override    {code} · catalog amount replaced with {value} on this plan
Waived      {code} · appears on the bill struck through, charges $0.00
Tax exempt  {code} · plan is exempt · prints on bill footer and filing packet
Override    {code} · rate replaced with {value} on this plan
Override    {code} · discount value replaced with {value}
```

PLN-02's Taxes tab also draws a **greyed non-applicable row**: *"TX State Utility Tax ·
6.25% · Does NOT apply — residential exempt · recorded as a plan exemption"*, and
CHG-01's Plans tab records the same thing as prose: *"Senior / Low-income · Overridden to
$10.00 on that plan"* and *"Industrial · Waived — capacity charge applies instead"*.

**Why this cannot be settled by a lane.** Part 4 gives the REASON for the prohibition —
a plan that can exclude a tax *"is what stops a mis-configured plan producing an
under-taxed bill"*. That is a money-correctness argument, and r10's `Mark exempt` button
is exactly the thing it forbids. Both readings are coherent; they cannot both ship.
**On the PO's agenda.**

---

## 2 · SCREEN IDS DO NOT LINE UP — and the closure bar depends on them

The PO's standing rule: *"everything should be passed only when web walkthorugh is
confirmed"*. r10's own screen-ID mapping (9203-9211) is contradicted by its handlers, so
**three of five branches are unreachable**:

| Mapping expects | Handler sets | Emitted | Line |
|---|---|---|---|
| `prView === 'rd'` → `RAT-02` | `prView: 'rate'` | **`PLN-rate`** | 10370-10371 |
| `prView === 'pl'` → `PLN-02` | `prView: 'plan'` | **`PLN-plan`** | 10372 |
| `prView === 'cd'` → `CHG-01` | `prView: 'cd'` | ✅ `CHG-01` (all three kinds) | 10477, 10515-10516 |
| `'newrate'` → `RAT-03.n` | `module: 'newRate'` | **never emitted** | 10599 |
| `'newcharge'` → `CHG-02.n` | `module: 'newCharge'` | **never emitted** | 10835 |
| `plansView 'new'` → `PLN-03.n` | `module: 'newPlan'` | **never emitted** | 10600 |

Working IDs: `PLN-01` · `RAT-01` · `PLN-01.charges` · `PLN-01.discounts` · `PLN-01.taxes`
· `CHG-01`. **A walkthrough evidenced by screen ID will not line up for the detail views
or any wizard.** Use route + heading text as the evidence for those.

**Dead handlers, wired with no markup** (do not port, do not treat as lost features):
`openPlanNew`, `backToPlans`, `publishPlan` (toast *"Rate plan saved as draft"*, 9406),
`plans_showNew`, and the inline create-a-charge-inside-the-plan-wizard path
`ncCreate`/`ncNameVal`/`ncAmtVal` (10775-10783, toast *"Charge created and added to the
plan"*). Charge- and tax-wizard handlers are also **defined twice** (10835-10871 and
11375-11409); the markup binds the FIRST copy (`chargePublish`, `taxPublish`).

---

## 3 · WHERE THE DRAWING AND THE CR TEXT DISAGREE

Recorded so no lane "corrects" a correct build back to the drawing, or vice versa.

| Detail | r10 draws | CR-013 says |
|---|---|---|
| RAT-02 tabs | `Overview · Rate matrix · **Billing rules** · Plans · Versions & filings` | part 1: `Overview · Rate matrix · **Worked example** · Plans & accounts · Versions` |
| PLN-02 tabs | **8**: Overview · Rate schedules · **Base rates** · Charges · Taxes · **Discounts** · Eligibility · Versions | part 5: **5**, with Charges & taxes as ONE tab |
| Charge detail tabs | Overview · Amounts · **Applicability** · Plans · Versions | part 2: Overview · Amounts · Where it is used · Versions |
| Discount detail tabs | Overview · Value & rules · Applicability · Plans · Versions | part 3: + **Enrolled accounts**, + **Budget & usage** |
| Tax detail tabs | Overview · Rate & basis · Applicability · Plans · Remittance & filings · Versions | part 4: **Rate history**, **Exemptions**, **Where it applies** |
| Charge types | `Recurring / One-time / **Refundable** / Penalty` (4) | part 2: `Recurring / One-time / **Deposit** / **Adjustment** / **Event-driven**` (5) |
| `Svc` for account-level codes | the literal string **`Any`** | part 2: **`—`** |
| Rate-schedule statuses | `Active / Draft / Standby` — **`Retired` is drawn nowhere** | part 1: + `Retired` |
| Discount statuses | `Active / Draft` | part 3: + `Retired`, + `Suspended-funding-exhausted` |
| Tax statuses | **no status column at all**, and **no rate-calendar strip** | part 4: `Active/Draft/Scheduled/Expired` + calendar strip |
| Plan statuses | `Active / Draft` | part 5: + `Retired`, + `Closed to new enrolment` |
| RAT-03 step 4 | the **`Requires regulator approval`** checkbox — and no impact analysis | part 1: impact analysis **mandatory**, four figures |
| RAT-03 step 3 structures | Seasonal · Flat · Tiered · TOU · Demand — **no `Base only`** | part 1: + `Base only` |
| RAT-03 step 1 | **no `code` field, no docket field** (filing ref is on step 4) | part 1 step 1: both required |
| RAT-03 step 2 | **no bulk helpers**; has `+ Add from registry…` and per-row remove | part 1: `set all`, `increase all by %` |
| RAT-03 step 5 | **one** worked example | CR header: *"worked examples at three usage levels"* |
| RAT-02 versions | no approver column, no bill count | part 1: *"submitter, approver, bill count"* |
| CHG-02 step 3 | six-cell read-back, **no sample bill line** | part 2: *"a sample bill line showing how it reads to the customer"* |
| CHG-02 | no customer class, no internal description; waiver is ONE checkbox | part 2: all three, plus a full waiver policy |
| TAX-02 step 1 | **no matched-premise count** | part 4: *"shows the matched premise count so a wrong boundary is visible before rates are entered"* |
| TAX-02 step 2 | four `Taxable base — include:` checkboxes only | part 4: compounding order, discount treatment, exemption categories, authority rounding |
| Plan wizard steps | **8** | part 5: **8** ✅ — but the **CR-013 HEADER says 4**. Part 5 supersedes the header. |

**⚠ NONE of the four new status vocabularies CR-013 settles is drawn in r10.** The
drawing carries exactly `Active`, `Draft`, `Standby` across all five landings, plus
`Superseded` inside version tables. `Retired`, `Closed to new enrolment`,
`Suspended-funding-exhausted`, `Scheduled` and `Expired` are **spec-only**. That is the
CR being an upgrade, not the drawing being wrong — but a builder checking against r10
will not find them.

---

## 4 · THE NUMBERS — these become test fixtures

**Landing sub-line, identical on all five tabs:** `6 plans · 7 rate schedules · 13 charge
codes · 5 discounts · 6 taxes & fees · effective Aug 1, 2026`

### RAT-02 rate matrix (10399 / 10411) — size · base · min · t1 · t2 · t3 · accounts

```
Water    5/8" · standard residential  12.00 / 18.00 / 3.20 / 4.80 / 7.20 / 802
         3/4"                         14.50 / 21.00 / 3.20 / 4.80 / 7.20 /  64
         1"                           22.00 / 30.00 / 3.20 / 4.80 / 7.20 /  38
         1.5"                         42.00 / 52.00 / 3.20 / 4.80 / 7.20 /   8
         2"                           64.00 / 78.00 / 3.45 / 5.10 / 7.70 /   2
Electric 1φ 100A · standard residential 18.50 / — / 0.11 / 0.14 / 0.19 / 812
         1φ 200A · large residential    22.00 / — / 0.11 / 0.14 / 0.19 / 286
```

### RAT-02 sample bill (10460-10461) — row 0 only, `base + Σ qᵢ·tᵢ`

```
WATER · "Typical family of four · 5/8" · 11 kgal / month", qty [4, 6, 1]
  Base charge                                $12.00
  0–4 kgal kgal priced at Tier 1   4 × 3.20 = $12.80
  Next 6 kgal at Tier 2            6 × 4.80 = $28.80
  Final 1 kgal at Tier 3           1 × 7.20 =  $7.20
  Usage + base before taxes                  $60.80

ELECTRIC · "Typical household · 1φ 100A · 840 kWh / month", qty [500, 340, 0]
  Base charge                                  $18.50
  0–500 kWh kWh priced at Tier 1 500 × 0.11 =  $55.00
  Next 340 kWh at Tier 2         340 × 0.14 =  $47.60
  Usage + base before taxes                   $121.10
```

⚠ **The doubled unit in the first label is what r10 literally draws** — the generator
takes `'0–4 kgal'.split(' · ')[1]` then appends the unit again. Do not "correct" it
without a decision; it is recorded here so a builder knows it is the drawing, not a
transcription slip. The Tier-3 line is omitted when its quantity is 0.

### RAT-02 impact panel (10462-10464)

```
Before  = row-0 formula on catalog values      W $60.80 · E $121.10
After   = same formula on edited values
%       = ((after − before) / before × 100).toFixed(1) + '%'
Revenue = ± '$' + |(after − before) × accounts|   accounts: W 914 · E 1098
```
Only row 0 feeds the panel — editing any other size row moves nothing.

### CHG-01 impact formulas (10533 / 10545 / 10557) — `$86.15` is the shared typical bill

```
charge (BASE-W, o=12.00)  bill  '$86.15 → $' + (86.15 + (n − o))
                          rev   ± '$' + |(n − o) × 915|
tax    (Bexar, o=2.00)    liab  '$' + 294600 × o/100 → n/100     [at o: $5,892]
                          bill  '$86.15 → $' + (86.15 + 84 × (n − o)/100)
disc   (SENIOR, o=15)     cost  '$' + 72 × 86.15 × o/100          [at o: $930]
                          bill  '$' + 86.15 × (1 − o/100)         [at o: $73.23]
```

### The tax Overview's worked base derivation (a three-number fixture)

> *"Of **$342,180** billed in August, **$47,580** of exempt lines (deposits, taps, fees)
> fall out, leaving the **$294,600** base."*

### PLN-02 sample bill (1024-1031) and plan-wizard step 8 (2929-2938)

```
Fixed charges                     $38.50
Usage · electric + water + sewer $142.30
Discounts (paperless)             −$1.00
Taxes & fees                       $6.94
Total                            $186.74
```
Caption differs between the two: PLN-02 reads `840 kWh · 11 kgal`, the wizard reads
`11 kgal · 840 kWh` and drops sewer from the usage line.

### PLN-02 base rates (1053-1055) · plan-wizard running total (10785)

```
5/8" · 1φ 100A  18.50 + 12.00 + 8.00 = $38.50   716 accts
3/4" · 1φ 100A  18.50 + 14.50 + 8.00 = $41.00    58
1"   · 1φ 200A  22.00 + 22.00 + 8.00 = $52.00    68
```
The wizard's footer total counts ONLY `BASE-E 18.5 + BASE-W 12 + BASE-S 8` →
**`$38.50/mo at 5/8"`**. LATE and every other code contribute nothing to it.

### PLN-03 step 7 eligibility figure (2901) — **hard-coded, does not move**

> *"**1,014 accounts** currently satisfy these rules · 233 would not. Accounts outside the
> bounds cannot be moved onto the plan."*

Adding or removing a rule does not change it. Step 8 restates `1,014 accounts qualify`.

### The BASE-W size expansion, drawn on the Charge-codes landing (803)

> *"'Per size' amounts expand against the size-class registry — e.g. BASE-W: 5/8" $12.00 ·
> 3/4" $14.50 · 1" $22.00 · 1.5" $42.00 · 2" $64.00 · 4" $96.00. **Multi-unit master
> meters bill the base once per unit served.**"*

That last sentence is a billing rule stated nowhere in CR-013.

---

## 5 · WHAT THE DRAWING HAS AND THE PROSE DOES NOT

The highest-value category: these vanish if a lane builds from the specs alone.

1. **A `Billing rules` tab on RAT-02 that CR-013 does not have at all** — five rows of
   *rule | value | why*, including `Multi-unit basis · Base × units served · "A master-
   metered 24-unit building pays the base 24 times, usage priced once."` and, for
   electric, `Net metering · Export credits Tier 1 first`. Both are billing law.
2. **A `Base rates` tab on PLN-02** — a per-connection-size table ACROSS services with a
   `Total fixed / mo` column and account counts. Absent from part 5.
3. **A 4-KPI strip on RAT-02** (`Accounts · Plans · Sizes|Service types · July revenue`)
   and on PLN-02 (`Accounts 842` sub `781 inside · 61 outside ×1.5` · `July revenue` ·
   `Services` · `Exceptions`).
4. **The inline-edit surface is NARROWER than the read table.** RAT-02's matrix drops
   `Minimum bill` and `Accounts` in edit mode — base and the three tier rates are the only
   editable cells. Part 1's *"sizes down, components across; inline edit"* implies all.
5. **`Activate` is drawn in the DANGER style** (`Activate v4 from date ✓`), with the
   three-button ladder Activate / Submit for approval / Save as draft. B14 rule 6 territory.
6. **The impact panel's own copy**: *"Saves as v4 — v3 keeps pricing reads before this
   date. Never edits a live version."*
7. **One detail shell serves charge, tax AND discount** — second tab relabels
   `Amounts` / `Rate & basis` / `Value & rules`, and the Remittance tab appears only for
   kinds that have remittance data (tax only).
8. **`data-hidecols="GL,Outside city"`** on the Charge-codes `<thead>` — the ONLY table in
   Plans & Rates carrying it. That is part 2's hidden-by-default rule, drawn.
9. **A column-chooser affordance on every tab**, titled `Choose columns · ↑↓ to reorder` —
   keyboard reorder is a stated interaction.
10. **`CAP discount offset` is a ROW IN THE TAXES TABLE** (GL 4990, remittance `—`), i.e.
    r10 files a discount inside the tax landing.
11. **The `Customer class` cell can hold a rate, not a class**: LATE draws
    `Res 1.5% · Comm 2.0%`.
12. **Registry entries the CR never names**: water `Fire line 2"` / `Fire line 4"`; trash
    `2-yd dumpster` / `4-yd dumpster`; and a demand table seeding a **power-factor penalty**
    (`$0.50/kW below 0.9 pf`) alongside `$0.08/kWh` and `$14.50/kW · 15-min peak`.
13. **PLN-03 step 3 draws an ALTERNATE-schedule mechanism** (`+ Add alternate schedule for
    a service…`, rows labelled `Electric · alternate`) — against part 1's *one active
    schedule per service*.
14. **Concrete billing-option defaults on plan step 6**: `Paper bill carries a charge of
    $2.00` · `Late-fee grace 10 days` · `Deposit rule DEPO-R on poor credit` · `Due date 21
    days after bill`.
15. **The eligibility operator vocabulary**: `is / is not / ≤ / ≥ / in list` over
    `Customer class / Meter size / Jurisdiction / Premise type / Income program / Demand (kW)`.
16. **The "warn and offer the create link" behaviour part 5 asks for is drawn only for rate
    schedules and charges** — *"Don't see the rate you need? Create a new rate schedule — you
    can come back here."* and *"Not listed? Define it in Charge codes →"*. **Never for a
    service with no schedule**, which is the case part 5 step 2 actually names.
17. **The RAT-03 approval checkbox GATES WHICH BUTTON APPEARS on step 5** — `Requires
    regulator approval before it can activate` (default ON) hides `Activate ✓` and shows
    `Submit for approval ✓`. No prose states this wiring, and it is now load-bearing: the PO
    ruled on 2026-08-19 that approval is a real gate again.
18. **`Standby` is drawn ONLY as a fixture pill on RAT-01** — no wizard offers it as a
    selectable status. Same for `Superseded`, drawn only in version tables.
19. **The `Rates in force · v3` toolbar kicker is hard-coded `v3` for BOTH fixtures**, even
    though the Electric fixture's own header kicker says `· v2`.

---

## 6 · EVERY TOAST, VERBATIM (2,200 ms auto-dismiss, `toast()` 8996)

| Toast | Raised by | Line |
|---|---|---|
| `Saved` | `Duplicate` and `Retire` on RAT-02, PLN-02 and CHG-01 (all kinds) | 10390 |
| `Saved as draft v4 · nothing bills until activated` | RAT-02 impact → Save as draft v4 | 10467 |
| `v4 filed for approval` | RAT-02 impact → Submit for approval | 10468 |
| `v4 activates Jan 1, 2027 · 2 plans notified` | RAT-02 impact → Activate v4 | 10469 |
| `Saved as a draft version` | CHG-01 impact → Save as draft | 10591 |
| `Filed for approval` | CHG-01 impact → Submit for approval | 10592 |
| `New version activates on the effective date · plans notified` | CHG-01 impact → Activate | 10593 |
| `Filed for approval · activates when the regulator signs off` | RAT-03 step 5 → Submit | 10651 |
| `Rate schedule created and activated` | RAT-03 step 5 → Activate ✓ | 10658 |
| `Rate schedule saved as draft` | RAT-03 → Save as draft | 10659 |
| `Plan published · ready to assign to accounts` | PLN-03 step 8 → Activate plan ✓ | 10827 |
| `Plan saved as draft` | PLN-03 → Save as draft | 10828 |
| `Charge code created` | CHG-02 step 3 → Save charge code ✓ | 10845 |
| `Charge code saved as draft` | CHG-02 → Save as draft | 10846 |
| `Tax / fee created` | TAX-02 step 4 → Save tax / fee ✓ | 10870 |
| `Tax / fee saved as draft` | TAX-02 → Save as draft | 10871 |
| `Discount saved · available to plans` | DIS-02 step 5 → Activate ✓ | 10520 |

⚠ **DIS-02's `Save as draft` raises NO toast** — it calls `backFromDisc` and exits
silently. The only silent exit in the module, and A18's state law says an action that
changed something must say so.

---

## 7 · THE HELPER PARAGRAPHS, VERBATIM (one per landing tab — customer-facing copy)

**Plans (741):** *"A **plan** is what customers subscribe to — a bundle of rate schedules
and charges per service, with a name customers understand. A **rate schedule** defines the
pricing math; plans reference them."*

**Rate schedules (762):** *"Rate schedules define the pricing math — flat, tiered,
time-of-use, seasonal, or demand — per connection size. Plans bundle them into customer
offerings. Click a schedule for its full matrix."*

**Charge codes (782):** *"Charge codes are the fixed charges, fees, and adjustments plans
carry. Each one declares what it applies to — customer class, connection size, service,
and jurisdiction — and which taxes touch it."*

**Discounts (809):** *"Discounts are overlays defined once and referenced by plans — a
percentage, fixed credit, or behavior reward applied before taxes. Click one for its
rules, verification and versions."*

**Taxes & fees (827):** *"Taxes and franchise fees are computed per bill line, not per bill
— each declares its jurisdiction, which services and customer classes it touches, and
which charge codes are exempt."*

**The taxes landing's `RULE` exception (841):** *"Applicability is evaluated per bill line:
the premise's jurisdiction flag (inside / outside city) and the account's customer class
select which rows fire. Each charge code's 'Taxable' flag decides if a percent tax sees
it."*

# CR-087 — Plans & Rates, redrawn: seven tab merges, a wizard step removed, and twenty-six specifications minted from the absences the screens already stated

**Status:** BUILT · raised 2026-09-08 · shipped `2.233.0` the same day, five lanes
**Supersedes:** nothing signed. Amends `CR-013 part 4` (taxes), `CR-060` and the r10
readouts on layout only — every figure and every money rule is untouched.
**Blueprint:** the whole of this CR is drawn screen by screen in the Plans & Rates
blueprint published 2026-09-08, read of `2.232.0` at `d2d493e4`.

---

## 0 · CAPTURE — the requester's words, verbatim

Raised across one working session, screen by screen, in reply to a wireframe the PO
reviewed one screen at a time. Quoted rather than paraphrased, because a paraphrase of
a PO sentence is how the next agent rebuilds the wrong thing.

> *"cn you simiplify create tax structure - information architecture and allow user to
> edit and define - currently it is littel complicated -how you will ahndle this"*

> *"overview and Remittance & filings - you can merge it in Overview only"*

> *"these should be drop down"* — of the discount Type's five radio buttons, and again
> of the Enrolment pair.

> *"the button duplicate retire and edit as per other screen make it uniform for all
> screen"*

> *"dont show base charge here let user only select the rate schedule; we might have
> multipe base charges so in review we will show the cororect ones"*

> *"user will need add more button - they can select ad nad from the chagre code"*

> *"please note in plan - we dont need these - we have added them in charge code"* — of
> the late-fee block and the deposits block.

> *"can you merge all these into 1 Overview / Rate schedules / Base rates / Charges /
> Taxes / Discounts / Eligibility … there is no point user clicking on 10 thing to
> review the entire plan. - second tab can be units and last tab can be audit"*

> *"this categories are too small and grey colored to be recohnized by user"*

> *"for services - use E and W we have build"*

> *"in case there are any back end related changes - please map it to respect screen
> level details section"*

---

## 1 · CLASSIFY — and the split is deliberately harsh on us

**This CR is a CHANGE. Three things that arrived with it are DEFECTS and are already
filed as such**, because the process says an ambiguous item is a defect and because
filing our own misunderstanding as a "change" quietly converts our error into the
customer's new requirement.

| What | Kind | Where it lives |
|---|---|---|
| Seven tab merges, a wizard step removed, dropdowns, Add buttons, the uniform action set, the review's architecture | **Reversal of a signed layout + UI/copy** | this CR |
| Twenty-six specifications minted from stated absences | **New requirement** | this CR, §5 |
| A rate schedule's minimum is published to the engine and read by nobody | **DEFECT** | `DEF-2446`, open, predates this CR |
| The plan still accepts a late-fee minimum and percentage nothing has read since `CR-078` | **DEFECT** | `DEF-RAT-4660`, filed 2026-09-08 |
| Every address in the wireframe carried no tenant segment | **DEFECT in the document, not the product** | repaired in the blueprint, reported in its own §08 |

---

## 2 · WHAT IS BEING REVERSED — quoted, never summarised

**Nothing signed by finance moves. No ❄️ FROZEN B4/B5 figure is touched.** What is
reversed is layout, and each reversal is a PO ruling of 2026-09-08 recorded verbatim in
`12-governance/02-decision-log.md`.

| Reversed | It used to say | It now says | Ruled |
|---|---|---|---|
| Tax detail tabs | Overview · Plans · Remittance & filings · Audit | Overview · Plans · Audit | *"you can merge it in Overview only"* |
| Plan detail tabs | eight tabs | Overview · Units · Audit | *"no point user clicking on 10 thing"* |
| Tax wizard | four steps | three | the 19-frozen-field line, put to the PO with the figure |
| Plan step 6 | late fee and deposits set on the plan | set on the charge code | *"we dont need these - we have added them in charge code"* |
| Five detail screens | five different action sets | Duplicate · Edit · Retire | *"make it uniform for all screen"* |

⚠ **ONE OF THESE SUPERSEDES AN ARGUMENT MADE THE SAME DAY, BY US.** We argued for keeping
Remittance its own tab — a different job for an outside bookkeeper who never opens the
rest of the product. The PO ruled the other way. Both are on the blueprint page so a
reader can see which won; the practical answer to the bookkeeper is a link straight to
the tax's page.

⚠ **AND ONE RULING WAS ALREADY RULED, WHICH IS OUR FAILURE AND NOT THE PO'S.** *"we
should not have this - we will take it from charge code"*, of the plan's late-fee
minimum and percentage, is `CR-078` / `BR-RAT-1011` of **2026-09-07** — finance
re-signed, shipped as `2.228.0`, and the engine has read both terms off the charge code
since. The PO was asked to decide something this repository had already decided, which
is the exact failure CLAUDE.md law 13 exists to prevent, and the grep that law
prescribes would have found it.

---

## 3 · IMPACT — the ten surfaces

| Surface | What moves |
|---|---|
| **User stories** | `US-RAT-009` (taxes) and the plan-builder stories lose a step and gain the Units tab. None becomes obsolete. |
| **Business rules** | `BR-RAT-088` (base precedence) is **unaffected and re-cited**. `BR-RAT-1011` is unaffected. `BR-RAT-036/042` unaffected. No rule is superseded by this CR. |
| **Build steps / waves** | Order unchanged: charge codes → taxes → rate schedules → discounts → plans. The blueprint runs in that order for the same reason. |
| **Documents** | `A1` screen inventory (the plan and tax tab lists), `04-docs/05-modules/` rating, the r10 readouts. Every one in the same commit as the code. |
| **Code** | `apps/rating` (models, services, selectors, api), `07-frontend/src/features/rating`. 🔒 **`gather.py` is NOT touched** — no pricing path changes. |
| **Test cases** | Every wizard step test in `TaxWizard.test.tsx`, `PlanWizard`, `ChargesTaxes`; the detail-screen action assertions on all five objects. |
| **E2E journeys** | Any journey asserting a four-step tax wizard or an eight-tab plan will fail **correctly**. They are the acceptance test for the merge. |
| **Locale catalogues** | All eleven. Band labels, the new dropdown option sentences, the Units tab, and the removal of the step-6 late-fee and deposit copy. |
| **Open questions — both ways** | **ANSWERS** nothing outright. **RE-OPENS / RAISES:** `PRB-10` (nine per-size block prices billed by nothing) and `PRB-26` (a plan's own billing cycle) have no ruling behind them and are named as such. `OQ-309` (rounding per authority) is untouched and still open. |
| **The demo fixture** | Pine Hill still reads as a coherent utility: the deposit becomes one charge code with two class prices rather than two rows on the plan. **The fixture must be re-seeded, or the plan page will show a deposit that no longer has a home.** |

---

## 4 · WHAT IS ALREADY BUILT AND IS NOW WRONG

* **`TaxWizard.tsx` has four steps** (`TAX_WIZARD_STEPS`). Step 3's fields all stay — they move to the tax's page, which already has the tab that reads them.
* **`plan_penalty_rules` and `plan_deposit_rules` are still written by the plan wizard.** The ruling moves where a clerk SETS them, not which table stores them. **What reads a deposit once it is a charge code is not answered by this CR and is open.**
* **`late_fee_min` / `late_fee_pct` are validated and served and read by nothing** — `DEF-RAT-4660`.
* **A lane is building on the eight-tab plan page right now.** The PO must be asked whether that lane stops or lands first; this CR does not decide it.
* **Nothing shipped is deleted by this CR.** Every field keeps its column; what moves is which screen collects it.

---

## 5 · SIZE IT, IN PLAIN ENGLISH WITH A FIGURE

**Twenty-six pieces of work, of which one unblocks nine others.**

`PRB-01` is the whole of it: **`charge_code_amounts` is unique on
`(tenant_id, charge_id, size_class)` and carries no customer-class column at all**, so a
$45.00 residential connection fee and an $85.00 commercial one are the same row. One
column, that column inside the unique key, one migration — and until it lands, the class
grid cannot be stored and the review cannot list the bases that apply.

**Not a fast path.** It touches a money table and a migration, so it goes through r11 in
full. The layout half — the tab merges, the dropdowns, the action set — touches no rule,
no money and no data, and **that half is the fast path**.

The twenty-six, and the eleven absences ruled out of scope with their reasons, are the
blueprint's own registers. Every one carries a sentence saying what a person could do
once it is built.

---

## 6 · THE TASKS

| # | Task | Done when |
|---|---|---|
| **A1** | `charge_code_amounts` gains a customer-class column, inside the unique key, with a migration (`PRB-01`) | a clerk types 45.0000 against Residential and 85.0000 against Commercial on one charge code, and a commercial move-in is quoted $85.00 |
| **A2** | The charge-code amount screen draws the class × size grid | the grid saves and reads back; a blank cell is *not served* and a bill for it is refused, never charged $0.00 |
| **B1** | Tax wizard: four steps → three; remittance moves to the tax's page; `effective_from` moves to step 2 | a tax is saved from three steps, and the filing form is entered on the tax's own page afterwards |
| **B2** | Tax detail: four tabs → three, remittance folded into Overview | one page carries what it is, on the bill, what is taxed, who it reaches, remittance |
| **B3** | `GET /taxes/matched-premises` narrows on class and service (`PRB-05`) | ticking Commercial only moves the count from 1,284 to 212 before the clerk leaves the step |
| **C1** | Discount Type and Enrolment become dropdowns; the impossible enrolment pair is refused by the server (`PRB-14`) | a POST setting automatic + proof-required comes back 422 naming both fields |
| **D1** | Plan wizard: multi-select services; the outside-city surcharge takes a **percentage** and the server converts (`PRB-16`) | a clerk types 15, the screen reads *a $100.00 bill outside the city becomes $115.00*, and the stored multiplier is 1.150000 |
| **D2** | Plan step 3 drops the base column; steps 4/5/6 gain Add buttons fed by a filtered catalogue (`PRB-17`) | *+ Add a charge code* on a residential electric plan offers 6 codes, not the utility's 41 |
| **D3** | Plan step 6 loses the late-fee and deposit blocks | a plan saves with neither, and step 8 shows both read-only from the attached charge codes |
| **D4** | Plan step 8 and the plan page become one banded card, in bill order | the same component draws both, and a clerk who checks a plan before publishing recognises the page after |
| **D5** | Plan detail: eight tabs → three; the Units tab and its list read (`PRB-21`) | the Units tab lists a vacant unit reading *base charges still bill to the owner*, paged from the server |
| **E1** | Duplicate · Edit · Retire on all five detail screens, same order, same weight | no screen offers a fourth spelling of Edit |
| **E2** | Band labels read as headings; an absent value is italic and grey; figures right-aligned | a plan with no city tax no longer looks identical to one with a city tax of zero |
| **F1** | Locale keys, all eleven catalogues, written natively | no missing-key warning; G15 does not move |
| **G1** | Tests RED first (law 7), on real PostgreSQL (law 14) | each failure quoted where it was measured |
| **H1** | Version bump (step 7) | **the integrator's act at merge, never in a lane's own branch** — recorded here rather than skipped |

---

## 7 · VERSION — **`2.233.0`**, cut 2026-09-08

Cut at merge, after all five lanes reported, per the PO ruling of 2026-08-26 that step 7
is the integrator's act and not the lane's. Written into the three files that carry it —
`07-frontend/package.json`, `07-frontend/package-lock.json`, `06-backend/pyproject.toml` —
and into `CHANGELOG.md`, where the entry is written for a person rather than for us.

⚠ **`2.232.0` HAS NO CHANGELOG ENTRY.** It is on the branch, cited by this CR's own
blueprint header, and nothing says what it was. Recorded here rather than quietly
skipped over, because a version with no entry is exactly the gap step 7 exists to close.

**Status: the layout half and `PRB-01` are BUILT.** What remains open is named in §5's
registers and in `DEF-RAT-4666` — a charge code priced per connection size still shows no
figure on its own page, only a count, which is `PRB-04` and was never in this CR's task
list.

## 8 · ROLLBACK, STATED BEFORE SHIPPING

**The layout half reverts as one frontend commit.** No data changes shape, no column
moves, and every field keeps the column it has today — a tab merge is a rendering
decision.

**`PRB-01` is the one piece that does not revert cleanly**, and it is additive: the new
column is nullable, and a NULL means *this amount applies to every class*, which is
exactly today's behaviour. Reverting is one migration back; rows written with a class
lose the narrowing and fall back to applying to all, which under-narrows rather than
mispricing. **Nothing is refunded and no issued bill changes**, because
`TAX_RATE_HISTORY_FIELDS` and `BR-RAT-088`'s precedence are untouched by this CR.

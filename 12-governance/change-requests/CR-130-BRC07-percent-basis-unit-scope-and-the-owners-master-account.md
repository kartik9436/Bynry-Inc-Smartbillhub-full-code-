# CR-130-BRC07 — A PERCENTAGE OF ANOTHER SERVICE CAN BE A PERCENTAGE OF ITS MONEY OR OF ITS METER

**Raised:** 2026-09-22 · **Branch:** `claude/laughing-thompson-kpmwih` (`BRC07`)
**Requester:** Product Owner, in the working session, looking at `RAT-03` step 3 on the
`smartbillhub.bynry.com/ottumwa-water-works` build at `v2.322.0`.
**Module:** rating (🔒 money math — B4/B5, `CLAUDE.md` sensitive paths)
**Status:** SIZED AND APPROVED — *"go ahead and start the fix"*

---

## 0 · CAPTURE — THE REQUESTER'S OWN WORDS, VERBATIM

> *"we are setting sewer rates as percentage of utility services. on this screen when we say % of
> service, dont we need to mention which service - Water, electric gas. you ahve given this value.
> now We want to use %age to calculate how much consumption - consumtiom can be charge flat or
> tiered - that is not allowed currently - we also need to create 2 option 5age of charges or % of
> usage - when we say charges - in that case if water charge is $100, and %age is 80% then sewer
> cahrge will be $80; if % of usage then if Water usage will be 100 gallan %age is 80% then sewer
> uage will be 80 gallan = sewer charge will be 80 X { flat rate or tiered rate} - this is how it
> should be done"*

And, on being asked whether the charge basis should be restricted to pairs that make sense:

> *"youa re correct - however dont hard code anything - use logic to derive it so that it is
> flexible and handle any scenario. that the objective. you may want to provide a check for
> tableble or non tablebale in this - all the changes are good"*

**Their two worked figures, which are the acceptance test:**

| they said | so the product must bill |
|---|---|
| *"if water charge is $100, and %age is 80% then sewer cahrge will be $80"* | **$80.00** |
| *"if Water usage will be 100 gallan %age is 80% then sewer uage will be 80 gallan = sewer charge will be 80 X { flat rate or tiered rate}"* | **80 gallons**, priced through sewer's own flat rate or its own ladder |

---

## 1 · CLASSIFY — ONE CHANGE CARRYING TWO DEFECTS

**The CHANGE** is the charge basis and the tier ladder: two capabilities the product does not have.

**The two DEFECTS were found while sizing it, and they are why the request reads the way it does.**
Both are `CR-081`'s frontend half, which its own lifecycle block records as
*"E=deferred(no-frontend-half; the CONFIG half is S11's %-of-service card, already built)"* — **a
comment claiming a guarantee that is not the guarantee** (hard-won law 1). The card WAS built, for
the DOLLAR basis, three weeks before the basis changed.

* **`DEF-RAT-6145` — the screen describes arithmetic the engine stopped doing on 2026-09-08.** Five
  sentences in eleven catalogues still say *"a percentage of another service's usage charge"* and
  *"the base charge and tax are not included"*. **This is why the PO asked for % of usage as a new
  option: the screen told them they had the other one.** A stale sentence did not merely confuse —
  it produced a change request for a feature that already exists.
* **`DEF-RAT-6146` — a percent schedule cannot be saved from this screen at all.**
  `RateScheduleWizard.tsx:786` sends `{ percent, basis_service }`; `services._validate_structure`
  has required `structure.unit_price` since `CR-081` (`required=True`). The screen has no field for
  it and no place to show its error. ⚠ **REPRODUCE THIS IN A BROWSER BEFORE FIXING IT** — it is read
  from the code and has not been clicked.

---

## 2 · WHAT SIGNED STATEMENT IS BEING REVERSED

**NOTHING IS REVERSED. THIS IS ADDITIVE, AND GETTING THAT WRONG WOULD MOVE SIX RE-SIGNED FIGURES.**

`BR-RAT-015` was ❄️ SUPERSEDED on 2026-09-08 by `CR-081`: sewer moved from a percentage of water's
MONEY to a percentage of water's VOLUME, and the PO re-signed six frozen figures under
HUMAN-GUIDE §6, verbatim — *"C — factor 90%, rate $5.00 → $36.00, which is what a real sewer
customer actually pays"*.

**This CR does not undo that. It puts the dollar basis back BESIDE it as a choice.**

| | stays exactly as signed |
|---|---|
| **GT-17 (= WE-1)** | water 8 kgal · sewer 90% × 8 = 7.2 kgal × $5.0000 = **$36.00** |
| **GT-20 (WE-4)** | sewer **$54.00** on 12 kgal |
| **GT-25 (WE-9)** | **$27.00** on 6 kgal |
| **GT-26 (WE-10)** | **$27.00** per half |

**Every existing schedule is migrated to `usage` explicitly**, by name and not by default, so no live
bill moves. A schedule that silently changed basis would move real money on a real customer.

**The charge basis needs its OWN worked figure**, put to the PO in plain English (HUMAN-GUIDE §6,
`CLAUDE.md` sensitive-paths rule), because it is a money path with no golden test behind it. It does
not re-open the six above.

---

## 3 · THE WIRE CONTRACT — BOTH HALVES BUILD TO THIS

Written here rather than discovered twice, because the backend and frontend halves are built by
different lanes and a contract agreed in two places is a contract that drifts.

### The stored shape

`tariff_versions` gains **one** column:

```
percent_basis  TEXT  NOT NULL DEFAULT 'usage'   -- 'usage' | 'charge'
```

⚠ **NO SECOND COLUMN FOR THE RATE, AND NO `rate_shape` FLAG.** `BR-RAT-032` already says one price
is ONE 0→∞ `rate_tiers` row, and that is how `flat` and today's `percent_of_service` both store it.
**Flat versus tiered is how many blocks there are** — one unbounded block is flat, several is a
ladder — so there is exactly one representation of "one price" in the product and nothing new to
keep in step.

### The request payload, `structure` object

| field | when | meaning |
|---|---|---|
| `percent` | always, required | percent points, as today (90 = 90%) |
| `basis_service` | always, required | the service code this is a percentage OF |
| `percent_basis` | always, **required on a new or edited schedule** | `"usage"` or `"charge"` |
| `tiers[]` | **`usage` only, required** | `{from_qty, to_qty\|null, unit_price}`; one unbounded block = flat |
| `unit_price` | accepted for one block, as today | kept so existing callers do not break |

**`tiers` / `unit_price` on a `charge` basis is REFUSED BY NAME, never ignored.** A percentage of
money needs no price per gallon, and a silently-dropped rate is the shape of `tiers[0]` below.

### What `pricing_inputs` publishes to the engine

| basis | blocks | publishes |
|---|---|---|
| `usage` | 1 | `unit_price` — **unchanged, which is what keeps GT-17 at $36.00** |
| `usage` | many | `tiers: [{upper, unit_price}]`, the same shape `tiered` uses |
| `charge` | — | neither; the plugin reads `basis_amount` |

⚠ **`selectors.py:5244` CURRENTLY READS `tiers[0].unit_price` AND SILENTLY DISCARDS THE REST.** It
is correct today because nothing can create a second block; **it becomes a silent wrong-money bug
the moment the ladder exists.** Fix it in the same change that opens the door.

### What the engine's second pass supplies

`engine.py:399` already supplies `basis_quantity` and `basis_unit`. It must ALSO supply
**`basis_amount`** — the basis service's usage-charge dollars — which is the field that existed
until 2026-09-08 and was replaced rather than kept. `ModelConfig` still documents it in the past
tense at `contracts.py:332`.

**Both refusals stay, one per basis:** an unavailable quantity refuses on the usage basis, an
unavailable amount refuses on the charge basis, and neither ever answers `$0.00`. *"90% of an
unavailable number is not $0.00"* — a bill that silently forgives a sewer charge is worse than one
that goes to the exception list.

### What the **Based on** list offers — DERIVED, never a named pair

PO ruling 2026-09-22, in the decision log: *"dont hard code anything - use logic to derive it"*.

| basis | the list offers | the logic |
|---|---|---|
| `usage` | enabled services, not this one, **that meter a quantity** | the answer is a quantity in that service's own unit; a service metering nothing has none (hard rule 3) |
| `charge` | enabled services, not this one | the answer is money; anything that can put a usage charge on a bill can supply it |

**No service code appears in any condition, on either half.** *Electric as a percentage of gas* is
not forbidden — it is simply never configured.

---

## 4 · WHAT IS ALREADY BUILT AND IS NOW WRONG

| surface | today | after |
|---|---|---|
| step 3's percent card | percentage, basis, over-100 confirm | + basis choice, + the rate ladder, − the stale help |
| `rating.percentOfService.hint` | *"...another service's usage charge"* | says what the chosen basis does |
| `rating.percentOfService.percentHelp` | *"...the base charge and tax are not included"* | basis-dependent; the tax sentence points at Settings |
| `rating.percentOfService.preview` | *"{{percent}}% of {{service}} usage charges"* | one wording per basis |
| `rating.planSummary.rate.percentOf` | *"{{percent}} of {{service}} usage charges"* | same |
| `rating.percent.confirm_over_100` | *"...the whole of the other service's charge"* | same |
| `percent_of_service.py` docstring | argues the volume basis as the only basis | states both, with the supersession chain intact |

**Eleven catalogues.** `G15` compares catalogues to each other and never code to catalogue, so a key
added to `en.json` alone renders as a raw key on ten languages and no gate says so.

---

## 5 · THE TAXABLE HALF — ANSWERED, NOT BUILT

The PO asked for *"a check for tableble or non tablebale"*. **It is not being built on the rate
schedule**, and the reasoning is recorded in full in the decision log of 2026-09-22. Two independent
reasons:

1. **It already exists on the TAX** — `taxes.applies_to_services` is a per-tax list of the services
   a tax reaches, read by `resolution.py`, whose own note says it *"also NARROWS THE BASE"*. A
   second switch on the schedule is a second place that can disagree about one fact, which is this
   repo's own `$12.00`-billed-as-`$24.00` failure.
2. **It would move signed law.** Every plugin emits its usage line `taxable=True` citing **B4.2**,
   ❄️ FROZEN: *"tax base = usage + base charge only"*. Taxability is a property of the line's KIND.

**What ships instead is one sentence of screen copy** naming where taxability is decided, so a clerk
looking for the switch is sent to Settings rather than concluding there is none.

---

## 6 · EXECUTION

Two lanes, one contract (§3). **Wave A is the money path and is 🔒** — `HUMAN-REVIEW-PENDING` with a
row in `12-governance/09-human-review-ledger.md`, per `CLAUDE.md`'s sensitive-paths rule.

| wave | owns |
|---|---|
| **A · backend** | the column + migration + explicit backfill · both bases in the plugin · the tier ladder · `pricing_inputs` (including the `tiers[0]` discard) · `basis_amount` on the engine's second pass · validation · the derived basis list · the new golden figure + its test |
| **B · frontend** | step 3's card: the basis choice, the rate box, the ladder, the derived **Based on** list, the taxability sentence · the five stale strings in eleven catalogues · the step 5 review line · the plan summary and rate list wording |

**Version:** `allocate.py version --bump change`. **Rollback:** a plain revert plus a migration that
drops the column; every schedule is `usage`, which is today's behaviour, so nothing already billed
changes.

## 7 · ACCEPTANCE — IN A BROWSER, NOT IN A SUITE

1. A sewer schedule saves and activates from step 3 — **it cannot today**.
2. `% of charge`, water $100.00, 80% → sewer **$80.00**.
3. `% of usage`, water 100 gallons, 80% → sewer **80 gallons**, priced flat.
4. The same, priced through a ladder, with the derived quantity going through the blocks.
5. The existing seeded sewer schedule still bills **$36.00** on 8 kgal.
6. **Based on** offers the tenant's services with no service named in any condition.
7. No sentence anywhere still says *"usage charge"* about a usage-basis schedule.

---

# PART TWO — THE UNIT PICKER OFFERS UNITS THIS UTILITY DOES NOT MEASURE IN

**Folded in by PO instruction 2026-09-22** (*"fold it into the same change"*). It is **step 1 of
this same wizard**, it follows the same *derive it from settings* ruling, and it edits the same
file — and two lanes in one file is how this project loses work.

## 8.0 · CAPTURE, VERBATIM

> *"when you show the unit of measure while setting the rates, please use unit of measurement set
> in the settings for that utility. you are not applying filter to it and showing all unit of
> measurements. can you chekc this and tell em what you wil do"*

Screenshot: `RAT-03` step 1 on a **Sewer** schedule at **Ottumwa Water Works**, offering `ccf`,
`day`, `EDU`, `kgal`, `kW`, `kW-DC`, `MMBtu`, `month`.

## 8.1 · THE FILTER IS NOT MISSING. IT HAS NOTHING TO FILTER ON.

`activeUomOptions` applies the server's own rule verbatim — *"a unit is valid for a service when it
is scoped to that service or scoped to none (NULL = 'All services')"* — and `SettingsServicesTab`
and `selectors.uom_scope_filter` are deliberately two copies of one sentence.

**Measured on `apps/tenancy/fixtures/lookup_defaults.json`: 28 seeded units, 9 with NO service
scope** — `kWh`, `kW`, `kgal`, `ccf`, `therm`, `month`, `MMBtu`, `kW-DC`, `day` — **and those nine
appear on every service.** Sewer has exactly ONE unit scoped to it: `EDU`. The screenshot is that
list, faithfully rendered.

## 8.2 · AND THE BIGGER MISS UNDERNEATH IT

`tenant_services` already carries **`primary_uom`, `alt_uom` and `billed_uom`** — what THIS utility
declared it measures THIS service in, set in Settings → Services. **Step 1 never reads them.**

The product checks them only at SAVE, as `BR-RAT-038`'s notice: *"warn now, rating blocked later —
never a silent conversion"*. ⚠ **So the product already knows the right answer for Ottumwa's sewer
and waits until the clerk has chosen wrong to mention it** — which breaks the doctrine
`activeUomOptions`' own docstring quotes: *"Present and unselectable beats absent, and beats
selectable (they would only learn on submit)."*

## 8.3 · WHAT CHANGES

| # | change | where |
|---|---|---|
| 1 | the picker reads **this tenant's declared unit for this service** (`billed_uom`, else `primary_uom`), not only the unit row's scope | step 1 |
| 2 | that unit is **preselected** on a new schedule | step 1 |
| 3 | units the service does not measure in are **present and unselectable, with the reason** — never absent | step 1 |
| 4 | ⚠ **WITHDRAWN 2026-09-22 BY WAVE B — the nine cannot be scoped.** Nothing in `lookup_defaults.json` or in any migration changes | ~~`lookup_defaults.json` + a migration~~ |
| 5 | a unit **already saved** on a schedule stays visible even when out of scope | step 1 — the existing `alreadySaved` escape hatch, unchanged |
| 6 | the save-time mismatch notice **stays** | unchanged — it is the backstop for a script or a replay, which never opens this screen |

⚠ **NO SERVICE CODE IN ANY CONDITION** (PO ruling 2026-09-22, this CR §3).
⚠ **SEED SCOPES ARE FORWARD-ONLY.** A tenant that has already edited a unit row is never
overwritten (`BR-TEN-012`), and no existing schedule's `uom` is changed by this — hard rule 4.

⚠⚠ **ITEM 4 IS WITHDRAWN, AND THE REASON IS WORTH READING BEFORE ANYBODY RE-RAISES IT (wave B,
2026-09-22; the judgment and its figures are in `12-governance/02-decision-log.md`).**
`tenancy.services._derive_uom_service_scope` NULLs any unit **more than one service claims**, on
purpose — *"One nullable column cannot say 'water or gas'"* — so the unscoped units are not an
oversight, they are that rule working. Measured: of the fixture's nine, only **seven** are actually
unscoped in a provisioned database (`kWh` already resolves to electric and `therm` to gas); of those
seven, `kgal`, `ccf` and `kW` are claimed by two or three services each, `month` and `day` are how
ANY service bills a flat or prorated charge, and `MMBtu` and `kW-DC` are each ambiguous between two.
**Scoping `kgal` to water would refuse the very sewer schedule this change request is about** —
`CR-081` widened that scope back on 2026-09-08 for exactly that reason. The whole item would have
moved Sewer's list from **8 units to 7** and cost a refusal on a live schedule to do it.
**Items 1, 2, 3, 5 and 6 are what was reported and are what shipped.**

⚠⚠ **AND §8.2's SENTENCE ABOUT THE SAVE-TIME NOTICE IS FALSE FOR THE SERVICE IT WAS WRITTEN ABOUT.**
It says the product *"checks them only at SAVE, as `BR-RAT-038`'s notice"*. `uom_gate_for` answers
`no_register` — satisfied, no notice — before either unit is read, whenever the tenant's
`billing_basis` is `share` or `capacity`. **Sewer is `share`.** So on the reported screen nothing
anywhere told a clerk the unit was wrong: not at entry, and not at save. Filed as `DEF-RAT-6152`.

---

# PART THREE — AN OWNER NEVER BECOMES A MASTER ACCOUNT, IN THREE PLACES

**Folded in by the same instruction.** Different module (metering + customers), different files, no
overlap with parts one and two — so it is a separate lane, not a separate change.

## 9.0 · CAPTURE, VERBATIM

> *"next bug is in premises -> mapping master account ; we are unabel to find and map master
> account to premises later; please tell me whether owner and master account are two differnt data
> in your calculations - how are you hadling it and why it is not working. in edit also we are
> unabel to search owner - and owner and master account is confusing we ahve to use one volcabory ;
> in add presmies also we are providing person or company name, ids and documents - but it does not
> create the master account and also not linking that account to premsies - why"*

## 9.1 · THE ANSWER TO THEIR QUESTION: THREE TABLES, ONE IDEA, ONE MISSING WIRE

| table | holds | billable |
|---|---|---|
| `premises` | `owner_id` → an owner record · `owner_manager` → **free text, a name somebody typed** | no |
| `premises_owners` | the **owner record** — a typed party, carrying `master_account_id` | no |
| `customers.accounts` | the **master account**, `kind='master'` | **yes, and only this** |

`BR-MET-400` (PO 2026-08-27) already rules them one idea: *"so premises owner is master accountin
system … Premises -> owner = Master account - it can be existing master account also"*, and
`master_account_id` was added as *"the one missing link"*.

⚠ **THE MODEL IS RIGHT. THE CAUSE IS ONE UNWIRED DOOR, AND IT IS HARD-WON LAW 2 EXACTLY.**
`createPremisesOwner` is defined in `endpoints.ts:6799` and in `metering/api.py:478`, and **is
called by NO screen in the product** — measured across the whole of `07-frontend/src`, test files
excluded. So `premises_owners` can only be filled by the seed or an import, and **all three
surfaces the PO names read from it.** They are not broken; they search a cupboard nobody can put
anything into.

## 9.2 · THE THREE PLACES, FROM THE CODE

| place | what the clerk does | what the code does | why nothing happens |
|---|---|---|---|
| **Add premise** | types a person or company name | it lands in `owner_manager` and nowhere else | `BR-MET-151` clause 3 forbids reading a party's category off a name; `BR-MET-112` forbids a wizard minting an account because a field was filled in |
| | gives SSN, driving licence, tax id, phone | collected, sent | used only when an owner RECORD was picked |
| | expects a master account | `_owner_account_for_premises` reads `owner_id` FIRST: empty → warning `no_typed_owner`, **returns immediately** | no account, no link — **and it is NOT silent; the reason simply never reaches the screen** |
| **Edit premise** | opens **Owner (record)** | a plain dropdown of existing owner records | empty, per §9.1 |
| | reads *"Not listed? Type the name below"* | the name goes to `owner_manager` | **the instruction is a dead end — it names no party and creates nothing** |
| **Premises detail** | presses **Find an owner** | `listPremisesOwners({q})` — searches **owner records** | empty, per §9.1 |
| | is looking for a master account | **it never queries accounts** | an existing master account could never appear, however it is spelled |

## 9.3 · WHAT CHANGES

| # | change | place |
|---|---|---|
| 1 | the name, ids and documents already captured **create the owner record** | Add premise |
| 2 | and then open and link the master account, per `BR-MET-400` | Add premise |
| 3 | the server's existing verdict (`no_typed_owner`, `no_account_type`, `refused`, `already_linked`) **reaches the screen** | Add premise |
| 4 | **Owner** becomes a search that can also **create from what was typed** | Edit premise |
| 5 | **Find an owner** searches **accounts as well as owner records**, so an existing master account can be attached | Premises detail |
| 6 | **one word for one thing**: `Owner` on screen, the account number beside it; *owner record* and *master account* become internal words a clerk never reads | all three, and the list chip |

⚠ **`OQ-790` IS OPEN AND IS NOT RESOLVED HERE** — whether a newly created owner's account is
`master` or `regular` is derived from whether anyone else occupies the premises, and at creation no
unit is occupied. `BR-MET-400` already records that guessing it *"decides who is billed"*. Where the
kind cannot be derived, the screen **asks**; it never picks.
⚠ **`BR-MET-112` IS NOT BEING WEAKENED.** Nothing is written until the last button; what changes is
what that one press writes.
⚠ `owner_manager` is **never dropped** when a record is created — it is what `BR-MET-151` matches on
and the only clue to who an un-typed owner is.

## 9.4 · REPRODUCE FIRST

All of §9.2 is **read from code and has not been clicked.** The reporter has seen it; the lane
must too, on a running copy, before changing a line — `22-product-maintenance-process.md` step 1.

---

# 10 · EXECUTION, ALL THREE PARTS

| lane | owns | files |
|---|---|---|
| **A · rating backend** 🔒 | §3's whole contract — the column, migration, both bases, the ladder, `pricing_inputs`, `basis_amount`, validation, the derived basis list, the new golden figure | `apps/rating/**` |
| **B · rating frontend** | step 3's card **and** part two's step 1 unit picker · the five stale strings · eleven catalogues | `07-frontend/src/features/rating/**`, `features/tenancy/SettingsServicesTab.tsx`, `i18n/**` |
| **C · metering** | part three end to end, all three places + the vocabulary | `apps/metering/**`, `apps/customers/**`, `07-frontend/src/features/metering/**` |

**A and B share one file boundary and no file.** **C shares nothing with either.**

---

# APPENDIX A — WAVE A HAS LANDED: WHAT WAVE B MUST BUILD TO

**Added 2026-09-22 by the rating-backend lane, after building §3.** Nothing above is amended; this
states what the server now does, in the words the two lanes have to agree on. **Lane B: read this
instead of re-deriving §3 from the code.**

## A.1 · The payload, as the server now validates it

`structure` on a `percent_of_service` schedule:

| field | when | server behaviour |
|---|---|---|
| `percent` | always, required | percent POINTS (90 = 90%); `<= 0` refused, `> 100` needs `confirm_percent_over_100` — unchanged |
| `basis_service` | always, required | must be ENABLED, must NOT be this schedule's own service, and on the `usage` basis must be a service the tenant declares it METERS |
| `percent_basis` | **always, required, on create AND on edit** | `"usage"` or `"charge"`. Anything else → `structure.percent_basis` / `rating.unknown_value`. Absent → `structure.percent_basis` / `rating.required` |
| `tiers[]` | **`usage` only** | `[{from_qty, to_qty\|null, unit_price}]`, validated by the same `_validate_tiers` the `tiered` model uses. One unbounded block = flat |
| `unit_price` | **`usage` only**, when `tiers` is absent | required; the server writes it as one 0→∞ block |
| either of the two | **on `charge`** | **REFUSED BY NAME** → `structure.unit_price` / `structure.tiers`, `rating.percent.rate_not_on_charge_basis` |

`GET /rate-schedules/{id}` now serves `percent_basis` on the version row, so reopening a saved draft
reloads the basis the clerk chose rather than redrawing the card on a default.

## A.2 · The **Based on** list — ask the server, do not derive it twice

**`GET /rate-schedules/percent-basis-options?service=<code>&basis=usage|charge`** →
`{"results": [{"code", "name"}, …]}`, in the platform catalogue's own order.

It applies the PO's ruling — *"dont hard code anything - use logic to derive it"* — and **names no
service in any condition**. It exists so the derivation is not written a second time in TSX: the
wizard already holds every enabled service with its `billing_basis`, and hard-won law 2 is precisely
about the front end keeping its own copy of that list.

## A.3 · THREE NEW `message_key`s NEED A SENTENCE IN ALL ELEVEN CATALOGUES — WAVE B OWNS THOSE FILES

The backend raises these today. **Until wave B lands them they resolve to nothing, which means the
refusal reaches a clerk as SILENCE** (`G32`'s own reason for existing), and `G32` counts three more
unresolved keys — 8 → 11 against a baseline of 0. Wave A did not add them because `i18n/**` is wave
B's and two lanes in eleven JSON files is how this project loses work.

| key | field it lands under | the sentence it needs (English; ≤ 6 words per sentence, B14 rule 33) |
|---|---|---|
| `rating.percent.rate_not_on_charge_basis` | `structure.unit_price`, `structure.tiers` | *"A share of a charge needs no rate."* |
| `rating.percent.basis_is_itself` | `structure.basis_service` | *"Choose a different service."* |
| `rating.percent.basis_meters_nothing` | `structure.basis_service` | *"{{service}} is not metered. Choose a metered service, or use % of charge."* |

⚠ **`rating.percent.basis_meters_nothing` carries a `service` param** and is the only one of the
three that does.

### ⚠ A.3.1 · WHAT WAVE B SHIPPED, AND WHERE IT DIVERGES FROM THE TABLE ABOVE (2026-09-22)

**All three keys are in all eleven catalogues.** One is wave A's sentence VERBATIM; **two were
shortened, because measured against the rule this section itself cites they do not meet it.** Run
through `10-scripts/gates/g33_refusal_copy_length.py`, which enforces B14 rule 33's six words per
sentence:

| key | wave A proposed | measured | wave B ships | measured |
|---|---|---|---|---|
| `rating.percent.basis_is_itself` | *"Choose a different service."* | **4 words — fits** | **unchanged, verbatim** | 4 words |
| `rating.percent.rate_not_on_charge_basis` | *"A share of a charge needs no rate."* | **8 words — OVER** | *"Percent of charge needs no rate."* | 6 words |
| `rating.percent.basis_meters_nothing` | *"{{service}} is not metered. Choose a metered service, or use % of charge."* | **9 words in its second sentence — OVER** | *"That service is not metered. Choose one that is."* | 5 and 5 |

**Two further reasons for the third one, beyond the count:**

* **`{{service}}` IS NOT INTERPOLATED, DELIBERATELY.** The server passes `service=basis["code"]` —
  the WIRE code, so a clerk would read *"storm_water is not metered"*. **B14 rule 32 keeps an
  internal code out of clerk-facing copy.** The param is still sent and simply unused; the field the
  refusal lands under (`structure.basis_service`) already says which control is meant.
* **ONLY ONE REMEDY FITS IN TWO SENTENCES.** Wave A offered both — pick a metered service, or switch
  to % of charge. B14 rule 33 allows at most two sentences, so the one kept is the one that matches
  the FIELD the error is attached to. The other remedy is one press away and visible on the card.

**Measured effect on the gate:** G33's over-cap total goes **578 → 574** — the three new refusals
add none, and the re-worded `rating.percent.confirm_over_100` leaves the baseline. The eight
remaining failures all date from `d54a7f7d7`, 2026-09-20, and belong to neither lane.

### ⚠ A.3.2 · A.2 WAS FOLLOWED, AND IT COST A FUNCTION AND SEVEN GREEN TESTS

Wave B had already built `basisServiceOptions()` in `ratingShared.tsx` — the same three clauses,
client-side, with seven passing cases. **Both are deleted.** The two derivations agreed exactly,
which is what makes keeping them both dangerous rather than safe: two copies that agree today are
two that can disagree tomorrow, and the copy on the SCREEN is the one no gate in this repo can watch
go wrong. The card now calls `GET /rate-schedules/percent-basis-options` per service and basis, and
says so on screen while the answer is in flight. The rule is asserted by
`06-backend/tests/test_cr130_percent_basis.py` and read in a browser, on both bases, by
`10-scripts/cr130_laneb_percent_card_walkthrough.mjs`.

## A.4 · What the LINE says on a bill, per basis — the wording contract §4 asks for

The plugin emits one of two sentences, and wave B's `preview` / `planSummary` strings should read
the same way so the screen and the bill agree:

| basis | the bill line reads | note |
|---|---|---|
| `charge` | `sewer usage — 80.00% of water usage charges` | no quantity, no unit: this line prices dollars |
| `usage`, flat | `sewer usage — 80.00% of water volume` | carries the derived quantity and the basis service's unit |
| `usage`, ladder | `sewer usage tier 1 (0-30 gal) — 80.00% of water volume`, one line per block | the block wording is `tiered`'s own, with the provenance appended |

**The percentage is always padded to two decimals** (`90.00%`, never `90%` and never `90.000000%`) —
`DEF-968`, and hard rule 2.

## A.5 · The three defects are filed

`DEF-RAT-6145` (the five stale sentences) and `DEF-RAT-6146` (the un-saveable schedule) are rows in
the register, both **open**, both with wave B's half named in their `prevention` column.
`DEF-RAT-6142` is new and **closed**: this file's own plugin recorded `OQ-232` as closed by
supersession for fourteen days while the register's status column read OPEN throughout.

## A.6 · TWO OF THE THREE DEFECT IDS MOVED AFTER THIS CR WAS WRITTEN, AND SAYING SO IS THE POINT

**§1 above names `DEF-RAT-6140` and `DEF-RAT-6141`. THEY ARE FILED AS
`DEF-RAT-6145` AND `DEF-RAT-6146`**, and §1's two citations are corrected in the
same commit that files them.

**Why:** this CR reserved those two numbers by naming them, which is not a
reservation anything enforces — `12-governance/14-id-reservations.md` is. While
wave A was being built, a sibling lane on this same branch pushed
**`DEF-LED-6140`**, a row with a different module segment and **the same
number**. `10-scripts/allocate.py` treats the NUMBER as the resource (its
`--verify 6140` answers *"TAKEN — a sibling pushed it"*), so one running number
across the whole register is the invariant and two rows cannot share 6140.

**The lane that has not pushed yields**, which is what `--verify` exists to
decide *"at the only moment the answer can be final"*. `6143` and `6144` were
taken the same way, so the two rows landed at the next genuinely free pair.

⚠ **THIS IS `CR-090-BRC01`'s LESSON IN THE DEFECT FAMILY.** A module segment
makes the STRING unique and leaves the NUMBER shared, and a number is what a
person says out loud and cites from a business rule. **Naming an id in prose
does not reserve it.** A block in `14-id-reservations.md` does, and this CR
should have opened one before either wave started.

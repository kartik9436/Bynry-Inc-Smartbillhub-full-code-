# 13 · Rate schedule → Create · Step 1 · Basics — THE DRAWN SPEC

`S11 · RAT-03` · route `/:tenant/plans-rates/rates/:id/edit` (and `…/rates/new`) ·
**blueprint pages 39–42**

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, section
`03 RATE SCHEDULES` opening at the foot of page 39, **frame drawn on page 40**,
specified on pages 41–42. Read as RENDERED pages — the step rail, the field order
and the two locked-field help lines are drawn, and text extraction alone puts the
`FOR` block above the frame it belongs under.

⚠ **THIS FILE COVERS A SCREEN WHOSE FRAME IS ON PAGE 40, ONE PAGE BEFORE THIS
RANGE.** The range assigned here is 41–64; pages 41–42 are this screen's whole
specification and are unreadable without the frame, so the frame is inventoried
here too. If the lane covering pages 1–40 also filed it, this file is the
duplicate and should be merged into theirs.

**State chip:** `NEW READ`
**Commitment:** `NO COMMITMENT` — no card in section 03 undertakes this screen.

**Masthead warning, applied.** The blueprint's own front page says every
*"as-built"* statement was true at **2.232.0 / d2d493e4 / 8 September 2026** and
must be re-verified. We are on **2.234.19**. Every *"the product currently does X"*
line below was re-checked against the code and the verdict is recorded.

---

## 1 · Header — the wizard frame's own head

| slot | drawn |
|---|---|
| kicker | `PLANS & RATES` |
| title (H1) | `New version of Sample — Residential water` |
| sub-line | `One pricing formula for one service. The name is internal: customers see the plan name, not this one.` |

**Actions, drawn TOP-RIGHT on the title row, in this order:**

| # | label | tier |
|---|---|---|
| 1 | `Cancel` | text / ghost, accent-coloured |
| 2 | `Save draft & exit` | secondary (outline) |

⚠ **B14 rule 37 — `Sample — Residential water` is an ILLUSTRATION.** The title
shape is `New version of <schedule name>`; the name itself says nothing.

## 2 · Step rail — five steps, in this order, `1 Basics` active

`1 Basics` | `2 Base rates` | `3 Rates` | `4 Effective & approval` | `5 Review & activate`

⚠ **STEP 3 IS DRAWN `Rates`, NOT `Pricing formula`.** Page 46 states the rename in
its own words and names the three places it must land: *"Renamed in the strip, the
panel heading and the review summary; nothing else moves."*

## 3 · The panel — `Basics`, one section, four fields in this order

**Panel heading:** `Basics`
**Panel hint:** `What this formula is called, which service it prices, in what unit, and for whom.`

| # | label | required | help line, verbatim | value drawn |
|---|---|---|---|---|
| 1 | `SCHEDULE NAME` | `*` | `Internal only — never shown to a customer.` | `Sample — Residential water (inclining tiers)` |
| 2 | `SERVICE` | `*` | `This schedule is already in force, so its service cannot change.` | `Water` (select, **locked**) |
| 3 | `UNIT OF MEASURE` | `*` | `Only units set up for this service are offered. Every price below is expressed in this unit.` | `kgal` (select) |
| 4 | `CUSTOMER CLASS` | — | `Leave blank and this schedule prices every class. Set one and it prices only that class — and the base charge on the next step is the one declared for it.` | `Residential` (select) |

## 4 · Footer — one row, right-aligned

`Continue` — primary, drawn in the outline/accent tier the wizard frame uses.

## 5 · States — the blueprint's own STATES block, verbatim

| state | drawn behaviour |
|---|---|
| **Creating** | *"The service help reads `a schedule prices exactly one service, and this cannot be changed later`."* |
| **Editing a live schedule** | *"The same field says `this schedule is already in force, so its service cannot change`, and the control is locked rather than merely warned about."* |
| **No units set up** | *"Says where to add them — Configure → Reference data → Units of measure — and refuses rather than offering an empty list."* |
| **Read-only role** | *"A role that may read but not change Plans & Rates sees every figure and no button. The refusal names the role, not the screen."* |

## 6 · Components named in the frame

`WizardFrame` `Panel` `TextField` `SelectField` `Disclosure`

## 7 · Rules stated on the screen

*"Money shows two decimals and is stored to four; a percentage six. Colour is
never the only signal — every state carries its word. A code a clerk reads down
the phone is a printed reference, not a database id, so it is shown; a database
id never is. Built in the shared utility classes, adding nothing to a stylesheet."*

## 8 · FOR · HOW YOU GET HERE · PRIMARY ACTION

* **FOR** — *"A clerk creating a pricing formula, or opening an existing one to change its prices."*
* **HOW YOU GET HERE** — *"`Rate schedules` tab → `+ New rate schedule`, or `Edit` from a schedule's own page. The plan builder also offers `Create a rate schedule` where a service has none, and returns here."*
* **PRIMARY ACTION** — `Continue.`
* **COGNITIVE LOAD** — *"Four questions, and two of them can only ever be answered once. The service and class fields say so on the screen rather than refusing later."*

---

# THE DIFF — drawing against the code at 2.234.19

Code: `07-frontend/src/features/rating/RateScheduleWizard.tsx`.

## D1 · THE CUSTOMER CLASS PICKER IS NOT BUILT — and the server has served it for weeks

**Drawn:** field 4, a `SELECT` with the help line quoted in §3.
**Built:** a disclosure carrying a sentence that says the field does not exist.

`RateScheduleWizard.tsx:1300-1306`

```tsx
      <MoreAbout>
        <p className="field-help" data-tracks="DEF-471">
          {t("rating.rate.customerClassArrivesWith")}
        </p>
      </MoreAbout>
```

`rating.rate.customerClassArrivesWith` = *"A rate schedule can be limited to one
customer class, and this screen does not offer the picker yet."* — the exact
sentence page 41 quotes back as the admission.

⚠ **THIS IS A COLUMN THE SERVER ALREADY SENDS.** `account_type_id` is on
`ScheduleCard` (`07-frontend/src/api/endpoints.ts:3761`), is in `SCHEDULE_FIELDS`
on the write side, and **the plan builder already reads it** —
`PlanWizard.tsx:1048` and `:1081` filter candidate schedules on
`card.account_type_id`. The file's own lifecycle block says so at
`RateScheduleWizard.tsx:2888`: *"`account_type_id` IS in SCHEDULE_FIELDS, so the
S11 step-1 customer class is a picker nobody has wired, not an absence."*

**Consequence, in the blueprint's words (page 41):** *"Without it a utility cannot
run a residential water schedule and an industrial one side by side — and it is
the field that decides which base charge the next step reads, so its absence is
what made the base look like one fixed number per service."*

## D2 · UNIT OF MEASURE IS NOT REQUIRED AND NOT GATED

**Drawn:** `UNIT OF MEASURE *`.
**Built:** the select carries no `required` and the step gate does not read it.

`RateScheduleWizard.tsx:1282-1295` — the `SelectField id="rate-uom"` passes
`options`, `placeholder` and `help`, and **no `required`**, where the two fields
above it (`rate-name`, `rate-service`) both pass `required`.

`RateScheduleWizard.tsx:1117`

```tsx
    basics: () => current.name.trim() !== "" && current.service !== "",
```

`Continue` therefore advances with no unit chosen. Page 41's headline is exactly
this: *"The unit of measure is now required and checked here. It was optional and
ungated, so a schedule could reach the last step priced in a unit the service is
not billed in — which surfaced as a warning on every later screen and blocked
billing entirely."*

## D3 · THREE STRINGS DIFFER FROM THE DRAWING

| # | where | drawn | in `en.json` |
|---|---|---|---|
| a | panel hint | `What this formula is called, which service it prices, in what unit, and for whom.` | `rating.rate.basics.hint` = *"What this formula is called, which service it prices, and in what unit."* |
| b | UoM help | `Only units set up for this service are offered. Every price below is expressed in this unit.` | `rating.rate.uomHelp` = *"Only units set up for this service are offered."* |
| c | service help (creating) | `a schedule prices exactly one service, and this cannot be changed later` | `rating.rate.serviceHelp` — **matches, verbatim** |

(b) is not decoration: it is the sentence that makes step 3's rates readable, and
it is the second half of D2's rule.

## D4 · THE WIZARD DOES NOT USE THE SHARED PAGE HEADER, AND THE ACTIONS ARE NOT ON THE HEADER ROW

**Drawn:** `Cancel` and `Save draft & exit` top-right, on the kicker/title row.
**Built:** a bespoke `div.rating-head` (kicker + `<h1>` + `<p class="rating-sub">`)
followed by a separate right-aligned `div.rating-wizard-bar` holding the two
buttons — `RateScheduleWizard.tsx:1129-1166`, with the bar's geometry in
`features/rating/PlansRates.css:305-311`.

`PageHeader` is never imported in this file. **B14 rule 2** — *"One page header.
Every screen, including task pages and workflows, uses the shared page-head:
kicker, title, optional subtitle, right-aligned actions"* — is not met, and that
is why the actions sit under the title instead of beside it.

⚠ **B14 rule 38 applies to the CONSTRUCTION half of this and the drawing loses
there.** What the drawing decides is that these two controls exist, in this
order, with these labels — and they do (`rating.plan.cancel` = `Cancel`,
`rating.rate.saveDraft` = `Save draft & exit`, both exact). Where they sit is
B14 rule 2's, and B14 rule 2 already wants what the drawing wants. **Recorded as
a rule-2 gap on an existing screen, not as a drawing defect.**

## D5 · A RULE ID REACHES THE SCREEN

`RateScheduleWizard.tsx:1194-1198`

```tsx
        <p key={notice.code}>
          {t(notice.code, notice.params)}
          {notice.br_ref !== null && <span className="rating-muted"> ({notice.br_ref})</span>}
        </p>
```

`NoticeList` renders above the step rail on **every step of this wizard**, so a
server notice carrying `br_ref: "BR-RAT-038"` prints `(BR-RAT-038)` to a clerk.

**B14 rule 32**, fourth clause: *"no rule id or internal code in clerk-facing
copy"*. The blueprint's own RULES line says the same in its own words — *"a
database id never is"* — and `Absent`'s docstring one file over
(`RateScheduleDetail.tsx:520-522`) states the settled position: *"no BR id, no DEF
number, no module path (DEF-319 — 219 strings once put engineering references on
a user's screen)"*.

## D6 · THE READ-ONLY REFUSAL IS NOT ON THIS SCREEN AT ALL

**Drawn state:** *"A role that may read but not change Plans & Rates sees every
figure and no button. The refusal names the role, not the screen."*

`GuardedButton` appears **nowhere** in `RateScheduleWizard.tsx` — `Cancel`,
`Save draft & exit` and the frame's commit are plain `Button`s. The detail screen
guards its three actions (`RateScheduleDetail.tsx:771-836`); the wizard does not.

And the refusal string the detail uses, `rating.readOnlyReason` = *"Your role can
view Plans & Rates but not change them."*, **names the screen and not the role** —
the opposite of what the drawn state asks for — and is **eleven words** against
B14 rule 33's five-or-six-word cap.

## D7 · STEP 3'S RAIL LABEL IS STILL `Pricing formula`

`RateScheduleWizard.tsx:833-839` builds the rail from `RATE_WIZARD_STEPS`;
`rating.rate.step.structure` = **`Pricing formula`** in `en.json` and in all
eleven catalogues (`Preisformel`, `価格計算式`, `मूल्य-सूत्र`, `Fórmula de preços`).
The drawing labels it `Rates` on this screen's rail and on all four other steps'
rails. Detail is in this range's `CR-087-p045-create-step3-rates.md`.

---

## ABSENCES — drawn as absent, do not fill them

* **No `Base charge` field.** BR-RAT-088 owns it; step 2 shows it read-only.
* **No `Minimum` field on this step.**
* **No approval control** — approval is out of system (BR-RAT-031 as-modified).
* **No `Back`** on step 1; the exit is `Cancel`.

## WHAT THE CODE HAS THAT THE DRAWING DOES NOT

* **`MoreAbout` (a `Disclosure`) holding the customer-class sentence** — it goes
  when D1 is built, and `Disclosure` stays in the frame's component list because
  page 41 names it.

---

## CONTRADICTIONS AND THINGS FOR THE PRODUCT OWNER

1. **THE LOCKED-SERVICE HELP IS DRAWN AS THE EDIT-MODE STRING ON A FRAME TITLED
   `New version of …`.** The frame draws *"This schedule is already in force, so
   its service cannot change"* — which is the **editing** state — while the title
   says a new version is being made. Both are consistent (a new VERSION of a live
   schedule cannot move its service) but a lane reading the frame alone would
   ship the locked string on a genuinely new schedule. The code already
   distinguishes them at `RateScheduleWizard.tsx:1252` (`props.activated ?
   serviceLocked : serviceHelp`). **The code is right; the frame is drawing one
   of its two states.** No action.

2. **`Save draft & exit` IS DRAWN ON A LIVE SCHEDULE'S HEADER.** The code hides
   it once the schedule is activated (`RateScheduleWizard.tsx:1148` — `{!activated
   && …}`), on BR-RAT-031's save-draft rule. The frame is titled `New version of
   …`, i.e. an activated schedule, and draws the button. **One sentence to the PO:
   may a new version of a live schedule be saved as a draft?** Do not pick.

---

## ⚑ BUILT 2026-09-10 — `CR-087` RATE-SCHEDULE MAINTENANCE LANE

**D1 · THE CUSTOMER CLASS PICKER IS BUILT.** `account_type_id` joins
`ScheduleDraft`, the picker reads the same `account_types` list the plan builder
reads, and the payload posts the key **even when it is empty** — `null` is *this
schedule prices every class*, and an omitted key would leave the old value, so
clearing the field would silently do nothing. The disclosure that said the
picker does not exist is deleted and `rating.rate.customerClassArrivesWith` is
retired from all eleven catalogues.

**D2 · UNIT OF MEASURE IS REQUIRED AND GATED.** The select carries `required`
and `basics` now reads `current.uom.trim() !== ""`, so `Continue` no longer
advances with no unit chosen.

**D3 · TWO OF THE THREE STRINGS ARE THE DRAWN ONES.** `rating.rate.basics.hint`
gains *"and for whom"*; `rating.rate.uomHelp` gains the second half.

⚠ **THE DRAWN CUSTOMER-CLASS HELP LINE IS 32 WORDS AND IS NOT BUILT AS DRAWN.**
B14 rule 33 caps an instruction at six words a sentence and says two sentences of
six beat one of twelve; B14 rule 38 gives the UI rules the CONSTRUCTION of a
form. Built as **"Blank prices every class. The base follows the class."** — both
facts the drawing carries, in two short sentences. **Divergence recorded, not a
drawing defect.**

**D4 · NOT DONE.** The wizard still draws its own head rather than `PageHeader`
(B14 rule 2). Untouched by this lane — it moves every wizard in the module.
**D5 · NOT DONE** — `NoticeList` still prints `br_ref` to a clerk (B14 rule 32).
**D6 · NOT DONE** — the wizard's buttons are still ungarded `Button`s.
**D7** — the rail still reads `Pricing formula`; that rename is step 3's file.

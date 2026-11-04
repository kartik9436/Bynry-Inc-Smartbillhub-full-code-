# DIS-02 step 1 · Create · Basics & type — THE DRAWN SPEC, AND WHAT IS BUILT

Blueprint screen **21**, `/:tenant/plans-rates/discounts/new` · **blueprint
pages 64–67**, frame drawn on **page 65**.

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`
(md5 `2e46f5053ca65804da9c1a90a487e044`), read with `10-scripts/pdf/pdf_text.py`
**and looked at** as a rendered PNG at scale 2.0.

**State chip:** `NEW READ` · **Commitments:** `NO COMMITMENT`

**Masthead warning honoured.** The blueprint's *as-built* statements were true at
**2.232.0 / d2d493e4**. This checkout is **2.234.19**. Every *"the product does
X"* line below was re-verified against the code and carries file and line.

**Code read:** `07-frontend/src/features/rating/DiscountWizard.tsx`
(`BasicsStep`, lines **924–1044**; the shell at **833–887**).

---

## 1 · The frame — header

| slot | drawn |
|---|---|
| kicker | `NEW DISCOUNT` |
| title (H1) | `Define an overlay.` |
| sub-line | `Five steps · discounts reference the plan's normal rates and reduce them — never a cloned schedule.` |

## 2 · Header actions — in the drawn order, top right

| # | label | tier |
|---|---|---|
| 1 | `Cancel` | link / ghost, accent text |
| 2 | `Save draft & exit` | secondary, outlined |

## 3 · Step rail — five, `1 Basics & type` active

`1 Basics & type` | `2 Value` | `3 Eligibility & verification` |
`4 Effective & approval` | `5 Review`

## 4 · The one panel — heading `The programme`

Section sentence, verbatim:

> `A discount reduces what a customer pays and never changes the plan's rates, so`
> `the bill shows the full amount and the reduction on its own line.`

**Five controls, in this order. Two required.**

| # | label | control | drawn value |
|---|---|---|---|
| 1 | `CODE` * | text | `SENIOR` |
| 2 | `BILL LINE LABEL` * | text | `Senior citizen discount` |
| 3 | `PROGRAMME OWNER` | text | *(empty)* |
| 4 | `FUNDING SOURCE` | **dropdown, with chevron** | `Rate-payer funded` |
| 5 | `TYPE` * | dropdown | `Percentage — a share of what the scope selects` |

⚠ **THERE IS NO HELPER LINE UNDER ANY OF THE FIVE.** Page 66, verbatim:
*"Every helper sentence that explained a field's own label is gone. … Here that
meant `what the customer reads on the reduction line of their bill` under a
field labelled **Bill line label**, and three more of the same shape."*

⚠ **THE OVERLAY SENTENCE IS THE ONLY SENTENCE ON THE SCREEN.** Page 66: *"Kept,
and it is now the only sentence on the screen."* Cognitive load, as stated:
*"Five controls, two required. From seven blocks of prose to one."*

## 5 · Footer — one row

| side | drawn |
|---|---|
| right | `Continue` |

**PRIMARY ACTION:** `Continue.`

## 6 · States — the frame's own STATES block, verbatim

| state | drawn behaviour |
|---|---|
| **Editing** | *"Code, label, owner, funding and the filing flag lock, with a banner saying why: editing drafts a new dated **version**, and a version carries the value and the rules, not the identity."* |
| **Rate override or Usage allowance chosen** | *"Says plainly that this type can be written down and cannot be priced yet, so a version of it is refused at activation rather than at save. The type stays offered because removing it would delete a signed requirement."* |
| **Read-only role** | *"A role that may read but not change Plans & Rates sees every figure and no button. The refusal names the role, not the screen."* |

## 7 · Components named by the drawing

`WizardFrame` `TextField` `SelectField` `Callout accent`

## 8 · Rules it must obey, verbatim

*"Money shows two decimals and is stored to four; a percentage six. Colour is
never the only signal — every state carries its word. A code a clerk reads down
the phone is a printed reference, not a database id, so it is shown; a database
id never is. Built in the shared utility classes, adding nothing to a
stylesheet."*

## 9 · Absences — drawn as absent

* **No `STEP 1 OF 5` kicker** and no step heading sentence above the panel. The
  panel heading `The programme` is the only heading.
* **No assistance-filing tick-box** anywhere on the frame.
* **No helper text on any control.**
* **No second panel** — one bordered panel holds all five controls.

---

## AS BUILT AT 2.234.19 — the diff, with evidence

### Matches

* Kicker / title / sub-line — `DiscountWizard.tsx:836-857`, catalogue
  `rating.discountWizard.kicker` · `.title` · `.sub`. **Exact.**
* Back link `← Discounts` — `:835`.
* `Cancel` in the header cluster, ghost tier — `:858-862`.
* Five rail steps with the drawn labels — `DISCOUNT_WIZARD_STEPS` at `:170-176`,
  labels `rating.discountWizard.step.*`. **Exact.**
* `TYPE` is a dropdown carrying the sentence in the option — `:1014-1030`,
  composed `${type} — ${typeHint}`. **This is CR-087 C1 and it is built.**
* The not-priceable note fires on exactly the two types the drawing names —
  `isPriceable` at `:1040`, list `DISCOUNT_TYPES_PRICEABLE` at `:215-219`.
* Editing locks the five identity fields with a banner — `:945` (`headFrozen`),
  `readOnly={editing}` on all four text fields.

### 1 · The four helper lines the drawing deletes are all still rendered

| drawn | built | evidence |
|---|---|---|
| no help under `CODE` | `Short, unique to this utility, and uppercased on save — SENIOR, CAP, PAPERLESS.` | `:953` |
| no help under `BILL LINE LABEL` | `What the customer reads on the reduction line of their bill.` | `:963` |
| no help under `PROGRAMME OWNER` | `The team or agency that runs the programme and answers for it.` | `:972` |
| no help under `FUNDING SOURCE` | `Who pays for the subsidy — rate-payer funded, a grant, a partner agency.` | `:981` |

The second of those is quoted **word for word** by page 66 as the example of
what the redesign removes. All four are live.

### 2 · `FUNDING SOURCE` is drawn as a dropdown and built as a free-text box

`:975-983` is a `TextField`. The frame draws a select with a chevron and a
chosen value `Rate-payer funded`. B14 rule 8 governs how a dropdown looks, not
whether a field is one — **this is the drawing deciding WHAT the control is**,
which the 2026-09-10 *the frame wins* ruling leaves with the drawing. **No
enum, constant or endpoint for funding sources exists** — `DiscountDraft.
funding_source` is a bare `string` — so building it needs a value list somebody
has to author. **Not resolvable by a lane; needs the PO.**

### 3 · A sixth and a seventh control the frame does not draw

`:985-997` renders a `CheckboxField` **`Report in the assistance filing`** plus
a `Note` **`Include this programme's granted subsidy in the assistance report a
regulator asks for.`** on the create door. The frame draws neither, and states
*"Five controls, two required"*. See CONTRADICTIONS §1 — the drawing's own
STATES row names the filing flag.

### 4 · The step head is three lines the drawing does not draw

`StepHead` (`:899-913`, mounted `:934-938`) renders `Step 1 of 5` as a kicker,
`Name the programme and pick its type.` as an `h2`, and
`A discount is an overlay. It reduces what a customer pays and never alters the
plan's rates: the bill shows the full tariff amount and the reduction as its own
line, so the subsidy granted can be reported.` as a note — **38 words where the
drawing writes 26**, under a heading the drawing replaces with `The programme`.

### 5 · A whole extra sentence sits between the header and the rail

`:872` renders `rating.discountWizard.saveDraftAbsent` —
*"There is no separate Save draft: this whole wizard saves a draft. Nothing
bills from a draft, and going live is a second, deliberate act."* — on **every
step of the wizard**. The frame draws no such line, and draws the
`Save draft & exit` button instead. See CONTRADICTIONS §2.

### 6 · `typeNotPriceable` NAMES THE WRONG PAIR

The predicate is right; the sentence is not.

* `:1040` fires when `!isPriceable(type)` — true for **`rate_override`** and
  **`usage_allowance`** (`DISCOUNT_TYPES_PRICEABLE = percentage · fixed_amount ·
  charge_waiver`, `:215-219`).
* The string it renders says: *"**Rate override and Charge waiver** can be
  written down and cannot be priced yet…"*.

So a clerk who picks **Usage allowance** is told about **Charge waiver**, and
Charge waiver — which activates perfectly well — is named as the one that
cannot. The frame's STATES row has it right: *"Rate override or Usage allowance
chosen"*. This is the residue of `DEF-2802`, which fixed the predicate on
2026-08-31 and left the sentence.

### 7 · The composed TYPE option reads mid-sentence capitals and past tense

Built renders `Percentage — A share of what the scope selected.` (`.typeHint.
percentage`), `Charge waiver — Remove the whole of what the scope selected.`
The drawing writes `Percentage — a share of what the scope selects` and
`Charge waiver — removes the whole of the scope`. Lower case after the em-dash,
present tense, no trailing full stop. Eleven catalogues carry the built form.

---

## CONTRADICTIONS INSIDE THE BLUEPRINT — recorded, not resolved

1. **THE ASSISTANCE-FILING FLAG.** The frame draws five controls and page 66
   states *"Five controls, two required"* — yet the same page's STATES row says
   on Editing: *"Code, label, owner, funding **and the filing flag** lock"*. The
   flag therefore exists in the drawing's own model and is absent from its
   frame. **Reading needed: is the tick-box deleted from step 1, or omitted from
   the drawing?** One sentence to the PO settles it; a lane must not pick.

2. **`Save draft & exit` IS DRAWN AND r10 SAYS IT IS ABSENT.** All five discount
   frames (pp. 65, 67, 69, 72, 74) draw it. `DiscountWizard.tsx:865-871` records
   r10's own annotation — *"⚠ Absent on the discount wizard"* — and the product
   states the reason in words (`saveDraftAbsent`): `create_discount` lands the
   discount **and** version 1 as drafts, so the ordinary commit **is** the
   save-draft. **The blueprint also contradicts itself here**: its charge-code
   screen 01 (page 4) draws the same button and its own text says *"There is
   deliberately no Save-draft"*. Under **B14 rule 36** r10 governs the visual
   kit and this is a control the kit does not put on this wizard. **Flag for the
   PO; build nothing.**

3. **THE FRAME IS A CREATE DOOR DRAWN WITH EDIT CONTENT.** The kicker says
   `NEW DISCOUNT` and step 5 of the same wizard (page 75) commits
   `Save new version` over `SAVING AS V3`. B14 rule 37 covers the figures; the
   **door** is not a figure. Read the frames as the create door's shape with an
   edit door's example data.

---

## WHAT NEEDS THE PRODUCT OWNER

* **§2 — the funding-source value list.** Building the drawn dropdown means
  authoring the options. Only the PO can say what a utility may choose.
* **CONTRADICTIONS §1** — five controls or six.
* **CONTRADICTIONS §2** — `Save draft & exit` against r10 and against the
  product's own stated reason.

## WHAT COULD NOT BE VERIFIED WITHOUT THE APP RUNNING

* Whether the composed `TYPE` option wraps inside the select at 1280 in the
  longer catalogues (German, Portuguese) — the composed label is the two longest
  strings joined.
* Focus order and the visible focus ring on the five controls.

---

## FIXED 2026-09-10 — what this wave built, and what it deliberately did not

**§6 · `typeNotPriceable` NAMED THE WRONG PAIR — FIXED.** The note now names the
type the clerk actually chose, derived from the same `DISCOUNT_TYPES_PRICEABLE`
tuple the predicate reads, so a condition and the English it renders can no
longer disagree. That is `DEF-2802`'s residue closed at the root rather than by
retyping two words. `DEF-RAT-4827`.

**§§1, 2, 3, 4, 5 · NOT BUILT, and each for a stated reason.** The four helper
lines, the funding-source dropdown, the assistance-filing tick, the step head
and the `saveDraftAbsent` sentence all still stand. Two of them are blocked on
this file's own **WHAT NEEDS THE PRODUCT OWNER** — the funding-source value list
somebody has to author, and CONTRADICTIONS §1's *five controls or six* — and the
rest are a copy sweep this wave did not take, because the maintenance process's
minimal-fix step forbids widening a defect fix into the neighbourhood.

# 11 · View · Plans — THE DRAWN SPEC, AND WHAT THE PRODUCT DOES

`S13` · route `/:tenant/plans-rates/taxes-fees/:id?tab=plans` · **blueprint pages
34–36** (heading at the foot of 34, frame drawn on **34–35**, specified on 35–36).

**State chip:** `EXISTS BEHIND` **Commitment:** `NO COMMITMENT`

⚠ **THE CHIP AND THE PROSE DISAGREE — SEE §7.**

**Re-verify:** as-built claims were true at **2.232.0**; we are on **2.234.19**.

---

## 1 · The frame above the tab body is IDENTICAL to screen 10

Back link `← Taxes & fees` · kicker `TAX · STATE · TEXAS STATE` · title
`TX State Utility Tax` · `ACTIVE` pill · the same sub-line · `Duplicate · Edit ·
Retire` · tabs with `Plans` active · the same four KPI tiles (`RATE 6.25%` ·
`PLANS IT TOUCHES 6` · `PREMISES IN SCOPE 1,284` · `STATUS Active`) · the same
`NOT WORKED OUT YET` bar with its two rows.

Tab description line: `Which plans carry this tax to customers.`

## 2 · Panel `Where this reaches` — a THREE-column table

| # | header | alignment |
|---|---|---|
| 1 | `PLAN` | left |
| 2 | `REACHED BY` | left |
| 3 | `UNITS` | **right** |

Drawn rows:

| Plan | Reached by | Units |
|---|---|---|
| `Sample — Residential` | `Its authority is bound to the plan` | `74` |
| `Sample — Commercial` | `Its authority is bound to the plan` | `12` |
| `Sample — Industrial` | `Attached on the plan` | `1` |

⚠ **THE FIGURES ARE ILLUSTRATIONS (B14 rule 37). THE TWO `REACHED BY` SENTENCES
ARE NOT** — they are the two mechanisms `BR-RAT-113` gives a plan for carrying a
tax, and page 35 says why the distinction earns a column: *"a bound authority and
an individual attachment behave differently when the authority changes."*

⚠ **THE COUNT IS UNITS, NOT ACCOUNTS.** Page 35: *"The count is units, not
accounts."*

## 3 · Accent callout below the table

| kicker | sentence |
|---|---|
| `A PLAN CANNOT OPT OUT` | `A plan may not leave off a tax its bound authority levies. Attaching adds; nothing on a plan can detach.` |

## 4 · Primary action — `None.`

## 5 · States — the blueprint's own block, verbatim

| state | drawn behaviour |
|---|---|
| **Bound nowhere** | *"No plan binds this authority, so this tax reaches nobody through a plan."* |
| **Bound but levies nothing** | *"Says so: the authority is bound and levies nothing on the services those plans carry."* |

## 6 · Components named in the frame

`Panel` `ReachTable` `Callout accent`

RULES line, this screen's own addition: *"A count names what it counts."*

---

## 7 · WHAT THE PRODUCT DOES — file and line evidence

**The whole drawn tab body is absent.** The `plans` tab renders a single
`ArrivesWith`:

```
07-frontend/src/features/rating/DefinitionDetailPage.tsx:724-728
  if (props.tab === PLANS_TAB) {
    return <ArrivesWith title={heading} message={t("rating.definition.plans.arrivesWith")} />;
  }
```

`rating.definition.plans.arrivesWith` reads: *"The tile above counts the plans that
carry this definition. Naming them one by one needs a read that does not exist
yet."*

| drawn | built? | evidence |
|---|---|---|
| tab exists and is reachable at `?tab=plans` | ✅ | `DEFINITION_TABS.tax`, `definitionDetail.tsx:103`; `TAB_PARAM`, `DefinitionDetailPage.tsx:455-458` |
| header, actions, pill, tabs | ✅ | identical to screen 10 — see the `p030` file |
| KPI strip on this tab too | ✅ | `KPIStrip` is outside the tab body, `DefinitionDetailPage.tsx:605` |
| the four DRAWN tiles | ❌ | same gap as screen 10 §10.4 — no `PREMISES IN SCOPE`, no `STATUS`, two permanent em-dashes |
| `NOT WORKED OUT YET` bar | ❌ | no `AbsenceBar` in the kit; the two absences are tiles |
| tab description `Which plans carry this tax to customers.` | ❌ | nothing renders between the tab strip and the KPI strip |
| panel `Where this reaches` | ❌ **NOT BUILT** | — |
| the three-column table | ❌ **NOT BUILT** | `ReachTable` exists nowhere in `07-frontend/src` ⟨grepped⟩ |
| `A PLAN CANNOT OPT OUT` callout | ❌ **NOT BUILT** | the sentence exists in no catalogue ⟨grepped⟩ |
| primary action `None` | ✅ | the tab offers no control |

### What the server can and cannot answer today

`GET /taxes/{id}` serves **`used_by_plans` as a COUNT and nothing else** —
`06-backend/apps/rating/selectors.py:2910-2919`, a `PlanTaxRule` count over the
two mechanisms (`Q(jurisdiction_id=…) | Q(tax_id=…)`).

⚠ **THE COUNT ALREADY DISTINGUISHES THE TWO MECHANISMS THE DRAWN `REACHED BY`
COLUMN NAMES** — the bound-authority half and the explicit-attachment half are
the two arms of that `Q(...)`, per `BR-RAT-113`. So the drawn column is one
`values_list` away from existing; **the UNITS column is the part with no read
at all**, and it is the one the blueprint changed (*"The count is units, not
accounts"*).

---

## 8 · THE BLUEPRINT AGAINST ITSELF — recorded, not resolved

1. **`EXISTS BEHIND` + `NO COMMITMENT` contradicts this screen's own prose.**
   The legend on page 2 defines `EXISTS BEHIND` as *"the screen is drawn **and
   the data behind it is served**"* and `NEW READ` as *"the screen exists and
   something on it has no read"*. Page 35's own WHAT CHANGED says: *"The tab said
   naming them needed a read that does not exist. It names them, and — more
   usefully — **how** each one gets the tax."* **A screen that needs a read that
   does not exist is `NEW READ` by the blueprint's own definition.** And with
   `NO COMMITMENT` on the same line, *"nobody has undertaken to build"* the one
   thing the section spends two pages specifying. Per the legend, *"that absence
   is the finding, not an oversight"* — so it is recorded here as the finding.
2. Consequently the built product is **exactly what page 34's `What was wrong`
   describes** (*"The tab rendered a sentence saying it could not list what it
   exists to list"*) and nothing in the blueprint commits anyone to changing it.

## 9 · FOR THE PRODUCT OWNER

* **The reach table needs a server read that nobody has committed to.** The
  question is not a design one — it is whether `PRB`-numbered work should exist
  for it. Two shapes, both cheap: a `plans` array on `GET /taxes/{id}`, or a
  `GET /taxes/{id}/plans` of its own. **The unit count is the part that needs a
  ruling**, because a unit count per plan per tax is a join nothing in the
  rating module owns today.

## 10 · NOT VERIFIABLE WITHOUT THE APP RUNNING

* Nothing on this tab — the body is a single stated absence and reads the same in
  a browser as it does in the source.

---

## 11 · WHAT WAS BUILT — 2026-09-10, the CR-087 tax-screens maintenance lane

**The tab body is built.** PO ruling 2026-09-10, verbatim: *"build"* — asked
whether these tabs should exist at all given §8's `EXISTS BEHIND` +
`NO COMMITMENT` contradiction. The ruling answers §9's question to the Product
Owner and supersedes the `NO COMMITMENT` chip.

| §7 finding | now |
|---|---|
| panel `Where this reaches` | **BUILT** — `TaxPlansTab`, `taxDetailTabs.tsx` |
| the three-column table | **BUILT** — `PLAN` · `REACHED BY` · `UNITS` (right-aligned), on the kit's `PlainTable` |
| `A PLAN CANNOT OPT OUT` callout | **BUILT** — the kit's `AccentBand`, kicker + one sentence |
| state *Bound nowhere* | **BUILT** — a stated absence, never an empty table |
| the reach read | **BUILT** — `GET /taxes/{id}/plans`, `selectors.tax_plans` |
| the four DRAWN tiles | **BUILT** — see `p030` §16.3 |
| the tab description line | **BUILT**, shortened to B14 rule 33's cap |
| `NOT WORKED OUT YET` bar | **BUILT** — see `p030` §16.3 |

### ⚠ §9's SENTENCE ABOUT THE UNIT COUNT WAS STALE, AND THAT IS THE FINDING

§9 says *"a unit count per plan per tax is a join nothing in the rating module
owns today"* and calls it the part needing a ruling. **It was true when written
and is not true now:** `selectors.discount_offered_unit_count` — landed with
`CR-087 C2`, in this module, over `UnitPlanAssignment`, which is rating-owned
(B2 r16 #6) — counts exactly this shape for exactly this reason. `tax_plans`
uses the same query with a `GROUP BY`. **No ruling was needed and none was
taken.** Corrected here rather than left standing (hard-won law 1).

### ⚠ A PLAN CAN HOLD BOTH MECHANISMS, AND THE BINDING IS REPORTED

The model's check constraint bounds a ROW, not a PLAN, so a plan that binds
Texas State *and* attaches this Texas State levy has two rows. The drawn table
has one row per plan, so one has to win, and `BR-RAT-113` decides it: a
jurisdiction-mandated tax stays on the bill *"whether or not anyone ticked it"*,
so the attachment is the removable half and the binding is the fact that
survives. **Reporting the attachment would tell a clerk they can detach a tax
they cannot.** Proved RED: with the naive *last row wins*,
`assert 'attached' == 'jurisdiction'`.

### DIVERGENCES, RECORDED

1. **NO PAGINATION FOOTER (B14 rule 16).** The drawing draws no toolbar and no
   footer, so `DataTable` is the wrong piece — it would put a search box, filter
   chips and a column chooser on a three-row panel. `PlainTable` is the same
   table type at the same two tiers with none of that chrome. The read is
   bounded by the tenant's own plan catalogue and can never grow a row per
   account, which is what `NFR-3` is about. Same divergence as the rate
   schedule's two tabs.
2. **`REACHED BY`'s wording** is *"Its authority is on the plan"* (6 words),
   where the drawing writes *"Its authority is bound to the plan"* (7). B14
   rule 33 caps a fact at six.
3. **The drawn figures `74` · `12` · `1` are illustrations** (B14 rule 37) and
   nothing in the code or the tests asserts one.

### ⚠ ADDENDUM 2026-09-10 — THREE TABS, TWO ANSWERS (`DEF-RAT-4841`)

The divergence recorded above (no pagination footer, B14 rule 16) is **not the
one the product ended the day with.** Three lanes built *which plans carry this
definition* from this same blueprint on the same day:

| tab | built as |
|---|---|
| charge code → `Plans` | **paginated** — `ListPager`, `page`/`per`, and a server read that takes them |
| rate schedule → `Plans` | `PlainTable`, no toolbar, no footer (`CR-087-p058`) |
| **tax → `Plans`** (this file) | `PlainTable`, no toolbar, no footer |

**Both readings are defensible and both are written down.** What is wrong is that
there are two: a clerk who opens a charge code's Plans tab and then a tax's meets
one question answered two ways. **No gate compares two screens with each other**,
and B14 rule 36 names this exact shape — it is how a product acquires four
different chips.

**Not resolved here, deliberately.** One lane cannot pick the convention for
three tabs it does not all own; picking silently is what produced the split. It
is `DEF-RAT-4841`, and the fix it asks for is that a reach list is a kit
decision made ONCE for the kind rather than per tab.

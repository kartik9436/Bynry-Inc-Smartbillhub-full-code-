# EP-CWP-01 — The public front, and the guard in front of it

**Module:** portal · **Wave:** release 1 · **Screens:** CWP-001 · **Status:** draft

## Scope

**In:** the front page a visitor meets before any password, and the throttle and lockout
that sit under every guest door.

**Out:** every errand card's destination — those are `EP-CWP-02`, `03`, `04` and `12`.
Out too: the sign-in form itself (`US-CWP-016`), which is now the screen *behind* a card
rather than the front page.

⚠ **THIS EPIC EXISTS BECAUSE THE BLUEPRINT CORRECTED ITSELF.** Its first draft made the
sign-in screen the front door, *"which puts a password field in front of a person whose
errand takes ninety seconds and needs no account"*. Sign-in became one card among six.
**A lane that restores the sign-in form as the front page has undone the correction.**

## Capability matrix

| Screen | Search | Filters | Default sort | Sortable | Columns | Row actions | Bulk | Export |
|---|---|---|---|---|---|---|---|---|
| CWP-001 | — | — | — | — | — | — | — | — |

---
id: US-CWP-001
epic: EP-CWP-01
module: portal
screens: [CWP-001]
wave: 1
status: ready
blocked_by: []
depends_on: [US-CWP-069]
journeys: [J30, J31, J32, J33, J34]
rules: [BR-CWP-007, BR-CWP-021, BR-CWP-093]
golden_tests: []
finance_calc: none
---
### US-CWP-001 — The public front page, with sign-in as one card among six

**1 · Details** — As **a visitor at a utility's web address**, I want **to see the six
things I might have come for**, so that **I can finish a ninety-second errand without
meeting a password field**.

Entry: `smartbillhub.bynry.com/{tenant}` — the tenant is the first path segment and the
only thing that says which utility was meant. Exit: one of six cards, or the sign-in
screen `CWP-015` behind the *Sign in* card.

The six cards are **Pay a bill · Report a problem · Check my area · Start service · What
things cost · Help & answers**, plus a footer line offering a login. The utility's own
name, logo and colours — all already stored on the tenant record.

⚠ **ALL SIX CARDS ARE ALWAYS ON SCREEN; A CARD THE TENANT CANNOT OFFER IS DISABLED, WITH
ONE SENTENCE SAYING WHY — AND ITS ENDPOINT STILL REFUSES.** PO ruling 2026-09-05, verbatim:
*"Yoi ahev these cards - may be disable them, but for completess have them on screen"*,
given on seeing four cards on a live tenant beside the blueprint's six.

**THIS REVERSES THE SENTENCE THAT STOOD HERE**, which read *a card whose per-tenant switch
is off is not rendered … a greyed-out button with a live route behind it is the built-is-not-
wired failure inverted*. That reasoning was sound and the ruling outranks it; what the ruling
saw is what filtering costs (`DEF-CWP-3953`): **an absence has no empty state**, so B14 rule
17 could never reach it, and no utility was ever told that publishing one help answer is what
adds *Help & answers* to its own front page. Two cards were missing for reasons a week apart
in cost — a ruling and a five-minute job — and from the utility's chair both looked like
nothing at all.

**The half that did not move is the half that matters for money.** A visible card is not an
open door: the endpoint behind a disabled card refuses exactly as it did when the card was
hidden (`BR-CWP-002`, at the edge). And a greyed control over a LIVE route is still the
inverted failure — which is why every card the server calls available must draw a real link,
asserted in both suites.

⚠ **THE NAV WORDS DO NOT CHANGE.** *Help* and *Visit us* still appear only when there is
something behind them. A grid of six is a CATALOGUE of what this product does; a nav word is
a DESTINATION, and a greyed word in a top bar that goes nowhere is hard-won law 2's dead
control (`DEF-CWP-3925`, on this very page).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-007` | The portal lives at `/{tenant}/portal/…`; the guest surface at `/{tenant}/…` | CONFIRMED — `CR-068` `R11` |
| `BR-CWP-021` | A guest sees an amount and a status, never a person. The front page shows neither | CONFIRMED — blueprint §20 |
| `BR-CWP-093` | Nothing empty ever appears — **no LINK opens onto nothing**. ⚠ **NARROWED FOR THE SIX ERRAND CARDS ONLY, PO 2026-09-05:** the cards are a catalogue and are all drawn, disabled where they cannot be used; the *Help* and *Visit us* NAV WORDS still disappear with the content, and every other list in the portal is untouched | CONFIRMED — blueprint §16 Figure 11; **card clause SUPERSEDED 2026-09-05** (*"for completess have them on screen"*) |
| `BR-CWP-022` | Behind the anonymous throttle at 60/min | CONFIRMED — blueprint §7 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open `/pine-hill` with all five switches on and content published | Six errand cards render — **six on every tenant since 2026-09-05, usable or not** — *Sign in* is one of them, and **Pay a bill is reachable in one click without a password field** |
| TC-2 ⚠ **AMENDED 2026-09-05** | `portal_settings.quick_pay_enabled = false` | The **Pay a bill** card is **drawn and DISABLED**, carrying one sentence — *Not offered online at the moment.* — and linking nowhere; **and** `POST /public/bills/lookup` still returns refused, not a 200 with an empty body. ⚠ This read *"the card is absent"* until the PO ruled *"for completess have them on screen"*; the card half is reversed and the ENDPOINT half is untouched |
| TC-3 · **negative** | Open `/pine-hill` with `is_live = false` | A holding page. **Bills and letters are unaffected** — no notification row changes |
| TC-4 · **negative** ⚠ **AMENDED 2026-09-05** | No help answer is `published` and no service centre is shown | The **Help & answers** CARD is drawn and disabled, saying *Nothing published here yet.* — and the *Help* and *Visit us* HEADER LINKS do not render at all. **No empty page, no "no answers found".** ⚠ The card and the nav word part company here on purpose: a catalogue tells you what exists, a nav word takes you somewhere |
| TC-5 · **tenant isolation** | Open `/oak-ridge` while Pine Hill has six published answers | Oak Ridge's own content only. `app.tenant_id` is set from the path **before** any content query, and Pine Hill's answers do not appear |
| TC-6 | Open `/portal` where no tenant is named `portal` | Resolves as a **reserved segment**, not as a tenant, and does not 500 |

**4 · Test Data** — Tenant `pine-hill`, trading name *Pine Hill Water & Power*, brand
`#EC3013`, accent `#E15B47`, logo `pine-hill-logo.svg`. Services Water, Sewer, Trash,
Electric. Office `8am–5pm · (512) 555-0148`; emergency `(512) 555-0100`. Strapline *"Your
account, your bills and your meter readings — any time."* Second tenant `oak-ridge` for
TC-5, with one published answer of its own.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Trading name | CWP-001 header | prototype-extracted | `tenant.dba_name`, falling back to `tenant.name` when null (⚠ `trading_name` does not exist — `apps/tenancy/models.py:112,121`; this cell named it until 2026-09-03, `DEF-CWP-3609`) | text | reference-data | Read-only here |
| Logo | CWP-001 header | prototype-extracted | `tenant.logo_bytes` + `logo_content_type` | bytea | reference-data | Sanitised on upload in Company → Profile |
| Brand / accent colour | CWP-001 | prototype-extracted | `tenant.brand_primary_hex`, `tenant.brand_accent_hex` (⚠ `brand_colour` / `accent_colour` do not exist — `apps/tenancy/models.py:147–148`, the columns the Company tab saves; corrected 2026-09-03, `DEF-CWP-3609`) | char(7) | reference-data | Hex |
| Strapline | CWP-001 | GAP | `portal_settings.strapline` | text | user-input | B14 rule 32 |
| Front-page services | CWP-001 chips | GAP | `portal_settings.front_page_service_ids` | uuid[] | user-input | Subset of the tenant's services |
| Five switches | CWP-001 cards | GAP | `portal_settings.*_enabled` | boolean | user-input | Default per `CR-068` `R8` |
| Office hours, emergency phone | CWP-001 footer | prototype-extracted | `portal_settings` | text | user-input | — |

**6 · Acceptance** — **Given** Pine Hill is live with quick pay on, **when** a visitor
who has never signed in opens `smartbillhub.bynry.com/pine-hill`, **then** they see six
errand cards in the utility's own colours, and reach *Pay a bill* in one click without
meeting a password field. **And given** quick pay is switched off, **when** they look for
it, **then** the card is still there, plainly disabled, saying *Not offered online at the
moment.* — and the endpoint behind it refuses.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-CWP-002
epic: EP-CWP-01
module: portal
screens: [CWP-002, CWP-012]
wave: 1
status: ready
blocked_by: []
depends_on: [US-CWP-003, US-CWP-010]
journeys: [J30, J31]
rules: [BR-CWP-022, BR-CWP-023, BR-CWP-025]
golden_tests: []
finance_calc: none
---
### US-CWP-002 — The throttle, and a lockout on the two lookups worth guessing at

**1 · Details** — As **the utility**, I want **every public door rate-limited, and the
two that take a reference locked after five wrong tries**, so that **the guest surface
cannot be used to enumerate accounts**.

Every guest endpoint sits behind the anonymous throttle the product **already** applies
to its three existing public endpoints — sixty requests a minute. **On top of that**,
quick pay (`CWP-002`) and track (`CWP-012`) lock for fifteen minutes after five wrong
pairs from the same address, because a bill number is a short sequential string and a
reference is guessable.

⚠ **NO `CP-` SPECIFICATION COVERS THE THROTTLE.** The blueprint states it in the prose of
§7 — *"A public form is a public form"* — and specifies only the lockout, as `CP-37`.
This story is ours, derived and recorded rather than inherited.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-022` | Every guest endpoint sits behind the anonymous throttle at 60/min | CONFIRMED — the existing public endpoints |
| `BR-CWP-023` | Quick pay and track additionally lock 15 minutes after 5 wrong attempts from one address | CONFIRMED — `CP-37` |
| `BR-CWP-025` | Every public lookup requires a second fact only the sender would know | CONFIRMED — blueprint `G12` |
| `BR-CWP-026` | A public form may create work and may never change an account | CONFIRMED — blueprint `G10` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | 60 requests in a minute to `POST /public/reports` | All accepted |
| TC-2 · **negative** | The 61st in the same minute | Refused. The refusal sentence is **five or six words** (B14 rule 33) and names no internal code |
| TC-3 · **negative** | Six wrong bill-number-and-postcode pairs from one address | The sixth returns *"locked for fifteen minutes"*; a **correct** pair from the same address in minute 14 is still refused |
| TC-4 | The same six wrong pairs from a **different** address | Not locked — the lock is per address |
| TC-5 · **negative** | Six wrong reference-and-postcode pairs on `POST /public/track` | Locked independently of the quick-pay lock; locking one does not lock the other |
| TC-6 · **tenant isolation** | Lock the form on `/pine-hill`, then open `/oak-ridge` from the same address | Oak Ridge is **not** locked. A lockout is per tenant and per form |
| TC-7 | A locked form after 15 minutes with a correct pair | Accepted, and the counter is reset |

**4 · Test Data** — Correct pair `BL-2608-0141` + `78702`. Five wrong pairs
`BL-2608-0142`…`0146` + `78702`. Reference `RP-26-0412` + `78702` for track. Source
address `198.51.100.10`; second address `203.0.113.7`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Attempt count | — | GAP | cache, keyed by tenant + form + address | integer | system-derived | Not a table — a lockout is not a financial record |
| Locked until | CWP-002, CWP-012 | prototype-extracted | cache | timestamp | system-derived | 15 minutes |

**6 · Acceptance** — **Given** a stranger is guessing bill numbers on Pine Hill's quick
pay, **when** their sixth pair is wrong, **then** the form refuses for fifteen minutes
from that address, a correct pair inside the window is still refused, and Oak Ridge's
form is unaffected.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None. ⚠ **The lockout state is deliberately NOT a table.** It
is not a financial record and hard rule 4 does not reach it; a lane that models it as one
has added an append-only row per wrong guess on a public endpoint.

# J32 — *Can I get service here* → apply → paperless consent (`31 Palm Ct`, `$185.00` before we start, `$150.00` on the first bill, and nothing charged today)

---
id: J32
tier: 2
rules: [BR-CWP-021, BR-CWP-022, BR-CWP-026, BR-CWP-028, BR-CWP-031, BR-CWP-056, BR-CWP-058, BR-CWP-076, BR-CWP-087, BR-CWP-093, BR-CWP-007]
stories: [US-CWP-001, US-CWP-012, US-CWP-013, US-CWP-014, US-CWP-015, US-CWP-050, US-CWP-069]
# Wiring: every story above cites `J32` in its own `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J32.spec.ts`. Release 1, except step 10
# (`US-CWP-050`, collecting the fee) which is RELEASE 5 and is written as the
# boundary it is.
---

**Intent.** The one guest journey the product is genuinely ready for, because a service
request already has a draft state, an applicant identity, a document checklist by request
type and a fee quote — **all built, all reachable only by a clerk**. This journey opens the
public door onto it: a visitor reads what an address can get and what it costs **before**
filling in the wrong form, types a draft that **survives a closed tab** and carries **no
reference** until submit, and on submit **paperless consent is taken with the wording
version they saw** — the one place in the product it is captured (`CR-068` `R5`, `R6`).
⚠ **Nothing is charged today and no document is demanded up front.**

**Upstream leaves (handoff in).** Tenant `pine-hill` live, `requests_enabled = true`.
Premises `31 Palm Ct, Austin TX 78702`: Water available (connection `$185.00`, deposit
`$150.00`), Sewer available (included, no deposit), Trash available (`$0.00`), **Electric
not present**. The connection fee sits on the **currently effective** tariff version; a
future-dated fee version exists and must not be quoted. Occupied premises `1408 Elm St · A`
(for the move-in case). Unknown address `77 Nowhere Ln`. A **closed** account for *Daniel
Okafor*, born 4 Dec 1987, at `91 Cedar Row` (the returning-customer seed). Request
categories configured for Pine Hill: `re_read`, `missed_collection`, `copy_of_bill`,
`low_pressure`, `bill_question`, `other`.

**This journey leaves (handoff out).** ONE `service_request` in `submitted`, reference
allocated **at submit**, channel `customer_portal`, applicant *Daniel Okafor*, services
Water + Sewer + Trash, `requested_start_on = 2026-09-21`, a fee quote `$185.00` before we
start + `$150.00` deposit on the first bill, a checklist (Photo ID, Proof of address) in
`AFTER YOU APPLY` state, a *possible returning customer* flag **for a clerk**. ONE
`portal_consent` row: `kind = paperless`, `wording_version = paperless-v1-2026-09`,
`agreed_on` = the moment of submit, `taken_on_screen = CWP-009`, `withdrawn_on` NULL —
this row is **J45's** starting point. **Zero** payments, **zero** customer or account rows
created. When approved (a clerk's act, J26's shape), the request carries the fees `CWP-050`
reads.

**Fixture.** Applicant **Daniel Okafor**, a person, `d.okafor@example.com`, `(512)
555-7730`, born **4 Dec 1987**. Start **21 Sep 2026** (today 2 Sep → 13 working days out).
Wording version `paperless-v1-2026-09`. Approved request for step 10: `SR-26-0061`, fees
*New connection `$185.00` before we start* · *Meter installation `$150.00` before we start*
· *Security deposit `$150.00` on your first bill* · *Account set-up `$25.00` **waived***.
Screens `CWP-008` → `CWP-047` → `CWP-009` → (`CWP-010`, `CWP-050`).

| # | Actor · action | Expected outcome (contract) | Downstream assertions (record · worklist · consent · money) | Rule |
|---|---|---|---|---|
| 1 | Guest opens *Start service* (`CWP-008`), types `31 Palm Ct, Austin TX 78702`, *Check →* | `MiniTable` Service / Available / To connect / Deposit: **Water YES `$185.00` `$150.00`** · **Sewer YES Included —** · **Trash YES `$0.00` —** · **Electric NOT HERE — —** (greyed). `ConsequenceBox` **IF YOU APPLY**: *$185.00 before we start · $150.00 deposit on your first bill · About three working days* | **Not here** carries no fee and no deposit — ⚠ not `$0.00`, which means free. Figures read from the tariff version **effective today**, never next quarter's. Money 4 dp stored, 2 displayed. Availability names the **services**, never the current occupier | BR-CWP-021 · `US-CWP-012` TC-1/4/6 · hard rule 2 |
| 2 | **negative · not a refusal** — `77 Nowhere Ln` | *"a person will look at it"* and an *Apply* route — **not a refusal and not an empty table**. An unknown address means a person looks at it; they may never become a customer if we refuse them | `1408 Elm St · A` (occupied) → the panel says this is a **move-in**, quicker and cheaper, and **does not name the current occupier** | BR-CWP-093 · BR-CWP-021 |
| 3 | `CWP-047` — types first and last name and email, **closes the tab**; reopens the URL | The two fields are **restored**. A draft `service_request` exists with **no reference** — saved from the first keystroke (`PUT /public/applications/{draft}`), because no promise has been made | Rail `Panel.Info` *nothing is promised yet*. The footer says so rather than printing a number that does not exist (cf. J26 step 1) | `US-CWP-013` TC-1 |
| 4 | Completes *About you*: a person, `d.okafor@example.com`, `(512) 555-7730`, born 4 Dec 1987, start 21 Sep 2026 | Accepted. The date of birth matches the closed `91 Cedar Row` account → a **possible returning customer** is flagged **for a clerk**; the records are **not** linked and **the applicant is told nothing**. Matching runs through the **existing** encrypted, blind-indexed identity service — the portal never reads those fields directly | ⚠ Date of birth is asked **here and not on enrolment**, deliberately: here a person decides; on a public sign-in form it would be a fact anyone can hammer (`BR-CWP-031`). A start date two working days out is refused *"at least three working days from today"*. A business with no tax ID is refused. Submitting with the address step incomplete is refused **naming the step** and the draft is kept | BR-CWP-031 · `US-CWP-013` TC-2…TC-5 |
| 5 | `CWP-009` — check and send. `KVList` Address `31 Palm Ct` / Applicant / Services *Water, Sewer, Trash* / Start on *21 Sep 2026* / To pay before we start **`$185.00`** / On your first bill **`$150.00` deposit**. Checklist *Photo ID · AFTER YOU APPLY* · *Proof of address · AFTER YOU APPLY*. Ticks *Send my bills and letters by email* | The figures **equal `CWP-008`'s** — `US-CWP-014` restates `US-CWP-012`'s arithmetic and must not recompute it. Helper reads *We print them as well. You can go back to paper at any time.* `ConsequenceBox`: *Sends your application to us · Records how you want your bills sent · **Nothing is charged today** · We answer within two working days* | Copy claiming paperless **stops paper bills fails review** — print is the floor on bills, receipts, notices and plan letters (`CR-068` `R4`). No document is demanded up front: the checklist is real and the upload box is not | BR-CWP-087 · BR-CWP-058 · `CR-068` `R4` |
| 6 | *Send my application ✓* (`POST /public/applications/{draft}/submit`) | State `submitted`; **reference allocated now**, at submit, not at draft; channel **`customer_portal`** on a clerk's worklist (`REQ-01`). ONE `portal_consent` row: `kind = paperless`, `wording_version = paperless-v1-2026-09`, `agreed_on` = now, `taken_on_screen = CWP-009` | A **double-click** → one request, one reference, one consent row (idempotent). **Nothing charged**: zero `payment` rows, zero journal lines. Sending it **unticked** → the application succeeds and **no consent row is written** — an absent consent is not a withdrawn one. `agreed_on` **may never be in the future** — refused by constraint (the blueprint shipped one nineteen days after its own *today*) | BR-CWP-087 · BR-CWP-076 · BR-CWP-026 |
| 7 | `CWP-010` — *Ask for a quick service*: *A meter reading looks wrong* at `1408 Elm St`; then *Something else*: *"please put the account in my name"* | Six `ErrandCard`s **read from the tenant's categories** (a renamed category shows its new label; a category configured only by Oak Ridge is not offered). The re-read lands under the tenant's own `re_read` category with a reference. *A question about my bill* requires the bill number and the row **names that bill** | **The boundary:** the *Something else* ask is accepted as **a request a clerk judges** — and **nothing on the account changes**. Assert the `account` and `customer` rows are byte-identical afterwards. With `requests_enabled = false` the cards are absent **and** `POST /public/requests` refuses | BR-CWP-026 · BR-CWP-076 · BR-CWP-028 |
| 8 | **negative · the guard** | The 61st ask in one minute is refused, five or six words, no code | 60 accepted. The lockout that applies to quick pay and track does **not** apply here — these forms take no reference to guess at | BR-CWP-022 |
| 9 | **tenant isolation** | `31 Palm Ct` on `/oak-ridge` → Oak Ridge's own premises and prices, or *"a person will look at it"* — **never Pine Hill's fees**. The draft started on `/pine-hill` opened under `/oak-ridge` → **not found**. The consent row is scoped tenant + account; RLS `FORCE` on `portal_consent` | `app.tenant_id` from the path before any premises or tariff read | hard rule 1 · `US-CWP-012` TC-5 |
| 10 | **release 5 · boundary** — a clerk approves; `CWP-050` *What starting service will cost* for `SR-26-0061` | `MiniTable` Fee / When / Amount × 4, the waived `$25.00` **still listed, struck through** — never deleted. `TotalRow` *To pay now **`$335.00`*** (`$185.00 + $150.00`; the waived line in **neither** total) · *On your first bill `$150.00`*. **Pay `$335.00` is held** — visible, disabled, carrying its reason | *To pay now* **must equal the quote `CWP-008` gave before the customer applied** — a disagreement between quote and invoice is the defect both stories test for. Once rails exist: paying `$335.00` moves the request out of *fees due* and **the `$150.00` deposit still shows as due on the first bill rather than being taken now**; a partial amount is refused. An unapproved request cannot reach this page | BR-CWP-056 · BR-CWP-058 · `US-CWP-050` TC-2/3/4 |
| 11 | **INVARIANCE** | A public form created a request, a consent row and a worklist item — and **changed no account, moved no money, created no customer**. The fee figures were the same on `CWP-008`, `CWP-009` and `CWP-050`. The consent carries the wording version they actually saw; a consent without one is not a consent | Existing paperless customers were **not asked** at any step; a migration back-filling consent for existing customers **invents a consent nobody gave** — assert no `portal_consent` row exists for a customer who did not tick on `CWP-009`/`CWP-025` | BR-CWP-026 · BR-CWP-087 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | Step 10's payment | Rails — release 5. The fee table, the totals and the held control are asserted now |
| b | A document uploaded by the applicant | Consumer upload is a **signed deferral**, not an open question. The checklist exists; the request ends with *bring it to the office* |
| c | The request producing a live account and a first bill | That is the clerk's approval and the connection job — J26/J27's territory (customers), not the portal's |

---

## ⊕ STAMPED BY THE BUILD, 2026-09-04 (CR-068 wave C, `2.136.0`)

**This journey was written before the code existed. Four of its assumptions were
wrong about the product, and the code is what is right** (`10-execution-plan.md`
step 0). Each is a defect row, not a change of intent — the journey still asks
for the same thing.

1. **The draft is NOT a `service_request` in `draft` state.** `BR-CUS-093` (PO
   2026-08-24) numbers every service request at creation, so a draft written
   that way carries a reference from the first keystroke — the opposite of what
   this journey's *"no reference until submit"* asks for. The draft is
   `portal_application_drafts`, portal-owned, and the request is created **at
   submit** (`DEF-CWP-3700`).

2. **The connection fee is not on a tariff version.** There is no such column.
   It is a `one_time` CHARGE CODE attached to the rate plan, quoted at its
   **catalogue** amount — a plan composes, it does not price (PO 2026-08-19
   ruling 1). Effective dating is the PLAN's, so *"a future-dated fee version
   must not be quoted"* is implemented as: a plan that is not PUBLISHED, or
   whose window has not opened, quotes **nothing at all** (`DEF-CWP-3703`).
   ⚠ **That case is proved in `tests/test_us_cwp_012_availability.py` TC-6 and
   is NOT in the fixture**, because `metering` refuses to put a unit on a
   not-yet-effective plan — correctly, and that refusal is the first line of
   defence.

3. **The returning-customer seed is not a closed account at `91 Cedar Row`.**
   It is *Maria Alvarez* on `(512) 555-0134`, the live account that also makes
   `1408 Elm St` read as a **move-in**. One person serves both cases, which is
   the honest fixture: recognition is only demonstrable against somebody who has
   actually held an account here.

4. **The request categories are not `service_request.category`.** That column
   does not exist and no tenancy lookup holds request kinds, so the six cards
   live on `portal_settings.quick_service_categories`, beside the front-page
   service list and for the same reason (`DEF-CWP-3701`). Oak Ridge carries its
   own three — one renamed, one Pine Hill does not sell — which is what makes
   *read from the tenant's configuration* provable rather than merely stated.

**What runs it today.** `10-scripts/render-checks/cr068-c-start-service.mjs` —
eleven steps against the running product, with the figures read off the screen
and the consent read back through the API. `07-frontend/e2e/J32.spec.ts` is
still absent, so this journey is **NOT ACTIVATED** in the wiring index, exactly
as its frontmatter says.

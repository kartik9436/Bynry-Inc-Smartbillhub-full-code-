# 15 · Customer Web Portal — the four edges

**98 endpoints across four edges.** ⚠ **The confirmation table said 82; the real design
needs 98** — see the note at the foot of this file. Nothing was added to scope; the
estimate was low.

⚠ **THE EDGES ARE SEPARATE FILES AND SEPARATE MIDDLEWARE, NOT ONE ROUTER WITH A
DECORATOR.** A portal session must not be able to call a staff route, and the guest
surface must not be able to call the portal edge (`BR-CWP-011`). One router with a
per-route check is one missing decorator away from a customer reading the staff API.

| Edge | File | Count | Who may call it |
|---|---|---|---|
| Guest | `apps/portal/guest_api.py` | **14** | Nobody signed in. Anonymous throttle, 60/min |
| Portal | `apps/portal/api.py` | **71** | A portal session, filtered on tenant **and** account set |
| Back office | `apps/tenancy/…` | **12** | A System Admin in the **staff** app |
| Webhook | `apps/payments/webhooks.py` | **1** | The gateway, on the reserved idempotency key |

---

## 1 · Guest edge — 14

All rooted at `/{tenant}/`, all behind the anonymous throttle, none of them able to
change an account (`BR-CWP-026`).

| # | Endpoint | Screen | Notes |
|---|---|---|---|
| 1 | `GET /public/front` | `CWP-001` | Branding, the six errand cards, and which of the five switches are on. ⚠ **`cards` CHANGED SHAPE 2026-09-05** (PO: *"for completess have them on screen"*): it was the list of KEYS a visitor could use and is now ALL SIX objects — `key`, `available`, `reason_code` — in `CARD_ORDER`. `reason_code` is one of exactly three catalogue keys (`switched_off_by_the_utility` · `status_page_not_offered` · `nothing_published_yet`) and is null when the card is usable; the screen turns it into one sentence in the reader's own language, and a code never reaches the glass (B14 rule 31). `links` is UNCHANGED — the nav words still come and go with published content. ⚠ **AS BUILT (wave A, 2026-09-03):** mounted at `/api/{tenant}/portal/public/front`; behind the sixty-a-minute per-address throttle AND a per-tenant rate (600/min default) AND the in-flight budget (`NFR-39`, `apps/portal/guards.py`); three point reads, no join (`NFR-41`); `is_live: false` answers the holding page's data. ⚠ **AND IT CARRIES `locales` FROM 2026-09-07** (`DEF-CWP-4442`, `BR-CWP-106`) — the two languages the portal OFFERS, `["en", "es"]`, which the guest's dropdown draws. It rides here because the guest half has no other payload, exactly as `regional.language` does one key over, and it travels on BOTH branches although the holding page draws no nav: a field present on one branch and absent on the other is the optional-shape trap. **It is not `regional.language`** (what the utility CHOSE) **and not the eleven catalogues** (what the bundle can DRAW) — `BR-CWP-105` names all three and says do not fold them |
| 2 | `POST /public/bills/lookup` | `CWP-002` | Bill number **plus** service postcode. Returns amount owing and a **masked** name and nothing else (`BR-CWP-019`). ⚠ Locks 15 min after 5 wrong pairs. ⊕ **BUILT 2026-09-05** (CR-068 wave P, screen half): mounted at `/api/{tenant}/portal/public/bills/lookup`, behind the same three guards as `/public/front`, on `lockout.FORM_QUICK_PAY` — reserved in `lockout.py` since wave B and used for the first time here. Answers **six keys and no more**, and the allow-list is `guest_fields.py`'s, written before the code: `number`, `amount` (the money cell — four stored, two displayed), `status` (one of `payable · settled · cancelled · replaced`, a WORD the catalogues turn into a sentence), `due_on`, `masked_name`, `replaced_by`. ⚠ A **paid** and a **voided** bill are ANSWERED rather than refused (`US-CWP-003` TC-4/TC-5) — silence would read as *no such bill* and send somebody who has already paid to the office; a **draft** is refused identically to a number that does not exist |
| 3 | `POST /public/bills/{ref}/pay` | `CWP-003` | ⊕ **BUILT 2026-09-05** (CR-068 wave R, `US-CWP-004`), and it replaces two earlier readings of this row. It said *"BLOCKED — no rails. Route exists and returns the held reason"*; then wave P declined to mount it at all, because *"a live unauthenticated route that answers only held is surface with nobody on the other side of it"* (`DEF-CWP-3704`). Both were right at the time and the rails have arrived. ⚠ **`{ref}` IS THE BILL NUMBER**, `BL-2608-0141` — the thing printed on the paper, never a payment reference and never a row id (B14 rule 31). Mounted at `/api/{tenant}/portal/public/bills/{number}/pay` behind the same three guards as `/public/front`. **SIX GUARDS IN ORDER:** the tenant off the path · quick pay switched on (`BR-CWP-002`) · no unpriced surcharge (`OQ-1394` CLOSED 2026-09-04, beta ABSORBS) · **the same `FORM_QUICK_PAY` five-tries lockout row 2 uses** · the number-and-postcode pair RE-PROVED through the same selector, burning a try on a miss and answering row 2's refusal byte for byte · the bill payable, for the figure the person agreed to. ⚠ **The figure is RE-READ at the commit and the browser's is only COMPARED** (`US-CWP-004` §7); a figure that moved is refused rather than silently charged. ⚠ **No card number reaches the process** — the body carries a gateway token, a brand and a last four (`BR-CWP-057`), and a card number, expiry or security code is refused BY NAME. Answers six keys, allow-listed in `guest_fields.py`: `reference`, `amount`, `paid_at`, `against`, `method` (`brand` + `last_four`), `receipt_sent` — **whether** a receipt went, never **where**, because `US-CWP-004` §4 makes that address deliberately a neighbour's. A silent gateway is a `503` and writes nothing (`TC-7`: *"a zero is a claim nobody can make"*) |
| 4 | `GET /public/premises/availability` | `CWP-008` | ⚠ An unknown address returns *"a person will look at it"*, **never a refusal**. ⊕ **`CR-200-BRC10` (PO 2026-10-29, 2A):** takes `unit=` (a LABEL). At a premises with more than one live, non-common-area unit the answer carries `units` (labels only, no occupancy) and `unit` (the label meant, or null); `job` is `null` until one is named. ⊕ **AMENDED 2026-10-30 (PO ruling A, `DEF-CWP-10690`):** `job` is `move_in` for every matched premises and every picked apartment, **occupied or empty** — never `new_connection`, which belongs only to an address not in Premises (and that answer carries `null`); occupancy is not read. The fees are the plan's MOVE-IN fees for a home (`rating.move_in_fees`) |
| 4a | `GET /public/premises/suggestions?q=` | `CWP-008` · `CWP-010` | ⊕ **`CR-200-BRC10` (PO 1A), BUILT 2026-10-29.** From the 4th character, at most 5 held addresses, each `{street, city, state, postal_code}` and nothing else — no id, no name, no occupancy (`BR-CWP-021`, B14 rule 31). Word by word over street, town and ZIP, through metering's matcher (`address_match.address_suggestions`). Same two throttles as row 4; under 4 characters `[]`, never a refusal |
| 5 | `GET /public/prices` | `CWP-008` | Connection fees, standing charges, deposits, per service, for that address. ⊕ **NOT BUILT BY WAVE C, 2026-09-04** (`DEF-CWP-3704`): `CWP-008` is answered whole by row 4, no wave-C screen reads a price list, and a live unauthenticated endpoint no screen reads is surface without a caller. The *What things cost* screen owns it |
| 6 | `POST /public/reports` | `CWP-006` | ⚠ Reporter **need not be a customer**. `gas_smell` returns the phone number and creates nothing. ⚠ **SINCE `CR-072` (2026-09-04) IT WRITES ONE ROW AND RETURNS THAT ROW'S `SR-` NUMBER** — it used to write a `service_requests` row AND an `interruptions` row and return the interruption's `RP-`. The `RP-` series is no longer served to a guest; a CLERK opens the interruption through `POST /service-requests/{id}/interruption` (`BR-CWP-101`) |
| 7 | `POST /public/requests` | `CWP-010` | The quick asks — re-read, missed collection, copy of a bill. ⊕ **BUILT 2026-09-04**, with a companion read `GET /public/quick-services` that serves the utility's OWN card list; a category the utility does not offer is refused at the edge (`BR-CWP-002`). ⊕ **`CR-200-BRC10` (PO, Ask us A):** optional `street`, `city`, `postal_code`, `unit` — a picked suggestion's parts and the apartment LABEL, never an id — re-matched on the server; a match links the request to the premises (and unit) through `create_from_portal(resolved_place=…)`; a typed address is still accepted as typed (`BR-CUS-070`) |
| 8 | `GET`/`PUT /public/applications/{draft}` | `CWP-047` · `CWP-009` | Upsert. **Saved from the first keystroke**, so a closed tab survives; no reference until submit. ⊕ **BUILT 2026-09-04.** `GET` was added because reopening the link is the half TC-1 actually tests; the `{draft}` is a browser-generated capability token, never a reference |
| 9 | `POST /public/applications/{draft}/submit` | `CWP-009` | ⚠ **Where paperless consent is taken** — wording version and all (`BR-CWP-087`). ⊕ **BUILT 2026-09-04**: one `service_request` through `customers`' own portal door, one `portal_consent`, and nothing else — no payment, no document, no account |
| 10 | `POST /public/track` | `CWP-012` | Reference **plus** a second fact. Returns **progress and never data** (`BR-CWP-024`). ⚠ Locks 15 min after 5. ⊕ **BUILT, and WIDENED 2026-09-05** (`7ac5d92c`, `US-CWP-005` TC-3 / `US-CWP-010` TC-7, `DEF-CWP-3939`): `selectors.TRACKABLE_SERIES` was `("request",)` and is now `("request", "payment")`, so somebody who paid with no login, kept `PAY-26-08841` and reloaded the tab can find their own receipt again. The second fact for a payment is the **postcode of the service address**, reached through `payments_seam.payment_by_number` and `bill_lookup`'s existing `account_premises_id → premises_postcode` walk — so a bill payable on a postcode is trackable on the same postcode **by construction**, not by a second rule. ⚠ **FIVE KEYS AND NO FIGURE:** `series`, `reference`, `status`, `reported_at`, `cleared_at`. No amount, no masked name, no account — `US-CWP-010` TC-7 says the amount is account data and a guest payer may be a neighbour. The receipt screen still shows its figure because the person reading it agreed to that figure ten seconds earlier on the same screen. Payments' FIVE states fold to THREE words server-side, so `posted` and `reversed` — ledger words — cannot reach a public page |
| 11 | `GET /public/help` | `CWP-011` | ⚠ `status = published` **in the query**. Draft and Not-shown never leave the back office. ⚠ **AS BUILT (wave D, 2026-09-04):** mounted at `/api/{tenant}/portal/public/help`, behind the same three guards as `/public/front`; answers `{answers, topics, visit_link}` — the topics are DERIVED from what is published and there is **no count of what is hidden** (`G88` reads the gate as data) |
| 12 | `GET /public/help/{slug}` | `CWP-011` · `CWP-060` | Falls back to English when the locale has no variant. ⚠ **AS BUILT:** `?locale=` carries the READER's browser language and the answer reports `asked_for`, `shown_in` and `is_fallback`, so the screen can say which language it is showing — a silent fallback would be a promise nobody made. A regional variant falls back to its own language first (`fr-CA` reads the French we have) and only then to English |
| 13 | `GET /public/service-centres` | `CWP-013` | ⚠ Only `is_shown_to_customers`. **The link 404s when none is shown** — no empty page (`BR-CWP-093`). ⚠ **AS BUILT:** each centre carries `cannot_do` computed by the SERVER, so four rows saying *no* are drawn rather than inferred from an absence |
| 14 | `GET /public/service-centres/{slug}` | `CWP-014` | Hours, allowed actions, what it takes, holiday closures from the tenant calendar. ⚠ **AS BUILT:** `today` carries FACTS and never a sentence — `next_open_weekday` (Monday = 0), `next_open_at` as `HH:MM`, `closed_for_holiday` and `next_holiday` with the calendar's own label. *"Closed today · Opens Thursday at 9:00am"* is written by the SCREEN, in the reader's own language, because a server that assembled it would ship an English sentence to eleven catalogues (B14 rule 35) |

## 2 · Portal edge — 71

All rooted at `/{tenant}/portal/`. **Every one filtered on both halves — the tenant and
the account set — in the query, never in the screen** (`BR-CWP-010`).

### Authentication and enrolment — 7

`POST auth/sign-in` · `POST auth/sign-out` · `POST enrol/find-account` ·
`POST enrol/verify-code` · `POST enrol/set-password` · `POST auth/forgot-password` ·
`POST auth/reset-password`

⊕ **AS BUILT (wave E, 2026-09-04):** all seven are live at `/api/{tenant}/portal/…` in `apps/portal/api.py`, on the third portal edge — its own file, its own `PortalSessionAuthentication`, its own `sbh_portal` cookie. The four enrolment routes carry `authentication_classes([])` so a stale STAFF cookie is never read on them (`BR-CWP-011`), and each is guarded by what it actually needs rather than by the screen order: the enrolment lockout, a proven one-time code, or a single-use link.

⊕ **AND A TWELFTH ROUTE THE TABLE ABOVE DOES NOT LIST — `POST enrol/consequences`.** `BR-CWP-039` requires a consequence panel naming the account, the address, the services and **the balance** before the button, and that is a READ nothing else served. It is not folded into `verify-code`'s body because the disclosure deserves its own guard: it answers only for a code whose `consumed_at` is set, so the panel cannot be fetched by somebody who merely matched the account.

⚠ `enrol/find-account` returns **matched or not matched and nothing else** — no name, no
balance, no address (`BR-CWP-032`). ⚠ `enrol/verify-code` sends only to a contact
**already on file** and dead-ends into *"ring the office"* when none exists
(`BR-CWP-033`, `BR-CWP-034`). ⚠ `auth/forgot-password` returns the **same** response for
an address with a login and one without (`BR-CWP-038`).

### Session and the account set — 4

`GET session` · `GET accounts` · `POST accounts/add` · `POST sessions/revoke-all`

### Balance — 2

`GET accounts/{id}/balance` · `GET balance/summary`

⊕ **AS BUILT (wave E, 2026-09-04):** both live, composing `payments`' own published reads in `apps/portal/seams/payments_seam.py` and computing nothing. ⚠ **`outstandings()` IS NAMED BY THE EXECUTION PLAN AND IS DELIBERATELY NOT COMPOSED** — it joins the collection ladder, the live payment plan, the notice counts and the bad-address flag onto every row, and every one of those is on `BR-CWP-052`'s held-back list or above the issued bill. `billing_seam.outstanding_positions` is the same arithmetic without them, and is what `outstandings()` itself composes. Decision logged 2026-09-04.

⚠ **Build these first.** The blueprint names the balance read *"the single
most-requested number in the whole product"* and nothing publishes it today. ⚠ **Never
cached** (`BR-CWP-047`). ⚠ `balance/summary` totals **without merging into one invoice**.

### Bills and documents — 6

`GET accounts/{id}/bills` · `GET bills/{no}` · `GET bills/{no}/document` ·
`GET bills/{no}/explain` · `GET accounts/{id}/documents` ✅ ·
`GET accounts/{id}/final-bill` ✅ ·
`GET accounts/{id}/statement` ⚠ **BLOCKED — `OQ-1395`**

⊕ **AS BUILT (2026-09-04) — `accounts/{id}/final-bill`, `CWP-032` (`US-CWP-037`).** ⚠ **IT
IS NOT UNDER `bills/{no}` AND THAT IS THE SHAPE RATHER THAN A CHOICE:** there is exactly ONE
final bill per account, a customer reaches it from a move-out letter rather than by knowing
its number, and the SETTLEMENT is what the screen is about. Every figure is
`billing.final_bill.settle_final_bill`'s — the same function that settles the account for a
clerk — so a customer and a counter clerk cannot quote different closing figures
(`US-CWP-037` §7). ⚠ **BUILDING IT FOUND THAT NOTHING COULD SETTLE ON A DEPOSIT-HOLDING
ACCOUNT AT ALL (`DEF-CWP-3842`)**: the caller asked for an accrual without naming the day it
accrues to, and the engine answers `None` to that by design. `settle_final_bill` now passes
`as_of=invoice.period_end` — the move-out day, off the bill and not off a clock. `deposit`
is **absent, never `$0.00`**, on an account that holds none; `remainder` is **signed**, and
`path` is the engine's word (`BR-CWP-048`: a refund, never a carried credit) rather than a
reading of that sign.

⚠ `bills/{no}/document` serves **the file that was issued**, from its pinned template.
It never re-renders (`BR-CWP-045`). ⚠ `bills/{no}/explain` must sum exactly to the
stated difference (`BR-CWP-046`).

⊕ **AS BUILT (wave H, 2026-09-04) — `accounts/{id}/documents`.** ⚠ **IT SAYS WHAT WAS SENT AND
NEVER THAT IT ARRIVED**, and that is the contract rather than a presentation choice. The body's
`state` is one of **four** — `sent` · `queued` · `held` · `could_not_send` — and `delivered` and
`bounced` are DELIBERATELY not among them: both are provider facts, `delivery_ops.
UNPOPULATED_STATUSES` records that nothing on this deployment can write either, and `OQ-1399`
closed 2026-09-04 with the portal as a CONVENIENCE COPY (`BR-CWP-083`: post and email remain the
delivery record). Every row therefore carries `delivery_reported: false` with its reason, as DATA
rather than as a convention a screen might forget.

⚠ **`documents: null` IS NOT `[]`.** Null means the queue could not be asked; `[]` means it was
asked and this account has nothing sent — which for a new customer is the truth. A screen that
rendered one empty state over both would tell a customer of eleven months that we never wrote to
them, which is the `accountDetailTabs.tsx` FRAME's own reasoning inherited.

⚠ **ONE ROW PER DOCUMENT, NOT PER CHANNEL.** The queue's grain is one row per document per channel
(`BR-BIL-016`), so a bill posted AND emailed is two rows there and ONE here, with `routes` naming
every route it went by and each route's own state — a leg that failed is named, never dropped
(`BR-BIL-036`). **No database id crosses this wire** (B14 rule 31): `reference` is the number on
the paper, or `null` with the screen saying so in words.

⚠ **THE READ IS `notifications`', NOT THE PORTAL'S.** `apps/notifications/correspondence_reads.
account_correspondence` is published by the module that owns `outbound_messages`, so the staff
Account details Documents tab — today a FRAME with no endpoint — can be built on the same read
rather than on a second copy (PO ruling 2026-09-04, `12-reuse-map.md`).

### Usage and readings — 5

`GET accounts/{id}/usage` ✅ · `GET accounts/{id}/readings` ✅ · `GET readings/{id}` ⚠ **NOT BUILT** ·
`POST accounts/{id}/readings` ⚠ **`OQ-1393`** · `GET accounts/{id}/equipment` ✅

⚠ **THREE OF THE FIVE ARE BUILT (`CR-068` wave H, 2026-09-04) AND THE OTHER TWO ARE ABSENT FOR
DIFFERENT REASONS.** `POST accounts/{id}/readings` is `US-CWP-042`'s, wave 3 — a WRITE with no screen
is a route into billing nobody has clicked. **`GET readings/{id}` is not built at all and is not
deferred: `CWP-034` opens a reading IN PLACE** rather than at its own address, so the row's
correction comes down with the list. A route with nothing calling it is surface with no caller
(`DEF-CWP-3704`); if a later screen needs a single reading, that is the wave that adds it.

⚠ **THE THREE BUILT ROUTES READ `metering`'s OWN PUBLISHED READS AND COMPOSE NOTHING** — the same
`monthly_usage_reads.usage_payload` the staff Account details Usage tab draws
(`04-docs/05-modules/15-portal/12-reuse-map.md`). Each is `no-store`, and each intersects the account
id with the session's set IN THE QUERY (`BR-CWP-010`).

⚠ `POST readings` calls **the same validation service** a staff read calls — high, low,
rollover, window — and lands `awaiting_review` (`BR-CWP-067`, `BR-CWP-068`). A second,
weaker validation path here is a route into billing nobody checked.

### Payments, methods and autopay — 8

`GET accounts/{id}/payments` · `GET payments/{ref}/receipt` ·
`POST accounts/{id}/payments` ⚠ **BLOCKED** · `GET payment-methods` ·
`POST payment-methods` ⚠ **step-up** · `DELETE payment-methods/{id}` ⚠ **step-up** ·
`GET accounts/{id}/autopay` · `PUT accounts/{id}/autopay` ⚠ **BLOCKED**

⚠ Adding or removing a stored method **requires a fresh one-time code** — it is the one
action that redirects money (`BR-CWP-040`).

⊕ **AS BUILT (wave G, 2026-09-04) — and the PATH DIVERGES FROM THE ROW ABOVE.** The money
list is served at **`GET portal/payments`**, over the session's WHOLE account set, rather than
at `accounts/{id}/payments`. `GET portal/bills` took the same shape in wave G and the contract
was never annotated, so the divergence already existed and was invisible. **Both screens answer
one question for one person** — a landlord holding four accounts reconciling one bank statement
— and an id in the path would be a database id in an address bar (B14 rule 31), which is why
`/account` and `/my-details` carry none either. `BR-CWP-010` is satisfied identically: the set
is the session's and the intersection is in the query. It composes **payments' own S33 read**
(`selectors.payment_queryset` + `payment_row`, the pair the staff Payments tab uses) and
**`billing.selectors.account_credit_notes`**, then NARROWS: no row id, no `customer_name`, no
`memo`, and — `BR-CWP-051` — **no write-off reason, which is not selected, not serialised and
not in the body**. ⚠ `billing.Adjustment` **has no writer anywhere in this product**, so a
goodwill concession is read as a `CreditNote`, which is where `credit_notes_api.py` puts one.
⚠ **THERE IS NO PUT, PATCH OR DELETE ON A PAYMENT ON THIS EDGE and `urlpatterns` is the proof**
(`US-CWP-048` TC-3). Decision logged 2026-09-04.

### Credits, refunds and adjustments — 3

`GET accounts/{id}/credits` · `GET accounts/{id}/refunds` ·
`GET accounts/{id}/adjustments`

⚠ **Credit and refund are different things** and customers use the words
interchangeably. A credit comes off the next bill; a refund is money sent back. ⚠ **The
credit figure is re-read every load** — one real on Tuesday can be spent by Thursday.

⚠ **BUILT 2026-09-05 AS ONE ROUTE — `GET accounts/{id}/money-back` — AND THE REASON IS
THE RULE IN THE PARAGRAPH ABOVE.** `CWP-045` is ONE screen and its whole job is that the
two halves are shown together and told apart (*"a credit comes off your next bill. A
refund is money sent back."*). Two round trips would let them be read a second apart, on
a figure `BR-CWP-047` forbids caching. The body carries `credits` and `refunds` under
their own names, so both reads above are answered and neither is a second arithmetic —
the credit half calls `billing.selectors.account_credit_notes` (`CR-059` CS-37, the same
read the staff Credits tab and `CWP-041` use) and the refund half `payments.selectors
.refund_row`. **`GET accounts/{id}/adjustments` is NOT built**: `billing.Adjustment` has
no writer anywhere in this product, which the paragraph above §160 already records.
Decision logged 2026-09-05.

### Payment plans — 6

`POST accounts/{id}/plans/preview` · `POST accounts/{id}/plans/request` ⚠ **`OQ-1391`** ·
`GET accounts/{id}/plans/current` · `GET accounts/{id}/plans/offer` ✅ ·
`POST plans/{id}/accept` ⚠ **`OQ-CWP-1568`** · `POST plans/{id}/decline` ⚠ **`OQ-CWP-1568`**

⚠ `plans/offer` and `plans/{id}/accept` are the endpoints the blueprint's whole §17 audit
was written for: **a plan activates on the customer's signature alone**, so
`agreement_sent` means offered-and-waiting, and until these exist the utility raises a
plan the customer cannot see, cannot accept, and hears about only by telephone.

⊕ **AS BUILT (wave M slice, 2026-09-04) — three of the six.** `POST accounts/{id}/plans/preview`,
`POST accounts/{id}/plans/request` and `GET accounts/{id}/plans/current` are live and **keep the
account-scoped shape above**, because a plan spreads ONE account's arrears and the switcher names
which; `_account_in_set` intersects the id with the session's set IN THE QUERY before anything is
read, so an account outside it answers the same 404 an account that does not exist answers. ⚠ **THE
PREVIEW CALLS `apps.customers.payment_plan_service.preview` — THE SAME FUNCTION
`POST /accounts/{id}/payment-plans/preview` CALLS FOR A CLERK** (❄️ GT-47, `BR-CUS-043`), so the
portal contributes not one line of instalment arithmetic and the two surfaces cannot hand out
different figures. It writes nothing and says so on the wire (`writes: []`). ⚠ **The two-to-twelve
range is enforced at THIS edge and nowhere else**: `validate_proposal` refuses only
`installments < 1`, so it is an INPUT constraint of the portal's, refused by name. ⚠ **`…/plans/request`
is NOT a new write point** — `OQ-1391` closed 2026-09-04 option (a) and `BR-CWP-066` says the ask
*"raises an ordinary service request under `CR-072`, never a request of a new kind"*, so it is a
fourth SHAPE of `services.raise_service_request` and `write_points.py` still declares six kinds.
**No `payment_plan` row is written and the response says `plan_created: false` on its face.**

⊕ **AS BUILT (wave H, 2026-09-04) — `GET accounts/{id}/plans/offer`, and NEITHER of the two POSTs.**
The read serves the one plan at `agreement_sent`, or `offer: null`; its figures come from
`plans.payment_plans_for_account`, the S24 wizard's own read, so `US-CWP-053` §7's *"the figures on
the offer must be byte-identical to the plan that activates"* holds by construction rather than by
assertion. **`accept` and `decline` are NOT built and are not deferred quietly:** a plan signature
starts a payment schedule and `BR-CWP-001` allows the portal six kinds of row, none of them this
one — `write_points.py` says adding a seventh *"is a ruling and not an edit"*, and `G81` fails the
build on one. `OQ-CWP-1568` puts it to the Product Owner; meanwhile all three controls render
**visibly held with their reason** (`BR-CWP-056`), which is how `08-screen-layouts.md` already
draws *Accept this plan ✓*.

⚠ **ONE FIELD ON THIS BODY IS A NAMED ABSENCE AND WILL STAY THAT WAY UNTIL RULED.**
`expires_on: null` with `expires_on_unavailable: "OQ-CWP-1566"` — **no column holds an offer's
expiry** (`payment_plans` has `proposed_on`, `agreement_sent_on`, `signed_on`, `closed_on` and
nothing else about time), so `US-CWP-053` TC-4's refusal after 16 September cannot be enforced and
the screen does not print a deadline this product could not honour.

⚠ **`offered_by` IS NO LONGER ONE OF THEM — `OQ-CWP-1567` CLOSED 2026-09-08, option (a)**
(`CR-085` `CPB-21`; decision log of that date). ~~The clerk exists only on a
`payment_plan.rows_written` audit row, which is pruned on a retention schedule.~~ **The plan
keeps the fact itself now**: `payment_plans.offered_by_user_id`, an FK to `identity.User`, written
by `propose_payment_plan` from the actor it was already given. The body carries `offered_by` as a
**NAME** — resolved in `payments`, because the portal may not read `identity` at all
(`BR-CWP-004`, `G91`) — and **no id**, which is B14 rule 31. `offered_by_unavailable` is `null`
where a person is named and `"not_recorded"` where none is: a plan written before the migration,
or one a job wrote with no person behind it. **Nothing was backfilled** — the trail is pruned, so
a backfill would be right for recent plans and fabricated for the rest.

### Level pay — 2

`GET accounts/{id}/level-pay` ✅ · `GET accounts/{id}/level-pay/standing` ✅ ·
`POST accounts/{id}/level-pay/join` ⚠ **`OQ-CWP-1568`**

⊕ **AS BUILT (2026-09-04) — `…/standing`, `CWP-066` (`US-CWP-055`).** ⚠ **IT SITS UNDER THE
READ ABOVE BECAUSE IT IS THE SAME SUBJECT ASKED A DIFFERENT QUESTION:** `/level-pay` is *what
would I pay if I joined*, `/level-pay/standing` is *what am I paying and where do I stand*.
The standing body carries **none of the offer's figures** — no trailing total, no average —
because repeating them would be a second arithmetic over one fact; it reads
`budget_service.effective_level`, the cached `variance_balance` whose truth is the
append-only events, and each re-levelling as an event row. `ahead` / `behind` travel as a
DIRECTION beside a positive size and the catalogue writes the sentence (B14 rule 35);
`level_override_reason` is **not on the wire at all** (`BR-CWP-052`). A customer who is not
enrolled gets `standing: null` and `join_at`, and is ROUTED rather than refused — a 404 is
indistinguishable from a broken page.

⊕ **AS BUILT (wave H, 2026-09-04) — the READ.** It composes exactly what
`GET budget-billing/{id}/eligibility` composes for a clerk —
`billing.selectors.budget_history_for`, `billing.budget.compute_level` and the tenant's own
`settings_seam.budget_billing()` — so a customer and a counter clerk cannot be handed different
levels (PO ruling 2026-09-04). Twelve months of `$1,501.09` give a monthly average of `$125.09`
and a level of **`$125.00`**, and BOTH figures are on the body because *"$125.09 rounded to
$125.00"* is the sentence that explains the level.

⚠ **THE AVERAGE IS THE ONE PIECE OF ARITHMETIC HERE THAT IS NOT `apps.billing.budget`'s**, because
that module publishes the ROUNDED level and not the raw average `US-CWP-054` TC-1 asks to show. It
divides by the TENANT'S WINDOW and not by the list length — `compute_level`'s own docstring names
that trap — and `test_us_cwp_054_level_pay.py` asserts the average ROUNDS TO the level, so the two
figures on one line cannot drift apart quietly.

⚠ **`settle_up_month` IS `null` UNTIL A TENANT PICKS ONE** and is never 6: `settings_families`
ratifies no month (*"rule names the parameter, ratifies no month"*), so a body that defaulted to
June would be right for one utility and silently wrong for every other. `level` is `null` WITH ITS
REASON and never `0.00` — a zero monthly amount is a real, chooseable figure that would read as
*this customer pays nothing*. **`…/join` is not built**: enrolment writes `account_budget_status`,
which is not one of `BR-CWP-001`'s six kinds, so the control is held and `OQ-CWP-1568` is the
ruling that would open it.

### Service requests — 8

`GET request-categories` · `POST requests` · `POST requests/{ref}/submit` ·
`POST requests/{ref}/withdraw` · `POST requests/{ref}/notes` · `GET requests` ·
`GET requests/{ref}` · `GET requests/{ref}/fees`

⚠ **Exactly four transitions and no more** (`BR-CWP-075`). ⚠ Every row carries channel
`customer_portal` (`BR-CWP-076`). ⚠ `GET requests/{ref}` returns the customer-safe
history — transitions plus notes flagged customer-visible, **never internal routing
comments** (`BR-CWP-078`).

⊕ **AS BUILT (2026-09-04) — `GET requests` (the hub, `CWP-046`) and
`GET accounts/{id}/stop-or-restart` + `POST accounts/{id}/stop-or-restart/ask` (`CWP-052`).**

⊕ **AS BUILT (2026-09-05) — `GET requests/{ref}`, `POST requests/{ref}/withdraw` and
`POST requests/{ref}/notes` (`CWP-051`), plus TWO ROUTES THIS SECTION DOES NOT LIST:
`POST bills/{number}/dispute` (`CWP-055`) and `POST questions` (`CWP-054`).**

⚠ **THE QUERY HANGS OFF THE BILL AND THE QUESTION HANGS OFF NOTHING, AND EACH ADDRESS IS
THE STORY IT SERVES.** A query is always ABOUT one bill, so the bill is in the path and the
lookup is `bill_in_set` — the same one every other bill route goes through, with both halves
of `BR-CWP-010` in the query. A question may be about **no** bill at all (`US-CWP-066`
TC-5: *"accepted as a general question and routed by category"*), and a path segment cannot
be absent, so the bill travels in the body where it can be.

⚠ **BOTH ARE SHAPES OF THE `service_request` WRITE POINT AND `write_points.py` IS
UNTOUCHED** — six kinds, one public function, eight shapes. `CR-072` (PO 2026-09-04): *"all
the request coming from portal should go in Service request"*.

⚠ **`GET requests/{ref}` FILTERS ON A PHONE AND NOT ON AN ACCOUNT, AND THAT IS
`OQ-CWP-1680`.** A portal service request carries no `account_id` — `create_from_portal`
refuses the field by name under `BR-CWP-026` — so there is nothing for `BR-CWP-010`'s
account set to intersect against. Three clauses go in the query instead: this tenant, the
channel, and a phone one of this login's own accounts holds. Two customers sharing a
telephone number would see each other's requests, which is narrower than the guest tracker
already ships with and is not narrow enough to be the answer.

⚠ **`POST bills/{number}/dispute` RAISES NO `meter_reads` MARKER AND HOLDS NO COLLECTION**,
and both absences are on the wire as `reading_marked: false` and `collection_held: false` so
no screen can imply otherwise — `OQ-CWP-1681` and `OQ-CWP-1682` / `OQ-420`.

⚠ **THE WRITE IS AT `/ask` AND NOT AT THE READ'S OWN ADDRESS, AND THE SUFFIX IS THE
CONTRACT.** `POST` to the same path would read as *stop this service*, and this route does
nothing of the kind: it puts a row on a clerk's worklist. `plans/request` beside it took the
same shape for the same reason, and `BR-CWP-066`'s ruling names the verb — **ask**, never
*apply* and never *do*.

⚠ **`GET requests` CARRIES NO ACCOUNT ID AND CANNOT.** A portal service request carries **no
account at all** — `create_from_portal` refuses the field by name under `BR-CWP-026`
(*"a public form may create work and may never change an account"*) — so the list is the
LOGIN's, and it is `customers_seam.my_requests`: this tenant, the channel, and any phone one
of this login's own accounts holds, all three **in the query** (`BR-CWP-010`). ⚠ **ONE READ,
NOT TWO** — the hub arrived with its own email-matched version of that read and it was
deleted at merge (`12-reuse-map.md`: two reads of one fact are two answers). What the link
cannot see is a request a CLERK raised at the counter;
the body carries `lists_only_portal_requests: true` so no screen may imply otherwise, and
whether it should widen is **`OQ-CWP-1680`** (OPEN). A utility with requests switched off
**404s** rather than serving an empty hub, because a reachable empty page reads as *this
utility takes no requests online* — a different sentence from *this page is not here*
(`BR-CWP-093`).

⚠ **`stop-or-restart` IS A COMPARISON READ AND AN ORDINARY REQUEST WRITE.** The GET quotes
the standing charge from the PLAN through `apps.rating.seams.base_charge_for` — the one
implementation of `BR-RAT-088`'s precedence, and `DEF-154` is what having two cost — plus the
connection fee and deposit `CWP-008` already quotes. **The portal's own arithmetic is two
multiplications and one comparison**: `5 × $18.50 = $92.50` against `$185.00 + $150.00 =
$335.00`, so stopping is cheaper; at nineteen months `$351.50` exceeds `$335.00` and the
answer flips. A missing figure travels as a REASON and never as `$0.00` (`US-CWP-062` TC-8).
The POST is the **fifth SHAPE** of the existing `service_request` write point, not a seventh
write point: `write_points.py` is untouched, the account stays open (`BR-CWP-080`) and
nothing here disconnects anything.

### Messages and notices — 3

`GET messages` · `POST messages/{id}/read` · `GET accounts/{id}/notices`

⚠ `GET notices` shows **every notice sent AND every notice deliberately not sent**, with
its reason. A skipped notice produced no document, so the one the customer most needs to
know about is otherwise invisible (`BR-CWP-085`).

### My details, preferences and consent — 5

`GET details` · `PATCH details` · `GET details/preferences` ·
`PUT details/preferences` · `POST details/paperless/withdraw`

⚠ `PATCH details` accepts **email, mobile and postal address only**. Legal name and
account holder are refused with a route into a request — they change who owes the money
(`BR-CWP-026`). ⚠ `PUT preferences` must **refuse to switch off print** rather than
accepting a value it ignores.

⊕ **AS BUILT (wave G, 2026-09-05) — three of the five, and the verbs and paths differ
from the row above.** `GET my-details` and `POST my-details/save` shipped with `CWP-024`;
this wave adds `GET my-details/preferences`, `POST my-details/preferences/save` and
`POST my-details/paperless/withdraw`. **`POST` rather than `PATCH`/`PUT`** because this
edge already has one verb for a write (`my-details/save`), and a second convention on
the same screen is a convention nobody can rely on.

⚠ **AND THE PRINT FLOOR IS SIX KINDS, NOT FOUR** — `invoice`, `payment`, `notice`,
`plan`, `account` and `move`, read from `notifications.CHANNEL_FLOOR_BY_SOURCE` rather
than listed in the portal (PO 2026-08-30: *"don't switch of print for any document it
is awayls on"*). `post_on` in a body is refused **by name**, at the endpoint.

⚠ **WHAT `preferences` DOES NOT SERVE, and it is a finding rather than a deferral
(`DEF-CWP-3860`, `OQ-CWP-1660`):** a per-event customer choice. `notification_rules` is
the TENANT's row, one per event per tenant; the customer's own store is two booleans on
the account plus the language. The read says `applies_to_every_document: true` so the
screen can print it.

### Delegates — 5

`GET details/access` · `POST details/access/invite` ⚠ **`OQ-1396`** ·
`DELETE details/access/{id}` · `GET invitations/{token}` ·
`POST invitations/{token}/accept`

⚠ Only the account holder may invite. ⚠ Every action by an invitee is recorded under
**their** name (`portal_delegate.audit_actor_id`), not the holder's.

### Protections, arrears and account facts — 3

`GET accounts/{id}/protections` · `GET accounts/{id}/arrears` ·
`GET accounts/{id}/account-facts`

⚠ `GET protections` returns **three different lifetimes and three different sentences**
(`BR-CWP-090`). ⚠ `GET arrears` reads **this account's own disconnection case**, not the
cadence settings, and renders an unmapped tier as an **absence** (`BR-CWP-092`).

### Help, tips and feedback — 4

`GET help` · `GET help/{slug}` · `POST help/{slug}/feedback` ·
`GET tips?screen={screen}`

⚠ `GET tips` returns **at most one** tip — on, in season, top of the list — and **an
empty response is a normal response**: the slot closes up and nobody can tell it was
there (`BR-CWP-095`).

## 3 · Back office — 12

In the **staff** app under `Settings → Configure → Customer portal`, plus one card in
`Reference data`. Not a tenth top-level tab — Settings already carries nine.

`GET/PUT settings/portal` (2) · `GET/PUT settings/portal/branding` (2) ·
⚠ **AS BUILT (wave A, 2026-09-03): both pairs live in `apps/portal/backoffice_api.py`** (the table is portal-owned, B2 §2 — plan §0 row 18), joined by a thirteenth route, **`GET settings/portal/qr.svg`** (the address as a QR code, `?download=1` to save it; US-CWP-069 TC-1). Help, tips and centres stay in `tenancy`. ·
`GET/POST settings/portal/help` (2) · `PUT/DELETE settings/portal/help/{id}` (2) ·
`POST settings/portal/help/{id}/publish` (1) · `GET/POST/PUT/DELETE
settings/reference-data/service-centres` counted as 2 · `GET/POST/PUT/DELETE
settings/portal/tips` counted as 1

⚠ **AS BUILT (wave D, 2026-09-04): all ten of these live in
`apps/tenancy/published_content_api.py`, and an answer or a centre is addressed
by SLUG rather than by `{id}`** — B14 rule 31 makes a URL a visible value, so a
uuid may not be one. The routes are `GET/POST settings/portal/help`,
`GET/PUT/DELETE settings/portal/help/{slug}`, `POST
settings/portal/help/{slug}/publish`, `POST settings/portal/help/reorder`,
`GET/POST settings/portal/tips`, `PUT/DELETE settings/portal/tips/{id}`, `POST
settings/portal/tips/reorder`, `GET/POST
settings/reference-data/service-centres` and `GET/PUT/DELETE
settings/reference-data/service-centres/{slug}`.

⚠ **AND `GET settings/portal/tips` ANSWERS THREE THINGS, NOT ONE (2026-09-05,
`DEF-CWP-3820`).** The body is `{tips, all_screens, word_guidance}` — the rows,
the **six** screens a tip may be aimed at (`TIP_SCREENS`), and the **fifteen**-word
guidance the editor flags against. It grew when `CWP-073`'s editor was built,
and the reason is the first paragraph of `CLAUDE.md`: a closed set typed into
the front end is a set that never grows on screen, because the row exists, the
API serves it, `tsc` and every test pass, and the picker simply never offers it.
`GET/POST settings/reference-data/service-centres` has answered
`{centres, all_actions, all_payment_methods}` since wave D for the same reason;
this is that shape, one route up. The four WRITES answer the rows only — the
closed sets cannot move — so a client merges into the cached view rather than
replacing it.

⚠ **AND ONE GUEST ROUTE IS SERVED FROM THAT SAME MODULE:** `POST
/portal/public/help/{slug}/feedback` — the read and the *did this help?* vote.
`help_answer_feedback` is a **tenancy** table and B2 §2 forbids a cross-module
write, so `apps/portal` could not write it wherever it were mounted; it wears
the portal's own per-address and per-tenant throttles and its in-flight budget.
`BR-CWP-001`'s four write points are untouched — see `DEF-CWP-3727`.

⚠ **Branding READS the logo, colours and names from `Company → Profile` and keeps no
copy.** Two editable logos is how a utility ends up with two logos.

## 4 · Webhook — 1

`POST /webhooks/payments/{provider}` — ⚠ **idempotent on the key the schema already
reserves.** The gateway will send the same settlement twice and the account must show one
payment (`BR-CWP-059`).

⚠ **This file is no longer a stub.** It was one docstring line when the blueprint was
written; it is **577 lines with 15 tests as of 2026-09-03** (`CR-060` C21). **Verify
before building** — this may be largely done.

---

## Why the count moved from 82 to 98

The estimate of 82 was made from the blueprint's screen count before the endpoint list
was written out. Writing it out added sixteen, in three places, and none of them is new
scope:

* **The signed-in surface needed 71, not 55.** Reading the fifty-four `P` screens against
  the four write points produced more distinct reads than a screen count implies — the
  §17 audit alone found nineteen things the back office holds that reach no screen, and
  each of those is a read: protections, arrears, account facts, adjustments, notices,
  credits, refunds.
* **Plans needed six endpoints, not two.** The offered-plan state — the one the whole §17
  audit was written for — needs an offer read, an accept and a decline of its own.
* **Delegates needed five, not three.** An invitation is accepted by somebody who is not
  yet signed in, so the token read and the accept sit outside the account set.

The count of screens, specifications, stories, rules and tables is **unchanged**.

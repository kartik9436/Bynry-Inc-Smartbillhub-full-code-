# J40 — Move-out → final bill → deposit settled → refund sent (`$63.40 − $150.00 − $3.20 = −$89.80`, a refund and not a credit, because there is no next bill)

---
id: J40
tier: 2
rules: [BR-CWP-048, BR-CWP-049, BR-CWP-060, BR-CWP-075, BR-CWP-076, BR-CWP-078, BR-CWP-079, BR-CWP-080, BR-CWP-081, BR-CWP-082, BR-CWP-047, BR-CWP-010]
stories: [US-CWP-037, US-CWP-049, US-CWP-056, US-CWP-060, US-CWP-061, US-CWP-063, US-CWP-064]
# Wiring: every story above cites `J40` in its own `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J40.spec.ts`. Release 3 (the request,
# the final bill, the credits); release 5 (`US-CWP-049`, refund to the original
# method) — step 10 is written as that boundary.
# ⚠ BLOCKED ON OQ-1392 — can a customer CLOSE their own account, or only ASK to?
# A move-out settles a deposit and issues a final bill, so self-serve means a
# mistaken click has a refund at the end of it. The request is built; the
# self-serve close raises `NotImplementedError("OQ-1392")` (step 4).
# ⚠ THE DANGER-TIER COMMIT (B14 rule 6) — the one place in the portal the brand
# outline is the commit — and the screen states the distinction customers get
# wrong BEFORE the button: a move-out closes and settles; a disconnect leaves the
# account open and standing charges keep running.
---

**Intent.** The request with the most already built behind it — an eleven-state service
request, a document checklist by request type, a complete transition history, and a field
for channel `customer_portal` that **nothing has ever written** — driven from the front by a
customer leaving. The customer makes **four of the eleven transitions and no more**: create a
draft, submit, answer a question, withdraw. Approving stays with the utility. The move-out
settles the deposit **with its accrued interest** and can end in a **negative balance, which
is a refund rather than a credit to carry forward**, because there is no next bill to carry
it to. The refund goes back **the way the money came in** (release 5), and the customer can
see it is a refund and not a credit — two words they use interchangeably.

**Upstream leaves (handoff in).** J36's session for **Maria Alvarez**, `1408 Elm St · A`,
deposit `$150.00` taken 4 Mar 2021, interest to date `$3.20` (`CWP-065`). Tenant `pine-hill`
with `requests_enabled = true`, six request categories in the customer's words. A **closed**
account at `91 Cedar Row, Austin TX 78704` (her forwarding address). A clerk **Sarah Miller**
(Sarah at the office). The move-out checklist for this request type: *Photo ID · to confirm
who you are* · *Proof of address · a tenancy agreement or a deed* · *Landlord's consent · you
are not the owner*. Two credits of `$25.88` (goodwill from a reading dispute; overcharge
corrected), 12 Jul 2026, both used on `BL-2607-0139`. Standing charge on the plan `$18.50`
a month; connection fee `$185.00`. Clock **2 Sep 2026** (so 15 days' notice to 17 Sep).

**This journey leaves (handoff out).** `SR-26-0056` (move-out, channel `customer_portal`
— **the first row in the fixture ever to carry it**), its customer-visible transitions and
one hidden internal note; a closing read `154,310` on 17 Sep by a reader; a **final
invoice** `$63.40` for 1–17 Sep; the deposit settled `−$150.00` and interest `−$3.20`; a
**refund row `$89.80`** (raised 18 Sep, approved 19 Sep by the office, sent 21 Sep) — and
**no credit note** on the closed account; the account **closed**. `CWP-045` shows the refund
timeline; `CWP-027` shows the final bill.

**Fixture.** Screens `CWP-046` → `CWP-048` → `CWP-051` → `CWP-049` → `CWP-032` → `CWP-045`
(and `CWP-052` for the distinction). Internal note *"route to Tuesday crew, low priority"*
(must never appear). Refund by cheque `#10241` to `91 Cedar Row`; card case `Visa
••••8812` (release 5); expired-card case `Visa ••••4417`.

| # | Actor · action | Expected outcome (contract) | Downstream assertions (record · channel · money · immutability) | Rule |
|---|---|---|---|---|
| 1 | `CWP-046` — *What do you need?* | Six `ErrandCard`s **in the customer's words**: *Move out · close this account and settle up. We need eight days' notice* · *Move to a new address · take your account with you* · *Add a service* · *Stop service for a while* · *Report a problem* · *Something else*. **OPEN REQUESTS** `MiniTable` empty state naming what fills it | Cards are the tenant's **configured categories** — a renamed category shows its new label; a hardcoded list is the defect. With `requests_enabled = false` the hub is unreachable **and** the endpoint refuses | BR-CWP-075 · BR-CWP-080 |
| 2 | *Move out* → `CWP-048`, step 3 of 3 | `KVList` Leaving `1408 Elm St · A` / Last day of service **17 Sep 2026** / Final bill goes to `91 Cedar Row, Austin TX 78704` / Deposit held **`$150.00`**. `ConsequenceBox`: *We read your meter on 17 September · A final bill settles your deposit · **The account closes. You cannot undo this.*** Rail **NOT THE SAME THING**: ***Moving out** closes the account and settles the deposit · **Stopping service** leaves the account open — standing charges keep running.* · ⓘ *Moving within our area? A transfer keeps your history and your deposit.* | **The commit is `Button(danger)` *Send this request ✓*** — outlined brand, filled on hover — **not** the standard primary. The deposit figure **equals `CWP-065`'s `$150.00`**. Fewer than eight days' notice is refused **naming the notice period**. A move within the area offers a **transfer** instead | BR-CWP-080 · B14 rule 6 · `US-CWP-061` TC-4/5/7/10 |
| 3 | *Send this request ✓* (2 Sep, 9:14am) | `SR-26-0056` in `submitted`, **`channel = customer_portal`** — assert this is the **first** row in the fixture carrying the value, proving the field was inert before. On a clerk's worklist (`REQ-01`). The customer may **withdraw until it is approved** | ⚠ A double-click → one request. Nothing on the account changed: `account` row byte-identical, deposit untouched, no money moved | BR-CWP-076 · BR-CWP-079 · BR-CWP-026 |
| 4 | **boundary · `OQ-1392`** — call the self-serve **close** path | `NotImplementedError("OQ-1392")` — the request **lands for a person** until it is ruled (ask only · a cooling-off window · self-serve outright — the PO's three options) | A lane may not choose. The commit was already the danger tier either way | BR-CWP-082 · `OQ-1392` |
| 5 | `CWP-051` — *Track your request* (3 Sep) | **PROGRESS** `ChecklistTimeline` × 6: *You sent it · 2 Sep, 9:14am · through the portal* done · *We picked it up · 2 Sep, 2:40pm · Sarah at the office* done · **We need something from you · 3 Sep** current (*proof of address and your landlord's consent*) · *We decide · usually the same day the documents arrive* · *Final reading and bill · 17 Sep* · *Account closes*. **DETAILS**: Reference `SR-26-0056` / Last day of service 17 Sep / Waiting on *two documents* / **Open for `1 day`** (computed, not stored). Actions *Add a note* — and **no *Withdraw*** (⚠ AMENDED 2026-09-19, `OQ-CUS-12486`: the customer's withdraw door closed with the clerk's; assert the control is ABSENT) | The internal note *"route to Tuesday crew, low priority"* is **absent** — assert the response body does not contain it. Only transitions and notes flagged `customer_visible` appear. Signed **out**, `SR-26-0056` + `(512) 555-4218` on `CWP-012` returns **progress and never data**. A **refused** request shows the refusal **and its reason** | BR-CWP-078 · BR-CWP-024 · BR-CWP-077 |
| 6 | `CWP-049` — *Two things still to send* | Table Document / **Why** / Status: *Photo ID · to confirm who you are · RECEIVED 2 SEP* (👁) · *Proof of address · a tenancy agreement or a deed · NEEDED* · *Landlord's consent · **you are not the owner** · NEEDED*. Then **a sentence saying documents come to the office** | ⚠ **No upload control and no upload route** — assert no `<input type=file>` in the DOM and that posting a file to any portal endpoint is refused. Consumer upload is a **signed deferral**, not an open question; the drawing's dashed drop zone is **not built** (layout entry). A request type needing no documents → the screen and its link are absent | `US-CWP-064` TC-3/4/5 · BR-CWP-056 |
| 7 | ⚠ **AMENDED 2026-09-19 — THERE IS NO WITHDRAW TO PRESS** (`OQ-CUS-12486`). It read: *negative · withdraw, then approval — Maria presses Withdraw on a second test request; Sarah approves `SR-26-0056`; Maria tries to withdraw it.* **negative · the closed door** — Maria has changed her mind; she finds no *Withdraw* anywhere on `CWP-051`, rings the utility, and Sarah refuses the request with reason *Applicant withdrew* | **No withdraw control renders on any request in any state.** `POST portal/requests/{reference}/withdraw` is still mounted and **refuses cleanly from every state** — `BIZ_STATE` / `customers.serviceRequest.transitionNotAllowed`, a readable sentence and never a 500 or a 404, because a bookmarked tab and a replayed post both still reach it. The clerk's refusal carries reason `applicant_withdrew`, one of the five the Refuse dialog draws, and **the account carries on as normal** — nothing touched | **THREE** transitions and no more: the customer never approved, refused, held, routed or completed anything, and no longer withdraws either. ⚠ Rows already `withdrawn` before the ruling keep that state and still display | BR-CWP-079 (SUPERSEDED) · BR-CWP-075 (AMENDED) |
| 8 | 17 Sep — the closing read `154,310` by a reader (`1,270 gal` since 1 Sep); the final bill issues; `CWP-032` — *Your final bill* | **SETTLING UP** `KVList` *Service to 17 September* **`$63.40`** / *Deposit held* **`−$150.00`** / *Interest on your deposit* **`−$3.20`** → `TotalRow` **We owe you `$89.80`**. `ConsequenceBox` **WHAT HAPPENS NEXT**: *A refund is raised for $89.80 · It goes to the address you gave us · Allow ten working days.* **CLOSING READING** *Water · front meter `154,310` · Taken 17 Sep, by a reader · Used since 1 Sep `1,270 gal`* · *Query this reading* | **The arithmetic:** `63.40 − 150.00 − 3.20 = −89.80`, presented as *we owe you `$89.80`*. The deposit and interest **match `CWP-065` exactly**. ⚠ **A refund row exists and no credit note does** — a negative final balance on a **closed** account is a refund, never a carried credit. Where service **exceeds** the deposit the screen reads an amount **owed** with a (held) Pay control — not *we owe you* with a minus sign. No deposit → the deposit lines are **absent**, not `$0.00` | BR-CWP-048 · BR-CWP-049 · hard rule 2 |
| 9 | **negative · the last cheap query** — *Query this reading* after settlement | The route is **gone** and the screen says a correction is slower now — once the final bill is settled the account closes and a correction becomes a much slower business, which is why the screen said so before the customer left | The final invoice is issued and **immutable**; the settlement is the **existing** move-out settlement shown to the person it belongs to | `US-CWP-037` TC-9 · hard rule 4 |
| 10 | `CWP-045` — *Money coming back to you* | **A REFUND ON ITS WAY** `ChecklistTimeline` × 4: *Raised · 18 Sep · $89.80 after your final bill* · *Approved · 19 Sep · by the office* · **Sent · 21 Sep** current · *Cleared · usually within ten working days*. **CREDITS ON THE ACCOUNT** `MiniTable`: *Goodwill — reading dispute · 12 Jul · $25.88 · used on BL-2607-0139* · *Overcharge corrected · 12 Jul · $25.88 · used on BL-2607-0139*. Footer: ***A credit comes off your next bill. A refund is money sent back.*** | `2 × 25.88 = 51.76` of credit already applied. **The refund figure equals `US-CWP-037`'s settlement, `$89.80`.** The credit figure is **re-read on every load** — a credit spent between two loads shows the new figure, assert no cache. A **voided** refund is shown as voided, **not removed**. **Release 3:** the *Sent* row names the cheque `#10241` and the address. **Release 5 boundary (`US-CWP-049`):** money that came in by card is returned *to the card ending 8812* — the timeline names the **method**, not a cheque number; an **expired** card (`••••4417`) falls back to a cheque **and the timeline says so**; money across two methods names the split or the rule that chose one — never a bare *sent* | BR-CWP-060 · BR-CWP-047 · `US-CWP-049` TC-1…4 |
| 11 | **the sibling distinction** — Maria's second property tries *Stop service for a while* (`CWP-052`): stop 1 Nov 2026, restart 1 Apr 2027 | `ConsequenceBox`: *your supply is turned off on 1 November · **the account stays open** · standing charges keep running — about `$18.50` a month.* Rail **WOULD MOVING OUT BE CHEAPER?**: five months × `$18.50` = **about `$92.50`**, against a `$185.00` connection fee plus a `$150.00` new deposit (`$335.00`) — **for this property, stopping is cheaper**. `Button(danger)` *Request this ✓* — the second danger-tier commit | The recommendation is **computed, never hardcoded**: the crossover is `335.00 ÷ 18.50 = 18.1` months, so **from 19 months closing wins** and the screen must then say so (⚠ `US-CWP-062` §4 notes that twelve months — `$222.00` — does **not** cross it). Assert the phrase *the account stays open* is present. A service with no standing charge says so rather than showing `$0.00` as a saving | BR-CWP-080 · BR-CWP-081 |
| 12 | **tenant isolation** | `SR-26-0056` with an Oak Ridge session → not found. The final bill, the refund and the credits for `1408 Elm St · A` are refused to an Oak Ridge session. Requests hub with a Pine Hill session shows Pine Hill categories and requests only | RLS `FORCE`; both halves in the query | BR-CWP-010 · hard rule 1 |
| 13 | **INVARIANCE** | The customer made exactly **three** kinds of transition (⚠ AMENDED 2026-09-19 — *withdraw* was the fourth and is retired, `OQ-CUS-12486`); the deposit figure was `$150.00` on `CWP-065`, `CWP-048` and `CWP-032`; the settlement was a **refund**, not a credit; the final invoice, the payment rows and the refund rows were never updated or deleted; every money action wrote an audit row naming Maria; the internal note never surfaced | The portal fixed nothing itself — every *fix this* became a precise request a member of staff acted on | BR-CWP-075 · hard rules 4 · 7 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | A customer **closing** the account without a clerk | `OQ-1392` — the request lands for a person; the self-serve path raises |
| b | The refund returned to the **card** | Rails — release 5 (`US-CWP-049`). Release 3 names the cheque and the address |
| c | A document uploaded by the customer | A **signed deferral** — uploads stay staff-mediated; the checklist is real and the box is not |

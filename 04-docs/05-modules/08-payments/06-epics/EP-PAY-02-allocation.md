# EP-PAY-02 — Allocation (how money meets bills · overpayment credit · Reapply)

**Module:** payments · **Wave:** W4 · **Screens:** S22, S33, S35 · **Status:** draft (BR-PAY-001..031 all CONFIRMED — session closed 2026-08-08; schema B2 Addendum r12)

## Scope
**In:** the allocation engine consuming BR-PAY-001/010 with the PE-2/3/4 worked scenarios (model §3): oldest-invoice-first, within an invoice usage+base → taxes → fees LAST, overpayment → account credit, tenant-reconfigurable order; the carried-credit lifecycle (auto-apply + refundable, BR-CUS-061 pattern); and the **Reapply** modal (BR-PAY-031 — reversing allocation rows + new rows, reason + audit, never edits). Allocation happens for every intake path (single US-PAY-001, bulk US-PAY-003, purpose credits US-PAY-002).
**Out:** intake forms (EP-PAY-01) · reversal of the PAYMENT itself (EP-PAY-03, BR-PAY-011) · refund execution (US-PAY-011) · billing's credit-preview tab (US-BIL-002 Credits — preview only, this engine executes) · ledger posting (posting service 🔒, W5).
**Tables (B2 + r12):** `allocations` (payment N:M invoice), `payments` (credit carry), tenant allocation-order setting (BR-BIL-021 config family "allocation order"). Invoices read-only via service fns (B1); balances update through the account-balance read-model, never hand-written.

## Capability matrix (list screens only — B9 conformance)
No list screens — the engine is a service; Reapply is an S35 modal (IS-6). Allocation visibility rides S33's "Applied to" column (US-PAY-004).

## Stories

---
id: US-PAY-006
epic: EP-PAY-02
module: payments
screens: [S22, S33]
wave: 4
status: draft
blocked_by: []
depends_on: [US-BIL-005, US-PAY-001, US-CUS-012]
journeys: [J2]
rules: [BR-PAY-001, BR-PAY-010, BR-PAY-021]
golden_tests: [GT-7]
finance_calc: confirmed
---
### US-PAY-006 — The allocation engine: oldest first; usage+base → taxes → fees last

**1 · Details** — As the payments service, I want every payment allocated per the ratified order (BR-PAY-010): **DEFAULT oldest-invoice-first; within an invoice usage+base → taxes → fees LAST; overpayment → account credit; tenant-reconfigurable** — honoring the staff instruction from the entry form (BR-PAY-001: oldest / specific bill / carry as credit / split), so that the J2 step-10 contract holds: *payment cleared, allocations rows per BR-PAY-010 order*. Allocation writes `allocations` rows (payment N:M invoice) at posting (posted_at is what billing consumes for on-time-ness, BR-PAY-021); a later NSF/reversal reverses allocations with reversing rows (EP-PAY-03) — allocation rows are never edited. The tenant allocation-order setting (BR-BIL-021 config family) reorders the within-invoice classes; nothing is hardcoded. Entry: called by US-PAY-001/002/003 and by bill issue for carried credits. Exit: allocations written, account balance read-model updated, audit.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-010 | Allocation order: DEFAULT oldest-invoice-first; within invoice usage+base → taxes → fees last; overpayment → account credit. Tenant-configurable. **⚠ AMENDED 2026-08-11 by BR-PAY-038 (OQ-109 closed) — the within-invoice order is FOUR classes, not three: usage+base → taxes → the TENANT-DEFINED class → fees LAST. Everything else in this rule stands.** **⚠ AMENDED 2026-08-12 (PO, OQ-189 dissolved) — the within-bill SEQUENCE is a TENANT SETTING; the four-class order above is the SHIPPED DEFAULT.** Verbatim: *"better to let user set the sequence; we can give default option and allow them to change the order"* — because a municipal utility, a submetering operator and an HOA are three businesses with three regulators. | CONFIRMED — PO Q&A R6 (OQ-010 closure) · class count amended by PO 2026-08-11 · **order = tenant setting, PO 2026-08-12** |
| BR-PAY-038 | **A FOURTH allocation class sits between taxes and fees; its MEMBERSHIP is tenant configuration in the ledger, never a hardcoded list of line kinds.** PO ruling 2026-08-11, verbatim: *"C Its own class between tax and fees - it can be service fees or it can be special fees anything; allow tenant user to define it in ledge[r]"*. Worked: usage+base $100.58 + tax $8.30 + tenant-defined service fee $15.00 + late fee $5.00 = $128.88; a $120.00 payment meets $100.58, then $8.30, then **$11.12** of the $15.00, and the late fee stays LAST at **$0.00**. ~~NOT settled: where in the ledger it is defined (OQ-123), whether more than one may exist and how they order (OQ-124), what happens to bills issued before one exists (OQ-119).~~ **⚠ ALL THREE CLOSED 2026-08-12 (PO): defined under Settings → Configure with the GL codes and the finance ledger (OQ-123, *"GL code or finance ledge in configure section, settings"*); ONE extra class only, so there is no second custom class to order against (OQ-124, *"One extra class only"*); bills issued before the class existed stay under the OLD split (OQ-119, *"Leave old bills under the old split"*, BR-BIL-004 immutability).** | CONFIRMED — PO 2026-08-11 (OQ-109) · **residual questions all CLOSED PO 2026-08-12** |
| BR-PAY-001 | Default allocation = oldest open bill; staff options: specific / carry credit / split. | CONFIRMED — A2 §Record payment |
| BR-PAY-021 | Allocation is evaluated off the POSTING date for billing (on-time); money-received facts hang off clearing. | CONFIRMED — PO explicit ruling, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | PE-2 partial: bill $247.87 (usage+base 221.90 · taxes 20.97 · late 5.00), pay $200.00 | Allocation covers usage+base only ($200.00 of 221.90); outstanding **$47.87** = 21.90 + 20.97 + 5.00; the next late-fee candidate computes on that overdue portion (WE-15c linkage) |
| TC-2 | PE-3 two bills: open Jun 142.30 + Jul 247.87, pay $300.00 | Jun paid in full (142.30); Jul receives **157.70**; Jul balance **90.17** — oldest-invoice-first |
| TC-3 | PE-4 overpayment: open 292.87, pay $350.00 | Bills settled; **credit 57.13** carries on the account (US-PAY-007 lifecycle) |
| TC-4 | Staff instruction Specific bill / Split ($100 to BL-2607-018311, rest oldest) | Engine honors the instruction (BR-PAY-001); split writes one allocation row per target; Σ rows = payment amount |
| TC-5 | Tenant reorders within-invoice classes (fees before taxes) | Engine follows the tenant setting (config, not constant); default order restored → default behavior returns |
| TC-5b *(PO 2026-08-12, OQ-189)* | The **four** classes are reordered by a tenant — taxes first — on the $128.88 bill (usage+base 100.58 · tax 8.30 · tenant-defined service fee 15.00 · late fee 5.00), payment $120.00 | Engine follows the SETTING: 8.30 tax, then 100.58 usage+base, then **11.12** of the service fee, late fee 0.00. On the **shipped default** (usage+base → taxes → tenant class → fees LAST) the same payment meets **100.58**, then **8.30**, then **11.12**, late fee **0.00** — the default's figure is unchanged by the setting existing |
| TC-5c *(PO 2026-08-12, OQ-124/OQ-119)* | A tenant attempts a SECOND custom class; a bill issued before any custom class existed is re-read | Second class refused — **one extra class only**; the older bill allocates under the **old three-class split**, never re-read under the new rule (issued bills immutable, BR-BIL-004) |
| TC-6 *(posting vs clearing)* | Payment posted Aug 22 (due date), cleared Aug 25, allocated to BL-2608-018410 | Allocations exist from posting; billing's on-time evaluation uses posted_at (no late fee); bank-rec facts use cleared_at (BR-PAY-021) |
| TC-7 *(negative)* | Forged allocation set where Σ allocation amounts > payment amount; allocation naming a void invoice | Rejected — engine invariant Σ allocations ≤ payment; void/draft invoices are not allocation targets |
| TC-8 *(isolation)* | Engine run for a Lone Star Ridge payment | Considers only Lone Star Ridge open invoices (RLS); Brazos Bend invoices can never receive its money |

**4 · Test Data** — ACC-1042: BL-2608-018410 $247.87 (usage+base 221.90 · taxes 20.97 · late 5.00, due Aug 22). PE-3 account ACC-1103: BL-2606-018091 Jun $142.30 (due Jun 22) + BL-2607-018205 Jul $247.87 (due Jul 22); payment $300.00 Aug 8. PE-4: ACC-1042 open 292.87, payment $350.00. Tenant allocation-order setting: seeded default (usage+base → taxes → fees). Actors: engine (service), Marcus Vega (instruction). Isolation: Lone Star Ridge payment $88.40.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Allocation row | S33 "Applied to" | model §3 + B2 DDL | `allocations` (payment_id, invoice_id, amount) | numeric(18,6) USD | system-derived | Σ per payment ≤ payment amount; append-only |
| Within-invoice class order | — | BR-PAY-010 · **BR-PAY-038** | line-class walk over `invoice_lines` (taxable/charge class read via service fn) | ordered classes | system-derived | usage+base → taxes → **the tenant-defined class** → fees last (default, PO 2026-08-11) |
| Tenant-defined class MEMBERSHIP | **Settings → Configure**, with the GL codes and the finance ledger (**OQ-123 CLOSED, PO 2026-08-12**) | BR-PAY-038 | **no column** — `apps.ledger.selectors.allocation_class_members` is NAMED and unpublished; `apps/payments/allocation.py` refuses (`AllocationClassNotConfigured`) while it stays that way | set of line kinds | reference-data (tenant) | **exactly ONE extra class** (OQ-124 CLOSED); **bills issued before it existed keep the old split** (OQ-119 CLOSED) |
| Tenant allocation order | **Settings → Configure** (S66 family) | BR-PAY-010 + BR-BIL-021 ("allocation order") | tenant billing settings allocation-order key (r10 #6 family) — **owed: the setting itself. `apps/payments/allocation.py` already takes `class_order` as an argument and its constant is `DEFAULT_CLASS_ORDER`; storage, screen and plumbing are what is missing (PO 2026-08-12, OQ-189)** | enum[] (4 classes) | reference-data | seeded default = usage+base → taxes → tenant class → fees LAST; tenant-reorderable |
| Staff instruction | S22/S35 | BR-PAY-001 | instruction passed from intake (oldest\|specific\|carry\|split) | enum(+targets) | user-input | specific/split ⇒ named invoices |
| Overpayment remainder | — | BR-PAY-010 | carried account credit (US-PAY-007) | numeric(18,6) | system-derived | never lost |
| Balance effect | S21/S34 | model §12 | account balance read-model (`accounts.balance` cache; ledger is truth) | numeric(18,6) | system-derived | ties to open invoices |
| Allocation audit | — | CLAUDE.md #7 | `audit_log` `payment.allocated` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given PE-2/3/4 inputs, Then allocations equal §7 to the cent, and the S33 "Applied to" column names every touched invoice.
- Given a staff instruction, Then it overrides the default exactly as chosen; given none, oldest-first applies.
- Given the tenant order setting changed, Then the within-invoice walk follows it — nothing hardcoded.
- Given a reversal later, Then allocation rows are only ever reversed by new rows (EP-PAY-03/US-PAY-008), never edited.

**7 · Finance Calculation** — CONFIRMED (BR-PAY-010; PE-2/3/4 model §3 verbatim).
- **PE-2 partial:** bill 247.87 (usage+base 221.90 · taxes 20.97 · late 5.00), pay 200 → covers usage+base only; outstanding **47.87** (21.90 + 20.97 + 5.00); next late fee computes on that overdue portion (WE-15c).
- **PE-3 two bills:** open Jun 142.30 + Jul 247.87; pay 300 → Jun paid in full, Jul gets **157.70**, Jul balance **90.17**.
- **PE-4 overpayment:** open 292.87, pay 350 → bills settled + **credit 57.13** carries.
- **Four-class default (PO 2026-08-11, order made a SETTING 2026-08-12):** bill **128.88** = usage+base **100.58** + tax **8.30** + tenant-defined service fee **15.00** + late fee **5.00**; payment **120.00** meets 100.58, then 8.30, then **11.12** of the service fee, late fee **0.00**. This is the SHIPPED DEFAULT's figure, not a constant.
GT ref: **GT-7**.

**8 · Open Questions** — **None open. Four closed 2026-08-12 (PO), recorded because this story is where they land:** **OQ-189** — the within-bill SEQUENCE is a **tenant setting**, *"better to let user set the sequence; we can give default option and allow them to change the order"*, because a municipal utility, a submetering operator and an HOA are three businesses with three regulators; the 2026-08-11 order ships as the DEFAULT with its 100.58 / 8.30 / 11.12 figure intact, and what is owed is storage + a Settings → Configure screen + the plumbing, not a change to the arithmetic. · **OQ-123** — the fourth class is defined under **Settings → Configure**, with the GL codes and the finance ledger (*"GL code or finance ledge in configure section, settings"*), not in payments. · **OQ-124** — *"One extra class only"*, so no ordering rule between custom classes is needed or invented. · **OQ-119** — *"Leave old bills under the old split"*: bills issued before the class existed are not re-read under it (BR-BIL-004).

---
id: US-PAY-007
epic: EP-PAY-02
module: payments
screens: [S33, S21]
wave: 4
status: draft
blocked_by: []
depends_on: [US-PAY-006, US-BIL-005]
journeys: [J2]
rules: [BR-PAY-010, BR-PAY-012]
golden_tests: []
finance_calc: confirmed
---
### US-PAY-007 — Overpayment / carried credit: auto-apply, visible, refundable

**1 · Details** — As a Billing Clerk, I want every unapplied amount — overpayment remainders (BR-PAY-010), prepay-purpose money (BR-PAY-012), and cutover opening credits (BR-CUS-061 pattern) — held as a **carried account credit** that: shows on the account header and S33 (type credit rows, "Applied … bill"), **auto-applies to the account's next issued bill** in allocation order, and is **refundable on request** (routes to US-PAY-011). Billing previews these in the run's Credits tab (US-BIL-002) — this story is the execution side. Credits are payment-type rows (B2 `payment_type` credit), append-only; application writes `allocations` rows at bill issue. Entry: created by US-PAY-006 remainders / US-PAY-002 prepay. Exit: credit consumed by future bills or refunded — never silently dropped.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-010 | Overpayment → account credit; auto-applies to the next bill; tenant order governs application. | CONFIRMED — PO Q&A R6 (OQ-010) |
| BR-PAY-012 | Prepay purpose and unapplied purpose-money sit as the same account credit. | CONFIRMED — PO PA-1, 2026-08-08 |
| BR-CUS-061 *(consumed)* | Opening CREDIT balances import as carried account credit — same lifecycle (auto-apply, refundable). | CONFIRMED — PO OQ-065 (b) (cited) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | PE-4 remainder 57.13 on ACC-1042 | Credit visible on account header + S33; run 08-A Credits tab (US-BIL-002) previews it |
| TC-2 | ACC-1042's September bill issues at $184.20 | Credit auto-applies 57.13 at issue (allocation rows); bill's amount-due presentation reflects it; remaining credit 0.00 |
| TC-3 | Credit larger than the next bill (credit 57.13, bill 42.10) | 42.10 applies; **15.03 remains carried** — never dropped; applies again next cycle |
| TC-4 | Customer requests payout | Refund flow (US-PAY-011) draws down the credit; credit and refund rows reference each other |
| TC-4b *(PO 2026-08-12, OQ-167)* | The credit is built from **TWO** overpayments — $40.00 in June + $17.13 in July — and the customer asks for the **$57.13** back | Refundable: the refund is raised against the **CREDIT BALANCE**, not against a single payment (`refunds.payment_id` names one payment and cannot express this). The clerk chooses **refund or credit** — *"it will be manula decision"* — and neither is automatic |
| TC-4c *(PO 2026-08-12, OQ-135)* | The same customer holds **$57.13** credit here and **$948.20** overdue (91 days) on another of their accounts | **No refund.** The arrear is offset FIRST (*"offset first"*); the refund is what remains. The offset is a balance transfer through the reviewed writer — `accounts.balance` is a cache, good enough to stop a payout, not to net one down (BR-CUS-015) |
| TC-5 *(negative)* | Attempt to apply the same credit twice (double issue retry) | Application is idempotent per bill issue (guard 🔒 Eng-Lead); credit never over-applies beyond its balance |
| TC-6 *(isolation)* | Lone Star Ridge credit | Applies only to Lone Star Ridge bills; a Brazos Bend issue can never consume it (RLS) |

**4 · Test Data** — ACC-1042 credit 57.13 (PE-4). Next bills: BL-2609-018602 $184.20 (TC-2 variant) / $42.10 (TC-3 variant). Opening-credit fixture: ACC-1930 imported credit $23.40 (BR-CUS-061, US-CUS-021 handoff). Actors: Marcus Vega, Sarah Miller (payout request). Isolation: Lone Star Ridge credit $12.00.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Carried credit position | S21 header / S33 | model §3 (PE-4) | read-model: Σ unallocated credit `payments` (type credit / overpay remainder) | numeric(18,6) USD | system-derived | ≥ 0; ties to rows |
| Credit row | S33 | prototype-extracted (Credit rows) | `payments` (type = credit, B2 `payment_type`) | numeric(18,6) | system-derived | append-only |
| Auto-application | — | BR-PAY-010 | `allocations` rows written at bill issue (engine call from billing issue path, B1) | numeric(18,6) | system-derived | ≤ credit balance; idempotent per issue 🔒 |
| Credits preview (run) | S31.2 | US-BIL-002 §5 (consumed) | same read-model, billing-side display | numeric(18,6) | computed-display | preview only — this story executes |
| Refund linkage | S58 | BR-PAY-014 | `refunds.payment_id` → the credit row (B2) — ⚠ **the single-payment shape is the OQ-167 blocker: a credit built from TWO overpayments ($40.00 + $17.13 = $57.13) cannot be named by one `payment_id`, so a refund must be raisable against the CREDIT BALANCE (PO 2026-08-12)** | uuid | system-derived | only from real credit (US-PAY-011); **offset against the customer's other accounts FIRST (PO 2026-08-12, OQ-135 → BR-CUS-054)** |
| Audit | — | CLAUDE.md #7 | `audit_log` `credit.applied` / `credit.carried` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a remainder or prepay, Then the credit is visible, auto-applies at the next issue, and any leftover carries again — demoable across two issues.
- Given a payout request, Then the refund flow consumes the credit with full linkage.
- Given retries, Then the credit never over-applies; given tenants, credits never cross.

**7 · Finance Calculation** — CONFIRMED (PE-4 verbatim: open 292.87, pay 350 → **credit 57.13** carries, auto-applies to the next bill, refundable on request — BR-CUS-061 pattern). TC-3 carry split (42.10 applied / 15.03 carried) follows the same rule; Σ applications ≤ 57.13 always. **Multi-source credit (PO 2026-08-12, OQ-167):** the same **57.13** reached by **40.00 (June) + 17.13 (July)** is the same refundable credit — the figure does not change, only the number of payments behind it does.

**8 · Open Questions** — **None open. Two closed 2026-08-12 (PO):** **OQ-167** — *"user can do a refund or issue a credit - it will be manula decision, provide a mecahnism to complete the tasks"*: a credit built from two overpayments (**$40.00 + $17.13 = $57.13**) MUST be refundable, so a refund is raised against the **credit balance** rather than against one payment; the clerk chooses, and the product offers both and decides neither. · **OQ-135** — *"offset first"*: a customer owing on ANOTHER of their accounts (**$57.13** credit vs **$948.20** overdue) is offset before any refund; the refund is what remains, and the offset is a balance transfer, not a subtraction from the `accounts.balance` cache.

**9 · Build state (2026-08-15, payments visible-half lane)** — **CREDIT IS VISIBLE AND EXPLAINABLE; IT DOES NOT AUTO-APPLY BY ITSELF.** `apps/payments/credit.py` serves the signed position with the payments behind it, and `apply_credit_at_issue` writes the allocation rows (57.13 against 184.20 → 0.00 left; 57.13 against 42.10 → 15.03 carried). ⚠ **NOTHING CALLS IT** — the caller is `apps/billing/issue.py` and belongs to another lane; every result carries `credit_auto_application_has_no_caller`. ⚠ **TC-4b IS BLOCKED BY THE SCHEMA, NOT WORKED AROUND:** `refund_from_credit_balance` raises `NotImplementedError("OQ-195")` — `refunds.payment_id uuid NOT NULL` cannot name a credit built from two overpayments, and changing a signed B2 column is a contracts-lane act. The single-source PE-9 path is untouched and the offset-first test (OQ-135) still runs before any payout.

---
id: US-PAY-008
epic: EP-PAY-02
module: payments
screens: [S35, S33]
wave: 4
status: draft
blocked_by: []
depends_on: [US-PAY-006]
journeys: [J2]
rules: [BR-PAY-031, BR-PAY-002, BR-PAY-030]
golden_tests: []
finance_calc: confirmed
---
### US-PAY-008 — Reapply: reversing allocation rows + new rows, reason + audit — never edits

**1 · Details** — As a Billing Clerk, I want to move a payment's application between bills via the S35 Reapply modal (row or bulk from S33): choose the new target (**Oldest open bill per account / Newest bill per account / A specific bill / Carry forward as credit** — prototype options), choose the larger-than-bill behavior (**carry remainder as credit / refund remainder** — refund routes to US-PAY-011), and give a reason (required, "Note for the audit trail") — executed as **reversing allocation rows + new allocation rows** (BR-PAY-031): the original rows are never edited or deleted. The payment row itself is untouched (BR-PAY-002 — reapply moves application, not money). A consequence line states the balance effect per bill before confirm (BR-PAY-030 family). Entry: S33 row action / bulk "Reapply to bill". Exit: allocations re-pointed; both bills' balances move; audit `payment.reapplied` with reason.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-031 | Reapply = reversing allocation rows + new rows, reason + audit; never edits. | CONFIRMED — PO Lane B-10, 2026-08-08 |
| BR-PAY-002 | The payment row is append-only and untouched by reapply — only its application moves. | CONFIRMED — B2 §payments |
| BR-PAY-030 | Plain-language consequence shown before confirm (which bill goes up, which goes down). | CONFIRMED — PO Lane B-9, 2026-08-08 (family rule, applied to reapply UI) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Move Park's $100.00 (check #4021) from BL-2606-018091 to specific BL-2607-018206, reason "customer directed" | Reversing allocation row −100.00 (BL-2606-018091) + new row +100.00 (BL-2607-018206); Jun bill re-opens by 100.00, Jul bill closes by 100.00; consequence message shown first; audit `payment.reapplied` (actor, reason, both bills) |
| TC-2 | Reapply target = Carry forward as credit | Reversing rows only + credit carried (US-PAY-007); no new invoice allocation |
| TC-3 | Payment larger than the new target bill; behavior = carry remainder | New rows: bill amount to the bill, remainder to credit; behavior = refund remainder routes the remainder to US-PAY-011 |
| TC-4 | Bulk reapply 3 selected payments ($988.70) | Per-payment reversing+new row pairs; one reason captured for the set; per-row results listed |
| TC-5 *(negative)* | Confirm without a reason; or an API attempt to UPDATE an existing allocation row | Blocked — reason required (BR-PAY-031); allocation rows append-only, UPDATE rejected |
| TC-6 *(negative)* | Reapply targeting a draft or void invoice | Rejected — only open issued invoices (or credit carry) are valid targets |
| TC-7 *(isolation)* | Reapply naming a Lone Star Ridge invoice from a Brazos Bend session | 404/reject (RLS); no rows written |

**4 · Test Data** — A-11455 Park, Jenna: check #4021 $100.00 currently on BL-2606-018091; targets BL-2607-018206. Bulk fixture: prototype selection 3 payments $988.70. Reasons: "customer directed", "keyed to wrong bill". Actors: Priya Menon. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Reapply target | S35 Reapply | prototype-extracted (4 options) | new `allocations` rows | enum(+bill ref) | user-input | open issued invoices or credit carry |
| Remainder behavior | S35 Reapply | prototype-extracted (carry/refund) | credit carry (US-PAY-007) or refund route (US-PAY-011) | enum | user-input | refund needs credit-flow approval chain |
| Reason / note | S35 Reapply | prototype-extracted ("Note for the audit trail") + BR-PAY-031 | audit payload (+ case reason on the reapply event) | text | user-input | required |
| Reversing allocation rows | — | BR-PAY-031 | `allocations` negative/reversing rows referencing the originals | numeric(18,6) | system-derived | append-only; Σ net per payment ≤ payment amount |
| Consequence message | S35 | BR-PAY-030 | rendered from computed per-bill balance deltas | text | computed-display | always before confirm |
| Audit | — | CLAUDE.md #7 | `audit_log` `payment.reapplied` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a reapply, Then the original allocation rows survive untouched, reversing + new rows express the move, and both bills' balances change accordingly.
- Given the modal, Then a reason is mandatory and the consequence message precedes confirm.
- Given remainders, Then carry/refund behaves per the chosen option; given tenants, targets never cross.

**7 · Finance Calculation** — CONFIRMED (BR-PAY-031 mechanics; amounts conserved). Worked (TC-1): payment 100.00 — reversing row −100.00 on BL-2606-018091, new row +100.00 on BL-2607-018206; net application per payment unchanged at 100.00; per-bill balances move ±100.00. No rounding events (whole reapplication of existing 2dp amounts).

**8 · Open Questions** — None.

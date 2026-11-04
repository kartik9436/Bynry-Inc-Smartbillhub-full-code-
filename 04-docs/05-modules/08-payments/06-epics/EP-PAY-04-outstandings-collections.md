# EP-PAY-04 — Outstandings & collections (S34 · sequence engine · notices · returned mail)

**Module:** payments · **Wave:** W4 · **Screens:** S32, S34, S35, S30 · **Status:** draft (BR-PAY-001..031 all CONFIRMED — session closed 2026-08-08; schema B2 Addendum r12)

## Scope
**In:** the S34 Outstandings list per BR-PAY-029 (AR high→low, aging KPIs, bulk actions), the **collection sequence engine** per BR-PAY-017 (tenant-config ladder due+3 reminder → late fee → 10-day → 5-day → 48h certified final; paper v1; medical-hold excluded; email + SMS text-to-pay ride the outbound queue WHEN their channels land — every notice is a QUEUE-WRITE per BR-NOT-005, never an inline send), the S35 manual **Reminder / Disconnect-notice** bulk modals with `notice_history` (J4 step 2 contract), and the **returned-mail bad-address flow** per BR-PAY-018 (PE-16). Collection state per account + notice_history are r12 #7; bad-address flag + delivery-return events are r12 #8.
**Out:** late-fee computation/application (billing, BR-BIL-001/008 — the ladder cites it, billing executes) · disconnect scheduling/field ops (S22 disconnect notice content = BR-CUS-039/US-CUS-015; field-visit modal has no ratified rule — pack report) · payment plans (EP-PAY-05 — S34 "Payment plan" bulk action opens that wizard) · write-off execution (US-PAY-012) · dispatcher mechanics (BR-NOT-005, notifications-owned; Eng-Lead 🔒 r12 #17) · text-to-pay page (rails W7).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S34 · Outstandings tab | account #, customer | age band (1–30/31–60/61–90/90+), class (residential/commercial/industrial), payment-plan state, autopay state, collection tier, bad-address | balance desc (BR-PAY-029) | balance, days late, last payment, account | # · Account · Customer · Days late · Age · Balance · Last payment · Notice history · Autopay · Payment plan / +Collection tier, Next step due, Bad-address, Medical hold (IS-5) | per-row action select per A2 §S34 (Send reminder … Write off; "Retry autopay" superseded by BR-PAY-015) | Send reminder · Disconnect notice · Payment plan · Write off (Field visit = no BR, pack report) | CSV (IS-9) |

## Stories

---
id: US-PAY-013
epic: EP-PAY-04
module: payments
screens: [S34, S32]
wave: 4
status: draft
blocked_by: []
depends_on: [US-BIL-005, US-PAY-006, US-SHL-006]
journeys: [J4]
rules: [BR-PAY-029, BR-PAY-015, BR-PAY-018]
golden_tests: []
finance_calc: none
---
### US-PAY-013 — S34 Outstandings: AR high→low, aging KPIs, bulk actions

**1 · Details** — As a Billing Clerk, I want S34 to list every account owing money, **sorted balance high→low** (BR-PAY-029), with the aging KPI strip (Current 1–30 / 31–60 / 61–90 / 90+ buckets, per-bucket $ + account counts + %), search + filters, columns per A2 §S34 (Days late · Age · Balance · Last payment · Notice history · Autopay · Payment plan), and the bulk toolbar (**Send reminder · Disconnect notice · Payment plan · Write off** — each routing to its owning story: US-PAY-015/015/017/012). Days-late anchors on the oldest unpaid invoice's **due date** (the BR-PAY-017 ladder is due-date-anchored; A2 marks the base UNKNOWN — anchoring recorded in the pack report for confirmation, not silently decided); age buckets derive from days late (A2). On-time-ness respects BR-PAY-021: a payment POSTED by due date removes the row even if not yet cleared. The A2 "Retry autopay" row action is superseded by BR-PAY-015 (capture-only — no charging v1). Per-row action sets vary by row state per A2. DSO KPI excluded pending a formula (GAP — pack report P-1).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-029 | S34 Outstandings: AR high→low, bulk actions (reminder/notice/plan/write-off). | CONFIRMED — PO Lane B-8, 2026-08-08 |
| BR-PAY-021 *(consumed)* | Outstanding evaluation uses the posting date — posted-by-due-date money is not outstanding. | CONFIRMED — PO explicit ruling, 2026-08-08 |
| BR-PAY-015 *(consumed)* | No autopay retry/charge action exists v1; the Autopay column shows enrollment/intent state only. | CONFIRMED — PO PA-4, 2026-08-08 |
| BR-PAY-018 *(consumed)* | Bad-address flag surfaces as a filter/column (needs-attention linkage, US-PAY-016). | CONFIRMED — PO PA-7, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Default load (prototype fixture set) | Rows sorted balance desc: A-11340 $8,240.00 first, then A-11024 $1,842.10, A-10802 $948.20 …; KPI strip bucket totals tie to the rows exactly; header "184 accounts owe $184,320" ties to Σ |
| TC-2 | Age-band filter 90+; class filter Commercial | Only matching rows (A-10802 in 90+); counts re-tie; filters combine |
| TC-3 *(posting vs clearing)* | ACC-1042 pays by check POSTED Aug 22 (due date), clearing Aug 25; list refreshed Aug 23 | Row gone — posted_at ≤ due date makes it not outstanding (BR-PAY-021), even though money hasn't cleared |
| TC-4 | Bulk select 4 rows → each bulk action | Toolbar shows "4 selected · $11,642.90 owed" (prototype copy); Reminder → US-PAY-015, Notice → US-PAY-015, Payment plan → US-PAY-017 wizard, Write off → US-PAY-012; list itself writes nothing |
| TC-5 | Columns: add Collection tier + Bad-address | Tier from collection state (r12 #7); bad-address flag rows badged (r12 #8); IS-5 preference persists |
| TC-6 *(negative)* | API attempt to mutate a row via the list endpoint | 405 — read-model only; actions route to owning flows |
| TC-7 *(isolation)* | J. Okafor loads S34 | Lone Star Ridge rows only (RLS); Brazos Bend account ids 404 |

**4 · Test Data** — Prototype S34 rows verbatim: A-11340 Northwind $8,240.00 (45d, 31–60, "1st + 2nd sent") · A-11024 Ridge Coffee $1,842.10 (30d, "Reminder sent") · A-10802 Novak $948.20 (91d, 90+, "Final sent Aug 1") · A-11020 Main St. $820.40 (62d) · A-11455 Park $542.10 (62d, "1st sent Jul 20") · A-11025 Blueprint $328.60 (15d, autopay Failed). KPI strip: $118,240/$34,120/$18,540/$13,420. Posted-not-cleared fixture: ACC-1042 (US-PAY-001 TC-2). Actors: Priya Menon. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Row (rank, account, customer, balance) | S34 | A2 §S34 | read-model over `accounts` balance > 0 (partial index ix_ar_outstanding) + open `invoices` | rows | computed-display | balance desc default (BR-PAY-029) |
| Days late | S34 | A2 §S34 (base UNKNOWN) | computed: today − oldest unpaid invoice `due_date` (due-anchor per BR-PAY-017; pack-report confirm P-2) | int days | computed-display | posted-by-due money excluded (BR-PAY-021) |
| Age bucket | S34 | A2 §S34 (derived from days_late) | computed enum 1–30\|31–60\|61–90\|90+ | enum | computed-display | ties to KPI strip |
| Aging KPI strip | S34 | prototype-extracted (5 tiles) | computed per bucket ($, accounts, %) — DSO tile excluded (GAP P-1) | $/counts | computed-display | ties to rows |
| Last payment | S34 | A2 §S34 | max `payments.posted_at` per account | date | computed-display | — |
| Notice history column | S34 | A2 §S34 | summary over `notice_history` (r12 #7) | text | computed-display | e.g. "1st + 2nd sent" |
| Autopay column | S34 | A2 §S34 (set UNKNOWN) + BR-PAY-015 | enrollment (customers read) + intent state (r12 #6); no retry action | enum | computed-display | display-only v1 |
| Payment plan column | S34 | A2 §S34 | `payment_plans.status` per account | enum | computed-display | None\|Active (+ full A5 set) |
| Collection tier / Next step due | S34 | BR-PAY-017 | collection state per account (r12 #7) | enum/date | computed-display | IS-5 extras |
| Bad-address badge/filter | S34 | BR-PAY-018 | `accounts.bad_address` (r12 #8) | boolean | computed-display | links US-PAY-016 |
| Bulk toolbar | S34 | prototype-extracted + IS-6 | routes to US-PAY-015/017/012 | — | user-input | count + $ shown |
| CSV export | S34 | IS-9 | computed file | file | computed-display | filters + visible columns |

**6 · Acceptance**
- Given the fixture set, Then ordering, buckets, KPI ties and column values render exactly, and every bulk action routes to its owning flow — the list writes nothing.
- Given a payment posted by due date, Then the row leaves the list regardless of clearing (BR-PAY-021).
- Given v1, Then no autopay-charging action exists anywhere on S34.
- Given tenants, Then rows and exports never cross.

**7 · Finance Calculation** — N/A (read-model; bucket sums are display ties, late-fee math is billing's BR-BIL-001).

**8 · Open Questions** — None.

**9 · Build state (2026-08-15, payments visible-half lane)** — **BACKEND COMPLETE, FRONTEND NOT STARTED.** `apps/payments/outstandings.py` serves the whole read-model — rows balance-desc, days-late on BR-PAY-032's anchor, the four ageing bands plus `current`, last payment, notice summary, collection tier, plan status, autopay and bad-address — and `GET /api/{tenant}/outstandings?as_of=YYYY-MM-DD` returns it with its `problems`. ⚠ **THE S34 TAB IS STILL THE PLACEHOLDER PANEL.** `07-frontend/src/features/payments/PaymentsPage.tsx` renders the *awaiting* panel for the Outstandings tab and does not call this endpoint, so **no human can see any of it** (hard-won law 2). Also owed: the CSV export (`POST /exports` registers no `outstandings` resource, BR-SHL-010) and the bulk toolbar's four routes.

---
id: US-PAY-014
epic: EP-PAY-04
module: payments
screens: [S34, S32]
wave: 4
status: draft
blocked_by: []
depends_on: [US-PAY-013, US-BIL-023, US-CUS-015]
journeys: [J4]
rules: [BR-PAY-017, BR-NOT-005, BR-PAY-021]
golden_tests: []
finance_calc: none
---
### US-PAY-014 — The collection sequence engine: due+3 → late fee → 10-day → 5-day → 48h certified final

**1 · Details** — As the payments service, I want the tenant-config collection ladder (BR-PAY-017, PE-15) evaluated per account: **due+3 friendly reminder → late fee (billing applies per BR-BIL-001/008 — the ladder only cites the step) → tier-1 10-day notice → tier-2 5-day notice → 48-hour certified FINAL** — with: **paper v1** (certified mail REQUIRED on final per A19 rule 3 / BR-CUS-039); **medical-hold accounts excluded** (A15); email + **SMS text-to-pay** rows written to the outbound queue from day one but dispatched only WHEN their channels land (email W6, SMS Twilio seam — deferral markers per the US-BIL-023 pattern); every step a **queue-write** (BR-NOT-005 — never inline), every send/skip appended to `notice_history` (J4 step-2 contract), and the account's **collection state** (tier, last/next notice dates, r12 #7) advanced. A payment POSTED by due date (BR-PAY-021) or an ACTIVE payment plan (BR-CUS-043, US-PAY-019) stops/pauses the ladder. Every interval and tier is a tenant setting seeded with the BR-PAY-017 defaults — nothing hardcoded. **⚠ THREE 2026-08-12 PO RULINGS CHANGE WHEN THIS LADDER STOPS AND WHERE IT RESUMES.** **(1) A BOUNCE RESTARTS IT AT RUNG 1 (OQ-133, *"Restart from the beginning"*):** a **$1,842.10** bill due **6 Jul** paid by cheque posted **5 Jul** stopped the chase; the cheque bounces three weeks later and the customer gets **the full ladder again, first notice onward** — not the step it had reached — **because the payment that stopped it never existed**. **(2) A PARTIAL PAYMENT PAUSES IT ONLY ABOVE A CONFIGURED PERCENTAGE OF THE OUTSTANDING BALANCE (OQ-136):** an account owing **$948** that pays **$150** has paid **15.8%**, under either threshold the PO named, **so the ladder continues** — at 25% it would need **$237.00**, at 50% **$474.00**. The percentage is a **TENANT SETTING**, not a platform constant, placed (Eng decision, delegated) in **Settings → Configure beside the collections/dunning settings**. **(3) A MISSED INSTALMENT LIFTS THE PLAN PAUSE IMMEDIATELY (OQ-170, *"Immediate"*):** PE-13's **$36.22** unpaid on 1 Oct resumes chasing on **2 Oct**, no grace, with the plan still `active` — there is no void and nobody is dropped. **And the whole ladder — not just the late fee — is subject to the $25.00 floor (PO 2026-08-12, OQ-137 ladder half → BR-BIL-001):** an account leaving **$2.40** unpaid gets no late fee and **no certified letter either**, because the letter costs **$8.00** and chasing $2.40 spends more than it recovers. Entry: scheduled evaluation + manual sends (US-PAY-015) which advance the same state. Exit: queue rows + notice_history + state.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-017 | Collection sequence (tenant-config): due+3 reminder → late fee → 10-day → 5-day → 48h certified final (paper v1, medical-hold excluded); email + SMS text-to-pay ride the delivery queue WHEN their channels land (email W6, SMS Twilio seam). | CONFIRMED — PO PA-6, 2026-08-08 (recorded per PM recommendation, PO wrote "pa-5" twice — flagged for veto in the rules file) |
| BR-NOT-005 | Every notice row is WRITTEN to the platform outbound table first; only the dispatcher sends, in tenant-config batches; statuses queued→sent→delivered/failed/bounced, retry ×3. | CONFIRMED — PO volume ruling, 2026-08-08 (r12 #16) |
| BR-PAY-021 | Ladder evaluation uses the posting date — money posted by due date stops the sequence even if uncleared. | CONFIRMED — PO explicit ruling, 2026-08-08 |
| BR-CUS-039 *(consumed)* | Final-tier content/certified-mail requirements + medical-hold exclusion per A19 §2/A15. | CONFIRMED — customers pack (cited) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | PE-15 ladder on A-11024 (due Jul 6, unpaid) | Due+3 (Jul 9): reminder queue row (paper) + notice_history "Reminder sent"; grace end: late-fee step CITED to billing (BR-BIL-001 applies it); +tier intervals: 10-day notice → 5-day → 48h certified final; collection state tier advances each step; next-step date always visible |
| TC-2 | Channel rows | Each step writes paper rows dispatchable v1 + email/SMS rows with the deferred-channel marker (no ESP/Twilio call before their rails); SMS body carries the text-to-pay token for W7 activation; all rows in `outbound_messages` (BR-NOT-005) |
| TC-3 | Medical hold on A-11020 | Account EXCLUDED from every ladder step (A15); exclusion appended to notice_history as a skip with reason; surfaced, never silent |
| TC-4 *(posting vs clearing)* | A-11024 pays: posted Jul 5 (≤ due Jul 6), clears Jul 8 | Ladder never starts — BR-PAY-021 posting-date evaluation; variant: posted Jul 20 → ladder stops at the current tier, no further steps |
| TC-5 | Active payment plan (US-PAY-019) | Ladder paused while plan active + current; ~~on plan void, dunning resumes (BR-PAY-016 linkage)~~ ⚠ **AMENDED — there is no void (PO 2026-08-11): dunning resumes the day AFTER a missed instalment, immediately and with no grace (PO 2026-08-12, OQ-170 — PE-13's $36.22 unpaid 1 Oct → chasing 2 Oct), while the plan stays `active`** |
| TC-5b *(PO 2026-08-12, OQ-133)* | The **$1,842.10** bill due 6 Jul was paid by cheque posted 5 Jul (ladder stopped); the cheque bounces three weeks later | The ladder **restarts at rung 1** — due+3 reminder onward — not at the tier it had reached; collection state resets to the first rung and every subsequent step follows the tenant intervals from there |
| TC-5c *(PO 2026-08-12, OQ-136)* | An account owing **$948** pays **$150** the day before its disconnection notice | **15.8% — below the tenant threshold, so the ladder CONTINUES** and the notice goes out. At a 25% threshold the payment would need to be **$237.00**; at 50%, **$474.00**. With the threshold set to 15% the same $150 pauses it — the behaviour follows the setting |
| TC-5d *(PO 2026-08-12, OQ-137 ladder half)* | An account leaves **$2.40** unpaid | **No ladder step at all** — the **$25.00** floor applies to the WHOLE ladder, not only the late fee; a certified letter costs **$8.00** and chasing $2.40 spends more than it recovers. Skip recorded with its reason, never silent |
| TC-6 | Tenant edits intervals (due+5 reminder; 12-day tier-1) | Next evaluation honors the new settings — config, not constant |
| TC-7 *(negative)* | A code path attempts to send a collection email inline at evaluation time | Forbidden — queue-write is the only path (BR-NOT-005) |
| TC-8 *(isolation)* | Lone Star Ridge ladder | Its settings, queue rows, notice_history only (RLS) |

**4 · Test Data** — A-11024 Ridge Coffee: BL-2607-018206 due Jul 6, 2026, unpaid; tenant ladder seeded per BR-PAY-017 (reminder due+3; tiers 10-day/5-day/48h); grace 5 calendar (BR-BIL-008). Medical hold: A-11020 (A15 flag). Plan fixture: ACC-1310 active plan. Settings-change fixture: reminder due+5. Actors: system job; Priya Menon (review). Isolation: Lone Star Ridge ladder (reminder due+3).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Ladder settings | S66 | BR-PAY-017 | tenant collection settings (intervals per tier; r12 #7 family, keys 🔒 #17) | ints/enums | reference-data | seeded BR-PAY-017 defaults |
| Collection state (tier, last/next dates) | S34 columns | BR-PAY-017 | collection state per account (r12 #7) | enum/dates | system-derived | advances per step; resets on settle |
| Notice queue rows | — | BR-NOT-005 | `outbound_messages` (r12 #16): account, template (tier), channel, status queued | rows | system-derived | one per account × channel per step; queue-only |
| Channel deferral markers | — | BR-PAY-017 (email W6, SMS Twilio seam) | channel-config flags (US-BIL-023 pattern) | flag | reference-data | rows written, not dispatched before rails |
| Certified-final flag | — | BR-CUS-039/A19 rule 3 | certified-mail marker on the final-tier row | boolean | system-derived | required on final; SMS never stands alone |
| Medical-hold exclusion | S34/S35 | A15 (via BR-CUS-039) | account medical-hold read (customers-owned) → skip + history entry | boolean | reference-data | excluded every step |
| notice_history append | S34 column / S21 | BR-PAY-017 + J4 step 2 | `notice_history` append-only (r12 #7) | rows | system-derived | every send AND skip |
| Late-fee step | — | BR-PAY-017 (cites) | billing late-fee flow (BR-BIL-001/008) — no payments write | — | system-derived | billing owns the fee |
| Stop conditions | — | BR-PAY-021 + BR-CUS-043 · **PO 2026-08-12 (OQ-136, OQ-170, OQ-137)** | posted-by-due payment / active-current plan / **partial payment ≥ the tenant threshold %** / **balance below the $25.00 floor** | — | system-derived | evaluated before each step; **a partial payment below the threshold stops nothing** ($150 of $948 = 15.8%); **a missed instalment un-pauses the plan the next day, no grace** |
| Partial-payment pause threshold | **Settings → Configure** (beside collections/dunning; Eng placement, delegated by the PO) | **BR-PAY-016 / BR-PAY-017 as amended (PO 2026-08-12, OQ-136)** | tenant collections setting: minimum % of outstanding a partial payment must meet to pause the ladder | percent | reference-data | tenant-set, **never a platform constant**; the PO named 25% and 50% as examples, not as the value |
| Ladder restart on bounce | S34 columns | **PO 2026-08-12 (OQ-133)** · BR-PAY-016 · BR-PAY-041 | collection state resets to **rung 1** when the payment that stopped the ladder is reversed | enum/int | system-derived | *"Restart from the beginning"*; applies to the bounced-cheque path (BR-PAY-013 NSF) |
| Audit | — | CLAUDE.md #7 | `audit_log` `collection.step` (account, tier, channels) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given an unpaid due date, Then the ladder advances exactly per the tenant settings, writing queue rows + notice_history at every step and never sending inline.
- Given medical hold, plan-active, posted-by-due payment, **a partial payment at or above the tenant threshold**, or **a balance under the $25.00 floor**, Then the account is excluded/paused/stopped with the fact recorded — never silent.
- Given a **bounced** payment that had stopped the ladder, Then the ladder restarts at **rung 1**; given a **missed instalment**, Then the plan pause lifts **the next day**.
- Given v1 channels, Then paper dispatches, email/SMS rows persist deferred, and the final tier always carries the certified-mail marker.
- Given tenants, Then settings and state never cross.

**7 · Finance Calculation** — N/A (the ladder moves documents and state; the only money step — the late fee — is billing's, computed per BR-BIL-001: max(5.00, 0.015 × overdue portion), cited not restated). Ref: PE-15. **Figures cited, not recomputed, for the 2026-08-12 edges:** bounce restart **$1,842.10**; threshold **$150 / $948 = 15.8%** (25% → **$237.00**, 50% → **$474.00**); floor **$2.40** unpaid vs an **$8.00** certified letter under the **$25.00** ladder floor.

**9b · Build state (2026-08-16, payments SURFACE lane) — THE BOARD, AND A CORRECTION TO 9 ABOVE.**

⚠ **§9's first owed item is NO LONGER TRUE and is corrected here rather than left to rot (hard-won law 1).** It says `apps.tenancy.settings_families.COLLECTIONS` *"stores neither `ladder_balance_floor_amount` (OQ-137/OQ-157) nor `partial_payment_pause_percent` (OQ-136), so `settings_seam` REFUSES and both figures must be passed in"*. **The DEF-097 lane added both `Param`s on 2026-08-15** — seeded **25** (the PO's ruled $25.00 floor) and **25%** (the lower of the two figures the PO named) — and this sentence was never re-read. `apps/payments/ladder.py`'s `LADDER_UNAVAILABLE` docstring carries the same stale claim and is REPORTED; rewriting it is not this lane's act. The other two owed items — **no nightly caller** and **the late-fee rung is billing's** — are unchanged and still owed.

**WHAT SHIPPED: A BOARD THAT PREVIEWS THE LADDER AND STEPS NOTHING** (`/payments/collections`, a fourth tab on the Payments page). `POST /collections/run` has existed since the ladder landed and it SENDS — it writes the notice, advances the tier and records a `notice_history` row on every path, skips included — so **there was no way to look first.** A clerk drove a five-stop-condition engine over a selection they could not inspect, and every one of those stop conditions is a customer nobody contacted.

`GET /collections/ladder` calls the PURE `ladder.decide` with the same inputs `run_ladder` gathers, so the preview and the run agree by construction. A backend test asserts that opening the board leaves `account_collection_state` untouched — the guarantee that makes the screen safe to open at all.

**§3 test cases added:**

| TC | Scenario | Expected |
|---|---|---|
| TC-8 *(US-PAY-015 TC-4's other half)* | An account whose reminder went on 30 Jul | The board shows the rung AND *"sent 2026-07-30"*, which is the fact that stops a manual send doubling a tier — until this read existed it lived in a table no surface could open |
| TC-9 *(the honest absence)* | A tenant whose collections settings cannot be read | `next_step_available: false`; every account, balance and tier-already-sent still renders; the NEXT step is null and the screen says *"Cannot say yet"*. **Never a plausible rung** — a rung drawn from a guessed floor posts letters |
| TC-10 *(the preview guarantee)* | Opening the board | No notice queued, no tier advanced, no `notice_history` row — asserted server-side, because a screen that called `run_ladder` to find out what would happen would have made it happen |

**9 · Build state (2026-08-15, payments visible-half lane)** — **ENGINE BUILT, TWO SETTINGS AND THE NIGHTLY CALLER OWED.** `apps/payments/ladder.py` implements the rungs, all five stop conditions and the bounce restart, and `POST /api/{tenant}/collections/run` drives it over an S34 selection. **THREE THINGS ARE NOT WIRED and each is named on the engine's own results:** (1) `apps.tenancy.settings_families.COLLECTIONS` stores neither `ladder_balance_floor_amount` (OQ-137/OQ-157) nor `partial_payment_pause_percent` (OQ-136), so `settings_seam` REFUSES and both figures must be passed in — the two `Param(...)` lines are owed by tenancy; (2) BE-07's job runner registers no collections job, so nothing evaluates the ladder nightly (`no_scheduled_caller`); (3) the late-fee rung applies no fee — BR-BIL-001/008 own it (`late_fee_step_is_billings`). ⚠ **The gap between the reminder and the first disconnect notice is a DERIVATION, not ratified law** — see `rung_due_on`'s docstring and the 2026-08-15 decision-log row.

**8 · Open Questions** — **None open. Four closed 2026-08-12 (PO), all of which change this ladder:** **OQ-133** *"Restart from the beginning"* — after a bounce the ladder restarts at rung 1. · **OQ-136** *"partial payment is okay it should be aleast 25% or 50% of outstanding; you ahve to allow user to set this limit in configuration or setting section, decide the place"* — a TENANT SETTING; placement delegated to Eng and decided: **Settings → Configure**, beside the collections/dunning settings that already hold the grace days and the notice steps. · **OQ-170** *"Immediate"* — a missed instalment lifts the plan pause the next day, no grace. · **OQ-137 (ladder half)** *"Same $25 floor on the whole ladder"* — the floor is not only the late fee's. · **OQ-157** *"per utility - uyiliyy can define it using settings"* — the **$25.00 is the seeded DEFAULT and each utility sets its own** in Settings; a submetered block averaging **$38** a bill and a municipal water utility averaging **$180** cannot share one floor. ⚠ **Recorded honestly from the decision log: OQ-137 and OQ-157 are DIFFERENT questions ruled on the same day** (the ladder's scope, and whether the figure is tenant-set) — the ladder answer was first written beside the wrong number, and the two must not be read as one ruling. The floor figure itself lives in BR-BIL-001 (billing's rule, not amended by this lane).

---
id: US-PAY-015
epic: EP-PAY-04
module: payments
screens: [S35, S34]
wave: 4
status: draft
blocked_by: []
depends_on: [US-PAY-013, US-PAY-014, US-BIL-023]
journeys: [J4]
rules: [BR-PAY-017, BR-NOT-005, BR-PAY-029]
golden_tests: []
finance_calc: none
---
### US-PAY-015 — Manual reminder + disconnect-notice modals (bulk, queue-writes, notice_history)

**1 · Details** — As a Billing Clerk, I want the S35 bulk modals from S34 selections: **Send a friendly reminder** (tone Friendly/Firm/Final-warning selecting the tier template; channels email/SMS/print with per-channel eligibility counts — "Email 4 of 4 · SMS 3 of 4 opted in"; template preview with tokens {first_name} {account} {balance}; pay-now-link toggle = rails-deferred token) and **Send disconnect notices** (tier 1st 10-day / 2nd 5-day / Final 48-hr; service-cut date; reconnect fee DISPLAYED from tenant charge codes per BR-BIL-007 — read-only; delivery elections incl. **certified mail required for final**; the medical-hold banner "1 of 4 selected is on a medical hold and will be skipped" with the skip enforced). Every send is a **queue-write** (BR-NOT-005; paper dispatches v1, email/SMS rows deferred to their rails per BR-PAY-017); every send/skip appends `notice_history`; manual sends record the tier into the collection state so the automatic ladder (US-PAY-014) and manual action never double-send a tier. Entry: S34 bulk/row. Exit: queue rows + history + state; toast "Sent N ✓" (IS-6).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-017 | Manual sends use the same tier ladder, channels and exclusions as the sequence engine; channels beyond paper ride the queue when their rails land. | CONFIRMED — PO PA-6, 2026-08-08 |
| BR-NOT-005 | All modal sends are outbound-table writes; the dispatcher sends. | CONFIRMED — PO volume ruling (r12 #16) |
| BR-PAY-029 | Reminder/notice are S34 bulk actions. | CONFIRMED — PO Lane B-8 |
| BR-CUS-039 *(consumed)* | Notice tiers/content per A19 §2; certified for final; reconnect fee from charge codes; medical-hold excluded. | CONFIRMED — customers pack (cited) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Reminder to 4 selected ($11,642.90), tone Friendly, channels email+SMS | Queue rows: 4 email + 3 SMS (opt-in only) with deferral markers, 0 paper; notice_history appended ×4; collection state notes the reminder; toast "Send to 4 ✓" |
| TC-2 | Disconnect notice, tier 2nd (5-day), cut date Aug 11, 4 selected incl. 1 medical hold | Banner shows the skip; **3** notice sets queued (paper + certified where final), 1 skip recorded with reason; reconnect fee display = tenant RECONN code $45.00 — not editable |
| TC-3 | Tier Final (48-hr) | Certified-mail election forced on (A19 rule 3); SMS alone impossible; cut date within tenant rules |
| TC-4 | Manual 2nd notice on an account the engine already has at tier 2 | No double-send — state dedupes the tier (US-PAY-014 shared state); staff see "tier already sent Jul 30" |
| TC-5 *(negative)* | Reminder with zero channels selected | Confirm disabled (≥ 1 channel); nothing queued |
| TC-6 *(negative)* | Direct provider call attempted from the modal path | Forbidden — queue is the only path (BR-NOT-005) |
| TC-7 *(isolation)* | Lone Star Ridge bulk reminder | Its templates/queue rows only (RLS) |

**4 · Test Data** — Prototype selections: 4 accounts $11,642.90 (A-11340, A-11024, A-10802, A-11020 — A-11020 medical hold). Reminder tokens per prototype preview. Notice: tier 2nd, cut Aug 11 2026, RECONN $45.00 (Brazos Bend charge code — B4 sample). Templates: tenant reminder/notice per tier (S67/BR-NOT-004 family). Actors: Priya Menon. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Tone / tier select | S35 | prototype-extracted | template selection (tier) per BR-PAY-017 ladder | enum | user-input | maps to tier templates |
| Channel elections + eligibility counts | S35 | prototype-extracted | `outbound_messages` rows per account × elected channel (r12 #16) | boolean/counts | user-input | opt-in respected; ≥1 channel |
| Preview + tokens | S35 | prototype-extracted | template render ({first_name},{account},{balance}) | text | computed-display | template-owned (notifications) |
| Pay-now / text-to-pay link | S35 | prototype-extracted + BR-PAY-017 | token in SMS/email body — rails-deferred (W7) | flag | user-input | inert until rails |
| Service-cut date | S35 Notice | prototype-extracted | notice content field + collection state | date | user-input | ≥ notice-period days for the tier |
| Reconnect fee display | S35 Notice | prototype-extracted + BR-BIL-007 | `charges` RECONN read (rating-owned) | numeric USD | reference-data | display-only, from the code |
| Certified election | S35 Notice | A19 rule 3 (BR-CUS-039) | certified marker on the queue row | boolean | system-derived | forced on final |
| Medical-hold skip | S35 Notice | A15 | skip + notice_history entry | — | system-derived | enforced server-side |
| notice_history / state | S34 | BR-PAY-017 + J4 | `notice_history` append (r12 #7) + tier state | rows | system-derived | send AND skip recorded |
| Audit | — | CLAUDE.md #7 | `audit_log` `notice.sent` / `reminder.sent` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a bulk send, Then queue rows exist per account × elected channel (respecting opt-ins and deferral markers), notice_history and tier state update, and the toast counts match.
- Given a medical hold in the selection, Then the account is skipped with the skip recorded — demoably "Send 3 notices ✓" from a 4-selection.
- Given the final tier, Then certified mail is mandatory and SMS never stands alone.
- Given engine + manual overlap, Then a tier never double-sends.

**7 · Finance Calculation** — N/A (notices move documents; the reconnect fee is displayed from the charge code, applied only by billing flows).

**8 · Open Questions** — None.

---
id: US-PAY-016
epic: EP-PAY-04
module: payments
screens: [S35, S30, S32, S21]
wave: 4
status: draft
blocked_by: []
depends_on: [US-BIL-023, US-BIL-024]
journeys: [J4]
rules: [BR-PAY-018, BR-NOT-005]
golden_tests: []
finance_calc: none
---
### US-PAY-016 — Returned mail: mark returned → bad-address flag → needs-attention → paper suppressed

**1 · Details** — As a Billing Clerk working the returned-mail stack (a Tuesday chore — model §11), I want to mark delivery records **returned** (single row on S30's delivery dashboard / bulk from S35, PE-16): each mark writes a **delivery-return event**, sets the account's **bad_address flag** (r12 #8), lands the account in a **needs-attention queue** (S32 chip + S21 account banner), and — per tenant config — **suppresses paper delivery until the address is verified** while balances and billing continue completely unaffected (BR-PAY-018). Fixing/verifying the address clears the flag, lifts suppression, and closes the queue entry; suppressed-while-flagged documents remain queued rows (BR-NOT-005) so nothing is lost — they release on verification. All audited. Entry: S30 delivery rows / S35 bulk-mark. Exit: flag + queue + suppression state; history on the account.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-018 | Returned mail: delivery record marked returned (single/bulk) → account bad-address flag → needs-attention queue + banner → paper suppressed until address verified (config); balances unaffected; audited. | CONFIRMED — PO PA-7, 2026-08-08 (r12 #8, PE-16) |
| BR-NOT-005 | Suppression operates on queue rows (held, never deleted); release re-queues for dispatch. | CONFIRMED — PO volume ruling (r12 #16, applied) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | PE-16: A-11455's paper bill comes back; Priya marks the delivery record returned | Delivery-return event; `accounts.bad_address` = true; needs-attention queue entry; S32 chip +1; S21 banner "Mail returned — address needs verification"; audit `delivery.returned` |
| TC-2 | Bulk-mark: 12 returned pieces in one action | 12 events, de-duped to their accounts; per-row results; the stack clears in one pass (model §11 "bulk-mark supported") |
| TC-3 | Suppression while flagged (tenant config ON) | Subsequent paper queue rows for A-11455 hold with a suppressed marker — written, never dispatched, never lost; email/SMS rows unaffected (their own rails); balances/late fees continue normally (BR-PAY-018 "balances unaffected") |
| TC-4 | Address verified/corrected (customers flow) | Flag clears; queue entry closes with resolution; held paper rows release to the dispatcher; audit `bad_address.cleared` |
| TC-5 *(negative)* | Mark-returned on a delivery row already marked returned; or on an email row | Idempotent (no duplicate events); returned-mail is a paper-channel event — email bounces ride the queue's own bounced status (BR-BIL-016), not this flow |
| TC-6 *(isolation)* | Lone Star Ridge returned stack | Its rows/flags/queues only (RLS) |

**4 · Test Data** — A-11455 Park, Jenna: paper bill BL-2607-018206 delivery row → returned Aug 12, 2026. Bulk stack: 12 pieces across 9 accounts. Tenant config: suppress_paper_on_bad_address = true. Verification: address corrected Aug 19 (US-CUS address flow). Actors: Priya Menon. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Mark returned (single/bulk) | S30 delivery rows / S35 | BR-PAY-018 | delivery-return events (r12 #8, bulk-markable) | rows | user-input | paper-channel rows only |
| bad_address flag | S21/S34 | BR-PAY-018 | `accounts.bad_address` (r12 #8) | boolean | system-derived | set on first return; cleared on verify |
| Needs-attention queue + chip | S32 | BR-PAY-018 | queue read-model over flagged accounts | rows/int | computed-display | ties to flags |
| Account banner | S21 | BR-PAY-018 | rendered from the flag | text | computed-display | until cleared |
| Paper suppression | — | BR-PAY-018 (config) | held marker on paper `outbound_messages` rows (r12 #16) | flag | system-derived | rows kept, released on verify |
| Suppression config | S66 | BR-PAY-018 ("config") | tenant setting suppress_paper_on_bad_address | boolean | reference-data | tenant-set |
| Verification / clear | S21 | BR-PAY-018 | flag clear + queue resolution + release | — | user-input (customers flow) | audited |
| Audit | — | CLAUDE.md #7 | `audit_log` `delivery.returned` / `bad_address.set/cleared` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a returned piece (single or bulk), Then the event, flag, chip and banner all appear, and balances/billing continue untouched.
- Given suppression config on, Then paper rows hold without loss and release on address verification; email/SMS channels are unaffected.
- Given verification, Then flag, queue and suppression all clear with the audit chain complete.
- Given tenants, Then flags and queues never cross.

**7 · Finance Calculation** — N/A (delivery-state flow only; PE-16 is document-path, not money).

**8 · Open Questions** — None.

**9 · Build state (2026-08-16, returned-mail surface lane) — BUILT END TO END, AND ONE CLAUSE IS DELIBERATELY NOT.**

**What existed and could not be reached.** `apps/payments/returned_mail.py` has written the
delivery-return event, derived the bad-address flag, aged the needs-attention queue and audited
every mark since 2026-08-11. `POST /deliveries/returned` (US-NOT-014, notifications-owned per
11b §2.9) mounted on 2026-08-16 morning and hands every event to this module's
`mark_returned_bulk` through `apps/notifications/payments_seam.py`. The S32 chip had COUNTED the
queue for days. **A clerk holding a Tuesday stack had nowhere to type an envelope** — which is
exactly what `10-scripts/gates/surface_debt.txt`'s `payments` line said.

**What shipped (§1's own entry points, both of them):**
* **S30 delivery rows** — every row on a bill's delivery panel carries *Mark returned* and a
  *Came back* date. Live only on PAPER rows not already marked; an email row renders DISABLED with
  the true reason (a bounce is the provider's fact, BR-BIL-016), and a marked row shows its date.
* **S35 bulk mark** — opens from the returned-mail chip on S32, lists the stack still to work
  (`f.channel=pdf_print&f.returned=false`), marks the selection in one action and names every
  refusal with the server's own sentence.
* Both are `07-frontend/src/features/payments/returnedMail.tsx` — ONE module, because the four
  rules are one rule set.

**Two reads landed with them because nothing else could have:**
`apps/billing/selectors._deliveries_for` now serves `returned_at` and `held`; `f.returned` is a
declared filter on `GET /outbound`. Both RED-PROVED before being trusted.

**TC-3 IS THE CLAUSE THAT IS NOT BUILT, and it is not a gap in this lane's work.** Paper
suppression is BR-NOT-005's `held` marker on the queue row and its only writer is the dispatcher
(US-NOT-002), which is OUT OF THIS RELEASE by PO ruling. `held` is SERVED so the panel can state a
hold the day one appears; every row reads `false` today and **no screen claims otherwise**. TC-4's
release half is the same story.

**TC-2's fourteen** are asserted server-side (`06-backend/tests/test_us_pay_016_surface.py`), with
the money tables counted either side — J18 step 6's *"zero money rows written or changed"*. The
browser proof (`07-frontend/e2e/US-PAY-016-returned-mail.spec.ts`, 20 assertions against a real
Django and Postgres) covers TC-1 and TC-5 by clicking.

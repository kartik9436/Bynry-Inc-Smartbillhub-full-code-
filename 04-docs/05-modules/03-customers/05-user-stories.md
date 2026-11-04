# customers (Accounts) — User Stories (INDEX)
> Reconciled 2026-08-08 against PO rulings (BR-CUS-046..059) — propagation sweep.

**Stories live inside their epic files in [`06-epics/`](06-epics/).** This index is generated from story frontmatter at each pack merge — do not hand-edit story content here.

| Story | Title | Epic file | Status | Wave |
|---|---|---|---|---|
| US-CUS-001 | Accounts list table & header roll-up | [EP-CUS-01-accounts-list.md](06-epics/EP-CUS-01-accounts-list.md) | draft | W2 |
| US-CUS-002 | Search, status segments & wizard entry points | [EP-CUS-01-accounts-list.md](06-epics/EP-CUS-01-accounts-list.md) | draft | W2 |
| US-CUS-003 | New Account wizard (S18, six steps) | [EP-CUS-02-account-lifecycle.md](06-epics/EP-CUS-02-account-lifecycle.md) | draft | W2 |
| US-CUS-004 | Move-In wizard (S19, five steps) | [EP-CUS-02-account-lifecycle.md](06-epics/EP-CUS-02-account-lifecycle.md) | draft | W2 |
| US-CUS-005 | Move-Out wizard (S20, four steps) & final-bill handoff | [EP-CUS-02-account-lifecycle.md](06-epics/EP-CUS-02-account-lifecycle.md) | draft | W2 |
| US-CUS-006 | Account attribute snapshot at assignment (incl. solar/battery capacity units) | [EP-CUS-02-account-lifecycle.md](06-epics/EP-CUS-02-account-lifecycle.md) | draft | W2 |
| US-CUS-007 | Deposit application per rate-plan deposit rules | [EP-CUS-02-account-lifecycle.md](06-epics/EP-CUS-02-account-lifecycle.md) | draft | W2 |
| US-CUS-008 | Detail header, status pills & action rails | [EP-CUS-03-account-detail.md](06-epics/EP-CUS-03-account-detail.md) | draft | W2 |
| US-CUS-009 | Overview tab (recent bills, usage trend, customer/payment/deposit/portal panels) | [EP-CUS-03-account-detail.md](06-epics/EP-CUS-03-account-detail.md) | draft | W2 |
| US-CUS-010 | Financial tabs: Bills · Payments · Adjustments (read-models with boundaries) | [EP-CUS-03-account-detail.md](06-epics/EP-CUS-03-account-detail.md) | draft | W2 |
| US-CUS-011 | Operational tabs: Usage · Meters · Documents · Notes · Audit | [EP-CUS-03-account-detail.md](06-epics/EP-CUS-03-account-detail.md) | draft | W2 |
| US-CUS-012 | Record payment modal | [EP-CUS-04-account-actions.md](06-epics/EP-CUS-04-account-actions.md) | draft | W4 |
| US-CUS-013 | Adjust & Issue credit modals | [EP-CUS-04-account-actions.md](06-epics/EP-CUS-04-account-actions.md) | draft | W4 |
| US-CUS-014 | Send statement & Print bill modals | [EP-CUS-04-account-actions.md](06-epics/EP-CUS-04-account-actions.md) | draft | W4 |
| US-CUS-015 | Disconnect notice & Add note modals | [EP-CUS-04-account-actions.md](06-epics/EP-CUS-04-account-actions.md) | draft | W4 |
| US-CUS-016 | Pick plan, effective date & proration preview (steps 1–2) | [EP-CUS-05-change-plan.md](06-epics/EP-CUS-05-change-plan.md) | draft | W8 |
| US-CUS-017 | Confirm, sync unit + account & notify (step 3) | [EP-CUS-05-change-plan.md](06-epics/EP-CUS-05-change-plan.md) | draft | W8 |
| US-CUS-018 | Payment Plan wizard (amount & term → editable schedule → agreement & activation) | [EP-CUS-06-payment-plan.md](06-epics/EP-CUS-06-payment-plan.md) | draft | W4 |
| US-CUS-019 | Bulk account upload against the published template (customer-linked, premises-first) | [EP-CUS-07-account-onboarding.md](06-epics/EP-CUS-07-account-onboarding.md) | draft | W2 |
| US-CUS-020 | Source→target value-mapping step (legacy codes → tenant reference data) | [EP-CUS-07-account-onboarding.md](06-epics/EP-CUS-07-account-onboarding.md) | draft | W2 |
| US-CUS-021 | Opening balances as aged buckets (aging correct from day one) | [EP-CUS-07-account-onboarding.md](06-epics/EP-CUS-07-account-onboarding.md) | draft | W2 |
| US-CUS-022 | Opening journal entries: the balanced AR↔clearing handoff to ledger | [EP-CUS-07-account-onboarding.md](06-epics/EP-CUS-07-account-onboarding.md) | draft | W2 |
| US-CUS-023 | Deposits-on-file import with original receipt dates + interest accrual start | [EP-CUS-07-account-onboarding.md](06-epics/EP-CUS-07-account-onboarding.md) | draft | W2 |
| US-CUS-024 | `REQ-03` the applicant's form — six steps, a number from the first save, and a fee that is a quote | [EP-CUS-09-service-requests.md](06-epics/EP-CUS-09-service-requests.md) | ready | CR-030 W4 |
| US-CUS-025 | `REQ-01` the requests list — five tiles, five segments, oldest first, and one cell that may not be styled | [EP-CUS-09-service-requests.md](06-epics/EP-CUS-09-service-requests.md) | ready | CR-030 W4 |
| US-CUS-026 | `REQ-02` the request detail — six tabs, two save controls, and a decision nothing preselects | [EP-CUS-09-service-requests.md](06-epics/EP-CUS-09-service-requests.md) | ready | CR-030 W4 |
| US-CUS-027 | The transfers worklist (S89) — one job, two addresses, and a money cell that may show no figure at all | [EP-CUS-08-transfer-disconnect-worklists.md](06-epics/EP-CUS-08-transfer-disconnect-worklists.md) | ready | CR-030 W7 |
| US-CUS-028 | The disconnects worklist (S90) — the ladder, its protections, and the column that makes no delivery claim | [EP-CUS-08-transfer-disconnect-worklists.md](06-epics/EP-CUS-08-transfer-disconnect-worklists.md) | blocked (OQ-374) | CR-030 W7 |
| US-CUS-029 | The transfer wizard (`TRF-02`) — one job, five steps, and a carried deposit whose total cannot be shown | [EP-CUS-10-transfer-disconnect-wizards.md](06-epics/EP-CUS-10-transfer-disconnect-wizards.md) | ready | CR-030 W7 |
| US-CUS-030 | The disconnect wizard (`DSC-02`) — it schedules, it never cuts, and it will not say "All clear" | [EP-CUS-10-transfer-disconnect-wizards.md](06-epics/EP-CUS-10-transfer-disconnect-wizards.md) | ready | CR-030 W7 |
| US-CUS-031 | Parked wizard drafts on each flow's own tab (S17.2) — drafts that are not records, pinned above the list they belong to, and an age that is the whole feature. ⛔ **RE-POINTED 2026-08-26 (CR-035 · AMENDMENT 1)**: was *"The Waiting-on list — eight columns…"*; the PO struck the ninth tab (*"seperate queue not reequired"*) and the behaviour moved onto the five flow tabs as a pinned panel. The story is kept, not deleted — the behaviour kept its home rather than disappearing | [EP-CUS-11-waiting-on.md](06-epics/EP-CUS-11-waiting-on.md) | ready | CR-035 (`2.51.0`) |

**31 stories.**

> ⚠ **US-CUS-029 and US-CUS-030 were transcribed into this index on 2026-08-26** by
> the CR-035 close-out lane. They have existed in
> [`EP-CUS-10`](06-epics/EP-CUS-10-transfer-disconnect-wizards.md) since 2026-08-25
> with full frontmatter and were **missing from this table**, which is the file
> anybody greps first for *"which story owns this screen"* — the same gap
> DEF-695 records one epic over. Nothing was renumbered; only the index was
> completed.

> ✅ **US-CUS-024 · 025 · 026 ARE NOW ALLOCATED AND WRITTEN — 2026-08-25, CR-030
> task 4.16, by the W4-FINISH lane.** They live in
> [`EP-CUS-09-service-requests.md`](06-epics/EP-CUS-09-service-requests.md) in the
> same eight-section format as every other story, and `J26`'s `stories:` list now
> names them. **The box below is kept, superseded, because its DIAGNOSIS is still
> the useful part** and because two of its statements are still true: the wizard
> halves of S89/S90 own no story, and no screen id is allocated to any request
> screen (decision **D1**).
>
> ⚠ **THE THREE NEW STORIES CARRY `screens: []`, NOT `[S83]`/`[S84]`/`[S85]`.**
> A1 declares none of the three, D1 is unruled and
> `07-frontend/src/routing/screenIds.ts` already refuses them for that reason. The
> box below is right that *"inventing them here would index screens against ids
> nobody can look up"* — so the stories exist and the ids do not, which is the
> only combination that is honest today. ⚠ **`US-CUS-027`/`028` above take the
> other posture (`screens: [S89]` / `[S90]` for ids A1 also does not declare).
> One of the two is wrong and a lane may not settle D1 by picking either;
> recorded here so the divergence is visible rather than inherited.**

> ~~⚠ **US-CUS-024 · 025 · 026 ARE NOT ALLOCATED, AND THE GAP IS DELIBERATE — DEF-695.**~~ **SUPERSEDED 2026-08-25 — see above.**
> The two rows above were transcribed from `EP-CUS-08`'s own story frontmatter on
> **2026-08-25** by the W7-TESTS lane, because **S89 and S90 shipped with both
> halves built and no story owning either** (hard-won law 8) and this index —
> the file anybody greps first for *"which story owns this screen"* — did not
> carry them. `EP-CUS-08` allocated 027 and 028 and left **024–026 free for the
> REQUESTS screens S83 / S84 / S85**, which are also built and also own no story:
> `08-qa/01-e2e/journeys/J26-request-to-service.md` names them as owed
> (*"US-CUS-024 (capture) · US-CUS-025 (the list) · US-CUS-026 (the detail and
> its decision)"*). **Three stories are still OWED**, and inventing them here
> would index screens against ids nobody can look up.
>
> ⚠ **AND EACH ROW ABOVE COVERS THE *LIST* HALF OF ITS SCREEN ONLY.** B18 §3 maps
> S89 as *"Transfers tab — list **+ 5-step wizard**"* and S90 as *"Disconnects tab
> — list + ladder **+ 5-step wizard**"*. `TRF-02.1…5` and `DSC-02.1…5` have **no
> route in this application**, and the write paths behind them
> (`apps/customers/transfers.py`, `apps/customers/disconnects.py` — CR-030 W7
> tasks 7.1–7.3 and 7.5–7.9) are owned by **no story at all**. Both source files
> say so in their own Trace headers. **A story is owed for each write path.** Rules: [`02-business-rules.md`](02-business-rules.md) · Fields: [`03-field-map.md`](03-field-map.md) · Traceability: [`../../10-traceability-matrix.md`](../../10-traceability-matrix.md)

# billing — Flows & States

> Fleshed out 2026-08-08 from the ratified model (`07-pre-session-model.md` §6, r1.2–r1.4) and BR-BIL-001..029. Exact DB enum spellings = Eng-Lead 🔒 (B2 r10 #15); the transitions below are the ratified behavior.

## 1. The bulk run pipeline (S31 — everything visible before anything commits)

```
S30 "Start a billing run"
  → SELECT (US-BIL-001)        bill_runs row · idempotency key (tenant+cycle+period) — identical re-run blocked w/ who/when/link
  → CHECK  (S31.2, US-BIL-002) Consumers · Plans · Reads · Balances · Credits · Overcharges (guardrail BR-BIL-029)
  → EXCEPTIONS (S31.3, US-BIL-003) per-case dispositions; missing service = estimate | hold | bill-without-service (BR-BIL-015)
  → DRAFTS (US-BIL-004)        full line detail; powers: exclude / re-rate / add charge line — computed amounts never editable; discard free
  → ISSUE  (US-BIL-005)        all-remaining or subset: number VERIFIED (allocated at draft, BR-BIL-063) · immutable · GL + template pinned · posting handoff · delivery queued · audit
```
Run states (behavioral): `draft → in_preview → drafting → partially_issued → issued/closed`; a run with held accounts stays linked to its **catch-up sub-runs** (`parent_run_id` + scope, idempotency = parent key + scope — BR-BIL-015/r1.3). Held accounts sit in the **Pending-billing queue**: `held → escalated (age > tenant days) → resolved (catch-up link)` — nothing silently stays unbilled.

## 2. Invoice lifecycle (A5 + r10 #12)

`draft → issued → paid` · derived display state `past-due` (issued ∧ unpaid ∧ due_date passed) · `corrected` (credit note + rebill chain exists — original stays issued+visible) · `void` (reversing entries per OQ-012 windows; never deleted). `bill_type`: `cycle | first | final | rebill | backbill | penalty`. Issued invoices/lines: no UPDATE/DELETE ever (BR-BIL-004).

## 3. Correction workflow (r1.2 — single + bulk, EP-BIL-04)

```
Initiate (bill or bulk selector) → Reason code (reference data) → Scope (single | run/cycle/plan/service/date-range)
  → Impact preview (credit note · rebill lines · GL reversals · balance delta · payment re-allocation plan)  ← the approval artifact
  → Approval (v1: ALL by System Admin — OQ-072)   ← NO money-bearing write before this
  → Execute (bulk = staged background job: idempotent, resumable, per-bill results)
  → Deliver (rebill pins the CURRENT template version) + audit every record touched
```
Case states: `preview → pending_approval → approved → executing → executed | partially_failed (resumable) → delivered`. Back-bills and penalty bills pass the same gate (BR-BIL-018/019).
⚠ **AMENDED 2026-08-12 — the flow above describes the RESTATEMENT (class R) only, and the other two classes now have their missing half (BR-BIL-041).** **Class C (goodwill / concession, OQ-105 + OQ-168):** credit note, **no rebill**, and the posting is **DR write-off / CR customer credit balance** — a *separate* write-off account, never a reversal of the original service revenue (GT-6: a **$25.00** credit on a **$247.30** invoice leaves **$222.30** owing either way, and it **counts in the phase-4 sign-off panel like a replacement**, OQ-121). **Class D (document-only, OQ-103 + OQ-169 + DEF-084):** no credit note, no rebill, no posting, delta exactly **$0.00** — the artifact is a **reissued corrected document instance**; a later reprint, re-send or dispute copy renders **the corrected one**; and reissues **ACCUMULATE**, each composed from the instance before it.

## 4. Delivery queue (r1.4 — BR-BIL-016)

Issue writes one delivery record per bill per channel → dispatcher hands tenant-config batches (default 500) to the provider.
Row states: `queued → sent → delivered | failed | bounced`; retry ×3 with backoff before `failed`; dashboard **re-queue** resets to `queued`. Print/PDF active v1 (batch PDF from the queue); **email channel rows written from day one, dispatch deferred → W6** (OQ-073); BYO mailbox vs transactional ESP per OQ-074. Mass sends are never synchronous.

## 5. Budget billing states (BR-BIL-017)

`eligible (12-mo history + plan flag) → enrolled (level = trailing-12 avg, whole $) → [re-leveled at ±20% drift each 6 mo | level-overridden ±30% w/ reason] → settle-up month (variance collected/credited as non-taxable AR-timing line, balance resets) → ~~off_budget (after 2 missed payments — variance carried into the next actuals bill)~~ off_budget (STAFF removal from S30 only)`. Every parameter tenant-set, seeded with the BR-BIL-017 defaults.
⚠ **STAMPED LATE — the automatic drop-off was SUPERSEDED on 2026-08-11 (PO: *"nodrop we chase for payments until write off"*, OQ-141) and this flow still described it.** There is **no drop-off event**: an account that falls behind is chased through the ordinary collections path to write-off and stays on its level while that happens. `off_budget` survives only as a **staff decision taken from S30 ("Remove from budget"), with a reason and an audit row** — a different thing entirely from a silent consequence of two arrears. See BR-BIL-017.
⚠ **AMENDED 2026-08-12 (PO, OQ-164) — the FINAL bill of an enrolled account is the LEVEL ONLY: 242.00, not 282.27.** A move-out does not fold the accumulated variance into the last level payment; the variance is settled through the settle-up, which is its own event. ⚠ **OQ-142 (which account the settle-up line touches) is still OPEN** — the settle-up's GL side stays stubbed on it.

## 6. Template versions (BR-BIL-025/026/027)

`draft → published (one per template; Admin only) → archived`; append-only versions; **pinned at issue** — reprint renders the pinned version forever; a pinned version can never be deleted (audit-lock). Assignment: consumer-category default, account override.

## 7. Final-bill settlement (BR-BIL-013 — exactly one path)

`move-out handoff (BR-CUS-031) → final bill through the move day → deposit + interest auto-apply FIRST **against the account's WHOLE CLOSING POSITION** → one of: refund · collect (cycle due-days) · transfer-to-master (landlord-link prereq, balanced + audited) · payment plan · small-balance write-off (|bal| ≤ tenant $5 default, both directions)`.
⚠ **AMENDED 2026-08-12 (PO, OQ-158): *"everything outstanding"*.** The deposit settles the final bill **plus every arrear**, never the final bill alone. **Worked:** a **$120.84** prior balance inside a *Final amount due* of **$184.20** — the bill-only reading refunds **$90.14** to a customer who is in debt to the utility on an account that is now closed. WE-7's frozen figures are unaffected (that account has no arrears). Pairs with OQ-179 the same day: **no mid-tenancy deposit differential exists** — the deposit is settled ONCE, at closure.

Screens: A1 (S30/S31/S31.2/S31.3); states standard: A18/A5. Journeys: J2 (read-to-cash step 8–9), J5 (posting/month-end), J6 (corrections).

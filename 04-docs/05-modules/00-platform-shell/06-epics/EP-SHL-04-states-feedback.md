# EP-SHL-04 — States & feedback (A18 components + toast system)

**Module:** platform-shell · **Wave:** W0 · **Screens:** no own S-number — the six A18 patterns and the toast surface compose into every screen (S7–S48, S49–S60, S91–S114) · **Status:** draft

## Scope
**In:** the six A18 shared patterns as reusable components — empty list, zero-results-after-filter, loading skeleton, failed-with-retry (incl. partial-success counts), inline form validation (presentation kit shared with EP-SHL-03), permission denied — plus the global toast system (bottom-center, ~2.5s auto-dismiss, aria-live).
**Out:** per-screen empty-state copy (each consuming screen supplies its own title/helper/CTA through the component's slots), the events that *trigger* toasts (consuming modules fire them with A13 copy), the notifications bell (EP-SHL-01/OQ-019).

## Capability matrix (list screens only — B9 conformance)
N/A — no list screens. IS-7 delegates state behavior to A18; this epic ships the components those conformance rows rely on.

## Stories

---
id: US-SHL-011
epic: EP-SHL-04
module: platform-shell
screens: [S17, S25, S28, S33, S36, S38]
wave: 0
status: draft
blocked_by: []
depends_on: []
journeys: []
rules: [BR-SHL-020]
golden_tests: []
finance_calc: none
---
### US-SHL-011 — The six A18 states as reusable components

**1 · Details** — As a staff user, I want every list, detail, wizard, and import to handle "nothing yet / nothing matches / still loading / it broke / I typed it wrong / I'm not allowed" the same way, so that the app never dead-ends me. Ship six components per A18, built from Modernist tokens (A12, incl. the 2026-08-07 semantic success/warning/danger tokens): **(1)** EmptyList — centered h4 title + 13px muted helper + primary create action; replaces the whole table (never an empty header). **(2)** ZeroResults — toolbar/filters stay; rows region shows "No results for '‹query›'." + ghost "Clear filters"; no create action here. **(3)** LoadingSkeleton — real layout with shimmer bars (tables 6–10 rows; KPI-sized blocks; card/title variants); buttons that trigger work show disabled + "Working…". **(4)** FailedWithRetry — `.card` with danger top border + "Failed" pill; bold what-failed line, muted plain-language reason; Retry / Download error report / Cancel; partial success shows counts with a link to failing rows. **(5)** Inline validation — presentation kit per US-SHL-009 (same component family). **(6)** PermissionDenied — centered title/helper/"Back to Dashboard"; no data rendered behind. Consumers: every module (representative screens cited in frontmatter).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| BR-SHL-020 | The six A18 patterns exist exactly once as shared components; screens compose them and may supply only slot content (titles, helpers, CTAs, reasons) — never re-implement the pattern. An empty table header with zero rows must never render anywhere in the app. Failed-state reasons are plain language (e.g. "We couldn't read row 42 (missing amount).") — never raw error codes alone. | CONFIRMED — A18 preamble ("six SHARED patterns… every list, detail, wizard, and import composes from these") + A18 §1–§6 <br><br>**AMENDED 2026-08-19 (r2) — PO ruling, verbatim: *"server detail text should not reach customer screens"*.** A failed-state reason is still plain language and still never a raw error code — and it now comes from **the catalogue entry for the refusal's `message_key` and from nothing else**. `params.detail` is a diagnostic: it reaches the BR-AUD-018 attempt row and the server log, never a screen. `envelopeErrors()` and `refusalText()` (07-frontend) strip it before i18next sees it, so a catalogue value cannot reintroduce it by interpolating `{{detail}}`.<br><br>**And the third clause, ruled the same day:** a refusal the user CANNOT act on says it is a **system error**, that **nothing was changed**, and hands over an identifier — *"Something went wrong on our side. Nothing was changed — quote {{ref}} to support."* `{{ref}}` is the envelope's own `trace_id` shortened to eight hex characters (`5F2B-9C1D`) because a person has to read it aloud, and the S61 audit filter matches that short form by prefix so support can look it up. A refusal the user CAN act on carries no identifier. Twelve of the forty-eight keys written on 2026-08-19 are that group; the other thirty-six say what is wrong and what to do next.<br><br>**Copy shape, same day (decision log `6baa846`):** no sentence over 12 words, at most two sentences per message — the catalogue's own median longest sentence rounded up from 9. Shorten by deleting RATIONALE, never the sentence that says what to do next. |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Brand-new tenant opens S17 Accounts (zero accounts) | EmptyList: "No accounts yet." + helper + "+ New account" primary button; no table header rendered |
| TC-2 | S17 has data; search "zzzz" | ZeroResults: toolbar stays, rows replaced by "No results for 'zzzz'." + "Clear filters" ghost button; **no** create button (A18 §2) |
| TC-3 | Open S33 on a slow connection | 6–10 skeleton rows in the real table layout; never a bare spinner for the content area |
| TC-4 | Bank statement import (S38) fails on row 42 | FailedWithRetry card: danger top border, "Failed" pill, "Bank statement import failed." + "We couldn't read row 42 (missing amount)." + Retry/Download error report/Cancel |
| TC-5 | Read import (S28) partially succeeds | Counts render: "84 imported · 6 need review · 2 failed" with a working link to the failing rows |
| TC-6 (negative) | Click Retry on TC-4 and the retry succeeds | Failed card replaced by the normal success flow; no duplicate import of the 84 already-imported rows (retry re-runs per the consuming module's idempotency, surface just re-invokes) |
| TC-7 | Jordan (Billing Clerk) deep-links /finance | PermissionDenied: "You don't have access to this." + "Billing Clerks can't open Finance. Ask a System Admin if you need it." + "Back to Dashboard"; DOM contains no Finance data |

**4 · Test Data** — Fresh tenant "Maple Court Utilities" (zero accounts) for TC-1; Silver Creek S17/S33 seeds from EP-SHL-02 §4; S38 bank file `firstnational-2026-08-06.csv` with row 42 missing its amount; S28 read file with 92 rows (84 clean, 6 flagged, 2 malformed); Jordan Blake (Billing Clerk) for TC-7.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Empty-state slots (title/helper/CTA) | every list | A18 §1 | none (per-screen copy, externalized per IS-8) | text | reference-data | supplied by consuming screen |
| Zero-results query echo | every searchable list | A18 §2 | none | text | computed-display | echoes current `q` |
| Skeleton variant (table/KPI/card) | all content areas | A18 §3 | none | — | computed-display | matches real layout |
| Failure reason + partial counts | imports/syncs | A18 §4 | none (from job result payload) | text / ints | integration | plain language; counts link to failing rows |
| Permission-denied copy | any gated route | A18 §6 | none | text | computed-display | role + module named in helper |

**6 · Acceptance** — Given the seeds in §4, When each of the seven scenarios runs, Then the rendered state matches its A18 pattern (verified against A18's copy and token requirements), no screen ever shows an empty table header or a bare content spinner, and the permission-denied route leaks no data into the DOM.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-SHL-012
epic: EP-SHL-04
module: platform-shell
screens: [S22, S31, S35, S38]
wave: 0
status: draft
blocked_by: []
depends_on: []
journeys: []
rules: [BR-SHL-021, BR-SHL-022]
golden_tests: []
finance_calc: none
---
### US-SHL-012 — Toast system

**1 · Details** — As a staff user, I want a transient confirmation toast after every committed action, so that I get closure without a blocking dialog. One global toast surface owned by the shell: bottom-center, ~2.5s auto-dismiss (04-docs/README §Interactions, A13), announced via aria-live (IS-10). Consuming modules fire toasts with their A13 verbatim copy (e.g. "Payment $247.30 recorded · balance $0.00"); the shell owns queueing, timing, position, and accessibility. Toasts are feedback only — the durable record of any money action is its `audit_log` row (CLAUDE.md rule 7), never the toast. Entry: any module calls the toast API after a committed action (S22 modals, S31 run completion, S35 payment modals, S38 reconcile…). Exit: auto-dismiss.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| BR-SHL-021 | Toast contract: rendered bottom-center; auto-dismisses after ~2.5s; announced via an aria-live region without stealing focus; content is text (with A13's `·` separators), no actions inside the toast; a toast is never the only record of an action. | CONFIRMED — 04-docs/README §Interactions ("~2.5s auto-dismiss"), A13 §Global ("toasts auto-dismiss ~2.5s"), IS-10 ("toasts announced via aria-live") |
| BR-SHL-022 | Queueing: one toast visible at a time; toasts fired while one is visible queue FIFO and display sequentially, each with its full ~2.5s; the queue is unbounded in practice (bulk flows fire one summary toast, per A13's bulk copy — "Reminders sent to N customers" — not N toasts). | CONFIRMED (PO R1-B9 — statuses live in 02-business-rules.md; this cell was stale, synced 2026-08-09) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Record a $247.30 payment on A-10432 (S22) | Toast bottom-center: "Payment $247.30 recorded · balance $0.00"; gone after ~2.5s (2.0–3.0s tolerance) |
| TC-2 | Fire 3 toasts within 200 ms | Shown one at a time, FIFO, each for its full duration; none lost |
| TC-3 | Screen-reader session during TC-1 | Toast text announced via aria-live; keyboard focus stays where it was (no focus steal) |
| TC-4 (negative) | Action fails server-side | **No** toast fires — failures render A18 §4/§5 states, never a success toast; asserted for a failed payment post |
| TC-5 | Bulk reminder to 12 accounts (S35) | Exactly one toast: "Reminders sent to 12 customers" — not twelve toasts |
| TC-6 (negative) | Toast fires during route change (commit → redirect) | Toast survives the navigation and completes its display on the destination screen |

**4 · Test Data** — A-10432 payment $247.30 → balance $0.00 (matches A13 verbatim). Triple-fire copy set: "Note added" / "Adjustment posted · –$25.00" / "Statement sent · email + mail". Bulk: 12 Silver Creek accounts in the 60+ bucket.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Toast message | global surface | A13 §Toast confirmations (verbatim strings, externalized per IS-8) | none (transient; durable record = `audit_log` via the acting module) | text | computed-display | supplied by consuming module from A13 catalog |
| Toast queue | global surface | derived (BR-SHL-022) | none (client state) | FIFO list | system-derived | one visible; sequential |

**6 · Acceptance** — Given Jordan records the §4 payment, When the commit succeeds, Then the exact A13 toast renders bottom-center, is announced via aria-live without moving focus, and auto-dismisses in ~2.5s; And three rapid toasts display sequentially with none dropped; And a failed action never produces a success toast.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

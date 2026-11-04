# EP-SHL-03 — Forms & wizard framework

**Module:** platform-shell · **Wave:** W0 · **Screens:** no own S-number — consumed by every form/modal and by the guided wizards (S10, S11, S16, S18, S19, S20, S23, S24, S28, S31, S38, S110–S114) · **Status:** draft

## Scope
**In:** the shared form field patterns (`.field`+label+`.input`, selects, segmented radios `.seg`, checkboxes `.radio`, service chips, required marking, help text, inline validation per A18 §5) and the wizard framework (numbered clickable step rail `.br-steps`/`.br-step`, Back/Continue action row, final confirm-with-✓ + toast, transactional commit). Guided-page vs modal placement per IS-1 / 04-docs/README §Interactions.
**Out:** every wizard's actual steps/fields/writes (owned by consuming modules — e.g. Run Bills S31 is billing's), the toast component itself (EP-SHL-04), validation *rules* beyond presentation (consuming modules), any money math.

## Capability matrix (list screens only — B9 conformance)
N/A — no list screens. Wizards embedding tables (e.g. S31.2/S31.3 case tables) consume EP-SHL-02 inside their steps; those rows are declared by the billing epic.

## Stories

---
id: US-SHL-009
epic: EP-SHL-03
module: platform-shell
screens: [S12, S13, S16, S22, S114]
wave: 0
status: draft
blocked_by: []
depends_on: []
journeys: []
rules: [BR-SHL-017]
golden_tests: []
finance_calc: none
---
### US-SHL-009 — Form field patterns & inline validation

**1 · Details** — As a staff user filling any form (quick modals like Record payment S22, full-page forms like New Charge Code S12 / New Tax-Fee S13 / Add Premises & Unit S16, onboarding S114), I want consistent field composition and inline validation, so that errors are caught where they happen and every form feels like the same product. Composition from A12 components: `.field` wrapper + label + `.input`/select/textarea, `.seg` segmented radios, `.radio` checkboxes, service chips. Validation presentation per A18 §5: offending input gets danger border, 12px danger message directly under the field; submit stays enabled, re-validates on click, scrolls to the first error; >3 errors adds the summary line "Fix N fields to continue." Money/quantity inputs render tabular numerals (A12) and never accept float ambiguity — raw strings go to the server, which owns parsing (CLAUDE.md rule 2). Consumption values are always captured **with an explicit unit** control beside the quantity (CLAUDE.md rule 3).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| BR-SHL-017 | Every form in the app composes from the shared field kit; validation errors render inline per field (never a single top alert alone); submit re-validates and scrolls to the first error; >3 errors shows "Fix N fields to continue."; required fields are visibly marked; labels are programmatically associated with inputs and errors announced to assistive tech (IS-10). | CONFIRMED — A18 §5, A12 components, IS-10 (required-marking convention PROPOSED — not shown in prototype) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | In Record payment (S22), submit with amount `0` | Amount input gets danger border + "Amount must be greater than 0." under the field (A18 §5 example copy); modal stays open; nothing posted |
| TC-2 | Submit a form with 4 invalid fields | All four show inline errors; summary "Fix 4 fields to continue." renders above the actions; viewport scrolls to the first error |
| TC-3 | Fix the errors and resubmit | Errors clear per-field as they become valid on re-validation; submit succeeds |
| TC-4 (negative) | Submit with amount `12.3.4` (malformed) | Inline error on the field; the raw string is never coerced client-side into a float and never sent as a number |
| TC-5 | Keyboard-only: Tab through S12 New Charge Code | Every input reachable in order; labels announced; error text read by screen reader on failed submit (aria association) |
| TC-6 | A consumption quantity field renders (e.g. in S16 meter assignment) | A unit control (from the tenant's UoM reference data) sits beside it; quantity cannot be submitted without a unit |

**4 · Test Data** — S22 Record payment for A-10432: amounts `0` (TC-1), `12.3.4` (TC-4), `247.30` (valid). S12 New Charge Code: code `LATE`, name `Late payment fee`, blank required fields for TC-2 (code, name, GL account, amount type). S16 quantity `1240` with unit `kWh` / missing unit for TC-6.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Field kit components | all forms | A12 §Components (`.field`, `.input`, `.seg`, `.radio`) | none (presentation) | — | computed-display | per A12 tokens; radii 0px |
| Inline error message | all forms | A18 §5 | none | text, 12px danger-700 | computed-display | directly under the offending field |
| Error summary line | forms with >3 errors | A18 §5 | none | text | computed-display | "Fix N fields to continue." |
| Money amount input (pattern) | money forms | A12 (tnum), CLAUDE.md rule 2 | consuming module's NUMERIC(18,6) column (server-parsed) | decimal string | user-input | server owns parsing; client sends raw string |
| Consumption quantity + unit (pattern) | metering forms | CLAUDE.md rule 3, A2 | consuming module's quantity + `unit` columns | decimal + UoM code | user-input | unit mandatory with quantity |

**6 · Acceptance** — Given the Record payment modal is open for A-10432, When Jordan submits amount 0, Then the field shows the A18 §5 inline error and nothing is posted; When a form has 4 invalid fields, Then all four error inline, the summary line shows, and focus/scroll lands on the first error; And every field pattern passes keyboard/aria checks per IS-10.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-SHL-010
epic: EP-SHL-03
module: platform-shell
screens: [S10, S18, S23, S28, S31, S38]
wave: 0
status: draft
blocked_by: []
depends_on: [US-SHL-009, US-SHL-011, US-SHL-012]
journeys: []
rules: [BR-SHL-018, BR-SHL-019]
golden_tests: []
finance_calc: none
---
### US-SHL-010 — Wizard framework: step rail, Back/Continue, confirm & toast

**1 · Details** — As a staff user running any guided flow (New Plan S10, New Account S18, Change Plan S23, Read upload S28, Run Bills S31, Bank import S38, onboarding S110–S114), I want a shared wizard frame — numbered step rail, clickable completed steps, Back/Continue, a final explicit confirm — so that long flows are steerable and commits are deliberate. Per 04-docs/README §Interactions: numbered step rail; **steps are clickable to jump back**; Back/Continue in a right-aligned action row; final step has a confirm/commit button **with a ✓** that fires a toast. Wizard step lives in the URL (`?step=`, A9 routing model). Commits are transactional and the commit button shows the A18 §3 working state (disabled + "Working…") — used by billing run, import, reconcile. Below 1024px the rail scrolls horizontally (A12). The wizard frame owns navigation/validation orchestration; each consuming wizard declares its steps, per-step validation, and commit handler.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| BR-SHL-018 | Rail semantics: steps are numbered; completed steps are clickable to jump **back**; forward movement only via Continue after the current step validates (forward-jumping past unvisited steps is not possible); the current step is visually indicated; entered values are retained when jumping back and returning forward. | CONFIRMED — 04-docs/README §Interactions ("steps are clickable to jump back"), S110–S114 addendum ("clickable progress rail", Review's per-block Edit links); value retention PROPOSED (derived — Review step re-shows earlier answers) |
| BR-SHL-019 | Commit semantics: the final step's confirm button carries a ✓ label (e.g. "Create utility & go live ✓" per A13); the commit is a single transactional call; on submit the button disables and shows "Working…" (A18 §3) making double-clicks harmless; success fires the flow's toast and routes to the declared exit screen; failure renders A18 §4 (failed-with-retry, partial-success counts where the operation reports them) with entered state preserved. | CONFIRMED — 04-docs/README §Interactions, A13 (✓ copy), A18 §3–4; single-flight guard derived from CLAUDE.md idempotency posture |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | In New Account (S18), complete steps 1–2, then click step 1 in the rail | Jumps back; step-1 values still populated; Continue returns to step 2 with its values intact |
| TC-2 | On step 1, click step 3 in the rail (not yet reached) | No navigation — forward jump blocked until Continue validates each step |
| TC-3 | Click Continue with a required field empty | Stays on the step; inline errors per US-SHL-009; rail state unchanged |
| TC-4 | Final step: click "Create account ✓" | Button disables + "Working…"; on success a toast fires and the app routes to the account detail (declared exit) |
| TC-5 (negative) | Double-click the confirm button | Exactly one commit request is sent (single-flight); no duplicate record |
| TC-6 (negative) | Commit fails server-side (500) | A18 §4 failed card with Retry; wizard state and entered values preserved; Retry re-submits |
| TC-7 | View a 5-step wizard at 1000px width | Step rail scrolls horizontally; no wrap or page overflow (A12 breakpoints) |

**4 · Test Data** — S18 New Account: customer "Maria Delgado", maria.delgado@gmail.com, +1 (208) 555-0177; step 3 picks premises "Cedar Ridge Apartments" / Unit 3B (plan already attached — displayed, not re-selected, per 04-docs/README §Screens 8). Commit toast: account-created confirmation. Failure injection: 500 on POST, then success on retry.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Wizard step | all wizards | A9 routing model (`?step=`) | none (URL state) | int | system-derived | clamped to reached steps (BR-SHL-018) |
| Step rail state (completed/current/upcoming) | all wizards | 04-docs/README §Interactions, A12 `.br-steps` | none | — | computed-display | back-clickable only when completed |
| Confirm button working state | final steps | A18 §3 | none | — | computed-display | disabled + "Working…" while in flight |
| Wizard payload (pattern) | per wizard | consuming module's spec | consuming module's tables via its service (transactional) | — | user-input | committed once, atomically |

**6 · Acceptance** — Given Jordan is on step 3 of New Account with steps 1–2 complete, When she clicks step 1, edits, and continues forward, Then all values persist; When she confirms on the final step, Then exactly one transactional commit occurs, the ✓ button shows "Working…" while in flight, a toast confirms success, and the app lands on the declared exit screen — with a failed commit leaving her data intact behind a Retry.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

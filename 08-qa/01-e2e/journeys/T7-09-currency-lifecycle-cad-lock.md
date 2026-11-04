# T7-09 — Currency lifecycle: fresh tenant picks CAD, formats flow, first financial record locks it

---
id: T7-09
tier: 7
knob: tenant.currency (unset → CAD → LOCKED)
rules: [BR-TEN-042, BR-TEN-021, BR-TEN-016, IS-8, NFR-22]
stories: [US-TEN-001, US-TEN-006, US-BIL-005]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** The POSITIVE currency path T5-03 points at: a fresh tenant chooses its ONE currency from the seed list while it still can, every screen and document formats accordingly (IS-8), and the FIRST financial record arms the lock (BR-TEN-042) — after which the only ratified door is "you chose at onboarding." The lock-arming moment itself is the thing under test: mutable before, immutable after, with nothing restated in between.

**Fixture.** Fresh tenant maple-creek (Maple Creek Utilities, Saskatchewan), provisioned via US-TEN-001, timezone America/Regina · fixture rates cloned from the Brazos Bend flat plan so money-triples apply · zero financial records at start · System Admin Joel Tremblay.

| # | Actor + action | Expected outcome (contract) | Downstream assertions (upstream/downstream) | Rule |
|---|---|---|---|---|
| 1 | Post-provisioning, Joel opens S8 Regional → Currency | Seed list offered: USD/CAD/MXN/EUR/GBP (full ISO list behind); control is ENABLED — no financial record exists yet | Checklist (US-TEN-003) surfaces regional setup; tenant row currency defaults from provisioning seed | BR-TEN-042 |
| 2 | Joel sets currency CAD; then (still pre-financials) flips CAD→USD→CAD to prove mutability | Each save succeeds → toast → audit row with before/after (T5-03 step 4 contrast case, exercised here as the positive) | Three `tenant settings` audit rows; explicit forward-only warning copy appears once financials would exist (BR-TEN-021) | BR-TEN-042 · BR-TEN-016 |
| 3 | Screens render money entry/display under CAD per Regional settings | IS-8: currency formatting flows from tenant Regional settings; stored amounts remain NUMERIC(18,6) + CHAR(3)='CAD' on new config rows (plan rates entered in CAD) | No format transform ever stored; display-time only (BR-TEN-020) | IS-8 · BR-TEN-020 |
| 4 | First bill run issues BL-2608-0001 — total 97.41 CAD (money-triples `flat,cycle,full`: 89.00 + 8.41) | THE ARMING EVENT: first financial record (issued invoice, append-only set DB-4) exists → currency lock engages from this commit | Invoice + lines carry CHAR(3)='CAD'; balanced posting hands off; delivery queues | BR-TEN-042 · BR-BIL-005 fixture |
| 5 | Joel attempts CAD→USD (UI, then `PATCH /api/tenant/settings`) | UI control now disabled-with-reason naming the lock + the arming record; API refused 409/422 class — the full T5-03 refusal, one commit after arming | Tenant currency still CAD; zero money rows changed; no audit row for the non-executed change | BR-TEN-042 |
| 6 | INVARIANCE — re-read BL-2608-0001, the posting, and the settings history after the refused attempts | Bill renders 97.41 CAD exactly as issued; ledger balanced and unchanged; the pre-lock USD/CAD flips restated nothing (no financial rows existed then; none touched now) | Historical documents never restate on settings change | NFR-22 · BR-TEN-020 · BR-TEN-021 |

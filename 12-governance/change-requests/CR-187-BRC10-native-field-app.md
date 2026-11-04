# CR-187-BRC10 · The field technician app becomes a native app (React Native), in `field-app/`

**Raised:** 2026-10-21 by the Product Owner, in chat, from the *SMART360 Next Field App* design canvas (11 pages, 193 boards).

**Requester's words (verbatim):** *"we are going to set aseperate folder for this … we are going to code this app in react native; we will have to create seperate react native UI Componants"*, then, to the twelve-conflict table, *"this is correct and i want to handle it as per your suggestion"*, to the folder layout *"This is correct"*, to the documentation map *"this is correct ; please go ahead update this details in repo"*, and *"As per Work to be done -page in artifacts complete phase 0"*.

**Rulings:** decision log 2026-10-21 — *"The native field app (React Native) lives in this repo, in its own folder: twelve conflicts"* · *"The native field app's folder is `field-app/`"* · *"Where the field-app design lives in the repo"* · *"Field-app write-up: on the payments branch, all of it now"* · *"Field app Phase 0"*.

## 1 · Classification

A **change**. It reverses a CONFIRMED rule: **BR-WRK-045** (CONFIRMED 2026-09-05), *"The phone is a WEB APP — installable, offline-first — not a native shell."* That is design decision **AD-01**, which states the supersession rather than assuming it (Phase 0 task T-02).

## 2 · What is reversed, quoted

| Signed statement | Supersedes chain | Now |
|---|---|---|
| BR-WRK-045: *"The phone is a WEB APP — installable, offline-first — not a native shell. One codebase, the staff app's furniture, its own route family under `/{tenant}/work/mobile/`."* | decision log 2026-09-03 → CONFIRMED 2026-09-05 (`CR-070` wave J) → **SUPERSEDED 2026-10-21 by this CR** | The phone is a **cross-platform native app (React Native)**, one codebase shipped to the Apple and Google stores, offline-first. Not a PWA, not a WebView shell. |
| BR-WRK-045's stated cost: *"no background push while the app is closed on some phones"* | same | **Retired with it.** The reason for the change: iPhone web push has no custom sound and Safari has no vibration API, so an emergency alert would be silent on half the fleet (requirement 13). |

**What does NOT change:** `06-backend/apps/work/` and its sync contract (accepted / duplicate / refused), the server-side safety re-derivation, the push job, the audit trail (AD-02). The web field app at `07-frontend/src/features/work/mobile/` stays live until T-72 decides retire or fallback.

## 3 · Impact

| Surface | Effect |
|---|---|
| Code | New top-level `field-app/` (own `package.json`, lockfile, Expo/EAS build); `shared/tokens.ts`; new endpoints in `work`, `metering`, `identity` (device sign-in), `payments` seam reads, `assets` documents. None built yet. |
| Rules | `BR-FLD-*` in `04-docs/05-modules/18-field-app/02-business-rules.md`; BR-WRK-045 SUPERSEDED; B14 rule 45 (native type ramp, touch standard). |
| Decisions | ADR-006 to ADR-029, one per design decision (AD-01 to AD-24 — the design page grew from sixteen to twenty-four). |
| Open questions | `OQ-272` (a) answered — Archivo; new `OQ-FLD-*` minted from the design's open items. |
| Gates | `10-scripts/gates/common.py` learns `field-app/src`; `G35` and `allocate.py version` learn `field-app/package.json`. |
| i18n | Field words under `field.*` in the 11 catalogues. |
| Versioning | One product version; the app carries its own store build number. |
| Lanes building now | The CR-186 payment follow-ups on this branch — no overlap (payments vs. docs). |

## 4 · Tasks

The design's own plan, `04-docs/05-modules/18-field-app/10-execution-plan.md` (Phases 0–15, T-01 onward).

| Phase 0 task | State |
|---|---|
| T-01 Apple Critical Alerts entitlement | **DONE** — PO, 2026-10-21: *"we have taken this permission"* |
| T-02 This CR; BR-WRK-045 superseded | **DONE** 2026-10-21 |
| T-03 Close `OQ-272` — ratify Archivo | **DONE for (a)** 2026-10-21; (b) web self-hosting stays open, never asked |
| T-04 Native type ramp + touch standard into the UI standard | **DONE** — B14 rule 45 |
| T-05 Every ruling of the design conversation into the decision log | **DONE** — decision log 2026-10-21 *"Field app Phase 0 (T-05)"*: 58 PO rulings and 49 derived judgments, verbatim |

## 5 · Version and rollback

Documentation and governance only in this step; no build changes, so no version bump on its own (it ships in the next release cut on this branch). Rollback: revert the commit; BR-WRK-045 returns to CONFIRMED.

## 6 · Status

**ACTIVE** — Phase 0 complete; the documentation write-up (T-61 to T-71) follows on this branch.

# tenancy — Flows & States

> Fleshed out 2026-08-09 from BR-TEN-001..043, EP-TEN-03/05/06/07/08, the A1 addendum (S110–S114, 5-step onboarding) and the tenant-provisioning runbook (04-docs/08-runbooks). Screens: S1 Pricing · S2 Welcome · S110–S114 onboarding · S8 Settings (Company / Services & UoM / Reference data / Numbering). Blanket law over every flow below: **config-forward (BR-TEN-043)** — the value in force when an event occurs governs it; no retroactive re-evaluation, no mid-flight re-timing.

## 1. Onboarding wizard S110–S114 (A1 addendum r8; rail conforms to BR-SHL-018)

```
S1 Pricing → S2 Welcome gateway → Create your utility
  S110 1·Your utility   name (only required field) · web address (live availability check, advisory — BR-TEN-011) · country/state · services billed
  S111 2·How you bill   rate style / cycle / bill-on day / tax region / currency / load-reference-data toggle — ALL defaulted, "Skip — use defaults"
  S112 3·Plan & setup   subscription tier (Growth pre-selected) + implementation package; connection-range picker ADVISORY, never enforced (BR-TEN-002)
  S113 4·Review         read-only summary, per-block Edit links, due-today / then-monthly panel
  S114 5·Create login   owner name/email/password/mobile + terms → "Create utility & go live" → provisioning (§2)
```
No card at signup (BR-TEN-014). Subscription/implementation invoicing = S107–S109, B10 — never mixed with customer bills.

## 2. Provisioning transaction (US-TEN-001/004, BR-TEN-001/010/011/013/014/016; runbook)

```
S114 commit → ONE atomic transaction (BR-TEN-010):
  tenants row (subdomain per BR-TEN-011: lowercase DNS label 3–63, reserved names blocked, re-checked at commit)
  + owner user + System Admin membership (via identity service — BR-TEN-013)
  + subscriptions status=trial, trial_ends_at = provisioned_at + 14 d (BR-TEN-014)
  + tenant_services per selected service + reference seed if toggled (§3)
  → RLS-context verification query (runbook step 4) → audit rows tenant.provisioned / reference.seeded (BR-TEN-016)
  → owner signed in → post-signup checklist (§4)
IDEMPOTENT on subdomain natural key: replay returns the EXISTING tenant, never a duplicate (BR-TEN-010)
FAILURE: whole transaction rolls back — no half-seeded tenant goes active (BR-TEN-001); tenant flagged failed + support alert
  (runbook); audit tenant.provision_failed (no PII); retry succeeds with no manual cleanup (US-TEN-004)
```
Subscription states: `trial → active` per A5 (past_due/canceled: no ratified flow — A5 UNKNOWN, B10 scope).

## 3. Reference-data seeding (US-TEN-002, BR-TEN-012/013)

`S111 toggle ON → copy versioned platform fixtures → per-list idempotent upsert by code → seed-run record per list; tenant-touched rows NEVER overwritten by later fixture versions (BR-TEN-012); cross-module lists written only via owning-module service functions (BR-TEN-013/031); toggle OFF → empty lists with valid A18 empty states`.

## 4. Post-signup checklist (US-TEN-003, BR-TEN-015/016)

`auto after S114 → items computed from LIVE data (never a stored to-do); manual mark-done for advisory items (audited); "Finish later" dismisses but checklist stays reachable until complete; items deep-link to Settings tabs (Company gaps: legal name, EIN, mailing address, remit-to…)`. Screen ID = **S62** (OQ-034 CLOSED, PO R6).

## 5. Settings save flow — every S8 tab (BR-TEN-024/016)

`edits stage client-side → Save commits the whole tab atomically with ONE audit_log row (before/after — BR-TEN-016) → Discard reverts all → navigating away with unsaved changes prompts (BR-TEN-024)`.

## 6. Company identity stamping (US-TEN-005, BR-TEN-017/018/019)

`edit identity/brand/remittance → values stamped onto documents AT ISSUE TIME → future documents only; issued documents NEVER re-rendered (BR-TEN-017)`. EIN format-only 9 digits (BR-TEN-018); logo ~~SVG/PNG ≤2 MB, SVG sanitized + rasterized for PDF~~ PNG/JPG ≤2 MB, SVG refused (SUPERSEDED 2026-10-27, DEF-TEN-10618) (BR-TEN-019).

## 7. Regional & format changes (US-TEN-006, BR-TEN-020)

Display-time transforms ONLY: storage stays UTC + NUMERIC(18,6) + CHAR(3); changing formats re-renders screens/future documents, never restates historical bills or stored values (BR-TEN-020).

**Money precision (BR-TEN-080, PO 2026-08-12):** the SCREEN shows **2** decimals through one formatter, the API serves **4** (a tax line computing to 8.2985 travels as 8.2985 and renders **$8.30**), and STORAGE stays `NUMERIC(18,6)` — unchanged, no re-sign. The UI showing 4 decimals today is **DEF-088**.
**A typed date (BR-TEN-081, PO 2026-08-12):** resolves to **midnight in the utility's own timezone** — a Houston clerk (UTC−5 in August) entering **22 August** stores **22 Aug 00:00 Central**. ⚠ **The timezone setting this depends on is not on Company settings yet (DEF-082), so the rule cannot be honoured until that field ships.**

## 8. Currency state machine (BR-TEN-042/021)

```
UNLOCKED (one currency per tenant, seed USD/CAD/MXN/EUR/GBP, full ISO behind)
  ──(first financial record exists — INCLUDING A DRAFT BILL)──→ LOCKED (BR-TEN-042 — no further change)
  ←──(that draft is deleted, and nothing else financial exists)── the lock RELEASES
pre-lock change: forward-only with explicit warning; issued records keep their stored CHAR(3) (BR-TEN-021)
```
**Amended 2026-08-12 (PO, OQ-181): _"currency locked"_ — a DRAFT bill arms the lock. ⚠ This OVERTURNS the drafts-do-not-lock behaviour that shipped on 2026-08-11.** A draft already carries amounts stamped USD, so moving the currency under it leaves the run's figures and the setting disagreeing until somebody notices. The probe is a live existence question, **so deleting the draft releases the lock again** — a run abandoned before issue does not permanently freeze a tenant that is still setting itself up. The hole this closes is **DEF-075**: the seam polls billing AND payments and only payments had authored the probe, so a tenant holding issued bill **BL-2606-000001, 108.88 USD** re-denominated to CAD at **200 OK**.

## 9. Fiscal period flow (BR-TEN-022/023/038)

```
fiscal settings (FY start, method, close cadence, close-by day) → periods DERIVED, current-period card computed never stored (BR-TEN-022)
period: OPEN → CLOSED (close cadence; "lock periods once closed" toggle)
  money event dated into a CLOSED period → AUTO-POSTS to the earliest OPEN period + audit note (BR-TEN-038/023 — enforcement in the ledger posting service 🔒)
  CLOSED → reopened: System Admin only, audit-logged (BR-TEN-038)
```

## 10. Reference-list entry lifecycle (US-TEN-009..011, BR-TEN-036/029/030/034/031)

```
SEEDED (platform defaults, is_system — deactivatable, never deletable) → tenant EXTENDS/edits (BR-TEN-036)
ACTIVE → DEACTIVATED (excluded from new-record pickers; existing records keep rendering; reactivation allowed — BR-TEN-029)
DELETE: Used-by = 0 → hard delete after confirm | Used-by > 0 → blocked server-side, deactivate only (🔒 audit-lock, BR-TEN-034)
code unique per list per tenant (case-insensitive) and IMMUTABLE once Used-by > 0 (BR-TEN-030); Used-by/card counts computed live (BR-TEN-029)
content + validation belong to owning modules; writes via their service functions (BR-TEN-031)
```
List set incl. the ratified additions: S63 holiday calendar · S64 read validation & estimation · S65 account types · S66 billing defaults (BR-TEN-039) · S69–S71 + 8 upgrades (BR-TEN-041). Tax jurisdictions tenant-entered (BR-TEN-037). Template cards navigation-only → Settings → Templates (BR-TEN-033/040).

## 11. Services & UoM (US-TEN-007/008, BR-TEN-025..027)

`service types = closed platform enum, tenants toggle only (BR-TEN-025)` · `enable → row on (soft state)` · `disable GUARDED: blocked while active service agreements or rate schedules reference it (counts shown); soft — row retained, disabled services vanish from new-record pickers, history keeps rendering (BR-TEN-026)` · `per-service UoM change FORWARD-ONLY: new records get the new unit; historical reads/lines keep their stored explicit unit, never converted (BR-TEN-027)`.

## 12. Number allocation (US-TEN-012, BR-TEN-035)

`format = literal prefix + {YYYY}/{YY}/{MM}/{DD} + exactly one zero-padded sequence token (per-series tenant-editable) → allocation INSIDE the issuing transaction from a per-tenant per-series monotonic counter → gaps ok, never reused → format changes future-only, issued numbers never renumbered → next-number edits forward-only (≥ current)`.

Journeys: J1 (signup → provisioned tenant → checklist) · J5 step 0 context (fiscal periods).

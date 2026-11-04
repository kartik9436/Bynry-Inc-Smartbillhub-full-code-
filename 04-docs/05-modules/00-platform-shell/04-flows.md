# platform-shell — Flows & States

> Fleshed out 2026-08-09 from the ratified rules BR-SHL-001..031 + B9 (IS-1…IS-11). The shell owns no domain state machines — its flows are the interaction pipelines every module conforms to (conformance declared per screen via a B9 capability-matrix row, BR-SHL-010). Screens: shell chrome hosting S7–S49+ (A1); public S1/S2 are the sign-out exit only.

## 1. Shell mount & navigation (US-SHL-001/002, BR-SHL-001..004)

```
authenticated route → read user_preferences `shell.sidebar_collapsed` (BR-SHL-002 — applied BEFORE first paint)
  → render sidebar 240/64px, canonical order Dashboard · Plans & Rates · Premises · Assets · Accounts · Reads · Billing · Payments · Work · Finance · **Runbooks** · Reports · Settings — THIRTEEN items, Premises BEFORE Assets, Work before Finance, Runbooks between Finance and Reports (BR-SHL-001 as amended 2026-08-16 CR-003 and 2026-09-06 CR-075; ⚠ this line read *twelve* and omitted Runbooks until 2026-09-06. Work is a real screen since CR-070 wave A; **Runbooks → not-built-yet** until RBS-001 lands in CR-075 wave D)
  → role-inaccessible items HIDDEN (BR-SHL-003); direct URL to a hidden module → A18 §6 block, no data behind
  → route change → breadcrumb `Module › Sub-context` (leaf = human identifier, never UUID; tab title mirrors leaf — BR-SHL-004)
  → toggle → persisted per (user, tenant) server-side (BR-SHL-002/027)
```

## 2. Global search (US-SHL-003, BR-SHL-005/006/028)

`focus topbar search → IS-3 mechanics (300 ms debounce, min 2 chars) → tenant-scoped query under app.tenant_id + RLS FORCE (BR-SHL-006) → popover grouped into the FIFTEEN groups of BR-SHL-005 as amended 2026-09-05 (`CR-073`) — premises · units · assets · master accounts · accounts · customers · bills · payments · service requests · work orders · work order templates · parts · workforce · plans · charge codes — ≤5 rows/group, prefix-then-recency rank (BR-SHL-005) → select = deep-link | per-group "View all" opens the module list with q applied → zero results = A18 §2`. Role-invisible entity groups are omitted (BR-SHL-006). `GET /search` = proposed A11 addition (BR-SHL-005).

## 3. Notifications bell (US-SHL-004, BR-SHL-007/026)

Event catalog CONFIRMED (BR-SHL-026): billing run completed/failed · payment failures · approvals waiting · import results with exception counts · integration broken — "the bell tells the user where attention is required"; tax-deadline/disconnect-today/account-activity excluded. Surface per BR-SHL-007: unread badge (9+) → popover newest-first, tenant-scoped → item deep-links to subject; read actions clear. Read-state persistence (per-user vs per-tenant), storage table and retention: (no ratified flow — story-level only, US-SHL-004).

## 4. User menu & sign-out (US-SHL-005, BR-SHL-008/009)

`sidebar footer block (initials · name · current-tenant role) → S48 upward menu (v1 items per BR-IDN-028: My profile / Change password / Sign out) → modals per A1 addendum` · `Sign out → session ended (identity, BR-IDN-007) → tenant context + client caches cleared → public Pricing/sign-in (BR-SHL-009); authed deep-links thereafter redirect to sign-in`.

## 5. Table interaction pipeline (US-SHL-006..008, BR-SHL-010..015, IS-2..6)

```
screen declares its capability-matrix row (BR-SHL-010 — undeclared capabilities don't render)
  → framework renders: server-side pagination 25/page (IS-2) · declared-field search (IS-3) · AND-combined filter chips (IS-4)
  → URL state grammar q/sort/dir/page/per/f.‹name› — shareable; invalid values clamp, never error (BR-SHL-011)
  → column chooser (IS-5): per (user, tenant, screen) in user_preferences, identity column unhideable (BR-SHL-013); SERVER-side always (BR-SHL-027)
  → framework owns skeleton/zero-results/failed states; screen supplies empty-list copy only; no empty header ever (BR-SHL-012)
SELECTION: header checkbox = current page → survives paging within the SAME query state → q/filter change CLEARS it (BR-SHL-014)
  → bulk bar: count + running $ total (display-only 2 dp over server amounts — BR-SHL-015)
  → destructive/money action: modal → explicit confirm → toast → audit_log (IS-6)
```

## 6. CSV export (US-SHL-008, BR-SHL-016/029, IS-9)

`export action → server-side stream under RLS (IS-9: current filters + visible columns, money 2dp, UTF-8, filename ‹screen›-‹tenant›-‹YYYYMMDD›.csv) → >50,000 rows REJECTED (BR-SHL-029, cap revisitable) → money-table exports write audit_log (BR-SHL-016)`. Report downloads (CSV always / PDF where layout matters / no XLSX v1, 3-day retention) = IS-11, owned by reports (BR-REP rules).

## 7. Form & wizard pipeline (US-SHL-009/010, BR-SHL-017..019)

```
form: shared field kit → inline per-field errors, never top-alert alone → submit re-validates + scrolls to first error; >3 errors add a summary line (BR-SHL-017, A18 §5)
wizard: numbered rail — completed steps back-clickable, forward ONLY via validated Continue, values retained on back-jump (BR-SHL-018)
commit: ✓ confirm → ONE transactional call, button disabled + "Working…" (double-click safe)
  → success: toast + exit route | failure: A18 §4 failed-with-retry, state preserved (BR-SHL-019)
```

## 8. States & feedback (US-SHL-011/012, BR-SHL-020..022)

Six A18 patterns exist ONCE as shared components (empty · zero-results · skeleton · failed-with-retry · inline validation · permission denied); screens fill slots only (BR-SHL-020). Toasts: bottom-center, ~2.5 s, aria-live, never the sole record (BR-SHL-021); queue FIFO one-visible; bulk flows fire ONE summary toast, not N (BR-SHL-022).

## 9. i18n & preference storage (US-SHL-013, BR-SHL-023/024/027/030)

`string → ICU catalog; adding a language = adding a catalog, never code (BR-SHL-030 — data-driven; seeded language set per BR-TEN-042) → resolution: per-user profile override → tenant default language → formats via ONE formatting service fed by tenant Regional settings (IS-8, BR-SHL-023); consumption always with explicit unit; money 2 dp at display only`. Preference write: `key → user_preferences (tenant, user, key), jsonb ≤32 KB, last-write-wins, removed with membership, RLS like every tenant table (BR-SHL-024); never localStorage-only (BR-SHL-027)`.

## 10. Document storage (BR-SHL-031 — TD-15/NFR-33..36 confirmed)

```
upload (v1 staff-mediated) → allowlist PDF/PNG/JPG/CSV + 10 MB tenant-config cap
  (NO malware scan — the scan step is SUPERSEDED (PO 2026-09-22 / 2026-09-23 → no malware scan on upload), DEF-SHL-6347)
  → object storage with tenant-prefix isolation
two classes: GENERATED (re-render via template pinning — never stored stale) | STORED ARTIFACTS (e-signed docs, uploads, import files)
legal class: WRITE-ONCE, 7-year retention
```

## 11. RBAC gating (US-SHL-014, BR-SHL-003/025)

`server-provided permission set read once at shell mount → nav items hidden (BR-SHL-003) · visible-but-forbidden actions render disabled-with-reason (A18 §6 voice, focusable — BR-SHL-025) → server independently enforces every mutating call (403, no write) — UI gating is convenience only (IS-6, A4)`.

Conformance journeys: every module epic's capability row (B9) + A18 states — no shell-owned journey files.

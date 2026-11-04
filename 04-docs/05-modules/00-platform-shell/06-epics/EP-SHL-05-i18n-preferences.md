# EP-SHL-05 — i18n readiness & user preferences

**Module:** platform-shell · **Wave:** W0 · **Screens:** no own S-number — string/format rendering applies everywhere; Regional settings authored in Settings → Company (S8); preferences consumed by shell chrome + all list screens · **Status:** draft

## Scope
**In:** externalization of all UI strings as ICU MessageFormat (en-US ships; Spanish v1.1 shown disabled per IS-8), rendering of dates/numbers/currency per the tenant's Regional settings, and the `user_preferences` storage service (the module's **only** owned table — PROPOSED-SCHEMA, absent from B2) backing sidebar state (US-SHL-001) and column sets (US-SHL-007).
**Out:** the Regional settings **editor** (Settings → Company — tenancy module owns the screen and its tables), translation authoring/locale files beyond en-US, tenant-authored template content (already the tenant's own language, IS-8), notification templates (notifications module).

## Capability matrix (list screens only — B9 conformance)
N/A — no list screens.

## Stories

---
id: US-SHL-013
epic: EP-SHL-05
module: platform-shell
screens: [S8, S17, S30, S36]
wave: 0
status: draft
blocked_by: []
depends_on: [US-TEN-006]
journeys: []
rules: [BR-SHL-023, BR-SHL-024]
golden_tests: []
finance_calc: none
---
### US-SHL-013 — String externalization, regional format rendering & preference storage

**1 · Details** — As the platform (and as every staff user benefiting from it), I want all UI strings externalized in ICU MessageFormat and all dates/numbers/currency rendered per the tenant's Regional settings, plus a small per-user preference store, so that v1 ships English-only but nothing needs rewriting for Spanish in v1.1, tenants in different regions see their own formats, and UI choices (sidebar, columns) follow the user. Per IS-8: strings externalized (ICU), en-US ships, Spanish disabled in the design; formats come from Settings → Company → Regional & Formats (country, timezone, currency, language, date/time/number format, first day of week — A1 Settings addendum), which tenancy owns and this story **consumes read-only**. Consumption values always render with their explicit unit (CLAUDE.md rule 3); money displays at 2 dp only at display time (CLAUDE.md rule 2 — display rounding, no stored rounding). Storage: `user_preferences` — the module's only table, proposed here because B2 lacks it. Entry: shell boot loads the string catalog, tenant formats, and the user's preferences; preference writes happen via a `PUT /me/preferences/‹key›` service (PROPOSED addition to A11). Screens cited: S8 (source of Regional settings), S17/S30/S36 (representative format-rendering consumers).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| BR-SHL-023 | No string literal ships inside a component: every user-facing string lives in the ICU MessageFormat catalog (plural/select where count/gender-like variants exist); en-US is the only v1 locale, Spanish appears disabled where the design shows it; dates, times, numbers, and currency render through a single formatting service fed by the tenant's Regional settings — never `toLocaleString` ad hoc, never a hardcoded format; consumption always renders with its explicit unit; money renders 2 dp at display time only. | CONFIRMED — B9 IS-8, A1 Settings addendum (Regional & Formats), CLAUDE.md rules 2–3 (enforcement-by-lint approach PROPOSED) |
| BR-SHL-024 | `user_preferences` stores **UI preferences only** — never business data, never money, never anything another user needs. One row per (user, tenant, key); dotted-namespace keys ≤128 chars (`shell.*`, `table.*`); jsonb value ≤32 KB; last-write-wins on concurrent writes; unknown keys read as absent (callers fall back to defaults); rows are removed when the tenant membership is removed; tenant-scoped under RLS like every tenant table. | PROPOSED — table absent from B2 (PROPOSED-SCHEMA below); constraints derived from CLAUDE.md tenancy rule 1 and the consuming stories (US-SHL-001, US-SHL-007) |

**PROPOSED-SCHEMA — `user_preferences` (owned by platform-shell; needs B2 ratification + Eng-Lead migration review):**

```sql
CREATE TABLE user_preferences (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  user_id uuid NOT NULL REFERENCES users(id),   -- ⚠ cross-module → identity (B2 §2 review set)
  key text NOT NULL,                            -- dotted namespace, ≤128 chars
  value jsonb NOT NULL,                         -- ≤32 KB, UI preferences only
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, user_id, key)
);
-- RLS: standard tenant policy block per B2 §3 (FORCE).
```

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Silver Creek Regional settings: MM/DD/YYYY, USD, week starts Sunday. Render invoice BL-2608-018410 due date on S30 | "08/25/2026" and "$148.63" (2 dp, tabular numerals); switching the tenant setting to DD/MM/YYYY re-renders "25/08/2026" with no code change |
| TC-2 | ICU plural: S17 footer count with 1 vs 60 accounts | "1 account" / "60 accounts" from one ICU message (`{count, plural, one {# account} other {# accounts}}`) |
| TC-3 | Preference roundtrip: write `shell.sidebar_collapsed = true`, reload | GET returns the value; sidebar honors it (US-SHL-001 TC-2 passes through this service) |
| TC-4 (negative) | Write a 40 KB value to `table.S34.columns` | Rejected (413/422) with a clear error; existing stored value untouched |
| TC-5 (negative) | Extraction lint runs on a component containing a hardcoded user-facing literal | Build/lint fails naming the file — catalog coverage is enforced, not aspirational |
| TC-6 (negative) | Read an unknown key `table.S99.columns` | Returns absent (no error); caller falls back to the screen's default column set |
| TC-7 (isolation) | Alex writes prefs in Silver Creek; automated test attempts to read them under the Harbor Point tenant context, and as Jordan within Silver Creek | Both reads return nothing: rows are invisible cross-tenant (RLS) and are never served for another user_id |
| TC-8 | Language selector wherever design shows it (e.g. Regional settings preview) | "Spanish" renders disabled with a v1.1 note (IS-8) — not hidden, not selectable |

**4 · Test Data** — Silver Creek Regional settings: country US, state ID, timezone America/Boise, currency USD, date MM/DD/YYYY, first day Sunday. Harbor Point: date DD/MM/YYYY (contrast tenant). Preference rows: `(alex, silvercreek, 'shell.sidebar_collapsed', true)`, `(jordan, silvercreek, 'table.S34.columns', ["balance","account_no","name","age","class","last_payment"])`. Oversize payload: 40 KB JSON array for TC-4. ICU message: `{count, plural, one {# account} other {# accounts}}` with counts 1 and 60.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| String catalog entries | all screens | B9 IS-8 (ICU MessageFormat) | none (locale files in repo) | ICU messages | reference-data | en-US complete; lint-enforced coverage |
| Tenant regional formats | all screens (authored S8) | A1 Settings addendum §Company — Regional & Formats | tenancy-owned settings tables (read-only here; column detail in the tenancy epics) | codes (date/number/currency/timezone/first-day) | reference-data | consumed via formatting service only |
| `user_preferences.tenant_id` | — | PROPOSED-SCHEMA (B2 lacks table) | `user_preferences.tenant_id` | uuid | system-derived | FK tenants.id; RLS FORCE |
| `user_preferences.user_id` | — | PROPOSED-SCHEMA | `user_preferences.user_id` | uuid | system-derived | FK users.id (⚠ cross-module → identity) |
| `user_preferences.key` | — | PROPOSED-SCHEMA | `user_preferences.key` | text | system-derived | dotted namespace ≤128 chars; unique per (tenant,user,key) |
| `user_preferences.value` | — | PROPOSED-SCHEMA | `user_preferences.value` | jsonb | user-input | ≤32 KB; UI preferences only |

**6 · Acceptance** — Given the two tenants in §4, When the same invoice-date component renders in each, Then each tenant's configured format appears with zero per-screen format code; When Alex's preferences are written, Then they survive reload, respect the 32 KB cap, and are provably unreadable from any other tenant context or user; And the string-extraction lint blocks any hardcoded user-facing literal from merging.

**7 · Finance Calculation** — N/A (display-time formatting only; no stored value is rounded or computed — B4 owns all money math).

**8 · Open Questions** — None.

---

## Addendum r2 — eleven locales (PO ruling 2026-08-10)

The ratified set was five (`en · es · es-MX · de · hi`, PO LC-1..3 2026-08-08). The PO has expanded it to **eleven**, supplied as a picker mock-up, and ruled **both** surfaces in scope — staff UI *and* customer documents — with all six new languages landing together and machine translation acceptable as a first pass pending human editing.

| Screenshot label | Code | Status |
|---|---|---|
| English (United States) | `en-US` | have, re-tagged from `en` |
| Español (España) | `es-ES` | have, re-tagged from `es` |
| Español (Latinoamérica) | `es-419` | have, **re-tagged from ratified `es-MX`** — PO ruled `es-419` on 2026-08-10 |
| Deutsch (Deutschland) | `de-DE` | have, re-tagged from `de` |
| हिन्दी (भारत) | `hi-IN` | have, re-tagged from `hi` |
| Français (France) | `fr-FR` | **new** |
| Indonesia (Indonesia) | `id-ID` | **new** |
| Italiano (Italia) | `it-IT` | **new** |
| 日本語 (日本) | `ja-JP` | **new** |
| 한국어 (대한민국) | `ko-KR` | **new** |
| Português (Brasil) | `pt-BR` | **new** |

**6 new · 5 re-tagged · 2,063 keys per catalog · 12,378 strings to translate.** None of the eleven is right-to-left, so no bidirectional layout work is implied — the expensive case is absent by luck rather than design, and adding Arabic or Hebrew later would not be a data change.

**The cost that is not a translation cost:** every feature from R2 onward writes its strings into eleven catalogs instead of five. That is a permanent multiplier on every release, not a one-time project.

---
```yaml
id: US-SHL-017
epic: EP-SHL-05
module: platform-shell
screens: [S48]
wave: 2
status: draft
blocked_by: []
depends_on: [US-SHL-011]
journeys: []
rules: [BR-SHL-040, BR-SHL-041]
golden_tests: []
finance_calc: none
```
### US-SHL-017 — Eleven locales, loaded one at a time

**1 · Details** — As a staff user, I want the product in my language without paying to download ten others, so that the app stays fast. The eleven locales come from one registry; each catalog is a separate chunk fetched on demand.

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-SHL-040 | Catalogs load **lazily, one locale at a time**. Today all five are static `import`s compiled into a single bundle: `dist` is 1,546,871 bytes of which **824,000 bytes (53%) is translation JSON** — every user downloads five languages to read one. At eleven that would approach 2 MB of catalogs in a ~2.8 MB bundle. This change is warranted at five and mandatory at eleven | PROPOSED — measured against the R1 build, 2026-08-10 |
| BR-SHL-041 | The eleven codes live in **one registry** that the picker, the tenant default and the per-user override all read. Plural categories come from `Intl.PluralRules`, never hand-written: Japanese and Korean have one plural form, French treats zero as singular, Indonesian has no plural inflection — any hand-rolled `n === 1` is wrong in at least three of the eleven | PROPOSED — extends BR-SHL-030 (data-driven catalogs) to the expanded set |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | Load the app in `en-US` | Only the `en-US` catalog chunk is fetched; no other locale JSON is in the initial bundle |
| TC-2 | Switch to `ja-JP` | The `ja-JP` chunk is fetched once, then cached; the UI re-renders without a full reload |
| TC-3 | Build size after the change | Main bundle drops by ~800 KB; no single locale chunk is in the entry chunk |
| TC-4 (neg) | A locale chunk fails to load (offline) | Falls back to `en-US` with a non-blocking notice; the app does not white-screen |
| TC-5 | Plural rendering in `ja-JP`, `fr-FR`, `id-ID` | Resolved via `Intl.PluralRules`; zero renders as singular in French |
| TC-6 | A key missing from a non-English catalog | Falls back to `en-US` for that key only, not for the page |
| TC-7 (isolation) | Two tenants with different default languages | Each resolves its own default; language is a user/tenant preference and never leaks across tenants |

**4 · Test Data** — All eleven catalogs present, `ja-JP` and `id-ID` deliberately missing three keys each to exercise TC-6.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Locale registry | S48 | A1/BR-SHL-030 as amended | platform constant (eleven codes) | — | reference-data | BCP-47 codes; adding one is a data change (NFR-37) |
| Tenant default language | S6 Settings | BR-TEN-042 | `tenant_settings.default_language` | text | user-input | must be in the registry |
| Per-user override | S48 | BR-SHL-030 | `user_preferences` | jsonb | user-input | must be in the registry |

**6 · Acceptance** — **Given** eleven locales are configured, **when** a user loads the app in English, **then** no other locale's catalog is downloaded; **and when** they switch to Japanese, **then** exactly one additional chunk is fetched and the UI re-renders in Japanese.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
```yaml
id: US-SHL-018
epic: EP-SHL-05
module: platform-shell
screens: [S48, S6]
wave: 2
status: draft
blocked_by: []           # was [OQ-077]; CLOSED 2026-08-10 (→BR-SHL-043). Cleared 2026-08-15 (DEF-104)
depends_on: [US-SHL-017]
journeys: []
rules: [BR-SHL-042, BR-SHL-043]
golden_tests: []
finance_calc: none
```
### US-SHL-018 — Language picker, `es-419` normalisation, and the machine-translation guard

**1 · Details** — As a staff user, I want to pick my language from my profile; and as the platform, I must re-tag the five existing catalogs to their region-qualified codes **before real data exists**, because `accounts.preferred_language` and per-user overrides will hold whichever code we pick.

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-SHL-042 | The ratified `es-MX` becomes **`es-419`** (Spanish, Latin America), and `en`/`es`/`de`/`hi` become `en-US`/`es-ES`/`de-DE`/`hi-IN`. A data migration rewrites every stored value in `tenant_settings.default_language`, `accounts.preferred_language` and `user_preferences`. **This is time-sensitive**: it is a rename of empty columns today and a live-data migration once Spanish-speaking customers are onboarded | CONFIRMED — PO ruling 2026-08-10 ("es-419"), superseding the `es-MX` of PO LC-1..3 2026-08-08 |
| BR-SHL-043 | **Machine translation is permitted for staff-UI catalogs and marked as such.** Each catalog carries a `translation_status` of `human` or `machine_unverified`. Customer-facing document templates are a different matter: TD-16 (5) already forbids machine-translating tenant-authored content, and a machine-translated **disconnection notice, late-fee term or payment-plan agreement** carries legal exposure to the utility's own customers. So platform-seeded template variants in a new language ship marked *unverified* and **cannot be published until a tenant user confirms them** — the block is on first publish, not on authoring | PROPOSED — PO ruling 2026-08-10 ("machine for time being; later I will get it edited by human") + TD-16 (5); the publish gate is the Eng-Lead provision, routed as OQ-077 |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | Open S48 profile | Language picker lists all eleven with native labels exactly as the PO's mock-up (English (United States), Français (France), …) |
| TC-2 | Choose 한국어 | UI switches; the choice persists server-side (BR-SHL-027), not in localStorage |
| TC-3 | Migration over a database holding `es-MX`, `en`, `es`, `de`, `hi` | Rewritten to `es-419`, `en-US`, `es-ES`, `de-DE`, `hi-IN`; row counts unchanged; the migration is idempotent |
| TC-4 (neg) | A stored value not in the registry after migration | Migration fails loudly rather than defaulting silently — an unmapped language is a data question, not a fallback |
| TC-5 | A catalog marked `machine_unverified` | Staff UI renders it normally; the marking is metadata, not a banner on every screen |
| TC-6 (neg) | Publish a machine-translated **customer document** template variant | **RULED — implement it, do NOT stub it (amended 2026-08-15, DEF-104).** OQ-077 CLOSED 2026-08-10 → BR-SHL-043: a customer-facing variant ships `machine_unverified` and **cannot be published until a tenant user confirms**; authoring is not blocked, sending is. The publish branch refuses an unconfirmed variant with its reason. The old wording here asked for `NotImplementedError("OQ-077")`, which any agent following it would now fail G8 on the spot — a stub citing a CLOSED question is stale by definition |
| TC-7 (isolation) | Tenant A sets `ko-KR` as default | Tenant B's default is unaffected; language is per-tenant settings under RLS |

**4 · Test Data** — Pre-migration fixture: 3 tenants (`es-MX`, `en`, `de`), 40 accounts across `en`/`es-MX`, 6 users with overrides. Post-migration expectation: `es-419`, `en-US`, `de-DE` with identical row counts.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Language picker | S48 | PO mock-up 2026-08-10 | `user_preferences` | text | user-input | one of the eleven |
| Tenant default | S6 | BR-TEN-042 | `tenant_settings.default_language` | text | user-input | one of the eleven |
| Account language | S21 | BR-CUS-064 | `accounts.preferred_language` | text | user-input | one of the eleven |
| Catalog translation status | — | GAP | catalog metadata, not tenant data | enum | reference-data | `human` \| `machine_unverified` |

**6 · Acceptance** — **Given** a database holding the five old codes, **when** the migration runs, **then** every stored value is a region-qualified code from the registry, no row is lost, and re-running it changes nothing; **and** the S48 picker offers all eleven in their native labels.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**
| OQ-ID | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-077 | Machine translation is accepted for staff UI. May a **machine-translated customer-facing document** (bill, disconnection notice, payment-plan agreement) be sent to a real customer before human review? Several US states impose statutory language on disconnection notices. Proposed: seeded variants ship `machine_unverified` and a tenant must confirm before first publish | TC-6; the template publish branch | Product Owner + legal | **CLOSED(→BR-SHL-043)** — PO ratified the guard as proposed, 2026-08-10. Mirrored here 2026-08-15 (DEF-104): this cell still read `**OPEN**` five days after the ruling, which is how a story keeps instructing a stub for a question that was answered |

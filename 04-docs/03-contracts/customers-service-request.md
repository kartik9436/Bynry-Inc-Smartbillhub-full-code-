# Contract — the consumer-category vocabulary and the CR-031 service-request tables

**Status: CONTRACT.** These are stable interfaces (see this folder's README). A
change here ripples across FE + BE and needs a ruling, not an edit.

**Sources, in precedence order:** the PO rulings of **2026-08-24** recorded in
`04-docs/05-modules/03-customers/02-business-rules.md` (BR-CUS-090, BR-CUS-091,
BR-CUS-093, BR-CUS-094, BR-CUS-095) → B2 (`../02-decisions/02-database-design-brief.md`)
→ B19 (`../02-decisions/19-cr031-service-request-capture.md`).

---

## 1 · `account_types` — the utility's OWN list, SEEDED with seven and one LEGACY code

> ⚠⚠ **THE SEVEN ARE NO LONGER THE VOCABULARY. THEY ARE THE SEED.**
> **PO ruling 2026-09-17, verbatim: *"utility can get their own account types"***
> — answering a straight either/or (*do utilities get their own account types,
> or do the seven stay the signed vocabulary and the screen simply stops
> pretending they're editable?*) and **superseding `BR-CUS-094`'s PLATFORM
> posture**, which is what the paragraph below describes. `account_types` now
> carries `tenant_id`, RLS `ENABLE`+`FORCE` and a **per-tenant**
> case-insensitive unique code (`customers.0054` / `0055`, `BR-CUS-1079`), and a
> utility adds, renames, deactivates and deletes its own rows on S8 Settings →
> Reference data → Account types.
>
> **WHAT SURVIVES UNCHANGED:** the seven codes and names below, their ORDER,
> `government`'s legacy treatment, and every sentence about what `legacy` means.
> **WHAT CHANGES:** a code is a fact about ONE utility and no longer about the
> install, so two tenants may lawfully hold one code for different things, and
> **no consumer may hardcode this list.** A picker reads the tenant's rows.
>
> ⚠ **SUPERSEDES B2 Addendum r5 #12 [D5]'s FOUR-CODE LIST**
> (`residential / commercial / industrial / government`), which was a **signed**
> vocabulary. Superseded by **BR-CUS-094 (PO 2026-08-24)**, verbatim:
> ***"Expand the signed list to seven"***.
> The superseding ruling also reaches
> `06-backend/apps/customers/migrations/0019_cr031_br_cus_090_093_094_095.py`.
> Migration `0003_seed_account_types.py` is **not edited** — migrations are
> append-only (`.github/workflows/migration-guard.yml`) — so 0019 is its
> successor and carries the same supersedes line in its own docstring.

### The seven a NEW TENANT starts with, in the ruling's own order (which is REQ-03.2's chip order)

| # | `code` | `name` | selectable |
|---|---|---|---|
| 1 | `residential` | Residential | ✅ |
| 2 | `commercial` | Commercial | ✅ |
| 3 | `industrial` | Industrial | ✅ |
| 4 | `agricultural` | Agricultural | ✅ |
| 5 | `institutional` | Institutional | ✅ |
| 6 | `municipal` | Municipal | ✅ |
| 7 | `builder_developer` | Builder or developer | ✅ |
| — | `government` | Government | ⛔ **LEGACY** |

Rows 1–3 were seeded by migration 0003 and rows 4–7 by migration 0019, both
**additively and insert-missing**, into what was then a platform table.
⚠ **SINCE 2026-09-17 THE EIGHT ARE SEEDED PER TENANT** by
`customers.services.ensure_account_types()`, out of the platform fixture
(`account_types` went 4 → 8 at bump `V2.48.0.12`; the four missing rows had been
missing since `BR-CUS-094` and were harmless only while the table was global).
`customers.0054` fanned the existing eight out per tenant and repointed every
`accounts`, `account_subtypes` and `service_requests` FK at **its own tenant's**
row.

The order above is contract and is now a **stored** fact rather than an
iteration order: `account_types.sort_order` carries it as 10..70, `government`
sits at 900, and **a row a tenant ADDS is appended at `max + 10`** — so the drawn
order survives and new rows land behind it in creation order. A picker sorted
alphabetically silently re-orders a screen the PO drew; a picker that iterates
`SEVEN_CATEGORIES` silently DROPS every row the tenant added, which is exactly
what `GET /service-requests/categories` did until `DEF-CUS-5647`.

### What `legacy` means, and what it does NOT mean

`account_types.legacy` is a **new boolean column** (migration 0019, default
`false`), and it is a **third axis**, not a synonym for `active`:

| flag | meaning |
|---|---|
| `active = false` | the code is retired from every surface |
| `legacy = true` | the code is **unselectable on new records and lawful everywhere else** |

**A legacy code is still a valid FK, still filterable, still priceable.** Every
existing account keeps it and bills exactly as it did the day before the ruling.

> ⚠ **`government` IS NOT RE-LABELLED, AND THIS IS THE PART THE RULING SAYS IT
> COULD NOT SETTLE FOR US.** Verbatim: *"Municipal and Institutional are both
> plausible readings of it — a city water department and a state university are
> different things and the stored value cannot tell them apart. So no row is
> re-labelled by guess."* Re-pointing is a **human act per record**. A migration
> that UPDATEs `government` rows to `municipal` is changing what a utility
> charges people, silently.

### Where it is enforced

| surface | behaviour |
|---|---|
| `GET /api/{tenant}/service-requests/categories` | serves `selectable` and `legacy` as two lists. ⚠ **AMENDED 2026-09-17:** `selectable` is now **every active, non-legacy row of THIS tenant's list** in `sort_order`, not the seven read out of a tuple — it silently dropped every row a tenant added (`DEF-CUS-5647`). |
| `service_request_service.set_customer_category` | refuses a legacy code by name — `customers.serviceRequest.categoryIsLegacy`, `BIZ-STATE`. Resolves within the tenant since 2026-09-17. |
| `GET /api/{tenant}/lookups/account_types` (S8 card) | ✅ **CLOSED 2026-09-17.** It publishes `legacy` beside `active`, and the card has full CRUD — `AccountTypeLookupHandler` refused create/update/set_active/delete until that date, with a message key that existed in no catalogue (`DEF-CUS-5647`, `DEF-CUS-5648`). |
| `apps/customers/services.SEED_ACCOUNT_TYPES` + the platform reference fixture | ✅ **CLOSED 2026-09-17.** Both hold the full **eight** (the seven + `government`, seeded `legacy`), behind fixture bump `V2.48.0.12`. ⚠ **The gap stopped being harmless the moment the rows went per-tenant:** while the table was global a fresh seed found all eight already present, and a tenant seeded from a four-entry fixture would have received FOUR types and no Agricultural, Institutional, Municipal or Builder. |

---

## 2 · `service_request_document_requirements` — the BR-CUS-095 checklist

**NEW table** (migration 0019; RLS policy migration 0020). Tenant-scoped.

| column | type | notes |
|---|---|---|
| `id` | uuid7 PK | |
| `tenant_id` | FK → `tenancy.tenant` | RLS `ENABLE` + `FORCE` |
| `request_type` | text | one of `ServiceRequest.JOB_OUTCOMES` — `new_connection · move_in · move_out · transfer · disconnect` |
| `doc_type` | text | one of the **eight designed types** (below) |
| `required` | boolean, default `false` | a `false` row is a tick that was TAKEN BACK — stored, never deleted |
| `updated_by` | FK → `identity.user`, null | who decided |
| `created_at` / `updated_at` | timestamptz | |

Unique: `(tenant, request_type, doc_type)` — `ux_sr_doc_requirements`.

### The eight designed document types (checklist-eligible)

`proof_of_identity` · `proof_of_address_or_occupancy` ·
`tenancy_agreement_or_deed` · `authority_to_act` · `site_plan_or_unit_schedule` ·
`assistance_evidence` · `signed_service_agreement` · `completion_paperwork`

**A ninth value, `other`, is ATTACHABLE and never tickable** — B19 §5 draws it on
REQ-03.4 as `Anything else`, badged *Optional*. Keeping the two vocabularies
apart is what stops a tenant ticking a box no attachment can satisfy.

> ⚠ **THE TABLE SHIPS EMPTY AND MUST STAY THAT WAY UNTIL A HUMAN TICKS A BOX.**
> BR-CUS-095's sharpest clause: *"We ship with nothing ticked, and a utility that
> configures nothing blocks nothing."* **There is no seed, no data migration and
> no fixture** — not even a pre-tick of *proof of identity*, however reasonable
> that looks. The product ships with no opinion about any jurisdiction's law.

**Two gates, unchanged and joined rather than replaced (B19 §5):** attaching
never blocks CREATION; an unverified required document blocks APPROVAL.

Served at `GET|PUT /api/{tenant}/service-request-settings/document-requirements`,
**System Admin only**. The GET returns the whole `5 × 8` grid, ticked or not,
with `configured: false` distinguishing *"nobody has looked"* from *"we said
no"*.

---

## 3 · `service_requests` — the columns the 2026-08-24 rulings add

| column | type | rule |
|---|---|---|
| `fee_quoted` | `NUMERIC(18,4)` null | **BR-CUS-090** — the quote AS IT STOOD when the money was taken (a snapshot, not a live sum) |
| `fee_collected` | `NUMERIC(18,4)` null | what the counter took |
| `fee_currency` | `CHAR(3)` null | CLAUDE.md rule 2 |
| `fee_receipt_no` | text null | **ONE** receipt number, **recorded not allocated** — payments owns the `RCT-` series |
| `fee_collected_at` | timestamptz null | |
| `fee_collected_by` | FK → `identity.user` null | |
| `applicant_name` | text → **NULLABLE** | **BR-CUS-091** — not required on a **staff-raised** request (`channel` ∈ `STAFF_RAISED_CHANNELS`). Still required for an applicant-raised one. `address_as_given` stays required either way. |

`request_no` is unchanged as a column and changed in WHEN it is written:
**BR-CUS-093 allocates it at CREATION**. It stays nullable only for rows that
predate the ruling; nothing back-fills them, because **gaps are normal** and
renumbering would move an identifier somebody has already written down.

**Money contract:** `fee_quoted`, `fee_collected` and every `service_request_fees`
amount are stored to **4 decimals** with a `CHAR(3)` currency and **displayed to
2** (PO re-sign 2026-08-22). Never float, never cents. **Nothing in this module
posts to the ledger or issues an invoice** (B18 §4.6, hard rules 4 and 5).

**Derived, never stored:** `outstanding = quoted − settled − collected`, signed
and not clamped. `fee_collected < fee_quoted` is a **lawful, storable state**;
the difference is an **open fee balance** that is **REPORTED and blocks
nothing**, and it is never a refusal at the desk and never a silent waiver.

⛔ **THAT SENTENCE READ *"blocks APPROVAL only"* UNTIL 2026-09-21.** PO,
verbatim: *"make application fees optional - so that we can approve it"*. The
fee stopped being a precondition of approval; `BR-CUS-090` clause (1) carries
the amendment and its date. ⚠ **NOTHING ELSE MOVED** — the figure is still
derived the same way, still signed, still printed on the request **after** the
approval, and a shortfall still never becomes a waiver. The condition is served
with `state: "blocked"` and `blocking: false`, so a screen still names it.

⛔⛔ **SUPERSEDED 2026-09-23 — THE FEE GATES APPROVAL AGAIN (`OQ-CUS-12617` CLOSED, `DEF-CUS-6420`).** PO, verbatim: *"we already told you - either fee is paid or waived - no other condition"*. Approve waits until the application fee is **paid in full or waived**; a part payment holds it on the REMAINDER (quoted $130.00, taken $25.00 → *✗ Fee · $105.00 unpaid*, Approve off). A utility with no fee lines is untouched, and the counter still accepts a short payment and never refuses — the desk half of `BR-CUS-090` stands. The paragraph above is kept as the record of 2026-09-21. The condition is served `blocking: true` again.

---

## 4 · Outcomes — `disconnect` is one of five, and it is not a move-out

**BR-CUS-091 (PO 2026-08-24): *"Yes customer can request it"***. The list's
`SR-26-0048 · DISCONNECT` was correct; REQ-02's decision-panel reason (*"only
ever started by collections, never from a customer request"*) is **withdrawn**.

> ⚠ **What that reason got RIGHT is contract and survives the withdrawal:**
> a **move-out** closes the account and settles the deposit (BR-CUS-030);
> a **disconnect** leaves it **open and accruing** (BR-MET-105's base charge
> keeps running). They map to **different child kinds** —
> `OUTCOME_CHILD_KINDS["disconnect"] == "disconnect"` — and nothing may collapse
> one into the other.

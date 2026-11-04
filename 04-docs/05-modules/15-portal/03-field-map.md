# 15 · Customer Web Portal — field map

**Every table below is tenant-scoped and every one carries RLS `FORCE`**, in its own
migration, the way every other module does it (CLAUDE.md hard rule 1).

**Money is `NUMERIC(18,4)`, percentages `NUMERIC(18,6)`, both display 2** (hard rule 2,
PO re-sign 2026-08-22). Currency is `CHAR(3)`. Never float, never cents.

⚠ **THE OWNING MODULE OWNS ITS DATA (B2 §2), SO THE PORTAL OWNS FIVE TABLES AND NOT
FOURTEEN.** A stored card is a payment concept and the money rules live in `payments`;
an interruption is a network fact and lives in `metering`; published content is
per-tenant reference data and lives in `tenancy`. **A lane that puts all fourteen in
`apps/portal/` has made the portal a second billing system.**

---

## 1 · The tables the portal OWNS — `apps/portal/`

⚠ **THE HEADING SAID *FIVE* AND THE COUNT IS NOW SEVEN**, both added by builds that met a rule this section did not have a column for: `portal_application_drafts` (`DEF-CWP-3700`, wave C) and `portal_one_time_code` (`DEF-CWP-3741`, wave E). The number is left out of the heading rather than corrected to seven, because it has now been wrong twice for the same reason and a count is the part that goes stale.

### `portal_credential` — `CP-01`

| Column | Type | Origin | Validation |
|---|---|---|---|
| `id` | `uuid` PK | system | — |
| `tenant_id` | `uuid` FK → `tenant` | system | RLS `FORCE` |
| `customer_id` | `uuid` FK → `customer` | system | **Must already exist.** Enrolment attaches a password to a person on file; it never creates one (`BR-CWP-029`) |
| `email` | ~~`citext`~~ **`text` + normalisation** | user-input | Unique per tenant. The sign-in identifier. ⚠ **AMENDED 2026-09-04:** `citext` is a PostgreSQL extension SQLite has no form of, and the default suite runs on SQLite (law 14) — a case-insensitivity proved only on PostgreSQL is not proved. `credentials.normalise_email` lower-cases and strips on the way IN, so the unique constraint is real on both engines |
| `password_hash` | `text` | system-derived | ⚠ **THE DEPLOYMENT'S CONFIGURED HASHER, NOT `Argon2id` VERBATIM — AMENDED 2026-09-04 (wave E).** `argon2-cffi` is not installed here, so Django's `PASSWORD_HASHERS` resolves to PBKDF2 — which is what `apps/identity/services.py` already hashes every STAFF password with. Two hashing policies in one product is worse than one slower hash: it is a deployment that upgrades one population and silently not the other. `credentials.py` calls `make_password`/`check_password`, so the day `PASSWORD_HASHERS` names Argon2id both populations move together and each row re-hashes on its next sign-in. Policy read from the tenant's existing password settings (`BR-CWP-037`) |
| `password_changed_on` | `timestamptz` | system | Shown on `CWP-024` |
| `otp_channel` | enum `sms` \| `email` | user-input | Default `sms` where a mobile is held |
| `failed_attempts` | `smallint` | system-derived | Lock at 5 for 15 minutes (`BR-CWP-036`) |
| `locked_until` | `timestamptz` NULL | system-derived | — |
| `status` | enum `active` \| `locked` \| `disabled` | system-derived | — |
| `enrolled_on` | `timestamptz` | system | — |

⚠ **THIS TABLE MUST NEVER JOIN TO `identity.user`.** Separate table, separate session,
separate permission catalogue — not one table with a flag on it (`BR-CWP-004`).

### `portal_session` — `CP-01`

| Column | Type | Origin | Validation |
|---|---|---|---|
| `id` | `uuid` PK | system | — |
| `tenant_id` | `uuid` FK | system | RLS `FORCE`. **Resolved before the credential is read** (`BR-CWP-005`) |
| `portal_credential_id` | `uuid` FK | system | — |
| `account_set` | `jsonb` | system-derived | Array of `{account_id, permissions[]}`. Built from **exactly two sources** and nothing else (`BR-CWP-009`). **Flat** — a master account is one more entry (`BR-CWP-013`) |
| `issued_at`, `last_seen_at`, `expires_at` | `timestamptz` | system | Sliding idle timeout, mirroring the staff policy |
| `device_fingerprint` | `text` NULL | system-derived | Decides whether a code is required on this sign-in |
| `revoked_at` | `timestamptz` NULL | system | *Sign out everywhere* on `CWP-024` |

### `portal_delegate` — `CP-04` · ⚠ blocked on `OQ-1396`

| Column | Type | Origin | Validation |
|---|---|---|---|
| `id` | `uuid` PK | system | — |
| `tenant_id` | `uuid` FK | system | RLS `FORCE` |
| `granted_by_credential_id` | `uuid` FK | system | The account holder. **Only the holder may invite** |
| `invitee_email` | `citext` | user-input | — |
| `invitee_display_name` | `text` | user-input | *"Kestrel Bookkeeping"* — the name that appears in the audit trail |
| `account_id` | `uuid` FK → `account` | user-input | Must be in the granter's own set |
| `permissions` | `text[]` | user-input | Subset of `see`, `download`, `pay`, `save_method`. **Never** `close_account`, `change_owner`, `move_out` |
| `expires_on` | `date` NULL | user-input | ⚠ **How long access may run, and who may revoke it, is `OQ-1396`.** Stub the policy, not the column |
| `status` | enum `invited` \| `active` \| `ended` | system-derived | An ended row **stays** on the record |
| `audit_actor_id` | `uuid` | system-derived | **This is the point of the table.** Without it every portal action by a bookkeeper is recorded as the account holder, and the audit trail is quietly wrong on exactly the accounts where a dispute is most likely |

### `portal_one_time_code` — ⊕ **ADDED BY THE BUILD, 2026-09-04** (`CR-068` wave E)

⚠ **THIS TABLE IS NOT IN §1's ORIGINAL FIVE, AND IT HAD TO BE** (`DEF-CWP-3741`).
`BR-CWP-033` puts a one-time code between *matched* and *proven*, and at that
moment **no credential exists yet** — `enrol/set-password` creates one two
screens later. So the code cannot hang off `portal_credential`, and
`BR-CWP-038`'s seven-day reset link has the same shape one door along. §1 named
`otp_channel` and stopped there, which reads as complete: a column exists, a
channel is chosen, and the storage the rule needs is simply absent.

⚠ **THIS IS THE SECOND TIME A WAVE HAS FOUND A PORTAL TABLE THE FIVE DO NOT
HOLD** — `portal_application_drafts` was the first (`DEF-CWP-3700`) — and the
pattern is the same both times: **§1 lists what the design DREW, not what the
rules REQUIRE.**

| Column | Type | Origin | Validation |
|---|---|---|---|
| `id` | `uuid` PK | system | — |
| `tenant_id` | `uuid` FK → `tenant` | system | RLS `FORCE` |
| `purpose` | `enrol` \| `reset` | system | Two doors, one store: they differ in lifetime and shape, not in kind |
| `account_id` | `uuid` FK NULL | system | The account being enrolled on. NULL for a reset, which is asked for by email and reaches a credential |
| `portal_credential_id` | `uuid` FK NULL | system | The credential being reset. NULL for an enrolment, where none exists yet |
| `code_hash` | `text` | system-derived | ⚠ **THE CODE ITSELF IS NEVER STORED.** SHA-256 over the code, compared with `hmac.compare_digest`. A support screen that could read back a live code would be a second way in |
| `channel` | `sms` \| `email` | system-derived | Whichever contact was held (`BR-CWP-033`) |
| `destination_masked` | `text` | system-derived | `••• ••• 4218` — masked HERE as well as on the way out, so nothing downstream has to remember |
| `outbound_message_id` | `uuid` NULL | system | The queue row carrying it. ⚠ Queued under `source_type='portal'`, which is deliberately **absent** from `CHANNEL_FLOOR_BY_SOURCE`: filing it under `account` would post a six-digit login code by letter |
| `expires_at` | `timestamptz` | system | Ten minutes for a code (`BR-CWP-035`), seven days for a reset link |
| `consumed_at` | `timestamptz` NULL | system | Single use |
| `superseded_at` | `timestamptz` NULL | system | ⚠ **THIS IS WHAT MAKES *RESEND INVALIDATES* TRUE.** Issuing a new code stamps every live one in the same transaction, so the first message cannot still work after the second arrives |
| `attempts` | `smallint` | system-derived | Six wrong tries lock it |
| `created_at` | `timestamptz` | system | — |

### `portal_settings` — `CP-30`, one row per tenant

| Column | Type | Origin | Validation |
|---|---|---|---|
| `tenant_id` | `uuid` PK FK | system | — |
| `is_live` | `boolean` | user-input | Default **false**. Off shows a holding page; bills and letters are unaffected (defaults fail closed, hard-won law 3) |
| `quick_pay_enabled` | `boolean` | user-input | Default **true** |
| `self_read_enabled` | `boolean` | user-input | Default **false** — ⚠ the one switch that is off for a new tenant (`CR-068` `R8`) |
| `plans_enabled` | `boolean` | user-input | Default **true** |
| `requests_enabled` | `boolean` | user-input | Default **true** |
| `outage_reporting_enabled` | `boolean` | user-input | Default **true** |
| `strapline` | `text` | user-input | Portal only. B14 rule 32 applies to its length |
| `front_page_service_ids` | `uuid[]` → **built as a JSON list of `services.id` strings** (wave A, 2026-09-03: the default suite runs on SQLite, which has no array column; the rule — a subset of the tenant's OWN enabled services — is enforced in `settings_service.save_branding`) | user-input | Which of the tenant's services appear as chips, **in the order the utility listed them** |
| `office_hours_text`, `emergency_phone` | `text` | user-input | Shown on every guest screen |

⚠ **THE PORTAL ADDRESS IS NOT A COLUMN HERE.** It is the tenant slug already stored on
`tenant.subdomain`, already routing every request as the first path segment, and **never
displayed after the sign-up wizard** — which is why a utility cannot put its own portal
on a bill. `CWP-069` displays what is already there. **Do not add a second copy.**

⚠ **AND `tenant.subdomain` IS A MISLEADING NAME THAT NOW HOLDS A PATH SEGMENT.** Reading
the column name and inferring the URL shape is exactly the reasoning that wrote all
seventy-five of the blueprint's routes as subdomains, three weeks after the product
stopped working that way. The ruling lives in the decision log, not in the column name.

### `portal_application_drafts` — ⊕ **ADDED BY THE BUILD, 2026-09-04** (`CR-068` wave C)

⚠ **THIS TABLE IS NOT IN §1's ORIGINAL FIVE, AND IT HAD TO BE** (`DEF-CWP-3700`).
`US-CWP-013` §5 maps the applicant's half-filled form to `service_request.status = draft`
with *"No number allocated"* — and `BR-CUS-093` (PO ruling 2026-08-24, verbatim: *"At
creation — every draft is numbered"*) makes `create_request` allocate `SR-26-nnnn` inside
its own transaction. A portal draft written as a service request is therefore **numbered on
the applicant's first keystroke**, and every abandoned half-typed form arrives on the
clerk's worklist carrying a reference nobody was shown. `US-CWP-013` TC-1 asserts the
opposite in as many words: *"No reference has been issued."*

| Column | Type | Origin | Validation |
|---|---|---|---|
| `id` | `uuid` PK | system | — |
| `tenant_id` | `uuid` FK → `tenant` | system | RLS `FORCE` |
| `token` | `text` | user-agent | ⚠ **The URL capability, not a reference.** 122 bits from the browser's own CSPRNG; unique per tenant |
| `address_as_given`, `address_unit_as_given` | `text` | user-input | Kept verbatim |
| `matched_premises_id` | `uuid` NULL | system-derived | Evidence, never a decision. Re-resolved server-side; ⚠ **never sent to the browser** |
| `service_codes` | `jsonb` | system-derived | The services available at the matched address |
| `applicant_kind` | `text` | user-input | `person` \| `business` |
| `first_name`, `last_name`, `company_name`, `email`, `phone` | `text` | user-input | — |
| `date_of_birth` | `date` NULL | user-input | ⚠ **Recognition only** (`BR-CWP-031`), and **cleared at submit** |
| `tax_id` | `text` NULL | user-input | Business only; stays here — `OQ-CWP-1560` is where it should ultimately land |
| `requested_start` | `date` NULL | user-input | ≥ 3 working days |
| `service_request_id` | `uuid` NULL | system | ⚠ **NULL is the whole of *no reference until submit*, written as a column** |
| `submitted_at` | `timestamptz` NULL | system | A submitted draft is frozen |

### `portal_consent` — `CP-30`, `CR-068` `R5`

| Column | Type | Origin | Validation |
|---|---|---|---|
| `id` | `uuid` PK | system | — |
| `tenant_id` | `uuid` FK | system | RLS `FORCE` |
| `account_id` | `uuid` **NULL** | system | ⊕ **NULLABLE SINCE THE BUILD, 2026-09-04** (`DEF-CWP-3702`). This row typed it NOT NULL; the ONE screen release 1 takes this consent on is `CWP-009`, the connection form, where **the applicant has no account and may never have one**. A NOT NULL column would have made the only consent the product takes impossible to write. The row hangs off the service request at that moment and an account is stamped on later if one is opened |
| `service_request_id` | `uuid` **NULL** | system | ⊕ **ADDED BY THE BUILD.** What the consent was given ON |
| `kind` | enum `paperless` | user-input | Extensible; only paperless in release 1 |
| `wording_version` | `text` | system-derived | **The version of the words they actually saw.** A consent without it is not a consent |
| `agreed_on` | `timestamptz` | system | ⚠ **May never be in the future** — the blueprint shipped a consent dated nineteen days after its own "today" and its §26 lists the repair |
| `withdrawn_on` | `timestamptz` NULL | user-input | Withdrawal is one control away, and the row is **never deleted** |
| `taken_on_screen` | `text` | system-derived | `CWP-009` for a new connection, `CWP-025` for a withdrawal |

⚠ **EXISTING PAPERLESS CUSTOMERS ARE NOT ASKED AGAIN** (`CR-068` `R6`). The consent is
taken on the new-connection form, so it applies from the next customer onward. A
migration that back-fills consent rows for existing customers **invents a consent
nobody gave**.

---

## 2 · The nine tables owned by OTHER modules

### `payments` module

**`payment_method`** — `CP-08`, the customer's stored instrument.

| Column | Type | Validation |
|---|---|---|
| `id`, `tenant_id`, `customer_id` | `uuid` | RLS `FORCE` |
| `gateway_token` | `text` | ⚠ **A token from the gateway. The product never holds a full card number** (`BR-CWP-057`) |
| `brand` | `text` | `Visa`, `Chase` |
| `last_four` | `char(4)` | The only digits ever stored |
| `expires_month`, `expires_year` | `smallint` | Card only |
| `kind` | enum `card` \| `bank` | — |
| `status` | enum `active` \| `verified` \| `expired` | `verified` is bank-only |
| `used_for` | `text[]` | `autopay`, `one_off` |

⚠ **NAME COLLISION, AND IT MUST BE RESOLVED BEFORE THE MIGRATION.**
`06-backend/apps/payments/models.py:65` records that `payment_methods` **as B2 §2 spells
it** is the customer's stored instrument — and the name is **currently taken by the staff
tender lookup**. Two different things want one name. Rename one of them first; a
migration that discovers this at `makemigrations` time has already picked, badly.

### `metering` module

**`interruption`** — `CP-15`, *"the largest genuinely new record in the blueprint"*.

⚠ **BUILT 2026-09-04 (CR-068 wave B). THE TABLE IS `interruptions`, PLURAL** — every table in this schema is (`premises`, `connections`, `work_orders`, `service_requests`, `portal_settings`) and this document writes entity names in the singular throughout. The code wins; nothing else moved. **Two columns joined it that are not in the table below:** `reference` (`RP-26-0412`, from a new thirtieth number series `interruption_report` — the number a stranger keeps, deliberately NOT the clerk's `SR-`) and `service_request_id`, a cross-module FK to `customers` and a POINTER never a write, the same shape and the same disposition as `work_orders.account_id`. **And `affected_area` is `JSONField`, not `jsonb`-only:** the default test suite runs on SQLite (CLAUDE.md law 14) and Django serves the same Python value on both.

| Column | Type | Validation |
|---|---|---|
| `id`, `tenant_id` | `uuid` | RLS `FORCE` |
| `kind` | enum `no_water` \| `leak_or_burst` \| `low_pressure` \| `gas_smell` \| `missed_collection` \| `damaged_meter` | ⚠ `gas_smell` **routes to a phone number, never to a queue** |
| `reported_at`, `resolved_at` | `timestamptz` | — |
| `status` | enum `looking_into_it` \| `crew_on_site` \| `resolved` | Drives the timeline on `CWP-007` |
| `location_text` | `text` | ⚠ **Free text, resolved later.** Demanding an exact premises match would refuse the person standing over a burst main (`BR-CWP-027`) |
| `premises_id` | `uuid` FK NULL | Resolved by a clerk, not by the form |
| `affected_area` | `jsonb` | Street plus a number range — *"Elm St, 1400–1500"*. **The affected-area rule, and it is the new thinking in this table** |
| `reporter_name`, `reporter_phone` | `text` | ⚠ **The reporter need not be a customer** |
| `expected_back_on` | `timestamptz` NULL | — |

**`planned_outage`** — `CP-16` · ⚠ **waits on the field-work module, whose scope is
unresolved (`OQ-249`)**. Columns: work description, affected premises rule, window,
status `planned` \| `scheduled`, and whether it is published to everyone or only to
affected accounts. **Do not build this before that scope question is answered.**

### `tenancy` module — the published content

**`help_answer`** — `CP-31`. `question`, `topic`, `status` enum `draft` \| `published` \|
`not_shown`, `position` (integer — **the order here is the order on the portal**),
`also_show_on_screen` (text, nullable — one field that makes an answer appear under a
bill as well as in the list), `last_changed_by`, `last_changed_on`.

⚠ **`draft` AND `not_shown` ARE TWO DIFFERENT STATES AND NEITHER LEAVES THE BACK
OFFICE.** The blueprint's own public help page listed all eight answers including both,
and its §16 records the repair. **The gate is `status = published`, in the query, not in
the template.**

**`help_answer_variant`** — one row per language. `help_answer_id`, `locale` (one of the
eleven that ship), `body`, `status` enum `published` \| `needs_translating`,
`last_changed_on`. ⚠ **A missing translation shows the English answer rather than hiding
it** (`BR-CWP-094`) — *"a missing translation is better than a missing answer"*.

**`help_answer_feedback`** — `CP-34`, the portal's smallest write and the one that makes
the help screens improvable. `help_answer_id`, `locale`, `event` enum `read` \|
`helpful` \| `not_helpful`, `occurred_on`. ⚠ **A read and a vote are counted
separately** — pressing *No* is not the same event as opening the page.

**`tip`** — `CP-32`, the smallest table in the module. `text` (⚠ **keep under fifteen
words or nobody reads them**), `target_screen`, `month_from` / `month_to` (nullable —
null means all year), `is_on`, `position` (**breaks the tie when two match**).

**`service_centre`** — `CP-33`. `name`, `address`, `phone`, `directions_note`,
`allowed_actions` `text[]`, `payment_methods_accepted` `text[]`, `is_shown_to_customers`,
`position`. ⚠ **`is_shown_to_customers = false` is a REAL STATE, not a deletion** — it
is how a depot stays off the public page without being removed from the list.

**`service_centre_hour`** — `service_centre_id`, `day_of_week`, `opens_at`, `closes_at`,
`is_closed`. ⚠ **Holiday closures are NOT rows here.** They come from the tenant's
existing holiday calendar, so a centre closes itself on Thanksgiving with nobody
remembering to edit the page (`BR-CWP-096`).

⚠ **AS BUILT — CR-068 wave D, 2026-09-04, `tenancy` migrations `0037` + `0038`.**
Four shapes differ from the six rows above and each is stated rather than quiet:

1. **`allowed_actions` and `payment_methods_accepted` are JSON, not `text[]`.**
   The default suite hardcodes in-memory SQLite (CLAUDE.md law 14) and
   `ArrayField` has no SQLite form, while the validation that matters — the
   values are the catalogue's — is the service's business and not the column's.
2. **Every child table carries its OWN `tenant_id`** rather than inheriting one
   through its foreign key. A policy on the parent does not constrain a query
   that starts at the child, and a Wednesday opening time is as much one
   utility's business as the centre it belongs to.
3. **`help_answer` and `service_centre` each carry a `slug`**, unique per
   tenant. B14 rule 31 makes a URL a visible value, so `/portal/help/{id}`
   could not be a uuid.
4. **`day_of_week` is Monday = 0 … Sunday = 6** — Python's `date.weekday()`, so
   the clock read in `published_content.centre_today()` needs no conversion
   table and no place to get it wrong.

⚠ **AND THE WRITE SIDE OF `help_answer_feedback` IS TENANCY'S, WHICH IS WHY
`BR-CWP-001` IS NOT BENT.** This document calls it *"the portal's smallest
write"* and `BR-CWP-001` says the portal may create rows of exactly four kinds;
both are ratified and they collide (`DEF-CWP-3727`). The row is a **tenancy**
table and B2 §2 forbids a cross-module write, so `apps/portal` could never write
it — the route lives in `apps/tenancy/published_content_api.py` wearing the
portal's guest guards, the four write points are untouched, and `G81` still
refuses a fifth.

---

## 3 · The eleven changed columns, across six existing tables

| # | Table (module) | Column | Why |
|---|---|---|---|
| 1 | `meter_read` (metering) | `source` enum `staff` \| `portal` \| `estimated` | `CP-19`. **One validation, two sources** — the portal adds a way in, not a second set of rules |
| 2 | `meter_read` (metering) | `review_state` enum `awaiting_review` \| `cleared` \| `superseded` | `CP-19`. A submitted read is on **no bill** until a clerk clears it (`BR-CWP-068`), and a superseded one must not leave the customer charged twice (`BR-CWP-069`) |
| 3 | `meter_read` (metering) | `submitted_by_credential_id` `uuid` FK NULL | The named actor. Points at `portal_credential`, **never** at `identity.user` |
| 4 | `meter_read` (metering) | `evidence_document_id` `uuid` FK NULL | The photo of the dial — *"it settles most questions"*. ⚠ Uses the existing document store with its allow-list and size cap — no malware scan, SUPERSEDED (PO 2026-09-22 / 2026-09-23 → no malware scan on upload) |
| 5 | `payment_plan` (payments) | `customer_signed_on` `timestamptz` NULL | `CP-39`. **A plan activates on the customer's signature alone, not the clerk's** (`BR-CWP-065`) |
| 6 | `payment_plan` (payments) | `offer_expires_on` `date` NULL | `CP-39`. *"The offer stands until 16 September; after that the office has to set it up again"* |
| 7 | `payment` (payments) | `portal_credential_id` `uuid` FK NULL | Hard rule 7 needs a **named actor** for every money action, and the delegate is the reason it cannot be the account holder by default |
| 8 | `service_request` (customers) | `portal_credential_id` `uuid` FK NULL | Same reason |
| 9 | **a portal-owned per-recipient message row** (message × credential; `apps/portal`, named by wave K) — ⚠ **NOT `outbound_message`**: its docstring (`apps/notifications/models.py:828–840`) forbids a recipient's read state on the row that records what the utility sent, which is why the staff mailbox already keeps its own `read_at` row (917). This row named `outbound_message` until 2026-09-03 — `DEF-CWP-3612` | `delivered_at` `timestamptz` NULL | `CP-17`. ⚠ **Delivered to the portal means QUEUED AND VISIBLE, never ARRIVED** (`BR-CWP-084`) |
| 10 | the same portal-owned per-recipient row (⚠ not `outbound_message` — `DEF-CWP-3612`) | `read_at` `timestamptz` NULL | `CP-18`. Drives the unread count on the bell |
| 11 | `audit_log` (audit) | `portal_actor_id` `uuid` NULL + `portal_actor_label` `text` NULL | So an audit row can read *"Kestrel Bookkeeping"* rather than *"Maria Alvarez"*. **Counted as one change; it is one purpose** |

**And one enum gains a value rather than a column:** `service_request.channel` gains
`customer_portal`. The field has existed since the record was designed and **nothing has
ever written that value** — the first row carrying it is the proof `CP-56` is done.

**Two flags already exist and are inert. Neither is a schema change; both are switched
on:** `account_note.customer_visible` (the boundary between a note for the customer and
one for the counter — `CP-25`) and the account's portal-access switch.

---

## 4 · What is deliberately NOT modelled

| Not built | Why |
|---|---|
| A statement document | **There is no statement in this product.** Either the transaction list becomes one or a statement gets built — `OQ-1395` |
| Consumer document upload | Deferred by signed decision; uploads stay staff-mediated. The **checklist is real and the upload box is not**, so a request needing a document ends with *"bring it to the office"*. ⚠ **SUPERSEDED FOR THE NEW-SERVICE REQUEST, PO 2026-10-01 (`CR-158-BRC10`):** `portal_application_documents` (`id`, `tenant_id`, `draft_id` → `portal_application_drafts`, `name`, `content_type` — sniffed from the bytes, CHECK PDF/JPEG/PNG, `size_bytes` — CHECK 1..10 MB, `payload` `bytea`, `uploaded_at`; RLS `FORCE`, `portal/0011`) holds up to 5 files on an unsent draft; at submit each becomes a `service_request_documents` row (`doc_type` `other`, `not_checked`, `uploaded_by` NULL) in the document store and the held row is deleted. Every other flow keeps the deferral. |
| A public status page | `CR-068` `R9` — reporting ships, the status page waits until somebody owns keeping it current out of hours |
| A high-usage trigger | `CP-29`. The event is declared in the catalogue and **nothing ever fires it**. On monthly reads it can only fire at billing time |
| A credit-tier read | Held back on purpose (`BR-CWP-052`) |

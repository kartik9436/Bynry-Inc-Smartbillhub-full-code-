# EP-INT-11 — The partner reading from us: machine authentication, the partner surface, and the record of who read what

**Module:** integrations (+ identity for the authentication class) · **Wave:** GL track — *"not a phase; a different project wearing the same word"* · **Screens:** S144 machine credentials · S142 (the access log as `inbound_read` runs) · the subprocessor register view · **Status:** `US-INT-041` **BUILT `2.199.0`** (2026-09-06, integrations half) · `US-INT-040` draft — ⚠ **`OQ-INT-1481` was CLOSED 2026-09-04, option (a): the System Admin, as an audited grant plus a register row pointing inward.** The scope paragraph below still describes the blocked world and is corrected here rather than rewritten: nothing waits on a ruling any more.

## Scope

**In:** the SERVE quadrant — the cell that was empty and nothing said so. A finance system connects to ours, on its schedule, and reads payments and bills into its own general ledger. **We are the provider.** It needs none of the adapter machinery and three things this design never had to think about: a partner API surface, machine authentication, and a record of who read what (`BR-INT-035`, `BR-INT-044`, `BR-INT-053`).

**Out:** the account string in `Fund.Department.Account` form — a segmentation of OUR chart, `OQ-INT-1480`; the subprocessor register's shape for an inward relationship beyond the row this epic writes (`C33`); the runner itself, which phase 1 built with nothing behind it (`US-INT-013`).

⚠ **THAT RULING LANDED, AND TWO LANES CORRECTED THIS PARAGRAPH INDEPENDENTLY ON THE SAME DAY. `OQ-INT-1481` WAS CLOSED ON 2026-09-04 — option (a): the System Admin authorises, recorded as an audited grant on the connection plus a subprocessor-register row pointing inward.** This paragraph read *"the whole epic waits on one ruling … the act of enabling a partner connection raises `NotImplementedError("OQ-INT-1481")` until the PO rules"*, and **every clause of it is now false**: both stories are BUILT — `US-INT-040` (the key we issue) by wave R on 2026-09-06, `US-INT-041` (the door, the allowlist, the rate limit, the access log, the grant and the register) by wave S the same day. The enable path is a build: `POST /integrations/{key}/grant` writes the grant, gated on `SettingsReadAnyWriteSystemAdmin`. It is amended rather than deleted because a lane briefed from the old sentence would have stubbed a path that already serves. *"Every other connector is a tenant reaching outward. This one is a third party reaching in"* is still exactly right and is why the epic exists.

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S144 · machine credentials | partner | state (active · revoked) | issued desc | issued · last used | partner · hint (`••••7Q2F`) · scope (tenant) · issued by/on · last used · state | replace (icon) · revoke (danger) | — | — |
| S142 · *Who has been reading* (the `inbound_read` runs) | key hint | partner · date | when desc | when · records | when · partner · what (payments · bills) · records handed over · pages · key hint | open | — | — |

## Stories

---
id: US-INT-040
epic: EP-INT-11
module: integrations
screens: [S144, S141]
wave: 1
status: draft            # was `blocked`; OQ-INT-1481 ruled 2026-09-04 — System Admin, audited grant
blocked_by: []
depends_on: [US-INT-014, US-INT-019, US-INT-024]
journeys: [J54]
rules: [BR-INT-003, BR-INT-043, BR-INT-053]
golden_tests: []
finance_calc: none
---
### US-INT-040 — Machine authentication for a partner: a credential we issue, scoped to one tenant, shown once and never again (C30)

**1 · Details** — As **a finance system with no human at the keyboard**, I want **to authenticate with a credential the utility issued me, scoped to that one tenant** — so that **I can read their payments on my schedule, and a revoked key refuses my very next call**.

`DEFAULT_AUTHENTICATION_CLASSES` is `IdentitySessionAuthentication` and nothing else — no API key, no client credential, no token. *"This is identity work and it belongs to identity, not to this module"*: `apps/identity` gains `MachineCredentialAuthentication` (a companion identity story is owed and is recorded as seam **I-9** in `03-field-map.md`); integrations declares the field kind — `issued_secret` — and the connection, and **S144** lists the credentials: issued by whom and when, last used, hint, state. `POST /integrations/{key}/key` **issues or replaces** the key — returned **once**, copyable, never re-displayed; `DELETE /integrations/{key}/key` **revokes**, and the partner's very next call is refused, not their next scheduled collection. The key is stored as a hash-blind-indexed encrypted credential (`core/crypto.py` blind indexes) scoped to `tenant_id`; a key presented against another tenant's route answers as an unknown caller.

✅ **BUILT 2026-09-06 (wave R).** Issuing, listing, replacing and revoking work, and **enabling the partner connection to serve is a build rather than a boundary** — `OQ-INT-1481` closed on 2026-09-04 and wave S landed the door the same day. ⚠ **One thing this story assumed and does NOT have: `machine_auth` does not authenticate.** The single answer to *may this machine read* is `runners/serve.resolve_caller()`, wave S's, and this story WRITES the blind index that door reads — under `serve.ISSUED_KEY_BLIND_INDEX_CONTEXT`, imported and never retyped, because two spellings would refuse every valid key and would look exactly like a wrong key. Identity's `MachineCredentialAuthentication` (seam I-9) is still unbuilt and was not needed: the three partner routes opt out of the default authenticator and call the resolver themselves.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-053` | A machine credential is scoped to one tenant, shown once, only replaced; revocation refuses the next call | PROPOSED — design §2.2.6, `C30` |
| `BR-INT-043` | `issued_secret` is a declared field kind — the opposite of every other card | PROPOSED |
| `BR-INT-003` | Never rendered back — the hint only, after the one display | CONFIRMED |
| `OQ-INT-1481` | Who may authorise a partner to read | **CLOSED 2026-09-04 — option (a), the System Admin, as an audited grant plus a register row pointing inward. Built by wave S** |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Alex presses **Issue key** for *Third-party GL* | The key is shown once with **Copy**; `GET` afterwards returns `••••7Q2F` only; S144 lists it *issued by Alex Reed, 3 Sep, never used* |
| TC-2 | The partner presents the key on `GET /api/v1/payments` | Authenticated as the partner **for Brazos Bend only**; S144 *last used* updates |
| TC-3 | Alex presses **Revoke**; the partner calls one second later | **Refused** — the very next call, not the next collection; the refusal reveals nothing about the account |
| TC-4 | **Replace key** | New key shown once; the old one refuses from that moment; both appear on S144 (old *revoked*) |
| TC-5 · **negative** | The key presented against Lone Star Ridge's route | Unknown caller — identical body to a wrong key |
| TC-6 · ~~boundary~~ **AMENDED 2026-09-06 — THERE IS NO BOUNDARY HERE ANY MORE** | Alex sets the partner connection `enabled = true` | **The connection serves.** This case asked for `NotImplementedError("OQ-INT-1481")` and the words *Waiting for a decision on who may allow this*; `OQ-INT-1481` was CLOSED on 2026-09-04 and wave S built the path, so that refusal would now tell a clerk a decision is waited on that was made two days earlier. The test asserts the opposite — a partner call answers `200`, and **no line in `serve.py`, `partner_api.py` or `machine_auth.py` raises naming that question** |
| TC-7 · **three exits** | Logs, audit rows and API responses after TC-1 | The key's plaintext appears in none |

**4 · Test Data** — `gl_partner` connection *Aclarian* on Brazos Bend; issued key `sbh_live_7Q2F…` (hint `••••7Q2F`); actor Alex Reed; partner caller from `198.51.100.12`.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| issued key | shown once | `C30` | **`integration_credential.blind_index` ONLY** (+ a marker in `payload_enc` that holds no key material) | one-way HMAC-SHA256 token | system-issued | never stored, so never re-displayable — ⚠ **AMENDED 2026-09-06**, this row said `payload_enc` *encrypted + blind index*. Encryption is reversible and is right for `we_hold_theirs`, where an adapter must PRESENT a secret; nothing here ever presents this key, only RECOGNISES one, so a reversible copy is a liability we would be choosing to keep. Decision log 2026-09-06 |
| `masked_hint` · issued on · last used · state | S144 | — | `integration_credential.masked_hint` · `created_at` · **the newest `inbound_read` run inside that version's window** · `is_active` | text/ts/bool | system-derived | ⚠ **AMENDED 2026-09-06**: *last used* was mapped to `config.last_used_at`. It is DERIVED from the access log wave S already writes, because one column on the connection holds ONE timestamp — so a REPLACED key could never say when it was last used, its number having been overwritten by its successor's. A version's window is `created_at → rotated_at` and the two cannot overlap |
| authentication class | — | `C30` | `apps/identity` — **seam I-9** | code | identity | scoped to `tenant_id` |

**6 · Acceptance**
- Given a partner, then it authenticates with a key we issued, sees one tenant, and a revoked key fails on the next request.
- Given the ruling is open, then nothing can be served yet and the screen says so in words.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-INT-1481` | Who may authorise a partner to read a tenant's data, and how is that authorisation recorded? | ~~Enabling any partner connection~~ nothing — it is built | PO | **CLOSED 2026-09-04 — option (a)**, the System Admin, as an audited grant plus a register row pointing inward |

---
id: US-INT-041
epic: EP-INT-11
module: integrations
screens: [S142, S141]
wave: 1
status: draft            # was `blocked`; OQ-INT-1481 ruled 2026-09-04 — System Admin, audited grant
blocked_by: []
depends_on: [US-INT-040, US-INT-037, US-INT-039, US-INT-020]
journeys: [J54]
rules: [BR-INT-035, BR-INT-044, BR-INT-032, BR-INT-033]
golden_tests: []
finance_calc: none
---
### US-INT-041 — A partner reading from us: the partner surface, the allowlist, the rate limit, and the record of who read what (C5, C33)

**1 · Details** — As **a utility manager**, I want **to see who has been collecting our data, how much and when** — so that **an unusual collection is something I notice rather than something I find out about later**.

Failure 13, the last of the silent four: *"a partner with a valid key collects two years of payment history at two in the morning. Every request is authorised. Nothing in the product would show it."* **The partner surface** — `GET /api/v1/payments`, `GET /api/v1/billing`, versioned, machine-authenticated, filtered by type · tender type · date range, paginated **in the partner's declared envelope** (`{total_records, page, page_size, total_pages}` — a second envelope, cheap, but a second envelope, declared per operation), described by a published specification (`GET /api/v1/openapi.json`) rather than a bespoke document. Each record carries `id`, `paymentDate`, `amount` (4-decimal money, displayed 2), `tenderType` **through the mapping rows** (`BR-INT-032` — their four words for our tenders), `projectType` (**a constant, *Utility Billing***), `accountString` (the partner's word for our account from the mapping rows; `ledger_accounts.code` where none — the segmentation question is `OQ-INT-1480`). **Every read is a run** — `direction = inbound_read`, `trigger = partner`, `attempted = records handed over`, the key hint as *who* — listed on S142 as *Who has been reading*. **A source allowlist** (`198.51.100.0/24, 203.0.113.7`) refuses any other address **without revealing whether the account exists**; **a per-partner rate limit** applies; **an unknown account answers in the operation's declared way, which may not be 404.** The subprocessor register gains the relationship **pointing inward**, derived from the live connection (`C33`).

⚠ **To the boundary:** the surface, the record and the guards are built and tested with a test partner; **serving a real partner needs the connection enabled, which is `OQ-INT-1481`.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-035` | Every partner read recorded (who, when, how many, which key); tenant authorises explicitly; register in both directions | **CONFIRMED 2026-09-04** — the authorisation half was `OQ-INT-1481` and is ruled: option (a), the System Admin, an audited grant plus a register row pointing inward |
| `BR-INT-044` | Allowlist on the connection; refusal reveals nothing | PROPOSED — `C5` |
| `BR-INT-032` · `BR-INT-033` | Tender words and account strings from mapping rows; the envelope is a declared value | PROPOSED |
| CLAUDE.md hard rule 5 | The debits and credits handed over already balance — the posting service refuses anything else | CONFIRMED — *"already true"* |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | The partner collects yesterday's payments over three pages at 02:41 | Three `inbound_read` runs on S142 — *02:41 · Aclarian · payments · 412 records · page 1 of 3 · ••••7Q2F* …; the counts match what we hold (doc TC-INT-35, J54) |
| TC-2 | The unusual read: two years of history at 02:41 | Every request authorised; **the access log is the only place it shows** — 105 runs, 48,000 records, on S142 with the total in the header |
| TC-3 · **negative** | A read from `203.0.113.99` (outside the allowlist) | Refused **without revealing whether the account exists** — identical body for a real and an unknown account |
| TC-4 · **negative** | The 101st request in a minute against a limit of 100 | `429` with `Retry-After`; recorded as a refused read |
| TC-5 | `tenderType` on a Brazos Bend *Bank transfer* payment | Serves the partner's word from the mapping row (`ACHCHECK`); an unmapped tender serves *Other* and the row goes red on S143 |
| TC-6 | Pagination | The partner's envelope `{total_records: 1236, page: 2, page_size: 500, total_pages: 3}` — not the DRF `{count, next}` shape — from a declared `envelope = partner_paged` |
| TC-7 · **tenant isolation** | The partner's key, scoped to Brazos Bend, with `?company_id=<Lone Star Ridge>` | Answers as if the company were unknown, in the declared way |
| TC-8 · **register** | The subprocessor register view | Shows *Aclarian — reads payments and bills — authorised by … on …* as an **inward** relationship, derived from the live connection, not typed |
| TC-9 · **boundary** | A System Admin grants the partner authority | The grant is written to the connection AND to `audit_log`, and the register row derives from it — `OQ-INT-1481` CLOSED 2026-09-04 (a), so the boundary MOVED rather than being removed. ⚠ Previously *`NotImplementedError("OQ-INT-1481")`*. A clerk is refused by the permission class, not by an `if` |

⚠ **DATED AMENDMENT, 2026-09-17 — `TC-7`'s `?company_id=<Lone Star Ridge>` LEG IS SUPERSEDED (`CR-111-BRC04`, `BR-INT-070`).** PO verbatim, replying to a plain-English explanation that `company_id` selects nothing but that a mismatch is REFUSED today: *"you will ahve to remove company ID filter from all Apis - we cannot tell tenant ID outside our system"*. **`company_id` is removed as a filter from every partner API:** it is no longer required, it refuses nothing, it is still ACCEPTED and IGNORED (Invoice Cloud sends it on every call), and what was sent is RECORDED on the run row so a misconfigured partner stays visible without being refused. **`403 COMPANY_MISMATCH` disappears from every partner route** along with `_admit`'s check 7.

⚠ **THE TENANT-ISOLATION CASE THIS ROW EXISTS FOR IS NOT WEAKENED AND MUST NOT BE DELETED — IT IS REWRITTEN.** `company_id` never isolated anything: **key → connection → tenant → `app.tenant_id` → RLS `FORCE`** does, and that chain is untouched. **What `TC-7` must now assert is that the Brazos Bend key presented with another utility's `company_id` is served BRAZOS BEND'S OWN DATA, normally, and that the value they sent is recorded** — not that it is refused. The isolation the case is named for is still the thing being proved; the mechanism proving it was always the key, never the parameter.

**Supersession chain, stated not assumed (law 13):** PO 2026-09-16 *"company_id = tenant id"* (BUILT) → PO 2026-09-17 *"company_id = Keys will esnure it map to tenant ID"* (recorded, never built) → PO 2026-09-17 *"remove company ID filter from all Apis"* (current). Full record: `12-governance/02-decision-log.md` 2026-09-17 and `12-governance/change-requests/CR-111-BRC04-invoice-cloud-partner-api.md` §2.

**4 · Test Data** — *The partner's morning* (J54): Brazos Bend, 2026-09-02's 1,236 payments over three pages of 500; *the unusual read*: 2024-09-01 → 2026-09-01, 48,000 records at 02:41 (⚠ the blueprint's frame 46.2 draws *98,204*; the card's figure stands — `DEF-INT-3614`); allowlist `198.51.100.0/24, 203.0.113.7`; rate limit 100/min; tender mapping from `US-INT-037`.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `direction = inbound_read` · `trigger = partner` · `attempted` = records | S142 | design §2.13.6 | `integration_run` (two new enum values, no new column) | enum/int | system-derived | one row per page served |
| who (key hint) | S142 | `BR-INT-035` | `integration_run.summary` / `config` ref to the credential hint | text | system-derived | never the key |
| `envelope = partner_paged` | — | §2.13.5 | manifest per operation | enum | reference-data | `ours \| partner_paged` |
| `accountString` · `tenderType` · `projectType` | partner response | §2.2.6 Figure 22 | mapping rows / constant | text | computed | `projectType` constant *Utility Billing* |
| allowlist · rate limit | S141 | `C5` | `integration_connection.config` | CIDR list / int | user-input | — |
| register row (inward) | register view | `C33` | derived from `integration_connection` where `initiative = them` and `direction = out` | row | computed-display | never hand-maintained |

**6 · Acceptance**
- Given a partner collects on its own schedule, then every page is a row a manager can read, with who, when and how many.
- Given a read from an address not on the list, then it is refused and learns nothing.
- Given the ruling is open, then no real partner is served.

**7 · Finance Calculation** — N/A — the balanced pairs are the ledger's; this story only hands them over.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-INT-1481` | Who may authorise a partner to read | Enabling the connection | PO | **CLOSED 2026-09-04 — option (a)** |
| `OQ-INT-1480` | The account string's shape | `accountString` beyond the flat code | PO (finance) | **CLOSED 2026-09-04 — HELD.** *"we will use our GL code only"*: a partner needing `001.100.51200` is not served, permanently, and that is the ruling rather than a gap |
| `OQ-INT-12397` | How do our `id` values travel — their samples are integers and ours are `A-10432` | nothing; it confirmed what was built | PO | **CLOSED 2026-09-17** — *"a) they store our text exactly as we send it"*. No integer is minted and no second identity is kept |
| `OQ-INT-12403` | What does `remote_plan_id` carry, and on which payloads | the field on `consumer-info` | PO | **CLOSED 2026-09-17** — *"this rate plan ID for that account"*, on `consumer-info` ONLY. An account has no plan; a UNIT does, so it is resolved account → unit → the open assignment. A master account names no unit (`BR-CUS-1010`) and `null` is the true answer |
| `OQ-INT-12399` | What does `additional_data.payment_received` mean | the field, on `consumer-info` | PO / Invoice Cloud | **OPEN — the one of the six not answered.** A money field with three readings — the last payment, the total ever, or this cycle — and on an account that has paid **$142.18** this month against **$3,410.94** since it opened those are three different numbers. **The key is ABSENT from the payload, never null**, and a test asserts it appears nowhere |
| `OQ-INT-12400` | What does `projectType` say when one bill covers several services | `projectType` on every bill | PO | **CLOSED 2026-09-17** — *"a) always \"Utility Billing\""*. ⚠ **A FIXED CATEGORY, NOT A DESCRIPTION — deriving it from the bill's services is what was ruled against**, because a partner branching on it would get one answer for a house on one service and another for the house next door on two |
| `OQ-INT-12401` | Whose number does `remote_utility_id` carry | the field in every envelope | PO | **CLOSED 2026-09-17** — *"a) echo back whatever they sent"*. Nothing of ours goes into it, and when they send nothing the key is **omitted rather than null** |
| `OQ-INT-12402` | How does the payment feed reach us | the whole payment collection | PO / Invoice Cloud | **OPEN, AND THE QUESTION CHANGED SHAPE.** *"no this is not there - we will call htheir APis - we will ahnel those APis seperately - rember Invoice Cloud is both direction"*. ⚠ **THERE IS NO FILE** — `lockbox.py`, `PaymentImportBatch` and the staged-batch screen are NOT the path here. We call their APIs on a schedule; their document does not describe them, so nothing is invented. ⚠ Also blocked on `DEF-INT-5574` — a connector cannot declare both directions today |

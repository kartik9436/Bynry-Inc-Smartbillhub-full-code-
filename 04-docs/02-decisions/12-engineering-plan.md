# B12 — Engineering Plan (Eng-Lead / Full-stack profile, PO-directed 2026-08-08 — PLAN ONLY, no build yet)

> How the ratified corpus becomes code: architecture execution, the API error catalog, the story→code generation process, the PO-directed completion CHECKLIST, and worked examples. Companions: B8 conventions · B1 TD register · B11/B2-r16 (migration starts there) · HUMAN-GUIDE §9.

## 1. Backend engineering (Django)
Request path: subdomain → tenant-resolution middleware → `SET app.tenant_id` (TD-4) → RLS does the rest. Apps mirror modules; layering per B8 (api thin / services sole-writer / selectors read / models owned). Engines behind interfaces: `rating.engine` 🔒 and `ledger.posting` 🔒 are called, never reimplemented; their goldens (GT-1..61) are the contract. Async = Celery/Redis (TD-17): bill runs, imports, dispatcher (BR-NOT-005 pacing), archival, estimation — every job idempotent + resumable, progress rows for wizards. Reads: query services; period aggregates from NFR-26 close-rollups (TD-18). Partition-aware querying (tenant+period leading) on the big five. Migrations authored ONLY from B2-r16 + the 18-item checklist (B11) — never raw §2/§3.

## 2. Frontend engineering (React)
Feature folders per module, files named for screens. The IS-system as shared primitives: ONE config-driven DataTable (IS-5), ConfirmDialog (IS-6), state frames (IS-7/A18), download button (IS-11). OpenAPI-generated client from A11; TanStack Query; zod forms mirroring VAL codes; i18n catalog keys everywhere (TD-16 — server sends codes+params, UI renders language). Money display: server-formatted strings on documents, locale-formatted on screens, never client-computed.

## 3. API error catalog (every code maps to law; message_key → i18n; refusals write BR-AUD-018 attempt rows)
Envelope: `{code, message_key, params, field_errors[], br_ref, trace_id}`.
| Class | Codes | HTTP | Law |
|---|---|---|---|
| AUTH | AUTH-001 unauthenticated · AUTH-002 permission-denied (server-RBAC) · AUTH-003 tenant-unresolvable | 401/403 | BR-IDN-001/009, T6 |
| VAL | VAL-001 required · VAL-002 format · VAL-003 range · VAL-004 UoM-mismatch (blocks rating) · VAL-005 unknown-lookup | 422 | IS-7, OQ-004 closure |
| BIZ | BIZ-IMMUTABLE (issued/posted/cleared edit) · BIZ-IDEMPOTENT (duplicate run/webhook/file — payload carries who/when/link) · BIZ-LOCKED (currency · closed period · pinned template) · BIZ-WINDOW (reversal windows) · BIZ-APPROVAL (gate not satisfied) · BIZ-COMPLETENESS (plan-driven channel set) · BIZ-CAP (50k/10k/3,000) · BIZ-STATE (occupied unit · retired meter · last admin · IP self-lockout · plan-missing) · BIZ-SOD (wrong-role approver) | 409/422 | HR-4 · NFR-16 · BR-TEN-042/038 · BR-BIL-026 · BR-PAY-011 · BR-BIL-014 · BR-MET-049 · caps rules · state rules |
| SYS | SYS-DRIFT (tie-out breach → alert + red flag) · SYS-PROVIDER (adapter down; queue holds) · SYS-INTERNAL | 500/503 | BR-LED-007, BR-NOT-005 |
Every BIZ code has its T5 journey as the executable spec of the refusal. No endpoint invents a code; catalog additions = PR to this file.

## 4. Story → code generation process (agents write, humans ratify — same as docs)
Per story: **(1) PACKET** assembled mechanically from the repo: story §1–§8 + cited BR rows verbatim + field-map rows + journeys touching it (wiring index) + dataset/workbook figures + depends_on stories' handoff contracts + reverse-depends (impacted stories) + screen rows + error codes in scope. **(2) GENERATE** backend (models*, services, selectors, api, tests-from-TCs) and frontend (screen, components, tests) — *tables only per approved addenda; 🔒 paths stubbed `NotImplementedError("HUMAN-OWNED")`. **(3) SELF-VERIFY**: agent runs the full local gate set + the COMPLETION CHECKLIST (§5) and emits it filled into the PR body. **(4) HUMAN REVIEW** per HUMAN-GUIDE §9 + CODEOWNERS on 🔒. **(5) MERGE** flips frontmatter `status: done`; matrix code-refs column updated same commit. Generation order = build waves (W0 shell/i18n/audit-contract first); one story (or tight group) per PR.

## 5. THE COMPLETION CHECKLIST (PO-directed 2026-08-08) — closes EVERY story's code-writing; embedded in the PR template; CI validates the machine-checkable rows, the reviewer signs the judgment rows
**A. Traceability** ☐ header block present, all IDs resolve (code-trace lint) ☐ inline BR tags at every enforcement point ☐ PR line 1 = US-ID ☐ Impacts list == reverse-depends lookup
**B. Requirements** ☐ every §2 rule → code ref or explicit N/A ☐ every §3 TC → passing test named `..._tc<k>` ☐ §4 data as fixtures ☐ every §6 acceptance criterion demonstrably met (list them, tick each) ☐ §7 figures match workbook/GT VERBATIM ☐ §8 None (or OQ stubs raise with OQ-ID)
**C. Non-negotiables** ☐ no query without tenant scope; isolation suite green ☐ Decimal-only (grep-gate green) ☐ rounding at finalization only ☐ no UPDATE/DELETE path on append-only tables ☐ ledger writes via posting service only ☐ idempotency where the story requires it ☐ audit rows on every money action ☐ attempt-audit on refusals (BR-AUD-018) ☐ posted_at vs cleared_at both handled where money moves
**D. API** ☐ catalog codes only, each with br_ref + message_key ☐ RBAC server-enforced + denial test ☐ pagination on lists ☐ basis label on every money figure returned
**E. Frontend** ☐ capability row == rendered table config ☐ all IS-7/A18 states implemented ☐ i18n keys only ☐ tokens only ☐ generated client only
**F. Tests/CI** ☐ all gates green (lint/types/tests/golden/isolation/code-trace/coverage) ☐ ≥1 negative + 1 isolation test ☐ journeys touching this story runnable or stub-listed by ID
**G. Propagation** ☐ frontmatter → done only if ALL above ☐ matrix updated same commit ☐ any discovered gap → OQ minted, NEVER guessed
**H. Human** ☐ HUMAN-GUIDE §9 review done ☐ 🔒 files untouched or Eng-Lead-approved
A story with ANY unticked box does not merge. The filled checklist in the PR body IS the audit artifact.

## 6. Worked examples
### 6a. Service (backend) — issue, traceable + rule-tagged
```python
# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-005 (EP-BIL-01 §Issue)   Screens: S31
# Rules:    BR-BIL-011 · BR-BIL-022 · BR-BIL-024 · BR-BIL-026 · HR-4
# Tests:    US-BIL-005/TC-1..8 · GT-17 · Journeys: J2-step8, J19, T5-05
# Impacts:  ledger posting (US-LED-001) · delivery queue (US-NOT-002) · S30
# ───────────────────────────────────────────────────────
@transaction.atomic
def issue_drafts(run: BillRun, selected: QuerySet[Invoice], actor: User) -> IssueResult:
    run = BillRun.objects.select_for_update().get(pk=run.pk)          # racing issue clicks
    if run.status is not RunStatus.DRAFTED:
        raise BizError("BIZ-STATE", br_ref="BR-BIL-023", message_key="billing.run.not_draftable")
    for inv in selected.iterator():
        inv.invoice_no = numbering.next("BL", run.tenant)             # BR-BIL-022: tenant series
        inv.due_date = inv.bill_date + run.cycle.due_days             # BR-BIL-024
        inv.template_id, inv.template_version, inv.template_language = (
            templates.pin_for(inv.account))                           # BR-BIL-026: pinned FOREVER
        inv.status = InvoiceStatus.ISSUED                             # HR-4: append-only from here
        inv.save(update_fields=ISSUE_FIELDS)
        ledger.posting.post_invoice(inv)                              # 🔒 sole writer, balanced
        outbound.enqueue_bill(inv)                                    # BR-NOT-005: queue, never send
        audit.money_action(actor, "invoice.issue", inv)               # HR-7
```
### 6b. Test from a TC (name carries the ID; figures from the frozen dataset)
```python
def test_us_bil_005_tc3__issue_pins_template_and_totals_match_dataset(brazos):
    run = brazos.run_cycle("mixed", "2026-07")
    inv = issue_drafts(run, run.drafts.filter(account=brazos.acc1042), actor=brazos.admin).one()
    assert inv.total == Decimal("242.87")            # money-triples.csv: mixed,cycle — never hand-math
    assert (inv.template_version, inv.template_language) == ("v2", "en")   # BR-BIL-026
    with pytest.raises(BizError) as e: inv.save()    # HR-4 immutable
    assert e.value.code == "BIZ-IMMUTABLE" and e.value.br_ref == "BR-BIL-004"
```
### 6c. Frontend screen (capability row → config; i18n keys; generated client)
```tsx
// Trace: US-BIL-025 (EP-BIL-07) · S30 · BR-REP-006 (live vocabularies) · IS-5/IS-11
export function BillsList() {
  return <DataTable
    query={api.billing.listInvoices}                 // generated client, server pagination
    columns={S30_COLUMNS}                            // == capability row; user column-sets via prefs
    filters={{ bill_type: useLookup("bill_types"),   // BR-REP-006: never hardcoded
               status: useLookup("invoice_statuses") }}
    moneyBasisLabel="posting"                        // BR-REP-001: every money view labeled
    exportPer="IS-11" />;
}
```

## 7. Expanded engineering considerations
Observability: structured logs (tenant, trace_id, US-ID of the code path); metrics — queue depth/oldest, tie-out drift (=0 alarm), run duration (budget: full cycle < 5 min), provider error rates. Seeding: the Brazos Bend fixture family as the dev/demo seed (workbook-verified numbers make demos self-proving). Performance: N+1 lint in CI, partition-pruned queries proven by EXPLAIN tests on the big five. Security: no secrets in code (env + provider vault), dependency scanning continuous, pen-test annual (SC-4). Branch/release: trunk-based, story branches, migration-guard; releases gated on isolation+golden suites (release blockers by law). Rollout: waves W0–W8; W0 = shell + i18n wiring + audit write-contract + RLS middleware + CI gates — the foundations every later story assumes.

---
## Addendum r1 — PO rulings on the build process (2026-08-08)

### §8 Build-time exception protocol (PO: "unseen issues — how do we handle it?")
When coding surfaces something the corpus doesn't cover, classify and route — NEVER guess, NEVER stall the whole wave:
| Class | Example | Handling | Blocking? |
|---|---|---|---|
| **E1 Missing screen/design** | a flow needs a screen the prototype never drew | PM derives from the IS-1..11 standards + assigns the next free S-ID (the S68/S69–71 precedent); PO one-liner batch DAILY | No — build the derived version, flagged `DERIVED-PENDING-PO` in the trace header |
| **E2 Rule gap / contradiction** | two CONFIRMED rules collide in an edge case; a §2 rule is silent on a real input | STOP that code path only: mint OQ same-day, stub `raise NotImplementedError("OQ-###")`, keep building elsewhere (prime directive unchanged) | Path-blocking only |
| **E3 Technical unforeseen** | library limitation, perf surprise, provider quirk | Eng decision recorded as a TD row in B1 same-day; if it touches money/isolation semantics → escalate to E2 | No |
| **E4 Minor UI ambiguity** | spacing, ordering, empty-state wording | IS standards govern silently; no process | No |
Every E1/E2 lands in the decision log the day it's found; the PO sees ONE daily batch (the ratification rhythm continues into build). An exception discovered but not logged = process violation caught by the lifecycle tag (below).

### §3-expanded: FULL HTTP series contract (PO: "all 2xx/3xx/4xx/5xx handled")
| Series | Contract |
|---|---|
| **2xx** | 200 read/action result · 201 + Location on create · **202 + job_id for EVERY async op** (runs, imports, dispatch, archival — poll `/jobs/{id}`) · 204 delete/no-content |
| **3xx** | 304 + ETag on lookup/reference-data GETs (cheap caching); no other redirects inside the API (auth redirects live at the web layer) |
| **4xx** | 400 malformed request · 401 AUTH-001 · 403 AUTH-002 (role) — but **cross-tenant resources return 404, never 403** (existence must not leak, HR-1) · 404 not-found (incl. cross-tenant) · 405 wrong method · 408 request timeout · 409 BIZ conflicts (immutable/idempotent/locked/state) · 413 upload size cap (NFR-34) · 415 upload type not allowlisted · 422 VAL + BIZ semantic refusals · **429 + Retry-After** (per-tenant API rate limits, ops-config) |
| **5xx** | 500 SYS-INTERNAL (trace_id, no internals leaked) · 502/503 SYS-PROVIDER (adapter down — queues HOLD, nothing lost) · 503 maintenance window (announced) · 504 upstream timeout |
Client contract: the generated frontend client handles every row (retry w/ backoff on 429/502/503/504 idempotent GETs; job-polling on 202; ETag caching on 304; error envelope rendering for 4xx). A response outside this table = a bug by definition.

### §4-amended + §5A: LIFECYCLE TAGS (PO: "audit tag at the end of every code — marker that the entire process ran correctly"; human step DEFERRED)
Process step (4) human review is **deferred by PO direction** — replaced by machine verification + the lifecycle tag. Two boundaries survive unconditionally: 🔒 HUMAN-OWNED paths stay `NotImplementedError` stubs until a human writes them (hard law, not reviewable away), and the isolation/golden suites remain merge-blocking. Human ratification (HUMAN-GUIDE §9) resumes when the PO adds people; the tags make retro-review trivial.
**Every code file ends with a machine-STAMPED trailer** — written by the verifier tool, never by hand (CI recomputes and rejects a mismatched or hand-edited tag):
```python
# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-005@a3f19c2 (story+rules snapshot hash)
# generated: 2026-08-08T21:14Z by story-coder v1
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
# gates: ruff✔ mypy✔ tests 14/14✔ golden 33/33✔ isolation✔ code-trace✔ cov 91%✔
# exceptions: none        # or: E1 S115-DERIVED-PENDING-PO / E2 OQ-075 stubbed
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
```
`status` lifecycle: `GENERATED → VERIFIED-UNRATIFIED → RATIFIED` (when humans arrive) → `SUPERSEDED` (on regeneration; old tag retained in git history). The tag is the per-file audit certificate: checklist result, gate results, exception disclosures, packet hash (proving WHICH version of the story/rules the code was built from — a later rule change makes stale packet-hashes findable in one grep).

## Addendum r2 — Process-compliance enforcement (PO question 2026-08-09)

> PO: *"How do we ensure that every time the process we agreed is in compliance? Without that we will not be able to write the code — we will miss many points."*

**Principle: a process that depends on anyone (agent or human) remembering it is not a process.** Every agreement in this document is converted into a **machine gate that blocks the merge** — code physically cannot enter the repository without passing all of them. Compliance is enforced by construction, not by discipline or promises.

### The gate stack (G1–G19, ALL merge-blocking, run automatically on every code change)
**This table was G1–G12 until 2026-08-11 and the runner had nineteen gates in it** — a heading
that claims the set while `10-scripts/gates/run_gates.py` holds seven more is hard-won law 1 in
the process document itself, so the seven are written in below with their provenance. G1–G12 are
B12 Addendum r2 (PO-confirmed 2026-08-09); **G13–G16 were ratified 2026-08-11** (PO, option A:
*"Keep all four blocking — Nothing merges until each passes. Safest. - go with this"*);
**G17–G19 are Eng-Lead additions of 2026-08-11 and are ON the daily PO batch for the same
ratification** — they block merges today and that is stated here rather than assumed.
| Gate | What it enforces | Agreement it locks in |
|---|---|---|
| **G1 Packet gate** | Code exists only if generated FROM a packet; the lifecycle tag's packet hash must equal the hash of the CURRENT story+rules files | §4 generation process |
| **G2 Code-trace lint** | Every service/api file carries the Trace header (US-ID, S-IDs, BR-IDs); every cited BR exists; every CONFIRMED rule the diff touches is cited somewhere | B8 traceability standard |
| **G3 Checklist validator** | Checklist A–H machine rows are RECOMPUTED by the tool, never trusted from the tag | §5 completion checklist |
| **G4 Golden harness** | Engine outputs equal the frozen B4/B5 figures (33 assertions) + the 245-row expectation dataset | Finance freeze ❄ |
| **G5 Isolation suite** | Every story's isolation TC + an RLS probe (cross-tenant access = empty/404, never data, never 403) | HR-1 tenant scoping |
| **G6 Forbidden-pattern greps** | float on money · UPDATE/DELETE on immutable tables · writes into another module's tables · raw SQL outside selectors · wall-clock time in money paths (event-time law BR-TEN-043) | HR-2/3/4/5, module boundaries |
| **G7 🔒-path guard** | Diffs touching human-owned files (RLS policies, rating math kernel, idempotency keys, ledger posting, rounding, migration ordering) by an agent are auto-rejected; those files may contain only `NotImplementedError` stubs until a human commits them | "Do NOT touch without a human" |
| **G8 Stub honesty** | Every `NotImplementedError("OQ-###")` must cite an OPEN OQ. A CLOSED OQ with a surviving stub = stale → reject. An OPEN OQ whose path contains real code = agent decided a question → reject | Prime directive |
| **G9 Error-envelope conformance** | Every endpoint's responses ∈ the §3 catalog + HTTP-series table; shapes validated against the OpenAPI contract | §3 error catalog |
| **G10 Coverage + TC-named tests** | Services ≥85%; every TC in the story exists as a test literally named `test_TC_n` — a missing TC is findable by grep | B8 |
| **G11 Lifecycle-tag stamp** | Trailer is recomputed by the verifier tool; absent or hand-edited tag → reject | Addendum r1 |
| **G12 Journey gate (wave-scoped)** | Every E2E journey whose stories are all built must run green before its wave closes | E2E catalog (300) |
| **G13 Unwired props** (ratified 2026-08-11) | A component prop with no non-test caller is dead UI — built, styled, fully tested and never given its data | DEF-007..010, the largest defect category |
| **G14 Prototype conformance** (ratified 2026-08-11) | Shipped copy and tab labels match `05-prototype/`; no converted screen draws its own page head | hard-won law 6, DEF-021 |
| **G15 i18n parity** (ratified 2026-08-11) | The eleven catalogues carry the same key set as `en.json`, and a value left in English is named one by one in an allowlist | BR-SHL-041, DEF from the S1 port |
| **G16 NFR-24 partition coverage** (ratified 2026-08-11) | Every table NFR-24 names is created `PARTITION BY`, or carries an EXPIRING exception citing a live OQ | NFR-24 "No exceptions", DEF-031 |
| **G17 Duplicate IDs** (2026-08-11, pending ratification) | An ID the repo references by ID is DEFINED once — OQ · DEF · US · BR · GT · ADR · EP · S. Two lanes minting one number is otherwise found by accident, three times in a day | DEF-053 (with DEF-052's cross-file BR case measured and explicitly out of scope) |
| **G18 i18n call sites** (2026-08-11, pending ratification) | The catalogues against the CODE, both ways: every catalogue key has a call site, every `t()`/`message_key` resolves to a key. G15 compares catalogues to each other, which is only as strong as `en.json` being right | DEF-036 + DEF-041 + DEF-049 — three defects, one missing comparison |
| **G19 Environment names in copy** (2026-08-11, pending ratification) | No catalogue value names a host, URL, `localhost` or IP. Carries NO domain list — it matches the SHAPE, because the 2026-08-10 sweep searched for the dead domain and could not see the live one | DEF-050 |

### Who watches the watchers
- The gate scripts are themselves protected: they live in `10-scripts/` + CI config, and any change to them goes into the daily PO batch exactly like an E1 — a silently weakened gate is a process violation by definition.
- `grep "status: GENERATED"` finds any file that skipped verification; a stale packet hash finds every file whose story/rules changed after its code was generated — one command, whole repo.
- Nightly full run of the entire stack (gates + golden + isolation + built journeys) on the main branch, so drift cannot hide between changes.
- The `exceptions:` field of every lifecycle tag is cross-checked against the decision log — an exception in code that never reached your daily batch is itself a gate failure.

**Net effect: a point cannot be "missed" silently.** It is either (a) caught by a gate → the code never merges, or (b) a genuine gap in the documentation → it surfaces as an E2 STOP + a new OQ, i.e. it reaches the PO instead of disappearing into code.

Status: r2 records the enforcement design. The gate scripts are the FIRST code of W0 — built and proven before any feature code exists for them to guard.

## Addendum r3 — PO rulings 2026-08-09: simplicity law · gates confirmed · wave plan · build-phase test automation · component checkpoint

**(1) THE SIMPLICITY LAW (PO: "human will also look at this code, so please do not over-complicate it").** Recorded as **B8 LAW 0** — boring explicit code beats clever code; abstraction earns its place on the third use, not the first; a service reads top-to-bottom as the story's flow in glossary vocabulary; a junior developer follows it without a tour guide; simplicity beats DRY on conflict. Every generation packet carries LAW 0; the ratification reviewer test is "could the PO's future hire read this cold?"

**(2) Gate stack G1–G12 (r2): PO AGREED 2026-08-09** ("I agree with this approach — ensure it is updated"). r2 is now CONFIRMED process law, not proposal. Gate scripts remain the first code of W0.

**(3) Build order corrected (PO: "you are missing assets"):** Shell+tokens → Settings/lookups → Plans&Rates → Premises/Units → **Assets (meters)** → Accounts → Reads(+estimation) → Billing run → Payments → Finance → Reports → Public. CLAUDE.md + 04-docs/README updated. Assets epics were already wave-assigned (W1) — the prose order now matches the wave data.

**(4) THE WAVE PLAN (W0–W8, computed from story frontmatter — 227 stories, all assigned):**
| Wave | Theme | What gets built | Epics | Stories |
|---|---|---|---|---|
| **W0** | Foundations | Gate scripts G1–G12 → A11 conformance audit → **component checkpoint (B13/13a, PO reviews before feature code)** → app shell · shared table/forms/wizard/states frameworks · i18n wiring · RBAC gating · sign-in/users/security policies · tenant provisioning + onboarding (S110–S114) · ALL Settings (company/regional, services & UoM, reference data, numbering) · audit write-contract · RLS middleware (policies 🔒 human) | 16 | 39 |
| **W1** | Data backbone | Plans & Rates (plans, schedules, charge codes/taxes, versioning + bulk updates) · Premises & Units · Routes & Cycles · **Assets/meters** (registry, detail, lifecycle, bulk import) · audit viewer (S61) | 11 | 30 |
| **W2** | Customers & reads | Accounts (list, lifecycle/move-in-out, detail, brownfield import) · read import wizard · read validation & flags · net-meter reads | 7 | 28 |
| **W3** | Billing engine | Bill run (S31) · invoice anatomy + GL stamping · bill types (first/final/ad-hoc/back-bill/penalty) · templates & queue-based delivery · bills list/void · estimation & true-up · platform outbound queue + dispatcher · template rendering engine · **rating engine core 🔒** · capacity charges | 10 | 33 |
| **W4** | Money in | Record payments + purpose model · allocation · NSF/reversals/refunds/write-offs · outstandings & collections · payment plans + notices · autopay intents + receipts · budget billing · account action modals + plan wizard · notice/receipt/contract rendering · delivery ops (bounces/returned mail) · connections surface + bank/lockbox file channels | 13 | 39 |
| **W5** | Finance & reports | Ledger posting consumption + dimensions · chart of accounts + GL mapping/export codes · S36 Revenue & AR + trial balance · manual JEs (draft→post, 3 types) · tax remittance + month close + accounting export · deposit batches + bank reconciliation · corrections workflow (single + bulk) · report center + canned + builder + scheduled + dashboards · comms connections (BYO/ESP) · audit retention job | 13 | 54 |
| **W6** | Email ACTIVATION | **Zero new stories** — flips ON customer email through the queue already built in W3: bill email, receipts/notices, scheduled-report email, external recipients (confirm step), staff alert catalog, bookkeeper copy. Connection ≠ activation (BR-INT-007) — a tenant connects BYO/ESP, sending activates | 0 | 0 |
| **W7** | Payment rails | Stripe/Plaid seams live: real autopay charging, card refunds, payment webhooks (schema + `webhook_key` already provisioned, 🔒) | 1 | 1 |
| **W8** | v1.1/v2 unlocks | Change Plan wizard · Twilio SMS · QBO/Xero live sync · MDM · SSO (per BR-INT-001 visible-but-later matrix) | 1(+seams) | 3 |
Wave close rule: migrations → backend stories → frontend stories → **that wave's activated journeys green (G12)** → close. Totals: 227 stories / 72 epics.

**(5) TEST AUTOMATION DURING BUILD (PO question 2026-08-09):** Tests are not a phase — they are generated WITH the code, in the same packet, and run by machines from day one.
- **Story TCs → automated tests, same packet:** every TC ships as a test named for it (`test_us_bil_005_tc3__…`) in the same PR as the code — G10 rejects a story whose TCs aren't all present. TCs are never "executed manually later."
- **Money truth, always on:** golden harness (33 assertions) + the 245-row expectation CSV run on EVERY change (G4) — the engine must reproduce the frozen figures forever.
- **Isolation, always on:** every story's isolation TC + RLS probes on every change (G5); red = release blocker, no override.
- **The 300 E2E journeys automate INCREMENTALLY:** the generated wiring index knows which stories each journey needs; a journey ACTIVATES the moment its last story is built. UI journeys run in Playwright driving the real screens; engine journeys run at API level; both assert against the expectation CSV (docs and tests physically cannot drift). A wave cannot close with an activated journey red (G12). By W5 close, all 300 run nightly.
- **Fixtures:** the Brazos Bend seed family (workbook-verified figures) is the one seed for dev/demo/tests — demos are self-proving.
- **Cadence:** per-PR = touched-module tests + golden + isolation (always); nightly = the full stack (all gates, all activated journeys) on the main branch.

**(6) COMPONENT CHECKPOINT (PO: "I will first build a list of all frontend and backend components and mark what is available and what is not available, make it as check point and then move to the build"):** B13 (`13-component-registry.md`) = the component inventories with availability status; 13a (`13a-screen-component-map.md`) = the per-screen map. **B13/13a is a formal PO checkpoint: reviewed and acknowledged BEFORE feature code begins.** Status cells in B13 flip ✅ as components land — it doubles as the live build tracker.

## Addendum r4 — AGILE RELEASE PLAN (PO ruling 2026-08-09: "current approach looks like waterfall; we need agile — 3 or 4 phases, each phase fully deployable, so we can see how it is shaping up; otherwise issues in between and we will not know")

**Accepted — the diagnosis is correct.** Waves W0–W8 remain the *dependency order* (you still cannot bill before plans and reads exist), but they are NOT the delivery plan. Delivery = **four releases, each ending in a deployed, seeded, clickable product** the PO walks through. Issues surface at the end of every release (and continuously inside it), never at the end of the project.

### The four releases
| Release | Waves | What the PO can DO in the deployed product at release end | Release gate |
|---|---|---|---|
| **R1 — "Set up your utility"** | W0+W1 | Sign up at the public page → tenant provisions → sign in → invite users/roles → complete ALL Settings (company, services & UoM, reference data, numbering) → build Plans & Rates end-to-end → create Premises/Units, routes/cycles → register meters (assets) with lifecycle + bulk import → audit viewer shows every action. Seeded Brazos Bend fixture alongside a blank tenant | Compose stack boots clean · R1-activated journeys green (G12) · PO walkthrough sign-off |
| **R2 — "Bill"** | W2+W3 | Open accounts, move customers in, import + validate reads (flags, estimation), run the FULL bill-run wizard on the fixture month, issue real bills (correct money per the frozen figures), render/queue bill documents, see bills on the account. **The human-owned kernels (rating engine 🔒, posting 🔒, RLS policies 🔒) are this release's critical path — scheduled FIRST in R2** | Golden figures reproduced by the ENGINE (G4 on live code) · isolation suite green (RLS live) · walkthrough |
| **R3 — "Collect & close the books"** | W4+W5 | Record/import payments, allocation, NSF/reversals/refunds, collections + plans, budget billing, deposit batches + bank rec, ledger with dimensions, manual JEs, tax remittance, month-end close, accounting export, ALL reports + the S7 dashboard | Full meter-to-cash journeys green incl. month-close (J19-class) · trial balance ties out · walkthrough |
| **R4 — "Switch on the world"** | W6+W7+W8 | Email activation (bills/receipts/notices/scheduled reports through the queue), payment rails (real autopay, card refunds), v1.1 unlocks per matrix | Activation journeys green · provider sandbox proofs · walkthrough |

### Addendum r9 — the R2/R3 boundary MOVED: payments come into R2 (PO ruling 2026-08-11)

**PO verbatim: _"We will have to complete all Payment related items to complete the billing"_.**

The table above ends R2 at an issued, rendered, queued bill and puts every payment
item in R3. This ruling moves that line. **A bill you cannot pay does not close the
meter-to-cash loop, and a balance no screen can show is not a billing product.**

The evidence had been accumulating inside R2's own open questions all session, and
every one of them dead-ends at the same missing module:

| What R2 could not answer | Why | 
|---|---|
| Is this bill past due? (OQ-113) | *Unpaid* is the payments position and **there is no payments table** |
| Which class does a payment meet first? (OQ-109) | The order is ruled and `allocation.py` executes it **against invoices that can never receive a payment** |
| Where does the money land in the books? (BR-BIL-011) | Billing emits a balanced posting handoff to `apps/ledger/posting.py` — **the sole journal writer in the system, and a nine-line stub that raises** |

**Measured state at the moment of the ruling**, recorded so the size of the change is
not re-litigated later: `apps/payments/models.py` is **3 lines and defines no tables at
all**; `api.py`, `webhooks.py` and `lockbox.py` are 1 line each; `reconciliation.py` is 2.
The one substantial file is `allocation.py` — **938 lines of tested math with nothing to
allocate**. `apps/ledger/posting.py` is **9 lines and raises `NotImplementedError`**.
This is not a wiring job.

**THE BOUNDARY IS NOT YET RULED.** *"All payment related items"* has two defensible
readings and they are materially different bodies of work:

| | Reading | Contents |
|---|---|---|
| (a) | The closed loop | Record + import a payment · allocate it (math built) · post it to the ledger · show the balance · make past-due answerable |
| **(b) ✅ RULED** | **All of R3's collect half** | (a) **plus** NSF / reversals / refunds · collections + payment plans · budget billing · deposit batches + bank reconciliation |

**BOUNDARY RULED 2026-08-11 — reading (b). PO verbatim: _"B All of collections A, plus
bounced payments, refunds, collections, payment plans, budget billing, bank
reconciliation"_.**

So R3's **collect** half moves wholesale into R2. What REMAINS in R3 is the **close the
books** half:

| Moves to R2 (ruled) | Stays in R3 |
|---|---|
| Record / import payments | Ledger with dimensions |
| Allocation (938 lines of math, currently unreachable) | Manual journal entries |
| Ledger posting service (**the sole journal writer — a 9-line stub that raises**) | Tax remittance |
| Balance + past-due answerable (unblocks OQ-113) | Month-end close |
| NSF / bounced payments · reversals · refunds | Accounting export |
| Collections + payment plans | All reports + the S7 dashboard |
| Budget billing | |
| Deposit batches + bank reconciliation | |

**This is the largest single scope item in the project to date**, and after it R2's
remaining work is mostly payments rather than mostly billing. Stated plainly rather
than discovered later: **several of these carry their own money law and their own open
questions** — NSF fees, refund routing, budget-billing true-up and bank-reconciliation
matching are each rule-bearing, not mechanical. The implementing lanes surface those as
OQs for the PO rather than choosing.

R2's release gate must widen accordingly: the old gate (golden figures reproduced by
the engine · isolation suite green · walkthrough) no longer covers a release that now
ends at a reconciled bank statement. The gate itself is not re-drafted here — it is a
PO/Eng-Lead item flagged by this addendum.

### Inside every release — continuous visibility (not just at the end)
1. **Preview deploy per landed epic**: every time an epic's stories merge, the compose stack redeploys the demo environment; the PO gets a short "what you can click now" note. Never more than a few days between visible increments.
2. **B13 is the live tracker** — status cells flip ✅ as components/stories land; the PO reads build progress from the same checkpoint file they ratified.
3. **Nightly full gate + activated-journey run** — regressions surface the morning after, not at release end.
4. **The daily PO batch continues** (E1/E2 exceptions, 🔒 dispositions) — the ratification rhythm IS the agile cadence.

### What deployable means here
`docker-compose up` from the repo root brings up Postgres 16 + Redis + backend + frontend, migrated and seeded with the Brazos Bend fixture family (workbook-verified numbers make every demo self-proving). A hosted demo URL (09-infra) is an R1 deliverable so the PO clicks a link, not a terminal.

Wave numbering in stories/epics is unchanged (it encodes dependencies); release membership is derived W→R per the table. G12 becomes release-scoped: `run_gates.py --wave-close` runs per release boundary and per wave inside it.

## Addendum r5 — 🔒 conversion (PO ruling 2026-08-09: "AI will do it; we will review it later as human")
The stub-until-human law for the sensitive paths (rating engine · ledger posting · RLS policies · money rounding · idempotency keys · migration ordering · webhook keys) is **converted**: AI authors these files now; human review is deferred, not deleted. The protection converts with it:
1. **AI implements SIGNED law only** — B4 ❄ math, B2 key shapes, B2 §3 RLS template, B11/r16 migration checklist. The rules stay human/finance-signed; AI writes their implementation. An unsigned gap in a 🔒 area is still an E2 stop (OQ + stub), never a guess.
2. **Every implemented 🔒 file** carries `HUMAN-OWNED` + `HUMAN-REVIEW-PENDING` in its docstring and a row in `12-governance/09-human-review-ledger.md` (what/when/machine evidence). **G7 fails any guarded file with real logic missing either.** Lifecycle status may never reach RATIFIED without a human sign-off recorded in the ledger row.
3. **Machine guardians per kernel** (merge-blocking today, human reviews later from the ledger): rounding/rating → G4 golden 33 + 245-row expectation CSV · posting → balanced-pair + subledger tie-out tests (drift = release blocker, BR-LED law) · RLS → isolation suite + cross-tenant probes (G5) · idempotency → double-fire tests · migrations → migration-guard CI + B11 anchoring checklist consumed at authoring.
4. **Consequence for the release plan (r4):** R2's critical path unblocks — the rating engine, posting service, and RLS policies are AI-authored in R2's kernel lane (first thing in R2), with the ledger as the standing human-review queue. This also answers the migration question: AI authors migrations from B2 r16 + the 18-item checklist under migration-guard.

## Addendum r6 — R1 deliverable added (PO 2026-08-09): DevOps handover architecture
At R1 the PO hands deployment to a HUMAN DevOps engineer. Deliverable: `09-infra/01-deployment-architecture.md` — written for that human (plain language + diagrams-as-text, no repo archaeology required): topology (PG16/Redis/Django+Celery/frontend), environments (demo/staging/prod), env-var + secrets contract, migration & RLS bootstrap order, backup/restore + retention (per B6 NFRs), scaling notes (partition plan, queue depths), monitoring/alerts (tie-out drift =0, queue oldest, provider errors), TLS/subdomain routing (tenant-per-subdomain), and the release runbook (deploy → migrate → seed → gates → journeys → walkthrough). Living doc: updated at every release boundary; R1 walkthrough includes handing it over.

---

## Addendum r7 — two capabilities added to R2 (PO rulings 2026-08-10)

The PO added **tenant custom fields** and an **eleven-locale expansion** and ruled both into R2. Neither reopens R1; both are additive to the W2/W3 wave content already scheduled.

### r7.1 · What lands, and where

| Slice | Epic / stories | Module | Note |
|---|---|---|---|
| Custom-field registry, S8 card + management, placement editor, deactivate lifecycle, cached registry endpoint | **EP-TEN-09** · US-TEN-014..017 | tenancy | New epic. Reuses the S8 Reference-data framework; **no new screen ID minted** |
| Shared render component: capture, display, list columns, CSV export | **EP-SHL-07** · US-SHL-015..016 | platform-shell | New epic. One component, eight entities, nine slots |
| `invoices.custom_snapshot` stamped at issue | US-BIL-028 (EP-BIL-02) | billing | **Stamps in R2 though nothing reads it until R3** — see r7.2 |
| Eleven locales + lazy per-locale chunks | US-SHL-017 (EP-SHL-05 r2) | platform-shell | Bundle is 53% translation JSON today; at eleven it would approach 2 MB |
| `es-419` normalisation + S48 picker + the MT guard | US-SHL-018 (EP-SHL-05 r2) | platform-shell | Migration is time-sensitive — see r7.2 |
| Custom fields as template variables | US-NOT-016 (EP-NOT-02) | notifications | **R3** — needs the templates that ship there |

Schema: **B2 addendum r17** (`custom_field`, `custom_data` on eight tables, `invoices.custom_snapshot`, DB-17). Gate: **G6 gains the DB-17 rule** — `custom_data` is a merge-blocking failure under `apps/rating/` absolutely and under billing/ledger/payments outside one allowlisted module.

### r7.2 · Two one-way doors, both in R2 on purpose

1. **The invoice snapshot.** You cannot retroactively reconstruct what an account looked like six months ago. If R2 issues real invoices with no snapshot column, every invoice from that period is permanently unable to render custom fields — and the tempting repair is a live join to master data, which rewrites issued documents without ever running an UPDATE. Stamp early, render later. The master-data columns have no such door: adding `custom_data DEFAULT '{}'` later is a clean, non-breaking migration.
2. **`es-MX` → `es-419`.** `tenant_settings.default_language`, `accounts.preferred_language` and `user_preferences` all store the code. Today those columns are empty and this is a rename; once Spanish-speaking customers are onboarded it is a live migration on customer data.

### r7.3 · The cost that is not on the schedule

Every feature from R2 onward writes its strings into **eleven** catalogs instead of five — 2,063 keys per catalog, 12,378 strings for the six new languages at the outset. That is a permanent multiplier on every subsequent release, not a one-time project. Machine translation makes the first pass cheap (PO ruling); it does not remove the multiplier, and it does not extend to customer-facing documents (BR-SHL-043, OQ-077).

### r7.4 · Blocking OQs

**OQ-075** (deactivate vs published template) · **OQ-076** (PII stamped into immutable rows) · **OQ-077** (machine-translated customer documents). Per the prime directive these are coded to the boundary and stubbed `NotImplementedError("OQ-0xx")` — never resolved by choosing a value.

## Addendum r10 — THE R2 RELEASE GATE (Eng-Lead draft 2026-08-15; **RULED BY THE PO the same day — this is now the gate**)

Addendum r9 moved payments wholesale into R2 and then said, in its own words:
*"R2's release gate must widen accordingly… The gate itself is not re-drafted
here — it is a PO/Eng-Lead item flagged by this addendum."*

**Nobody drafted it.** For four days the release has had no written definition
of done, which is why "all stories built" and "shippable" have been drifting
apart without anything measuring the gap. This is that draft. **It is a
proposal, not law** — every line is for the PO to accept, cut or change, and
nothing here is binding until they rule.

### Why the old gate no longer covers this release

The R1-era gate was three items: *golden figures reproduced by the engine ·
isolation suite green · walkthrough*. That was written for a release ending at
an ISSUED BILL. This one ends at a reconciled bank statement, carries the whole
collect half, and now carries accounts-payable capture as well. Two of those
three items are still right and neither is sufficient.

### The proposed gate — nine items in three groups

**A · THE MONEY IS RIGHT (non-negotiable, no override)**

1. **Golden harness 33/33 reproduced by the ENGINE on live code**, not by
   fixtures. *(Status: ~~passing~~ — **CORRECTED 2026-09-01, DEF-2846. This item
   claimed the thing it was written to prevent.** The harness's 33 are DOCUMENT
   self-consistency: `10-scripts/03-golden-verify.py` recomputes B4/B5's own
   figures and imports no application code, so a green 33/33 says nothing about
   live code and cannot go red when the engine drifts. What reproduces figures
   BY THE ENGINE is `06-backend/tests/golden/`, and it is **engine-verified: 14
   of the 61 signed GTs** — GT-1..11, 16, 24, 47. So this criterion is met for
   14 and unmet for 47. Read the number from `10-scripts/gates/
   g64_golden_engine_coverage.py --report`, never from a status line.)*
2. **Trial balance ties out** on the seeded fixture family, and every journal
   entry balances. *(Status: passing — the book foots 598.69 = 598.69.)*
3. **No money figure crosses any boundary without its currency.** Hard rule 2
   is a PAIR. *(Status: FAILING — DEF-099, two endpoints serve amounts with no
   CHAR(3) code, and no gate reads an API body for it.)*

**B · THE ISOLATION IS REAL (non-negotiable, no override)**

4. **The isolation suite runs against REAL POSTGRES, not SQLite**, and its skip
   count is reported alongside its pass count. *(Status: UNPROVEN as a release
   claim — the last run was 36 passed and **105 skipped**; the skips are the
   Postgres-only RLS probes, so the developer database proves almost none of
   hard rule 1.)*
5. **Every tenant-scoped table has a policy**, proved by the catalogue sweep and
   not by a migration's say-so. *(Status: passing.)*

**C · THE PRODUCT ACTUALLY WORKS (the group that has never been run)**

6. **At least one full meter-to-cash journey ACTIVATED and green** — read →
   rate → bill run → issue → deliver-or-record-the-absence → payment →
   allocation → ledger. *(Status: 0 of 304 journeys activated. Nothing in this
   product has ever been proven end to end.)*
7. **One month-close journey activated and green**, ending in an export batch.
   *(Status: not activated.)*
8. **A prototype walk of every screen a user can reach**, with deviations
   listed. *(Status: not done for this wave. Hard-won law 6 exists because nine
   defects were found this way and by nothing else.)*
9. **A deploy dry-run on real Postgres**: migrations forward AND backward, RLS
   bootstrap order, and defaults proved to FAIL CLOSED. *(Status: not done.)*

### The three questions — ANSWERED 2026-08-15, verbatim

> *"Does 'issue real bills' mean the customer receives one? **No** → the journey
> ends at a rendered document and this is already satisfied.; What's the defect
> bar? **zero open critical, and every major either fixed or explicitly accepted
> by you with the reason recorded**; Do the four queued finance re-signatures
> block R2? **No**"*

**(a) DELIVERY IS OUT, BY DECISION.** Item 6's journey ENDS AT A RENDERED
DOCUMENT. No provider adapter is required on any channel, print included. The
first deployment produces bill documents a human downloads and sends — stated
plainly because it is now expected behaviour rather than a gap. The two parked
notification seams are **accepted, not owed**, and every dispatch cycle
reporting the adapter absent is correct output. ⚠ **US-NOT-003 TC-1 (a print
batch reaching `sent`) is unsatisfiable in this release by ruling** and must be
re-scoped rather than left failing.

**(b) THE DEFECT BAR IS ADOPTED AS PROPOSED**, including *silence is not
acceptance*. ⚠ **The critical needs its own ruling and is raised, not assumed:**
DEF-048 is a mutilated RLS file in a HISTORICAL COMMIT, not a live hole — the
working tree is correct and the policy is present at HEAD — so "fix it" is not
available in the ordinary sense. Its code half is done; the process half is
open. It must be split or explicitly accepted; it cannot be closed by assertion.

**(c) THE FOUR FINANCE RE-SIGNATURES DO NOT BLOCK R2.** Each refuses by name
rather than guessing, which is what makes that safe. **They do block the first
release that can post a settle-up**, and the budget-variance one becomes real
six months after the first customer enrols.

### The original three questions, as put



**(a) DOES "ISSUE REAL BILLS" MEAN THE CUSTOMER RECEIVES ONE?** No provider
adapter exists for any channel, print included, because the integrations module
is out of this wave. The chain runs read → rate → bill → issue → render → STOP.
If the answer is yes, a minimal print/PDF adapter re-enters scope and item 6's
journey must reach a delivered document. If no, item 6 ends at a rendered
document and this is already satisfied.

**(b) WHAT IS THE DEFECT BAR?** 31 defects are open (1 critical, 18 major). The
critical one is a bad commit in history rather than a live hole. Proposed:
**zero open CRITICAL, and every MAJOR either fixed or explicitly accepted by
the PO with its reason recorded.** Silence is not acceptance.

**(c) WHAT BLOCKS ON A FINANCE RE-SIGNATURE?** Four items are queued: the
budget-variance account, the concession account, the tax-split addendum, and
the cost-of-service chart section. Each currently REFUSES BY NAME rather than
guessing, so none blocks a deploy — but the budget one becomes real six months
after the first customer enrols. Proposed: **none blocks R2; all four block the
first release that can post a settle-up.**

### What this gate deliberately does NOT require

Stated so the omissions are choices rather than oversights: reports and
integrations (PO-ruled out of this release), payment rails, email delivery,
template versioning, and the 24 open questions that are non-blocking by their
own rows. **A gate that requires everything is a gate nobody can pass, and one
that requires nothing is not a gate.**

### Status

**RULED 2026-08-15 — this is the gate.** On the measurements taken the same day
against a still tree (20/20 gates, backend 2400 passed / 0 failed, frontend 1042
passed, golden 33/33): the release **passes group A on two of three** (the
currency-on-the-wire item fails), **cannot yet CLAIM group B** (36 isolation
tests passed and 105 skipped — the skips are the Postgres-only RLS probes), and
**has never attempted group C** (0 of 304 journeys activated).

Ruling (a) makes item 6 reachable without any adapter work, so group C is now
attemptable rather than blocked.

---

## Addendum r11 — THE STORY→CODE PROCESS, REVISED (PO ruling 2026-08-16)

**This supersedes §4's five-step cycle. It is the process every lane follows from
2026-08-16 onward, and `CLAUDE.md` points here so no session can miss it.**

The PO's two additions are the two that were missing, and they are the same hole
seen from both ends: §4 told a lane how to READ the repo and never asked whether
what it read was still true, and it told a lane to write code and never said
where the KNOWLEDGE goes.

**The evidence, measured on the day this was ruled: 117 of 132 commits touched an
open question, the decision log or the defect register — roughly 89% of the
work.** Write-back was never an edge case. It was the main event, and the process
did not mention it once.

### 0 · CHECK THE PACKET IS CURRENT  *(new — PO 2026-08-16)*

Before assembling anything, read the four places the repo changes underneath a
lane, and ask the question beside each:

| Read | Asking |
|---|---|
| `12-governance/01-open-questions.md` | Is anything I need still open — or **ruled since this doc was written?** |
| `12-governance/02-decision-log.md` | Was this decided recently, in words the module doc has not caught up with? |
| `12-governance/10-defect-log.csv` | Is this already filed, already fixed, or a known trap? |
| `12-governance/11-change-requests.md` · `10-scripts/gates/surface_debt.txt` | Has scope moved? **Does that sentence still match the code?** |

**Every documentation failure of 2026-08-16 would have been caught here**, which
is why it is step 0 and not an optional courtesy:

* the PO's deposit-code ruling of 12 Aug reached every *document* that day and
  the *code* not at all — the code still refused the anniversary batch citing the
  question as OPEN, three days after it closed;
* four of seven `surface_debt.txt` sentences named the WRONG FEATURE and sent a
  lane at work already shipped — the counts were right, the sentences were not,
  and **nothing automated reads a sentence**;
* two documents claimed the collections-ladder settings did not exist, a day
  after they landed.

**Keep this step human.** Its whole value is a person reading prose for truth.
Automating it produces a check that passes without anyone having read anything,
which is the failure it exists to prevent.

### 1 · PACKET

The module folder (`04-docs/05-modules/<n>-<module>/`: overview, business rules,
field map, flows, user stories, epics, worked examples) **+ the cited shared law**
(`02-decisions` money math ❄ / golden tests ❄ / schema / NFRs · `03-contracts` ·
`08-qa/01-e2e` journeys · `05-prototype`) **+ what step 0 found.**

Rules are quoted VERBATIM, never summarised. Lanes have twice refused an
orchestrator's instruction and been right, both times because the orchestrator
paraphrased a rule and the lane read it.

⚠ **AND THE PACKET INCLUDES THE READ THAT ALREADY EXISTS — PO RULING
2026-09-04, ADDED BECAUSE WE BUILT A SECOND ONE.** Verbatim: *"all the services
that are required for Consumer portal - you will find it same set of services,
endpoints are already available for Accounts - account details view"*, said the
same hour as *"We are mainiting last 12 month usage details on account - you
canuse it"*.

**So before writing ANY new read, find the one the staff Account details view
already uses.** Two places, and they take one command each:

  * `06-backend/apps/*/[a-z]*_reads.py` — the read models (`monthly_usage_reads`,
    `connection_reads`, `service_request_reads`, `move_reads`,
    `disconnect_reads`, `transfer_reads`);
  * every account-scoped route in each module's `api.py` —
    `accounts/{id}/usage`, `/payments`, `/open-bills`, `/payment-plans`,
    `/payment-plans/preview`, `/collections`, `/notes`, `/discounts` and more.

Then read the SCREEN built on it under `07-frontend/src/features/`. A second
surface of the same facts is written in a customer's words, **never with a
second arithmetic** — the clerk and the customer must not be able to get
different answers to the same question.

⚠ **WHAT THIS COST, AND WHY IT IS A PROCESS STEP RATHER THAN A REMINDER.** On
2026-09-04 a lane concluded that `metering` published no per-account
consumption read, wrote a careful paragraph in
`apps/portal/seams/billing_seam.py` explaining why the home page's usage tile
would therefore be built from BILL LINES, and shipped it. `monthly_usage_reads.
usage_payload` had existed since `CR-030` W3 — per account, twelve or twenty-four
months, a unit on every series, and `BR-MET-106`'s absences served AS absences.
**The lane searched the CALLER's folder, found nothing, and read an absence in
one directory as an absence in the product.** No gate can see this: the code was
correct, tested and green. The only thing that finds it is looking on the
OWNING module's side before concluding a read does not exist — which is why it
is written here, in the step where the packet is assembled.

### 2 · BUILD — four parts, not one  *(PO 2026-08-16)*

| | |
|---|---|
| **2a Backend** | The engine. Refuses rather than guesses. |
| **2b Frontend** | The screens. **NOT separately closeable** — see below. |
| **2c Tests + data** | Test CODE for the cases the story's §3 already declares, plus the fixtures. |
| **2d Prove it** | Every guard broken FIRST and its failure quoted; then proved by clicking. ⚠ **AMENDED 2026-09-03 (PO, verbatim: *"everything should be executed based on actual code, and rules that we place, also ensure you do web walkthorugh before you sign off the user story or build"*): the click is a RECORDED web walkthrough of the running product — a `10-scripts/render-checks/<cr>-<wave>-<slug>.mjs` Playwright script that drives the wave's demo on the seeded fixture, asserts the sentences on screen and saves screenshots — and a story is signed off only when its tests are green, that script has run green on the actual build, and the screens match the module's `08-screen-layouts.md`. Every task's *touches* is verified against the code at HEAD before it is written; where a document and the code disagree, the code wins. Decision log 2026-09-03.** ⚠ **AND WRITE THE PROOF WHERE ONLY YOU CAN REACH IT — NEVER `/tmp` (`DEF-GOV-3958`, 2026-09-05).** Every lane in this container shares one `/tmp`, so a RED-proof log at `/tmp/red1.txt` is silently replaced by another worktree's run within the hour **and still reads as a plausible log** — same name, same shape, wrong run. A proof you cannot tell apart from somebody else's proof is not evidence of anything, and this one fails in the direction that matters: it reads as though the guard was shown red when it may never have been. **Put proof artefacts under your own worktree**, which is already per-lane and is already the path every brief tells you to build from. Where `/tmp` is unavoidable, put the lane id in the filename rather than `red1.txt`, and **check the file's mtime against the moment your command finished before you quote it.** This bit twice on 2026-09-05: once as filed, and once as the reconciliation lane finding a shared scratch directory holding eighty other files from eleven lanes. |

**2b is numbered so that skipping it is VISIBLE.** R2's central failure was 66
stories with a complete, tested, correct engine and no screen — every deferral
written down honestly, and nothing adding them up. A numbered step makes "we
skipped 2b" a fact rather than a footnote in a trailer nobody reads. **Step 6
refuses a story missing it.**

**2c writes test CODE, never test CASES.** The cases live in the story's §3 and
predate the code. Authoring cases after the code produces tests that confirm what
was built rather than what was asked for — which is how 2,900 passing tests sat
over a product that could not issue a bill.

**2d is per-half, not only at the end.** Three lanes on 2026-08-16 shipped a
browser check that PASSED against the broken screen before it was tightened; one
read the money figure on the line above the broken one. Assert the thing that was
actually wrong.

⚠ **AND 2d SAYS TO BREAK THINGS WITHOUT SAYING WHERE — SO BREAK THEM IN A
WORKTREE, NEVER IN THE SHARED TREE (2026-08-25).** A lane proving a guard RED
holds, for the length of the run, a tree in which the guarantee is genuinely
gone and the comment promising it is still there. **That is byte-for-byte
identical to a lane fabricating values, and no one reading the tree can tell
the two apart** — not a gate, not a sibling lane, not the merger. It happened:
two checkpoint commits landed mid-cycle and caught seven mutations, one of them
`outstanding_source: "ledger"` stamped on a figure that was not the ledger's.
The lane was doing exactly what this step asks; the merger read the diff,
applied hard-won law 1 correctly, and filed a wrong accusation. **Both parties
followed the process and the process produced the collision.**

**So: mutate in a `git worktree` or a scratchpad copy and run the suite against
that** — hard-won law 11 already says *"use a `git worktree`. Never move the
shared one"*, and neither party reached for it. Announcing the window helps and
is not the mechanism; a courtesy message loses every race a commit can win.

**Do NOT read this as a reason to skip 2d.** Skipping trades a real guarantee
for a quieter tree, which is the worse bargain by a wide margin. The RED proof
is not the problem — its *location* is. Note for whoever merges: **a diff that
looks like fabrication may be a RED window**, so ask the lane before filing;
and note for whoever mutates: **write the failing test BEFORE the mutation**, so
the mutation goes red rather than silent. The lane above had, which is the only
reason its own leaks surfaced at all.

⚠ **AND THE MERGER'S ADVICE ABOVE IS HALF THE PROBLEM — THE SAME DAY, THE
COLLISION HAPPENED IN THE OPPOSITE DIRECTION AND NOBODY NOTICED FOR AN HOUR.**
The clause above warns about a FALSE ACCUSATION: a mutation read as
fabrication. The mirror case is worse, because nothing objects. A checkpoint
commit captured `apps/metering/sample_data.py` mid-proof holding
`"electric": None` where the seed declares `25`, and **the merger read the
one-line diff, judged it deliberate seed judgment, and committed it** — the
comment two lines above it plausibly explained a per-premise service, so the
mutation looked like a considered choice. It reached the branch inside a commit
whose message was about something else entirely, and it was found only because
the lane said so in its own report an hour later.

**So a one-line diff is exactly the dangerous size.** A seven-`if False:` batch
announces itself; a single plausible value does not, and "does this look
reasonable" is not a test that can distinguish a mutation from a decision —
which is this repo's oldest recorded flaw class wearing new clothes. **The
merger cannot fix this by reading more carefully.** Only the mutator can, by
not putting the mutation in the shared tree at all.

**Practical rule for the merger, since asking about every one-line change does
not scale:** when a lane is RUNNING, its files are not reviewable — checkpoint
them as unreviewed and say so in the message, and treat the lane's final report
as the first reviewable state. **What made this recoverable is that the lane
reported it.** A lane that mutates in the shared tree owes its merger that
sentence, every time, and it belongs in the final report whether or not
anything went wrong.

### W · WRITE BACK AS YOU GO — *not a step, a continuous obligation (new, PO 2026-08-16)*

The next agent reads the repo, not your memory. Four triggers:

| When you find | Write it | Before you |
|---|---|---|
| A rule that is wrong or stale | Amend the rule doc — dated, with the reason | build anything on it |
| A question with no signed answer | Mint it in the register, stub with its ID, route to the PO | write code that would guess |
| A defect | File it in the register | fix it — so the fix has a row |
| A judgment made where the rules ran out | Decision log, with the worked figure | report it to anyone |

**Timing rule: "before the thing that depends on it", never "at the end."**
A ruling explained in chat and not in the repo is a context leak — it reads as
progress and evaporates (hard-won law 10).

**Race rule, learned the hard way:** re-read the register immediately before
writing an ID; patch by RECORD boundary; verify exactly one record moved. On
2026-08-16 two lanes minted the same question numbers, and a defect row was
destroyed by a malformed record and recovered from git history.

### 3 · SELF-VERIFY — the full gate set + the §5 completion checklist

### 4 · CLOSE THE RECORD  *(new — the write-backs that can only happen at the end)*

The decision-log row · the `surface_debt.txt` count **and its sentence, verified
against the code** · the human-review-ledger row stating **what was shown to the
PO in plain English with a concrete figure** · defect closures with their
evidence.

**Before review, not after** — so the reviewer reads the same repo the next agent
will.

⚠ **AND STAMP THE WAVE'S OWN ROWS DONE, IN THE COMMIT THAT LANDS ITS LAST TASK
(added 2026-09-05, `DEF-WRK-3933`).** A wave's table is what a task packet
quotes, so it is what the NEXT lane is dispatched from — and a wave that ships
without stamping its own rows reads as unstarted work forever. On 2026-09-05
that sent **two lanes at CR-070 wave B**, which had shipped as `2.136.0` two days
earlier: one was told to build `features/customers/ConnectionDetailPage.tsx`, a
file the next wave had already deleted, and following the brief would have
resurrected a retired destination and broken that wave's own grep case. Both
lanes ran step 0, found it, and wrote no code — which is why nothing was lost,
and is the argument for keeping step 0 a human reading.

**The mechanism is that a wave has TWO pointers and only one of them feels like
the work.** Wave O's section sat directly above wave B's table and already
described wave B in the past tense; the table itself never moved. **This is the
fifth recorded instance of that exact shape on this branch** — B14's rule-count
line has been wrong five times, `CR-068` R3's held controls rotted the day their
screens landed (`DEF-CWP-3925`), and hard-won law 12 records it for pointers
generally. **So it is not a tidying pass and must not be scheduled as one: a
pointer updated in a later commit is a pointer that does not get updated.**

### 5 · HUMAN REVIEW — the PO, on anything touching money rules

### 6 · MERGE — **refuses a story whose 2b was skipped**

---

**What this still does not fix, stated so nobody assumes otherwise:** no check
reads prose. A sentence can be wrong while its count is right, and that is
exactly what happened four times in one file. Step 0 is where a human notices —
which is the argument for keeping it a human reading rather than automating it
into a green tick.

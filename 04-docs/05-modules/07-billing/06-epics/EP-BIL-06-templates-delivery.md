# EP-BIL-06 — Bill templates & delivery (queue-based, never synchronous)

**Module:** billing · **Wave:** W3 (templates, pinning, queue + print/PDF) — email-channel dispatch **deferred → W6** (OQ-073 closed) · **Screens:** S8 (Settings → Templates tab), S91–S96 (printable designers), S31 (step 6), S30 · **Status:** draft (BR-BIL-001..029 all CONFIRMED — session closed 2026-08-08)

## Scope
**In:** bill/statement template management with append-only **versions** (draft → published → archived; one published per template; category assignment per BR-BIL-025), the ratified **rights split** (Clerk drafts + test-prints, System Admin publishes, pinned versions undeletable — BR-BIL-027), **pinning** of template + version on every bill at issue with reprint rendering the pinned version forever (BR-BIL-026, BS-17), and the **outbound delivery queue** (BR-BIL-016, r1.4): one record per bill per channel at issue, dispatcher batches (tenant-config, default 500), statuses queued→sent→delivered|failed|bounced, retry ×3 with backoff, per-run delivery dashboard + re-queue. Print/PDF ships v1 (batch PDF from the same queue); **customer email ships W6** with notifications (OQ-073) — the email queue rows are written from day one, dispatch activates at W6; BYO mailbox for small tenants + transactional ESP for volume (OQ-074).
**Out:** rendering engines + send infrastructure internals (notifications module — billing owns queue records + pinning, model §15) · email/SMS body designers S97–S106 (notifications templates) · dunning/disconnect notice workflow (collections/J4) · ESP/BYO connection UIs (integrations, A15/B7).
⚠ **SCOPE NARROWED 2026-08-12 (PO ruling, OQ-149 CLOSED) — NO CUSTOM BILL DESIGN IN V1.** Verbatim: *"out platform will porvide standard 3 to 5 variouation of printed bill - user can use those only in V1"*, given after the trade-off was put to the PO in plain English. **A utility CHOOSES one of the platform's 3–5 standard printed-bill layouts; nothing renders tenant-authored HTML.** So `bill_template_versions` holds **the platform's variants, not a tenant's markup**; the ~200MB page-rendering library (WeasyPrint and its Pango/HarfBuzz/fontconfig tree) is **NOT** added to the deployment image; and the S91–S96 designers are a **selection + options** surface in v1 rather than a free-form body designer. **What is UNCHANGED:** pinning at issue, reprint-renders-the-pin, the append-only version chain, the Clerk/Admin rights split, the audit-lock on a pinned version, per-category assignment (BR-BIL-025) and the tenant's own bill messages/footer (BR-BIL-021). A tenant still chooses per category and still writes its own copy — what it does not do is design the page.
**Tables (B2 r10):** `bill_templates` + `bill_template_versions` (#4), `invoices.template_id/template_version` (#3), outbound delivery queue (#8).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S8 · Templates tab (printable group) | template name | type (bill/statement/…), category, status (draft/published/archived) | name asc | name, type, updated | Name · Type · Category · Published vN · Draft? · Updated / +pinned-by count (IS-5) | Design (→ S91–S96) · Publish (Admin) · Archive · History | — | — |
| S30 · Delivery dashboard (per run) | bill #, account | channel, status (queued/sent/delivered/failed/bounced) | failed first, then queued_at | status, channel, attempts | Bill · Account · Channel · Status · Attempts · Last error · Batch / +provider ref (IS-5) | View bill · Re-queue | Re-queue selected | CSV (IS-9) |

## Stories

---
id: US-BIL-021
epic: EP-BIL-06
module: billing
screens: [S8, S91, S92, S93]
wave: 3
status: draft
blocked_by: []
depends_on: [US-TEN-010, US-SHL-014]
journeys: [J2]
rules: [BR-BIL-025, BR-BIL-026, BR-BIL-027]
golden_tests: []
finance_calc: none
---
### US-BIL-021 — Template CRUD, append-only versions, publish rights

**1 · Details** — As a Billing Clerk, I want to create and edit bill/statement template drafts in the designers (S91 bill residential · S92 bill commercial · S93 statement — variables, options, Preview PDF, Save version per the A1 r8+ addendum) and test-print them; and as a System Admin I want to **publish** a version (one published per template) — because publish rights are Admin-only, and a version pinned by ANY bill can never be deleted (audit-lock, BR-BIL-027). Template **assignment** defaults by consumer category (residential/commercial/industrial/govt) and is overridable per account (BR-BIL-025). Every edit = a new version (append-only, draft → published → archived, audited); publishing affects only FUTURE bills (BR-BIL-026). Entry: Settings → Templates tab (S8, r8 addendum). Exit: published versions available to issue-time resolution (US-BIL-005/022).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-025 | Template assignment: default by consumer category, overridable per account. | CONFIRMED — PO Lane B-6, 2026-08-08 |
| BR-BIL-026 | Versioning: edit = new version; publishing affects only future bills. **AMENDED 2026-08-12: v1 ships 3–5 PLATFORM layouts and no tenant-authored design — `bill_template_versions` holds the platform's variants (OQ-149 CLOSED).** | CONFIRMED — PO Lane B-7, 2026-08-08 · **AMENDED PO 2026-08-12 (OQ-149)** |
| BR-BIL-027 | Rights: Billing Clerk creates/edits drafts + test-prints; System Admin publishes; a pinned version can never be deleted (audit-lock). | CONFIRMED — PO Lane B-8, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Priya (Clerk) edits "Bill · residential" | New draft version v4 created append-only (v3 published untouched); test-print renders v4 with sample data; save audited |
| TC-2 | Priya attempts Publish; Alex (Admin) publishes v4 | Clerk's publish absent/disabled-with-reason + server-rejected; Admin publish succeeds → v4 published, v3 auto-archived (one published per template); only bills issued AFTER see v4 |
| TC-3 | Category assignment | "Bill · residential" ↔ residential category default; account-level override set on ACC-9001 → commercial template; resolution order account-override → category default (BR-BIL-025) |
| TC-4 *(negative)* | Delete attempted on v3 (pinned by 1,124 issued bills) | Blocked — audit-lock: archive allowed, delete never (BR-BIL-027); an unpinned draft version deletes fine |
| TC-5 *(negative)* | Direct UPDATE of a published version's body | Rejected — versions are append-only rows; edits create drafts |
| TC-6 *(isolation)* | Lone Star Ridge templates | Own template set only; Brazos Bend versions invisible (RLS) |

**4 · Test Data** — Brazos Bend templates: "Bill · residential" (v3 published, pinned by run 07-A's 1,124 bills; v4 draft), "Bill · commercial" (v2 published), "Statement" (v1 published — penalty bills render here per r1.5). Category map: residential/commercial/industrial/govt; override fixture ACC-9001 → commercial. Actors: Priya Menon (drafts/test-print), Alex Reed (publishes). Isolation: Lone Star Ridge "Bill · standard" v1.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Template + type + category | S8 Templates | A19 types + BR-BIL-025 | `bill_templates` (type, category assignment — r10 #4) | row | user-input | types per A19 (bill/statement/…) |
| Version body + status | S91–S93 | BR-BIL-026 | `bill_template_versions` (append-only; draft\|published\|archived — r10 #4) | rows | user-input | edit = new row; one published per template |
| Publish action | S8 | BR-BIL-027 | version status transition, Admin-gated | enum | user-input | server-enforced role |
| Test-print | S91–S93 footer | BR-BIL-027 | rendered preview (no money event, no delivery row) | pdf | computed-display | sample data only |
| Account override | S21 (customers surface) / resolution here | BR-BIL-025 | account-level template override (customers-owned attribute, billing reads at issue) | uuid | user-input | overrides category default |
| Audit-lock | — | BR-BIL-027 | delete blocked while pinned (`invoices.template_version` refs) | — | system-derived | archive allowed |
| Template audit | — | CLAUDE.md #7 | `audit_log` `template.saved/published/archived` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a Clerk edit, Then a new append-only draft version exists, test-printable, with the published version untouched.
- Given publish, Then only a System Admin succeeds, exactly one version is published per template, and only future bills are affected.
- Given a pinned version, Then delete is impossible forever; archive is fine.
- Given category defaults + account overrides, Then issue-time resolution picks override → category default.

**7 · Finance Calculation** — N/A (templates render money; they never compute it).

**8 · Open Questions** — None.

---
id: US-BIL-022
epic: EP-BIL-06
module: billing
screens: [S30]
wave: 3
status: draft
blocked_by: []
depends_on: [US-BIL-021, US-BIL-005]
journeys: [J2]
rules: [BR-BIL-026, BR-BIL-027]
golden_tests: []
finance_calc: none
---
### US-BIL-022 — Pinning at issue + reprint renders the pinned version forever

**1 · Details** — As the system, I want issue to stamp `template_id` + `template_version` on every bill (resolved account-override → category default, BR-BIL-025) and **reprint/re-send to render the pinned version forever** — a bill issued on v3 renders on v3 in 2031 even if v9 is published — with every reprint an **audited event, never a money event** (BR-BIL-026, model §10) — so that what the customer was sent is reproducible for the full retention window. Rebills pin the CURRENT version at rebill issue (BR-BIL-014/US-BIL-015). Entry: issue (US-BIL-005) writes the pin; S30 row action Reprint / Account detail Print bill (US-CUS-014 surface) renders from it.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-026 | Template + version PINNED on the bill at issue; reprint/re-send renders the pinned version forever; publishing affects only future bills. | CONFIRMED — PO Lane B-7, 2026-08-08 |
| BR-BIL-027 *(shared)* | The pin is what audit-locks a version against deletion. | CONFIRMED — PO Lane B-8, 2026-08-08 |
| BR-BIL-014 *(shared)* | A rebill pins the current version at REBILL issue (its own pin, its own render). | CONFIRMED — PO A-5/r1.2 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Run 07-A issues on "Bill · residential" v3 | Every invoice row carries template_id + version 3 (BS-17) |
| TC-2 | v4 published Sep 1; BL-2608-018410 reprinted Sep 15 | Renders **v3** — the pinned version; the reprint writes `audit_log` `invoice.reprinted` (actor, when, channel) and NO money/ledger/balance effect |
| TC-3 | WE-9 rebill issued Sep 20 | The rebill pins v4 (current at rebill issue); the original still renders v3 — two pins, both stable |
| TC-4 *(negative)* | Reprint requested with a "render on latest" flag | No such option exists — pinned version only (BR-BIL-026) |
| TC-5 *(negative)* | v3 delete attempted while pinned | Blocked (US-BIL-021 TC-4 pair) — the pin guarantees reproducibility |
| TC-6 *(isolation)* | Lone Star Ridge reprint | Renders its own pinned versions; Brazos Bend template ids unreachable (RLS) |

**4 · Test Data** — Run 07-A: 1,124 bills pinned v3 (issued Aug 1). Publish v4 Sep 1. Reprint fixture BL-2608-018410 Sep 15 → v3. Rebill fixture (WE-9's +227.95 rebill) issued Sep 20 → pins v4. Retention context: 7-year version retention CONFIRMED (B4 PO Q&A R1). Actors: Priya Menon (reprint). Isolation: Lone Star Ridge reprint on its v1.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Pin | — | BR-BIL-026 | `invoices.template_id` + `.template_version` (r10 #3) | uuid/int | system-derived | written at issue; immutable with the invoice |
| Resolution at issue | — | BR-BIL-025 | account override → category default → template published version | uuid | system-derived | published versions only |
| Reprint action | S30 / S22 Print bill | model §10 | render from the pinned version; delivery row optional re-queue (US-BIL-023) | pdf | user-input | audited, never a money event |
| Reprint audit | — | BR-BIL-026 + CLAUDE.md #7 | `audit_log` `invoice.reprinted` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given issue, Then every bill carries its pin; given any later publish, Then reprints still render the pinned version byte-for-byte.
- Given a rebill, Then it pins the current version independently of the original's pin.
- Given a reprint, Then an audit row exists and no balance/ledger/money state changes.
- Given tenants, Then pins resolve only within the tenant.

**7 · Finance Calculation** — N/A (reprint is never a money event — BR-BIL-026). Ref: BS-17.

**8 · Open Questions** — **ALL THREE CLOSED BY PO RULINGS OF 2026-08-12; the three paragraphs below are kept as the record of what was asked and what the lanes shipped in the meantime.**

⚠ **OQ-117 CLOSED (PO 2026-08-12): *"issue and report it"*.** A bill that renders its charge lines correctly but **cannot print its TOTAL DUE is ISSUED, and the missing total is raised as a run problem naming the bill** — the charge lines are correct and the customer needs them. The lane's shipped reading was the right one. **BR-BIL-033 is amended, not overturned:** a document that cannot be PRODUCED at all still refuses the issue (one named `ISSUE_RENDER_FAILED` break, rest of the batch issues); a document that is produced with a **named absence** goes out.
⚠ **OQ-150 CLOSED (PO 2026-08-12): *"print a substitution"*.** `Zofia Nowałczyk` prints `Zofia Nowa?czyk` and **the run names the bill and the character** so somebody can fix the record. *"A silent substitution would be the defect; a refused bill would punish the customer for our font."*
⚠ **OQ-149 CLOSED (PO 2026-08-12): *"out platform will porvide standard 3 to 5 variouation of printed bill - user can use those only in V1"*.** The engine question **does not arrive**: nothing renders tenant-authored HTML in v1, so no HTML/CSS engine is chosen and **the deployment image does not change** (see Scope above). The dependency-free standard-library page described in the addendum below is therefore the v1 shape rather than a stand-in — what it needs is the other 2–4 layouts, not a rendering library.
⚠ **REPORTED WITH THE CLOSURES AND NOT PAPERED OVER (2026-08-12):** *"issue and report it"* and *"print a substitution"* both produce a problem for a bill that **DID** issue, and **there is nowhere durable to put one**. `runs.BlockedAccount` holds bills that did NOT issue; there is no per-bill problem row for one that did, so the report is a WARNING on the `smartbillhub.billing` logger and **never reaches the S31 phase-4 run summary a clerk opens**. Every document carries `run_problems_are_logged_and_not_stored`. **A durable per-bill problem row is owed and needs a story against the run summary** — a clerk who never opens a log will believe every bill in a green run was perfect.

~~**OQ-117 (OPEN, raised 2026-08-11 by the bill-document lane).**~~ *Is a bill that renders its charge lines correctly but cannot print its **TOTAL DUE** a "failed render" that BR-BIL-033 must refuse the issue for — or a rendered document with a named absence?* The renderer (`06-backend/apps/billing/documents.py`) made the question answerable for the first time: it renders A-10432's Electric usage 684 kWh @ $0.1420 = **$82.08** plus base **$18.50** = current charges **$100.58**, then cannot fill A19 §1.3's Total due, because BR-BIL-035's balance-forward figures are not in `bill_payload` and `invoices.total` is the current charges alone. The same bill also has no masthead and no service address. **The lane ships the second reading** (render, name the absences, let the bill issue) because the first refuses every bill the system currently produces; a ruling of the first is one condition in `render_invoice`, and it would make closing the stage-6 stamping gap a release blocker. Registered in `12-governance/01-open-questions.md`.
~~**OQ-149 (OPEN, raised 2026-08-11 by the PDF lane).**~~ **CLOSED 2026-08-12 — the question below is the one that was asked; the ruling above is the answer.** *Which HTML/CSS engine renders the tenant's DESIGNED bill body when `bill_template_versions` lands — and does the answer change the deployment image?* Nothing is blocked today: the bill renders and prints. The engine question arrives with S91–S96, and its leading candidate (WeasyPrint) adds Pango/HarfBuzz/fontconfig to every container, which is an Eng-Lead/PO call and not a lane's.
~~**OQ-150 (OPEN, raised 2026-08-11 by the PDF lane).**~~ **CLOSED 2026-08-12 — the question below is the one that was asked; the ruling above is the answer.** *A customer whose name the PAGE cannot spell — `Zofia Nowałczyk` prints `Zofia Nowa?czyk`, because the unembedded Base-14 fonts encode WinAnsi only — does that REFUSE the issue under BR-BIL-033, or print substituted and report it?* The lane ships the second reading and names every substitution on the document (`pdf_unrepresentable`), for OQ-117's reason. `María Núñez` is unaffected; the HTML is unaffected in every case.

> **Implementation note (2026-08-11).** This story is BUILT as far as the schema allows. `documents.render_invoice` resolves its layout from `invoices.template_version` and never from a latest-published pointer, refuses a caller that asks for a different version (TC-4's *"no such option exists"* — proved by mutation), and renders **only** from the stamped instance plus the invoice's own immutable lines (TC-2's reproducibility — proved by a query-count guard, so a live join fails on the count even when it returns the right string). `issue.issue_invoice` calls it before the status moves, which is what makes BR-BIL-033 real. **TC-5** (a pinned version can never be deleted) is not testable: `bill_template_versions` does not exist, so ONE built-in layout stands in for every pinned version and the tenant's edited BODY is not honoured — each document names this in its `layout_source`. **TC-6** (cross-tenant reprint) belongs to the isolation suite. Tests: `06-backend/tests/test_us_bil_022_documents.py`.

> **Addendum (2026-08-11, PDF lane) — A19's *"printed + PDF"* now produces a PDF, and the note above previously said it did not.** `render_invoice` returns `.body` (HTML) and `.pdf` (bytes) as **two serialisations of one structure**: both built from the same mapping, neither parsing the other, and `LAYOUTS` holds ONE entry per template version carrying BOTH callables — so the pin cannot select the layout for the screen and a stand-in for the paper (BR-BIL-026, asserted in tc3/tc4). **No PDF library was installed to do it.** WeasyPrint renders the real HTML/CSS but needs Pango/HarfBuzz/fontconfig as system libraries and so changes the deployment image; ReportLab and fpdf2 bring their own layout language (a second layout that can drift) and fpdf2 is LGPL-3.0; xhtml2pdf drags the largest tree for the weakest CSS claim. None is warranted while `bill_template_versions` holds no designed body to render, so the page is written with the standard library: **US Letter, Base-14 fonts, A19 §1's field order, remittance stub, paginated, deterministic to the byte** (no `/Info` dates, `/ID` is a content hash — tc12 asserts two renders of one bill are identical). It is **BR-BIL-036's floor, not the designed bill**: no logo, no 12-month graph, no barcode, no tenant CSS. Two questions were minted rather than answered: **OQ-149** (which HTML/CSS engine renders the designed body when S91–S96 and the template tables land — a deployment-image decision) and **OQ-150** (a customer name outside WinAnsi prints substituted and named; should it instead REFUSE the issue under BR-BIL-033?). BR-BIL-033 now covers the page: any serialiser failure becomes one named `ISSUE_RENDER_FAILED` break for that bill and the rest of the batch issues (tc14, BR-BIL-055). Decision-log row: 2026-08-11.

---
id: US-BIL-023
epic: EP-BIL-06
module: billing
screens: [S31, S30]
wave: 3
status: draft
blocked_by: []
depends_on: [US-BIL-005, US-BIL-022]
journeys: [J2]
rules: [BR-BIL-016]
golden_tests: []
finance_calc: none
---
### US-BIL-023 — The outbound delivery queue + dispatcher (print/PDF v1 · email dispatch **deferred → W6**)

**1 · Details** — As the system, I want issue to write **one delivery record per bill per channel** (status `queued`) to the outbound-delivery table, and a **dispatcher job** to hand tenant-config batches (default 500) to the channel provider — statuses `queued → sent → delivered | failed | bounced`, **retry ×3 with backoff** — because 6k–10k bills can never push in one synchronous go (BR-BIL-016, r1.4). **v1 active channel: print/PDF** — batch PDF generation renders from the same queue concept using the pinned template version. **Email channel: queue rows are written from issue day one, but dispatch to the ESP activates at W6** with notifications (OQ-073 closed — `deferred → W6`); volume model per OQ-074: BYO mailbox for small tenants, transactional ESP integration for volume. S31 step 6 ("Send them out") chooses send-now vs scheduled; either way the queue is the only path — mass sends are never synchronous.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-016 | Queue-based delivery: one record per bill per channel; dispatcher batches (tenant-config, default 500); statuses queued→sent→delivered/failed/bounced; retry ×3 with backoff; mass sends never synchronous. | CONFIRMED — PO A-7, 2026-08-08 |
| BR-BIL-016 (email timing) | Print/PDF v1; customer email ships W6 with notifications — queue architecture stands. | CONFIRMED — OQ-073 closed (PO F-round) — email-channel dispatch marked `deferred → W6` |
| BR-BIL-016 (volume) | BYO mailbox for small tenants; transactional ESP as the tenant's integration for volume. | CONFIRMED — OQ-074 closed (PO F-round) |
| BR-BIL-026 *(shared)* | Every render (PDF batch, later email) uses the bill's pinned template version. | CONFIRMED — PO Lane B-7 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Run 07-A issues 1,124 bills (982 paperless / 142 paper prefs) | Queue rows: 142 pdf_print + 982 email, all `queued`; issue returns immediately — zero synchronous sends |
| TC-2 | PDF dispatcher runs (batch 500) | Three print batches (500/500/124 across channels' print set); rows → sent → delivered as batches complete; batch id stamped per row |
| TC-3 | Email rows in v1 (pre-W6) | Persist `queued` with the deferred-channel marker; NO ESP dispatch attempts; at W6 activation the dispatcher drains them or the tenant re-queues fresh — rows never lost |
| TC-4 | Provider failure on 6 rows | Retry ×3 with backoff; after the 3rd failure status `failed` with the provider error stored; dashboard surfaces them (US-BIL-024) |
| TC-5 | Tenant batch size changed to 200 | Next dispatch honors 200 (config, not constant) |
| TC-6 *(negative)* | A code path attempts a direct synchronous send at issue (bypassing the queue) | Forbidden — the queue is the only delivery path (BR-BIL-016) |
| TC-7 *(isolation)* | Lone Star Ridge dispatch | Batches contain only its rows; its BYO mailbox config never sees Brazos Bend bills (RLS + per-tenant dispatch) |

**4 · Test Data** — Run 07-A: 1,124 bills → 142 print + 982 email queue rows (prototype step-6 counts). Batch size 500 (seeded default); changed-to-200 fixture. Failure fixture: 6 rows, provider timeout, backoff schedule ×3 then failed. Channels enum: pdf_print (active v1) · email (deferred → W6). Isolation: Lone Star Ridge, 210 bills, BYO mailbox tenant.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Delivery row (bill × channel) | — | BR-BIL-016 | outbound delivery queue (r10 #8): invoice, channel, status, attempts, batch id, provider response | rows | system-derived | one per bill per channel at issue |
| Status lifecycle | S30 dashboard | r1.4 | status enum queued\|sent\|delivered\|failed\|bounced | enum | system-derived | forward-only + re-queue (US-BIL-024) |
| Dispatcher batches | — | BR-BIL-016 | batch id per handoff; size = tenant setting (default 500) | int | system-derived | tenant-config |
| Retry/backoff | — | BR-BIL-016 | attempts counter (≤3) + next-attempt time | int/ts | system-derived | ×3 then failed |
| Send-now vs schedule | S31 step 6 | prototype-extracted | dispatch-not-before timestamp on the run's rows | ts | user-input | queue path either way |
| Channel source | — | r1.4 | account delivery preference (customers-owned read) | enum | reference-data | paperless→email, paper→pdf_print |
| Email deferral marker | — | OQ-073 closure | channel config: email dispatch inactive until W6 | flag | reference-data | rows written, not dispatched |

**6 · Acceptance**
- Given issue, Then queue rows exist per bill per channel and nothing sends synchronously.
- Given the dispatcher, Then batches honor the tenant size, statuses progress, and failures retry ×3 with backoff before resting at failed with the provider error.
- Given v1, Then print/PDF dispatches and email rows persist deferred — no ESP call before W6.
- Given tenants, Then batches, configs and mailboxes never cross.

**7 · Finance Calculation** — N/A (delivery moves documents, never money). Ref: BS-23.

**8 · Open Questions** — None (OQ-073/OQ-074 closed; email activation is W6 roadmap, not a question).

---
id: US-BIL-024
epic: EP-BIL-06
module: billing
screens: [S30]
wave: 3
status: draft
blocked_by: []
depends_on: [US-BIL-023]
journeys: [J2]
rules: [BR-BIL-016]
golden_tests: []
finance_calc: none
---
### US-BIL-024 — Per-run delivery dashboard + re-queue

**1 · Details** — As a Billing Clerk, I want a per-run **delivery dashboard** (S30, run detail): counts by channel × status, the failures/bounces list with provider errors, and a **re-queue** action (row + bulk) that resets selected rows to `queued` for the next dispatch — so that "did every bill actually go out?" has one answer per run (BR-BIL-016). Email-channel counters render from day one (rows exist) with the deferred-to-W6 badge until dispatch activates (OQ-073). A re-queue is an audited delivery event, never a money event; re-queue of a sent-and-delivered row is a deliberate re-send (e.g. customer request) rendering the pinned version (BR-BIL-026).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-016 | Per-run delivery dashboard (counts + failures list + re-queue action) is part of the ratified delivery model. | CONFIRMED — PO A-7 / r1.4, 2026-08-08 |
| BR-BIL-026 *(shared)* | Any re-send renders the pinned template version. | CONFIRMED — PO Lane B-7 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dashboard for run 07-A after dispatch | Counts: print 142 (136 delivered · 6 failed) · email 982 queued-deferred (W6 badge); totals tie to the queue rows exactly |
| TC-2 | Failures list | 6 rows with provider error text, attempts=3, last-attempt time; sortable failed-first (capability row) |
| TC-3 | Re-queue the 6 failed rows | Status → queued, attempts reset per r1.4 retry policy; next dispatcher batch picks them; `audit_log` `delivery.requeued` per row |
| TC-4 | Deliberate re-send of a delivered bill | New dispatch renders the pinned version; audited; no money/balance effect |
| TC-5 *(negative)* | Re-queue attempted on another run's rows via forged ids | Rejected — run-scoped selection, server-validated |
| TC-6 *(isolation)* | Lone Star Ridge dashboard | Its runs' rows only (RLS) |

**4 · Test Data** — Run 07-A per US-BIL-023 §4: 142 print (136 delivered, 6 failed on provider timeout), 982 email deferred. Re-queue fixture: the 6 failed. Re-send fixture: BL-2608-018410 (delivered, customer requests a copy). Actors: Priya Menon. Isolation: Lone Star Ridge run W-01 dashboard.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Counts by channel × status | S30 dashboard | BR-BIL-016 | computed over the run's queue rows | counts | computed-display | ties to rows |
| Failures list | S30 dashboard | r1.4 | queue rows status failed/bounced + provider response | rows | computed-display | error text shown |
| Re-queue action | S30 dashboard | BR-BIL-016 | status reset → queued (row/bulk), audited | enum | user-input | run-scoped; IS-6 confirm |
| Deferred-email badge | S30 dashboard | OQ-073 closure | channel-config flag rendering | flag | computed-display | until W6 activation |
| Re-queue audit | — | CLAUDE.md #7 | `audit_log` `delivery.requeued/resent` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a dispatched run, Then the dashboard counts tie to queue rows and failures show their provider errors.
- Given re-queue, Then selected rows return to queued, dispatch picks them, and every action is audited with zero money effect.
- Given the deferred email channel, Then its rows are visible and clearly badged until W6.
- Given tenants, Then dashboards and re-queues never cross.

**7 · Finance Calculation** — N/A. Ref: BS-23.

**8 · Open Questions** — None.

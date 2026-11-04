# EP-BIL-04 — Corrections: approval-gated workflow, single + bulk

**Module:** billing · **Wave:** W5 (J6 wave) · **Screens:** S30 (Fix a bill tab) · **Status:** draft (BR-BIL-001..029 all CONFIRMED — session closed 2026-08-08; **reason taxonomy + preview contract + bulk path added 2026-08-11 from the PO's correction statement — BR-BIL-041..049 PROPOSED, ~~OQ-103/104/105 OPEN~~ → **OQ-103 and OQ-105/OQ-168 CLOSED by PO rulings of 2026-08-12; OQ-104 remains the only open question in this epic**)

## Scope
**In:** the ratified correction WORKFLOW (BR-BIL-014, model r1.2): Initiate (from a bill or the bulk selector) → Reason code (tenant-extensible reference data) → Scope (single | bulk by run/cycle/plan/service/date-range) → **Impact preview** (per bill: credit note, rebill lines, GL reversals, balance delta, payment re-allocation plan) → **Approval** (v1: ALL corrections require System Admin approval — OQ-072 closed) → staged idempotent **Execute** with per-bill results → **Deliver** corrected bills + full audit. NO money-bearing write before approval; the preview IS the approval artifact. J6 alignment: original invoice UNTOUCHED; credit note references it (GT-6); reversing entries by the posting service 🔒; payments reapplied per BR-PAY-010/011.
**Plus (2026-08-11, PO correction statement):** the **reason TAXONOMY** and the three mechanisms it derives — restatement (R) · credit-only (C) · document (D), BR-BIL-041/042, table in US-BIL-015 §1 — the **nine-section impact-preview contract** with its worked ledger handoff (BR-BIL-044/045, US-BIL-015 §7), the **bulk aggregate + partial-failure contract** (BR-BIL-046/047, US-BIL-016), and the **document-only reissue path** (US-BIL-031, ~~blocked by OQ-103~~ **RULED 2026-08-12**). The load-bearing addition is that the mechanism is DERIVED from the reason and never chosen: some reasons change the MONEY and some change only the DOCUMENT, and those two are not the same correction.
**Plus (2026-08-12, three PO rulings that complete the two mechanisms this epic could not build):** **(1) the class-D ARTIFACT** — *"Reissue a corrected copy"* (OQ-103 CLOSED): the case renders a NEW document instance from a **corrected copy of the snapshot** and attaches it to the original bill, the bill itself untouched (BR-BIL-004/030); **a later reprint, re-send or dispute copy renders THE CORRECTED ONE** (OQ-169 CLOSED — *"that is the document the customer is entitled to"*); and **reissues ACCUMULATE** — *"Accumilate"* (DEF-084 ruled): each is composed from the instance BEFORE it, never from the original bill, so an address fix a week after a name fix cannot bring *Sara* back in place of *Sarah* on the paper the customer holds. **(2) the class-C POSTING** — *"a separate write-off account"* (OQ-105 + OQ-168 CLOSED): **DR write-off / CR customer credit balance**, worked on GT-6 (**$25.00** credit against a **$247.30** invoice, balance **$222.30** either way — what moves is the BOOKS, and the original service revenue is never reversed). Concessions get their **own** account separate from bad debt (OQ-187), which mints a chart entry and needs a **finance re-sign**; until then they land on the seeded "Bad debt" designation. **(3) the CHAIN LINK** — *"Nod to add the link on the new bill"* (OQ-120 CLOSED): the **replacement** carries the pointer back to what it replaces, because the original is immutable and must not gain a column after issue; and a **credit note with no rebill counts in the phase-4 panel like a replacement** (OQ-121 CLOSED, BR-BIL-064).
**Out:** void (EP-BIL-07/US-BIL-027 — a void is not a correction) · the prototype's "Change an amount" card (superseded: line edits on issued bills do not exist — BR-BIL-004; the equivalent outcome is credit note + rebill) · standalone credits/adjustments with no originating bill (US-CUS-013, account actions — a goodwill credit raised FROM a bill is in scope as class C, BR-BIL-041) · the master-data edit itself (customers module — BR-BIL-049: this workflow decides what an already-sent document says, never what the account record says) · estimate→actual true-up (BR-BIL-006/WE-13 — register arithmetic on the NEXT bill, never a correction) · back-bills for never-billed periods (BR-BIL-018) · ledger reversal execution (W5 posting service) · payment re-allocation execution (payments; billing emits the plan).
**Tables (B2 + r10):** `correction_cases` (+ bulk runs w/ per-bill results, r10 #9), `credit_notes`, `invoices` (rebills, `bill_type=rebill`), reason-code lookups (r10 #13). **NONE of these is built** — `apps/billing/models.py` ships the invoice core and names the corrections workflow as a later wave. What is additionally missing beyond r10's list is enumerated in the closing section of this file.

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S30 · Fix a bill — case list | case #, bill #, account | status (preview/pending-approval/approved/executing/done/failed), reason code, **class (restatement/credit-only/document — BR-BIL-041)**, scope kind, **has warnings** | created desc | created, status, amount delta | Case · **Class** · Scope · Reason · Bills · Σ delta · Status · Approver / +initiator, executed-at, **↑up / ↓down counts** (IS-5) | Open case · View preview | — (bulk corrections are one case with many bills) | CSV (IS-9) |

## Stories

---
id: US-BIL-015
epic: EP-BIL-04
module: billing
screens: [S30]
wave: 5
status: draft
blocked_by: []
depends_on: [US-BIL-005, US-BIL-017, US-CUS-012]
journeys: [J6]
rules: [BR-BIL-004, BR-BIL-014, BR-BIL-041, BR-BIL-042, BR-BIL-043, BR-BIL-044, BR-BIL-045, BR-BIL-048]
golden_tests: [GT-6, GT-25]
finance_calc: confirmed
---
### US-BIL-015 — Single-bill correction: credit note + rebill with impact preview

**1 · Details** — As a Billing Clerk who finds an issued bill wrong (e.g. a superseded read, J6), I want to open a correction case on that bill: pick a reason code, see the full **impact preview** — the credit note that reverses the original (full GL reversal pairs), the recomputed rebill lines (own GL stamps at rebill issue), the customer balance delta, and the **payment re-allocation plan** (payments allocated to the original re-allocate to the rebill; overpayment → credit per BR-PAY-010) — then submit for System Admin approval; on approval the case executes: credit note written referencing the original (immutable, GT-6), rebill issued as a new invoice (`bill_type=rebill`, current template version pinned, citing the original), delivery queued, every touched record audited — so that corrections are safe, explained, and reversible-by-construction (BR-BIL-014). The original stays issued + visible forever.

**1a · The reason taxonomy — which reasons take which mechanism (PO 2026-08-11; BR-BIL-041/042, PROPOSED)** — The PO named the reasons: *"reading error, name or address changes, rate issues, credit, multiple reasons"*. They do not share a path, and this is the whole of why the taxonomy exists: **some reasons change the MONEY and some change only the DOCUMENT.** A name fix that issues a credit note is absurd — it moves the ledger and the customer's balance for a spelling. A rate fix that only reprints is a silent underbilling — the customer keeps the wrong amount and no gate ever fires. So the operator picks the **reason**; the system derives the **mechanism** from the reason's class; the mechanism is never a dropdown.

| Reason (seeded per r1.2, + examples) | What is actually wrong | Class | Money moves? | Document reissued? | What the case emits | Fixture |
|---|---|---|---|---|---|---|
| **wrong read** / superseded read (BR-MET-053) | the consumption the bill printed and priced | **R** restatement | **yes** | **yes** — rebill | full credit note (−original total) + rebill + full GL reversal handoff + re-allocation plan; original → `corrected` | **GT-25 / WE-9** |
| **wrong rate / wrong plan** / wrong tariff version | priced against the wrong schedule | **R** | **yes** | **yes** — rebill | as above (this is J11's bulk case at scale) | WE-9 shape |
| **wrong tax** — rate, jurisdiction, or an exemption not applied | the tax lines, and therefore the remittance basis | **R** | **yes** | **yes** — rebill | as above; the per-authority tax delta is shown separately because it moves a liability owed to a third party (BR-LED-002) | GT-10/11 base |
| **missed charge** — a line that should have been on the bill | the bill is incomplete → **upward** | **R** | **yes** (+) | **yes** — rebill | as above with a positive delta; the customer owes MORE — **whether the back-bill window caps this is OQ-104** | — |
| **charge billed in error** — a line that should not have been there | the bill overcharged for a named thing | **R** *(seeded default)* | **yes** (−) | **yes** — rebill | as above; a tenant may class its own equivalent reason **C** instead, and GT-6 is that shape's frozen fixture | GT-6 (C shape) |
| **wrong period / wrong proration / wrong service billed** | the bill covers the wrong days or the wrong service | **R** | **yes** | **yes** — rebill | as above | WE-6/WE-12 shapes |
| **theft-restated** | assessed reads replace what was billed (BR-BIL-019) | **R** | **yes** (+) | **yes** — rebill | as above; back-bill cap explicitly EXEMPT for theft (OQ-071 closed) | WE-11 |
| **goodwill** / concession / outage credit | **nothing** — the bill is right; the utility chooses to charge less | **C** credit-only | **yes** (−) | **no** | **partial** credit note referencing the original, **NO rebill**, original stays `issued`/`paid`; balance moves by the credit alone. **POSTING RULED 2026-08-12 (OQ-105/OQ-168): DR write-off / CR customer credit balance — a SEPARATE write-off account, never a reversal of the original service revenue.** It **counts in the phase-4 panel like a replacement** (OQ-121) | **GT-6** |
| **name spelling / legal name / DBA** | the document names the wrong party; the money is right | **D** document | **no** | **yes** — reissue | **no credit note, no rebill, no posting**; balance delta exactly **$0.00**; a reissued document instance (US-BIL-031). **RULED 2026-08-12 (OQ-103/OQ-169/DEF-084): a corrected COPY of the snapshot, later reprints render it, reissues ACCUMULATE** | *Sara → Sarah Whitfield* (US-BIL-031) |
| **service or mailing address, premises/unit label** | the document was addressed wrongly — this is also the returned-mail path (J18) | **D** | **no** | **yes** — reissue | as above | J18 returned-mail bill |
| **meter number or read dates printed wrong**, consumption right | presentation only | **D** | **no** | **yes** — reissue | as above | — |
| **wrong template / wrong language / missing bill message** | the document rendered from the wrong presentation (BR-BIL-026/031) | **D** | **no** | **yes** — reissue | as above — a template change never re-renders history, so a reissue is the only lawful route. ⚠ **In v1 the choice is between the platform's 3–5 standard layouts (BR-BIL-026 as amended 2026-08-12, OQ-149), not a tenant-authored design** | — |

**Not corrections at all — route elsewhere, and the case screen says so by name rather than accepting the work:** an estimate replaced by an actual read → **true-up on the NEXT bill** by register arithmetic (BR-BIL-006, WE-13: *"no reversal of the July bill"*) · a bill that should never have existed → **void** (US-BIL-027) · a period never billed → **back-bill** (BR-BIL-018 — there is nothing to restate) · a payment landed on the wrong bill → **payments re-allocation** (BR-PAY-010/031) · master data wrong with no already-sent document affected → the **customers-module edit** (BR-BIL-049).

**Multiple reasons (BR-BIL-042):** a case may carry several reason codes and takes the STRONGEST class present, R > C > D. A document reason costs nothing when a restatement is already happening, because the rebill re-snapshots from current master data anyway.

**1b · The impact preview contract (PO 2026-08-11: *"show user what will be impact before confirming final corrections"*; BR-BIL-044/045, PROPOSED)** — the preview is a persisted, content-hashed artifact and IS the approval record; nine sections, all required, none collapsible away: **(1) what is being corrected** — bill #, account, period, reason(s), the DERIVED class shown as a word not a code, initiator · **(2) the lines** — original / corrected / Δ for every line including the ones that did not move, with the changed input named in the operator's language (`water read 8 → 6 kgal`), because a preview that shows only movement cannot be checked · **(3) the money** — original total, corrected total, delta, tax split per authority · **(4) the documents that will exist** — credit note, rebill (with the template version that will be pinned), reissue, or the explicit word "none" · **(5) the ledger handoff IN FULL** — both balanced entries line by line, the net per GL bucket, and **the posting period the entries will land in** (BR-BIL-045: a closed period auto-posts to the earliest open one, BR-TEN-038, so the month that moves is not always the month on the bill) · **(6) the customer's balance** — before → after, with the payment re-allocation plan written in plain language per BR-BIL-009 · **(7) what the customer will receive** and on which channel (print is the floor, BR-BIL-036) · **(8) warnings** · **(9) the gate** — who must approve, and the standing statement that nothing money-bearing exists yet. **Approval binds the artifact, not the query:** any input drift between preview and execute REFUSES execution and demands a fresh preview.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-014 | Correction = approval-gated workflow: reason code → scope → impact preview (credit note, rebill lines, GL reversals, balance delta, payment re-allocation plan) → approval (v1 ALL by System Admin — OQ-072) → staged idempotent execution → delivery + full audit; NO money-bearing write before approval. | CONFIRMED — PO A-5, 2026-08-08 |
| BR-BIL-004 | Original invoice/lines never change; correction = credit note + rebill (new rows). | CONFIRMED — B2 §billing, CLAUDE.md #4 |
| BR-BIL-026 *(shared)* | The rebill pins the CURRENT template version at rebill issue (customer sees a full corrected bill citing the original — r1.2/A-5). | CONFIRMED — PO A-5 + Lane B-7 |
| BR-PAY-010/011 *(consumed)* | Re-allocation per tenant order; consequence messaging on payment reversal paths. | CONFIRMED — payments rules, cited |
| BR-BIL-041 | Every reason carries a CLASS (R restatement / C credit-only / D document) and the class DERIVES the mechanism; the operator picks the reason, never the mechanism. | **PROPOSED** — PO 2026-08-11, detail unratified |
| BR-BIL-042 | A multi-reason case takes the strongest class present, R > C > D; one bill is never corrected two ways at once. | **PROPOSED** — PO 2026-08-11 ("multiple reasons") |
| BR-BIL-043 | A D-class case with a non-zero money delta is REFUSED; an R-class case with a $0.00 delta still emits its pair but the preview FLAGS the zero. | **PROPOSED** — derived, hard-won law 3 |
| BR-BIL-044 | The preview is a persisted, content-hashed artifact with nine required sections; approval binds the artifact, and input drift refuses execution. | **PROPOSED** — PO 2026-08-11 ("show user what will be impact before confirming") |
| BR-BIL-045 | The preview names the POSTING PERIOD before confirm (closed period → earliest open, BR-TEN-038). | **PROPOSED** — derived from BR-TEN-038/BR-LED-002 |
| BR-BIL-048 | Only the LATEST document in a correction chain may be corrected; one open case per chain. | **PROPOSED** — derived from BR-BIL-004/014 |
| BR-BIL-030 *(consumed)* | The bill is LOCKED at issue and its snapshot is frozen by the immutability trigger — which is precisely why a correction can only ever produce a NEW document. | CONFIRMED — PO 2026-08-10 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | WE-9: ACC-1042's water read corrected 8 → 6 kgal after issue; case opened, reason "wrong read" | Impact preview: water 26.50 (was 39.50) · sewer 10.60 (was 15.80) · taxable 203.70 → tax 19.25 (12.73 + 2.04 + 4.07 + 0.41) → corrected current **227.95** vs original 247.87; credit note **−247.87**; rebill **+227.95**; balance delta **−19.92**; re-allocation plan: paid-in-full original → 19.92 becomes carried credit |
| TC-2 | Approval + execution | Nothing money-bearing exists pre-approval; post-approval: credit note row references the original invoice; rebill issued (`bill_type=rebill`, cites original, current template version pinned); GL reversal handoff to posting 🔒; delivery queued; audit rows on every record |
| TC-3 | Original bill afterwards | Still issued + visible, byte-identical lines; S30 shows status "Corrected" with the chain original ↔ credit note ↔ rebill |
| TC-4 *(negative)* | Execute attempted without approval (API) | Rejected — the gate is server-side; preview artifacts only |
| TC-5 *(negative)* | UPDATE attempted on the original's lines as a "small fix" | Rejected by immutability (BR-BIL-004) — the workflow is the only path |
| TC-6 *(negative)* | Execution re-triggered after success (retry/double-click) | Idempotent — exactly one credit note + one rebill exist for the case |
| TC-7 *(isolation)* | Lone Star Ridge correction | Own bills/reason codes; a Brazos Bend invoice id in a case 404s (RLS) |
| TC-8 | **The nine-section preview on the TC-1 case (BR-BIL-044)** | Every section rendered: the changed input named (`water read 8 → 6 kgal`); ALL nine lines shown, the seven that did not move marked unchanged (elec usage 88.60 · elec base 12.00 · water base 8.00 · trash 18.00 · solar 40.00 · LATE fee 5.00 — and the fee explicitly annotated "computed on a prior overdue balance, not on these charges"); tax split per authority 13.87→12.73 · 2.22→2.04 · 4.44→4.07 · 0.44→0.41; **both** journal entries in full plus the net per bucket (4110 −13.00 · 4120 −5.20 · 2200-03 −1.72 · 1200 AR −19.92) and the posting period; balance 0.00 → **−19.92 credit** in plain language; documents that will exist named; the gate stated. §7 carries the full artifact |
| TC-9 *(negative)* | Clerk opens a case on ACC-1042 with reason **"name spelling"** (class D) and the recomputation produces a non-zero delta because the read was ALSO wrong | **REFUSED** (BR-BIL-043) — "this reason does not change money but the recomputation moved $19.92; pick the reason that describes what is wrong." Nothing is written. Re-opened with "wrong read" it proceeds as TC-1 |
| TC-10 *(negative)* | An operator attempts to answer reason **"wrong rate/plan"** with a document reissue (API: D-class mechanism on an R-class reason) | **REFUSED** — the mechanism is derived, not supplied (BR-BIL-041). This is the silent-underbilling guard and is proved RED before it is trusted (hard-won law 7) |
| TC-11 | **Multi-reason case:** ACC-1042, reasons "wrong read" (R) + "address" (D) together | One case, class **R** (BR-BIL-042); the pair executes as TC-1 AND the rebill's snapshot carries the corrected address — one document, one approval, no separate reissue |
| TC-12 | **R-class case that nets to $0.00** (a rate fix raises water by exactly what it lowers sewer) | The pair is still emitted (credit note −247.87 / rebill +247.87) and the preview shows a **zero-delta FLAG** for the approver, not a refusal (BR-BIL-043) — the lines moved even though the total did not |
| TC-13 *(negative)* | The read is corrected AGAIN between preview and execute | Execution **REFUSED**, artifact hash mismatch named in the message; a fresh preview is required and the stale one is retained as evidence (BR-BIL-044) |
| TC-14 | The July period is CLOSED when the correction is approved in September | Preview section 5 names the posting period as the earliest OPEN period (BR-TEN-038/BR-BIL-045) before confirm, and warns that the −1.72 tax delta lands in a remittance basis after the July filing |
| TC-15 *(negative)* | A correction opened against the ORIGINAL after a rebill already exists | **REFUSED** naming the current rebill (BR-BIL-048) — only the latest document in the chain is correctable |
| TC-16 *(boundary — OQ-104, **CLOSED 2026-08-11**)* | Reason "missed charge", delta **positive**, the bill is 14 months old (tenant back-bill cap 12 months) | ~~Blocked pending OQ-104; implement to the boundary and stub.~~ **AMENDED 2026-08-15 (billing final lane): this is a REFUSAL test and never a stub.** The live registry records the PO closing OQ-104 on **2026-08-11 with option A** — *"the BR-BIL-018 back-bill window APPLIES to an upward correction; the correction workflow is NOT a route around the cap; downward corrections are unaffected at any age"*, shown with the figure *a 2023 under-read corrected now would bill $1,840 for a period 30 months back*. `corrections.refuse_upward_beyond_window` raises `BillingRuleError`; a not-implemented stub against a CLOSED id is what gate G8 exists to catch. The downward path is unaffected **at any age**, and that asymmetry is the ruling — both halves are asserted in `test_us_bil_015_tc16`. The `blocked_by` on this story's frontmatter was stale for the same reason and is now `[]` |
| TC-17 *(RULED 2026-08-12 — was blocked on OQ-105)* | Reason "goodwill", class **C**: $25 credit against a $247.30 invoice → balance **222.30** (GT-6) | Preview and credit-note arithmetic assert GT-6 as before, and **the posting half is now ruled: DR write-off / CR customer credit balance** (PO 2026-08-12, *"a separate write-off account"*, OQ-105 + OQ-168 CLOSED). **The original service revenue is NOT reversed** — assert that no 41xx bucket moves, which is the whole content of the ruling; the customer owes **222.30** either way. **The account resolves through the write-off DESIGNATION, never a hardcoded code**: concessions get their own account under OQ-187 but that needs a finance re-sign, so until it is signed the designation resolves to the seeded "Bad debt" account and the switch is one designation. The `NotImplementedError("OQ-105")` stub at the handoff is retired |
| TC-18 *(2026-08-12, OQ-121)* | The same class-C case reaches the phase-4 sign-off panel of the run that issued BL-2608-018410 | The panel **counts it like a replacement** (PO 2026-08-12, *"no rebill , Count it like a replacement"*) — **1 bill, 1 account, $222.30** — so a corrected account is never invisible to the person signing off. GROSS **247.30** and CREDIT **25.00** both travel on the summary beside the net (BR-BIL-064); a signed sum of the credit-note column would read **$272.30** and is the defect DEF-085 records |

**4 · Test Data** — WE-9 verbatim: original BL-2608-018410 (ACC-1042, 247.87 current, paid in full); corrected water 6 kgal → figures per TC-1; customer credit **$19.92** carried per allocation rules. Reason code "wrong read" (seeded set: wrong read · wrong rate/plan · wrong tax · missed charge · goodwill · theft-restated — r1.2). Actors: Priya Menon (initiates), Alex Reed (System Admin approves). Isolation: Lone Star Ridge case on LSR-2608-000102.
**Added 2026-08-11 for the taxonomy + preview (BR-BIL-041/044):** the original bill's full line set is **WE-1**, which is the same fixture bill — DR AR 247.87 / CR 4100 88.60 · 4105 12.00 · 4110 39.50 · 4115 8.00 · 4120 15.80 · 4130 18.00 · 4150 40.00 · 2200-03 20.97 · 4200 5.00 — so the correction fixture needs **no new numbers**, only WE-1 read alongside WE-9 (see §7 for the derivation). Tax authorities: TX State 6.25% · Travis County 1.00% · City franchise 2.00% · PUC 0.20% (WE-1 fixture). Account balance before the case = **0.00** (bill total due 292.87 = current 247.87 + prior balance 45.00, paid in full). Class-fixtures: **D** — the same account with `customer_name` misspelt and no money change (US-BIL-031); **C** — GT-6's $247.30 invoice with a $25 goodwill credit → balance 222.30. Reason-code class map (seeded, PROPOSED): wrong read=R · wrong rate/plan=R · wrong tax=R · missed charge=R · charge billed in error=R · goodwill=**C** · theft-restated=R · name/address/label=**D** · template-language=**D**.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Correction case | S30 Fix a bill | BR-BIL-014 | `correction_cases` (reason code, scope single, status, approver — r10 #9) | row | user-input | one open case per bill |
| Reason code | S30 | BR-BIL-014 | reason-code lookup (r10 #13, tenant-extensible) | uuid | reference-data | required |
| Impact preview | S30 | BR-BIL-014 | computed artifact persisted on the case (the approval artifact) | jsonb/rows | computed-display | no money writes |
| Credit note | — | BR-BIL-004 | `credit_notes` (original_invoice_id, amount) + full GL reversal handoff | numeric(18,6) | system-derived | references original; append-only |
| Rebill | S30 | BR-BIL-014 | new `invoices` row (`bill_type=rebill`, cites original) + lines w/ own GL stamps | rows | system-derived | current template version pinned |
| Re-allocation plan | S30 preview | BR-BIL-014 + BR-PAY-010 | plan emitted to payments (execution payments-owned) | rows | system-derived | overpayment → carried credit |
| Approval | S30 | BR-BIL-014 + OQ-072 | case approver + timestamp | uuid/ts | user-input | System Admin role, server-enforced |
| Audit | — | CLAUDE.md #7 | `audit_log` on case, credit note, rebill, delivery | jsonb | system-derived | every record touched |
| Reason **class** | S30 (derived, read-only) | BR-BIL-041 | reason-code lookup += `class` enum restatement\|credit_only\|document (**column does not exist** — r10 #13 mints the lookup only) | enum | reference-data | required on every reason incl. tenant-added; never operator-selected on the case |
| Preview artifact hash | S30 | BR-BIL-044 | `correction_cases.preview_hash` + the computed inputs it covers | text | system-derived | execution refused on mismatch |
| Posting period | S30 preview §5 | BR-BIL-045 | resolved against BR-TEN-038 at preview and re-checked at execute | date/period | computed-display | shown before confirm, always |
| Chain links | S30 | BR-BIL-048 · **BR-BIL-064 as amended 2026-08-12** | the link is carried **on the NEW bill** (PO 2026-08-12, OQ-120: *"Nod to add the link on the new bill"*) — the replacement points back at what it replaces, because the original is immutable and must not gain a column after issue (BR-BIL-004). **Still unbuilt**, but the SHAPE is no longer an open question; `credit_notes.correction_case_id` likewise | uuid | system-derived | only the latest chain member is correctable |
| Warning set | S30 preview §8 | BR-BIL-043/045 | computed on the case (zero-delta on R · closed period · in-flight payment/NSF · upward beyond window OQ-104 · closed account · chain depth) | rows | computed-display | never suppressible |

**6 · Acceptance**
- Given WE-9, Then the preview reproduces the workbook exactly and nothing money-bearing exists before approval.
- Given approval, Then credit note (−247.87, referencing the original), rebill (+227.95, typed rebill, current template pinned) and the 19.92 carried credit all exist, posting reversal is handed off, and delivery queues.
- Given the original, Then it is untouched forever and the chain is navigable both ways.
- Given retries or missing approval, Then nothing duplicates and nothing bypasses the gate.
- Given a reason code, Then the mechanism is DERIVED from its class and cannot be supplied by the caller; a document reason that moves money is refused and a money reason can never be discharged by a reprint (BR-BIL-041/043).
- Given the approval screen, Then all nine preview sections are present including both journal entries, the net per GL bucket, the posting period and the plain-language balance sentence — and the approver can reproduce the delta from what is on screen without opening another record (BR-BIL-044).
- Given any input drift between preview and execute, Then execution is refused and the stale artifact is retained.

**7 · Finance Calculation** — CONFIRMED (WE-9/BS-5, workbook verbatim). Recompute: water **26.50** (was 39.50) · sewer **10.60** (was 15.80) · taxable **203.70** → tax **19.25** (12.73 + 2.04 + 4.07 + 0.41) → corrected current **227.95**. Execution: credit note **−247.87** (full GL reversal) + rebill **+227.95** (own stamps) → customer credit **19.92**, carried per allocation rules. GT ref: **GT-6**.

**7a · The impact preview, worked in full (PROPOSED 2026-08-11 — presentation of frozen figures; NO new arithmetic)** — every number below is either stated in **WE-1** (the same bill's issued posting) or **WE-9** (its correction), or is the difference between the two. Nothing here is a new fixture and nothing may be read as amending B4/B5. This is what section (2), (3), (5) and (6) of BR-BIL-044 actually render for case **CC-2026-041**, reason "wrong read", class **R**.

**§2 · The lines** — bill **BL-2608-018410**, ACC-1042 (Sarah Whitfield), period Jul 1–31. Changed input: **water read 8 → 6 kgal** (read superseded, BR-MET-053).

| Line | GL | Original | Corrected | Δ |
|---|---|---|---|---|
| Electric usage (TOU 120/200/380 kWh) | 4100 | 88.60 | 88.60 | — |
| Electric base | 4105 | 12.00 | 12.00 | — |
| **Water usage** (8 → **6 kgal**, tiers 0–5 @4.00 / 5–15 @6.50) | 4110 | **39.50** | **26.50** | **−13.00** |
| Water base | 4115 | 8.00 | 8.00 | — |
| **Sewer** (40% of water usage-$, BR-RAT-015) | 4120 | **15.80** | **10.60** | **−5.20** |
| Trash (flat) | 4130 | 18.00 | 18.00 | — |
| Solar capacity (4 units @ $10) | 4150 | 40.00 | 40.00 | — |
| *Taxable subtotal* | | *221.90* | *203.70* | *−18.20* |
| Tax — TX State 6.25% | 2200 | 13.87 | 12.73 | −1.14 |
| Tax — Travis County 1.00% | 2201 | 2.22 | 2.04 | −0.18 |
| Tax — City franchise 2.00% | 2202 | 4.44 | 4.07 | −0.37 |
| Tax — PUC 0.20% | 2203 | 0.44 | 0.41 | −0.03 |
| LATE fee — **non-taxable; computed on a $45.00 prior overdue balance, not on these charges, so it does not move** | 4200 | 5.00 | 5.00 | — |
| **Current charges** | | **247.87** | **227.95** | **−19.92** |

**§3 · The money** — original **$247.87** → corrected **$227.95** → **delta −$19.92** in the customer's favour, of which **−$18.20** is service revenue and **−$1.72** is tax across four authorities. Seven of the twelve lines do not move; showing them is the point, because "only water and sewer changed" is a claim the approver must be able to check rather than take.

**§5 · The ledger handoff** — two balanced entries emitted to the posting service (billing writes no journal lines — CLAUDE.md #5, BR-BIL-011). **The correction is not one net entry**: the credit note reverses the original in full and the rebill posts its own stamps, per WE-9 and J11 step 4.

*JE-A · credit note **CN-2608-000041**, full reversal of BL-2608-018410*
DR 4100 88.60 · 4105 12.00 · 4110 39.50 · 4115 8.00 · 4120 15.80 · 4130 18.00 · 4150 40.00 · 2200-03 20.97 · 4200 5.00 = **247.87** / CR 1200 Accounts receivable **247.87** ✔ balanced

*JE-B · rebill **BL-2608-018997** (`bill_type=rebill`, cites the original, current template version pinned)*
DR 1200 Accounts receivable **227.95** / CR 4100 88.60 · 4105 12.00 · **4110 26.50** · 4115 8.00 · **4120 10.60** · 4130 18.00 · 4150 40.00 · **2200-03 19.25** · 4200 5.00 = **227.95** ✔ balanced

*Net per bucket, which is what the preview leads with* — **4110 Water usage −13.00 · 4120 Sewer −5.20 · 2200-03 Tax payable −1.72 (state −1.14 · county −0.18 · city −0.37 · PUC −0.03) · 1200 AR −19.92**; every other bucket nets to exactly zero, posted and reversed at the same figure. Cross-check: DR 13.00 + 5.20 + 1.72 = 19.92 = CR AR 19.92. **Posting period:** July if open, else the earliest open period (BR-BIL-045/BR-TEN-038) — named on screen before confirm, because the −1.72 changes a remittance basis (BR-LED-002).

**§6 · The customer's balance** — before: **$0.00** (the bill's total due was 292.87 = 247.87 current + 45.00 prior balance, paid in full). Re-allocation plan (BR-PAY-010, executed by payments — billing emits the plan): the 247.87 allocated to the original re-allocates **227.95 to the rebill**, leaving **19.92 unapplied → carried account credit**; the 45.00 against the earlier bill is untouched. After: **−$19.92 (credit)**, rebill amount due **$0.00**. Plain-language line the approver actually reads (BR-BIL-009): *"Sarah has already paid this bill. After the correction she will have paid $19.92 more than she owes. That $19.92 stays on her account as a credit and comes off her next bill; she can ask for it back instead."*

**§4 · Documents** — one credit note (−247.87), one rebill (+227.95, current template version pinned, citing BL-2608-018410); the original document is retained and unchanged. **§8 · Warnings** — none on this case; the same bill in a closed July would raise the period warning (TC-14).

**The document-only contrast, same account, zero arithmetic:** reason "name spelling", class **D** → recomputation delta **$0.00** · credit note **none** · rebill **none** · journal entries **none** · balance before $0.00, after **$0.00** · documents: one reissued instance. The preview for a D-class case renders the same nine sections and four of them say **none** — which is exactly what makes the two mechanisms impossible to confuse on screen.

**8 · Open Questions** — **OQ-104** (upward corrections and the back-bill window — blocks the *positive-delta beyond the tenant window* branch only; TC-16) is now **the only one**. ~~**OQ-105** (which GL a class-C concession debits — blocks the *class-C posting handoff* only; TC-17).~~ **CLOSED 2026-08-12 (PO): *"a separate write-off account"* → DR write-off / CR customer credit balance, GT-6's $222.30 unmoved (TC-17 above). OQ-168 carried the same question under a second id and closes with it.** **The class-R downward path of TC-1..TC-15 is fully specified by WE-1 + WE-9 and is buildable today.** ⚠ **A CONTRADICTION FOUND WHILE PROPAGATING THE 2026-08-12 RULINGS, AND DELIBERATELY NOT RESOLVED HERE — does a class-C concession emit a CREDIT NOTE against the bill, or an account-level credit?** This epic (§1a and TC-17) says *"a partial credit note referencing the original"* and moves the bill's balance to **222.30**. The corrections lane's decision-log row of **2026-08-11** records the opposite reading of the PO's OQ-105 closure of that day — *"you dont touch the bill; you issue new a good will credit; everything remain as it is, it is new good will credit to be applied in new bill"* and *"it will exclude the tax"* — under which the BILL's delta is **$0.00**, no credit note is emitted, and the concession is an account-level credit applied to the NEXT bill. **The 2026-08-12 ruling settles the DEBIT (a separate write-off account) and does not touch this question**, so both readings survive in the corpus and they disagree about what the customer's *current* bill says. **GT-6's frozen 222.30 is reached either way** — as a credit note on this bill, or as a credit carried to the next one — which is exactly why nothing has forced the question. It needs one sentence from the PO and is not a thing an implementer may pick. **MINTED AS OQ-215 on 2026-08-15 (billing final lane, US-BIL-015)** — it had no id until then, which is why nothing was tracking it. `apps/billing/single_correction.py` renders the question into preview section 3 of every class-C case and re-decides nothing; `corrections.build_impact` keeps the reading its own lane was given (the bill's delta is $0.00). Both the GT-6 balance **222.30** and the OQ-121 phase-4 figure (**247.30 gross − 25.00 = 222.30, 1 bill, 1 account**) are identical under both readings, which is exactly why nothing has forced it. BR-BIL-041..045/048 are PROPOSED: the PO stated the requirement on 2026-08-11 and has not ratified the detail — in particular **the seeded reason→class map in §4 is the thing to put to the PO in plain English with its figure** ("a misspelt name changes $0.00 and issues no credit note; a wrong rate changes $19.92 and always issues a credit note plus a corrected bill"), per the 2026-08-11 review mechanism.

---
id: US-BIL-016
epic: EP-BIL-04
module: billing
screens: [S30]
wave: 5
status: draft
blocked_by: []
depends_on: [US-BIL-015]
journeys: [J6, J11]
rules: [BR-BIL-014, BR-BIL-042, BR-BIL-046, BR-BIL-047, BR-BIL-048]
golden_tests: []
finance_calc: confirmed
---
### US-BIL-016 — Bulk corrections: scope selector, staged idempotent execution, per-bill results

**1 · Details** — As a System Admin fixing a systematic error (e.g. a wrong rate applied to a whole cycle), I want ONE correction case scoped in bulk — **by run / cycle / plan / service / date-range** — with a per-bill impact preview (each bill's credit note + rebill + delta + re-allocation plan), one approval covering the reviewed set, and execution as a **staged background job**: idempotent, resumable, progress-visible, finishing with a per-bill result summary (succeeded / failed with reason) — so that a 400-bill fix is one reviewed, gated, auditable operation instead of 400 hand runs (BR-BIL-014 BULK, r1.2). Failed bills stay uncorrected and re-runnable; succeeded bills never re-execute.

**1a · How N corrections are previewed and confirmed TOGETHER (PO 2026-08-11: *"if bill correction is in bulk then how do we handle it"*; BR-BIL-046, PROPOSED)** — the bulk case is the SAME nine-section preview (BR-BIL-044) computed per bill, plus an aggregate panel over the set and a pinned bill list. Four constraints make it reviewable rather than merely large:

1. **The approved set is a LIST, not a query.** The scope selector resolves once, at preview, into concrete bill ids. A bill issued between approval and execution does not silently join a set someone already signed off. (TC-5 already forbids editing the scope; this closes the same hole from the other side.)
2. **The aggregate never nets opposing movements into one reassuring number.** The panel shows N bills · Σ credit notes · Σ rebills · Σ net delta · Σ tax delta **per authority** · **↑ count and sum of bills going UP, ↓ count and sum going DOWN, side by side** · how many accounts end in credit vs owing more · how many rows carry warnings. 100 bills up $50 and 100 bills down $50 net to $0.00 and are a disaster; a single Σ would hide it, so a single Σ is not offered alone.
3. **The per-bill table is the evidence, and it is sorted for the reader.** Sortable, CSV-exportable (IS-9), default order = **warned rows first, then largest absolute delta first** — because a 240-row preview is not read in order and a systematic error announces itself in the outlier, not in the median.
4. **One class per case (BR-BIL-042).** A bulk case may not mix restatements with document reissues: an approver reading a Σ of money deltas is not reviewing reprints, and one approval cannot honestly cover both.

**1b · What a PARTIAL FAILURE does (BR-BIL-047, PROPOSED)** — **one bill is the unit of atomicity, and there is no batch rollback — not "not yet", but never.** A bill's credit note + rebill + posting handoff commit together or not at all. A failed bill leaves **zero artifacts** and stays correctable. Succeeded bills are **never reversed** because a later bill failed: a posted ledger pair cannot be un-posted (hard rule 4) and a delivered bill cannot be un-sent, so a "roll back the batch" button would be a lie in the UI. Consequences, all shown on the case: succeeded bills deliver immediately (a correct corrected bill should not wait on someone else's lock — BR-BIL-016 queues per bill anyway); the case stays **OPEN** while any bill is unresolved, exactly like the pending-billing queue that BR-BIL-034 exists to be; resume re-attempts ONLY the failures; and abandoning a failure is an explicit, reasoned, audited act rather than a case that quietly reports "done".

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-014 (bulk) | Bulk scope by run/cycle/plan/service/date-range; execution = staged background job with progress + per-bill results, idempotent, resumable; same reason-code → preview → Admin approval → deliver → audit chain. | CONFIRMED — PO A-5 escalation + r1.2, 2026-08-08 |
| BR-BIL-004 *(shared)* | Per bill, the mechanics are exactly US-BIL-015's credit note + rebill — originals untouched. | CONFIRMED — CLAUDE.md #4 |
| BR-BIL-046 | The approved set is a PINNED LIST of bills, never a stored query; the aggregate shows up-movements and down-movements separately and never netted; warned rows and largest absolute deltas sort first. | **PROPOSED** — PO 2026-08-11 |
| BR-BIL-047 | One bill = one transaction = the atomicity unit; no batch rollback exists; succeeded bills are never reversed; the case stays open while any bill is unresolved. | **PROPOSED** — derived from CLAUDE.md #4/#5 |
| BR-BIL-042 *(shared)* | One class per bulk case — restatements and document reissues never share an approval. | **PROPOSED** — PO 2026-08-11 |
| BR-BIL-048 *(shared)* | One open case per chain — a bulk case cannot claim a bill a single case already holds. | **PROPOSED** — derived |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Case scoped "run 07-A · service Water · plan Residential Standard", reason "wrong rate/plan" | Preview lists every matching bill with its own credit-note/rebill/delta figures; Σ shown; nothing written |
| TC-2 | Fixture: 3 bills each matching the WE-9 shape | Each per-bill preview = WE-9 figures exactly (credit −247.87 / rebill +227.95 / delta −19.92 per bill); approval covers the reviewed set |
| TC-3 | Execution with an induced failure on bill 2 (its account hits a concurrent lock) | Job completes: results "2 succeeded · 1 failed (reason)"; bill 2's original untouched, no partial artifacts; resume re-attempts ONLY bill 2 |
| TC-4 | Resume after TC-3 | Bill 2 corrects; bills 1/3 not re-executed (idempotent per-bill guard); final results 3/3 |
| TC-5 *(negative)* | Scope edited after approval | Rejected — approval binds the reviewed set; a new scope needs a new preview + approval |
| TC-6 *(negative)* | Second bulk case overlapping an executing case's bills | Blocked for the overlapping bills — one in-flight correction per bill (and per chain, BR-BIL-048) |
| TC-7 *(isolation)* | Lone Star Ridge bulk case | Scope selectors resolve only its runs/plans/bills (RLS) |
| TC-8 | **Aggregate panel on the 3-bill fixture (BR-BIL-046)** | N = **3** · Σ credit notes **−743.61** · Σ rebills **+683.85** · Σ net delta **−59.76** · Σ tax delta **−5.16** split per authority (state −3.42 · county −0.54 · city −1.11 · PUC −0.09) · **↓ 3 bills down $59.76 · ↑ 0 bills up $0.00** · 3 accounts end in credit · 0 warnings. Every figure is a display sum over the per-bill previews — the bulk layer performs no arithmetic of its own |
| TC-9 *(negative)* | A mixed set where 4 bills move up $50.00 each and 4 move down $50.00 each | The panel shows **↑ 4 · +200.00** and **↓ 4 · −200.00** as separate figures; a net of $0.00 is never displayed alone (BR-BIL-046). Proved RED against a build that showed only the net |
| TC-10 | Approval screen ordering on a 240-bill set (J11 fixture) | Warned rows first, then largest absolute delta; the CSV export (IS-9) contains every row in the pinned set with the same figures the screen shows |
| TC-11 *(negative)* | A bill is issued into the same run AFTER approval, matching the original scope query | It does **not** join the approved set (BR-BIL-046); it is reported as unaddressed and needs its own case |
| TC-12 *(negative)* | Operator asks to "undo the batch" after 200 of 240 bills executed | No such action exists and the screen says why: the 200 posted pairs cannot be un-posted and the delivered bills cannot be un-sent (BR-BIL-047). The remedy offered is a NEW correction case over the 200 |
| TC-13 | Case status while 1 of 3 bills is failed and unresolved | Case remains **open** with results "2 succeeded · 1 failed (reason)"; the 2 succeeded bills' documents are already queued for delivery; the case can only close by resuming to success or by an explicit, reasoned, audited abandonment |
| TC-14 *(negative)* | A bulk case scoped with both "wrong rate/plan" (R) and "address" (D) reasons | **REFUSED** at scope time (BR-BIL-042) — one class per bulk case; the operator is told to raise the document reasons as their own case |

**4 · Test Data** — Case CC-2026-014: run 07-A, Water, Residential Standard, reason "wrong rate/plan"; fixture set = 3 WE-9-shaped bills (ACC-1042, ACC-1091, ACC-1130 — identical plan/period/figures), per-bill numbers verbatim WE-9. Induced failure: ACC-1091 locked by a concurrent payment posting. Actors: Alex Reed (initiates + approves as Admin per OQ-072 v1; initiator/approver may be the same role, both recorded). Isolation: Lone Star Ridge case CC-L-003.
**Added 2026-08-11 (BR-BIL-046/047):** the aggregate figures for the 3-bill fixture are the per-bill WE-9 numbers summed and nothing else — 247.87 × 3 = **743.61**, 227.95 × 3 = **683.85**, 19.92 × 3 = **59.76**, tax 1.72 × 3 = **5.16** (state 1.14×3 = 3.42 · county 0.18×3 = 0.54 · city 0.37×3 = 1.11 · PUC 0.03×3 = 0.09). Mixed-direction fixture for TC-9: 8 synthetic bills, 4 at +50.00 and 4 at −50.00, whose only purpose is that their net is 0.00. Large-set fixture = **J11's 240 July bills** with ACC-1042 as the head; J11 deliberately leaves the other 239 deltas engine-computed, so **no aggregate figure is stated for the 240-bill set anywhere** — inventing one would create a fixture finance never signed.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Bulk scope | S30 Fix a bill | BR-BIL-014 | `correction_cases.scope` (run/cycle/plan/service/date-range — r10 #9) | jsonb | user-input | resolves to a concrete bill set at preview |
| Per-bill preview rows | S30 | r1.2 | bulk-correction run rows w/ per-bill computed impact (r10 #9) | rows | computed-display | the approval artifact |
| Execution job + progress | S30 | r1.2 | staged job state on the case; per-bill status queued\|done\|failed(reason) | enum | system-derived | idempotent, resumable |
| Per-bill artifacts | — | US-BIL-015 | `credit_notes` + rebill `invoices` per succeeded bill | rows | system-derived | exactly one set per bill per case |
| Result summary | S30 | r1.2 | computed over per-bill results ("N succeeded · N failed") | counts | computed-display | always shown |
| Pinned bill set | S30 | BR-BIL-046 | the resolved bill ids stored on the case at preview (**not** the scope predicate re-run at execute) | rows | system-derived | later-issued bills never join |
| Aggregate panel | S30 | BR-BIL-046 | computed over the per-bill previews: N · Σ credit · Σ rebill · Σ net · Σ tax per authority · ↑/↓ counts+sums · credit-vs-owing counts · warned count | counts/numeric(18,6) | computed-display | up and down never netted into one figure |
| Case openness | S30 | BR-BIL-047 | case stays open while any per-bill row is unresolved; abandonment = reason + actor + timestamp | enum/text | user-input | reason required to close over failures |

**6 · Acceptance**
- Given a bulk scope, Then the preview enumerates every affected bill with per-bill figures and Σ, and approval binds exactly that set.
- Given execution with failures, Then succeeded bills carry complete artifact sets, failed bills carry none, and resume touches only the failures.
- Given a retry storm, Then per-bill idempotency holds — never a duplicate credit note or rebill.
- Given delivery, Then corrected bills queue per BR-BIL-016 like any issue.
- Given the aggregate panel, Then upward and downward movements are shown separately with their counts and sums, and no screen offers the net alone (BR-BIL-046).
- Given a partially failed case, Then no batch-rollback action exists anywhere in the UI or the API, the case stays open, and closing it over unresolved failures demands a recorded reason (BR-BIL-047).

**7 · Finance Calculation** — CONFIRMED (per-bill math = US-BIL-015/WE-9 verbatim; the bulk layer adds no arithmetic of its own — Σ figures are display sums over per-bill previews). Worked: each fixture bill previews credit **−247.87** / rebill **+227.95** / customer credit **19.92** (WE-9). Ref: BS-22.
**7a · The aggregate, worked (PROPOSED 2026-08-11 — display sums only, per §7's own statement)** — 3-bill fixture: Σ credit **−743.61** · Σ rebill **+683.85** · Σ net **−59.76** · Σ tax **−5.16** (state −3.42 · county −0.54 · city −1.11 · PUC −0.09) · ↓ 3 bills / −59.76 · ↑ 0 bills / 0.00 · 3 accounts end in credit · 0 warnings. Tie-out the panel must assert: **Σ credit − Σ rebill = Σ net** (743.61 − 683.85 = 59.76) and **Σ net = Σ of the per-bill deltas** — the same redundancy BR-BIL-032 uses on the bill payload, for the same reason: drift between a total and its parts is otherwise invisible.

**8 · Open Questions** — None of its own. ~~The class-C and upward-correction boundaries (**OQ-105**, **OQ-104**)~~ **OQ-105 CLOSED 2026-08-12** (the class-C posting is DR write-off / CR customer credit balance — US-BIL-015 TC-17), so **only the upward-correction boundary (OQ-104)** reaches bulk, and it does so through US-BIL-015's per-bill mechanics; a bulk case whose direction hits that boundary is blocked for the same reason and by the same stub. ⚠ **A bulk case of class C now has a phase-4 consequence:** each credit-only bill **counts in the sign-off panel like a replacement** (OQ-121, BR-BIL-064), so the aggregate's up/down counts must include them rather than treating a no-rebill correction as nothing.

---
id: US-BIL-017
epic: EP-BIL-04
module: billing
screens: [S30, S8]
wave: 5
status: draft
blocked_by: []
depends_on: [US-TEN-010, US-SHL-014]
journeys: [J6]
rules: [BR-BIL-009, BR-BIL-014, BR-BIL-041, BR-BIL-044]
golden_tests: []
finance_calc: none
---
### US-BIL-017 — The approval gate + correction reason codes (reference data)

**1 · Details** — As a System Admin, I want the correction approval gate and its vocabulary owned in one place: **reason codes** as tenant-extensible reference data (seeded: wrong read · wrong rate/plan · wrong tax · missed charge · goodwill · theft-restated — r1.2; managed in Settings → Reference data per the platform lookup pattern), and the **gate rule**: v1, ALL corrections require System Admin approval (threshold-based = v2, OQ-072 closed); the correction-approval threshold setting exists in tenant config (BR-BIL-021) but is inert in v1. The same gate machinery serves back-bills and penalty bills (BR-BIL-018/019, r1.5 "same approval gate"). Every gate decision shows the operator plain-language consequences before confirm (BR-BIL-009 pattern) and is audited. Approvals are server-enforced; UI gating is convenience (IS-6).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-014 (gate) | v1: ALL corrections require System Admin approval; threshold-based approval is v2. NO money-bearing write before approval; the impact preview is the approval artifact. | CONFIRMED — OQ-072 closed (PO F-round) |
| BR-BIL-014 (reason codes) | Correction reason codes are reference data, tenant-extensible. | CONFIRMED — PO A-5 + r10 #13 |
| BR-BIL-041 | Each reason row carries a **class** — restatement \| credit_only \| document — and the class derives the case's mechanism. Required on seeded AND tenant-added rows; a reason with no class cannot be saved and cannot be cited by a case. | **PROPOSED** — PO 2026-08-11 |
| BR-BIL-044 *(served)* | The gate renders the same nine-section preview artifact this story's approval screen shows — one preview definition, three consumers (correction, back-bill, penalty). | **PROPOSED** — PO 2026-08-11 |
| BR-BIL-021 | `correction-approval threshold` is a seeded tenant setting (v2 activation); nothing hardcoded. | CONFIRMED — PO Lane B-2 + OQ-072 ("threshold v2") |
| BR-BIL-009 | Approval/void surfaces show plain-language consequence messaging before confirm. | CONFIRMED — PO Q&A R6 (OQ-012) |
| BR-BIL-018/019 *(served)* | Back-bills and penalty bills pass through this same gate. | CONFIRMED — r1.5 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Reference-data list "Correction reasons" | Seeded six rows; tenant adds "meter-swap mislink" → usable immediately in cases; audit-lock pattern once used (IS-1: deactivate allowed, delete blocked) |
| TC-1a | The same list shows each row's **class** | Seeded map renders: wrong read · wrong rate/plan · wrong tax · missed charge · theft-restated = **restatement**; goodwill = **credit-only**; and the two document rows a tenant adds for name/address = **document** (BR-BIL-041). The class is shown in the operator's words ("issues a corrected bill" / "issues a credit only" / "reprints the document, no money"), never as an enum value |
| TC-1b *(negative)* | Tenant adds a reason with no class | **Refused at save** — a classless reason would let the case pick its own mechanism, which is the exact failure BR-BIL-041 exists to prevent. The tenant-added "meter-swap mislink" saves once classed **restatement** |
| TC-1c *(negative)* | Tenant edits a used reason's class from document to restatement | Refused under the IS-1 audit-lock pattern — historical cases were approved on what the class meant then; the tenant deactivates and adds a new row instead |
| TC-2 | Clerk submits a case; Clerk attempts to approve it | Approve action absent/disabled-with-reason for Clerk; server rejects a forged approve (System Admin only, OQ-072 v1) |
| TC-3 | Admin approval screen | Shows the impact preview + plain-language consequences (credit note, rebill, balance effect, re-allocation) before confirm (BR-BIL-009); decision + approver + timestamp audited |
| TC-4 | Back-bill (US-BIL-013) and penalty (US-BIL-014) submissions | Route through this identical gate record; one gate implementation, three consumers |
| TC-5 *(negative)* | Tenant sets the correction-approval threshold to $100 expecting auto-approval below it | Setting stores but the gate still requires Admin for ALL cases (v1 rule; threshold activates in v2) — behavior documented on the setting |
| TC-6 *(isolation)* | Lone Star Ridge reason codes + approvals | Own lookup rows and approver pool only (RLS) |

**4 · Test Data** — Seeded reasons per r1.2 (six); tenant-added "meter-swap mislink". Gate fixtures: case CC-2026-014 (US-BIL-016), back-bill ACC-1888 (US-BIL-013), penalty ACC-1544 (US-BIL-014). Threshold setting fixture: $100 (stored, inert v1). Actors: Priya Menon (Clerk, cannot approve), Alex Reed (System Admin). Isolation: Lone Star Ridge, 4 seeded reasons retained.
**Added 2026-08-11 (BR-BIL-041):** the seeded class map — wrong read **R** · wrong rate/plan **R** · wrong tax **R** · missed charge **R** · goodwill **C** · theft-restated **R**, plus two document rows the seed set does not yet contain and which the taxonomy requires (**customer name/details** and **service or mailing address**, both **D**). Tenant-added "meter-swap mislink" = **R**. This map is the thing to put to the PO for ratification, in the plain-English form the 2026-08-11 review mechanism requires.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Reason-code lookup | S8 Reference data | r10 #13 | correction/penalty reason lookups (tenant-extensible) | rows | reference-data | IS-1 audit-lock when used |
| Reason **class** | S8 Reference data | BR-BIL-041 | `class` enum restatement\|credit_only\|document on the correction-reason lookup — **not in r10 #13, does not exist** | enum | reference-data | required at save; audit-locked once used |
| Gate record | S30 | BR-BIL-014 | `correction_cases.status/approver` (r10 #9) — shared by backbill/penalty flows | enum/uuid | user-input | System Admin, server-side |
| Consequence messaging | S30 modal | BR-BIL-009 | rendered from the persisted impact preview | text | computed-display | before confirm, always |
| Approval threshold setting | S66 | BR-BIL-021 + OQ-072 | tenant billing settings `correction approval config` (r10 #6) | numeric USD | reference-data | stored; inert in v1 (v2 activation) |
| Gate audit | — | CLAUDE.md #7 | `audit_log` `correction.approved/rejected` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given the seeded + tenant-added reason codes, Then cases can only cite lookup rows, with the audit-lock pattern on used rows.
- Given any correction/back-bill/penalty case, Then execution is impossible without a System Admin gate record, server-enforced, with consequences shown before confirm.
- Given the threshold setting, Then it stores but changes nothing in v1.
- Given tenants, Then vocabularies and approvals never cross.
- Given every reason row, Then it carries a class, the class is described to the operator in words rather than as an enum, and a classless reason can neither be saved nor cited (BR-BIL-041).

**7 · Finance Calculation** — N/A (the gate moves no money; per-case figures live in US-BIL-015/016 §7).

**8 · Open Questions** — None (OQ-072 closed; threshold activation is a v2 scope note, not a question). The reason **class** column (BR-BIL-041) is PROPOSED, not open: the PO stated the requirement on 2026-08-11 and the seeded map in §4 awaits ratification.

---
id: US-BIL-031
epic: EP-BIL-04
module: billing
screens: [S30]
wave: 5
status: draft
blocked_by: []
depends_on: [US-BIL-015, US-BIL-017]
journeys: [J6, J18]
rules: [BR-BIL-041, BR-BIL-043, BR-BIL-049, BR-BIL-030]
golden_tests: []
finance_calc: none
---
### US-BIL-031 — Document-only correction: the bill is right, the document is wrong

**1 · Details** — As a Billing Clerk told that a bill went out with the customer's name misspelt, the wrong service address, or the wrong template language, I want a correction case that fixes **the document and nothing else**: no credit note, no rebill, no journal entry, no balance movement — the preview's money delta is literally **$0.00** and four of its nine sections say "none" — so that a spelling mistake never touches the ledger and never lands as a credit on somebody's account (BR-BIL-041 class **D**, BR-BIL-043). This is the PO's *"name or address changes"* half of the 2026-08-11 statement, and it is a different mechanism from a restatement, not a cheaper version of one.

Two things make it awkward and both are load-bearing. First, **the issued document can never be rewritten**: `invoices.issued_snapshot` is frozen by the immutability trigger — deliberately, because a snapshot that can be edited later is not a snapshot (BR-BIL-030, and the trigger refuses the UPDATE outright). So the only lawful output is a NEW document instance, and **there is nowhere in the schema to put one today**. Second, **fixing the customer's actual name is not this workflow** — that is a customers-module edit governing future documents (BR-BIL-049); this case decides only what the already-sent document says, and records which master-data change it reflects.

~~**Blocked by OQ-103**, which is the fork: does a document-only correction (a) REISSUE a corrected instance of the historical bill, (b) leave history alone and simply re-send the ORIGINAL document to the corrected address, or (c) split by reason — address reissues, name does not? And whichever wins: which document does a later reprint or dispute render by default? Implement to the boundary — reason class, case creation, the zero-money preview and the refusal guard are all buildable — and stub the artifact at `raise NotImplementedError("OQ-103")`.~~

**RULED 2026-08-12 (PO) — option (a), and the reprint half with it.** Verbatim: *"Reissue a corrected copy"*. **(1) THE ARTIFACT (OQ-103 CLOSED):** the case renders a **NEW document instance from a corrected COPY of the snapshot** and attaches it to the original bill; the bill, its lines and its frozen `issued_snapshot` are untouched (BR-BIL-004/030). **(2) WHICH DOCUMENT A LATER REPRINT RENDERS (OQ-169 CLOSED):** with two instances on file, a reprint, a re-send and a dispute copy render **the CORRECTED one** — *"that is the document the customer is entitled to"*. **(3) REISSUES ACCUMULATE (DEF-084 ruled, verbatim *"Accumilate"*):** each instance is composed from **the instance before it**, never from the invoice's frozen payload. **Worked, and it is the defect this closes:** July's bill goes out misspelt *Sara Whitfield*; a clerk fixes the name → instance 1 reads *Sarah Whitfield*; a week later somebody fixes the service address → composing from the original would give instance 2 the corrected address **and the misspelt name back**, and since instance 2 is now what the customer receives, the second correction would **silently undo the first on the paper they hold**. Under the ruling instance 2 carries both fixes. **The risk accepted, stated plainly:** accumulating carries forward a correction somebody later decides was wrong, and undoing one is a further correction rather than a revert. ⚠ **One reading is the lane's and NOT the PO's:** with TWO reissues on file the **NEWEST** wins — the PO was shown one reissue, so that is HUMAN-REVIEW-PENDING and is exactly where DEF-084 turns dangerous. **What is still absent is the WRITE TARGET, not the rule:** there is no document-instance table in B2 (§5 below), so the story is buildable to the schema and no further.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-041 | Class **D**: no credit note, no rebill, no posting handoff, balance delta exactly $0.00; the artifact is a reissued document instance. | **PROPOSED** — PO 2026-08-11 |
| BR-BIL-043 | A D-class case whose computed money delta is non-zero is REFUSED — the reason is wrong or the wrong bill was picked. | **PROPOSED** — derived, hard-won law 3 |
| BR-BIL-049 | A correction never edits master data and a master-data edit is never a correction; the case records which master-data change it reflects. | **PROPOSED** — PO 2026-08-11 |
| BR-BIL-030 *(consumed)* | The bill is locked at issue and its snapshot is frozen — which is exactly why a document fix must produce a new instance rather than an edit. | CONFIRMED — PO 2026-08-10 |
| BR-BIL-026/031 *(consumed)* | Template + version pinned at issue; presentation and data are separate version axes — a template change never re-renders history. | CONFIRMED — PO Lane B-7 / 2026-08-10 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Case on BL-2608-018410, reason "customer name" (class D): "Sara Whitfield" → "Sarah Whitfield" | Preview renders all nine sections: money delta **$0.00** · credit note **none** · rebill **none** · journal entries **none** · balance before $0.00 → after **$0.00** · documents: one reissued instance. The customers-module name change is referenced, not performed here (BR-BIL-049) |
| TC-2 | Approval + execution | No `credit_notes` row, no `invoices` row, no posting handoff emitted — asserted by counting rows before and after, not by reading the UI. Audit rows on the case and the document |
| TC-3 | The original invoice afterwards | `status` still `issued`/`paid` — **not** `corrected`, because nothing about what is owed was corrected; money columns and `issued_snapshot` byte-identical (the trigger would refuse otherwise) |
| TC-4 *(negative)* | D-class case where the recomputation also moves money | **REFUSED** (BR-BIL-043), naming the delta; the operator is directed to the restatement reason. Proved RED first |
| TC-5 *(negative)* | Operator tries to fix the customer's master record from inside the case | Not offered — the case links to the customers-module action and records the reference (BR-BIL-049); two transactions, two audit trails |
| TC-6 *(RULED 2026-08-12 — was blocked on OQ-103)* | Execution reaches the artifact step | A **corrected document instance** is written against the original bill and the invoice is untouched (PO 2026-08-12, *"Reissue a corrected copy"*). **The boundary that remains is the SCHEMA, not the rule:** no document-instance table exists in B2, so a build against today's schema stops there and says so by name — never `NotImplementedError("OQ-103")`, which is now a closed question |
| TC-8 *(2026-08-12, OQ-169)* | BL-2608-018410 is reprinted, re-sent and produced as a dispute copy AFTER instance 1 exists | All three render **instance 1 (the corrected one)**, not the original — *"that is the document the customer is entitled to"*. The original instance is retained and reachable, because BR-BIL-030's reproducibility guarantee still has to hold for what was actually posted |
| TC-9 *(2026-08-12, DEF-084 — the accumulation guard)* | Case 1 fixes the name *Sara → Sarah*; a week later case 2 fixes the service address | Instance 2 carries **BOTH** fixes — it is composed from **instance 1**, never from `issued_snapshot`. **Proved RED first (hard-won law 7):** composing from the invoice payload reinstates *Sara* on the document the customer now receives, which is the defect the ruling closes |
| TC-7 *(isolation)* | Lone Star Ridge document case | Own bills and reason rows only (RLS) |

**4 · Test Data** — BL-2608-018410 / ACC-1042, issued with `customer_name` = "Sara Whitfield" in `issued_snapshot`; the corrected value "Sarah Whitfield" lives on the customer record. Address fixture: the J18 returned-mail bill, delivered nowhere because the service address was wrong — the case that most obviously wants a reissue, and the case the PO's 2026-08-12 ruling was given for. **Accumulation fixture (DEF-084):** the SAME bill corrected twice — case 1 fixes the name, case 2 fixes the service address a week later — where instance 2 must carry both and composing from `issued_snapshot` reinstates *Sara*. Reason rows: "customer name/details" and "service or mailing address", both class **D** (US-BIL-017 §4 — neither is in the r1.2 seeded six). Actors: Priya Menon (initiates), Alex Reed (approves — the gate applies to every correction in v1, OQ-072, including ones that move no money).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Document case | S30 | BR-BIL-041 | `correction_cases` with class `document` (r10 #9 — table not built) | row | user-input | one open case per chain |
| Money delta | S30 preview | BR-BIL-043 | computed, asserted **= 0.00** | numeric(18,6) | computed-display | non-zero → refuse |
| Reissued document instance | S30 | BR-BIL-041 · **BR-BIL-030 as amended 2026-08-12** | **no target exists yet** — `issued_snapshot` is frozen (correctly) and a document-instance table is unbuilt; **it is no longer UNSPECIFIED: the ruling of 2026-08-12 says what it must hold** — an ordered set of instances per bill, each a corrected COPY of the one before it, with the latest being what a reprint renders (OQ-103 · OQ-169 · DEF-084) | jsonb/rows | system-derived | schema-blocked, rule-settled |
| Master-data reference | S30 | BR-BIL-049 | link to the customers-module change the case reflects | uuid | user-input | recorded, never performed here |
| Audit | — | CLAUDE.md #7 | `audit_log` on case + document | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a document-class case, Then no money-bearing row of any kind is created and the ledger is not touched — proved by row counts, not by inspection.
- Given a document-class case whose recomputation moves money, Then it is refused before anything is written.
- Given the original invoice, Then its status, its money and its snapshot are unchanged forever.
- Given a second document correction on the same bill, Then the new instance is composed from the PREVIOUS instance and carries every earlier fix (PO 2026-08-12, *"Accumilate"*), and a later reprint renders the newest instance.
- Given today's schema, Then the artifact step stops at the missing document-instance table and names it — the RULE is settled and no reissue shape is guessed.

**7 · Finance Calculation** — N/A **and that is the entire point**: a document correction has no finance calculation, which is what distinguishes it from every other row in the taxonomy. The preview still renders the money sections, showing $0.00 and "none", because an approver must see that nothing moves rather than infer it from an absent section.

**8 · Open Questions** — ~~**OQ-103** (reissue vs forward-only, and which document a later reprint renders) blocks the artifact and therefore the story.~~ **NONE. OQ-103 and OQ-169 both CLOSED 2026-08-12 (PO): *"Reissue a corrected copy"*, a later reprint renders the corrected one, and reissues ACCUMULATE (DEF-084).** The story is no longer blocked on a decision — what remains is the missing document-instance table (§5, and the closing section of this file). ⚠ **One thing is HUMAN-REVIEW-PENDING rather than ruled:** with TWO reissues the NEWEST wins; the PO was shown one reissue, and a signature covers only what was shown.

---

## What this workflow needs that the repo does not have (named 2026-08-11, NOT built)

Documentation only — no code, no migrations. This section exists because hard-won law 1 says a document describing a guarantee is not the guarantee: everything below is absent, and a reader who assumes otherwise will build against nothing.

**Tables and columns.** `apps/billing/models.py` ships the invoice core and states in its own exceptions trailer that the corrections workflow (r10 #9) is a later wave, so:
1. **`correction_cases`** — specified at B2 Addendum **r10 #9**, not built. Needs beyond r10's list: the **derived class** (BR-BIL-041), the **persisted preview artifact + its content hash** (BR-BIL-044), the **resolved posting period** (BR-BIL-045), and the **pinned bill set** for a bulk case (BR-BIL-046 — a stored list, explicitly not the scope predicate).
2. **Per-bill result rows for a bulk case** — r10 #9 says "bulk runs w/ per-bill results" and names no table. Needs: bill, computed impact, status `queued|done|failed`, failure reason, and the ids of the credit note and rebill it produced, so the case's own claim of success is checkable against the artifacts (BR-BIL-047).
3. **A `class` column on the correction-reason lookup** — r10 #13 mints the lookup as reference data with no class. Without it BR-BIL-041 has nothing to derive from and the mechanism becomes a dropdown, which is the failure the taxonomy exists to prevent.
4. **Somewhere to put a reissued document.** `invoices.issued_snapshot` is frozen by the `0002` immutability trigger — correctly. There is no reissue/document-instance table, so a class-D correction has literally no write target (US-BIL-031 §5). ⚠ **UPDATED 2026-08-12: the DECISION is no longer missing, only the table.** The PO ruled the shape (OQ-103 · OQ-169 · DEF-084), so the table must hold an **ordered set of instances per bill**, each composed from the previous one, with the **latest** being what a reprint, a re-send and a dispute copy render — and the original instance retained, because BR-BIL-030's reproducibility guarantee still has to answer *"what did we actually post?"*.
5. **The chain's rebill leg.** `credit_notes.original_invoice_id` gives one edge; **`invoices` has no `corrects_invoice_id`** and neither `credit_notes` nor `adjustments` carries a `correction_case_id`. US-BIL-015 TC-3's "chain original ↔ credit note ↔ rebill, navigable both ways" and BR-BIL-048's latest-in-chain rule are both unimplementable today. ⚠ **UPDATED 2026-08-12 (PO ruling, OQ-120 CLOSED — *"Nod to add the link on the new bill"*): the column belongs on the REPLACEMENT, not on the original.** The original is immutable and must not gain a column after issue (BR-BIL-004), so the direction that survives is rebill → original. That also settles what BR-BIL-064's phase-4 panel follows.
6. **Ledger.** The module has no tables at all (r13 is unbuilt), and the **shape of the posting handoff billing emits is undefined** — the preview's §5 renders journal entries that nothing can currently produce or receive. Billing writes no journal lines either way (CLAUDE.md #5); what is missing is the contract, not the writer.
7. **`invoices.bill_payload` + `payload_version`.** BR-BIL-030 is CONFIRMED and specifies both columns, NOT NULL; the built model carries a nullable `issued_snapshot` instead. Reported, not resolved — reconciling a CONFIRMED rule with the shipped column is its own change, and a correction that re-snapshots needs to know which of the two it is writing.

**Rules.** BR-BIL-041..049, added to `02-business-rules.md` as PROPOSED on 2026-08-11 and awaiting PO ratification. BR-BIL-014 stays CONFIRMED and untouched — the new rules refine it and none contradicts it.

**Tests and fixtures.** No golden test covers: an **upward** correction (every fixture moves down — GT-25/WE-9 and GT-6 both reduce), a **class-C concession's POSTING half** (GT-6 pins the arithmetic and balance 222.30, not the GL — ⚠ **the GL is RULED since 2026-08-12, DR write-off / CR customer credit, so this is now a missing TEST rather than a missing decision, and B5 gains no new frozen figure because the balance does not move**), a **document-only correction** (no money to pin, so it needs a row-count assertion instead), or **an aggregate over a mixed-direction bulk set** (US-BIL-016 TC-9's up/down fixture is defined here and exists nowhere else). The isolation and immutability suites already cover T5-01 and T5-11 and need nothing new. Per hard-won law 7, each new guard — the D-class refusal, the derived-mechanism refusal, the netted-aggregate refusal — must be shown RED against a build that lacks it before it is trusted green.

# EP-BIL-07 — Bills list, bill detail & void

**Module:** billing · **Wave:** W3 (list/detail) + W5 (void — reversing entries) · **Screens:** S30 · **Status:** draft (BR-BIL-001..029 all CONFIRMED — session closed 2026-08-08)

## Scope
**In:** the S30 **All bills** list (capability row per B9/IS-5), the **bill detail view** (document render from the pinned version, line detail with GL stamps, A19 summary box, run/correction/delivery linkage, audit), and **void** with plain-language consequence messaging (BR-BIL-009) under the OQ-012 closure windows (free void while unpaid + same period; otherwise reverse payment first + Admin/Executive approval; always reversing entries — never deletion).
**Out:** account-scoped bills tab (US-CUS-010 read-model) · Print bill / Send statement modals (US-CUS-014 — render via the US-BIL-022 pin) · correction workflow (EP-BIL-04 — "Corrected" status here links into it) · payment reversal execution (payments, BR-PAY-011) · ledger reversal execution (posting service 🔒, W5).
**Tables:** `invoices`, `invoice_lines` (reads); void status + reversal handoff.

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S30 · All bills | bill #, account #, customer name | status segments All/Draft/Issued/Paid/Past-due/Corrected (prototype) + bill_type (cycle/first/final/rebill/backbill/penalty), cycle, run, date range | issue date desc | bill #, issue date, due date, total, status | Bill # · Cycle · Account · Customer · Issue date · Due date · Total · Status / +bill_type, run, template vN, delivery status (IS-5 chooser, identity column always visible) | View detail · Reprint (US-BIL-022) · Correct (→ EP-BIL-04) · Void (US-BIL-027, state-gated) | — (money-bearing bulk actions live in their own flows) | CSV — current filters + visible columns, money 2dp (IS-9) |

## Stories

---
id: US-BIL-025
epic: EP-BIL-07
module: billing
screens: [S30]
wave: 3
status: draft
blocked_by: []
depends_on: [US-BIL-005, US-SHL-006, US-SHL-007]
journeys: [J2]
rules: [BR-BIL-004, BR-BIL-022]
golden_tests: []
finance_calc: none
---
### US-BIL-025 — S30 All-bills list (search, segments, dynamic columns, export)

**1 · Details** — As a Billing Clerk, I want every bill in one server-side list (S30 All bills): search bill #/account/customer (IS-3), status segments per the prototype (All · Draft · Issued · Paid · Past-due · Corrected) plus bill_type/cycle/run/date filters as URL-persisted chips (IS-4), default sort issue-date desc (IS-2), the IS-5 column chooser (per-user persisted), and CSV export following filters + visible columns (IS-9) — so that any bill is findable in seconds across drafts, issued history, and correction chains. Row states drive actions (IS-6): drafts open in their run; issued rows offer Reprint/Correct/Void per state; corrected rows badge and link their chain. Money renders per tenant Regional settings (IS-8).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-004 | The list exposes immutable issued history — no edit affordance exists on any issued row; corrections/void are the only mutation entry points (both flow to their gated stories). | CONFIRMED — B2 §billing, CLAUDE.md #4 |
| BR-BIL-022 | Bill numbers render in the tenant's configured format (`BL-{YYMM}-{seq}` default). | CONFIRMED — PO Lane B-3, 2026-08-08 |
| B9 IS-2/3/4/5/6/9 *(cited)* | Table/search/filter/columns/actions/export behaviors are the platform standards — declared in the capability row, not restated. | CONFIRMED — B9 (PO-confirmed IS-5 universal) |
| A5 statuses *(cited)* | Status vocabulary: draft · issued · paid · past-due · corrected · void (prototype segments + r10 lifecycle). | CONFIRMED — A5/prototype extraction |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Default load (Brazos Bend, 7,240 bills lifetime) | Page 1 of 25 rows, issue-date desc; columns per the capability default; KPI sub-header per prototype |
| TC-2 | Search "1042"; segment Past-due | Server-side match on bill #/account/customer; Past-due segment shows only past-due rows; filter chips in the URL — shareable |
| TC-3 | Column chooser: add bill_type + template vN, hide Cycle | Persisted per user (BR-SHL-027 pattern); export now carries the visible set |
| TC-4 | Corrected chain row (WE-9 set) | Original shows "Corrected" badge; opening it links credit note + rebill both ways |
| TC-5 *(negative)* | Any inline-edit attempt on an issued row (double-click a total, forged PATCH) | No edit affordance; server rejects — immutable history (BR-BIL-004) |
| TC-6 *(negative)* | Export requested while a filter matches 0 rows | Valid empty CSV with headers (IS-7/IS-9 states) — no error |
| TC-7 *(isolation)* | Lone Star Ridge list | Only its bills; a Brazos Bend bill # in search returns nothing; direct URL 404s (RLS) |

**4 · Test Data** — Brazos Bend: 7,240 bills lifetime (prototype header); rows incl. BL-2608-018410 (WE-1, issued), the WE-9 chain (corrected original + rebill), drafts from an open run, past-due fixture ACC-3015. Export: `bills-brazos-bend-20260808.csv`. Actors: Priya Menon. Isolation: J. Okafor, Lone Star Ridge (210 bills).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| List row | S30 | prototype-extracted (columns) | read-model over `invoices` (+account/customer joins via service fn) | rows | computed-display | server-side page/sort/filter |
| Status segments | S30 | prototype-extracted | `invoices.status` (+derived past-due = issued ∧ unpaid ∧ due_date < today) | enum | computed-display | past-due derived, never stored |
| bill_type filter | S30 | r10 #12 | `invoices.bill_type` | enum | computed-display | 6 values |
| Column set | S30 | IS-5 | per-user preference (BR-SHL-027) | jsonb | user-input | identity column always visible |
| Export | S30 | IS-9 | CSV over current filters + visible columns | file | computed-display | money 2dp, UTF-8 |

**6 · Acceptance**
- Given the list, Then search/segments/filters/sort behave per the capability row with URL-persisted state.
- Given the column chooser, Then per-user persistence holds and export follows the visible set.
- Given issued rows, Then no edit path exists anywhere in the surface.
- Given tenants, Then rows never leak in list, search, or direct URL.

**7 · Finance Calculation** — N/A (display only; totals come stored from issue).

**8 · Open Questions** — None.

---
id: US-BIL-026
epic: EP-BIL-07
module: billing
screens: [S30]
wave: 3
status: draft
blocked_by: []
depends_on: [US-BIL-025, US-BIL-007, US-BIL-022]
journeys: [J2]
rules: [BR-BIL-004, BR-BIL-010, BR-BIL-026]
golden_tests: []
finance_calc: confirmed
---
### US-BIL-026 — Bill detail: pinned document, line detail with GL, linkage & audit

**1 · Details** — As a Billing Clerk, I want a bill's detail view to show both truths at once: the **customer document** rendered from the pinned template version (BR-BIL-026) with the A19 summary box (previous balance − payments/credits received + current charges = total due), and the **record truth** — every `invoice_line` with quantity/unit/unit-price/amount/taxable flag/GL stamp/tariff version, the bill's run (or single/catch-up origin), its correction chain (credit notes/rebills both directions), delivery history per channel, and the audit trail — so that any customer question or finance query resolves from one screen without touching anything (read-only; actions route to their gated flows).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-010 | Line detail shows the STAMPED GL (issue-time truth), never a re-resolution against today's mapping. | CONFIRMED — PO Billing A-1 option (a) |
| BR-BIL-026 | The document panel renders the pinned template version forever. | CONFIRMED — PO Lane B-7 |
| BR-BIL-004 | Detail is read-only on issued bills; mutation only via correction (EP-BIL-04) or void (US-BIL-027). | CONFIRMED — CLAUDE.md #4 |
| A19 summary *(cited)* | Bill summary box: previous balance − payments/credits received + current charges = total due. | CONFIRMED — A19 extraction (model §7) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open BL-2608-018410 (WE-1) | Document renders pinned v3; summary box: previous 45.00 − payments 0.00 + current 247.87 = **292.87**; 15 lines with flags + GL stamps per WE-1 |
| TC-2 | After the US-BIL-009 TC-2 mapping edit (4100→4101) | Lines still show 4100 — the stamp, not today's mapping |
| TC-3 | WE-9 chain | Original detail links credit note −247.87 and rebill +227.95; the rebill's detail cites the original; delivery history lists each channel row with status. ⚠ **AMENDED 2026-08-12 (PO, OQ-120): the LINK IS CARRIED ON THE NEW BILL** — *"Nod to add the link on the new bill"*. The rebill points back at what it replaces (the original is immutable and must not gain a column after issue, BR-BIL-004), and the original's "both ways" view is the REVERSE lookup of that one pointer, never a second column |
| TC-6 *(2026-08-12, OQ-169 + DEF-084 — which document a reprint renders)* | BL-2608-018410 has TWO document instances after a name fix and then an address fix | **Reprint, re-send and dispute copy all render the NEWEST instance**, which carries **both** fixes (PO 2026-08-12: *"Reissue a corrected copy"* + *"Accumilate"*). The original instance stays retained and reachable — BR-BIL-030's reproducibility guarantee still has to answer *"what did we actually post?"* — so the detail view shows the instance list, not one document with a hidden history |
| TC-4 | Catch-up bill detail | Origin shows the child run + parent run linkage (US-BIL-006) |
| TC-5 *(negative)* | Any write attempted from the detail surface (forged PATCH on lines/totals) | Rejected — read-only; only Reprint/Correct/Void actions exist, each routing to its gated story |
| TC-6 *(isolation)* | Lone Star Ridge detail URL with a Brazos Bend invoice id | 404 (RLS) |

**4 · Test Data** — BL-2608-018410 (WE-1: 15 lines, stamps 4100…4200, pinned v3, run 07-A, delivery 142-print batch). WE-9 chain fixtures. Catch-up fixture CU-07-A-1 bill. Actors: Priya Menon; Diana Chen (finance reads GL stamps). Isolation: Lone Star Ridge LSR-2608-000102.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Document panel | S30 detail | BR-BIL-026 | render from `invoices.template_id/.template_version` | pdf/html | computed-display | pinned version only |
| Summary box | S30 detail | A19 (model §7) | computed: previous balance − payments/credits + current = total due | numeric(18,6) | computed-display | §7 formula |
| Line table | S30 detail | model §3 | `invoice_lines.*` incl. `taxable`, `gl_account_id`, `tariff_version_id` | rows | computed-display | stamped values verbatim |
| Run/origin link | S30 detail | r10 #7 | `invoices.bill_run_id` (+parent run when catch-up) | uuid | computed-display | — |
| Correction chain | S30 detail | BR-BIL-004/014 · **BR-BIL-064 as amended 2026-08-12** | `credit_notes.original_invoice_id` + **the rebill's own pointer back to what it replaces** (PO 2026-08-12, OQ-120 — the link lives on the NEW bill; still unbuilt, but the shape is no longer an open question) | uuids | computed-display | both directions, from one pointer read forwards and backwards |
| Delivery history | S30 detail | BR-BIL-016 | queue rows for the bill | rows | computed-display | per channel |
| Audit trail | S30 detail | CLAUDE.md #7 | `audit_log` rows for the invoice | rows | computed-display | append-only read |

**6 · Acceptance**
- Given WE-1's bill, Then document, summary box and all 15 stamped lines match the workbook, and later mapping/template edits change nothing shown.
- Given a corrected or catch-up bill, Then the full chain and origin are navigable.
- Given the surface, Then it is read-only with only the three gated action routes.
- Given tenants, Then details never leak.

**7 · Finance Calculation** — CONFIRMED (A19 summary; WE-1 verbatim): `total due = previous balance − payments/credits received + current charges`. Worked: 45.00 − 0.00 + 247.87 = **292.87**. Credit-bill display (WE-14): 0.00 due, −17.70 carried shown per model §7.

**8 · Open Questions** — None.

---
id: US-BIL-027
epic: EP-BIL-07
module: billing
screens: [S30]
wave: 5
status: draft
blocked_by: []
depends_on: [US-BIL-026, US-CUS-012]
journeys: [J6]
rules: [BR-BIL-004, BR-BIL-009]
golden_tests: []
finance_calc: confirmed
---
### US-BIL-027 — Void with plain-language consequence messaging (OQ-012 windows)

**1 · Details** — As a Billing Clerk, I want to void a wrongly-issued bill ("Cancel this bill" — the customer owes nothing for it) with the ratified guardrails: **before confirm, a plain-language consequence message** states exactly what will happen — reversing ledger entries, the balance effect, any payment that must be reversed first, and whether approval is needed (BR-BIL-009); the **OQ-012 windows** govern: free void while the bill is **unpaid AND in the same open period**; otherwise the payment must be reversed first (payments flow, its own windows: ACH 60d · card 120d · check unlimited/NSF) and the void needs **Admin/Executive approval**; the void is ALWAYS reversing entries — the invoice row flips to `void` status, lines untouched, a full reversing JE posts via the posting service 🔒 — never a delete (BR-BIL-004). A void is not a correction: nothing replaces the bill (rebill needs = EP-BIL-04).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-009 | Void flows show a plain-language consequence message (reversing entries, balance effect, approvals) before confirm. | CONFIRMED — PO Q&A R6 (OQ-012) |
| OQ-012 closure *(cited)* | Free void while unpaid + same period; else reverse payment first + Admin/Executive approval; always reversing entries; payment-reversal windows ACH 60d / card 120d / check unlimited (NSF). | CONFIRMED — B4 addendum + PO Q&A R6 (OQ-012 CLOSED) |
| BR-BIL-004 | Void never deletes: invoice + lines remain immutable rows; the reversal is a new balanced JE by the posting service. | CONFIRMED — CLAUDE.md #4/#5 |
| BR-TEN-038 *(consumed)* | Reversals dated into a closed period auto-post to the earliest open period with audit. | CONFIRMED — OQ-033 closure |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Void an unpaid same-period bill (WE-1 shape, issued Aug 1, period open) | Consequence modal: "reverses DR AR 247.87 and all revenue/tax/fee postings; balance drops 247.87; no approval needed"; confirm → status `void`, reversing JE per §7, audit row; delivery rows for the bill cancelled-from-queue if undispatched |
| TC-2 | Void attempted on a PAID bill | Modal explains: payment must be reversed first (routes to the payments reversal flow with its windows) AND Admin/Executive approval required; void proceeds only after both |
| TC-3 | Void of a prior-period bill after fiscal close | Reversing JE auto-posts to the earliest open period with audit (BR-TEN-038); consequence message says so in plain language |
| TC-4 *(negative)* | Void attempted twice; DELETE attempted on the voided invoice | Second void no-ops (already void); delete rejected — rows remain forever (BR-BIL-004) |
| TC-5 *(negative)* | Clerk confirms a paid-bill void without the approval | Server rejects — approval gate is server-side (Admin/Executive per OQ-012) |
| TC-6 *(isolation)* | Lone Star Ridge void | Its bills only; approvals from its own admins (RLS) |

**4 · Test Data** — Void fixture: WE-1-shaped bill BL-2608-018455 (ACC-1130, current 247.87), unpaid, period open → free void. Paid fixture: BL-2607-018204 (paid via ACH Aug 6) → reverse-payment-first + approval path. Closed-period fixture: bill dated into closed July, void in September → JE posts to earliest open period. Actors: Priya Menon (initiates), Alex Reed (Admin approval). Isolation: Lone Star Ridge void on LSR-2607-000090.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Consequence message | S30 void modal | BR-BIL-009 | rendered from the computed reversal preview (entries, balance effect, approval need) | text | computed-display | always before confirm |
| Void status | S30 | A5/r10 lifecycle | `invoices.status = 'void'` (lines untouched) | enum | system-derived | one-way; no delete |
| Window evaluation | — | OQ-012 closure | computed: paid? same period? → free vs gated path | enum | system-derived | server-side |
| Approval (gated path) | S30 modal | OQ-012 closure | approval record (Admin/Executive) | uuid/ts | user-input | server-enforced role |
| Reversing JE handoff | — | BR-BIL-004/011 | posting service 🔒 — full reversal of the bill's stamped buckets; closed-period → earliest open (BR-TEN-038) | rows | system-derived | balanced; billing writes none |
| Payment-reversal prerequisite | — | OQ-012 closure | routed to payments (BR-PAY-011 consequence messaging there) | — | user-input | ACH 60d / card 120d / check unlimited |
| Void audit | — | CLAUDE.md #7 | `audit_log` `invoice.voided` (actor, path, approval) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given an unpaid same-period bill, Then the consequence message shows and confirm voids with a balanced reversing JE — no approval, no deletion.
- Given a paid or cross-period bill, Then payment reversal + Admin/Executive approval gate the void, server-enforced.
- Given a closed period, Then the reversal auto-posts forward with audit and the message says so.
- Given any voided bill, Then invoice + lines still exist, status void, chain auditable forever.

**7 · Finance Calculation** — CONFIRMED (reversal = the exact mirror of the bill's issue posting, WE-1 buckets verbatim): void JE = CR 1200 AR **247.87** / DR 4100 **88.60** · 4105 **12.00** · 4110 **39.50** · 4115 **8.00** · 4120 **15.80** · 4130 **18.00** · 4150 **40.00** · 2200–2203 **20.97** · 4200 **5.00** — balanced, posting-service-written. Balance effect: total due drops by 247.87.

**8 · Open Questions** — None (OQ-012 closed).

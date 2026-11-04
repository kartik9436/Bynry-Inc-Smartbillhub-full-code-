# EP-LED-04 — Manual journal entries: draft→post, three types, accrual auto-reverse, reverse+repost (S57 · S56)

**Module:** ledger · **Wave:** W5 · **Screens:** S57, S56 · **Status:** draft (BR-LED-001..016 all CONFIRMED; schema B2 Addendum r13)

## Scope
**In:** the **Manual journal entry modal S57** (A1 r2: balanced debit/credit lines, type standard/accrual/reversing, memo, add-line, audit required) and its ratified lifecycle (BR-LED-003): **draft** (editable, deletable, worthless, **and carrying NO number** — ⚠ unlike a draft BILL, which takes its number at draft creation under BR-BIL-063; see BR-LED-021 (a)) → **posted** (immutable forever, **stamped with its `JE-` number** — BR-LED-021, PO 2026-08-12 OQ-176); **balanced required at post; ~~Finance/Owner role~~ System Admin or Billing Clerk (PO 2026-08-12, OQ-175 — Executive may not); reason + audit**. **Accrual-type JEs auto-reverse on day 1 of the next period, linked both ways** (BR-LED-005, LE-4). "Edit/update" of a posted JE = **one-click REVERSE + REPOST** (mirror entry linked + prefilled new draft — LE-8). The **journal list carries the full IS-5 capability row** (BR-LED-012). Posting itself goes through the posting service 🔒 — the modal authors content; the service writes lines (CLAUDE.md #5).
**Out:** system-generated entries + reversal pairs from upstream events (EP-LED-01) · Record-refund modal S58 (payments US-PAY-011 — GL leg consumed via EP-LED-01 contract) · period-close dating rules execution (US-LED-015) · exact DDL/type enum mechanics 🔒 (r13 #2/#8).
**Tables (B2 + r13):** `journal_entries` (+ type enum standard|accrual|reversing, draft state, auto_reverse link + reversal_of link — r13 #2), `journal_lines`.

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S56 · Journal entries list | JE #, memo | type (standard/accrual/reversing), status (**draft/posted** — ~~reversed~~ **CORRECTED 2026-08-12, OQ-184: `reversed` is a LINK, not a status; filter on the reversal link, which the list already serves both ways on every row**), period, source_type | entry_date desc | date, JE #, type, debit, credit, status | JE # · Date · Type · Memo · Source · Debit · Credit · Status / +Links (reversal-of / auto-reverse), Posted by (IS-5, BR-LED-012) | View · Edit/Delete (draft only) · Reverse + repost (posted) | — | CSV (IS-9) |

## Stories

---
id: US-LED-011
epic: EP-LED-04
module: ledger
screens: [S57, S56]
wave: 5
status: draft
blocked_by: []
depends_on: [US-LED-005]
journeys: [J5]
rules: [BR-LED-003, BR-LED-015]
golden_tests: []
finance_calc: confirmed
---
### US-LED-011 — Manual JE: draft → post lifecycle, three types, balanced at post

**1 · Details** — As Finance/Owner staff, I want the S57 **Manual journal entry** modal (A1 r2 / prototype: Date · Type Standard/Accrual/Reversing · Memo · GL line rows with Debit/Credit · running "Must balance" footer · + Add line · audit-required notice) with the ratified lifecycle (BR-LED-003): a **draft** is freely editable and deletable — it is worthless until posted; **Post entry ✓** requires **balanced** (Σ debits = Σ credits, enforced again by the B2 §3 constraint trigger), a **memo/reason**, and the **Finance/Owner role**; the posted entry is **immutable forever** (hard rule 4 — the only "edit" is US-LED-013's reverse+repost). The write itself goes through the posting service 🔒 with source_type `manual_je` + full dimension stamping where lines carry account context (BR-LED-001). Every draft/post/delete event audits (BR-LED-015; prototype "Post to audit log (required)"). Entry: S56 "+ Journal entry". Exit: posted JE on the S56 list; toast "Journal entry posted · balanced" (prototype copy).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-LED-003 | Drafts freely editable/deletable before post; balanced required at post; posted = immutable; Finance/Owner role; reason + audit. | CONFIRMED — PO LF-3, 2026-08-08 (LE-8) |
| BR-LED-001 *(consumed)* | Manual-JE lines carry source_type `manual_je` + source_id; dimensions where applicable. | CONFIRMED — PO LF-1, 2026-08-08 |
| BR-LED-015 | Draft/post/delete all write audit_log. | CONFIRMED — PO LB-7, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Draft saved (DR 1210 Unbilled AR 500.00 / CR 4100 500.00, type Accrual, memo "Sep unbilled revenue") | Draft row on S56 (status draft); editable; deletable; posts nothing to the books yet |
| TC-2 *(balance)* | Post the draft | "Must balance" footer 500.00 = 500.00; posting service writes the entry; constraint trigger passes; S56 shows posted, immutable; audit `journal.posted` |
| TC-3 | Types | Standard / Accrual / Reversing selectable per prototype; accrual behavior = US-LED-012; type recorded on the entry (r13 #2) |
| TC-4 *(negative)* | Post attempted with DR 500.00 / CR 480.00, or with an empty memo | Blocked client-side (footer shows the 20.00 gap) AND server-side (balanced + reason required, BR-LED-003) — nothing partial |
| TC-5 *(negative)* | Staff-role user opens S57; a posted JE receives an UPDATE/DELETE | Modal is Finance/Owner-only (server-enforced); posted rows reject mutation outright (append-only triggers) |
| TC-6 | Draft deleted | Gone without trace in the books (it never touched them); audit `journal.draft_deleted` remains |
| TC-7 *(isolation)* | Lone Star Ridge JE | Its chart accounts only in the GL picker; its entries only on the list (RLS) |

**4 · Test Data** — LE-4's entry as the fixture: Sep 30, 2026 · Accrual · DR 1210 Unbilled AR **500.00** / CR 4100 Electric Revenue **500.00** · memo "Accrue Sep unbilled revenue". Unbalanced variant: 500.00/480.00. GL picker = US-LED-005 chart (active rows only). Actors: Norma Reyes (Finance, author), Sam Alvarez (Staff, refused). Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Date | S57 | prototype-extracted | `journal_entries.entry_date` | date | user-input | closed-period dating → BR-TEN-038 (US-LED-015) |
| Type | S57 | A1 r2 / r13 #2 | `journal_entries.type` (standard\|accrual\|reversing) | enum | user-input | required |
| Memo/reason | S57 | prototype-extracted + BR-LED-003 | `journal_entries.memo` | text | user-input | required at post |
| GL line (account, DR/CR, amount) | S57 | prototype-extracted | `journal_lines` via posting service 🔒 | numeric(18,6) USD | user-input | active chart rows; amount > 0; Σ DR = Σ CR |
| Draft state | S56 | r13 #2 | `journal_entries` draft state | enum | system-derived | editable/deletable only while draft |
| Must-balance footer | S57 | prototype-extracted | computed Σ DR vs Σ CR | numeric(18,6) | computed-display | mirrors the server check |
| Source stamp | — | BR-LED-001 | source_type `manual_je` | enum | system-derived | on every line |
| Audit | — | CLAUDE.md #7 | `audit_log` `journal.draft_*` / `journal.posted` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a draft, Then it edits and deletes freely and never touches the books.
- Given post, Then balance + memo + role are all enforced server-side and the entry becomes immutable with full audit.
- Given roles/tenants, Then S57 and the list respect Finance/Owner and RLS exactly.

**7 · Finance Calculation** — CONFIRMED (balance assertion, LE-4 entry): Σ DR = 500.00, Σ CR = 500.00 → **500.00 = 500.00** ✔ post allowed; variant 500.00 ≠ 480.00 → gap **20.00** shown, post refused.

**8 · Open Questions** — ~~None.~~ **AMENDED 2026-08-15 (close-the-books lane, on BUILDING §1).** The backend half ships: `apps/ledger/manual_je.py` (the story service) over `apps/ledger/posting.save_draft` / `delete_draft` / `post_draft` (the sole writer — see below). §7 is green: **500.00 = 500.00** posts, and the variant saves as a draft showing the **20.00** gap and REFUSES to post naming both totals. Five residues:

- **THE DRAFT IS A REAL ROW IN `journal_entries`, AND THE PRIMITIVES LIVE IN THE POSTING SERVICE.** `ledger/0004` refuses an INSERT into `journal_entries`/`journal_lines` outside `apps/ledger/posting.py`'s write window, so a manual-JE service that opened that window itself would be the SECOND write path hard rule 5 forbids. The draft therefore lives where B2 r13 #2 and this module's field map put it — *"`journal_entries` draft state"* — written through the one lawful door. `ledger/0002` was already built for exactly this: its balance function returns early unless an entry is posted (*"a draft may sit unbalanced until it posts"*), which is what makes TC-4's DR 500.00 / CR 480.00 draft storable at all.
- **US-LED-013's `repost_draft_is_not_persisted` IS NOW CLOSABLE.** That story reported *"a DRAFT row cannot exist until US-LED-011 builds the draft lifecycle this story `depends_on`"*. It can now: `posting.save_draft` writes one. The reverse+repost flow was NOT changed by this lane — the prefilled payload it returns can be handed to `save_draft` by a caller, and doing that wiring is a one-line change in `apps/ledger/journal.reverse_and_repost` that this lane did not make because US-LED-013 is green as it stands.
- **TC-5's ROLE GATE IS ENFORCED — as a READING.** `@require_role(SYSTEM_ADMIN, BILLING_CLERK)` sits on every write in `manual_je.py`, so an `executive` is refused server-side (BR-SHL-025 makes the service layer THE enforcement). ⚠ The story says *"Finance/Owner-only"* and this product has no Finance and no Owner; OQ-175 (*"System Admin, Billing Clerk"*) was ruled about **reversing a posted entry**, so the same two roles are carried here as the reading EP-LED-05 §8 already flags, and every result says so in `manual_je_role_gate_is_a_reading_not_a_ruling`. Not treated as separately ratified.
- **THE `JE-` NUMBER IS BUILT AND NO TENANT CAN ALLOCATE ONE.** BR-LED-021 is implemented end to end (ninth series, `journal_entries.number`, stamped at post, frozen after, on the S56 row as `je_number`, searchable). But `apps.tenancy.services.SERIES_DEFAULTS` seeds five series at provisioning and the journal one is not among them — the same state BR-TEN-041's DEP-/RCT-/EXP- are in, *"deliberately absent … their owning lanes seed them"*. A manual JE POSTS UNNUMBERED and reports `journal_number_series_is_not_seeded`; a number is never composed locally, because BR-TEN-035 makes numbering tenant-visible and format-configurable. **A posted entry can never be numbered afterwards** (hard rule 4), so entries posted during the gap stay unnumbered forever. The one-line fix belongs to the tenancy lane and is REPORTED.
- **BR-LED-025 IS NOW BUILT** (PO 2026-08-12, *"Refuse and make the caller round"*), and `apps/ledger/posting.py`'s docstring — which still claimed the rule was unsigned and *"raised as OQ-126"* — is corrected. A line carrying a third decimal is refused, naming the amount, on every path into the books. **NOT BUILT: the S57 MODAL, its *Must balance* footer, IS-6's confirm and the S56 row actions.** The `gap` figure the footer renders is on the result; the API and frontend halves of this story are another lane's.

---
id: US-LED-012
epic: EP-LED-04
module: ledger
screens: [S57, S56]
wave: 5
status: draft
blocked_by: []
depends_on: [US-LED-011, US-TEN-006]
journeys: [J5]
rules: [BR-LED-005, BR-LED-003, BR-LED-015]
golden_tests: []
finance_calc: confirmed
---
### US-LED-012 — Accrual auto-reverse: day 1 of the next period, linked both ways

**1 · Details** — As Finance/Owner staff, I want every **accrual-type** JE to **auto-reverse on day 1 of the next period** (BR-LED-005): the system posts the exact mirror entry automatically, and the two entries **link both ways** (r13 #2 auto_reverse link), so month-end accruals never double-count against the next period's real postings (LE-4: Sep 30 accrue $500 unbilled revenue → auto-reverses Oct 1 → October's real billing posts normally). "Next period" derives from the tenant fiscal settings (BR-TEN-022, US-TEN-006); if that day falls in a locked period (edge), the BR-TEN-038 auto-forward rule applies with audit. The mirror is system-posted through the posting service 🔒 and is itself immutable (BR-LED-003). Entry: posting an accrual JE (US-LED-011). Exit: mirror posted on schedule, linked, visible on the S56 list.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-LED-005 | Accrual-type JEs auto-reverse on day 1 of the next period, linked both ways. | CONFIRMED — PO LF-5, 2026-08-08 (LE-4) |
| BR-TEN-022 *(consumed)* | Period boundaries computed from fiscal settings. | CONFIRMED — PO R2-B5 |
| BR-TEN-038 *(consumed)* | Locked-period dating auto-forwards with audit. | CONFIRMED — PO Q&A R6 |
| BR-LED-003 | The mirror is a posted, immutable entry — never an edit of the original. | CONFIRMED — PO LF-3, 2026-08-08 |
| BR-LED-015 | Auto-reversal writes audit_log. | CONFIRMED — PO LB-7, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(balance)* | LE-4: JE-201 (accrual) posted Sep 30 — DR 1210 500.00 / CR 4100 500.00 | Oct 1: JE-202 auto-posts the mirror (DR 4100 500.00 / CR 1210 500.00), balanced; both entries linked both ways; audit `journal.auto_reversed` |
| TC-2 | October real billing posts | No double count: 1210 nets to 0.00 across the pair; October revenue = October's bills only (LE-4 outcome) |
| TC-3 | Links render | S56 list shows JE-201 ↔ JE-202 linkage in the Links column (BR-LED-012 row); each entry's view names the other |
| TC-4 | Standard-type JE posted | NO auto-reverse — only accrual type triggers it (BR-LED-005) |
| TC-5 *(negative)* | Attempt to delete/suppress the pending auto-reversal, or to edit JE-202 after it posts | No suppress path exists (the reversal is the rule); posted mirror immutable (append-only triggers) |
| TC-6 *(edge)* | Day 1 of the next period is inside a locked period (reopened-then-closed edge) | Mirror auto-forwards to the earliest open period with the BR-TEN-038 audit note — never lands in a locked month |
| TC-7 *(isolation)* | Lone Star Ridge accrual | Its mirror posts in its books only (RLS) |

**4 · Test Data** — LE-4 verbatim: JE-201 Sep 30, 2026 accrual DR 1210 Unbilled AR 500.00 / CR 4100 500.00 → JE-202 Oct 1, 2026 mirror, linked both ways. Fiscal settings: FY start Jan, monthly close (US-TEN-006 fixture). Actors: Norma Reyes (posts JE-201), system (JE-202). Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Accrual type | S57 | r13 #2 | `journal_entries.type='accrual'` | enum | user-input | triggers the schedule |
| Auto-reverse schedule | — | BR-LED-005 | day 1 of next period (fiscal settings) | date | system-derived | BR-TEN-038 on locked edge |
| Mirror entry | S56 | BR-LED-005 | `journal_entries` + mirrored `journal_lines` (sides swapped) | rows | system-derived | posting service 🔒; balanced |
| Auto-reverse link | S56 | r13 #2 | `journal_entries` auto_reverse link (both ways) | uuid | system-derived | required on the pair |
| Audit | — | CLAUDE.md #7 | `audit_log` `journal.auto_reversed` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a posted accrual, Then the mirror posts on day 1 of the next period, balanced, linked both ways, immutable.
- Given the next period's real activity, Then nothing double-counts.
- Given standard/reversing types, Then no auto-reversal fires; given the locked edge, BR-TEN-038 applies; given tenants, nothing crosses.

**7 · Finance Calculation** — CONFIRMED (LE-4 verbatim): Sep: DR 1210 **500.00** / CR 4100 **500.00** → Oct 1 mirror DR 4100 **500.00** / CR 1210 **500.00**; net 1210 across the pair = **0.00**; October books carry only October's real billing — no double-count.

**8 · Open Questions** — ~~None.~~ **AMENDED 2026-08-15 (close-the-books lane, on BUILDING §1).** LE-4 is green end to end: `apps/ledger/manual_je.run_accrual_auto_reversals` posts the Oct 1 mirror through `apps.ledger.posting.reverse_entry` (which READS the accrual and swaps the sides — never a hand-composed compensating entry), the pair links BOTH ways, and **1210 nets 0.00 across it** while October's revenue is October's bill alone. §7 reproduces verbatim. Four residues:

- **IT IS A SWEEP, NOT A TIMER, AND IT HAS NO SCHEDULER.** `run_accrual_auto_reversals(as_of, posted_at)` takes both times as INPUTS (BR-TEN-043 / gate G6 — nothing in a money path reads a clock), so a catch-up run after a host was down is the normal case and a replay writes nothing (`posting_key` = `journal_entry|<accrual id>|auto_reversed`, one string per accrual forever). **Wiring it to the jobs table is NOT done** — TC-1 fires when a caller calls it, and today the only callers are the tests. Hard-won law 2, stated rather than implied.
- **`link_forward` IS AN ADDITIVE PARAMETER ON THE 🔒 POSTING SERVICE.** BR-LED-005 links the pair both ways and `reversal_of` is only one of them; the accrual's `auto_reverse_entry` is the single column `ledger/0002`'s immutability trigger deliberately leaves writable on a posted entry. `reverse_entry` also gained `audit_action`, so TC-1's `journal.auto_reversed` is a different row from a human's `journal.reversed` — *"the schedule fired"* and *"somebody corrected this"* are different facts a month-end reviewer greps for separately. Both parameters are defaulted; no existing caller changed behaviour.
- **THE MIRROR CARRIES NO `JE-` NUMBER, SO LE-4's *JE-202* IS NOT REPRODUCED.** BR-LED-021 stamps a number at POST and the mirror posts through `posting.reverse_entry`, which allocates none. This is true of EVERY system-posted entry in the product (bills, payments, the remittance JE), so it is a gap in BR-LED-021's REACH — whether the series covers system-generated entries or only manual ones was never put to the PO — and is REPORTED on BR-LED-021 (ii), not decided here.
- **TC-6 IS GREEN AND IT IS THE CLOSE THAT MAKES IT SO:** the mirror's date runs through `apps.ledger.close.resolve_entry_date`, so a day-1 falling inside a locked period auto-forwards to the earliest OPEN period with the BR-TEN-038 note on the result and in the audit payload. An accrual a human ALREADY reversed by hand is SKIPPED and reported (`skipped="already_reversed_by_hand"`) rather than silently doing nothing — `uq_journal_entries_reversal` allows one mirror per entry, ever.

---
id: US-LED-013
epic: EP-LED-04
module: ledger
screens: [S56, S57]
wave: 5
status: draft
blocked_by: []
depends_on: [US-LED-011]
journeys: [J5, J6]
rules: [BR-LED-003, BR-LED-012, BR-LED-015]
golden_tests: []
finance_calc: confirmed
---
### US-LED-013 — Posted-JE "edit" = one-click reverse + repost; the journal list (IS-5 row)

**1 · Details** — As Finance/Owner staff, I want "edit/update" of a **posted** JE to be exactly the ratified **REVERSE + REPOST** flow (BR-LED-003, LE-8): one click on the posted entry generates (a) the **mirror reversal entry, linked** to the original (reversal_of, r13 #2) and (b) a **prefilled new draft** (S57, copy of the original ready to correct) — the books stay append-only (hard rule 4 never bends), and the trail shows all three entries forever. Reason required; Finance/Owner role; audited. And I want the **journal entries list** on S56 carrying the **full IS-5 capability row** (BR-LED-012 — columns/search/filters/sort/export per the epic matrix), where drafts, posted entries, reversals and links are all first-class visible. Entry: S56 list → posted JE → "Reverse + repost". Exit: net effect corrected; history complete forever.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-LED-003 | "Edit/update" of a posted JE = one-click REVERSE + REPOST (mirror linked + prefilled new draft); reason + audit; ~~Finance/Owner~~ **SYSTEM ADMIN and BILLING CLERK — Executive may NOT reverse (PO 2026-08-12, OQ-175: _"System Admin, Billing Clerk"_)**. | CONFIRMED — PO LF-3, 2026-08-08 (LE-8); role gate CONFIRMED-AS-MODIFIED — PO 2026-08-12 |
| BR-LED-012 | Journal list carries the full IS-5 capability row — including the **JE #** column and the *"JE #, memo"* search, which now have a source: the `JE-` series (BR-LED-021, PO 2026-08-12 OQ-176). `status` stays the two-value column; **`reversed` is a LINK, not a status** (OQ-184 — the matrix moved, the schema did not). | CONFIRMED — PO LB-4, 2026-08-08; extended PO 2026-08-12 |
| BR-LED-015 | Reverse + repost writes audit_log. | CONFIRMED — PO LB-7, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(balance)* | LE-8: JE-104 posted with 250.00 (should be 205.00) → one click | JE-105 mirror reversal posts (balanced, linked reversal_of → JE-104) + JE-106 opens as a prefilled S57 draft; staff corrects to 205.00 → post; net effect **205.00**; all three entries visible forever |
| TC-2 | Links + list | S56 list shows JE-104 (reversed), JE-105 (reversal, linked), JE-106 (posted); filters by type/status/period work; search by JE #/memo; CSV export per IS-9; column chooser per IS-5 |
| TC-3 | Reason + audit | The click demands a reason; audit `journal.reversed` (JE-104→105) + `journal.posted` (JE-106) with actor + reason |
| TC-4 | Reverse-only path | Staff may post JE-105 and discard the JE-106 draft (drafts are worthless) — net effect = clean reversal, trail intact |
| TC-5 *(negative)* | Direct UPDATE/DELETE on JE-104; reverse+repost by an **Executive** (PO 2026-08-12, OQ-175 — the role that may NOT reverse); reverse without reason | All refused server-side (append-only triggers · **System Admin / Billing Clerk** gate · reason required). A `system_admin` and a `billing_clerk` each succeed on the same click |
| TC-6 *(negative)* | Second "reverse" click on the already-reversed JE-104 | Blocked — an entry reverses once; the link makes the state visible (no double-mirror) |
| TC-7 *(isolation)* | Lone Star Ridge list + flow | Its entries only; a Brazos Bend JE id 404s (RLS) |

**4 · Test Data** — LE-8 verbatim: JE-104 (Aug 4, 2026, standard, memo "Reclass card fees", 250.00) → JE-105 mirror (Aug 8) + JE-106 corrected 205.00 (Aug 8). Reason: "keyed 250.00, correct amount 205.00". List fixtures: JE-201/202 pair (US-LED-012), drafts from US-LED-011. Actors: Norma Reyes (Finance), Alex Reed (Owner). Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Reverse + repost action | S56 | BR-LED-003 | mirror `journal_entries` (+reversal_of, r13 #2) + prefilled draft | rows | user-input → system-derived | one click; once per entry; posting service 🔒 writes |
| Reason | S56 modal | BR-LED-003 | audit payload + entry memo | text | user-input | required |
| Prefilled draft | S57 | BR-LED-003 | draft copy of original lines | rows | system-derived | editable like any draft (US-LED-011) |
| JE list row | S56 | BR-LED-012 | `journal_entries` + Σ lines + links | rows | computed-display | IS-5 capability row (epic matrix) |
| Links column | S56 | r13 #2 | reversal_of + auto_reverse refs | uuid | computed-display | both directions |
| Export | S56 | IS-9 | CSV of visible set | file | computed-display | filters respected; audited |
| Audit | — | CLAUDE.md #7 | `audit_log` `journal.reversed`/`journal.posted` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given LE-8, Then one click yields mirror + prefilled draft, the corrected post nets to 205.00, and all three entries remain forever.
- Given the list, Then the IS-5 row is fully honored with links visible.
- Given any mutation, double-reverse, role or tenant breach, Then the server refuses.

**7 · Finance Calculation** — CONFIRMED (LE-8 verbatim): JE-104 **250.00** − JE-105 **250.00** + JE-106 **205.00** = net effect **205.00** ✔; every leg individually balanced (Σ DR = Σ CR per entry); history shows all three, forever.

**8 · Open Questions** — ~~None.~~ **AMENDED 2026-08-11 (ledger reporting lane, on building §1).** §7 is BUILT and green — `apps/ledger/journal.reverse_and_repost` posts the mirror through `apps.ledger.posting.reverse_entry` (never a hand-composed compensating entry), the corrected repost nets to **205.00**, and all three entries survive. The original was captured column by column before the click and compared after. Three residues:

- **The PREFILLED DRAFT is RETURNED, not written.** `journal_entries` refuses an INSERT outside the posting service (`ledger/0004`) and the posting service POSTS — so a draft ROW cannot exist until **US-LED-011** builds the draft lifecycle this story `depends_on`. Nothing is lost: BR-LED-003 calls a draft *worthless* and TC-4 has staff discard it, which a payload nobody stored achieves by doing nothing. Carried as `repost_draft_is_not_persisted` on every result.
- ~~**The FINANCE/OWNER gate of TC-5 is not enforced** — **OQ-175**. Role enforcement here is a DRF permission class on an endpoint and this story ships none; more importantly the implemented vocabulary is `system_admin` / `billing_clerk` / `executive` and contains neither "Finance" nor "Owner". Mapping three roles onto two would decide who may correct the books, so it is raised rather than chosen.~~ **CLOSED — PO 2026-08-12 (OQ-175):** _"System Admin, Billing Clerk"_. **Two of the three implemented roles may reverse a posted entry and `executive` may NOT — an executive reads the books, a clerk corrects them.** This unblocks every §2.10 ledger WRITE, which until now had no role gate it could enforce; the permission class itself is still owed by this story. Reason, immutability, the double-reverse block and tenant scope ARE enforced.
- ~~**The JE # column and the "JE #, memo" search of the capability matrix have no source** — **OQ-176**. `journal_entries` has no number column and `core/numbering.KNOWN_SERIES` has no journal series, so the S56 list shows a UUID where this epic shows `JE-104` and the search box can only match the memo.~~ **CLOSED — PO 2026-08-12 (OQ-176):** _"Approve a JE- series"_ → **BR-LED-021**. Worked: the list shows `019ff23d-13ee-7aba-a280-58058e492cb9` today where this epic shows **JE-104** — a finance officer cannot read a 36-character id aloud, quote it in an email or find it again. The series joins `core/numbering.KNOWN_SERIES` as a ninth series under BR-TEN-035, **allocated per tenant and stamped at POST — a draft has NO number**. ⚠ Two clauses of the recorded ruling are carried on **BR-LED-021 as OPEN, not resolved here**: its word *"gapless"* sits against BR-TEN-035's *"gaps ok, never reused"*, and its analogy *"exactly as a draft bill does under BR-BIL-063"* is **backwards** — BR-BIL-063 allocates a bill number **at draft creation**, not at issue.
- **`reversed` IS NOT A STATUS AND THE CAPABILITY MATRIX WAS CORRECTED, NOT THE SCHEMA** — **OQ-184, CLOSED PO 2026-08-12** (_"the spec"_). The matrix listed `reversed` as a journal-entry STATUS filter; it is not a value the column can hold, it is a LINK between two entries which the list already serves in both directions on every row (TC-2). The two-value status column is what the immutability trigger and the ledger law are written against, so **the spec moved and the schema stands**.

**AMENDED 2026-08-15 (DEF-112 lane): THE S56 JOURNAL LIST NOW HAS A SCREEN.** `GET /ledger/journal-entries` had been served since 2026-08-11 with no caller; `07-frontend/src/features/ledger/GeneralLedgerPage.tsx` renders it under the trial balance at **Finance → General ledger**. **What the screen does with this story's three residues, so the next lane does not re-decide them:** a DRAFT renders with a DASH where its number would be (the 2026-08-12 ruling *"a draft has NO number"*, rendered rather than read as a missing value); an unbalanced draft carries the sentence *"This draft does not balance and cannot be posted"* — this list is the ONLY place a draft is visible at all, because every money figure in the module filters `status='posted'`; BOTH reversal links render, in both directions, since one column cannot answer *"was this reversed?"* and *"is this the reversal?"*; and an unmapped source shows the RAW value marked (*"unrecognised source: …"*) rather than being bucketed under a familiar word — BR-REP-008's *nothing invisible*, on screen. **The status filter offers `draft` and `posted` and NOT `reversed`**, per OQ-184's closure: offering it would put a value in a filter no column can ever equal. **NOT BUILT:** S57's reverse+repost ACTION has no endpoint (`apps/ledger/api.py` records that every §2.10 WRITE on the journal is unserved), so the list is read-only and draws no button onto nothing.

**TC-3's REASON now reaches the audit trail.** It did not before: `apps.ledger.posting.reverse_entry`'s `journal.reversed` payload carried ids, key, date and totals and had nowhere to put WHY. One additive, defaulted parameter (`audit_context`) was added to that function for exactly this test case and flows to BOTH rows of the pair — reported in the posting service's own trailer.

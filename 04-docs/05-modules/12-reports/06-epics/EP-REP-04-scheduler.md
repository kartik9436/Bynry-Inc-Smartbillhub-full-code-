# EP-REP-04 — Scheduled reports (S45): cadence, runs, retention, W6-deferred email

**Module:** reports · **Wave:** W5 (email dispatch = W6 per BR-REP-017) · **Screens:** S45 (+ S8 retention setting) · **Status:** draft (BR-REP-001..018 CONFIRMED; queue law BR-NOT-005 CONFIRMED)

## Scope
**In:** **schedule CRUD** (report, cadence, format per IS-11, recipients, next-run; Run now / Edit / Pause / Delete per A14) · **scheduled execution** producing IS-11-identical files + report_run rows into the US-REP-004 retention window (3 days default, tenant-config) · **email delivery = outbound-queue rows marked W6-deferred** (BR-REP-017 + BR-NOT-005; consumes the US-NOT-015 queue contract — v1 delivery is the S45 download).
**Out:** the Recent-runs list + retention mechanics (US-REP-004) · file/format contracts (US-REP-003) · dispatcher mechanics (US-NOT-002) · report content (EP-REP-02, ledger stories) · bookkeeper-copy email (BR-LED-020, US-NOT-015).
**Tables:** schedule/run storage — B2 anchoring pending (pack report R-1, DDL 🔒); `outbound_messages` (r12 #16, notifications-owned — reports WRITES queue rows via the module seam, never sends).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S45 · Scheduled | report name | status (active/paused), format | next run asc | report, frequency, next run | Report · Frequency · Delivery · Recipients · Next run · Action / +created-by, last run (IS-5) | Run now · Edit · Pause/Resume · Delete (IS-6 confirm) | — | — |

*(Recent-runs row = EP-REP-01 capability matrix, US-REP-004.)*

## Stories

---
id: US-REP-013
epic: EP-REP-04
module: reports
screens: [S45]
wave: 5
status: draft
blocked_by: []
depends_on: [US-REP-001, US-REP-012]
journeys: [J5]
rules: [BR-REP-018, BR-REP-017]
golden_tests: []
finance_calc: none
---
### US-REP-013 — Schedule CRUD: report, cadence, IS-11 formats, recipients, next-run

**1 · Details** — As staff, I want **+ Schedule a report** and the Scheduled table (A14 §Scheduled): **Report** (any canned report or saved custom definition, US-REP-012), **Frequency** (A14 samples: "Every Monday · 6am", "1st of month", "Monthly · 18th" — day-of-week/day-of-month + time patterns; scheduled reports run overnight per the S44 sub-copy; times in the tenant TZ per Regional settings, IS-8), **Delivery format = PDF and/or CSV only** (IS-11 — the A14 line-25 "Excel" is corrected/DROPPED, BR-REP-018), **Recipients** (tenant staff users — recipients matter at W6 email; v1 delivery = download per BR-REP-017), **Next run** computed and shown. Row actions per A14: **Run now / Edit / Pause / Delete** — modal-confirmed + audited per IS-6/IS-1; Delete removes the schedule but never its run history (report_run rows are append-only history, US-REP-004). Entry: S45. Exit: active schedule with a computed next-run.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| A14 §Scheduled | Table columns + action set as extracted. | CONFIRMED — A14 |
| BR-REP-018 | Formats = CSV always + PDF where specced; NO XLSX v1 (line-25 Excel corrected). | CONFIRMED — PO 2026-08-08 (IS-11 / A14 item 11) |
| BR-REP-017 | v1 = PDF/CSV download; email delivery ships W6 — recipients stored now, dispatched then. | CONFIRMED — PO RQ-9, 2026-08-08 |
| IS-1 / IS-6 / IS-8 *(consumed)* | Audited CRUD, confirm modals, tenant-TZ times. | CONFIRMED — B9 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Create "AR aging summary · Every Monday · 6am · PDF · Alex Reed" | Row renders per prototype; Next run = the coming Monday 06:00 tenant TZ (IS-8); audit row written |
| TC-2 | Cadence variants | "1st of month" and "Monthly · 18th" compute correct next-runs across month ends |
| TC-3 *(negative)* | Format options | CSV/PDF only — no XLSX anywhere (IS-11); an API request naming xlsx is rejected |
| TC-4 | Pause / Delete | Pause holds runs (row stays, next-run cleared); Delete (IS-6 confirm) removes the schedule, run history remains on Recent runs |
| TC-5 | Schedule a saved custom definition | "July high bills" schedulable; deleting the underlying definition blocks with the IS-1 in-use pattern (schedule references it) |
| TC-6 *(isolation)* | Lone Star Ridge schedules | Its schedules/recipients only (RLS); Brazos Bend users never listed as recipients |

**4 · Test Data** — Prototype schedules verbatim: AR aging (Mon 6am · PDF · Alex Reed) · Revenue by service & rate (1st of month · was "Excel" → CSV per IS-11 · Alex Reed + bookkeeper) · Sales tax remittance (Monthly 18th · PDF + CSV · Alex Reed). Actors: Alex Reed, Norma Reyes. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Report ref | S45 | A14 §Scheduled | canned key or saved-definition fk (R-1 anchoring, DDL 🔒) | enum/fk | user-input | must exist; in-use lock on definition |
| Frequency + next run | S45 | A14 samples | cadence spec + computed next-run (tenant TZ) | text/timestamp | user-input / system-derived | valid pattern; overnight window |
| Delivery format | S45 | A14 + IS-11 | pdf and/or csv | enum | user-input | XLSX rejected |
| Recipients | S45 | A14 §Scheduled | tenant staff user refs (W6 email targets) | list | user-input | tenant members; see pack report R-6 (external recipients) |
| Actions + audit | S45 | A14 + IS-1/IS-6 | schedule row lifecycle + `audit_log` | — | user-input | confirm + audit every change |

**6 · Acceptance**
- Given creation, Then the prototype rows reproduce with computed tenant-TZ next-runs and no XLSX path anywhere.
- Given lifecycle actions, Then pause/delete behave per IS-1/IS-6 and history survives deletion.
- Given tenants, Then schedules and recipients never cross.

**7 · Finance Calculation** — N/A (scheduling metadata).

**8 · Open Questions** — None. *(Prototype recipient "bookkeeper" implies an external email address — external vs staff-only recipients is underivable; candidate OQ R-6 in the pack report, W6-email concern only.)*

---
id: US-REP-014
epic: EP-REP-04
module: reports
screens: [S45]
wave: 5
status: draft
blocked_by: []
depends_on: [US-REP-013, US-REP-004, US-REP-003]
journeys: [J5]
rules: [BR-REP-018, BR-REP-001]
golden_tests: []
finance_calc: none
---
### US-REP-014 — Scheduled execution + Run now: identical IS-11 files into the retention window

**1 · Details** — As staff, I want scheduled runs executed at their cadence (overnight, S44 sub-copy) and on **Run now**: each run evaluates the report's read-model AT RUN TIME (BR-REP-002 — never a cached result), generates files **identical to a manual export** (IS-11: "Scheduled runs produce identical files" — same CSV contract, same PDF skeleton incl. the date-basis label, same filename convention with the run's generated stamp), writes a **report_run row with By = "Scheduled"** (or the acting user for Run now) into the US-REP-004 Recent-runs history, and lands the files in the 3-day (tenant-config) retention window. A failed generation surfaces on S45 per the IS-7 failed-with-retry standard — never a silent skip. Run-now uses the same pipeline (no second code path). Entry: cadence tick / Run now action. Exit: files + run rows per contract.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-REP-018 | Scheduled files = identical IS-11 files; retained 3 days default, tenant-config. | CONFIRMED — PO 2026-08-08 (IS-11) |
| BR-REP-001 *(consumed)* | The basis label rides into every scheduled PDF/filename. | CONFIRMED — PO ruling 2026-08-08 |
| BR-REP-002 *(consumed)* | Runs recompute from read-models at run time. | CONFIRMED — reports audit 2026-08-08 |
| IS-7 *(consumed)* | Failure surfaces as failed-with-retry; A18 states. | CONFIRMED — B9 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Monday 06:00 AR aging schedule fires | Run row "AR aging summary · Aug 10 06:00 · As of Aug 9 · Scheduled · rows · PDF" (prototype shape); file identical in contract to a manual US-REP-003 export of the same params |
| TC-2 *(basis label)* | The scheduled PDF + filename | PDF skeleton carries "Posting basis"; filename `brazos-bend_ar_aging_2026-08-09_posting_20260810.pdf` — a scheduled money file without its basis = FAIL (BR-REP-001/IS-11) |
| TC-3 | Run now | Same pipeline; By = the acting user; file lands in retention identically |
| TC-4 | Recompute-at-run | A payment recorded between two runs changes the second run's figures (BR-REP-002) — no cached result ever re-served as a new run |
| TC-5 *(negative)* | Generation failure (simulated read-model error) | Failed state surfaces on S45 per IS-7 with retry; no partial/empty file enters retention; next cadence unaffected |
| TC-6 *(negative)* | Paused schedule at cadence time | No run, no file, no queue row — pause is absolute |
| TC-7 *(isolation)* | Lone Star Ridge schedule fires | Generates under ITS RLS context only; its run rows/files invisible to Brazos Bend |

**4 · Test Data** — Prototype run rows (AR aging Aug 4 06:00 Scheduled 184 PDF; Revenue Aug 1 00:05 Scheduled 28). Recompute fixture: PE-10 payment added between Aug 3 and Aug 10 runs. Actors: Alex Reed (Run now). Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Run trigger | — | A14 §Scheduled + S44 sub-copy | scheduler job (cadence, overnight; mechanics 🔒) | — | system-derived | tenant TZ |
| Generated files | S45 | IS-11 | identical CSV/PDF via the US-REP-003 pipeline | file | system-derived | contract byte-rules; basis labeled |
| Run row | S45 | A6 §S46 `report_run` | report_runs (R-1 anchoring, DDL 🔒); By = Scheduled/user | row | system-derived | append-only |
| Failure state | S45 | IS-7/A18 | run row failed state + retry | enum | system-derived | never silent |

**6 · Acceptance**
- Given cadence and Run now, Then one pipeline produces contract-identical, basis-labeled files and honest run rows.
- Given recompute, Then every run reflects the live read-model.
- Given failure/pause/tenants, Then IS-7, absolute pause, and RLS hold.

**7 · Finance Calculation** — N/A (execution plumbing; figures owned by report stories).

**8 · Open Questions** — None.

---
id: US-REP-015
epic: EP-REP-04
module: reports
screens: [S45]
wave: 5
status: draft
blocked_by: []
depends_on: [US-REP-014, US-NOT-002, US-NOT-015]
journeys: [J5]
rules: [BR-REP-017, BR-REP-007, BR-NOT-005]
golden_tests: []
finance_calc: none
---
### US-REP-015 — Email delivery rides the outbound queue — rows written now, dispatch W6

⚠ **BUILT 2026-09-27 — `CR-142-BRC07` `P4.10`, `2.376.0` — AND THE PARAGRAPH
BELOW IS AMENDED IN THREE PLACES RATHER THAN LEFT TO ROT** (CLAUDE.md step W: a
body that contradicts what was built is what a lane actually reads).

1. **ONE ROW, NOT ONE PER RECIPIENT.** The paragraph says *"one
   `outbound_messages` row per recipient"*. The queue's key is
   `(tenant, source_type, source_id, channel, copy_no)`, so a row per person
   would need a `copy_no` per person — and `models.OutboundMessage.copy_no`'s
   own contract is that **automatic writers never set it**, because `> 0` means
   a human asked for an extra copy. `apps/notifications/staff_recipients.py`
   settled this shape for the staff bell in 2026-08-17 and it is the shape
   built here: **one row, `recipient_address` the primary recipient,
   `recipient_snapshot["recipients"]` the whole list**, snapshotted at queue
   time (`BR-TEN-017`), fanned out by the dispatcher at W6.
2. **A LINK, NOT THE FILE.** The paragraph says *"carrying the generated-file
   reference"*. `P4.10`'s task line is *"the outbound queue carries the link,
   not the file"* and its outcome is *"recipients get a link that respects
   their permissions"*. The row carries screen `5·2`'s address —
   `/{tenant}/reports/history/{run}` — and `{report_link}` is **mandatory
   content** on `catalogs.email_scheduled_report`, so a body saved without it is
   refused. There is no token in that palette that could carry an attachment.
3. **IT RECONCILES; IT IS NOT A HOOK AT RUN COMPLETION.** The paragraph's
   *Entry* is *"US-REP-014 run completion"*. The completion point is
   `apps/tenancy/exports.run_list_export_job`, the platform's export kernel,
   and reaching into it would mean editing another module's job body or
   wrapping the platform's handler from `ready()` — an ordering dependency,
   which is hard-won law 7's *structurally incapable of failing*. So
   `apps/reports/delivery.py` runs on reports' own beat entry and queues the
   message for a run that is READY. The consequence is the good one: **a
   message can never announce a run that failed.**

**Everything else in the paragraph stands**, including the one that matters
most: `BR-REP-017` is CONFIRMED and **nothing is sent** — the rows are written,
the dispatch is W6, and `tests/test_cr142_p4_10_delivery.py` asserts
`status == 'queued'` and `sent_at is None` as values so the day that changes it
goes red. The wording of the message itself is LANE-AUTHORED and unratified:
`OQ-REP-12757`.

**1 · Details** — As the platform (PO volume ruling), I want scheduled-report email to follow the ONLY sending path that exists: on run completion, one **`outbound_messages` row per recipient** is written to the platform-wide outbound queue (BR-NOT-005 — never sent inline; BR-REP-007: "scheduled-report email rides the outbound queue") carrying the generated-file reference; the email channel is **marked deferred → W6** (BR-REP-017, consistent with the OQ-073 email pattern) — **v1 delivery = the S45 download within the retention window** ("anyway we will email them" — IS-11; the download list is the courtesy window). When W6 email lands, the US-NOT-002 dispatcher sends these rows in tenant-config batches like all mail — a dispatch flip, no schema or flow change (US-NOT-015 contract). Attachment-vs-link mechanics at dispatch = the notifications seam. Entry: US-REP-014 run completion with recipients. Exit: queue rows recorded; nothing sent v1.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-NOT-005 | EVERY email from ANY module is written to the outbound table first — never sent inline; dispatcher-only sending. | CONFIRMED — PO explicit ruling, 2026-08-08 |
| BR-REP-017 | Scheduled-report email ships W6 with all email; v1 = download only. | CONFIRMED — PO RQ-9, 2026-08-08 |
| BR-REP-007 | Scheduled-report email rides the outbound queue. | CONFIRMED — audit F-4/5/7..13 |
| US-NOT-015 *(contract)* | Queue read-models + W6 email consumers — reports rows are ordinary queue rows. | draft story contract (depends_on) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Scheduled run completes, 2 recipients | 2 `outbound_messages` rows written (channel email, file ref, per recipient), status queued, marked deferred → W6; NOTHING is transmitted |
| TC-2 | v1 delivery path | Recipients retrieve via S45 download within retention (US-REP-004); expiry behavior per that story |
| TC-3 | W6 flip (simulated dispatcher enable) | The SAME rows dispatch via US-NOT-002 in tenant-config batches — no schema/flow change; statuses advance queued→sent→delivered/failed/bounced |
| TC-4 *(negative)* | Any inline SMTP/send path from the reports module | None exists — code path audit: report completion can only INSERT queue rows (BR-NOT-005); a direct-send attempt has no API |
| TC-5 *(negative)* | Run with no recipients | No queue rows; run + files unaffected |
| TC-6 *(isolation)* | Lone Star Ridge run | Its queue rows carry its tenant_id; RLS scopes the queue read-model |

**4 · Test Data** — Schedule fixture US-REP-013 TC-1 with recipients Alex Reed + Norma Reyes; run of Aug 10. Queue rows referencing `brazos-bend_ar_aging_2026-08-09_posting_20260810.pdf`. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Queue row | — | BR-NOT-005 + BR-REP-007 | `outbound_messages` (r12 #16, notifications-owned; reports inserts via seam) | row | system-derived | one per recipient; queued status |
| W6 deferral mark | — | BR-REP-017 | channel-deferred flag on the row (pattern per US-BIL-023 email deferral) | enum | system-derived | no dispatch before W6 |
| File reference | — | IS-11 | generated-file ref (retention per US-REP-004) | fk | system-derived | file exists at write |
| Dispatch (W6) | — | BR-NOT-005 | US-NOT-002 dispatcher batches | — | system-derived | dispatcher is the ONLY sender |

**6 · Acceptance**
- Given a completed run with recipients, Then queue rows exist from day one and nothing sends in v1.
- Given the W6 flip, Then the same rows dispatch with zero schema/flow change.
- Given the platform rule, Then no inline send path exists; given tenants, queue rows never cross.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

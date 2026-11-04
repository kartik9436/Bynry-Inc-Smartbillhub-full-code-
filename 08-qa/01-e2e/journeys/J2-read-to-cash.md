# J2 — Read-to-cash (THE money journey)

---
id: J2
tier: 1
stories: [US-MET-001, US-AST-002, US-MET-006, US-RAT-001, US-CUS-003, US-CUS-004,
          US-CUS-006, US-CUS-007, US-MET-010, US-MET-011, US-RAT-012, US-BIL-005,
          US-PAY-001, US-CUS-012, US-LED-001]
---

<!-- FRONTMATTER ADDED 2026-08-15 (DEF-102), AND IT IS NOT A PURE TRANSCRIPTION —
     read this before trusting the list.

     THE PROBLEM. This file predates the frontmatter convention. Its step table
     names most stories explicitly but uses WILDCARDS for four steps — US-BIL-**,
     US-NOT-**, US-PAY-** and US-LED-**. A wildcard cannot be indexed, so the
     index computed `stories: 0` and readiness None, and THE MONEY JOURNEY was
     invisible to the activation machinery rather than merely blocked.

     WHAT WAS CHOSEN, so a reviewer can disagree with it precisely:
       * step 8  US-BIL-**  -> US-BIL-005 (issue). The bill RUN's own stories are
                              declared by J24; this journey needs the issued
                              invoice, which is what step 8's handoff contract
                              actually names ("invoice status=issued, immutable").
       * step 10 US-PAY-**  -> US-PAY-001 (record payment), beside the
                              US-CUS-012 the step already names.
       * step 11 US-LED-**  -> US-LED-001 (the posting service).

     WHAT WAS REMOVED, AND BY WHOSE RULING:
       * step 9  US-NOT-**  delivery is DROPPED from this list. PO ruling
                            2026-08-15: issuing a bill does NOT mean the customer
                            receives one; delivery is out of this release and no
                            provider adapter exists on any channel, print
                            included. This journey therefore ENDS AT A RENDERED
                            DOCUMENT. Step 9 is re-scoped in place below rather
                            than deleted, so the ruling is visible where the step
                            is read.

     Leaving delivery in the list would have made the money journey permanently
     un-ready for a step the release deliberately does not have. -->
**Fixture.** (authored 2026-08-22, CR-014 — this file predated the Fixture convention and declared nothing) Tenant brazos-bend · the CR-014 flat money cohort (`06-backend/tests/journey_cohort_fixtures.py`): premises **Brazos Bend Apartments**, Unit **4B**, meter **MTR-0451**, account **ACC-2042** active on plan **E2E Flat Residential** (published; flat electric $0.11/kWh + $12.00 base, the money-triples flat shape) · committed August read: 45,210 → 45,910 = **700 kWh** explicit unit · issued bill for period **Aug 1–31 2026** (bill date Sep 1, due Sep 22): taxable **89.00** · tax **8.41** in FOUR authority lines (5.56 + 0.89 + 1.78 + 0.18, US-BIL-008 §4) · total **97.41** — money-triples row `flat,cycle,full`, unpaid at seed. Steps 10–11 (pay → allocate → post) are the journey's own acts over this state. August and not July because July is the finance-signed LE-1 book (DEF-556; OQ-218's rule that test data never restates a signed figure).

premises → unit+plan+assets → account → reads → validate → rate → bill → deliver → pay → allocate → post.
| # | Story | Handoff contract to next step |
|---|---|---|
| 1 | US-MET-001..002 premises/units | unit exists, occupancy derived (BR-MET-036) |
| 2 | US-AST-002/US-MET-006 asset assignment | asset active on unit, UoM explicit, register digits set |
| 3 | US-RAT-001..003 + unit plan assignment | rate_plan published; unit_plan_assignments current row (BR-CUS-010/011) |
| 4 | US-CUS-003/US-CUS-004 new account / move-in (+US-CUS-006 snapshot, US-CUS-007 deposit) | account active, plan version snapshot saved (account_plan_assignments, BR-CUS-014 sc.1), deposit rule applied (plan_deposit_rules fixed $); move-out variant US-CUS-005 leaves the BR-CUS-031 final-bill handoff; mid-tenancy plan change US-CUS-016/017 refreshes the snapshot billing reads (sc.6) |
| 5 | US-MET-010..013 read import | committed meter_reads, one row per `channel` (total/tou_*/export/demand per BR-MET-059, B2 r8), plan-required channel set complete (BR-MET-049), status ok/estimated |
| 6 | US-MET-011 validation | flags resolved or estimated per BR-MET rules |
| 7 | US-RAT-012..013 rating engine 🔒 | priced lines per B4 CONFIRMED math (GT-1/2/5/10/11/13/15), priced from the account snapshot as of service date (BR-CUS-014 sc.6) |
| 8 | US-BIL-** bill run (wave 3) | invoice status=issued, immutable, taxable flags set, due_date set |
| 9 | US-NOT-** delivery (stub W3, full W6) | bill rendered per A19, delivery recorded |
| 10 | US-PAY-**/US-CUS-012 record payment (wave 4) | payment cleared, allocations rows per BR-PAY-010 order |
| 11 | US-LED-** posting 🔒 (wave 5) | balanced journal pair via posting service ONLY |
| 12 | US-SHL-006/US-SHL-007 the filtered journal is SHARED (`P1.11`) | the URL alone reproduces the view: a colleague opening the pasted link, with no session and no cache, is served the SAME rows |

---

## REGRESSION · `CR-135` `P1.16`, measured 2026-09-22 — a hand-recorded payment behaves identically

**Why this journey needed re-measuring at all, and it is step 10.** `CR-135`
phase 1 gave `payments` an eighth `ImportTarget`, so a payment row can now be
created by **`payments.import_writer`** as well as by the counter. **That is a
second creation site on a money path**, and J2's step 10 is the first one — the
clerk taking a cheque at the window. The question this regression asks is not
*"does the importer work"* (that is `P1.11`'s, proved on PostgreSQL) but
*"did giving payments an importer change what happens when nobody uses it"*.

**MEASURED, at branch tip `266db24a8`:** `06-backend/tests/test_us_pay_001_record_payment.py`
— **19 passed, 4 skipped, 0 failed**, in 8m06s under `JOBS_EAGER=false --reuse-db`.
Step 10's handoff contract holds: the payment clears, the allocation rows are
written in `BR-PAY-010`'s order, and the balanced pair is posted by the posting
service.

⚠ **THE FOUR SKIPS ARE NAMED RATHER THAN COUNTED, because a skip a report does
not name is indistinguishable from a pass** (hard-won law 7: a check that cannot
cover its whole subject must print what it SKIPPED beside what it checked). All
four carry `@requires_postgres` — the `uq_payments_webhook_key` uniqueness index
and the RLS cases — and the default suite is in-memory SQLite, where neither
guarantee can exist (hard-won law 14). **They are not evidence either way**, and
the honest statement is that step 10 is proved on SQLite and its two
database-level guarantees are not proved by this run.

⚠ **AND THE SECOND HALF OF `P1.16` IS THE SCREEN, WHICH THIS SUITE CANNOT SEE.**
`CR-135` `P1.6` added two row actions — Move and Reapply — to the payments list
a clerk records into. `07-frontend`'s payments and workflow suites are **478
passing across 32 files** at the same tip, including the cases that pin the row
action set to Correct · Reapply · Move · Reverse, in that order. **No gate in
this repo reads rendered output** (hard-won law 6), so a browser walk of step 10
remains the only thing that could find a visual regression, and it has not been
run for this change.


---

## STEP 12 · `CR-135` `P1.11`, built 2026-09-24 — the money journey ends at a link somebody else can open

**WHY THE JOURNEY GAINS A STEP AT ALL, AND WHY IT IS HERE RATHER THAN IN A
SCREEN TEST.** Finance blueprint p013 `P1.11` reads *"add a step: filter, copy
the URL, open it in a new context, same rows"*, and its OUTCOME column is the
whole argument: ***"Shareability is asserted, not assumed."*** Phase 1's own
DONE WHEN (p012) is *"every list that grows with transaction volume pages in
SQL and carries its filters in the URL"* — the second half of which is a claim
about a **second person**, and a journey is the only artefact in this repo that
contracts across one act and the next.

**THE STEP, IN WORDS.** Steps 10 and 11 leave a payment cleared, allocated and
posted. Step 12 is what a clerk does next: open Finance → General ledger, filter
the journal to the entries they care about, and send the address to a colleague
— a supervisor checking a deposit, an auditor asking which entries touched an
account. **The handoff contract is that the URL is sufficient.** Not *the screen
remembers*, which is one component talking to itself, but *a reader with nothing
else gets the same rows*.

**HANDOFF CONTRACT, stated so a downstream lane can break it deliberately:**
every criterion `journalConfig` DECLARES — the search term, the sort and its
direction, the page, the page size, and the `type` / `status` / `source_type`
chips — is in the query string; the accounting period rides with it; an unknown
parameter is ignored and an invalid one falls back rather than reaching an error
screen (`BR-SHL-011`); and the request the server receives from the pasted link
is byte-identical to the one the clicking clerk sent.

**PROVED, 2026-09-24:**
`07-frontend/src/features/ledger/journalUrlShareability.dom.test.tsx`, five
cases, `vitest` + jsdom, no database. It mounts `GeneralLedgerPage` **twice, in
two fresh `QueryClient`s**, carrying nothing across but the URL.

⚠ **THE FIXTURE ANSWERS DIFFERENTLY WHEN THE FILTERS ARRIVE, AND THAT IS WHAT
MAKES THE FILE ABLE TO FAIL.** Two UNFILTERED mounts also agree with each other,
so a test that merely diffed the two would be green over a screen that had
dropped every filter on the floor — hard-won law 7's *structurally incapable of
failing*. The filtered question returns one entry and the unfiltered question
returns three, and both the REQUEST and the ROWS are asserted against the
filtered answer.

⚠ **RED FIRST, WATCHED.** With `journalRequest`'s four URL-derived fields
replaced by `""` — a lane "simplifying" the state away, which is exactly the
shape `P1.9` fixed — **2 of the 5 cases failed**:
`expected null to be 'deposit'` and `expected <td></td> to be null`. Restored,
5 passed.

⚠⚠ **AND THE STEP FOUND ONE CONTROL ON THAT SCREEN THAT DOES NOT HONOUR IT:
`DEF-LED-6654`.** The Balance view's **property filter** (`P2.3`) is `useState`
in `GeneralLedgerPage` and is written into no query string. A clerk who filters
the trial balance to one property and pastes the link sends a colleague **every
property**, silently, because the link looks complete. It is FILED rather than
fixed here — the fix is that screen's, not this journey's — and the last case of
the file **pins the absence**, so the day the control is wired the suite goes red
and names the defect instead of the hold outliving what it held (hard-won law 2's
mirror).

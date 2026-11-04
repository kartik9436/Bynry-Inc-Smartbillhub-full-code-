# reports — Business Rules

Format: BR-XXX-### · rule · source (spec/decision §) · status (CONFIRMED / PLACEHOLDER / OPEN) · test ref.
Rules CITE B-docs; they never copy values out of them (one source of truth).

| BR-REP-001 | **Date-basis rule for EVERY money KPI, dashboard and report**: billing-side numbers (billed, revenue, AR, aging, collection %) read the POSTING date; cash/bank-side numbers (today's payments, deposits, bank rec) read the CLEARING date; **every KPI/report header labels its basis** — no unlabeled money number anywhere | PO ruling 2026-08-08 (extends BR-PAY-021) | CONFIRMED — ⚠ **SUPERSEDED IN PART 2026-10-21** (PO, CR-186 follow-up: *"Posting date"*): *Payments by method*, the payments dataset, the collected-tax basis and the S32 Payments summary mix now read the **posting** date, counting posted + cleared (+ a bounce's negative reversing row in the reports/tax). Since CR-186 a payment clears only at bank reconciliation, so the clearing-date basis showed money days late. Every other read under this rule is unchanged (`DEF-PAY-10321`, `DEF-PAY-10342`) | reports pack TCs |
| BR-REP-002 | Reports/dashboards are READ-MODELS over journal-line dimensions + module read-models; never a side-maintained number (BR-LED-001) | reports audit 2026-08-08 | CONFIRMED | — |
| BR-REP-003 | Remittance report/S41 = dual-basis 4 columns per authority + basis indicator (BR-LED-002/013) | audit F-1 | CONFIRMED | LE-3 |
| BR-REP-004 | S36 carries tie-out panel + KPI strip; drift = red flag + release blocker (BR-LED-007/016) | audit F-3 | CONFIRMED | LE-7 |
| BR-REP-005 | S42 export = recorded idempotent batches, Finance-page export codes, drill-back, dimension CSVs (BR-LED-004/014) | audit F-6 | CONFIRMED | LE-5 |
| BR-REP-006 | Filters enumerate LIVE vocabularies (tenant services, 4 consumer classes incl. Government, 5 statuses + behavior classes, bill_type, payment purpose, read channel) — never hardcoded | audit F-17..21 | CONFIRMED | — |
| BR-REP-007 | Canned report set += back-bills/penalty, corrections, write-offs, budget status, delivery-queue health, returned-mail (read-models of BR-BIL-014/016/017/018/019, BR-PAY-018/020); scheduled-report email rides the outbound queue (BR-NOT-005), ship wave = RQ-9 | audit F-4/5/7..13 | CONFIRMED | — |
| BR-REP-008 | Account ledger Type = full source vocabulary; aging includes opening buckets aging forward (BR-LED-001, BR-CUS-048). ⚠ **AMENDED 2026-09-24 (`P2.21`, lane judgment — decision log of that date, NOT a PO ruling): THE TIE-OUT IS STRUCK OVER EVERY DEBTOR IN THE TENANT AND NEVER OVER WHAT A FILTER OR A PAGE LEFT ON SCREEN.** The ageing pages and filters since `DEF-REP-6607`, and a total folded over a FILTERED set is a subset BY DESIGN — comparing it against the ledger's AR control would report a discrepancy on every chip and every search, so the report would call the general ledger broken because a clerk typed a name. Two figures: `totals` describes the filtered set (the KPI tiles, which foot to the rows whatever page is cut) and `population_total` is the unfiltered receivable, which is the only one this rule's comparison may use. **Worked: two debtors owing 100.00 and 400.00; search *Bramble* and the tiles read 100.00 while the agreement line still reads 500.00**, byte-identical to the unfiltered one. ⚠ **AND THE BANDS ARE FIVE AND NOT FOUR** — `BR-REP-030` was always confirmed at five and this report folded two into one until the same date (`DEF-REP-6659`); no total moved. | audit F-15/22 · `P2.21` 2026-09-24 | CONFIRMED (the 2026-09-24 clause is a LANE JUDGMENT, recorded rather than asked — law 13) | `apps/reports/queries.ar_aging` · `apps/payments/billing_seam.aging_positions_page` · `tests/test_fin_p221_aging_page.py` |
| BR-REP-009 | Collection % = cash applied to bills in period ÷ billed in period, POSTING basis; applied deposits count as collected; write-offs excluded, shown separately | PO RQ-1, 2026-08-08 | CONFIRMED | — |
| BR-REP-010 | S32 "Today total" = posting · "Method mix MTD" = clearing (blessed); S7 "Cash today" = CLEARING | PO RQ-2, 2026-08-08 | CONFIRMED | — |
| BR-REP-011 | DSO = (AR ÷ billed last 12 months) × 365, rolling, posting basis | PO RQ-3, 2026-08-08 | CONFIRMED | — |
| BR-REP-012 | "New accounts" = created in period (status breakdown shown); "Active accounts" KPI = Active + Marked disconnect + Vacation hold; Pending activation + Closed excluded | PO RQ-4, 2026-08-08 | CONFIRMED | — |
| BR-REP-013 | Deposit batch "day" = POSTING date (physical drawer day); bank clears later (cross-ref BR-PAY-025) | PO RQ-5, 2026-08-08 | CONFIRMED | PE-10 |
| BR-REP-014 | Collections KPIs count BILL-purpose payments only; deposit/plan-down/prepay shown as their own lines, never in collection % | PO RQ-6, 2026-08-08 | CONFIRMED | — |
| BR-REP-015 | New ops chips (delivery health, pending billing, returned mail, corrections pending, tie-out drift) live on S7 + S32 — no new screen v1 | PO RQ-7, 2026-08-08 | CONFIRMED | — |
| BR-REP-016 | A19 Dunning 1/2/3 = reminder stages of the BR-PAY-017 sequence; day numbers 7/14/30 are SEEDED DEFAULTS of the tenant-config cadence | PO RQ-8, 2026-08-08 | CONFIRMED | — |
| BR-REP-017 | Scheduled-report email ships W6 with all email; v1 = PDF download only (consistent with OQ-073) | PO RQ-9, 2026-08-08 | CONFIRMED | — |
| BR-REP-018 | Every report download follows IS-11: CSV always + PDF where layout matters; NO XLSX v1; standard PDF skeleton (letterhead, filters echoed, basis label, generated-by); strict CSV contract (snake_case headers, plain 2dp money, ISO dates, no metadata rows, context in filename); scheduled files retained 3 days default, tenant-config | PO 2026-08-08 (IS-11) | CONFIRMED | — |
| BR-REP-019 | Saved custom reports are CREATOR-PRIVATE by default with an explicit share toggle (shared = visible to all report-access staff) | PO RP-1, 2026-08-08 | CONFIRMED | — |
| BR-REP-020 | Scheduled-report recipients: INTERNAL staff only in v1; EXTERNAL recipients arrive at W6 with an explicit confirm step — external send = data leaves the tenant, said in the UI | PO RP-2, 2026-08-08 | CONFIRMED | — |
| BR-REP-021 | The five column-unratified reports (disconnect/reconnect, meter inventory, PUC quarterly, rate-change history + user-activity) render via the GENERIC viewer in v1; column sets land at the next design session; user-activity report = the S61 audit dataset (owned by US-AUD-009, deduped) | PO RP-3, 2026-08-08 | CONFIRMED | — |
| BR-REP-022 | DSO target = tenant setting, default 15 days (joins the S66/S71 settings family); dashboard renders actual vs target | PO RP-4, 2026-08-08 | CONFIRMED | — |
| BR-REP-023 | Access-review report (SC-2): System Admin + Executive only — Billing Clerk excluded (user-management dataset) | PO AR-1, 2026-08-08 | CONFIRMED · **ENFORCED 2026-09-27** (`CR-142-BRC07` `P5.9`) — `report_definitions.min_role` on the `access_review` platform row, read by `apps/reports/role_gate.py` and asked TWICE: the catalogue leaves the card out, and `GET /reports/{key}` refuses 403. ⚠ It was signed for **fifty days with nothing enforcing it** — three files cited the rule, a test asserted the CITATION was present, and every card was served to every role. | T6-07 · `tests/test_rep_p5_9_role_gate.py` · `10-scripts/rep_p5_9_role_gate_walkthrough.mjs` |
| BR-REP-024 | **A dashboard tile never computes a figure.** Every KPI and panel on S7 renders the OWNING surface's own published figure, read through a seam resolved by name at call time — or **reports by name that it cannot answer. Never 0, never a client-side sum, never a second query over another module's tables.** A `None` from an owner means *"this module cannot answer"*, never *"this module has nothing"* | derived 2026-08-16 (DEF-129 lane) from BR-REP-002 + BR-LED-016 + DEF-104 (four surfaces disagreed about one balance: the account screen said $0.00 while the ledger held an issued, unpaid $108.88) + DEF-075 (a null read as "nothing" re-denominated a tenant's books) | **PROPOSED** — reported for the daily PO batch; it chooses no value, it forbids inventing one | US-REP-019 TC-4/TC-5 |
| BR-REP-025 | **The DSH-01 service mix draws THE TENANT'S OWN CONFIGURED SERVICES — ALWAYS ALL OF THEM — in the platform's fixed seed order (BR-RAT-024: Electric · Water · Gas · Sewer · Trash · Storm water · Solar · Broadband · Thermal/Heat · Battery).** ⚠ **AMENDED 2026-08-19 and the amendment is a REVERSAL.** This rule read *"FIVE FIXED ROWS — Electric, Water, Sewer, Trash, Gas"* from 2026-08-18, quoting the requirement's own reason — *"so row order is stable month to month"*. What the PO saw on 2026-08-19 is what that costs a utility that does not sell those five: **a broadband-and-water utility met five rows, three permanently empty, and its actual revenue in the remainder footnote.** PO verbatim: *"I agree - My proposal, which keeps your reason intact: draw the tenant's own configured services — always all of them"*. **The stability reason survives**: a service list changes when a utility ADDS a service, not month to month. A configured service with no revenue is still DRAWN with a zero-width bar and an em-dash and is never omitted, and **`$0.00` is never printed in this column** — an absent row says "this utility does not sell trash" and an em-dash says "trash billed nothing this month", which are two different facts. ⚠ **THE REMAINDER SURVIVES THE AMENDMENT AND IS STILL NOT OPTIONAL**: revenue that names NO service at all (a late fee is charged to an ACCOUNT) has no row to live in however complete the list is, and revenue on a service billed earlier in the period and since switched off has none either — folding either into a service row is a wrong figure and dropping it makes the panel foot to less than the period's revenue (BR-REP-002's own shortfall rule). ⚠ **The panel is EMPTY only when there is nothing to draw at all** — a month in which nothing has been billed yet still shows the utility its own services, each an em-dash, because *"always"* is the word the ruling turns on | PO ruling 2026-08-18 (CR-012 · the DSH-01 requirements) **AMENDED by PO ruling 2026-08-19** (CR-012 design review, decision 1 — 12-governance/02-decision-log.md) | **CONFIRMED (amended 2026-08-19)** | US-REP-019 TC-11/TC-12 · test_cr012_r1..r1g |
| BR-REP-026 | **Service-mix bars are proportional to the LARGEST service, not to the total.** PO verbatim: *"Bars proportional to the largest service, not the total."* On the PO's own figures — Electric 238k, Water 76k, Sewer 28k — that is Electric **100%**, Water **32%** (76/238), Sewer **12%** (28/238), and Trash and Gas **0%**. ⚠ **THIS REVERSES WHAT THE r10 FILE DRAWS** and the reversal is recorded so nobody re-derives the old answer: `05-prototype/r10-2026-08-16/SMARTBillHub.dc.html` hardcodes 70/22/8, which is 238/342, 76/342 and 28/342 — a share of the TOTAL summing to 100. r10 is the reference for layout, copy, flows and states (PO 2026-08-16); it is not a signed statement of arithmetic, and where the requirement and the drawing disagree the requirement governs. **The percentage is computed by the SERVER and arrives as an integer** (BR-REP-029) — a client that computed a share of money would be arithmetic over money on the busiest screen in the app **THREE IMPLEMENTATION DECISIONS, from the five worked examples the PO asked for (11-change-requests.md §"THE BAR RULE, WORKED"):** (1) the percentage is ROUNDED TO A WHOLE NUMBER and the bar width uses **that same rounded figure**, so the number and the bar can never disagree; (2) a NON-ZERO service floors at a visible bar — $1,900 beside $238,400 draws **1%**, never nothing, because a service that billed real money must not render as absent; (3) `—` means *not sold / nothing billed* and **`$0.00` is never printed in the value column**, because a printed zero and an absent service look identical to a reader and mean opposite things. The 100% bar belongs to whichever of the five billed MOST, not to Electric by right (worked example B: a water-only utility draws Water 100 / Sewer 33 / Trash 14). With nothing billed at all, no division is performed — five em-dashes, no divide-by-zero, and no `0%` anywhere (worked example D). The ruled column sums to **144%** on r10's own figures and is not meant to reach 100 | PO ruling 2026-08-18 (CR-012 · the DSH-01 requirements, verbatim in 12-governance/11-change-requests.md §CR-012) | **CONFIRMED** | US-REP-019 TC-13 |
| BR-REP-027 | **The DSH-01 cycle status line.** `{weekday} · {month day} · Cycle {code} closes in {n} days`, where the named cycle is *"the next-closing active cycle from SET-07 (tie broken by account count)"* (PO verbatim). Four states and no fifth: **normal** (n ≥ 1) · **"closes today"** (n = 0) · **"closed — bill run pending"** (the close is past and the cycle's run has not happened) · **no cycle configured**. ⚠ **AMENDED 2026-08-19: the fourth state OFFERS NO LINK.** It read *"which links to Settings → Routes & Cycles rather than printing a countdown to nothing"*; the PO ruled *"no provide any link - also consider what if status are set in settings - check that out"*, the second half was checked (cycle set-up does live in Settings → Routes & Cycles, CR-006's surface, reachable from the sidebar on every screen), and the line now **reflects the configured state rather than prompting a set-up**. The served `settings_target` is REMOVED rather than left unrendered, because a served target nothing draws is dead payload. A DRAFT or INACTIVE cycle is never named (BR-MET-076). "Closes" is the end of the READ WINDOW (`cycles.read_day_to`) — see OQ-221. ⚠ **AMENDED AGAIN 2026-08-23 — CR-029 D8② THEN RC-W5-T2, AND THE FOUR STATES ARE NOW TWO PLUS "NO CYCLE CONFIGURED".**

**First, D8② settled OQ-221.** PO verbatim: *"② which date 'closes in 4 days' counts to - **Next cycle date**"* — neither of the day-of-month candidates OQ-221 offered. So the line counts to `next_cycle_date`, metering's own derivation from start day · frequency · days-to-complete · first run (`apps/metering/period_engine.py`), and the dashboard and SET-07D's Schedule card cannot disagree about one cycle. Worked: a cycle whose next date is **1 Sep**, read on **28 Aug**, is *"closes in 4 days"*; on 1 Sep it is *"closes today"*.

**Then RC-W5-T2 dropped `cycles.read_day_to`, and TWO states went with it.**

* **`closed — bill run pending` is UNREACHABLE.** It was derived ENTIRELY from the day-of-month defaults — *"the read window has shut and the cycle's bill day has not arrived"* — and its own gap note (`GAP_CYCLE_RUN_NOT_PUBLISHED`) already recorded that it could not say whether a run had ACTUALLY happened, because billing publishes no per-cycle run read. The constant and the gap row are KEPT UNRENDERED and name the read that would restore it honestly (`apps.billing.selectors.last_run_for_cycle`); that is a named absence, not dead code.
* **A cycle that cannot say when it next comes round is SKIPPED**, where a transitional fallback used to count it down from `read_day_to`. RC-W2 left that branch and named its own end in as many words. The remedy for such a tenant is a **first-run date on the cycle** — a field the wizard asks for — rather than a date the reports module derives from a column nobody chose.

**So the live states are: `closes in n days` · `closes today` · `no cycle configured`.** The tie-break (more accounts wins) and the draft/inactive exclusion (BR-MET-076) are unchanged. **This amendment is REPORTED for the PO's ratification — it narrows a CONFIRMED rule as a consequence of D8② and D2, and no ruling named the loss of `closed — bill run pending` explicitly.** | PO ruling 2026-08-18 (CR-012) **AMENDED by PO ruling 2026-08-19** (decision 5) **· AMENDED 2026-08-23 by CR-029 D8② + RC-W5-T2** | **CONFIRMED (amended 2026-08-19) · NARROWED 2026-08-23, ratification REPORTED** (OQ-221 CLOSED by D8②) | US-REP-019 TC-14 · `test_cr012_tc14__the_cycle_states_that_survive_d8` · `test_cr012_tc14c` · `test_cr012_tc14d` · `tests/test_cr029_rcw5_legacy_columns.py` |
| BR-REP-028 | **Every DSH-01 region loads, empties and FAILS INDEPENDENTLY.** PO verbatim: *"Per-section loading/empty/error states; one section failing must not blank the page"* and *"Regions load, empty and fail independently."* The six regions are cycle status · KPI band · recent activity · service mix · AR aging · to do. A region that raises serves its own `error` object with a stable code beside the five that answered, and **the page still renders** — the screen never degrades to a single error panel and never renders a region's absence as a zero. Empty states keep their header and their link | PO ruling 2026-08-18 (CR-012 · the DSH-01 requirements, verbatim in 12-governance/11-change-requests.md §CR-012) | **CONFIRMED** | US-REP-019 TC-15/TC-16 |
| BR-REP-029 | **Money and counts on DSH-01 arrive PRE-FORMATTED as strings; the client performs no currency math.** PO verbatim: *"Money and counts arrive pre-formatted as strings — no client-side currency math."* Every figure travels twice: the exact NUMERIC(18,6) decimal string (hard rule 2, unchanged) AND a `display` string the SERVER formatted from the tenant's own `number_format` and CHAR(3) currency, rounded ONCE, half-up, to BR-TEN-080's two display decimals. ⚠ **This is in tension with BR-SHL-023** (*one money formatting path* — `MoneyCell`, client-side) and the tension is stated rather than smoothed: the dashboard's server formatter is built to reproduce `MoneyCell`'s en-US output byte for byte ($184,320.00), so the two paths agree today, and reconciling them permanently is the platform-shell owner's call, not this screen's. Reason the PO's direction is the right one: a client that rounds money can round it differently from the bill | PO ruling 2026-08-18 (CR-012 · the DSH-01 requirements, verbatim in 12-governance/11-change-requests.md §CR-012) | **CONFIRMED** (BR-SHL-023 tension REPORTED, not resolved) | US-REP-019 TC-17 |
| BR-REP-030 | **DSH-01 AR aging: five buckets, a rounded share, and the arrangement rule.** Buckets are Current / 1–30 / 31–60 / 61–90 / 90+ **by days past due**, each with accounts, amount and share of AR. ⚠ **Accounts on an ACTIVE PAYMENT ARRANGEMENT count in their TRUE bucket, not Current** (PO verbatim) — which is the opposite of what a naive implementation does, and is why the figure comes from `payments.outstandings`, whose bucket is derived from the oldest unpaid bill's due date and never from `payment_plans.status`. **Shares are rounded and NEED NOT TOTAL 100%** (PO verbatim: *"rounded, need not total 100%"*) — no fudge row, no balancing remainder, and a share of nothing is NULL rather than 0% | PO ruling 2026-08-18 (CR-012 · the DSH-01 requirements, verbatim in 12-governance/11-change-requests.md §CR-012) | **CONFIRMED** | US-REP-019 TC-18/TC-19 |
| BR-REP-031 | **DSH-01 recent activity: last 24 hours, MAX SIX ROWS, newest first, from the AUDIT LOG — and THE PANEL SAYS SO.** PO verbatim: *"Sourced from the audit log filtered to operator-relevant types; events the role can't see in their own module are excluded."* ⚠ **ADDED 2026-08-19, PO verbatim: *"yes it shoudl state the window"*.** The panel STATES the window it read, because *"nothing has happened here yet"* means something very different at 24 hours than at forever, and on a utility's first Monday the difference is the whole message. The window is published as a FIGURE (`window_hours`) that the screen renders into its own language, so changing it changes eleven catalogues' wording rather than leaving ten of them claiming 24 hours. The window is measured back from the read's `as_of` and is an ARGUMENT, never a clock (BR-TEN-043). Operator-relevant means the named classes — bill runs, payments, read imports, adjustments, dunning, new accounts — and nothing else: settings edits, user administration and login events are NOT operator work. A row carries `—` where there is no amount, and **on this deployment every row does**, because `audit_log` has no money column (BR-REP-024). "View all →" opens the audit log unfiltered | PO ruling 2026-08-18 (CR-012) **EXTENDED by PO ruling 2026-08-19** (decision 6) | **CONFIRMED (extended 2026-08-19)** | US-REP-019 TC-20 · test_cr012_r6 |
| BR-REP-032 | **DSH-01 To do: MAX FOUR items, generated by their OWNING modules — and A ROW NOBODY COULD COUNT SHOWS NO NUMBER.** PO verbatim (2026-08-18): *"To do holds max 4 items generated by their owning modules: `action` (billing exceptions), `review` (rate approval, disconnect eligibility), `draft` (finance close). Completing the work in the owning module clears the item on next refresh."* ⚠ **AMENDED 2026-08-19, PO verbatim: *"I will start with - Show 'Review billing exceptions' with no number"*.** An item MAY carry a count when the count is the OWNER's own published figure; **an item whose owner cannot produce one renders THE LABEL ALONE — never a `0`**, because a zero tells the operator *nothing needs my attention*, which is false when nobody counted. This is BR-REP-024 applied to this panel and it covers all six emittable codes: `billing_exceptions`, `disconnect_eligible`, `finance_close`, `rate_approvals`, `import_reads`, `run_billing`. The two absences stay apart: a count of `0` means the owner COUNTED and found nothing, so there is no row at all. Nothing on this panel is stored: no to-do table, no done flag, no dismiss — the item disappears because the work disappeared. **"Assign" is not built** (OQ-222); its role gate, when it is built, is System Admin | PO ruling 2026-08-18 (CR-012) **AMENDED by PO ruling 2026-08-19** (decision 3) | **CONFIRMED (amended 2026-08-19)** | US-REP-019 TC-21 · test_cr012_r3/r3b |
| BR-REP-033 | **Nothing on DSH-01 mutates data, and the two page actions are role-gated.** Every control is a navigation or a workflow entry point, so the screen writes no `audit_log` row of its own and needs no confirm anywhere. **`Import reads` (secondary) and `Run billing →` (primary) are HIDDEN — not disabled — for read-only roles** (PO verbatim: *"Both hidden for read-only roles"*); by A4's addendum the Executive is view-only on Reads & Billing runs and is therefore the read-only role here. **KPI cells do not navigate in v1** (PO verbatim). All roles see the dashboard; actions and To-do links degrade by permission. **A KPI must agree with its owning module for the same as-of moment; where cached, state cache age rather than disagree with Finance** (PO verbatim) — which on this build is structural rather than promised: every figure is read at one `as_of` through the owner's own read model and nothing on this screen is cached | PO ruling 2026-08-18 (CR-012 · the DSH-01 requirements, verbatim in 12-governance/11-change-requests.md §CR-012) | **CONFIRMED** | US-REP-019 TC-22 |
| BR-REP-034 | **The MTD-revenue tile's sub-line is a TYPED PER-TENANT MONTHLY TARGET, and with no target typed the tile shows the figure alone.** PO ruling 2026-08-18, closing OQ-265: four options were put up against one fixture (Silver Creek Water, MTD billed **$342,700.00**, Aug 18) and **the PO answered "B"**. With a **$400,000** target the sub-line reads exactly **`86% of $400,000 target`** (342,700 ÷ 400,000 = 85.675% → **86%**, rounded half-up to a whole number, the same rounding BR-REP-026 applies to the bars). **WITH NO TARGET TYPED THE TILE DEGRADES TO THE FIGURE ALONE — no sub-line, no percentage, no bar, no up/down delta** — and that untyped state is the DEFAULT for every tenant that exists today, so it is the state that must be proved first: a new tenant on day one sees nothing rather than a wrong denominator. ⚠ **DAY-PRORATED COMPARISONS ARE FORBIDDEN, and the reason is recorded so they are not re-proposed:** options (c) *same month last year* and (d) *pace vs last closed month* both pro-rate by DAYS ELAPSED, and billing is lumpy by cycle — if cycle 1 (842 accounts) issues Aug 5 and cycle 2 (405) issues Aug 20, then on Aug 18 straight-line assumes **58%** of the month is billed while the real billed share is 842/1,247 = **68%**. ⚠ **WHAT THE SIGNATURE DOES NOT COVER, per the sign-off rule (a signature covers only what was shown):** where in Settings the field lives, who may edit it, whether it is per-service or whole-tenant, and what happens when a tenant edits it mid-month. None was shown, so none is signed | PO ruling 2026-08-18 (OQ-265 CLOSED; 12-governance/02-decision-log.md §"THE MTD-REVENUE FORECAST IS A TYPED TENANT TARGET") | **CONFIRMED** (the four uncovered questions are NOT) | US-REP-019 TC-23/TC-24 |
| BR-REP-035 | **THE DASHBOARD REPORTS OVER A WINDOW THE OPERATOR CHOOSES, AND THE DEFAULT IS THE LAST COMPLETED BILLING CYCLE — falling back to the last 30 days only when no cycle is configured.** ⚠ **AMENDED 2026-08-23 BY `CR-029` `D8①` AND NOT STAMPED HERE UNTIL 2026-09-26 (`CR-142-BRC07` `P0.15` / `DEF-REP-6808`).** Asked what makes a cycle *"completed"*, the PO ruled verbatim **"dont build it"**, closing `OQ-268` WITHDRAWN. **The COMPLETED-CYCLE WINDOW IS REMOVED AND NOTHING IS SUBSTITUTED** — the menu offers THREE windows (last 30 days · this accounting period · last accounting period) and the default is **the last 30 days**, which is the fallback CR-015's own ruling already named. `last_cycle` survives as a recognised TOKEN so a shared link still resolves; it is never offered and never built. The rest of this rule — the operator chooses, the window is stated in dates — stands unchanged. PO ruling 2026-08-19 (CR-015), verbatim: *"If we allow this then there is now way user can see previous values and they will be confuse what is dashbaord is saying - so we will ahve to allow period filter on dashbaord - so user can select the filter ; default filter can be last cycle or last 30 days and let user to change the peiod"*. ⚠ **THE TWO OPTIONS THE PO OFFERED ARE NOT EQUIVALENT AND THE RULING IS THE FIRST.** A completed cycle is the utility's OWN unit — what Finance closes against, what a bill run produces, what an operator means by *"how did we do"* — and it is **STABLE**: it does not slide under the reader between two glances. A rolling thirty days agrees with nothing else in the product and shows two people different figures an hour apart, so it is the FALLBACK for the tenant that has no cycle yet, whose cycle-status line already reads `not_configured`. **THE VOCABULARY IS FOUR WINDOWS**, in this order: last completed cycle · last 30 days · this accounting period · last accounting period. An option the server cannot compute is **ABSENT** from the menu with a named reason (`no_completed_billing_cycle`, `fiscal_period_not_configured`), never present-and-broken. **WHY THE CALENDAR MONTH HAD TO GO, and it is not about a fixture:** a real utility on the **3rd of any month**, having billed on the 25th, met a dashboard showing almost nothing — revenue near zero, service mix nearly empty, for the first week of every month forever, with nothing broken. The demo seed EXPOSED that; it did not cause it. ⚠ **THE SELECTED WINDOW IS STATED PROMINENTLY ON SCREEN, IN DATES, ABOVE THE FIGURES** — not buried in the filter control. That is the PO's consistency rule (*"a KPI must agree with its owning module for the same as-of moment"*) surviving contact with a user-chosen window: once a user may pick an arbitrary period the dashboard can differ from Finance **because they are looking at different weeks**, both correct, and it reads as a bug unless the reader can see which window each is showing. ⚠ **WHAT THE SIGNATURE DOES NOT COVER** (a signature covers only what was shown): what makes a cycle "completed" and what its window's two ends are. That is a LANE DERIVATION over SET-07's published fields — *complete when its `bill_date` has passed; window `window_start` … `bill_date`* — recorded in the decision log with the worked cycle (08-B, reads 12–16 Aug, bills 19 Aug) and put to the PO as **OQ-268** rather than left as a caveat in this row | PO ruling 2026-08-19 (CR-015; 12-governance/02-decision-log.md §"FOUR RULINGS" 3) | **CONFIRMED-AS-AMENDED** (`CR-029` `D8①` 2026-08-23 — the completed-cycle window is WITHDRAWN; the completed-cycle derivation was never confirmed and is now moot) | CR-015 backend suite · e2e/CR-015-dashboard-period.spec.ts |
| BR-REP-036 | **`as_of` IS THE MOMENT THE FIGURES WERE READ, CLAMPED INTO THE SELECTED PERIOD — so mid-period it is today, and once a period closes it is the period end.** PO ruling 2026-08-19, option (a), closing DEF-299. **Shown:** today was **2026-08-19** and the dashboard reported **`as_of 2026-08-31`**, eleven days in the future, on the first screen after every sign-in. Nothing disagreed with anything else — the value was CARRIED correctly by all six regions, which is why every internal check in the repo was green. What was wrong was what it MEANT: the PO's own rule is that a KPI must agree with its owning module **for the same as-of moment**, and that cannot be checked by a person comparing a dashboard label of the 31st against a Finance page headed the 19th. It is also the value a cache states its age against, so a server-side dashboard cache cannot be built on the old behaviour. **Option (c) — the timestamp of the newest data — was REJECTED**: on the demo fixture it would read *as of Jul 31*, truthful about the data and reading as though the dashboard itself were a month stale. ⚠ **`as_of` STAYS AN ARGUMENT AND IS NEVER A CLOCK INSIDE THE READ (BR-TEN-043).** Pass it and no clock is consulted at all; the tenant's own today is read once, at the boundary, only when the caller supplied nothing. ⚠ **A SECOND DATE IS PUBLISHED BESIDE IT — `read_on`, the day the figures were read.** They are equal for any window containing today, which is every default, and they diverge the moment a CLOSED period is selected. The page BODY is as of `as_of`; the page HEADER's date line and its cycle countdown are as of `read_on`, because *"cycle 08-A closes in 4 days"* is a statement about the future from now and a countdown from a window that ended last week reads as a negative number of days | PO ruling 2026-08-19 (DEF-299 option (a); 12-governance/02-decision-log.md §"FOUR RULINGS" 4) | **CONFIRMED** | CR-015 backend suite (`as_of` mid-period, closed period, and the clamp's lower end) · e2e/CR-015-dashboard-period.spec.ts |

---

## R1–R46 — THE DRAWN REGISTER (brief p49–p73), AND THE 53 WARNINGS CLASSIFIED

**Source:** `05-prototype/09 Reports Build Brief.pdf` §03 *"The 46, drawn"*, pages
**49–73**, read **as images at scale 4** per B14 rule 42 (`10-scripts/pdf/pdf_render.py`).
Transcribed 2026-09-26 by lane **REP-REGISTER**.

⚠ **THIS SECTION IS A TRANSCRIPTION, NOT A RATIFICATION.** Every column list below is
what the drawing **shows**, in the order it draws it. **B14 rule 37 makes a drawn figure
an illustration**, `BR-REP-021` already puts five of these reports on the generic viewer
*because their column sets are unratified*, and `reports/0003_seed_catalogue.py`
deliberately seeds **no `columns` on any of the 46** for exactly that reason. **Nothing
here is seeded and nothing here should be** — an empty `columns` means *"every column the
dataset declares"*, and whether these 46 drawn sets become ratified lists is a question
for the Product Owner, put to them with the figures below.

⚠ **WHY THIS EXISTS AT ALL.** These 53 rule-bearing warnings lived in a PDF and in nothing
else, and **a PDF is the one place no check in this repo can read**. The repo has already
paid for that once — a PO ruling sat in the Finance blueprint and in no register and had to
be transcribed after the fact. A transcription rots, so it is guarded:
`06-backend/tests/test_rep_r1r46_drawn_register.py` compares the drawn record against the
seed **in both directions** and fails the day a definition is added, removed or renamed
without this section moving. The drawn column lists themselves are data, in
`10-scripts/rep_r1r46_drawn.py`; **run `python3 10-scripts/rep_r1r46_drawn.py --report`**
rather than trusting a figure quoted here.

### The arithmetic, measured

| | |
|---|---|
| definitions seeded | **46** (45 cards · 1 tab — R42 is Tab 2 by PO ruling and is not drawn) |
| drawings | **51** (R24 and R25 are one definition each, drawn at four subjects) |
| drawings whose column count differs from its dataset's | **48 of 51** — only R17, R18 and R43 agree |
| drawings whose headings match **no** declared column at all | **16** — R7, R15, R16, R17, R18, R19, R21, R43, R24a, R24d, R26, R28, R32, R39, R40, R41 |
| widest gaps | **R1** 5 → 19 (+14) · **R2**, **R14**, **R19** 6 → 19 (+13) |
| R-rows whose dataset does not resolve to one of the nine | **0** |

⚠ **THE COUNT GAP UNDERSTATES THE PROBLEM AND THE OVERLAP IS THE HONEST FIGURE.** A
definition with an empty `columns` serves *every column the dataset declares*, so the
generic viewer does not show a **wider** version of the drawn table — on sixteen of these
it shows a **different** table. `R28 Read Completeness` heads ROUTE · READER · EXPECTED ·
ACTUAL · ESTIMATED · SKIPPED · MISSING · COMPLETE, and `meter_reads` publishes one row per
**read**: not one heading corresponds. Those sixteen are reports whose rows are
**aggregates**, and no column list can reconcile them — they need a query, not a ratified
column set.

### The four buckets

**LAW** it restates a signed rule or a PO ruling · **TEST** checkable and unchecked ·
**DEFECT** the product contradicts it today · **OPEN** needs a decision nobody has made.

| bucket | count | note |
|---|---|---|
| LAW | **34** | 28 cite an existing id; 6 state a design intent no rule covers and none is contradicted |
| TEST | **13** | **2 are writable today** and are written (below). The other 11 name behaviour of reports with **no query behind them** — six of the nine datasets have none — so the test is owned by the phase that builds the query, and is named per row |
| DEFECT | **6** | `DEF-REP-6824` · `6825` · `6826` · `6827` · `6828` · `6829`, all filed |
| OPEN | **0** | deliberate — see *"Why no question was minted"* below |

⚠ **NO OPEN QUESTION WAS MINTED, AND THAT IS A FINDING RATHER THAN AN OMISSION.** Every
warning in these 25 pages either restates law already signed, is checkable, contradicts the
product, or is **ours to decide and write down** — CLAUDE.md law 13. One candidate came
close and **law 13 caught it**: R37's *"rates show four decimals"* reads like a challenge to
hard rule 2's *display 2*, and it is not — `OQ-620(a)` was **CLOSED on 2026-08-27** with the
PO's own words, *"What does a tariff rate show? Four ($0.1420). A rate is not money and not
a quantity"*. The percent half of the same sentence **is** wrong and is `DEF-REP-6829`, filed
against the document rather than asked again, because the PO has now answered the decimal
question three times (`OQ-285`, `OQ-286`, `OQ-620`) and a fourth ask manufactures exactly
the inconsistency law 13 exists to prevent.
⚠ **AMENDED 2026-10-02 — UP TO FOUR, ZEROS PAST THE SECOND DROPPED.** PO, verbatim: *"Show unit prices with up to 4 decimals and keep every total at 2."* (decision log *"THREE UI RULINGS FROM THE RATE-SCHEDULE SWEEP"* (1)). A unit price now reads `$0.0425`, `$0.10`, `$12.50` — `8.290000` reads **`$8.29`**, no longer `$8.2900`. The four-place ceiling and the reason for it stand; every amount stays at 2.

### The two guards written here, both proved RED first

`06-backend/tests/test_rep_r1r46_drawn_register.py`, through **pytest**, restored after each proof.

1. **the drawn register stays in step with the seed** — red-proved by deleting R41's drawn
   record: *"a seeded definition has no drawn record"*. **False pass it is written against:**
   reading the drawn table for both sides of the comparison (a check that cannot fail), and
   comparing two **counts**, which can agree while naming different reports — so the
   assertion is over the symmetric difference.
2. **a cross-service usage total is refused rather than computed** (R17, hard rule 3) —
   red-proved by adding a `usage` key to the footer: *"3,884,100 gal plus 1,102,400 kWh is
   not a number"*. **False pass:** asserting on `columns` instead of `totals` would forbid
   the drawing's own lawful per-service usage cell, and would go green only while the column
   is missing. ⚠ **It passes today for a reason that is itself a defect** — `DEF-REP-6828`,
   the built query serves no usage at all — which is why it exists **before** the column does.

### The 46

Group › sub-group, dataset and basis are read from `reports/0003_seed_catalogue.py`, never
re-typed. **Columns are the drawing's, in the drawn order.** Warnings are **verbatim**.

#### Billing — 5

| R | key | name | group › sub-group | dataset | basis | drawn columns | warning (verbatim) | bucket |
|---|---|---|---|---|---|---|---|---|
| R4 | `bill_run_readiness` | Bill Run Readiness | Billing › Readiness | `invoices` | Posting date | ACCOUNT · CUSTOMER · ROUTE · CHECK · DETAIL · USAGE | *"Run before the bill run, not after. The 49 held accounts are the whole point of the screen — they are what a clerk fixes in the twenty minutes before issuing 1,198 bills."* | **LAW** (design intent, no id — nothing contradicts it) |
| R5 | `billing_register` | Billing Register | Billing › Bills | `invoices` | Posting date | BILL # · ACCOUNT · CUSTOMER · TYPE · SERVICES · USAGE · AMOUNT · FLAG | *"The one report where **cycle** must be a parameter, not a date range. Today it runs on a date range only."* | **DEFECT** `DEF-REP-6824` |
| R6 | `bill_adjustments` | Bill Adjustments | Billing › Bills | `invoices` | Posting date | DATE · BILL # · ACCOUNT · REASON · BY · APPROVED BY · AMOUNT | *"An adjustment is a new row, never an edit. Issued invoices take no UPDATE and no DELETE — so this report lists corrections, and there is no edit control on any row of it."* | **LAW** — hard rule 4. Confirmed: no adjustment path UPDATEs an issued invoice |
| R7 | `bill_print_file` | Bill Print File | Billing › Delivery | `invoices` | Posting date | BATCH · CYCLE · BILLS · PAGES · BUILT · STATUS · FILE | *"The 137 suppressed bills are the eBill enrolments. They are stated rather than silently missing from the count."* | **TEST** (no query — owned by the phase that builds it). Same family as `BR-REP-024`: a stated absence, never a silent one |
| R8 | `bill_delivery` | Bill Delivery | Billing › Delivery | `audit_log` | — (no money) | ACCOUNT · CUSTOMER · CHANNEL · ADDRESS · SENT · STATUS · REASON | *"The address column walks to `premises` — an address is stored in one place and every other entity derives it. Nothing here holds its own copy."* | **LAW** — hard rule 8 / `BR-MET-1161` |

#### Receivables — 9

| R | key | name | group › sub-group | dataset | basis | drawn columns | warning (verbatim) | bucket |
|---|---|---|---|---|---|---|---|---|
| R1 | `payments_by_method` | Payments | Receivables › Payments | `payments` | Clearing date | METHOD · TELLER · COUNT · AMOUNT · SHARE | *"Group by switches this between method, teller, purpose and day. **Four reports, one row.**"* | **DEFECT** `DEF-REP-6825` — the query groups by method only and serves no teller |
| R2 | `deposit_batches` | Deposit Batches | Receivables › Payments | `payments` | Clearing date | BATCH · DAY · TENDER · ITEMS · AMOUNT · STATUS | *"A batch groups by **day and tender**. That is why a payment's tender can no longer be corrected once it is banked."* | **LAW** — hard rule 4's narrow exception, and it **reads correctly**: `method_id` is one of the three correctable columns and is refused once banked |
| R3 | `payment_exceptions` | Payment Exceptions | Receivables › Payments | `payments` | Clearing date | DATE · KIND · PAYMENT · ACCOUNT · BY · REASON · AMOUNT | *"Row two is the only kind of change a payment permits. Three columns may be corrected in place — the cheque number, the memo and the tender — through one named endpoint. Everything else about a payment is frozen."* | **LAW** — hard rule 4 as narrowed 2026-09-02; the endpoint is `POST /payments/{id}/correct-reference` |
| R9 | `ar_aging` | AR Ageing | Receivables › Arrears | `payments` | Posting date | ACCOUNT · CUSTOMER · CLASS · CURRENT · 31–60 · 61–90 · 90+ · TOTAL | *"An account on a payment arrangement counts in its true bucket, not Current — the bucket comes from the oldest unpaid bill's due date, never from the plan's status. Shares are rounded and need not total 100%."* | **LAW** — `BR-REP-030`, word for word, including the rounding clause |
| R10 | `debtor_list` | Debtor List | Receivables › Arrears | `payments` | Posting date | ACCOUNT · CUSTOMER · SERVICE ADDRESS · OLDEST BILL · DAYS · OWED · ARRANGEMENT | *"This list and the cut-off list are the same query with one flag. Today it is unpaginated on purpose — correct at 3,000 connections, 13× short at 40,000."* | **DEFECT** `DEF-REP-6826` — ⚠ **the second sentence is STALE.** `CR-138` `P4` withdrew that justification on 2026-09-23; `/outstandings` pages and sorts in SQL. `DEF-PAY-4221` stays open for the **wiring** (`DEF-PAY-6271`) |
| R11 | `cut_off_list` | Cut-Off List | Receivables › Arrears | `payments` | Posting date | ACCOUNT · CUSTOMER · SERVICE ADDRESS · OWED · DAYS · ELIGIBLE · HOLD REASON | *"The hold reason is served, not inferred. A clerk removing an account from this list is making a decision that must be recorded, and the eligibility flag is what makes that possible."* | **TEST** (no query). A served-not-inferred rule is `BR-REP-024`'s shape; the test belongs with the query |
| R12 | `collections_activity` | Collections Activity | Receivables › Recovery | `payments` | — | DATE · ACCOUNT · KIND · STAGE · CHANNEL · OUTCOME · AMOUNT | *"Dunning stage names come from the tenant's own cadence, not from a hardcoded 7/14/30. Those day numbers are seeded defaults a utility edits."* | **LAW** — `BR-REP-016`, verbatim agreement |
| R13 | `write_offs_and_late_fees` | Write-Offs & Late Fees | Receivables › Recovery | `invoices` | Posting date | DATE · ACCOUNT · KIND · REASON · APPROVED BY · AMOUNT | *"Write-offs are excluded from collection rate and shown separately — folding them in would flatter the figure."* | **LAW** — `BR-REP-009`, verbatim. ⚠ **TEST also owed:** nothing asserts the exclusion against a computed collection rate |
| R14 | `closed_account_balances` | Closed Account Balances | Receivables › Recovery | `payments` | Posting date | ACCOUNT · CUSTOMER · FINAL BILL · FORWARDING ADDRESS · OUTCOME · BALANCE | *"Three of Augusta's named mandatory reports are this one row with the outcome filter changed: final billed still owing, final-bill credits, and the collection-agency hand-off file."* | **LAW** (requirement consolidation, no id) |

#### Finance — 9

| R | key | name | group › sub-group | dataset | basis | drawn columns | warning (verbatim) | bucket |
|---|---|---|---|---|---|---|---|---|
| R15 | `trial_balance` | Trial Balance | Finance › Ledger | `journal_lines` | Posting date | ACCOUNT · NAME · OPENING · DEBITS · CREDITS · CLOSING | *"Balanced pairs are a database guarantee, not a report's opinion. A difference other than zero here means the posting service has a defect, not that the report needs tuning."* | **LAW** — hard rule 5 |
| R16 | `journal_export` | Journal Export | Finance › Ledger | `journal_lines` | Posting date | BATCH · PERIOD · ENTRIES · LINES · VALUE · EXPORTED · FILE | *"Idempotent by batch. Re-exporting a batch produces the same file; it does not double-post. The ERP is the system of record for the general ledger and this is the only way out."* | **LAW** — hard rule 6 + `BR-REP-005` |
| R17 | `revenue_by_service_rate` | Revenue Analysis | Finance › Income | `journal_lines` | Posting date | SERVICE · RATE SCHEDULE · ACCOUNTS · USAGE · USAGE REV · BASE · TAX · TOTAL | *"The usage column shows an em-dash for sewer and a blank total, on purpose. Gallons and kilowatt-hours cannot be added, so a cross-service usage total is refused rather than computed. Money adds; quantities do not."* | **TEST** (written, green, RED-proved) **+ DEFECT** `DEF-REP-6828` — the built query serves **no usage column at all** |
| R18 | `tax_remittance` | Tax Remittance | Finance › Income | `journal_lines` | Posting date | AUTHORITY · TAX · BASIS · TAXABLE · RATE · COLLECTED · REMITTED · DUE | *"Two bases in one report, labelled per row. Franchise fees read the clearing date and the others read posting — a dual-basis report is correct and unlabelled money is a contract failure."* | **LAW** — `BR-REP-001` + `BR-REP-003` (S41 dual-basis with a basis indicator) |
| R19 | `cash_reconciliation` | Cash Reconciliation | Finance › Cash | `payments` | Clearing date | DATE · REFERENCE · DESCRIPTION · SYSTEM · BANK · STATUS | *"The difference tile reads $0.00 while two rows are unmatched, and that is correct: the bank charge is not a payment. An unmatched row is a thing to explain, not a thing that breaks the reconciliation."* | **TEST** (no query) — a tile and its rows disagreeing **on purpose** is exactly the shape a naive assertion gets wrong |
| R20 | `deposits` | Deposits | Finance › Cash | `payments` | Clearing date | ACCOUNT · CUSTOMER · CLASS · TAKEN · AMOUNT · APPLIED · HELD | *"Two of Augusta's mandatory reports are this one row with the mode switched — deposits held at year end, and deposits taken in a date range."* | **LAW** (consolidation, no id) |
| R21 | `close_pack` | Close Pack | Finance › Ledger | `journal_lines` | Posting date | CHECK · SOURCE A · VALUE A · SOURCE B · VALUE B · DIFFERENCE · RESULT | *"Four of Augusta's named reports collapse into this one view switch — tie-out, pull totals, interdepartmental charges and the calculation audit. A drift here is a release blocker, not a report finding."* | **LAW** — `BR-REP-004` (*"drift = red flag + release blocker"*) |
| R42 | `operational_dashboard` | Operational Dashboard | Finance › Performance | `journal_lines` | Posting date | **not drawn — it is Tab 2** | *"This one is not in the catalogue and is not drawn here. It has no parameters worth exporting, no rows and no file — it is a screen. PO ruling: it becomes **a tab of its own** at `/reports/dashboard`, drawn as 4·1, and **the existing shell dashboard is not replaced or touched**. A card pointing at a sibling tab is noise, so there is no card. **That is why the catalogue holds 45 and the answers number 46.**"* | **LAW** — PO ruling |
| R43 | `trend_pack` | Trend Pack | Finance › Performance | `journal_lines` | Posting date | PERIOD · REVENUE · TARGET · COLLECTED · RATE · DSO · ACCOUNTS · REBILLS | *"The target is a typed per-tenant figure and is empty on every tenant that exists today, so the tile degrades to the figure alone. Day-prorated comparisons are forbidden — billing is lumpy by cycle, and straight-lining misreads it by ten points."* | **LAW** — `BR-REP-034`, both halves, including the ten-point figure (58% straight-line vs 68% real). ⚠ **Not OPEN:** the field exists (`seams.monthly_revenue_target()`) and the degrade is built. ⚠ **But BR-REP-034 signed a MONTHLY target and this draws one per ACCOUNTING PERIOD** — inside that rule's own *"what the signature does not cover"* clause, which is already on the agenda |

#### Customers — 9

| R | key | name | group › sub-group | dataset | basis | drawn columns | warning (verbatim) | bucket |
|---|---|---|---|---|---|---|---|---|
| R22 | `account_census` | Account Census | Customers › Accounts | `accounts` | As at | ACCOUNT · CUSTOMER · PREMISES · CLASS · SERVICES · STATUS · OPENED · BALANCE | *"The address column walks to premises and declares nothing of its own — hard rule 8. Unit B refines the premises by label, so it shares the street address and may carry its own point on a map."* | **LAW** — hard rule 8 **and** `BR-MET-1162`'s coordinate narrowing, both stated correctly |
| R23 | `account_activity` | Account Activity | Customers › Accounts | `accounts` | Event date | DATE · ACCOUNT · CUSTOMER · EVENT · PREMISES · BY · EFFECTIVE | *"Two date columns because two dates exist — when the clerk did it, and when it takes effect. A move-in dated 1 October appears in September's activity and in October's census, and both are right."* | **LAW** (no id) — the same two-dates rule `BR-PAY-021` states for payments |
| R24 | `statement` | Statement | Customers › Statements | `invoices` | Statement date | **four subjects — see below** | *"**Master is not a fifth subject** — the code is explicit that 'a master account is an ordinary row' with `kind='master'`, and there is deliberately no separate route for it."* | **LAW** |
| R24a | — | Statement · by account | " | " | " | DATE · REFERENCE · DESCRIPTION · CHARGES · CREDITS · BALANCE | *"This is what `/reports/account-ledger` is today — a whole page for one of four grains."* | **LAW** (as-built) |
| R24b | — | Statement · by customer | " | " | " | ACCOUNT · PREMISES · SERVICE · OPENING · CHARGES · CREDITS · CLOSING | *"One customer, three addresses — which is why Customer cannot be a filter on the account statement. The premises column is not stored on the account; it is **walked to premises**, hard rule 8."* | **LAW** — hard rule 8 |
| R24c | — | Statement · by premises | " | " | " | ACCOUNT · UNIT · CUSTOMER · KIND · CHARGES · CREDITS · CLOSING | *"The master account is a row like any other, marked, never merged. … **This report crosses customers — and that is now ruled.** Staff see it as drawn. In the customer portal a landlord sees **their own master account only**: the $69.60, never Unit 3's $100.00 (`P4.15`)."* | **LAW** (ruled) — ⚠ **the portal half is a money-privacy boundary owned by `P4.15`** and is flagged to that lane |
| R24d | — | Statement · by unit | " | " | " | DATE · REFERENCE · OCCUPANT · DESCRIPTION · CHARGES · CREDITS · BALANCE | *"The only one of the four that did not exist in any form. The head reads 1408 Elm Street · Unit 3 — the premises address and the unit label, because a unit refines its building by label and **declares no address of its own** (hard rule 8). An Occupant column appears here and nowhere else: a unit outlives its tenants, so a three-month statement can span two of them."* | **LAW** — hard rule 8 |
| R25 | `account_ledger` | Ledger | Customers › Statements | `journal_lines` | Posting date | **four subjects — see below** | — | — |
| R25a | — | Ledger · by account | " | " | " | DATE · TYPE · REFERENCE · DETAIL · DEBIT · CREDIT · BALANCE | *"**Dated by POSTING, not by statement** — so a bill issued on the 12th and posted on the 13th sits in a different row of this report than of that one, and both are right."* | **LAW** — `BR-REP-001` |
| R25b | — | Ledger · by customer | " | " | " | ACCOUNT · GL ACCOUNT · NAME · DEBIT · CREDIT · CLOSING | *"The GL account column is the same on every row and is drawn anyway. It is what lets a finance officer tie this straight back to the trial balance's `1200` line — and on a tenant with more than one receivable account it stops being constant."* | **LAW** (no id) |
| R25c | — | Ledger · by premises | " | " | " | ACCOUNT · UNIT · KIND · DEBIT · CREDIT · CLOSING | *"This is what `/reports/by-premises` is today — an entire page, its own table, **no paging**, for one cell of a 2×4 grid. It is also the row my own register left dangling: it said by-premises 'becomes a definition' and never named which one. **It is this.**"* | **DEFECT** `DEF-REP-6827` — a **fifth** unpaginated read, outside the four `DEF-PAY-4221` names. `NFR-3` admits no exceptions |
| R25d | — | Ledger · by unit | " | " | " | DATE · TYPE · REFERENCE · OCCUPANT · DEBIT · CREDIT · BALANCE | *"A unit is a place, and places do not owe money — people do. The closing balance here is the sum of whoever was in occupation, which is what a landlord wants and is **not** a debt anybody can be chased for. That distinction is why the Occupant column is mandatory on this subject and optional on none of the others."* | **LAW** (no id) — ⚠ *"mandatory on this subject"* is a **column-set** claim and rides with the ratification question below |
| R26 | `data_quality` | Data Quality | Customers › Accounts | `accounts` | As at | FINDING · SEVERITY · COUNT · EXAMPLE · EFFECT · FIX IN | *"Every row names the screen that fixes it. A quality report that lists problems without an address is a list of complaints — the Fix in column is the deliverable, and `P1.4` makes each one a link."* | **TEST** (no query) — and `P1.4`'s own door defect `DEF-REP-6812` is the precedent for asserting the destination **by address** |
| R27 | `plans_and_discounts` | Plans & Discounts | Customers › Enrolment | `accounts` | As at | PROGRAMME · ACCOUNT · CUSTOMER · SINCE · TERMS · INSTALMENT · REMAINING · STATUS | *"Three programmes in one table because a clerk asks one question — what is this account enrolled in. Splitting them into three reports was the first draft and it made the clerk run three."* | **LAW** (no id) |
| R44 | `my_bills_and_payments` | My Bills & Payments | Customers › Statements | `invoices` | Statement date | DATE · TYPE · DESCRIPTION · AMOUNT · STATUS (+ an unheaded action cell) | *"This one renders in the customer portal, not the staff shell — no left rail, no tenant switcher, and **the eight accessibility questions of the maintenance process apply to it**. It is the same definition row and the same dataset; only the frame differs."* | **LAW** — `12-governance/22-product-maintenance-process.md`. **TEST owed** with the portal frame |
| R45 | `my_usage` | My Usage | Customers › Enrolment | `meter_reads` | Read date | PERIOD · READ DATE · READING · USAGE · UNIT · DAYS · PER DAY · BASIS | *"Every quantity carries its unit, in its own column — hard rule 3, and the reason there is no Total usage tile on a multi-service account. The Basis column is why a customer's own figure and their bill can differ without either being wrong."* | **LAW** — hard rule 3. **Already checked across all nine datasets** by `test_p0_4__every_column_carries_a_type_and_a_quantity_carries_its_unit` |
| R46 | `bill_projection` | Bill Projection | Customers › Enrolment | `meter_reads` | Projection date | COMPONENT · BASIS · QUANTITY · UNIT · RATE · PROJECTED | *"Usage is straight-lined and base charges are not, and each row says which it is. The projection is a prediction shown to a customer, so the definition seeded by `P0.6` carries the ± range beside the figure: a single number reads as a promise and generates a complaint when the real bill differs."* | **TEST** (no query) — ⚠ **the ± range is NOT in the seeded row**, which carries register, key, name, group, sub-group, dataset and basis and nothing else. Named here rather than filed, because `P0.6` seeded no parameters for **any** of the 46 (that absence is `DEF-REP-6824`'s prevention column) |

#### Operations — 7

| R | key | name | group › sub-group | dataset | basis | drawn columns | warning (verbatim) | bucket |
|---|---|---|---|---|---|---|---|---|
| R28 | `read_completeness` | Read Completeness | Operations › Reads | `meter_reads` | Read date | ROUTE · READER · EXPECTED · ACTUAL · ESTIMATED · SKIPPED · MISSING · COMPLETE | *"Route R-03 has no reader and still reads 100% complete — an unassigned route is a scheduling gap, not a read gap, and the report must not conflate them. Complete counts actual plus estimated because an estimated read bills; Missing is the column that blocks a bill run."* | **TEST**, ⚠ **not a defect.** The drawing is explaining **its own illustration**, not reporting a bug: it *defines* Complete = actual + estimated and Missing as the blocking column. Two assertions for the phase that builds it |
| R29 | `consumption_exceptions` | Consumption Exceptions | Operations › Reads | `meter_reads` | Read date | ACCOUNT · METER · RULE · PRIOR · THIS READ · CHANGE · UNIT · STATUS | *"Prior and current sit side by side because the exception is a comparison, not a value. A reverse reading is negative usage and is shown as the raw difference, not as a percentage — dividing by a larger number to produce −0.1% would hide a meter swap."* | **TEST** (no query) — the −0.1% worked figure is the assertion |
| R30 | `usage_and_ranking` | Usage & Ranking | Operations › Reads | `meter_reads` | Read date | RANK · ACCOUNT · CUSTOMER · CLASS · USAGE · UNIT · SHARE · BILLED | *"One service at a time, and the dropdown is not optional. A ranking across water and electricity would sort gallons against kilowatt-hours, which is the single most common way a usage report lies. **The service parameter is required, not defaulted.**"* | **LAW** — hard rule 3. **TEST owed:** a *required* parameter has no representation in the seeded row (see R46) |
| R31 | `meter_fleet` | Meter Fleet | Operations › Assets | `assets` | As at | METER · TYPE · SIZE · PREMISES · INSTALLED · AGE · LAST READ · STATUS | *"A spare meter has no premises and no read, and both cells show an em-dash rather than a blank. Blank reads as missing data; the dash reads as not applicable, which is the fact."* | **TEST** (no query) — the same two-absences rule `BR-REP-025`/`026` already carry for the service mix |
| R32 | `read_import_log` | Read Import Log | Operations › Reads | `meter_reads` | Import date | DATE · FILE · SOURCE · ROWS · ACCEPTED · REJECTED · BY · DETAIL | *"A rejected row is skipped inside its own savepoint — hard-won law 14. Without the nested transaction the first rejection aborts the whole import on PostgreSQL and every row is lost at commit, while the test suite on SQLite passes. The 286 rejections are proof the savepoint is real."* | **LAW** — hard-won law 14, stated exactly. ⚠ **Its test must run on real PostgreSQL**; `config/settings/test.py` hardcodes in-memory SQLite, where the guarantee cannot exist |
| R33 | `service_order_activity` | Service Order Activity | Operations › Field | `work_orders` | Event date | ORDER · TYPE · PREMISES · RAISED · ASSIGNED · COMPLETED · DAYS · STATUS | *"Work is the eleventh module and owns these tables; this report reads them through a seam and writes nothing. The premises column walks to premises like every other address in the product — the work order declares no address of its own."* | **LAW** — CLAUDE.md module map + `G78` (which fails a foreign write) + hard rule 8 |
| R34 | `disconnect_reconnect` | Disconnect & Reconnect | Operations › Field | `work_orders` | Event date | ACCOUNT · CUSTOMER · BALANCE · NOTICE · DISCONNECTED · PAID · RECONNECTED · STATUS | *"The five states are columns, not a status filter, because a supervisor reads this to answer one question: where is each account in the sequence. Eligibility rules are the tenant's and live in Settings — this report shows who the rule selected, never decides it."* | **LAW** (no id) — and `BR-REP-021` already routes this report to the generic viewer as column-unratified |

#### Compliance — 7

| R | key | name | group › sub-group | dataset | basis | drawn columns | warning (verbatim) | bucket |
|---|---|---|---|---|---|---|---|---|
| R35 | `audit_trail` | Audit Trail | Compliance › Audit | `audit_log` | Event date | WHEN · ACTOR · ACTION · OBJECT · BEFORE · AFTER · WHERE | *"The retention tile is the honest part and it belongs here, not on a form. The first row is the only place cheque 4417 survives, and it is pruned on schedule with every other row — ruled 23 Sep, no row type exempt. The Correct-reference screen says nothing about it; this report shows the oldest date it holds."* | **LAW** — hard rule 4's retention clause (`OQ-1340` CLOSED 2026-09-23) **and** B14 rule 33 (rationale is zero words on screen). ⚠ **It states the Correct-reference screen correctly:** `CorrectionRetentionNote` was **deleted**, not reworded, by `P3.18` |
| R36 | `access_review` | Access Review | Compliance › Audit | `audit_log` | As at | USER · ROLE · ADDED · ADDED BY · LAST SIGN-IN · APPROVE MONEY · STATUS | *"Ten staff is the whole ICP, so this is nine rows and not a paginated list — and it is still served paginated, because `NFR-3` admits no exceptions and the four places that claimed one are the defect `DEF-PAY-4221` exists to close."* | **LAW** — `NFR-3` + `BR-REP-023` (System Admin + Executive only, **enforced since 2026-09-27** by `apps/reports/role_gate.py` — see BR-REP-023's own row; the check is on the DEFINITION and not in this dataset's query, so the next restricted report needs no new code). ⚠ **"the four places" is now five** — `DEF-REP-6827` |
| R37 | `rate_change_history` | Rate Change History | Compliance › Changes | `rate_schedules` | Effective date | EFFECTIVE · SCHEDULE · SERVICE · COMPONENT · WAS · NOW · CHANGE · BY | *"Rates show four decimals and percentages six, displayed at the precision the rule stores — hard rule 2, and the one report where trimming to two decimals would misstate a tariff. The future-dated row is why the effective date, not the entry date, is this report's basis."* | ⚠ **SPLIT.** **Rate half = LAW** — `OQ-620(a)`, CLOSED 2026-08-27, PO verbatim *"Four ($0.1420). A rate is not money and not a quantity"*. **Percent half = DEFECT** `DEF-REP-6829` — `BR-RAT-087` (PO 2026-08-20, built) and hard rule 2 both say **DISPLAY 2**. **Basis half = LAW**, `BR-REP-001`. Report column set is unratified per `BR-REP-021` |
| R38 | `adjustment_register` | Adjustment Register | Compliance › Changes | `invoices` | Posting date | DATE · REFERENCE · ACCOUNT · REASON · AMOUNT · RAISED BY · APPROVED BY · INVOICE | *"The second row's approver is an em-dash and that is lawful — it is under the tenant's threshold. The third row is self-approved, which the register shows rather than hides; whether that is allowed is the tenant's rule and this report is the evidence an auditor reads."* | **TEST** (no query) — *shows rather than hides* is the assertion, and it is the opposite of what a tidy implementation does |
| R39 | `regulatory_filing` | Regulatory Filing | Compliance › Filings | `journal_lines` | Period | SECTION · LINE · MEASURE · VALUE · UNIT · SOURCE | *"Line 4.1 states **not available** instead of zero, and that is the whole design. A filing that prints 0 for a figure the platform cannot derive is a false statement to a regulator; a stated absence is honest and tells the filer exactly what to supply by hand."* | **LAW** — `BR-REP-024`/`032`'s never-0 rule, and the repo's standing seam rule (*never answer 0 when the honest answer is "I could not"*). **TEST owed** with the query |
| R40 | `external_reconciliation` | External Reconciliation | Compliance › Filings | `journal_lines` | Posting date | MEASURE · OURS · THEIRS · DIFFERENCE · IN TRANSIT · RESULT | *"A difference with an equal in-transit figure reads **Explained**, not **Agrees** — two different facts, and collapsing them into one green pill is how a real break gets missed for a month."* | **TEST** (no query) — two facts, one pill: a check asserting only *"green"* is exactly the false pass this warns about |
| R41 | `migration_assurance` | Migration Assurance | Compliance › Filings | `accounts` | As at | CHECK · LEGACY · LOADED · DIFFERENCE · TOLERANCE · RESULT | *"Tolerance is zero for money and counts, and stated for history. The sixteen missing read rows are the legacy system's own duplicates, which is why this report keeps a tolerance column instead of going red — but a money tolerance above zero would make the report worthless, so it is **fixed at zero and not configurable**."* | **TEST** (no query) — ⚠ *not configurable* is a **negative** requirement, and `NFR-5`'s shape: nobody may add the setting later |

### The column-set question, for the Product Owner

**Phase 0 seeded no `columns` on any of the 46 and that reasoning is sound** —
`0003_seed_catalogue.py`'s own docstring: the drawn sets are *"a screen's four-of-seven
choice rather than a ratified list"*, `BR-REP-021` already names five reports as
column-unratified, and inventing 46 lists would be the seeder choosing, which spec rule 7
forbids. **Nothing above overturns it and nothing here is seeded.** What this section adds
is the **size of the gap**, so the question can be put with figures rather than adjectives:

* **48 of 51 drawings** show a different number of columns from the dataset their definition
  names. Only **R17**, **R18** and **R43** agree.
* **16 drawings share no column at all** with their dataset — those reports are aggregates
  and no column list can serve them; they need a **query**.
* The widest are **R1 Payments** (5 drawn, 19 declared), then **R2**, **R14** and **R19**
  (6 drawn, 19 declared).
* The practical consequence, stated plainly: **a clerk opening any of these 45 today would
  see columns the drawing does not draw**, and on sixteen of them would see a different
  table entirely.

### Cross-check: every R-row's dataset

**All 46 resolve** to one of the nine declared in `apps/reports/datasets.py`, and
`test_p0_6__every_definition_names_one_of_the_nine_datasets` already asserts it — this lane
confirms an existing guard rather than adding one.

⚠ **But the DRAWINGS name a composite source in 12 places and the definition holds exactly
one dataset**, which is a difference no check can see: R4 is drawn *"bills + reads"* and
seeded `invoices`; R32 *"jobs + meter reads"* → `meter_reads`; R36 *"identity + audit"* →
`audit_log`; R8 *"notifications"* → `audit_log`; R39 *"journal lines + accounts + reads"* →
`journal_lines`. **Two drawn source words are not datasets at all** — `jobs` (which §05 and
`datasets.py` both say is the export pipeline's table, deliberately not a report dataset)
and `identity` (a set of ATTRIBUTES on the audit dataset). That is the same document
miscount already filed as `DEF-REP-6797` (nine datasets stated four times, ten owners
listed), seen from the drawings' end, and **no new defect is filed for it**.


## BR-REP-036 — THE SIX ON `meter_reads`, AND WHICH THREE STATE ITS GRAIN (lane DS-METER, 2026-09-27)

**CONFIRMED-AS-BUILT.** `apps/metering/meter_reads_dataset.py` is the query; its
grain is **one committed lineage head** (BR-MET-016/053). The six definitions
`reports/0003_seed_catalogue.py` puts on this dataset were read AS IMAGES per
B14 rule 42 (brief p061–p065 at scale 4) and split three and three.

| id | key | what ONE ROW is, from the drawing | verdict |
|---|---|---|---|
| R45 | `my_usage` | one read, per period, per service, for the signed-in account | **SERVED** — `portal_usage()` |
| R29 | `consumption_exceptions` | one read that tripped a validation rule | **SERVED** — `meter_reads_dataset(flagged_only=True)` |
| R30 | `usage_and_ranking` | one **account**, ranked by usage | **GROUPED** — `account_usage_ranking()`; 7 of 8 drawn columns, `BILLED` is money from `billing` and is served `None` with a reason (BR-REP-024) |
| R28 | `read_completeness` | one **route** | **REFUSED BY NAME** |
| R32 | `read_import_log` | one **import** | **REFUSED BY NAME** |
| R46 | `bill_projection` | one projected **charge component** | **REFUSED BY NAME** |

The three refusal sentences live in `METER_READS_DEFINITIONS_NOT_SERVED` in the
dataset module — beside the query, so the lane that knows why a report is
refused is the lane that writes the refusal — and are asserted in BOTH
directions by `test_the_three_refusals_name_the_reports_and_nothing_else` and
`test_every_seeded_definition_is_either_served_or_refused_by_name`. A seventh
definition arriving on this dataset turns those red.

**R28's reason is its DENOMINATOR and it generalises.** `EXPECTED` is a count of
reads that did not happen, and a read that did not happen has no row in
`meter_reads`. This is the sharpest case of the overlap-zero finding recorded
above: those sixteen drawings *"need a query, not a ratified column set"*, and
for R28 the query is not over this fact at all. The arithmetic already exists as
`apps/metering/completeness.py::cycle_coverage`, whose expected set walks
`assets → service_points.cycle_id` through `PlanRegisterResolver` to each unit's
rate plan.

**R28's warning is a design rule, not a live defect — checked rather than
assumed.** `cycle_coverage` reports per CYCLE with no route breakdown and no
reader column, so nothing shipped conflates a scheduling gap with a read gap
today. The fact an R28 lane needs exists: `metering.models.Route.assigned_to`,
whose own comment reads *"NULL = System (auto-pull)"*. Render that NULL as
*Unassigned*; never as a gap.

**R32's warning is about the WRITE path and it is obeyed.** `10-scripts/
ds_meter_reads_cost.py --savepoint-audit` finds the nested
`transaction.atomic()` around the `_post_row` call in `apps/metering/services.py`
and prints where. Proved RED first by deleting that one line: it exits 1.

**R30's warning is enforced structurally, not documented.** `account_usage_
ranking(service=…)` is keyword-only **with no default**, so a caller that omits
it raises `TypeError` at the call site. The row above marks this *"TEST owed:
a required parameter has no representation in the seeded row"* — it now has one
in the QUERY, which is the stronger place: a seeded parameter can be edited, a
missing default cannot be forgotten.

**Hard rule 3 is a refusal, not a sentence.** `consumption_total()` counts the
distinct units in the SAME aggregate call as the sum and returns
`total=None` + `consumption_spans_more_than_one_unit` where the set spans more
than one. Measured on PostgreSQL 16 over a set holding `gal`, `kWh` and `kgal`:
refused; the same set narrowed to one unit returned **1,500 rows totalling
15,000.000000 gal**. Both halves are asserted, because a refusal that is really
*"always None"* is not a refusal. This is §7.2.2's `ADD_WITHIN_SERVICE`
declaration made to bite, and it is why `METER_READS` declares
`completeness_pct` as `ADD_NON` — R28's `COMPLETE` is a ratio and may never be
averaged across routes.

**MEASURED ON PostgreSQL 16, 40,201 reads in one tenant** (`10-scripts/
ds_meter_reads_cost.py`, median of 3 after a discarded warm-up): page 1 of 50
**0.054s / 4 statements**; the LAST page (805) **0.129s**; the R30 ranking
**0.286s**; R45 scoped to one account **0.022s**; the whole set streamed
**40,201 rows in 3.791s**. The last page is never slower than the first, which
is what distinguishes a SQL `OFFSET` walk from a Python slice over everything.

⚠ **`select_related` ON THIS TABLE DEFEATS THE `LIMIT` AND COST 7×, AND THAT IS
A FINDING FOR EVERY FUTURE READ OF `meter_reads`.** The table is PARTITIONED
MONTHLY on `read_at` (BR-MET-055) — 28 partitions on the proof clone — and the
planner joins the whole partitioned parent to `assets` and `accounts` before it
cuts a page: `0.345s` with the join against `0.011s` without it, for the same
fifty rows. Labels are resolved AFTER the page in two `IN (…)` reads bounded by
`per`. **A future read of this table that reaches for `select_related` is
reaching for the slow path.**

⚠ **NOT BUILT, AND NAMED SO IT IS NOT MISTAKEN FOR AN OMISSION.** R45's drawn
`NEIGHBOURHOOD AVERAGE` tile (p061, `152 gal`) is a deliberate cross-account
aggregate on a **customer-portal** screen. It is not served by `portal_usage()`.

⚠⚠ **RULED 2026-09-27 — THIS PARAGRAPH SAID *"no floor has been decided"* AND A
FLOOR IS NOW DECIDED.** PO verbatim, choosing option (a) of three put to them:
*"(a) with a floor of at least ten homes, and the tile simply absent below that,
saying nothing about why"*. **`BR-REP-037`:**

| | |
|---|---|
| Show the tile | only when the comparison group holds **at least 10 other homes** |
| Below 10 | the tile is **ABSENT** — not a dash, not a zero, not a placeholder |
| What the screen says about the absence | **NOTHING** — no sentence, no tooltip |
| The customer's own figure | always shown; it is their own data |

**The silence is part of the ruling, and B14 rule 33 already required it** —
rationale is ZERO WORDS ON SCREEN. It is also the safer build: *"too few homes
nearby to compare"* is itself a fact about the neighbourhood, and on a short
street it tells the reader something the tile was withheld to protect.

**The worked case the floor exists for:** a cul-de-sac of three houses. Alia
sees her own `137 gal` beside an average of `152 gal` over two neighbours, one
of whom she knows is away at near zero — so the third home's usage falls out in
one subtraction. At ten homes that subtraction stops being possible from one
known figure.

**Still not built** — this rule is the authority to build it, not a claim that
it exists. The ruling is `12-governance/02-decision-log.md`, 2026-09-27.

## BR-REP-038 · A customer statement is the account's running record, like a bank statement

**CONFIRMED 2026-09-27 by PO ruling.** Verbatim: *"it should be like bank
statement. this si correct - Build it on the ledger — the account's running
record, which holds both sides."*

| | |
|---|---|
| Built on | the **ledger** (`journal_lines`) — never invoices |
| One row is | one posting against the account |
| What it shows | an opening balance · every charge and every payment in date order · a closing balance |
| Why not invoices | invoices are charges, so a statement built on them cannot show a payment at all; its closing balance could only ever be the sum of what was billed |

**The worked case shown to the PO:** Dana opens Alia's statement for September.
It must show the September bill of `$84.20`, the payment of `$84.20` on the
14th, and the balance carried forward. On the invoice reading it shows what she
owed and never what she paid.

⚠ **`reports/0003_seed_catalogue.py` SEEDS `R24 statement` ON `invoices` AND
THAT SEED IS NOW WRONG.** Moving it is a migration and lands with the work. It
unblocks `CR-142-BRC07` `P2.8`, `P2.15` and `P2.16` — Phase 2's last three
tasks — and relates to `DEF-REP-6859`.

⚠ **`R44 My Bills & Payments` IS SEEDED ON `invoices` TOO AND IS NOT RULED BY
THIS.** Its drawn name promises both sides in the same way. **Measure whether it
can show a payment today and report the answer**; a defect and a one-line
question to the PO, never a value chosen by a lane. `R25 account_ledger` is
already on `journal_lines` and is untouched.

The ruling with its full reasoning is `12-governance/02-decision-log.md`,
2026-09-27.

### BUILT 2026-09-27 (lane REP-P2-LAST) — and what is still NOT built

⚠ **THE THREE WARNINGS ABOVE HAVE EACH BEEN ACTED ON, AND TWO OF THEM CHANGED
STATE. Read this block before citing one of them.**

| | state now |
|---|---|
| the seed on `invoices` | **MOVED.** `reports/0007_br_rep_038_statement_on_ledger.py` puts the platform `statement` row on `journal_lines` and its stored basis on `posting` / *Posting date*. A MIGRATION, not an edit — `0003` has already run everywhere. `HUMAN-REVIEW-PENDING`, row in `12-governance/09-human-review-ledger.md` |
| the report itself | **BUILT.** `apps/reports/statement.py`, out of `apps.ledger.reporting.account_ledger` through the existing seam. It computes no money and writes no journal line (hard rule 5) |
| the worked case | **PROVED.** `06-backend/tests/test_br_rep_038_statement.py` — the `$84.20` bill, the `$84.20` payment on the 14th, opening `0.000000`, closing `0.000000` struck as `opening + charges − payments` |
| `R44 My Bills & Payments` | **MEASURED AND NOT MOVED.** It **cannot show a payment today** — it refuses by name with the invoices dataset's own sentence. `DEF-REP-6909`, OPEN, one question for the PO |
| `R25 account_ledger` | **STILL UNSERVABLE.** Untouched, as this rule says |

⚠ **THE BASIS MOVED WITH THE DATASET AND THAT IS A CONSEQUENCE OF THIS RULE,
NOT A SECOND RULING.** `0003` seeded R24 at the **EVENT** basis labelled
*Statement date*. Every figure on the ledger reading is struck on
`journal_entries.entry_date`, the BOOK date. The `journal_lines` dataset already
refuses `regulatory_filing` over the opposite mismatch, and `BR-REP-001` exists
so a money report cannot state the wrong basis — so a statement claiming
`event` over posting-dated rows would have repeated that defect rather than
avoided it. Decision log, 2026-09-27.

⚠ **ONLY ONE OF THE FOUR SUBJECTS IS SERVED, AND THE OTHER THREE REFUSE BY
NAME.** The ledger publishes a running record for an ACCOUNT. `customer`,
`premises` and `unit` each raise `DatasetCannotServe` with their own sentence
rather than falling back — a fall-back would print one account's money under a
person's, a building's or a unit's heading. **`P2.15` is the `unit` one and it
needs a ledger read model, not a screen.**

## BR-REP-039 · Disconnect & Reconnect is one row per ACCOUNT

**CONFIRMED 2026-09-27 by PO ruling** (option (a) of two). One row is one
account, showing its **latest** disconnect case; earlier cases are available
underneath, never as sibling rows. The balance column then foots honestly.

**The worked case shown to the PO:** Alia is cut off on 3 June for `$210` and
restored on the 11th; cut off again on 9 September for `$185`. One row per case
would total `$395` — money she never owed at once.

⚠ **The spine is `customers.disconnect_cases`, not `work_orders`.** The earlier
refusal on `work_orders` stands as a statement about that dataset and is
superseded as a statement about this report.

### BUILT AND MEASURED 2026-09-27 (lane REP-P6-W2, `2.378.0`)

**BUILT.** `06-backend/apps/customers/disconnect_reconnect.py`, reached through
`apps/reports/report_seams.py` and registered as a per-KEY viewer in
`queries.VIEWERS` — so `runner.queries_for` finds it BEFORE the dataset, which
is the only way a report is served at a grain its own dataset refuses.

⚠ **`apps/work/work_orders_dataset.GAP_R34_IS_A_DIFFERENT_GRAIN` STAYS AS IT
IS.** It is right about THAT dataset — an account cut and restored inside the
window has two orders — and this rule supersedes it only as a statement about
the REPORT. A refusal deleted the day its read model lands is a refusal nobody
can read when the wiring rots.

**THE LATEST CASE IS PICKED IN SQL BY A CORRELATED `Subquery`, NOT
`DISTINCT ON`.** The suite runs on in-memory SQLite (hard-won law 14) where
`DISTINCT ON` does not exist, and Django forbids ordering a
`distinct('account_id')` queryset by anything that does not start with that
field — which is every sort this report offers. The subquery's order is TOTAL
(`-opened_on, -created_at, -id`), because two cases opened on one day would
otherwise make *latest* a coin toss and a coin toss decides which BALANCE an
account contributes. **The window is applied INSIDE the subquery as well as
outside**, so the tiles and the rows describe one population.

**MEASURED ON REAL PostgreSQL 16** (`10-scripts/p6w2_cost.py`, median of 3 after
a discarded warm-up, `DEBUG` off, tenant `perf-utility-95` holding **40,000
accounts and 53,332 disconnect cases** — cases EXCEED accounts on purpose, and
the script REFUSES a fixture where they do not, because this rule is only about
accounts with more than one case and a one-case-each fixture would let a
per-CASE query pass every figure below):

| | |
|---|---|
| page 1 of 50 | **1.879s** · 6 statements · 50 rows |
| page 800, the LAST, of 50 | **2.412s** · 6 statements · 50 rows |
| last page ÷ first page | **1.28×** |
| page 1 of 200 | 2.398s · **6 statements** — the count does NOT move with `per`, so the label reads are batched and there is no N+1 |
| sort `account_no` asc / desc | 1.405s / 1.239s, opening at `A-10432` and `P6W2-0039999` — they REVERSE, so the sort is not a Python sort of a page |
| export, the WHOLE filtered set | **48.708s** · 81 statements · **40,000 rows** |

⚠ **THE EXPORT IS 48.708s AGAINST A 60-SECOND WORKER** (`docker-entrypoint.sh`,
`GUNICORN_TIMEOUT:-60`) — **1.23× inside it, and that is the narrowest margin
this phase has measured.** It is stated rather than averaged away: it is a
generator that never holds a row, `NFR-5` forbids a ceiling on it, and the
number is published here so the next lane sees the margin rather than
rediscovering it. A tenant materially above 40,000 accounts — which is above the
whole ICP — would not answer.

**THE TILES FOOT TO THE WHOLE FILTERED SET AND NOT TO THE PAGE**, proved by
comparing `totals` on page 1 against page 2 rather than by reading the code:
`accounts 40,000 · owed $8,191,283.10 · notices_sent 10,003 · disconnected
29,997`, identical on both.

**ISOLATION** (`10-scripts/p6w2_rls_proof.py`): `disconnect_cases` carries
ENABLE and FORCE, probed as a role that is neither SUPERUSER nor BYPASSRLS, with
the neighbour's row PLANTED and **proved visible from the neighbour's own
context first** so the probe cannot be measuring an empty table, and my own
count asserted non-zero so a zero beside a zero cannot read as isolation. It
does NOT re-prove `accounts`, which R34 joins — `10-scripts/rep_ds_accounts_rls_proof.py`
covers that one, and a proof naming one table is a claim about one table.

**TESTS.** `06-backend/tests/test_rep_p6w2_disconnect_reconnect.py`, 7 of 7 —
Alia's `$185.00` asserted and `$395.00` refused by name, the tile footing to the
rows with a page cut, `ELIGIBLE` and `PAID` NULL with their reasons and never 0,
the page and the stream serving the same rows in the same order, both sort
directions reversing at both ends, the `work_orders` refusal still standing, and
the Download button having a registered resource to post to.

## BR-REP-040 · Plans & Discounts is one report, and its last page costs more

**CONFIRMED 2026-09-27 by PO ruling** (option (a) of two). One row is one
**enrolment** — account × programme. The three programmes live in three modules
(`billing.account_budget_status`, `payments.payment_plans`,
`rating.discount_enrolments`), so it is served as a k-way merge of three
SQL-sorted, SQL-limited streams, each fetching `offset + per` rows.

⚠ **A NAMED, RULED EXCEPTION to this phase's *the last page is not slower than
the first*, and to nothing else.** `NFR-3` and `NFR-5` are untouched: no Python
slice, no unpaginated read, no cap. Publish the measured cost here. Revisit if a
tenant's enrolments reach the tens of thousands. **Splitting the report is
refused** — the drawing forbids it.

⚠ The drawn `ENROLLED 318 / 16.3%` tile **mixes units**: 318 is enrolments,
16.3% is over accounts. Label each for what it is.

## BR-REP-041 · Bill Run Readiness reads the latest PREPARED RUN for the cycle

**CONFIRMED 2026-09-27 by PO ruling** (option (a) of two). The report is opened
for a **cycle**; readiness belongs to a **run**. It shows the latest prepared
run for that cycle, and where none exists it **states the absence** — *"No bill
run prepared for this cycle"*. Nothing is substituted: no empty table reading as
a clean result, no invented run.

## BR-REP-042 · The bill projection carries ± 15% of the USAGE part only

**CONFIRMED 2026-09-27 by PO ruling**, verbatim: *"Set a percentage — say ±15% —
applied to the usage part only, never to fixed charges"*.

| | |
|---|---|
| Range | **± 15%** |
| Applied to | the **usage-driven** part of the projection only |
| Never applied to | fixed charges — base, capacity, fire, any flat monthly amount |
| Shown range | `0.15 × projected usage charges`, never `0.15 × total` |

**Worked, and a test asserts it:** `$84.00` made of `$24.00` base and `$60.00`
usage carries **± `$9.00`**, not ± `$12.60`. The fixed `$24.00` is known exactly;
a range over it invents doubt the product does not have.

⚠ Customer-facing: **display two decimals** (hard rule 2), and **no rationale on
screen** (B14 rule 33) — the figure and its range, nothing about straight-lining.
⚠ The sewer row's drawn *"Winter average"* basis is a **second tenant rule, not
ruled here**. Stub and ask.

The rulings with their full reasoning are in `12-governance/02-decision-log.md`,
2026-09-27.

## BR-REP-043 · A statement is served for five subjects

**CONFIRMED 2026-09-27 by PO ruling.** Verbatim: *"we can do based on regualr
account, master account, premises, units, customer id ; then it resoleves your
questions"*, and on the unit specifically, asked again and answered again:
*"yes; i can generate statement for Unit"*.

The statement is the running record ruled in `BR-REP-038` — opening balance,
every charge and payment in date order, closing balance, built on the **ledger**.
This rule settles **whose** record it is. The subject scopes the SET; the grain
of a row does not change.

| subject | the set is |
|---|---|
| regular account | one account's postings |
| master account | the master and what it covers |
| premises | every account at that address |
| **unit** | one unit, across tenancies |
| customer | every account that customer holds |

⚠ **The UNIT subject needs a running-record read model in `apps/ledger` that no
seam publishes today.** `CR-142-BRC07` `P2.15` files it as a Front-end task; it
is a ledger task. That is the build.

⚠ **A unit outlives its tenants.** A statement spanning a move-out **names both
occupants**, and an Occupant column appears on this subject and no other. A unit
declares no address of its own (hard rule 8): the head reads the premises
address plus the unit label.

⚠ **The CUSTOMER subject must keep the guard that already exists** —
`CustomerStatementPage.tsx`'s `held_with` check stops a stranger's arrears
appearing on this person's statement, and its absent-figure is reasoned on the
server. `P2.16` says to keep those careful parts.

⚠ **No screen is deleted before its subject serves rows.** The old addresses are
bookmarked and linked from Finance; `P2.8` says keep them. Serve the subject,
prove it in a browser, then retire and redirect. A redirect to a subject that
refuses is the dead-control failure this repo files most.

The ruling with its worked cases is `12-governance/02-decision-log.md`,
2026-09-27.

## BR-REP-044 · The Delivery settings card is a LINK, not a list

**CONFIRMED 2026-09-27 by PO ruling** — option (a) of two, answered *"a"*.

**The question put to them, with its worked case:** the card is drawn as a list
of where schedules send their files. Recipients are stored **per schedule**,
never per tenant — the AR ageing goes to Dana weekly, the cash report to the
finance officer monthly — so *"the utility's recipients"* is not a thing that
exists. Option (b) was a tenant-level recipient list, which is a new table, and
Phase 5's own task mix declares **0 DB**.

**Ruled: the card LINKS to screen `4·1 Scheduled`**, where recipients actually
live. It duplicates nothing and it points at the truth.

⚠ **A `link` card, not a `rules` card**, and it must not be declared with
`arrivesWithKey` — a "coming soon" card with no dated owner is law 2's mirror
with better manners. `referenceDataConfig.ts` already carries the link shape.

This closes `CR-142-BRC07` `P5.5`'s fourth card. The ruling and the packet are
`CR-142-BRC07` §14.5 and `12-governance/02-decision-log.md`, 2026-09-27.

## BR-REP-045 · A manufacturer is data, never vocabulary

**CONFIRMED 2026-09-27 by PO ruling** (option (a) of two, answered *"a"*).

A brand name — `Itron`, `Sensus` — **never enters a translatable value**.
Translate the words (the reading method); render the manufacturer beside them as
data. `DEF-REP-6931` is the instance: `AMI · Itron` and `AMI · Sensus` read
identically in all eleven languages, correctly, and the translation check counts
them as untranslated.

⚠ **The rejected option is why this is a rule and not a fix.** Adding the two
values to the check's hand-curated exception list needs somebody to remember to
edit it the day a utility buys from a third manufacturer, and nothing would
remind them.

Ruling: `12-governance/02-decision-log.md`, 2026-09-27.

## BR-REP-050 · Trend Pack is one row per FISCAL PERIOD, and it has no Total row

⚠ **THIS IS A LANE DERIVATION FROM THE DRAWING, NOT A PO RULING.** `BR-REP-039`
to `BR-REP-042` were ruled by the Product Owner on 2026-09-27 and R43 was not
among them — it was not on the agenda, because nobody had yet noticed that the
report was being SERVED. Nothing here supersedes a signed statement, so under
hard-won law 13 it is DECIDED and WRITTEN DOWN rather than asked: the grain is
what p059 draws, the arithmetic is `BR-REP-009`'s and `BR-REP-011`'s word for
word, and the one absence a signature does not cover is named below.

**One row is one fiscal period.** p059 draws `P10 · Jul`, `P11 · Aug`,
`P12 · Sep` under a **Periods 12** control, with eight columns — PERIOD ·
REVENUE · TARGET · COLLECTED · RATE · DSO · ACCOUNTS · REBILLS — and **no Total
row**.

⚠ **THE MISSING TOTAL IS THE DRAWING BEING RIGHT, NOT THE DRAWING BEING
INCOMPLETE**, and it is written down here because the next lane's instinct will
be to add one. Three of the eight columns cannot lawfully be summed, each for a
different reason: RATE and DSO are **ratios**; ACCOUNTS is **as-of**, so the
same account is counted in all twelve rows and a column sum reports a utility
twelve times its own size; TARGET is **per period**, so adding twelve monthly
targets produces an annual one nobody typed. REVENUE, COLLECTED and REBILLS are
additive — and a footer carrying three figures under a table of eight, with the
other five blank or wrong, is worse than no footer.

⚠ **THE `· Jul` HALF OF THE DRAWN LABEL IS NOT COMPOSED ON THE SERVER.** The
column carries `P10`, a fiscal ordinal, with `period_start` and `period_end`
beside it. B14 rule 35 puts a catalogue in its own language rather than
translated from English, and a server emitting `Jul` would have decided for
eleven of them.

### WHAT WAS THERE BEFORE — `DEF-REP-6937`, live on 2026-09-27

`runner.run('trend_pack')` returned **one row per JOURNAL LINE** — posting date,
account code, debit, credit — **under the title *Trend Pack***, to a clerk. R42
Operational Dashboard, its neighbour in the same section, on the same dataset,
with the same by-period shape, was refused by name; R43 was not, because
`queries.JOURNAL_LINES_DEFINITIONS_NOT_SERVED` was missing one key. **A key
missing from a hand-kept map is indistinguishable from a deliberately absent
one** — every gate passed, the rows were real and the footer footed. That is
hard-won law 7's *looking at the wrong thing*.

⚠ **THE REFUSAL IS NOW IN THE MAP AND STAYS THERE.** `runner.queries_for` and
`definition_refusal` both check `VIEWERS` first, so the per-key viewer bypasses
it without deleting a sentence that is still true of the DATASET — `BR-REP-039`
set that precedent with `work_orders_dataset.GAP_R34_IS_A_DIFFERENT_GRAIN`, and
a refusal deleted the day its read model lands is a refusal nobody can read when
the wiring rots.

### THE FOUR AGGREGATES AND THE TWO RATIOS

| column | what it is | basis |
|---|---|---|
| REVENUE | billed in the period — debits to the designated AR account from a bill source | POSTING |
| TARGET | `BR-REP-034`'s **typed** per-tenant figure | — |
| COLLECTED | **cash APPLIED to bills issued in that period**, `BR-REP-009`'s numerator | POSTING |
| RATE | COLLECTED ÷ REVENUE × 100, six decimals stored, two displayed | — |
| DSO | (AR at the period end ÷ billed in the twelve months ending there) × 365, `BR-REP-011` | POSTING |
| ACCOUNTS | R22 Account Census's own as-at membership rule, at the period end | as at |
| REBILLS | `invoices.bill_type='rebill'` issued in the period | **ISSUE** |

⚠ **REBILLS IS DATED BY ISSUE WHILE THE MONEY IS DATED BY POSTING, AND THE
REPORT SAYS SO** — `rebills_basis` travels on the wire. `BR-REP-001` governs what
basis a MONEY figure states; this is a count of an ACT, and the act is the
issue. `BR-REP-003` is explicit that unlabelled money is a contract failure, and
the same courtesy costs one key here.

⚠ **COLLECTED CLOSES `apps/ledger/reporting.GAP_ALLOCATION_PERIOD` FOR THIS
REPORT AND FOR NOTHING ELSE.** That gap has said since August that BR-REP-009's
percentage *"is not derivable"* from the books — true, and still true: a journal
entry credits AR in one lump with `source_id` = the payment and never records
WHICH bill the cash met. It named its own remedy in its `wanted_reads`, and
`apps.payments.selectors.allocated_to_invoices_issued_between` is now that read,
exactly as named. **`revenue_and_ar`'s `collection_pct` is UNCHANGED and still
answers `None`** — moving a shipped KPI on S36 from *absent with a reason* to a
number belongs to that screen's owner, not to a report lane passing through.

### THE THREE ABSENCES, AND WHY EACH IS THE STATE PROVED FIRST

**TARGET is NULL on every tenant that exists.** `BR-REP-034`, PO ruling
2026-08-18 option B: *"With no target typed, the tile degrades to … the figure
alone, no sub-line."* Nothing publishes `monthly_revenue_target`, so this is the
default rather than an edge case, and REVENUE VS TARGET carries the reason with
the revenue figure still beside it.

⚠ **AND TARGET IS NULL A SECOND WAY, FOR A DIFFERENT REASON — `BR-REP-034`
SIGNED A *MONTHLY* TARGET AND THIS DRAWS ONE PER ACCOUNTING PERIOD.** On a
tenant closing monthly they are the same figure; on one whose `close_cadence` is
QUARTERLY they are not, and a quarter's revenue against a monthly target reads
as about **300% of target**. That sits inside `BR-REP-034`'s own *"what the
signature does not cover"* clause, which already names three uncovered questions
and now names a fourth. **The report does not divide or multiply by anything**:
a quarterly tenant gets NULL with `a_monthly_target_does_not_price_a_quarterly_period`.
The two absences are DIFFERENT sentences on purpose — collapsing them would tell
a quarterly utility that had typed a target that they had not.

**DSO is NULL until twelve months of books exist**, `BR-REP-011`, and
`apps/ledger/reporting.py` had already made this call in its own words: a DSO
computed on three months and labelled as twelve *"reads as a collections crisis
that is not happening"*. R43 answers it per ROW, so the periods that can carry
the figure carry it.

**RATE is NULL rather than 0% in a period that billed nothing.** A zero
denominator makes the ratio undefined, and 0% on a quiet month reads as a
collections failure that did not happen.

### BUILT AND MEASURED 2026-09-27 (lane REP-P6-W3, `2.382.0`)

**BUILT.** `06-backend/apps/ledger/trend_pack.py`, reached through
`apps/reports/report_seams.py` and registered as a per-KEY viewer in
`queries.VIEWERS` and a per-KEY stream in `queries.KEY_STREAMS`. Four cross-
module reads, one seam file each: `tenancy_seam` (the fiscal calendar, the typed
target, the DSO target), `payments_seam` (cash applied), `billing_seam`
(rebills), `dimension_seam` (accounts on the books). **The fiscal calendar is
WALKED, not selected** — `BR-TEN-022` makes the period card a computation over
the fiscal-year fields and there is no periods table — by asking tenancy for the
period containing the day before each start, with a floor that ends the walk the
moment a step does not go backwards.

**MEASURED ON REAL PostgreSQL 16** (`10-scripts/p6w3_cost.py`, median of 3 after
a discarded warm-up, `DEBUG` off, tenant `perf-utility-95` holding **40,000
accounts and 1,620 journal lines over 14 months**):

| | |
|---|---|
| 1 period | **0.090s** · 18 statements · 1 row |
| **12 periods — the drawn default** | **0.633s** · **77 statements** · 12 rows |
| 60 periods (five years) | 2.838s · 317 statements · 60 rows |
| 12 periods through `runner.run()` | 0.595s · 79 statements |
| export — every row | **0.569s** · 77 statements · 12 rows |
| statements per period | **5.4** |

⚠ **THIS REPORT IS BOUNDED BY A CONTROL AND NOT BY THE TENANT**, which is why
there is no `page` block on the wire and why `NFR-3` is satisfied rather than
dodged: twelve rows at a 40,000-account utility and twelve at a 300-account one.
What DOES grow with the tenant is the cost of each ROW, and it grows linearly in
the period count — 5.4 statements per period, so sixty periods is 317
statements and 2.838s. **The export is 0.569s against `docker-entrypoint.sh`'s
60-second `GUNICORN_TIMEOUT`, which is 105× inside it** — not the narrow margin
`BR-REP-039`'s 48.708s records, and stated so the two are not confused.

⚠ **WHAT THE MEASUREMENT DOES NOT COVER, PRINTED BY THE SCRIPT ITSELF** (law 7's
fifth shape): only **2 of 12** periods carry a non-zero COLLECTED on that
fixture, so the allocation subquery was timed over a mostly-empty match — the
timing is real and the SELECTIVITY is not; and **40 fixture entries were refused
because they fell inside a CLOSED fiscal period** (`BR-LED-006`), which the
script skips and counts rather than forwarding, because forwarding would pile
fourteen months into one row and measure the wrong report.

## BR-REP-060 · R4's ROUTE and USAGE columns are served EMPTY with their reason, and neither gets a filter

**DECIDED 2026-09-27 by lane REP-P6-W4 and written down rather than asked**
(hard-won law 13 — a judgment call recorded with its reasoning is the
deliverable; a question is the failure to make one). It supersedes no signed
statement and chooses no value: the value it would have had to choose is minted
as `OQ-REP-12768` instead.

p049 draws six columns — ACCOUNT · CUSTOMER · ROUTE · CHECK · DETAIL · USAGE —
and a **Route** parameter beside Cycle and Check. **Two of the six cannot be
filled and the Route parameter must not be offered.**

### Why, and it is ONE reason rather than two

⚠ **AN ACCOUNT HAS NO SINGLE ROUTE AND NO SINGLE USAGE FIGURE, AND THE PRODUCT
SAYS SO IN ITS OWN WORDS.** `metering.RouteMembership`'s docstring: *"CR-006
gives a route one [service], and a house on water AND gas is on two routes"*.
The table carries two partial unique constraints precisely so it can. So
*which route is this account on* has no answer for a multi-service account —
it has **one answer per service** — and the drawing's single ROUTE cell is only
right for a utility that sells one thing.

**USAGE fails identically and for the identical reason.** Hard rule 3 puts an
explicit unit on every consumption figure, and the brief's own p062 note says
quantities *"are never summed across services, because gallons plus kilowatt-
hours is not a number"*. A single USAGE cell on an account taking water and gas
is that sum.

⚠ **SO THIS IS NOT *THE READ IS MISSING*.** Wave 3's handover recorded that no
read answers it — true, and `customers.accounts_dataset` refuses a `route`
filter in as many words. But building the read would not fix it: it would force
a lane to decide **which service's route wins**, and that is a product decision
nobody has made. **B14 rule 37 settles the drawing's side of it** — a figure
drawn in a wireframe is an ILLUSTRATION, never a fact to build to — so `R-01`
beside `14,900 gal` is a single-service illustration and not a specification.

### What is built

| | |
|---|---|
| ROUTE column | **DRAWN, and NULL on every row**, carrying `route_is_not_single_valued_per_account` |
| USAGE column | **DRAWN, and NULL on every row**, carrying `usage_is_not_summable_across_services` |
| Route **filter** | **NOT OFFERED** |
| Usage sort | **NOT OFFERED** |

The columns stay because `BR-REP-024` keeps a drawn figure and states its
absence rather than deleting the column — the same posture `BR-REP-039` gives
R34's `paid` and `BR-REP-050` gives R43's `target`. **The FILTER goes**, because
a filter over a column that is NULL on every row is a live control that cannot
work — hard-won law 2's mirror, on a brand-new screen. A dead chip is worse than
a missing one: it tells a clerk the product can answer a question it cannot.

⚠ **THE TWO HALVES ARE DELIBERATELY OPPOSITE AND THAT IS THE RULE'S POINT.** A
column that states its own absence is honest; a control that offers to act on
that absence is a lie. Anyone tempted to "finish" this by adding the chip
should read `OQ-REP-12768` first.

## BR-REP-061 · R4's HELD tile counts OUTSTANDING breaks, and the two tiles above it degrade

**DECIDED 2026-09-27 by lane REP-P6-W4**, under `BR-REP-041`'s ruled spine (the
latest PREPARED run for the cycle, the absence STATED where none exists).

p049's four tiles are ACCOUNTS IN CYCLE · READY TO BILL · HELD · NO READ.

| tile | from | when it cannot be produced |
|---|---|---|
| ACCOUNTS IN CYCLE | `bill_runs.findings_summary["accounts"]` | **NULL** with `findings_pass_has_not_run` |
| READY TO BILL | `findings_summary["ready"]`, with `ready ÷ accounts` as its sub-line | **NULL**, same reason |
| HELD | `bill_run_breaks` where `resolution IS NULL` | always produced |
| NO READ | those breaks whose `stage` is `measure-consumption` | always produced |

⚠ **HELD AND NO READ COME FROM THE DURABLE TABLE AND THE OTHER TWO DO NOT, AND
THAT ASYMMETRY IS THE HONEST ONE.** `bill_run_breaks` is persisted per (run,
account) — it is what survived the refresh that `selectors.prepared_for`, *"recomputed
on every call and cached nowhere"*, does not. `findings_summary` is written only
by the background findings job, so a run calculated inline has none, and the two
top tiles then read NULL with their reason rather than a plausible zero
(`BR-REP-024`). **A `0` in ACCOUNTS IN CYCLE would say the cycle is empty; the
truth is that nobody counted.**

⚠ **`resolution IS NULL` IS THE MODEL'S OWN VOCABULARY** — `BillRunBreak`'s
comment reads *"NULL = outstanding (BR-BIL-053)"*. A break a clerk has resolved
is not held, and counting it would put 49 on a screen whose whole purpose is the
twenty minutes before the run.

⚠ **NO READ IS COUNTED BY STAGE, NEVER BY A LIST OF REASON CODES.**
`runs.STAGE_BY_REASON` already maps every read-shaped failure —
`CALC_UNRESOLVED_READ`, `RUN_READS_UNAVAILABLE`, `RUN_ACCOUNT_HELD_BY_DISPUTE`,
`CALC_ASSET_COUNT_UNAVAILABLE` — onto `measure-consumption`, and a second
hand-kept list here would drift the day a reason moves stage. **That is exactly
how `DEF-REP-6937` happened**: a hand-kept map missing one key, indistinguishable
from a deliberate absence.

## BR-REP-062 · R46's projection is the RATING ENGINE fed a hypothetical, never a second pricing

**DECIDED 2026-09-27 by lane REP-P6-W4** and written down rather than asked
(hard-won law 13). It chooses no figure and supersedes no signed statement; it
records **how** `BR-REP-042`'s report must be assembled, and **why this lane
stopped short of assembling it.**

### The ruled arithmetic IS built

`06-backend/apps/rating/projection.py` holds `BR-REP-042` whole — the ± 15% band
over the usage part only, the straight-lining, and `OQ-REP-12769`'s stub — and
`tests/test_rep_p6w4_bill_projection.py` asserts it, including **both wrong
answers by name**.

### What is NOT built, and why it is a rule rather than a to-do

p062 draws four component rows carrying a RATE and a PROJECTED amount. Turning
an account into those four rows means resolving its plan, its tariff version in
force, the base-charge precedence (`BR-RAT-088`) and the usage rate — **which is
the rating engine.** ⚠ **A REPORT MAY NOT RE-DERIVE ANY OF IT.** A second
spelling of the base-charge precedence inside a report is hard-won law 5 on a
money path shown to a CUSTOMER, and the two figures would both be plausible
while neither screen showed the other.

**The right door already exists and is named here so the next lane does not go
looking for a different one:** `apps.rating.engine.price_period` is PURE — no
I/O, no clock, no writes — and takes `tariff`, `consumption`, `period`,
`account`. **A projection is that function fed a STRAIGHT-LINED consumption
instead of a measured one**, and its `PricedBill` already separates base charges
from usage lines, which is the split `BR-REP-042` turns on. So the projection
gets the engine's own arithmetic rather than a copy of it.

⚠ **WHAT IS MISSING IS THE GATHERING, AND IT IS BILLING'S.** Everything that
gets from *an account* to *a tariff* is `apps/billing/gather.py`, reached through
the bill-run prepare path — `selectors.prepared_for`, whose own docstring says it
*"reads meters, plans and accounts as they stand"*. That is a RUN path and not a
report read, and calling it from a viewer would make opening a customer-facing
projection cost a prepare pass.

**So R46 needs a gather seam that resolves ONE account's tariff for ONE period
without running a prepare**, and that is a wave of its own.

### Until it exists, R46 GOES ON REFUSING — deliberately

⚠ **R46 IS NOT REGISTERED IN `queries.VIEWERS` AND THAT IS THE RULE'S TEETH.**
`meter_reads_dataset` refuses it by name today, correctly, and the refusal
**stays**. Registering a viewer over a half-built assembler would put a live
Download button, a live card and a live report title over a page that could not
name a single charge — hard-won law 2's mirror, on the one surface in this
product a CUSTOMER sees. **A report that refuses with a reason is honest; a
report that renders four empty rows under a projected total is not.**

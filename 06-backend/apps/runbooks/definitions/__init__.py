# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-015 (EP-RBS-01) — CR-075 wave B task B2: one Python module
#           per runbook, and adding one is the whole cost of runbook 23.
# Rules:    BR-RBS-024 · BR-RBS-025 (the chip row is built from what is present)
#           · BR-RBS-039 (this module never resolves an import it cannot be
#           censused on — G115)
# Tests:    06-backend/tests/test_us_rbs_015_conformance.py
# Impacts:  apps/runbooks/registry.py (load() walks DEFINITION_MODULES)
# ───────────────────────────────────────────────────────
"""One module per runbook, and one line here naming it.

A module in this package declares exactly one name:

    RUNBOOK = RunbookDefinition(key="...", kind="check", ...)

and adds itself to `DEFINITION_MODULES` below. `registry.load()` walks that
tuple at `AppConfig.ready()` and registers what each module declares.

⚠ **WHY THIS IS A LIST AND NOT A DISCOVERY LOOP, WHICH IS A DIVERGENCE FROM THE
EXECUTION PLAN'S `B2` AND IS RECORDED RATHER THAN APPLIED SILENTLY.** The
obvious build is `pkgutil.iter_modules()` + `importlib.import_module()`, and
`US-RBS-015`'s promise — *a developer adds ONE Python module and it appears* —
reads like a request for exactly that. **`G115` refuses it, by name and by line,
and `G115` is right.** Its rule 3 permits a dynamic import only where the
argument is a string LITERAL beginning `apps.runbooks.`; a computed module name
is a hole a static census cannot follow, and the census is the only thing
standing between this module and an `Account.objects.filter(...)` four lines
shorter than asking `customers` for a selector. Weakening the module's own
boundary gate to save one line per runbook is the wrong trade, so the second
line is the price and it is one line.

**AND THE SECOND LINE CANNOT BE SILENTLY FORGOTTEN**, which is the only reason
this is acceptable: `test_us_rbs_015_conformance.py` globs `definitions/*.py` on
disk and fails naming any module that is not in the tuple below. Forgetting the
line is a RED test that names the file, where a discovery loop's failure mode is
a runbook that silently registers a half-finished module a lane left behind.
The failure mode is strictly better; the cost is one import.

⚠ **THIS PACKAGE IS EMPTY IN WAVE B, DELIBERATELY, AND THE CONFORMANCE SUITE
SAYS SO OUT LOUD RATHER THAN REPORTING A SILENT PASS.** The first runbook is
wave C's `configuration_check.py` — *Can we bill?*, ten steps, a per-service
verdict rolled up to a tenant verdict. Wave B builds the contract, the registry
and the suite that refuses a bad declaration; it ships no runbook, because a
runbook written before its renderer exists is a result nobody can read.

**What that costs, stated rather than hidden:** the suite has zero live
definitions to conform, so it proves the MECHANISM instead — it registers
exemplar definitions built in the test, and it asserts the disk-versus-tuple
agreement above. `registry.describe()` prints the live count beside the verdict,
so *"0 registered"* is visible in the output and cannot be mistaken for *"all
registered runbooks conform"*. `G5` once ran the isolation suite on SQLite and
called 192 skips a pass; this is the same shape and the same answer — print the
number.
"""

from __future__ import annotations

from types import ModuleType

from apps.runbooks.definitions import (
    abnormal_readings,
    accounting_export,
    autopay_prenotice,
    bank_reconciliation,
    budget_relevel,
    cash_application,
    configuration_check,
    coverage_grid,
    cutover_readiness,
    data_hygiene,
    deposit_review,
    disconnect_eligibility,
    dunning,
    gis_reconciliation,
    leak_alert,
    meter_change_out,
    month_end,
    move_outs,
    newworld_receipt_push,
    payment_plans,
    payment_trace,
    rate_change_preview,
    read_validation,
    returned_payments,
    test_bill,
    undeliverable_contacts,
    vacant_with_usage,
    why_higher,
    why_not_billed,
)

#: Every runbook module in this package, in catalogue order — runbook 1 first.
#:
#: ⚠ **THIS IS THE ONE LINE `US-RBS-015` PROMISES, AND FORGETTING IT IS A RED
#: TEST RATHER THAN A SILENT ABSENCE.** `test_us_rbs_015_conformance.py` globs
#: `definitions/*.py` on disk and fails naming any module this tuple does not
#: carry, which is why the explicit list is affordable where a discovery loop is
#: not (see the docstring above, and `G115` rule 3).
DEFINITION_MODULES: tuple[ModuleType, ...] = (
    configuration_check,
    cash_application,
    bank_reconciliation,
    accounting_export,
    #: Runbook 8 — the Collections ladder (`CR-075` wave L task L6). The FIRST
    #: Action in this tuple that holds a bound port, and it still cannot write:
    #: `engine.acts.LIVE_ENABLED_RUNBOOKS` is empty for the whole catalogue.
    dunning,
    #: Runbook 23 — the Test bill (`CR-075` wave F task F2). A Check, so it holds
    #: no port at all, and **this line is the whole cost of adding it**: no
    #: frontend code, no endpoint, no migration — `RB-020`'s claim, and runbook
    #: 23 is the first one to test it.
    test_bill,
    #: Runbook 20 — GIS reconciliation (`CR-075` wave Q′ task, phase 3). An
    #: Action holding `apply_premise_change`, which IS bound — and cannot write,
    #: because `engine.acts.LIVE_ENABLED_RUNBOOKS` is empty for the whole
    #: catalogue.
    gis_reconciliation,
    #: Runbook 22 — Undeliverable contacts (`CR-075` wave Q′, phase 3). An Action
    #: holding `suppress_channel` and `flag_account`, **neither of which binds a
    #: writer**: `customers` has no undeliverable-channel column and `Account`
    #: carries only `cash_only` (`DEF-RBS-4331`). Each port's own refusal is
    #: recorded in the report rather than papered over with an invented write.
    undeliverable_contacts,
    #: Runbook 4 — *Why is this bill higher?* (`CR-075` wave S, phase 5). A
    #: Check over one account and two ISSUED bills, ranked by the dollars each
    #: cause contributed. No port, no writer, no frontend code.
    why_higher,
    #: Runbook 19 — Data hygiene (`CR-075` wave S, phase 5). A Check whose
    #: subject is the TENANT: seven set steps over the whole utility, grouped by
    #: what each finding will break.
    data_hygiene,
    #: Runbook 24 — the Coverage grid (`CR-075` wave G task G2). A Check, and
    #: the FIRST runbook in this tuple that runs another one: every cell is a
    #: real child run of `test_bill` with `parent_run` set, which is what makes
    #: *"a red cell opens that account's test bill"* a door rather than a
    #: sentence. It resolves that definition through the REGISTRY at run time
    #: and imports `test_bill` only INSIDE a function, for its fix-route table,
    #: so this tuple's order is a reading order and not an import dependency.
    coverage_grid,
    #: Runbook 2 — Cutover reconciliation (`CR-075` wave J task J2, phase 4). A
    #: Check, so it holds no port at all, and it is the FIRST runbook in the
    #: catalogue to declare `requires` — `configuration_check`, `BR-RBS-027`.
    #: The engine does not yet RUN a required Check (wave `I` task `I4` is
    #: unbuilt), so step 1 SAYS so rather than drawing a tick nobody computed.
    cutover_readiness,
    #: Runbook 9 — Books tie-out (`CR-075` wave K task K1, phase 4, and it
    #: CLOSES phase 4). A Check that reads the ledger's own tie-outs and its
    #: close checklist and subtracts nothing. **Close period ✓** stays a named
    #: person's act performed by the ledger — `BR-RBS-030`, confirmed by the PO
    #: on 2026-09-06 in the words *"1736 - always a person"* (`OQ-RBS-1736`).
    month_end,
    #: Runbook 15 — Deposit review (`CR-075` wave R′, phase 5). An Action holding
    #: `post_credit`, `raise_refund` and `queue_notice` — all three BOUND, and
    #: none of them reachable: `engine.acts.LIVE_ENABLED_RUNBOOKS` is empty for
    #: the whole catalogue. ❄️ `GT-61`'s deposit interest is READ from
    #: `customers` and computed nowhere in this package.
    deposit_review,
    #: Runbook 17 — Autopay pre-notification (`CR-075` wave R′, phase 5). An
    #: Action holding `queue_notice`, `schedule_retry` and `flag_account`; the
    #: last binds no writer and its own refusal is recorded. **Its failed-debit
    #: half reports NOT REPORTED and never zero** — nothing on this product
    #: drafts an autopay debit (`BR-PAY-015`), so none can fail.
    autopay_prenotice,
    #: Runbook 25 — Payment plans (`CR-075` wave R′, phase 5). An Action holding
    #: `queue_notice` alone, which is `US-RBS-035` §5's own list: **voiding a
    #: plan has no port and there is no `voided` status to write**
    #: (`OQ-RBS-1740`, OPEN). A plan reaches `to_void` with its rule and a route
    #: to the person who ends it, and the result says so rather than implying it
    #: was ended.
    payment_plans,
    #: Runbook 26 — Returned payments (`CR-075` wave R′, phase 5). An Action that
    #: **STOPS at step 1 on every deployment today** — no returns feed, no column
    #: for a bank's return code, and no port that reverses a payment
    #: (`OQ-RBS-1741`). The stop is a valid state by PO ruling 2026-09-06, and
    #: the run draws it as a designed answer rather than as a failure.
    returned_payments,
    #: Runbook 21 — **Read exceptions**, the card's *Read validation on
    #: arrival* (`CR-075` wave R′, phase 5). An Action holding `write_read`,
    #: **which binds no writer at all**: metering's read door certifies the
    #: reading as the acting HUMAN (`US-MET-010`), so an automation may not
    #: sign one (`DEF-RBS-4331`). It is the runbook that proves `BR-RBS-019` —
    #: 176,640 intervals become 1,840 meter-days, and the rollup happens on the
    #: OWNING side of the seam so this module never sees an interval.
    read_validation,
    #: Runbook 11 — **Leak and high-usage alert** (`CR-075` wave R′, phase 5).
    #: An Action holding `queue_notice` — bound, and still writing nothing while
    #: `LIVE_ENABLED_RUNBOOKS` is empty — and `flag_meter`, **which binds no
    #: writer at all**: nothing in this product holds *"told about a leak on"* a
    #: date, and the row it would belong to is `apps/assets`', which is not one
    #: of the five modules a port may write (`DEF-RBS-4331`). Its *once per
    #: meter every 7 days* guard therefore reads the notice OUTBOX, because
    #: `BR-RBS-040` makes the obvious substitute — a note — an engine act rather
    #: than a fourteenth port.
    leak_alert,
    #: Runbook 27 — **Move-outs** (`CR-075` wave R′, phase 5), the card's
    #: *Move-outs and final bills*. An Action holding `raise_refund`,
    #: `post_credit` and `queue_notice` — all three bound and none able to
    #: write while `LIVE_ENABLED_RUNBOOKS` is empty. ⚠ **It does NOT hold a
    #: bill-issuing port, because there is none and there will not be one**
    #: (`billing_ports.py`): a runbook hands billing a scope and the bill run is
    #: billing's own act, which is hard rule 4 read forward. Its money comes
    #: from `apps/customers/move_out_settlement.py` and is re-derived nowhere.
    move_outs,
    #: ── CR-075 WAVE S · THE EIGHT REMAINING CHECKS (phase 5) ───────────
    #: Each is a Check: no port, no writer, no frontend code. Runbook 4 walks
    #: one account and two ISSUED bills; runbook 5 walks each METER's own twelve
    #: months; runbook 6 explains one account on one bill run, or that run's
    #: whole break list; runbook 13 FINDS a payment and never moves one; runbook
    #: 18 is the only Check in the wave whose output is a dollar figure; runbook
    #: 19's subject is the TENANT.
    abnormal_readings,
    why_not_billed,
    payment_trace,
    vacant_with_usage,
    #: Runbook 12 — Disconnect eligibility (`CR-075` wave S, phase 5). A Check
    #: over the accounts at the LAST tier, and the one whose ports being empty
    #: is the whole promise: **nothing here disconnects anyone.** A person signs
    #: a field list and a crew acts through the Work module. Its removed rows
    #: are RECORDS rather than guards on purpose — the card draws each removal
    #: with its reason, and that list is the one that would have been wrong.
    disconnect_eligibility,
    #: Runbook 16 — Rate change preview (`CR-075` wave S, phase 5). A Check over
    #: the BILLS of one issued cycle, re-priced against a DRAFT schedule through
    #: the rating engine's own path — the same call a bill makes, pointed at a
    #: version that is not in force. It issues nothing and consumes no bill
    #: number, and it reports how many bills its baseline pass failed to
    #: reproduce, which is the run's own error bar.
    rate_change_preview,
    #: Runbook 28 — **Meters past change-out age or never tested** (`CR-075`,
    #: `US-RBS-043`). A Check, so it holds no port at all — and its kind is the
    #: CARD's own conditional: *"waits on `RB-049` for a field order, and is a
    #: Check without it"*. `RB-049` does not exist, so its two controls are
    #: LINKS to `assets` rather than writes, and the module docstring says what
    #: it becomes the day a field order arrives. **The FIRST runbook in the
    #: Assets category**, which held one step and no runbook until this commit —
    #: so `BR-RBS-025`'s chip row gains *Assets* and stops being dead UI.
    meter_change_out,
    #: Runbook 33 — **Budget billing re-level** (`CR-075`, `US-RBS-044`). An
    #: Action holding `queue_notice` alone — **and it is not the port the
    #: runbook is named after**: nothing in `interfaces.PORTS` moves a budget
    #: level, `billing`'s single port raises a draft fee, and a fifteenth is a
    #: reviewed interface (`BR-RBS-022`) rather than a line added here. So step
    #: 4 records the refusal, and step 3 HOLDS the notice too — nobody is told
    #: about a change this product cannot make. The level arithmetic is ❄️
    #: `GT-24`'s own (`apps.billing.budget.compute_level`) and is called, never
    #: re-implemented.
    budget_relevel,
    #: **New World receipt push** (`CR-173-BRC10`, 2026-10-07). An Action
    #: holding `send_partner_file` — the fifteenth port, owned by integrations
    #: — and the FIRST key on `engine.acts.LIVE_ENABLED_RUNBOOKS`. It writes no
    #: money; it places a file of payments already posted in a City's folder,
    #: and only for a utility that typed that folder on its own connection.
    newworld_receipt_push,
)

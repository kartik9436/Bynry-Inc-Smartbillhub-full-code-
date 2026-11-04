# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-008 (EP-RBS-03) — CR-075 wave J task J2, runbook 2,
#           *Ready for cutover?*, on screen **Cutover reconciliation**.
# Rules:    BR-RBS-002 (a Check is CONSTRUCTED with no ports) · BR-RBS-009
#           (scope resolved once and PINNED) · BR-RBS-010 (every record states
#           the rule that decided it, in words a clerk can read) · BR-RBS-011
#           (a failure names its fix route) · BR-RBS-014 (a sample record is
#           never acted on — step 7 refuses a cutover while one remains) ·
#           BR-RBS-019 (the declared unit of work) · BR-RBS-020 (the report is
#           frozen at close) · BR-RBS-021 (twelve blocks) · BR-RBS-023 (a step
#           declares its mode) · BR-RBS-024 (one category from the sixteen) ·
#           BR-RBS-026 (Onboarding & Cutover sorts first while a plan is open) ·
#           BR-RBS-027 (`requires` — one Check runs first as its own run) ·
#           BR-RBS-039 (every foreign read through a seam) · PO ruling
#           2026-09-05 (cutover open items are ONE LINE PER OPEN INVOICE) ·
#           CLAUDE.md hard rule 2 (money 4 stored / 2 displayed, CHAR(3)) ·
#           hard rule 5 (this writes no journal line) · B14 rules 31 · 32 · 33
# Tests:    06-backend/tests/test_us_rbs_008_cutover_readiness.py
# Impacts:  apps/runbooks/definitions/__init__.py (the one line registering it) ·
#           apps/runbooks/cutover.py (the plan and its items) ·
#           apps/runbooks/seams/{ledger,payments,billing}_seam.py ·
#           apps/payments/billing_seam.open_invoice_positions (the read it needs)
# ───────────────────────────────────────────────────────
"""Runbook 2 — **Cutover reconciliation**. *Can we switch this utility off the
old system on the agreed date?*

Nine read steps, run at freeze and as often as an implementer wants before it.
The answer is **Go** or **No-go**, and a No-go lists every disagreeing account
with BOTH figures and the difference, plus the plan items still open.

⚠ **THE COMPARISON IS AT BILL GRAIN AND THAT IS A PRODUCT OWNER'S RULING**
(5 September 2026, `US-RBS-008` §8): *one line per open invoice*, chosen over
*one balance per account* and *one bucket per age band*. It is not presentation.
An account-grain comparison nets two errors of opposite sign inside one customer
and reports a tie — **the one wrong answer a cutover check could give that an
implementer would believe** — and the `Open items at` parameter exists because a
legacy system that cannot produce invoice detail needs the bucket option
available rather than a workaround.

WHERE THE TRIAL BALANCE COMES FROM, AND WHY IT IS NOT THE IMPORT RUNNER
------------------------------------------------------------------------
The execution plan's `J2` says *"the trial balance as a `file` parameter read
once through the import runner"* and the catalogue's design note says the same.
**It is read as the `file` parameter's own content instead, and that is a
recorded judgment (law 13) rather than a shortcut.** Three reasons, in order of
weight:

1. **`trial_balance` IS NOT ONE OF THE SIX `IMPORT_TARGETS`.** A runbook calling
   `metering_seam.staged_import_batch("trial_balance")` could never get a batch
   back — the extract stage refuses an unknown target by name. That is a check
   **incapable of passing**, which is hard-won law 7's third shape and the exact
   failure this repository keeps paying for.
2. **`import_runs` is a stage → map → validate → LOAD machine for ENTITY rows**,
   with per-target numbering, dedupe, key resolution, load and rollback. A trial
   balance is compared once and never written, so six-sevenths of that machine
   would be dead weight, and a seventh target is `metering`'s work with its own
   field map and its own refusals.
3. **The per-row refusals the design note wants are this runbook's product
   anyway.** `BR-RBS-010` requires every record to state the rule that decided
   it; a row this file cannot read becomes a finding with a reason and a fix
   route, which is exactly what staging would have given and is on the screen a
   clerk is already looking at.

The day `metering` adds the target, `resolve()` is where it changes and nothing
else here moves.

IT IS A CHECK, SO IT DECLARES NO PORTS AT ALL
----------------------------------------------
`BR-RBS-002`, and `RunbookDefinition` refuses a Check that declares one at
CONSTRUCTION. **Attaching the run to a plan item is not this runbook's write** —
it is `POST /cutover-plans/{id}/items/{seq}/evidence`, performed by a person on
`apps/runbooks/cutover.py`, which is why `RB-102`'s own card says *"attaching
evidence to the plan is an act the engine or the owning module performs"*.

THIS RUNBOOK COMPUTES NO MONEY IT DID NOT HAVE TO
--------------------------------------------------
Every loaded figure crosses a seam already decided: per-account receivables are
`ledger.reporting.ar_positions`, per-bill balances are
`payments.billing_seam.open_invoice_positions`, and the two agree to the cent by
construction because they are one derivation at two grains. The only arithmetic
in this file is **their side minus ours**, which is the whole question.

FIVE JUDGMENTS RECORDED RATHER THAN ASKED (law 13)
----------------------------------------------------
1. **A MISSING FILE IS A REFUSAL, NOT A GREEN RUN.** With no trial balance there
   is nothing to reconcile, and a Go verdict over an absent file is the worst
   answer this runbook could give. Steps 3 and 4 report *"no legacy figures"* as
   a BLOCKER and the verdict is No-go.
2. **AN ACCOUNT IN THE FILE THAT WE DO NOT HOLD, AND ONE WE HOLD THAT THE FILE
   DOES NOT, ARE DIFFERENT FINDINGS.** `RBS-006-R2`'s own table draws *absent in
   file* as a distinct cell rather than as a difference, because a $0.00
   difference and *we have no record of this at all* are not the same fact and
   the fixes differ.
3. **THE TOTAL TOLERANCE IS A PERCENTAGE OF THE LEGACY TOTAL, NOT OF OURS.** The
   file is the authority a cutover is measured against; taking the percentage of
   our own side would make the tolerance move as the defect moves.
4. **STEP 8 REPORTS A STATED ABSENCE RATHER THAN A PASS.** The coverage grid is
   wave `G` and is not built, so *"the last grid run had no refusals"* has no
   run to read. Reporting it green would be a tick nobody computed (hard-won law
   1); it is a WARNING naming what is missing.
5. **A ZERO-VARIANCE RE-RUN IS WHAT TURNS A PLAN ITEM GREEN, AND THE RUNBOOK
   DOES NOT DO IT.** The run publishes its variance; `cutover.attach_evidence`
   reads it and decides. Two acts, because only the second one writes.

⚠ **WHAT WOULD MAKE THIS RUNBOOK PASS WRONGLY, ANSWERED IN WRITING** (law 7's
second habit). The dangerous shape is **an empty comparison that reads like a
clean cutover**: no file, or a file whose every row failed to parse, and nine
green steps over nothing. So every step returns a `checked` mapping saying how
many things it looked at, the KPI strip draws the compared count beside the
difference, and a file that yielded no readable row is reported as *"no legacy
figures"* in words rather than as a balanced zero.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from apps.runbooks import models
from apps.runbooks.contract import (
    MODE_SET,
    PARAM_ENUM,
    PARAM_FILE,
    PARAM_MONEY,
    PARAM_PERCENT,
    PARAM_REF_OBJECT,
    PARAM_TOGGLE,
    Block,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.seams import (
    customers_seam,
    ledger_seam,
    metering_seam,
    payments_seam,
    tenancy_seam,
)

# ── money, at the precision hard rule 2 states ────────────────────────────

#: Stored to FOUR, displayed at TWO. Every figure this file compares is held at
#: four and quantized only where it becomes a string a person reads.
_FOUR_PLACES = Decimal("0.0001")
_TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0")


def money4(value: Any) -> Decimal:
    """A `Decimal` at FOUR decimals — hard rule 2's storage precision.

    ⚠ **`Decimal(str(value))` AND NEVER `Decimal(float)`.** A float that has
    been through JSON is a binary fraction, and `Decimal(0.1)` is
    `0.1000000000000000055511151231257827`. The whole comparison in this file is
    an equality against a $0.01 tolerance, so one float would make a tied
    account report a difference of a hundred-quadrillionth of a cent.
    """
    if isinstance(value, Decimal):
        return value.quantize(_FOUR_PLACES, rounding=ROUND_HALF_UP)
    return Decimal(str(value or 0)).quantize(_FOUR_PLACES, rounding=ROUND_HALF_UP)


def money2(value: Any) -> str:
    """The same figure as the string a clerk reads — TWO decimals, always."""
    return str(money4(value).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP))


# ── what could not be reconciled ──────────────────────────────────────────

BLOCKER = "blocker"
WARNING = "warning"

#: Every fix route is TENANT-RELATIVE — the shell prefixes `/:tenant/` — exactly
#: as `tenancy.selectors.CHECKLIST_TARGETS` and runbook 1's are. ⚠ A route that
#: resolves to nothing is a dead button over a live finding, which is hard-won
#: law 2's mirror and which no backend test can see (`DEF-RBS-4329` is what it
#: cost when the tenant prefix was left off).
FIX_IMPORTS = "settings/imports"
FIX_ACCOUNTS = "accounts"
FIX_FINANCE = "finance"
FIX_SETTINGS_NUMBERING = "settings/numbering"
FIX_SETTINGS_SAMPLE = "settings/sample-data"
FIX_PLANS = "plans"
FIX_RUNBOOKS = "runbooks"


@dataclass(frozen=True)
class Finding:
    """One thing that stops a cutover, in words, with the screen that fixes it.

    ⚠ **`fix_route` IS REQUIRED** (`BR-RBS-011`): a failure a clerk cannot act on
    is a failure we should not have shown them.

    ⚠ **`decided_by_rule` IS A SENTENCE AND NEVER A RULE ID** (`BR-RBS-010`,
    B14 rule 32). The id belongs in this file's docstrings, where an engineer
    reads it.
    """

    key: str
    reason: str
    affects: str
    weight: str
    fix_route: str
    fix_label: str
    decided_by_rule: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("a finding with no reason says nothing to anybody")
        if not self.fix_route.strip():
            raise ValueError(
                f"finding {self.reason!r} names no fix route. BR-RBS-011: a failure names its "
                "fix route, and one without a route is a defect in the runbook."
            )
        if self.weight not in (BLOCKER, WARNING):
            raise ValueError(f"finding {self.reason!r} carries weight {self.weight!r}")

    def as_row(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "reason": self.reason,
            "affects": self.affects,
            "weight": self.weight,
            "fix_route": self.fix_route,
            "fix_label": self.fix_label,
            "decided_by_rule": self.decided_by_rule,
        }


@dataclass
class _StepResult:
    """What every set step returns — what it found, and what it LOOKED AT.

    `checked` is not decoration. A step that reports nothing over an empty file
    and a step that reports nothing over a correct migration are the same
    sentence with very different meanings (hard-won law 7).
    """

    findings: list[Finding] = field(default_factory=list)
    checked: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "findings": [row.as_row() for row in self.findings],
            "checked": dict(self.checked),
        }


# ── the legacy trial balance ──────────────────────────────────────────────

#: The column names this reader accepts, lower-cased and stripped. A legacy
#: export names its columns whatever the old system called them, so each target
#: carries the aliases seen in the field: `metering.importers` takes exactly this
#: posture for premises and units, and the reason is the same — a utility should
#: not have to rename columns before a check will read their file.
TB_ALIASES: dict[str, tuple[str, ...]] = {
    "account": ("account", "account_no", "account #", "account number", "customer", "cust_no"),
    "invoice": ("invoice", "invoice_no", "invoice #", "bill", "bill_no", "bill #", "document"),
    "amount": ("amount", "balance", "outstanding", "open", "due", "amount_due"),
}

#: `Open items at` — the PO's own two readings of a legacy export.
GRAIN_INVOICE = "Invoice level"
GRAIN_ACCOUNT = "Account level"


@dataclass(frozen=True)
class LegacyRow:
    """One line of the legacy trial balance, already in this product's terms."""

    account: str
    invoice: str
    amount: Decimal
    line_no: int

    @property
    def key(self) -> str:
        """What this row is compared AGAINST — the bill number where there is
        one, the account where the file is at account grain."""
        return self.invoice or self.account


@dataclass(frozen=True)
class LegacyFile:
    """A parsed trial balance, and every line that could not be read."""

    rows: tuple[LegacyRow, ...]
    unreadable: tuple[dict[str, Any], ...]
    headers: tuple[str, ...]
    present: bool

    @property
    def total(self) -> Decimal:
        return sum((row.amount for row in self.rows), ZERO)


def _map_headers(headers: list[str]) -> dict[str, str]:
    """`{target: source column}` for whichever of the three we can find."""
    lowered = {str(name).strip().lower(): name for name in headers}
    found: dict[str, str] = {}
    for target, aliases in TB_ALIASES.items():
        for alias in aliases:
            if alias in lowered:
                found[target] = lowered[alias]
                break
    return found


def parse_trial_balance(content: Any) -> LegacyFile:
    """The uploaded CSV, as rows this runbook can compare — **or an ABSENCE.**

    ⚠ **A LINE THAT CANNOT BE READ IS KEPT AS A FINDING, NEVER DROPPED.** A
    silently skipped row is a bill the legacy system says is open and this
    product will simply never mention — which is precisely the shape of failure
    a cutover reconciliation exists to catch. Each one carries its line number,
    which is what a person needs to open the file and look.

    ⚠ **`present=False` IS NOT `rows=()`.** *Nobody uploaded a file* and *the
    file was empty* are different sentences to an implementer and only one of
    them means the old system says nobody owes anything. Steps 3 and 4 read the
    flag, not the length.
    """
    if content in (None, ""):
        return LegacyFile(rows=(), unreadable=(), headers=(), present=False)
    text = content.decode("utf-8-sig") if isinstance(content, bytes) else str(content)
    reader = csv.DictReader(io.StringIO(text))
    headers = tuple(reader.fieldnames or ())
    if not headers:
        return LegacyFile(
            rows=(),
            unreadable=(
                {"line_no": 0, "reason": "The file has no header row.", "raw": ""},
            ),
            headers=(),
            present=True,
        )
    mapping = _map_headers(list(headers))
    if "amount" not in mapping or ("account" not in mapping and "invoice" not in mapping):
        return LegacyFile(
            rows=(),
            unreadable=(
                {
                    "line_no": 0,
                    # B14 rule 33 — an instruction is six words a sentence, and
                    # two sentences of six beat one of twelve. The second is
                    # where "what to do next" lives.
                    "reason": "Columns not recognised. Name them account, invoice, amount.",
                    "raw": ", ".join(headers),
                },
            ),
            headers=headers,
            present=True,
        )

    rows: list[LegacyRow] = []
    unreadable: list[dict[str, Any]] = []
    for line_no, raw in enumerate(reader, start=2):
        account = str(raw.get(mapping.get("account", ""), "") or "").strip()
        invoice = str(raw.get(mapping.get("invoice", ""), "") or "").strip()
        figure = str(raw.get(mapping["amount"], "") or "").strip()
        if not account and not invoice:
            unreadable.append(
                {"line_no": line_no, "reason": "No account or bill number.", "raw": figure}
            )
            continue
        try:
            # ⚠ THE STRING GOES STRAIGHT INTO `Decimal` AND NEVER THROUGH
            # `float()`. Hard rule 2 — never a float, never cents — and a
            # legacy export writes `1,204.05` and `$1,204.05` and `(88.20)`
            # for a credit, all of which are money and none of which `float`
            # would read the same way.
            cleaned = figure.replace(",", "").replace("$", "").strip()
            if cleaned.startswith("(") and cleaned.endswith(")"):
                cleaned = "-" + cleaned[1:-1]
            amount = money4(Decimal(cleaned or "0"))
        except (InvalidOperation, ValueError):
            unreadable.append(
                {
                    "line_no": line_no,
                    "reason": "The amount is not a number.",
                    "raw": figure,
                }
            )
            continue
        rows.append(
            LegacyRow(account=account, invoice=invoice, amount=amount, line_no=line_no)
        )
    return LegacyFile(
        rows=tuple(rows), unreadable=tuple(unreadable), headers=headers, present=True
    )


# ── the nine steps ────────────────────────────────────────────────────────

STEP_CONFIG = "config"
STEP_COUNTS = "counts"
STEP_BALANCES = "balances"
STEP_DEPOSITS = "deposits"
STEP_PLANS = "plans"
STEP_NUMBERING = "numbering"
STEP_SAMPLE = "sample"
STEP_COVERAGE = "coverage"
STEP_PLAN_ITEMS = "plan_items"

#: `RB-102`'s own nine, in its own order and its own words. The chain block
#: draws these, so the labels are a clerk-facing surface: B14 rule 33 caps a
#: LABEL at three words and every one of them obeys it.
STEP_LABELS = {
    STEP_CONFIG: "Config passes",
    STEP_COUNTS: "Counts",
    STEP_BALANCES: "Balances",
    STEP_DEPOSITS: "Deposits",
    STEP_PLANS: "Plans carried",
    STEP_NUMBERING: "Numbering",
    STEP_SAMPLE: "Sample gone",
    STEP_COVERAGE: "Coverage",
    STEP_PLAN_ITEMS: "Plan items",
}


def _params(ctx) -> dict[str, Any]:
    return dict(ctx.params or {})


def _legacy(ctx) -> LegacyFile:
    """The parsed file, parsed ONCE per run and carried on `set_results`.

    ⚠ **ONCE, AND THAT IS `BR-RBS-009` RATHER THAN A PERFORMANCE NOTE.** The
    scope is resolved once and pinned; a file re-parsed in each of four steps
    could in principle be four different files, and the run would have no single
    answer to *what was compared*.
    """
    carried = (ctx.set_results.get(STEP_COUNTS) or {}).get("legacy")
    if carried is not None:
        return carried
    return parse_trial_balance(_params(ctx).get("trial_balance"))


def step_config(ctx, subjects) -> dict[str, Any]:
    """1 · Did the configuration check pass? — `requires`, runbook 1.

    ⚠ **THE ENGINE DOES NOT YET RUN THE REQUIRED CHECK AND THIS STEP SAYS SO
    RATHER THAN CLAIMING IT DID.** `BR-RBS-027` and `RB-036` describe the
    behaviour — the required Check runs first as its own run, `parent_run_id`
    set, linked from step 1, and a failure stops the caller with *"Never
    reached"* on every later step. That wiring is **task `I4` of wave `I`**,
    which has not landed: `RunbookDefinition.requires` is validated for shape
    and for existence in the registry, `RunbookRun.parent_run` is a column, and
    nothing in `engine/executor.py` opens the sub-run.

    So this step reports the truth: it names the Check that must pass, states
    that the engine does not yet run it here, and carries a WARNING rather than
    a green tick. **A tick nobody computed is hard-won law 1 exactly**, and
    `DEF-RBS-4353` — filed the same week for wave `I`'s `I1` — is what the
    alternative costs.

    The day `I4` lands, this step reads the sub-run's verdict and the WARNING
    becomes a real pass or a real BLOCKER. Nothing else in this file changes.
    """
    result = _StepResult()
    required = RUNBOOK.requires
    result.checked = {"requires": required, "sub_run_executed": False}
    result.findings.append(
        Finding(
            key="config_check_not_run_here",
            reason="The configuration check has not run with this one.",
            affects="Every later step",
            weight=WARNING,
            fix_route=FIX_RUNBOOKS,
            fix_label="Run the check",
            decided_by_rule="A cutover is only readable once the setup check passes.",
        )
    )
    return result.as_dict()


def step_counts(ctx, subjects) -> dict[str, Any]:
    """2 · Do the counts agree — accounts, premises, meters, live services?

    The file's account count is DISTINCT accounts named in it, not its line
    count: at invoice grain one account carries several lines, and comparing
    2,911 lines against 2,907 accounts would report a difference on every
    correctly migrated estate.
    """
    result = _StepResult()
    legacy = parse_trial_balance(_params(ctx).get("trial_balance"))
    accounts = customers_seam.account_anchors()
    census = metering_seam.census()
    graph = metering_seam.service_point_graph()
    services = tenancy_seam.enabled_services()

    # ⚠ **THE KEY IS `assets`, NOT `service_points`, AND THE FIRST DRAFT READ
    # THE WRONG ONE.** `service_point_graph` returns `{unit_id, points,
    # assets}`; a walk over `unit["service_points"]` finds nothing, `.get`
    # returns `()`, the loop body never runs and the count is **0 with nothing
    # raising**. It reported *Meters 0* over a 73-premises estate and every test
    # would have agreed with it — an absence is invisible to every check this
    # repo has (CLAUDE.md hard rule 8's closing lesson). Named here because the
    # next reader of this line deserves to know it was got wrong once.
    meters = 0
    for unit in graph:
        for asset in unit.get("assets") or ():
            if str(asset.get("category") or "").startswith("meter"):
                meters += 1

    file_accounts = {row.account for row in legacy.rows if row.account}
    loaded = {
        "accounts": len(accounts),
        "premises": int(census.get("premises", 0)),
        "meters": meters,
        "services": len(services),
    }
    result.checked = {
        "loaded": loaded,
        "file_accounts": len(file_accounts),
        "file_lines": len(legacy.rows),
        "unreadable_lines": len(legacy.unreadable),
        "file_present": legacy.present,
        # Carried so every later step reads ONE parse of ONE file (BR-RBS-009).
        "legacy": legacy,
    }

    for entry in legacy.unreadable:
        result.findings.append(
            Finding(
                key=f"unreadable_line_{entry['line_no']}",
                reason=entry["reason"],
                affects=f"Line {entry['line_no']}" if entry["line_no"] else "The whole file",
                weight=BLOCKER,
                fix_route=FIX_IMPORTS,
                fix_label="Open the file",
                decided_by_rule="A line we cannot read is a balance we cannot compare.",
            )
        )
    if legacy.present and file_accounts and len(file_accounts) != loaded["accounts"]:
        gap = loaded["accounts"] - len(file_accounts)
        result.findings.append(
            Finding(
                key="account_count_differs",
                reason=f"{abs(gap)} accounts {'missing here' if gap < 0 else 'not in the file'}.",
                affects=f"{len(file_accounts)} in the file · {loaded['accounts']} loaded",
                weight=BLOCKER,
                fix_route=FIX_ACCOUNTS,
                fix_label="Open accounts",
                decided_by_rule="Every account in the old system has to arrive here.",
            )
        )
    return result.as_dict()


def step_balances(ctx, subjects) -> dict[str, Any]:
    """3 · Do the balances tie — every bill within $0.01, the total within 0.05%?

    ⚠ **THE PER-LINE TOLERANCE IS AN ABSOLUTE COMPARISON AT FOUR DECIMALS AND
    THE TOTAL'S IS A PERCENTAGE OF THE LEGACY SIDE.** Both are parameters and
    both default to `RB-102`'s own figures. The percentage is taken of the FILE's
    total rather than ours because the file is the authority a cutover is
    measured against; taking it of our own side would make the tolerance move as
    the defect moves.

    ⚠ **THREE OUTCOMES PER KEY, NOT TWO.** A difference · *absent in file* ·
    *absent here*. `RBS-006-R2` region 9 draws the second as its own cell rather
    than as a $0.00 difference, because *we hold this and the old system does
    not* is a different fact from *the figures disagree* and its fix is
    different. Netting them into one number is how a migration that dropped one
    bill and duplicated another reports a perfect tie.
    """
    result = _StepResult()
    params = _params(ctx)
    legacy = _legacy(ctx)
    grain = str(params.get("open_items_at") or GRAIN_INVOICE)
    tolerance = money4(params.get("money_tolerance", "0.01"))
    total_tolerance_pct = Decimal(str(params.get("total_tolerance", "0.05")))

    positions, problems = payments_seam.open_invoice_positions()
    accounts = {row["id"]: row for row in customers_seam.account_anchors()}

    # ⚠ **WITH NO FILE THERE IS NOTHING TO COMPARE, AND COMPARING ANYWAY IS
    # WORSE THAN NOT COMPARING.** Every open bill would come back
    # *absent in file*, the difference would be our own receivable in full, and
    # the screen would read *"31 accounts disagree · off by $7,661.92"* over a
    # run where nobody uploaded anything. Measured: that is exactly what the
    # first draft of this step said on the seeded utility. The figures below are
    # therefore OUR SIDE ONLY, plainly labelled, and the finding says the file
    # is missing.
    if not legacy.present:
        result.checked = {
            "grain": grain,
            "compared": 0,
            "ours": len(positions),
            "theirs": 0,
            "legacy_total": None,
            "loaded_total": sum((money4(one["balance"]) for one in positions), ZERO),
            "total_off_by": None,
            "percent_of_total": None,
            "total_tolerance": total_tolerance_pct,
            "money_tolerance": tolerance,
            "accounts_disagreeing": 0,
            "differences": [],
            "currency": tenancy_seam.currency(),
            "problems": [dict(problem) for problem in problems],
        }
        result.findings.append(
            Finding(
                key="no_trial_balance",
                reason="No legacy trial balance was given.",
                affects="Every balance",
                weight=BLOCKER,
                fix_route=FIX_IMPORTS,
                fix_label="Upload the file",
                decided_by_rule="Nothing can be reconciled against a file nobody supplied.",
            )
        )
        return result.as_dict()

    # ── our side, at the grain the file is written in ──
    ours: dict[str, Decimal] = {}
    labels: dict[str, str] = {}
    for one in positions:
        account = accounts.get(one["account_id"]) or {}
        account_no = str(account.get("account_no") or "")
        key = one["number"] if grain == GRAIN_INVOICE else account_no
        if not key:
            continue
        ours[key] = ours.get(key, ZERO) + money4(one["balance"])
        labels[key] = account_no or key

    theirs: dict[str, Decimal] = {}
    their_account: dict[str, str] = {}
    for row in legacy.rows:
        key = row.key if grain == GRAIN_INVOICE else (row.account or row.invoice)
        theirs[key] = theirs.get(key, ZERO) + row.amount
        their_account[key] = row.account or key

    differences: list[dict[str, Any]] = []
    for key in sorted(set(ours) | set(theirs)):
        legacy_amount = theirs.get(key)
        loaded_amount = ours.get(key)
        label = labels.get(key) or their_account.get(key) or key
        if legacy_amount is None:
            differences.append(
                {
                    "key": key,
                    "label": label,
                    "legacy": None,
                    "loaded": loaded_amount,
                    "off_by": None,
                    "state": "absent_in_file",
                }
            )
            continue
        if loaded_amount is None:
            differences.append(
                {
                    "key": key,
                    "label": label,
                    "legacy": legacy_amount,
                    "loaded": None,
                    "off_by": None,
                    "state": "absent_here",
                }
            )
            continue
        off_by = money4(loaded_amount - legacy_amount)
        if abs(off_by) > tolerance:
            differences.append(
                {
                    "key": key,
                    "label": label,
                    "legacy": legacy_amount,
                    "loaded": loaded_amount,
                    "off_by": off_by,
                    "state": "differs",
                }
            )

    legacy_total = legacy.total
    loaded_total = sum(ours.values(), ZERO)
    total_off_by = money4(loaded_total - legacy_total)
    # ⚠ THE PERCENTAGE IS OF THE **LEGACY** TOTAL, AND A ZERO LEGACY TOTAL HAS
    # NO PERCENTAGE. Dividing by ours would move the yardstick with the fault;
    # dividing by zero would crash the run on the tenant whose file is empty,
    # which is the tenant this check most needs to answer.
    pct = (
        (abs(total_off_by) / legacy_total * Decimal("100")).quantize(Decimal("0.0001"))
        if legacy_total
        else None
    )
    accounts_disagreeing = {
        (labels.get(one["key"]) or their_account.get(one["key"]) or one["key"])
        for one in differences
    }

    result.checked = {
        "grain": grain,
        "compared": len(set(ours) | set(theirs)),
        "ours": len(ours),
        "theirs": len(theirs),
        "legacy_total": legacy_total,
        "loaded_total": loaded_total,
        "total_off_by": total_off_by,
        "percent_of_total": pct,
        "total_tolerance": total_tolerance_pct,
        "money_tolerance": tolerance,
        "accounts_disagreeing": len(accounts_disagreeing),
        "differences": differences,
        "currency": tenancy_seam.currency(),
        "problems": [dict(problem) for problem in problems],
    }

    if differences:
        result.findings.append(
            Finding(
                key="balances_do_not_tie",
                reason=f"{len(accounts_disagreeing)} accounts disagree.",
                affects=(
                    # Hard rule 2 — the CHAR(3) beside every amount a person reads.
                    # This cell is a `text` value, so nothing downstream can add it.
                    f"{tenancy_seam.currency()} {money2(total_off_by)} "
                    f"across {len(differences)} lines"
                ),
                weight=BLOCKER,
                fix_route=FIX_FINANCE,
                fix_label="Open the books",
                decided_by_rule="Every balance has to arrive within a cent.",
            )
        )
    if pct is not None and pct > total_tolerance_pct:
        result.findings.append(
            Finding(
                key="total_outside_tolerance",
                reason=f"The total is {pct}% out.",
                affects=f"Limit {total_tolerance_pct}%",
                weight=BLOCKER,
                fix_route=FIX_FINANCE,
                fix_label="Open the books",
                decided_by_rule="The whole receivable has to arrive within a fraction of a percent.",
            )
        )
    return result.as_dict()


def step_deposits(ctx, subjects) -> dict[str, Any]:
    """4 · Do held deposits, credits and unapplied cash match?

    The GL side is `ledger.tie_out`'s own deposit-liability row — the same
    comparison `S36` renders and `BR-LED-007` blocks a release on. This runbook
    computes nothing: it reads the verdict the ledger already reached and says
    what it means for a cutover.
    """
    result = _StepResult()
    today = tenancy_seam.today()
    first = date(today.year, today.month, 1)
    tie_out = ledger_seam.tie_out_rows(first, today)
    deposit = next(
        (row for row in tie_out["rows"] if row["subledger"] == "deposit_liability"), None
    )
    result.checked = {
        "deposit_gl": None if deposit is None else deposit["gl"],
        "deposit_register": None if deposit is None else deposit["register"],
        "deposit_state": None if deposit is None else deposit["state"],
        "currency": None if deposit is None else deposit["currency"],
    }
    if deposit is None:
        result.findings.append(
            Finding(
                key="deposits_unreadable",
                reason="The deposit tie-out could not be read.",
                affects="Held deposits",
                weight=WARNING,
                fix_route=FIX_FINANCE,
                fix_label="Open the books",
                decided_by_rule="A deposit nobody can count is a deposit nobody can refund.",
            )
        )
    elif deposit["state"] != "agreed":
        result.findings.append(
            Finding(
                key="deposits_do_not_tie",
                reason="Held deposits do not tie.",
                affects=(
                    f"{money2(deposit['gl'] or 0)} in the books · "
                    f"{money2(deposit['register'] or 0)} recorded"
                ),
                weight=BLOCKER,
                fix_route=FIX_FINANCE,
                fix_label="Open the books",
                decided_by_rule="Deposits are the customer's money and must arrive exactly.",
            )
        )
    return result.as_dict()


def step_plans(ctx, subjects) -> dict[str, Any]:
    """5 · Are payment plans and budget levels carried?

    ⚠ **A STATED ABSENCE, NOT A PASS.** Payment plans and budget levels are a
    real migration risk and the product holds both, but neither module publishes
    a *"what arrived from the legacy system"* read, and there is no column
    saying a plan was MIGRATED rather than created here. A step that counted
    what exists today would report *5 plans carried* on a tenant where five were
    typed by hand this morning and none migrated — a tick nobody computed.

    So it reports what it CAN see — how many plans and levels the tenant holds —
    and says plainly that it cannot tell which of them came from the old system.
    That is `OQ-RBS-1738`, minted with this wave.
    """
    result = _StepResult()
    result.checked = {"can_tell_migrated": False}
    result.findings.append(
        Finding(
            key="plans_carried_unknown",
            reason="We cannot tell which plans were migrated.",
            affects="Payment plans and budget levels",
            weight=WARNING,
            fix_route=FIX_PLANS,
            fix_label="Open plans",
            decided_by_rule="Nothing records that a plan arrived from the old system.",
        )
    )
    return result.as_dict()


def step_numbering(ctx, subjects) -> dict[str, Any]:
    """6 · Do bill, receipt and customer numbers CONTINUE from the old system?

    ⚠ **THE FAULT THIS CATCHES IS A DUPLICATE NUMBER ON A DOCUMENT ALREADY
    SENT.** A series whose next value is below what the legacy system already
    issued will mint `BL-2608-000052` a second time, and a customer will hold
    two different bills with one number. `BR-TEN-035` allocates a number inside
    the writing transaction, so nothing downstream can catch it — this step is
    the only place it is visible before go-live.
    """
    result = _StepResult()
    series = tenancy_seam.number_series()
    result.checked = {"series": len(series), "rows": [dict(row) for row in series]}
    if not series:
        result.findings.append(
            Finding(
                key="no_number_series",
                reason="No numbering is set up yet.",
                affects="Bills, receipts, customers",
                weight=BLOCKER,
                fix_route=FIX_SETTINGS_NUMBERING,
                fix_label="Set numbering",
                decided_by_rule="A number series has to continue where the old one stopped.",
            )
        )
    return result.as_dict()


def step_sample(ctx, subjects) -> dict[str, Any]:
    """7 · Is every sample row gone? — `BR-RBS-014`, and it REFUSES the cutover.

    A demo account that survives go-live is a customer who does not exist being
    billed, chased and reported on. `BR-TEN-057` puts `is_sample` on the owning
    row, so reading the column is reading the fact rather than a copy of it.
    """
    result = _StepResult()
    sample_accounts = customers_seam.sample_account_ids()
    sample_premises = [
        row
        for row in metering_seam.premises_for_reconciliation(include_sample=True)
        if row.get("is_sample")
    ]
    result.checked = {
        "sample_accounts": len(sample_accounts),
        "sample_premises": len(sample_premises),
    }
    if sample_accounts or sample_premises:
        result.findings.append(
            Finding(
                key="sample_data_remains",
                reason="Sample records are still here.",
                affects=(
                    f"{len(sample_accounts)} accounts · {len(sample_premises)} premises"
                ),
                weight=BLOCKER,
                fix_route=FIX_SETTINGS_SAMPLE,
                fix_label="Remove samples",
                decided_by_rule="A sample record must never reach a live utility.",
            )
        )
    return result.as_dict()


def step_coverage(ctx, subjects) -> dict[str, Any]:
    """8 · Did the last coverage-grid run have no refusals?

    ⚠ **A STATED ABSENCE.** The coverage grid is runbook 24 and wave `G`, and it
    is not built — there is no grid run to read. Reporting this step green would
    be a tick nobody computed (hard-won law 1); it is a WARNING that names what
    is missing, and the day wave `G` lands this step reads that runbook's last
    run and the warning becomes a verdict.
    """
    result = _StepResult()
    from apps.runbooks.registry import registry

    built = "coverage_grid" in registry.keys()
    result.checked = {"coverage_grid_built": built}
    if not built:
        result.findings.append(
            Finding(
                key="coverage_grid_absent",
                reason="The coverage grid has not been built.",
                affects="Every service and rate",
                weight=WARNING,
                fix_route=FIX_RUNBOOKS,
                fix_label="Open runbooks",
                decided_by_rule="A cutover wants the grid green, and there is no grid yet.",
            )
        )
    return result.as_dict()


def step_plan_items(ctx, subjects) -> dict[str, Any]:
    """9 · Is every plan item done, with its evidence attached?

    ⚠ **A NULL `runbook_key` IS A HUMAN TASK THE ENGINE NEVER PERFORMS**
    (`03-field-map.md` D-7). *Customer signs bill layout* is not something this
    product can do; it is something a person ticks. That is why the column is
    nullable rather than required, and why this step counts the two kinds apart.
    """
    from apps.runbooks import cutover

    result = _StepResult()
    plan_id = _params(ctx).get("plan")
    plan = cutover.plan_for_run(plan_id)
    if plan is None:
        result.checked = {"plan": None, "open": 0, "items": 0}
        result.findings.append(
            Finding(
                key="no_cutover_plan",
                reason="No cutover plan is open.",
                affects="The go-live",
                weight=WARNING,
                fix_route=FIX_RUNBOOKS,
                fix_label="Open the plan",
                decided_by_rule="A cutover is tracked on a plan somebody keeps.",
            )
        )
        return result.as_dict()

    open_items = [item for item in plan["items"] if item["status"] != "done"]
    result.checked = {
        "plan": plan["name"],
        "plan_id": plan["id"],
        "items": len(plan["items"]),
        "open": len(open_items),
        "open_rows": [
            {
                "seq": item["seq"],
                "title": item["title"],
                "owner": item["owner"],
                "human_task": item["runbook_key"] is None,
            }
            for item in open_items
        ],
    }
    if open_items:
        result.findings.append(
            Finding(
                key="plan_items_open",
                reason=f"{len(open_items)} plan items are still open.",
                affects=plan["name"],
                weight=BLOCKER,
                fix_route=FIX_RUNBOOKS,
                fix_label="Open the plan",
                decided_by_rule="Every task on the cutover plan has to be done first.",
            )
        )
    return result.as_dict()


# ── the report ────────────────────────────────────────────────────────────

_TONE = {"go": "success", "warn": "warning", "no_go": "danger"}

#: Which chain cell is red. A cell's state is derived from its own step's
#: findings, so a step that produced a blocker cannot draw green — there is no
#: second list to fall out of step with.
CHAIN_OK = "ok"
CHAIN_FAILED = "failed"
CHAIN_WARNED = "warned"


def _findings(set_results: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return list((set_results.get(key) or {}).get("findings") or [])


def _all_findings(set_results: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in STEP_LABELS:
        rows.extend(_findings(set_results, key))
    return rows


def report(view) -> list[Block]:
    """`RBS-006-R2`'s six blocks: Verdict · KPIs · Chain · Reconciled · Records
    · Downloads.

    ⚠ **SIX OF THE TWELVE AND NO THIRTEENTH** (`BR-RBS-021`). The build sheet's
    twelve REGIONS are not twelve blocks: regions 5–12 are the two tables and
    their headings, which are the `reconciled` and `records` blocks and their own
    `heading` fields, and region 10 is `records`' pager.
    """
    set_results = dict(view.set_results)
    findings = _all_findings(set_results)
    blockers = [row for row in findings if row["weight"] == BLOCKER]
    warnings = [row for row in findings if row["weight"] == WARNING]
    balances = (set_results.get(STEP_BALANCES) or {}).get("checked") or {}
    counts = (set_results.get(STEP_COUNTS) or {}).get("checked") or {}
    plan_items = (set_results.get(STEP_PLAN_ITEMS) or {}).get("checked") or {}
    currency = str(balances.get("currency") or "USD")

    clear = sum(
        1 for key in STEP_LABELS if not any(f["weight"] == BLOCKER for f in _findings(set_results, key))
    )
    total_steps = len(STEP_LABELS)

    if blockers:
        word, tone = "No-go", "no_go"
        count = f"{total_steps - clear} of {total_steps} steps not clear"
    elif warnings:
        word, tone = "Go, with notes", "warn"
        count = f"{clear} of {total_steps} steps clear"
    else:
        word, tone = "Go", "go"
        count = f"{clear} of {total_steps} steps clear"

    detail_parts: list[str] = []
    off_by = balances.get("total_off_by")
    # ⚠ **WITH NO FILE THERE IS NO DIFFERENCE, ONLY OUR OWN SIDE — AND SAYING
    # *"Balances off by $7,661.92"* THERE IS THE WORST SENTENCE THIS RUNBOOK
    # COULD PRODUCE.** It reads as a reconciliation that found a discrepancy
    # when what actually happened is that nobody uploaded anything, and an
    # implementer would spend the morning looking for money that is not
    # missing. Measured on the seeded utility with no file: the first draft said
    # exactly that, over a legacy total of 0.00.
    if not counts.get("file_present"):
        detail_parts.append("No legacy file")
    elif off_by is not None and off_by != ZERO:
        detail_parts.append(f"Balances off by {currency} {money2(off_by)}")
    if plan_items.get("open"):
        detail_parts.append(f"{plan_items['open']} plan items open")
    detail = " · ".join(detail_parts)

    return [
        Block(
            block="verdict",
            payload={"word": word, "tone": _TONE[tone], "count": count, "detail": detail},
        ),
        Block(block="kpis", payload={"tiles": _tiles(balances, counts, clear, total_steps, currency)}),
        Block(block="chain", payload=_chain(set_results)),
        Block(block="reconciled", payload=_reconciled(balances, counts, currency)),
        Block(block="records", payload=_records(findings, blockers, warnings, set_results)),
        Block(
            block="downloads",
            payload={
                "files": (
                    [{"id": "differences", "label": "Differences", "format": "csv"}]
                    if balances.get("differences")
                    else []
                )
            },
        ),
    ]


def _tiles(balances, counts, clear, total_steps, currency) -> list[dict[str, Any]]:
    """`RBS-006-R2` region 3 — four tiles, and a money tile carries its basis."""
    # ⚠ **`None` AND `0.00` ARE DIFFERENT ANSWERS AND THE TILE SAYS SO.** With
    # no file there is no difference to state, and a tile reading `$0.00` there
    # would tell an implementer the books tie when nothing was compared — the
    # `DEF-127` shape, one surface up. `—` is the absence.
    off_by = balances.get("total_off_by")
    pct = balances.get("percent_of_total")
    limit = balances.get("total_tolerance")
    return [
        {
            "id": "difference",
            "label": "Balance difference",
            "value": {
                "kind": "money",
                "amount": "—" if off_by is None else money2(off_by),
                "currency": currency,
            },
        },
        {
            "id": "of_total",
            "label": "Of total",
            "value": {
                "kind": "percent",
                "value": "0.000000" if pct is None else str(pct),
                "basis": "points",
            },
            "detail": None if limit is None else f"limit {limit}%",
        },
        {
            "id": "accounts",
            "label": "Accounts disagree",
            "value": {"kind": "text", "text": str(balances.get("accounts_disagreeing", 0))},
        },
        {
            "id": "steps",
            "label": "Steps clear",
            "value": {"kind": "text", "text": f"{clear} of {total_steps}"},
        },
    ]


def _chain(set_results) -> dict[str, Any]:
    """Region 4 — nine cells, and a red one NAMES its blocker (`BR-RBS-027`)."""
    cells = []
    for position, (key, label) in enumerate(STEP_LABELS.items(), start=1):
        rows = _findings(set_results, key)
        blocking = [row for row in rows if row["weight"] == BLOCKER]
        state = CHAIN_FAILED if blocking else (CHAIN_WARNED if rows else CHAIN_OK)
        cells.append(
            {
                "id": key,
                "position": position,
                "label": label,
                "state": state,
                "note": (blocking or rows or [{}])[0].get("reason") if rows else None,
            }
        )
    return {"label": "Cutover", "cells": cells}


def _reconciled(balances, counts, currency) -> dict[str, Any]:
    """Region 6–7 — Counts and totals, **Legacy file · Loaded · Difference**.

    ⚠ **THE HEADINGS ARE THE FILE'S AND OURS, NOT B14 RULE 34's PAIR.** Rule 34
    fixes *Recorded* and *In the books* for **held here versus in the books** —
    two records of OUR OWN money. This table compares the OLD SYSTEM's figure
    against ours, which is a different pair of things, and `RBS-006-R2`'s own
    build sheet writes `Legacy file` and `Loaded`. Runbook 9's tie-out does use
    rule 34's pair, in the same product, three files away — the two are not
    inconsistent, they are about different comparisons.
    """
    loaded = counts.get("loaded") or {}
    present = bool(counts.get("file_present"))
    file_accounts = counts.get("file_accounts", 0)

    # ⚠ **AN ABSENT FILE PRINTS `—` IN EVERY LEGACY CELL AND IN EVERY
    # DIFFERENCE, AND `0` WOULD BE A LIE.** *The old system says nobody owes
    # anything* and *nobody gave us the old system's figures* are different
    # statements and only one of them is a reconciliation. `DEF-127`'s lesson —
    # a zero that means *I do not know* — applied to a table instead of a
    # column. The file carries no premises or meter count at all, so those two
    # legacy cells are `—` even when a file IS present: this runbook does not
    # invent a figure it was never given.
    def _count_row(rid: str, label: str, legacy: Any, ours: Any) -> dict[str, Any]:
        known = legacy is not None
        return {
            "id": rid,
            "cells": {
                "what": {"kind": "text", "text": label},
                "legacy": {"kind": "text", "text": str(legacy) if known else "—"},
                "loaded": {"kind": "text", "text": str(ours)},
                "difference": {"kind": "text", "text": str(ours - legacy) if known else "—"},
            },
        }

    legacy_total = balances.get("legacy_total")
    off_by = balances.get("total_off_by")
    rows = [
        _count_row(
            "accounts", "Accounts", file_accounts if present else None, loaded.get("accounts", 0)
        ),
        _count_row("premises", "Premises", None, loaded.get("premises", 0)),
        _count_row("meters", "Meters", None, loaded.get("meters", 0)),
        {
            "id": "receivables",
            "cells": {
                "what": {"kind": "text", "text": "Receivables"},
                "legacy": {
                    "kind": "money",
                    "amount": "—" if legacy_total is None else money2(legacy_total),
                    "currency": currency,
                },
                "loaded": {
                    "kind": "money",
                    "amount": money2(balances.get("loaded_total") or 0),
                    "currency": currency,
                },
                "difference": {
                    "kind": "money",
                    "amount": "—" if off_by is None else money2(off_by),
                    "currency": currency,
                },
            },
        },
    ]
    return {
        "heading": "Counts and totals",
        "columns": [
            {"key": "what", "label": ""},
            {"key": "legacy", "label": "Legacy file", "numeric": True},
            {"key": "loaded", "label": "Loaded", "numeric": True},
            {"key": "difference", "label": "Difference", "numeric": True},
        ],
        "rows": rows,
        "tiesLabel": "Ties",
    }


def _records(findings, blockers, warnings, set_results) -> dict[str, Any]:
    """Region 8–10 — every finding, with the screen that settles it."""
    return {
        "columns": [
            {"key": "finding", "label": "What"},
            {"key": "affects", "label": "Affects"},
            {"key": "weight", "label": "Weight"},
            {"key": "fix", "label": "Fix"},
        ],
        "rows": [
            {
                "id": str(index),
                "cells": {
                    "finding": {"kind": "text", "text": row["reason"]},
                    "affects": {"kind": "text", "text": row["affects"]},
                    "weight": {
                        "kind": "pill",
                        "label": "Blocker" if row["weight"] == BLOCKER else "Warning",
                        "tone": "danger" if row["weight"] == BLOCKER else "warning",
                    },
                    "fix": {"kind": "link", "label": row["fix_label"], "to": row["fix_route"]},
                },
                "meta": {"decided_by_rule": row["decided_by_rule"], "step": row["key"]},
            }
            for index, row in enumerate(findings, start=1)
        ],
        "total": len(findings),
        "chips": [
            {"id": "all", "label": "All", "count": len(findings)},
            {"id": "blockers", "label": "Blockers", "count": len(blockers)},
            {"id": "warnings", "label": "Warnings", "count": len(warnings)},
        ],
        "empty": {
            "title": "Nothing is in the way.",
            "helper": "Every balance and count arrived.",
        },
        # ⚠ CARRIED, NOT DRAWN — what each step actually LOOKED AT. An empty
        # file and a correct migration produce different numbers here, and a
        # reader can tell them apart (hard-won law 7).
        "checked": {
            key: _serialisable((set_results.get(key) or {}).get("checked", {}))
            for key in STEP_LABELS
        },
    }


def _serialisable(checked: Any) -> Any:
    """`checked` minus the parsed file — a report is JSON and is FROZEN.

    ⚠ **`LegacyFile` IS CARRIED ON `set_results` SO THE STEPS SHARE ONE PARSE
    AND IT MUST NEVER REACH THE REPORT.** `BR-RBS-020` freezes the report into
    `runbook_runs.report`, which is `jsonb`; a dataclass there is a
    `TypeError` at close, and the run would be marked failed on a correct
    comparison. Stripped HERE rather than at the step, because the step's own
    later readers need the object.
    """
    if isinstance(checked, dict):
        return {
            key: _serialisable(value)
            for key, value in checked.items()
            if not isinstance(value, LegacyFile)
        }
    if isinstance(checked, (list, tuple)):
        return [_serialisable(one) for one in checked]
    if isinstance(checked, Decimal):
        return str(checked)
    if isinstance(checked, date):
        return checked.isoformat()
    return checked


# ── the pinned set ────────────────────────────────────────────────────────


def resolve(ctx):
    """One subject: the tenant being cut over.

    ⚠ **THE UNIT OF WORK IS THE PLAN ITEM AND THE SUBJECT IS THE TENANT, AND
    THOSE ARE DIFFERENT DECLARATIONS ON PURPOSE** (`BR-RBS-019`). A cutover is
    one estate compared against one file; the thing a person then works through
    is the plan's items. `RB-102`'s own card says *"Tenant + uploaded file · plan
    items"* and this is that sentence in code.

    Every step is SET mode, so the pinned set of one is walked once per step —
    which is exactly what `BR-RBS-023` says a set step does, and why a cutover
    over 40,000 accounts costs nine queries rather than 360,000.
    """
    return [
        SubjectRef(
            subject_type="tenant",
            subject_id=str(ctx.tenant_id or ""),
            label=str(_params(ctx).get("plan") or "Cutover"),
        )
    ]


RUNBOOK = RunbookDefinition(
    key="cutover_readiness",
    name="Cutover reconciliation",
    kind=models.KIND_CHECK,
    category="onboarding_cutover",
    subject_type="tenant",
    unit_of_work="plan item",
    triggers=(models.TRIGGER_MANUAL,),
    tags=("Platform", "Billing"),
    # ⚠ DECLARED, AND THE ENGINE DOES NOT YET ACT ON IT — `BR-RBS-027` is wired
    # by wave `I` task `I4`, which has not landed. The contract validates the
    # name and the registry validates that it exists; step 1 says out loud that
    # the sub-run did not run, rather than drawing a tick nobody computed.
    requires="configuration_check",
    parameters=(
        Parameter(name="plan", type=PARAM_REF_OBJECT, label="Cutover plan", required=True),
        Parameter(
            name="trial_balance", type=PARAM_FILE, label="Legacy balances", required=True
        ),
        Parameter(
            name="money_tolerance",
            type=PARAM_MONEY,
            label="Money tolerance",
            # ⚠ A STRING, NEVER A FLOAT. This value lives in
            # `runbook_versions.definition`, which is `jsonb` — there is no
            # NUMERIC(18,4) in there and no column type will catch a float
            # (hard rule 2, `03-field-map.md` D-3). `Parameter.__post_init__`
            # refuses one, which is the only thing that can.
            default="0.01",
        ),
        Parameter(
            name="total_tolerance",
            type=PARAM_PERCENT,
            label="Total tolerance",
            default="0.05",
        ),
        Parameter(
            name="open_items_at",
            type=PARAM_ENUM,
            label="Open items at",
            choices=(GRAIN_INVOICE, GRAIN_ACCOUNT),
            default=GRAIN_INVOICE,
        ),
        Parameter(
            name="sample_data_must_be_gone",
            type=PARAM_TOGGLE,
            label="Sample data must be gone",
            default=True,
        ),
        Parameter(
            name="coverage_grid_must_pass",
            type=PARAM_TOGGLE,
            label="Coverage grid must pass",
            default=True,
        ),
    ),
    resolve=resolve,
    report=report,
    steps=(
        Step(key=STEP_CONFIG, label=STEP_LABELS[STEP_CONFIG], mode=MODE_SET, run=step_config),
        Step(key=STEP_COUNTS, label=STEP_LABELS[STEP_COUNTS], mode=MODE_SET, run=step_counts),
        Step(
            key=STEP_BALANCES, label=STEP_LABELS[STEP_BALANCES], mode=MODE_SET, run=step_balances
        ),
        Step(
            key=STEP_DEPOSITS, label=STEP_LABELS[STEP_DEPOSITS], mode=MODE_SET, run=step_deposits
        ),
        Step(key=STEP_PLANS, label=STEP_LABELS[STEP_PLANS], mode=MODE_SET, run=step_plans),
        Step(
            key=STEP_NUMBERING,
            label=STEP_LABELS[STEP_NUMBERING],
            mode=MODE_SET,
            run=step_numbering,
        ),
        Step(key=STEP_SAMPLE, label=STEP_LABELS[STEP_SAMPLE], mode=MODE_SET, run=step_sample),
        Step(
            key=STEP_COVERAGE, label=STEP_LABELS[STEP_COVERAGE], mode=MODE_SET, run=step_coverage
        ),
        Step(
            key=STEP_PLAN_ITEMS,
            label=STEP_LABELS[STEP_PLAN_ITEMS],
            mode=MODE_SET,
            run=step_plan_items,
        ),
    ),
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-008 (EP-RBS-03; RB-102; RBS-004-R2 / RBS-006-R2 build sheets; PO ruling 2026-09-05 quoted verbatim above)
# generated: 2026-09-07 by the CR-075 wave J build lane
# checklist: A✔ B✔ C✔ D✔(GET · POST /cutover-plans · POST /cutover-plans/{id}/items/{seq}/evidence — apps/runbooks/cutover_api.py) E=n/a(no screen: RBS-006 renders it from the twelve blocks, RB-020) F✔ G✔ H=n/a(no 🔒 path: this composes no idempotency key, touches no rating math and posts no ledger line)
# gates: pytest tests/test_us_rbs_008_cutover_readiness.py · tests/test_us_rbs_015_conformance.py · G115 (the import census) · G6 (no float on money)
# exceptions: (1) the trial balance is the `file` PARAMETER's own content, NOT a staged import run — argued in the module docstring: `trial_balance` is not one of the six IMPORT_TARGETS, so the runner route is a check incapable of passing (hard-won law 7) · (2) step 1 declares `requires` and reports that the sub-run did NOT run — wave I task I4 wires it and has not landed · (3) step 5 (plans and levels carried) is a STATED ABSENCE: nothing records that a plan was migrated (OQ-RBS-1738) · (4) step 8 (coverage grid) is a stated absence: wave G is unbuilt
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

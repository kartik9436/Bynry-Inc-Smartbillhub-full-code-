# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-015 · US-RBS-002 (EP-RBS-01) — CR-075 wave B task B1: the
#           declared object every runbook is, and every refusal it can earn.
# Rules:    BR-RBS-002 (a Check is CONSTRUCTED without action ports; a write
#           attempt raises rather than being refused at runtime) · BR-RBS-001
#           (kind is check|action, declared at creation) · BR-RBS-019 (a runbook
#           declares its unit of work) · BR-RBS-021 (the block vocabulary is
#           fixed at twelve) · BR-RBS-022 (a write is a named port; work items
#           and audit rows are the ENGINE's) · BR-RBS-023 (a step declares its
#           mode) · BR-RBS-024 (exactly one category from the fixed sixteen)
# Tests:    06-backend/tests/test_us_rbs_015_conformance.py (TC-RBS-1,
#           TC-RBS-15, TC-RBS-17, TC-RBS-19)
# Impacts:  apps/runbooks/registry.py · apps/runbooks/engine/executor.py ·
#           apps/runbooks/definitions/ (one module per runbook, from wave C)
# ───────────────────────────────────────────────────────
"""The object a runbook declares — and every way declaring it wrongly fails.

**EVERY REFUSAL IN THIS FILE HAPPENS AT CONSTRUCTION.** A runbook is a module
imported at `AppConfig.ready()`, so a declaration this file rejects stops the
process from starting and names itself. That is the difference `US-RBS-002`
turns on: *report-only* as a **capability** rather than as a sentence in a
docstring, which is hard-won law 1 exactly.

⚠ **THE ONE THIS WAVE EXISTS TO MAKE TRUE IS `BR-RBS-002`:** a Check is
constructed **without action ports**. Not *with ports it must not call* — with
none at all. Binding one to a `kind = "check"` runbook raises here, at
construction, before any run exists, and the message names the runbook key and
every offending port. A version of this rule that refuses at write time would
mean a Check with a writer exists in memory on a live schedule, and the promise
that two people can press **Run ▶** on a thousand accounts is gone.

CITE THE DECLARATIONS BY NAME, NEVER BY THE COUNT
--------------------------------------------------
`12-the-contract.md` §1 says *seven-part object* in its prose and lists **nine**
declarations in its own figure, and records the gap rather than picking a
number: `requires` was added by `RB-036` after the word *seven* was written, and
`ports[]` was originally counted with the write story. This file declares, in
this order — `key` · `kind` · `subject_type` · `unit_of_work` · `triggers` ·
`category` · `tags` · `parameters` · `resolve` · `steps` · `guards` ·
`requires` · `ports` · `report`. **Nothing here depends on how many that is.**

THE FOUR CLOSED VOCABULARIES, AND WHERE EACH ONE LIVES
-------------------------------------------------------
* the **sixteen categories** and the **twelve subject types** are
  `models.CATEGORIES` / `models.SUBJECT_TYPES` — wave A put them beside the
  columns that store them, and importing them here is what stops a second list
  drifting from the first;
* the **eleven parameter types** and the **twelve report blocks** are declared
  below, because no column stores either: parameters live inside
  `runbook_versions.definition` and blocks inside `runbook_runs.report`, both
  `jsonb`, where **no database constraint can see a wrong value**
  (`03-field-map.md` D-3). If they are not enforced here they are not enforced.

⚠ **THE TWELVE BLOCK NAMES ARE MINTED HERE AND EXIST NOWHERE ELSE YET.**
`09-component-inventory.md` names them in prose — *Verdict · KPIs · Chain ·
Records · Breakdown · Reconciled · Ranked · Sentence · Facts · Action · Row
decisions · Downloads* — and no machine spelling of them existed in the
repository before this file (grepped 2026-09-06: zero hits for `block_type`,
`row_decisions` or a quoted `"verdict"` anywhere under `04-docs/` or
`06-backend/`). The mapping is one-to-one and snake_case; the renderer of wave
C reads THIS tuple, so a thirteenth name added here without three runbooks that
need it is the thing `BR-RBS-021` forbids.

WHAT IS DELIBERATELY *NOT* ENFORCED HERE, AND WHY EACH
-------------------------------------------------------
1. **The category does NOT restrict which ports a runbook may hold.**
   `BR-RBS-024` ends *"the category names the owning module whose ports it may
   call"*, and `12-the-contract.md` §5 restates it — *"a Collections runbook
   reaches `payments`' ports and no other module's"*. **Enforcing that at
   construction would refuse all nine Actions the same contract defines, in its
   own §8 coverage table.** Runbook 8 is Collections (owning module `payments`)
   and holds `queue_notice` (`notifications`) and `apply_fee` (`billing`);
   runbook 14 is Finance (owning module `ledger`, which owns **no ports at
   all**) and holds `record_match` (`payments`); all three Data Sync runbooks
   name `integrations`, which likewise owns none. Counted: **15 of the 21 port
   bindings in §8 violate the sentence, and 9 of the 9 Actions violate it at
   least once.** So the sentence is read as *the module the runbook is ABOUT*,
   the allow-list is the runbook's own `ports[]` — which is what §8 calls *"the
   whole safety story"* — and the divergence is `DEF-RBS-4262` with a
   decision-log row of 2026-09-06.
2. **`unit_of_work` is checked for PRESENCE, not for not-being-a-raw-row.**
   `BR-RBS-019`'s second half is marked in `US-RBS-015` itself as *"declared
   here, first enforced in `EP-RBS-05`"* — the enforcement needs a subject
   whose roll-up exists to compare against (176,640 intervals → 1,840
   meter-days), and there is no such runbook until phase 5. A word-blocklist
   here would be a guess wearing a gate's clothes.
3. **`requires` is checked for SHAPE here and for EXISTENCE in the registry**,
   because the Check it names may legitimately be imported after this module.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from apps.runbooks import interfaces, models
from apps.runbooks.boundary import PortDeclaration

# ── the vocabularies no column can hold ───────────────────────────────────

#: The ELEVEN parameter types (`09-component-inventory.md` part 2). ⚠ There is
#: no `rate` type and there is not going to be one: a rate never appears as a
#: knob, only as a result cell, and it displays at FOUR decimals where money
#: displays at two (`OQ-620`, PO 2026-08-27). A twelfth type added here is a new
#: input control on twenty-six setup screens, which is why the list is closed.
PARAM_MONEY = "money"
PARAM_INTEGER = "integer"
PARAM_DAYS = "days"
PARAM_PERCENT = "percent"
PARAM_ENUM = "enum"
PARAM_TOGGLE = "toggle"
PARAM_TEXT = "text"
PARAM_WINDOW = "window"
PARAM_REF_SETTING = "ref:setting"
PARAM_REF_OBJECT = "ref:object"
PARAM_FILE = "file"
PARAMETER_TYPES = (
    PARAM_MONEY,
    PARAM_INTEGER,
    PARAM_DAYS,
    PARAM_PERCENT,
    PARAM_ENUM,
    PARAM_TOGGLE,
    PARAM_TEXT,
    PARAM_WINDOW,
    PARAM_REF_SETTING,
    PARAM_REF_OBJECT,
    PARAM_FILE,
)

#: The word a tenant stores when it wants **everything in the domain**, and it
#: is stored as THE WORD (`BR-RBS-042` clause 1, PO 2026-09-06).
#:
#: ⚠ **EXPANDING IT AT CONFIGURE TIME IS THE FAILURE THIS CONSTANT EXISTS TO
#: PREVENT, AND THE FAILURE IS SILENT.** A utility that sets *services = all*
#: while it sells Water and Sewer, and enables Trash next month, must get
#: **three** on its next run. Write `["water", "sewer"]` into the tenant's
#: settings at the moment they press Save and Trash is outside every runbook set
#: to *all* for ever — no error, no screen change, nothing on any screen to see.
#: `services.run_parameters()` expands it when the RUN starts and `BR-RBS-009`
#: pins it there.
PARAM_ALL = "all"

#: The TENANT-RESOLVED domains a parameter may draw from — the closed
#: vocabulary, and it is closed for the same reason `PARAMETER_TYPES` is: a new
#: domain is a new read through a seam, a new resolver and a new page of a list
#: endpoint, not a string somebody types into a definition.
#:
#: ⚠ **A DOMAIN AND `choices` ARE THE SAME IDEA FROM TWO SOURCES, AND A
#: PARAMETER MAY NAME ONLY ONE OF THEM.** `choices` is the RUNBOOK's own fixed
#: vocabulary — *Blockers and warnings · Blockers only* is the same list at
#: every utility and is not a fact about the tenant. A `domain` is read from the
#: tenant's own data at the moment the screen or the run asks for it, and
#: `BR-RBS-042` clause 2 is exactly that: *"a two-service utility sees two; a
#: utility with three plans sees three; an empty domain says so"*. Declaring
#: both would give one input two lists that can disagree.
#:
#: ⚠ **`account` IS UNBOUNDED AND THE OTHER IS NOT, AND THAT DIFFERENCE IS PART
#: OF THE DECLARATION RATHER THAN A NOTE.** `service` is bounded by the platform
#: catalogue — eleven, of which a tenant enables some. `account` scales with the
#: utility: 40,000 at the top of T5, and `NFR-3` binds every list this product
#: serves. So `domains.page()` slices `account` **in SQL** and nothing anywhere
#: materialises the whole set to draw a dropdown. See `domains.DOMAIN_IS_BOUNDED`.
DOMAIN_SERVICE = "service"
DOMAIN_PERIOD = "period"
DOMAIN_ACCOUNT = "account"
DOMAINS = (DOMAIN_SERVICE, DOMAIN_PERIOD, DOMAIN_ACCOUNT)

#: The TWELVE report blocks. A report naming a thirteenth is refused **at run
#: close** and never reaches the screen (`BR-RBS-021`, `TC-RBS-15`,
#: `TC-RBS-16`) — see `validate_report()`, which the executor calls before a run
#: is marked done. Refusing at RENDER instead would leave a half-drawn screen.
BLOCK_VERDICT = "verdict"
BLOCK_KPIS = "kpis"
BLOCK_CHAIN = "chain"
BLOCK_RECORDS = "records"
BLOCK_BREAKDOWN = "breakdown"
BLOCK_RECONCILED = "reconciled"
BLOCK_RANKED = "ranked"
BLOCK_SENTENCE = "sentence"
BLOCK_FACTS = "facts"
BLOCK_ACTION = "action"
BLOCK_ROW_DECISIONS = "row_decisions"
BLOCK_DOWNLOADS = "downloads"
BLOCK_TYPES = (
    BLOCK_VERDICT,
    BLOCK_KPIS,
    BLOCK_CHAIN,
    BLOCK_RECORDS,
    BLOCK_BREAKDOWN,
    BLOCK_RECONCILED,
    BLOCK_RANKED,
    BLOCK_SENTENCE,
    BLOCK_FACTS,
    BLOCK_ACTION,
    BLOCK_ROW_DECISIONS,
    BLOCK_DOWNLOADS,
)

#: The FIELDS each block's payload must carry, and the ones it may.
#:
#: ⚠ **THIS EXISTS BECAUSE THE NAME CHECK BELOW WAS ONLY HALF THE CONTRACT, AND
#: THE OTHER HALF CRASHED A SCREEN (`DEF-RBS-4352`).** `validate_report` refused
#: a thirteenth NAME and asked nothing about what was inside. So the collections
#: ladder shipped `breakdown {by, rows, rungs}` where the renderer needs
#: `{heading, columns, rows}`, and `RBS-006` drew an error boundary instead of
#: 835 planned notices. **Every test on both sides passed**: the backend
#: asserted the name, and the report crosses the wire as untyped JSON that
#: `GET /runbooks/runs/{id}/report` passes through deliberately, so it never
#: meets `types.ts` and `tsc` cannot see the mismatch either. It is the same
#: shape as `DEF-RBS-4284`, which was fixed for exactly ONE runbook by pinning
#: its report as a fixture — a fix that could not generalise, because a fixture
#: covers the runbook it was taken from and no other.
#:
#: ⚠ **THE RENDERER IS THE AUTHORITY AND THIS IS A COPY OF IT.** This file
#: already rules the direction — *"the twelve shapes are the renderer's (wave
#: C)"* — so these names are transcribed from
#: `07-frontend/src/features/runbooks/blocks/types.ts` and must not be edited
#: to match a runbook that is failing. **`test_us_rbs_015_conformance.py` parses
#: that file and asserts this map against it**, so the two cannot drift: change
#: a payload there and this goes red naming the field.
#:
#: Optional fields are listed so an UNEXPECTED key can be refused too. That
#: matters as much as a missing one: `rungs` was real data the ladder computed
#: and no block draws, so a clerk lost it silently while the screen crashed on
#: what was absent.
PAYLOAD_FIELDS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    BLOCK_VERDICT: (frozenset({"word", "tone", "count"}), frozenset({"detail"})),
    BLOCK_KPIS: (frozenset({"tiles"}), frozenset()),
    BLOCK_CHAIN: (frozenset({"label", "cells"}), frozenset()),
    BLOCK_RECORDS: (
        frozenset({"columns", "rows", "total", "empty"}),
        frozenset({"display", "grid", "chips"}),
    ),
    BLOCK_BREAKDOWN: (frozenset({"heading", "columns", "rows"}), frozenset()),
    BLOCK_RECONCILED: (
        frozenset({"heading", "columns", "rows", "tiesLabel"}),
        frozenset(),
    ),
    BLOCK_RANKED: (frozenset({"heading", "rows"}), frozenset()),
    BLOCK_SENTENCE: (frozenset({"tone", "text"}), frozenset({"label"})),
    BLOCK_FACTS: (frozenset({"rows"}), frozenset({"heading"})),
    # ⚠ A UNION, not a record: `enabled: false` REQUIRES `reason`, because B14
    # draws a control a user may not use as disabled WITH its reason, never
    # hidden. `reason` is therefore conditionally required — see
    # `_payload_problems`, which is the one place that conditional lives.
    BLOCK_ACTION: (frozenset({"label", "tier", "enabled"}), frozenset({"reason"})),
    BLOCK_ROW_DECISIONS: (
        frozenset({"heading", "columns", "rows", "choices"}),
        frozenset(),
    ),
    BLOCK_DOWNLOADS: (frozenset({"files"}), frozenset()),
}


#: Two step modes and no third (`BR-RBS-023`). **Set** runs once over the whole
#: pinned set — a tie-out, a totals comparison, each meter's own normal computed
#: before the per-record pass. **Per-record** runs once per subject, each inside
#: its own SAVEPOINT.
MODE_PER_RECORD = "per_record"
MODE_SET = "set"
STEP_MODES = (MODE_PER_RECORD, MODE_SET)

#: The FIVE trigger rows of `12-the-contract.md` §4, over THREE kinds. Manual
#: and Schedule wait on nothing; the three event names are BLOCKED-BY the
#: integrations substrate (`CR-069`), and a runbook whose only trigger is one of
#: them is not runnable until that lands — a screen must SAY so rather than
#: offering a **Run ▶** that refuses (`RB-022`).
TRIGGER_MANUAL = models.TRIGGER_MANUAL
TRIGGER_SCHEDULE = models.TRIGGER_SCHEDULE
TRIGGERS = (TRIGGER_MANUAL, TRIGGER_SCHEDULE, *models.EVENT_KINDS)

#: The thirteen port names, taken from the port declarations themselves rather
#: than re-typed. ⚠ `raise_work_item` IS NOT ONE OF THEM and is refused BY NAME
#: below: raising a work item and writing an audit row are ENGINE acts, which is
#: the only thing that lets a Check populate `RBS-007` while holding no writer
#: at all. The source specification's *"four named calls"* sentence says
#: otherwise in seven places and is stale in two ways at once
#: (`12-the-contract.md` §6).
ENGINE_ACTS = ("raise_work_item", "write_audit_row", "write_note")


class RunbookContractError(Exception):
    """A declaration this product refuses to load.

    Raised at CONSTRUCTION — during the import that `AppConfig.ready()`
    performs — so the process does not start and the message names the runbook.
    It is deliberately NOT a `NotImplementedError("OQ-…")`: nothing here is
    waiting on an open question, and `G8` reads a `NotImplementedError` as a
    blocked story.
    """


# ── the declaration parts ─────────────────────────────────────────────────


@dataclass(frozen=True)
class Parameter:
    """One knob, typed. The setup renderer draws it from `type` and nothing else.

    ⚠ **`money` and `percent` CANNOT BE HELD TO THEIR PRECISION BY A COLUMN.**
    A parameter lives inside `runbook_versions.definition`, which is `jsonb`;
    there is no `NUMERIC(18,4)` in there. Hard rule 2 — money stored to 4
    decimals, percentages to 6, both displayed at 2 — is therefore the
    validator's and the renderer's to keep, and a float written into that
    document is a breach **no database constraint can see** (`03-field-map.md`
    D-3). This class refuses a float on a money or percent parameter for that
    reason; nothing downstream can.
    """

    name: str
    type: str
    label: str
    required: bool = False
    default: Any = None
    #: `enum` only — the declared list. B14 rule 8 makes it searchable above five.
    choices: tuple[str, ...] = ()
    #: `ref:setting` only — the Settings key this value is READ from. The value
    #: is never duplicated into the runbook's own parameters: duplicating one is
    #: how a utility ends up with two ladders and no way to tell which one sent
    #: the notice.
    setting_key: str | None = None
    #: The TENANT-RESOLVED list this input draws from, one of `DOMAINS`, or
    #: `None` when the input has no list at all (a money box, a toggle) or
    #: carries the runbook's own fixed vocabulary in `choices`.
    domain: str | None = None
    #: May a tenant pick SEVERAL values, and therefore *all*? `BR-RBS-042`: *one
    #: value, several, or all*. ⚠ **`all` IS ONLY EVER LEGAL ON A `multi`
    #: PARAMETER**, because *all* of a single-value picker is not a choice a
    #: person could act on — *"run the test bill against every account"* is a
    #: different runbook, not a value of this one.
    multi: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise RunbookContractError("a parameter with no name cannot be drawn or read")
        if self.type not in PARAMETER_TYPES:
            raise RunbookContractError(
                f"parameter {self.name!r} declares type {self.type!r}, which is not one of the "
                f"eleven: {', '.join(PARAMETER_TYPES)}. A twelfth type is a new input control on "
                "twenty-six setup screens, not a line in a definition (09-component-inventory.md)."
            )
        if self.type == PARAM_ENUM and not self.choices and self.domain is None:
            # ⚠ **`domain` IS THE SECOND WAY AN ENUM GETS ITS LIST, ADDED IN
            # WAVE `T`** (`BR-RBS-042` clause 2). Until then `choices` was the
            # only one, so an enum drawing from the TENANT's data — its
            # services, its posted months — had to be declared with a
            # hardcoded list of eleven, which is the thing the rule forbids.
            # A dropdown of nothing is still refused; what changed is that the
            # list may now be read rather than written down.
            raise RunbookContractError(
                f"parameter {self.name!r} is an enum with neither choices nor a domain: a "
                "dropdown of nothing. Give it the runbook's own fixed vocabulary (choices) or "
                "the tenant's own list (domain) — BR-RBS-042 clause 2."
            )
        if self.type == PARAM_REF_SETTING and not self.setting_key:
            raise RunbookContractError(
                f"parameter {self.name!r} is ref:setting and names no setting_key. A ref:setting "
                "is READ from Settings and never duplicated here (09-component-inventory.md)."
            )
        if self.type in (PARAM_MONEY, PARAM_PERCENT) and isinstance(self.default, float):
            raise RunbookContractError(
                f"parameter {self.name!r} is {self.type} with a float default {self.default!r}. "
                "Hard rule 2: money is stored to 4 decimals and percentages to 6, never as a "
                "float — and this value lives in jsonb, where no column type will catch it."
            )
        self._check_domain()

    # -- the domain (`BR-RBS-042`) ----------------------------------------

    def _check_domain(self) -> None:
        """Four refusals — and the fifth one was written, proved, and REMOVED.

        ⚠ **THE ONE THAT IS NOT HERE: *a `ref:object` must name a domain*.** It
        is a true sentence — a picker with no list is a picker over nothing —
        and it was written, run, and it **refused four shipped runbooks at
        import**: `bank_reconciliation`'s *statement*, `cash_application`'s *the
        file you uploaded*, `gis_reconciliation`'s *parcel file* and
        `read_validation`'s *interval batch*. That is `DEF-RBS-4262` exactly one
        rule along — a construction rule that refuses the runbooks the contract
        itself defines is not enforceable as written, however true it reads.

        **Why those four are different, and it is a real distinction rather
        than an excuse.** They are supplied **at run time** by the event that
        started the run — a file landed, a person uploaded one — not chosen on a
        setup screen and saved. This product has **no list read for any of
        them**: `metering_seam.staged_import_batch(target)` answers *the one
        staged batch*, not *the batches you could pick from*, and payments and
        integrations publish nothing of that shape at all. So the domain those
        four need is four selectors in three other modules, which is a wave of
        its own and is filed rather than guessed.

        **Counted, so the blind spot has a number beside it** (hard-won law 7):
        **five** `ref:object` inputs exist; **one** declares a domain
        (`test_bill`'s *Account*, given one by this wave), **four** do not.

        What IS refused below: a domain name nothing resolves · a domain AND
        `choices` on one input · several values with nothing to pick them from ·
        and the word *all* on an input that takes one value.
        """
        if self.domain is not None and self.domain not in DOMAINS:
            raise RunbookContractError(
                f"parameter {self.name!r} names domain {self.domain!r}, which is not one of "
                f"{', '.join(DOMAINS)}. A new domain is a seam read, a resolver and a page of a "
                "list endpoint (BR-RBS-042 clause 2), not a string in a definition."
            )
        if self.domain is not None and self.choices:
            raise RunbookContractError(
                f"parameter {self.name!r} declares BOTH choices and domain {self.domain!r}. "
                "choices is the runbook's OWN fixed vocabulary — the same list at every utility; "
                "a domain is read from the tenant's data. Two lists behind one input can disagree."
            )
        if self.multi and self.domain is None and not self.choices:
            raise RunbookContractError(
                f"parameter {self.name!r} accepts several values and names nothing to pick them "
                "from. BR-RBS-042: one value, several, or ALL — of a declared domain."
            )
        if self.default == PARAM_ALL and not self.multi:
            raise RunbookContractError(
                f"parameter {self.name!r} defaults to {PARAM_ALL!r} and accepts one value. "
                "'all' is a RULE rather than a value (BR-RBS-042 clause 1) and it is only "
                "meaningful where several values are."
            )


@dataclass(frozen=True)
class Step:
    """One step. `mode` has NO default, so a step with no mode cannot be built.

    ⚠ **`mode` IS A REQUIRED FIELD ON PURPOSE.** `BR-RBS-023` says *a step
    declares which*, and a default would decide it silently for every step a
    lane forgets. Omit it and Python refuses the `Step(...)` call during the
    import `AppConfig.ready()` performs; pass an empty or unknown value and
    `RunbookDefinition` refuses, naming the runbook AND the step. Both are load
    failures, which is what the plan's *"a step with no mode"* asks for.

    `writes` is the step's own claim about itself. A Check whose step claims
    `writes=True` is refused at construction, before `ports` is even reached —
    the claim and the capability must agree, and the capability is what
    `BR-RBS-002` removes.
    """

    key: str
    label: str
    mode: str
    run: Callable[..., Any]
    writes: bool = False


@dataclass(frozen=True)
class Guard:
    """An absolute skip, evaluated BEFORE any step, and it cannot be switched off.

    `BR-RBS-012`. `RBS-004.4` draws the control **disabled with its reason**
    rather than hiding it, because a guard a clerk cannot see is a guard they
    will assume is absent.
    """

    key: str
    label: str
    applies: Callable[..., bool]


@dataclass(frozen=True)
class SubjectRef:
    """One member of a pinned scope — what `resolve()` returns.

    ⚠ **`subject_type` is the DECLARED unit, and it is never the raw row**
    (`BR-RBS-019`). Read validation walks the **meter-day**: 176,640 intervals
    become 1,840 records, and a per-record savepoint stays cheap.

    ⚠ `premise` is `premises`, the product's own word and its ONE address home
    (hard rule 8, `BR-MET-1161`). A runbook that wants an address WALKS TO THE
    PREMISES; nothing else in the product has an address column to read.
    """

    subject_type: str
    subject_id: str
    label: str = ""

    def __post_init__(self) -> None:
        if self.subject_type not in models.SUBJECT_TYPES:
            raise RunbookContractError(
                f"subject type {self.subject_type!r} is not one of the twelve: "
                f"{', '.join(models.SUBJECT_TYPES)}"
            )


@dataclass(frozen=True)
class Block:
    """One block of a report. Twelve names, and a thirteenth is refused at close.

    `payload` is whatever that block draws and is deliberately untyped here:
    the twelve shapes are the renderer's (wave C), and typing them in the
    backend would mean two declarations of one thing that can disagree. What is
    typed is the NAME, because that is what `BR-RBS-021` closes.
    """

    block: str
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.block not in BLOCK_TYPES:
            raise RunbookContractError(
                f"report block {self.block!r} is not one of the twelve: {', '.join(BLOCK_TYPES)}. "
                "A thirteenth needs THREE runbooks that cannot be drawn without it "
                "(BR-RBS-021) — one runbook wanting a new shape should compose the twelve "
                "differently."
            )

    def as_dict(self) -> dict[str, Any]:
        return {"block": self.block, "payload": self.payload}


@dataclass(frozen=True)
class Finding:
    """One thing waiting on a person, as a runbook hands it to the ENGINE.

    ⚠ **A RUNBOOK RETURNS FINDINGS; THE ENGINE WRITES `work_items`**
    (`BR-RBS-022`). That is the whole reason a Check with no writer at all can
    populate `RBS-007`: raising a work item is an ENGINE ACT and is refused BY
    NAME as a port, so making it one would give **every** Check the ability to
    write. This class is the handover — plain data, no row, no id.

    ⚠ **`kind` IS THE HALF OF THE FINGERPRINT THAT MUST NOT MOVE, AND IT IS THE
    QUESTION RATHER THAN THE ANSWER.** The daily pre-bill sweep raises the same
    missing read for thirty days and that must be **one item ageing, not thirty
    items** (`BR-RBS-017`, `TC-RBS-10`). So `kind` names what was ASKED — *the
    tax region on water* — and never the sentence that came back, because a
    reworded `title` would otherwise mint a second row and the age a clerk reads
    would reset to today.

    ⚠ **AND THE FINGERPRINT NEVER CONTAINS THE RUN ID.** `US-RBS-006` §5 says so
    in those words. With the run in it every run makes a new row and the screen
    becomes a log — which is `TC-RBS-006.2`'s *must first fail on* exactly.

    `fix_route` is REQUIRED for anything a runbook raises (`BR-RBS-011`): a
    finding a clerk cannot act on is a finding we should not have shown them.
    """

    kind: str
    title: str
    fix_route: str
    #: 0–100. The list sorts by weight, then age. 100 stops billing; 50 is
    #: before go-live; 0 is routine. It is an INTEGER because `work_items.weight`
    #: is one and a screen turns it back into a word (B14 rule 32 — no internal
    #: code in clerk copy).
    weight: int = 0
    #: What the finding is ABOUT, in the clerk's words — *240 accounts*, *Water*.
    #: Never a database id (B14 rule 31).
    subject_ref: str = ""
    #: The pinned subject this finding belongs to, when it belongs to one. It
    #: joins the fingerprint so two accounts with the same fault are two items.
    subject_type: str = ""
    subject_id: str = ""

    def __post_init__(self) -> None:
        if not self.kind.strip():
            raise RunbookContractError(
                "a finding with no kind cannot be fingerprinted, so every run would raise it "
                "again as a new row (BR-RBS-017)."
            )
        if not self.title.strip():
            raise RunbookContractError("a finding with no title says nothing to anybody")
        if not self.fix_route.strip():
            raise RunbookContractError(
                f"finding {self.kind!r} names no fix route. BR-RBS-011: a failure names its fix "
                "route, and a failure with no route is a defect in the runbook."
            )


# ── the object itself ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class RunbookDefinition:
    """One runbook, declared. Every refusal below happens at CONSTRUCTION.

    Cite the declarations by NAME, never by the count — `12-the-contract.md`
    §1's prose says *seven-part* and its own figure lists nine, and the file
    records the gap rather than picking a number.
    """

    key: str
    name: str
    kind: str
    category: str
    subject_type: str
    unit_of_work: str
    resolve: Callable[..., Iterable[SubjectRef]]
    report: Callable[..., Sequence[Block]]
    steps: tuple[Step, ...] = ()
    triggers: tuple[str, ...] = (TRIGGER_MANUAL,)
    tags: tuple[str, ...] = ()
    parameters: tuple[Parameter, ...] = ()
    guards: tuple[Guard, ...] = ()
    #: One Check run FIRST, as its own run, linked from step 1. If it fails,
    #: every later step reads **Never reached** and the verdict is No-go
    #: (`BR-RBS-027`, `RB-036`). Its existence is checked by the registry once
    #: every module has been imported, because import order is not declaration
    #: order.
    requires: str | None = None
    #: ⚠ **EMPTY FOR A CHECK, ENFORCED HERE** (`BR-RBS-002`).
    ports: tuple[str, ...] = ()
    #: What the run leaves on somebody's desk — `Sequence[Finding]` from the
    #: same view `report()` is handed. **OPTIONAL, and the absence is the
    #: honest default**: a runbook that raises nothing declares nothing, and a
    #: stub returning `[]` would be indistinguishable from one whose findings
    #: nobody has written yet. `engine.work_items.upsert` calls it at run close
    #: and writes the rows itself (`BR-RBS-022`) — the runbook never touches the
    #: table, which is what lets a Check with no ports populate `RBS-007`.
    findings: Callable[..., Sequence[Finding]] | None = None

    # ── construction is the only gate that matters ────────────────────────

    def __post_init__(self) -> None:
        self._check_identity()
        self._check_category()
        self._check_triggers()
        self._check_parameters()
        self._check_steps()
        self._check_guards()
        self._check_ports()
        self._check_callables()

    # -- identity ---------------------------------------------------------

    def _check_identity(self) -> None:
        if not self.key:
            raise RunbookContractError("a runbook with no key cannot be registered or cited")
        if self.kind not in models.KINDS:
            raise RunbookContractError(
                f"runbook {self.key!r} declares kind {self.kind!r}; it is 'check' or 'action' "
                "and never changes afterwards (BR-RBS-001)."
            )
        if self.subject_type not in models.SUBJECT_TYPES:
            raise RunbookContractError(
                f"runbook {self.key!r} declares subject_type {self.subject_type!r}, which is not "
                f"one of the twelve: {', '.join(models.SUBJECT_TYPES)}"
            )
        if not self.unit_of_work.strip():
            raise RunbookContractError(
                f"runbook {self.key!r} declares no unit_of_work. A runbook declares what it walks "
                "and the unit is NEVER the raw row (BR-RBS-019): read validation walks the "
                "meter-day, so 176,640 intervals become 1,840 records."
            )

    # -- category ---------------------------------------------------------

    def _check_category(self) -> None:
        """One category from the fixed sixteen (`BR-RBS-024`, `TC-RBS-19`).

        ⚠ This checks MEMBERSHIP and nothing else. It deliberately does NOT
        check that every port belongs to the category's owning module — see the
        file docstring, item 1: that sentence would refuse all nine Actions the
        contract itself defines (`DEF-RBS-4262`).
        """
        if self.category not in models.CATEGORIES:
            raise RunbookContractError(
                f"runbook {self.key!r} declares category {self.category!r}, which is not one of "
                f"the sixteen: {', '.join(models.CATEGORIES)}. A seventeenth category needs THREE "
                "runbooks that fit nowhere else (BR-RBS-025)."
            )

    # -- triggers ---------------------------------------------------------

    def _check_triggers(self) -> None:
        if not self.triggers:
            raise RunbookContractError(
                f"runbook {self.key!r} declares no trigger: nothing could ever start it."
            )
        for trigger in self.triggers:
            if trigger not in TRIGGERS:
                raise RunbookContractError(
                    f"runbook {self.key!r} declares trigger {trigger!r}, which is not one of the "
                    f"five rows: {', '.join(TRIGGERS)} — three kinds, of which three rows are "
                    "event names (12-the-contract.md §4)."
                )

    # -- parameters -------------------------------------------------------

    def _check_parameters(self) -> None:
        seen: set[str] = set()
        for parameter in self.parameters:
            if parameter.name in seen:
                raise RunbookContractError(
                    f"runbook {self.key!r} declares parameter {parameter.name!r} twice; a setup "
                    "screen would draw two boxes writing one value."
                )
            seen.add(parameter.name)

    # -- steps ------------------------------------------------------------

    def _check_steps(self) -> None:
        if not self.steps:
            raise RunbookContractError(
                f"runbook {self.key!r} declares no steps: a run of it would examine nothing and "
                "report a clean result, which is the most dangerous shape this product has."
            )
        seen: set[str] = set()
        for step in self.steps:
            if step.key in seen:
                raise RunbookContractError(
                    f"runbook {self.key!r} declares step {step.key!r} twice; the chain block "
                    "would draw one cell for two steps."
                )
            seen.add(step.key)
            if step.mode not in STEP_MODES:
                raise RunbookContractError(
                    f"runbook {self.key!r} step {step.key!r} declares mode {step.mode!r}. A step "
                    f"declares its mode and it is one of {' or '.join(STEP_MODES)} "
                    "(BR-RBS-023): set runs ONCE over the pinned set, per-record once per "
                    "subject in its own savepoint."
                )
            if not callable(step.run):
                raise RunbookContractError(
                    f"runbook {self.key!r} step {step.key!r} has no callable run()."
                )
            if step.writes and self.kind == models.KIND_CHECK:
                raise RunbookContractError(
                    f"runbook {self.key!r} is a Check and its step {step.key!r} declares "
                    "writes=True. A Check is CONSTRUCTED without a writer (BR-RBS-002); the "
                    "capability is absent, not merely unused. Findings become work items when "
                    "the run closes, and the ENGINE writes those — never the runbook "
                    "(BR-RBS-022)."
                )

    # -- guards -----------------------------------------------------------

    def _check_guards(self) -> None:
        for guard in self.guards:
            if not callable(guard.applies):
                raise RunbookContractError(
                    f"runbook {self.key!r} guard {guard.key!r} has no callable applies(). A guard "
                    "is ABSOLUTE and evaluated before any step (BR-RBS-012); one that cannot be "
                    "evaluated would silently guard nothing."
                )

    # -- ports: the rule this wave exists for ------------------------------

    def _check_ports(self) -> None:
        """`BR-RBS-002` · `TC-RBS-1`, and this is the module's whole safety promise.

        Three refusals, in the order they matter:

        1. **A Check holding ANY port.** The message names the runbook key and
           every offending port, because `TC-RBS-1` asks for exactly that.
        2. **An engine act declared as a port.** `raise_work_item` is refused BY
           NAME with the reason, because the source specification lists it among
           *"four named calls"* in seven places and the contract corrects it in
           one — a lane grepping for *port* finds the wrong answer seven times
           out of eight.
        3. **A name that is not one of the thirteen.** A fourteenth port is a
           reviewed interface (`BR-RBS-022`), not a line somebody writes on the
           way past.
        """
        if self.kind == models.KIND_CHECK and self.ports:
            raise RunbookContractError(
                f"runbook {self.key!r} is a Check and declares ports "
                f"{', '.join(sorted(self.ports))}. A Check is CONSTRUCTED without action ports "
                "(BR-RBS-002): the capability is ABSENT, not merely unused, so this is a build "
                "error and not a bad Monday. If it must write, it is an Action — and if it must "
                "raise a work item or write an audit row, those are ENGINE acts and need no port "
                "at all (BR-RBS-022)."
            )
        for port in self.ports:
            if port in ENGINE_ACTS:
                raise RunbookContractError(
                    f"runbook {self.key!r} declares {port!r} as a port. Raising work items and "
                    "writing audit rows are ENGINE acts, not ports (12-the-contract.md §2) — "
                    "which is exactly how a Check populates the work list while holding no "
                    "writer. The specification's 'four named calls' sentence is stale."
                )
            if port not in interfaces.PORTS:
                raise RunbookContractError(
                    f"runbook {self.key!r} declares port {port!r}, which is not one of the "
                    f"thirteen: {', '.join(sorted(interfaces.PORTS))}. A fourteenth port is a "
                    "reviewed interface (BR-RBS-022), not a new line."
                )

    # -- the two callables -------------------------------------------------

    def _check_callables(self) -> None:
        if not callable(self.resolve):
            raise RunbookContractError(
                f"runbook {self.key!r} has no callable resolve(). It is ONE function and it also "
                "answers 'matches 1,004 today' on the setup screen."
            )
        if not callable(self.report):
            raise RunbookContractError(f"runbook {self.key!r} has no callable report().")
        if self.findings is not None and not callable(self.findings):
            raise RunbookContractError(
                f"runbook {self.key!r} declares findings() and it is not callable. It is "
                "OPTIONAL — leave it out entirely rather than setting it to something that "
                "cannot be called, because the engine reads its absence as 'this runbook "
                "raises nothing' and a broken one as nothing too."
            )

    # ── what the rest of the module asks a definition ─────────────────────

    @property
    def is_check(self) -> bool:
        return self.kind == models.KIND_CHECK

    @property
    def owning_module(self) -> str:
        """The module this runbook is ABOUT, from its category.

        ⚠ **Read this as provenance, not as an allow-list.** See the file
        docstring item 1 and `DEF-RBS-4262`: the contract's own coverage table
        binds 15 of 21 ports outside the category's owning module, so treating
        this as a restriction would refuse every Action the product defines.
        The allow-list is `ports`.
        """
        return models.CATEGORY_OWNING_MODULE[self.category]

    def port_declarations(self) -> tuple[PortDeclaration, ...]:
        """The declarations this runbook may call — `()` for a Check, always.

        Declarations, not writers: in phase 1 every one of them raises
        `PortNotBound` when called, which is the shipped behaviour rather than a
        gap (`boundary.PortDeclaration.call`).
        """
        if self.is_check:
            return ()
        return tuple(interfaces.PORTS[name] for name in self.ports)

    def writes_nothing(self) -> bool:
        """What `RBS-002`/`RBS-004`'s *What it can touch* renders from, and only this.

        `US-RBS-002`: the words **Writes: Nothing · Sends: Nothing** are derived
        from `ports[]` and from nothing else — never from a hand-written label
        that could disagree with the constructor.
        """
        return not self.ports

    def as_definition_document(self) -> dict[str, Any]:
        """The snapshot stored in `runbook_versions.definition` (`jsonb`).

        Callables are recorded by NAME rather than serialised: the version row
        exists so that a run pins what it used and a later edit never rewrites
        history (`BR-RBS-038`), and the code that a step ran is identified by
        the module and the step key, not by a pickled function.
        """
        return {
            "key": self.key,
            "name": self.name,
            "kind": self.kind,
            "category": self.category,
            "subject_type": self.subject_type,
            "unit_of_work": self.unit_of_work,
            "triggers": list(self.triggers),
            "tags": list(self.tags),
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "label": p.label,
                    "required": p.required,
                    "default": p.default,
                    "choices": list(p.choices),
                    "setting_key": p.setting_key,
                    # `BR-RBS-042` — the input's declared list and whether it
                    # takes several. Both are the SHIPPED half of the document;
                    # what a tenant CHOSE lives in the settings half, under
                    # `services.SETTINGS_KEY`, so a template update never
                    # overwrites a tenant's answer and a tenant's answer never
                    # looks like a template change.
                    "domain": p.domain,
                    "multi": p.multi,
                }
                for p in self.parameters
            ],
            "steps": [
                {"key": s.key, "label": s.label, "mode": s.mode, "writes": s.writes}
                for s in self.steps
            ],
            "guards": [{"key": g.key, "label": g.label} for g in self.guards],
            "requires": self.requires,
            "ports": list(self.ports),
        }


# ── the two checks the engine performs on a report ────────────────────────


def _payload_problems(name: str, payload: Any, *, strict: bool = False) -> list[str]:
    """What is wrong with this block's payload, in words, or an empty list.

    ⚠ **A MISSING FIELD AND AN EXTRA ONE ARE NOT THE SAME FAULT, AND ONLY ONE OF
    THEM IS REFUSED AT CLOSE.** A missing field is what crashes `RBS-006`: the
    renderer reads `payload.rows.length` and gets `undefined`, and a clerk meets
    an error boundary instead of 835 notices (`DEF-RBS-4352`). An EXTRA field
    crashes nothing — it is data the runbook computed that no block draws, so it
    is lost silently, which is a real fault and a smaller one.

    Refusing both at close would have failed **49 cases across two shipped,
    working runbooks** on the day this was written — the accounting export sends
    `records.checked` and nothing draws it — and a validator that red-lines
    working code on arrival is one that gets reverted rather than obeyed. So the
    extra-field question is asked with `strict=True` by
    `test_us_rbs_015_conformance.py`, where the answer is a list to work off
    rather than a run marked failed.

    ⚠ **THE CONDITIONAL FOR `action` LIVES HERE AND NOWHERE ELSE.**
    `ActionPayload` is a UNION in `types.ts`: `enabled: false` carries a
    `reason` and `enabled: true` does not. B14 draws a control a user may not
    use as disabled WITH its reason, never hidden — so a refused action with no
    reason is a grey button that says nothing, which is `DEF-SHL-4043` and cost
    twenty screens four weeks. It is refused at close because it IS a missing
    field, just a conditional one.
    """
    if name not in PAYLOAD_FIELDS:
        return []
    if not isinstance(payload, dict):
        return [f"payload is {type(payload).__name__}, not an object"]
    required, optional = PAYLOAD_FIELDS[name]
    keys = set(payload)
    problems: list[str] = []

    missing = sorted(required - keys)
    if missing:
        problems.append("missing " + ", ".join(repr(field) for field in missing))

    if name == BLOCK_ACTION and payload.get("enabled") is False and "reason" not in payload:
        problems.append(
            "is disabled and carries no 'reason' — B14 draws a control a user may not use "
            "with its reason, never hidden"
        )

    if strict:
        unexpected = sorted(keys - required - optional)
        if unexpected:
            problems.append(
                "carries "
                + ", ".join(repr(field) for field in unexpected)
                + ", which no block draws"
            )
    return problems


def validate_report(blocks: Sequence[Any], *, runbook_key: str) -> list[dict[str, Any]]:
    """Refuse a thirteenth block, **at run close**, and return the frozen list.

    `BR-RBS-020` · `BR-RBS-021` · `TC-RBS-15` · `TC-RBS-16`. The refusal belongs
    here and not in the renderer: refused at render, the run is already marked
    done and a clerk gets a half-drawn screen with no way to tell whether the
    missing part mattered. Refused at close, the run is marked **failed** and
    the block is named.

    Accepts `Block` instances or the plain dicts a stored report is read back
    as, so the same validator can be run over a report that has already been
    written — which is what `TC-RBS-16` needs to assert byte-identity.
    """
    frozen: list[dict[str, Any]] = []
    for index, block in enumerate(blocks):
        if isinstance(block, Block):
            as_dict = block.as_dict()
            problems = _payload_problems(as_dict["block"], as_dict.get("payload"))
            if problems:
                raise RunbookContractError(
                    f"runbook {runbook_key!r} report position {index}: the "
                    f"{as_dict['block']!r} block's payload " + "; and ".join(problems) + ". "
                    "The twelve payload shapes are the RENDERER's "
                    "(07-frontend/src/features/runbooks/blocks/types.ts) and a report that "
                    "does not match them crashes RBS-006 rather than drawing a partial screen "
                    "(DEF-RBS-4352). Refused at run close; it never reaches a clerk."
                )
            frozen.append(as_dict)
            continue
        if not isinstance(block, dict) or "block" not in block:
            raise RunbookContractError(
                f"runbook {runbook_key!r} report position {index} is not a block: {block!r}"
            )
        name = block["block"]
        if name not in BLOCK_TYPES:
            raise RunbookContractError(
                f"runbook {runbook_key!r} report names block {name!r}, which is not one of the "
                f"twelve: {', '.join(BLOCK_TYPES)}. A thirteenth needs THREE runbooks that "
                "cannot be drawn without it (BR-RBS-021). Refused at run close; it never "
                "reaches the screen."
            )
        payload = block.get("payload", {})
        problems = _payload_problems(name, payload)
        if problems:
            raise RunbookContractError(
                f"runbook {runbook_key!r} report position {index}: the {name!r} block's payload "
                + "; and ".join(problems)
                + ". The twelve payload shapes are the RENDERER's "
                "(07-frontend/src/features/runbooks/blocks/types.ts) and a report that does not "
                "match them crashes RBS-006 rather than drawing a partial screen "
                "(DEF-RBS-4352). Refused at run close; it never reaches a clerk."
            )
        frozen.append({"block": name, "payload": payload})
    return frozen


def scope_fingerprint(subjects: Sequence[SubjectRef]) -> str:
    """The pinned id list, frozen at start — `BR-RBS-009`, `TC-RBS-22`.

    Scope is resolved ONCE. An account that becomes past due mid-run is not in
    the review list and is not acted on, and this string is how a later reader
    proves the set did not move. It is a digest of the ORDERED
    `subject_type:subject_id` pairs, so two runs over the same subjects in a
    different order are legitimately different fingerprints — the order is what
    the records table and the CSV are written in.

    ⚠ **THIS IS NOT AN IDEMPOTENCY KEY AND MUST NEVER BE USED AS ONE.** How
    `runbook_run_records.idempotency_key` is composed contradicts itself across
    our own documents (`DEF-RBS-4246`) and is `OQ-RBS-1737`, OPEN — deliberately
    left to wave L with the collections ladder in front of it, because with the
    run in the key a same-day re-run sends **496 notices where 248 were meant**.
    Nothing in this module composes such a key.
    """
    material = json.dumps(
        [[s.subject_type, str(s.subject_id)] for s in subjects],
        separators=(",", ":"),
        sort_keys=False,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-015 · US-RBS-002 (EP-RBS-01; CR-075 wave B task B1)
# generated: 2026-09-06 by the CR-075 wave B build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint in wave B — the routes are wave D) E=n/a(no screen — the renderers are wave C) F✔ G✔ H=n/a(no 🔒 path: this composes no idempotency key, touches no rating math and posts no ledger line)
# gates: pytest tests/test_us_rbs_015_conformance.py · G115 (the import census) · G74 (the baseline lines this wave moves)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

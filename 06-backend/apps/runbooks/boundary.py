# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A4: the two declaration
#           types the seams and the ports are written in.
# Rules:    BR-RBS-002 (a Check is CONSTRUCTED with no ports — a write from one
#           is a construction error, not a runtime refusal) · BR-RBS-022 (a
#           runbook reaches another module or a partner ONLY through a named
#           port; work items and audit rows are the ENGINE's) · BR-RBS-039 (a
#           read goes through a seam this module owns; every seam is a row in
#           the cross-module interface register)
# Tests:    06-backend/tests/test_us_rbs_041_module.py
# Impacts:  apps/runbooks/seams/*_seam.py · apps/runbooks/ports/*_ports.py ·
#           apps/runbooks/interfaces.py (the two registries)
# ───────────────────────────────────────────────────────
"""The two shapes this module's boundary is written in — types only, no registry.

TYPES ONLY, AND THAT IS WHY THIS FILE IS SEPARATE FROM `interfaces.py`. The seam
and port modules import the declaration types from here; `interfaces.py` imports
those modules to build the registries. Putting the registries here too would
make the import circular, which is the kind of thing that is obvious in
hindsight and costs an afternoon in the moment.

WHAT A PORT IS, AND WHY AN UNBOUND ONE IS THE POINT OF PHASE 1
--------------------------------------------------------------
A port is the **only** way a runbook writes anything belonging to another
module. Each maps to exactly ONE service function in the owning module, so the
platform's ban on cross-module writes holds and the list of everything a runbook
can do to the rest of the product is fourteen lines long and reviewable.

**Wave A declares all thirteen and binds NONE.** ⚠ **THE FOURTEENTH, `step_ladder`,
LANDED 2026-09-07** (`CR-075` wave `N`, `DEF-RBS-4347`) and is bound: a
collections step moves payments' own notice history and tier, and `queue_notice`
writes neither. `PortDeclaration.writer` is
`None` on every one of them, and `call()` raises `PortNotBound` naming the wave
that will bind it. That is not a stub awaiting an answer — it is the shipped
behaviour of phase 1, whose launch sentence is *"a clerk presses one button and
sees exactly what is stopping billing… **nothing can be written: no writer is
bound**"*.

⚠ **AND A CHECK HOLDS NO PORTS AT ALL, WHICH IS A DIFFERENT AND STRONGER
STATEMENT** (`BR-RBS-002`). An Action with unbound ports would fail at RUN time;
a Check is CONSTRUCTED with an empty port list, so a write from one is a
**construction error** — the capability is absent, not merely unused. Wave B's
contract object is where that becomes true for a runbook; this file is where the
vocabulary for saying it exists.

⚠ **THIRTEEN, AND `raise_work_item` IS NOT ONE OF THEM.** The source
specification says a runbook writes through *"four named calls"* and lists
*raise a work item* among them — in seven places. The contract, one page later,
lists thirteen and states in its own heading that **raising work items and
writing audit rows are ENGINE acts, never ports**. Thirteen is right: it is the
later and finer statement, it names an owning module for each entry, and it is
the list the twenty-one result wireframes need — `record_match` is drawn on
runbook 14, `write_read` on 21, `apply_premise_change` on 20, `suppress_channel`
on 22, `post_credit` and `raise_refund` on 15, `schedule_retry` on 17, and **the
four-port sentence cannot draw any of them**. Two lanes reached that reading
independently (`12-the-contract.md` §6, `03-field-map.md` D-1), and a third
would be arguing with two. **A lane building the four-call version gives every
Check a writer, and `BR-RBS-002` is gone.**
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

#: The nine modules this one READS, and the five whose rows it may WRITE through
#: a port. Both are closed sets: a tenth read or a fourteenth port is a reviewed
#: interface, not a code change somebody makes on the way past.
READ_MODULES = (
    "customers",
    "metering",
    "rating",
    "billing",
    "payments",
    "ledger",
    "notifications",
    "tenancy",
    "integrations",
)
#: ⚠ **SIX SINCE `CR-173-BRC10` (2026-10-07).** `integrations` owns
#: `send_partner_file` — a file placed in a partner's folder, which changes the
#: world outside this product and is therefore a write, not a read. Added as a
#: reviewed interface with a decision-log row, not as a line on the way past.
WRITE_MODULES = ("notifications", "payments", "billing", "metering", "customers", "integrations")


class PortNotBound(RuntimeError):
    """A port was called before any writer was bound to it.

    In phase 1 this is the CORRECT behaviour of every port, not an error
    condition to be worked around: the engine ships with sending switched off
    and nothing outside this module's seven tables can be written. Wave L binds
    the writers, with sending still off; wave N turns the first one on.
    """


@dataclass(frozen=True)
class SeamDeclaration:
    """One read seam — `operations → <module>`, read only, for ever.

    `crosses` is prose rather than a list of selector names on purpose. Naming
    a selector here that no module exposes yet would do two harmful things at
    once: it would be a promise nothing keeps (hard-won law 1), and `G20`
    harvests `apps.<module>.<kind>.<name>` out of seam docstrings and comments
    and FAILS when the target does not exist — which is how `DEF-075` was
    caught and is a guard worth not blunting. The selectors this module will
    need and no module offers today are inventoried in
    `04-docs/05-modules/17-runbooks/13-selector-inventory.md`, with the OWNING
    module named for each, and each is added by that module.
    """

    module: str
    #: The source specification's own name for the pair, kept so a reader of
    #: either document finds the same seam.
    pair: str
    crosses: str
    #: There is no other value and there is not going to be one. A write to
    #: another module is a PORT; a seam that writes is a seam in name only, and
    #: `G115` fails an ORM write on a foreign model inside `seams/` too.
    direction: str = "read"
    #: The B2 addendum whose table carries this seam's row in the cross-module
    #: interface register. Written in the same commit as the file (`BR-RBS-039`).
    register_row: str = "B2 Addendum r25"

    def __post_init__(self) -> None:
        if self.module not in READ_MODULES:
            raise ValueError(
                f"{self.module!r} is not one of the nine modules this one reads. "
                "A tenth read seam is a reviewed interface (B2 §2), not a new file."
            )
        if self.direction != "read":
            raise ValueError(
                f"seam {self.module!r} declares direction {self.direction!r}: a seam READS. "
                "A write to another module is a port (BR-RBS-022)."
            )


@dataclass
class PortDeclaration:
    """One write port — the only way a runbook touches another module's rows.

    `writer` is `None` until the wave named in `binds_in` lands. It is a
    mutable dataclass for exactly that reason: the binding is a later act, done
    once, in the owning module's own service function.
    """

    name: str
    owning_module: str
    what_it_does: str
    #: The wave that binds a real writer here. Everything is `L` today, which is
    #: phase 4's dry half — the risky code runs against real accounts, in
    #: production, for a full cycle, unable to do anything.
    binds_in: str = "CR-075 wave L"
    writer: Callable[..., Any] | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.owning_module not in WRITE_MODULES:
            raise ValueError(
                f"port {self.name!r} claims owning module {self.owning_module!r}, which is not "
                "one of the five a runbook may write through. A fourteenth port in a new "
                "module is a reviewed interface (BR-RBS-022), not a new line."
            )

    @property
    def is_bound(self) -> bool:
        return self.writer is not None

    def call(self, *args: Any, **kwargs: Any) -> Any:
        """Perform the write, or refuse in a way that says which wave binds it.

        ⚠ THIS IS NOT A STUB AWAITING AN OPEN QUESTION and carries no
        `NotImplementedError("OQ-…")`. Phase 1's launch sentence promises that
        nothing can be written, so refusing here is the SHIPPED behaviour rather
        than a gap. The distinction matters to `G8`, which reads a
        `NotImplementedError` as a blocked story, and to the next lane, which
        would otherwise go looking for a question that was never asked.
        """
        if self.writer is None:
            raise PortNotBound(
                f"port {self.name!r} ({self.owning_module}) has no writer bound. "
                f"Phase 1 binds none by design; {self.binds_in} binds this one."
            )
        return self.writer(*args, **kwargs)

"""The four quadrants — direction × initiative picks the runner, and there is no fifth cell.

    direction  initiative   runner            the sentence
    out        us           deliver.py        we send them something
    in         us           fetch.py          we go and collect something
    out        them         serve.py          they read from us
    in         them         inbound.py        they send us something (the door)

Two exhaustive axes replace the old four verbs (US-INT-018): *which way does
the data move, and who starts it*. `runner_for(operation)` reads both off
the manifest's operation and returns the module; a quadrant name (`DELIVER`,
`SERVE`) never reaches a screen — the card says *They send*, *We collect*.

The runners own the RUNTIME around one adapter call — the run row, the view,
the secrets for the length of the call, the counts — and nothing about a
provider. The inbound door is a module-root file (`apps/integrations/inbound.py`)
rather than `runners/inbound.py`, because that is the path the review-ledger
row asks the Product Owner to put on the guard list; the execution plan's
task B2 named the other spelling and is corrected there.
"""

from __future__ import annotations

from types import ModuleType

from apps.integrations import inbound
from apps.integrations.registry import Operation
from apps.integrations.runners import deliver, fetch, serve

_QUADRANTS: dict[tuple[str, str], ModuleType] = {
    ("out", "us"): deliver,
    ("in", "us"): fetch,
    ("out", "them"): serve,
    ("in", "them"): inbound,
}


def runner_for(operation: Operation) -> ModuleType:
    """The module for one operation. Both axes are closed vocabularies the
    registry already validated, so this cannot miss."""
    return _QUADRANTS[(operation.direction, operation.initiative)]


__all__ = ["runner_for", "deliver", "fetch", "serve", "inbound"]

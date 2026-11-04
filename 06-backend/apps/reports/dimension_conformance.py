# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 0 task `P0.17`.
#          Verbatim: *"Service must mean the same thing, carry the same label
#          and offer the same values in EVERY dataset that has it. ⚠ This is
#          how two reports come to disagree — one calls it Service with eleven
#          values, another calls it Utility with three, and a clerk comparing
#          them is comparing nothing. A test, not care."*
#          Outcome: *"A dimension declared twice with different labels or
#          value sets fails the suite by name."*
# Rules:   BR-REP-006 (a vocabulary enumerates the LIVE set) · §7.2 of the
#          brief (the dimension model, `P0.16` — lane REP-P0A's)
# Tests:   06-backend/tests/test_cr142_p0_17_conformed_dimensions.py
# ───────────────────────────────────────────────────────
"""ONE DIMENSION, ONE MEANING — checked, rather than reviewed for.

**WHY THIS IS A FUNCTION AND NOT A TEST.** The check itself has to be provable,
and a check that lives only inside a test can only be proved by breaking the
real registry — which means the proof runs against whatever the registry
happens to hold that week. So the RULE is here, takes declarations as an
argument, and is proved red against a hand-built pair that will never change.
The test then points it at the live registry. Two questions, two places: *does
the rule work* and *does the product satisfy it*.

**WHAT CONFORMED MEANS, EXACTLY.** Three things must agree everywhere a
dimension appears, and each fails differently:

  · **The key.** `service` in one dataset and `utility` in another are two
    dimensions as far as any tool is concerned, and a report cannot slice
    across them. Nothing here can catch that — two different keys ARE two
    different dimensions — which is why the register of keys is reviewed and
    why this module says so out loud rather than implying coverage it has not
    got (hard-won law 7's fifth shape).
  · **The label.** One key, two labels, and the same column is headed
    *Service* on one report and *Utility* on another. The number is right and
    the clerk comparing two printouts cannot tell.
  · **The value set.** One key, one label, eleven values here and three there.
    This is the expensive one: a *Revenue by service* totalling eleven services
    and a *Consumption by utility* totalling three both foot internally, and
    neither states that it covered a different population.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


class DimensionConflict(AssertionError):
    """One dimension key declared two ways. The message names both datasets."""


def _values_of(declaration: Any) -> tuple[str, ...] | None:
    """The declared value set, normalised, or None when the dataset declares none.

    **None is not an empty set and the difference matters.** A dataset that
    does not enumerate its values is not claiming there are none — it is
    leaving them to the live lookup, which is BR-REP-006 working. Treating the
    two the same would make every un-enumerated dimension conflict with every
    enumerated one, and the check would be discarded within a week.
    """
    raw = declaration.get("values") if isinstance(declaration, dict) else getattr(declaration, "values", None)
    if raw is None or callable(raw):
        return None
    return tuple(sorted(str(value) for value in raw))


def _label_of(declaration: Any) -> str | None:
    if isinstance(declaration, dict):
        return declaration.get("label")
    return getattr(declaration, "label", None)


def _key_of(declaration: Any) -> str | None:
    if isinstance(declaration, dict):
        return declaration.get("key")
    return getattr(declaration, "key", None)


def check_conformed(declarations: Iterable[tuple[str, Any]]) -> list[str]:
    """Every disagreement, as sentences. An empty list means conformed.

    `declarations` is `(dataset_key, dimension_declaration)` pairs — flat, so
    the caller decides how to walk the registry and this function never has to
    know the registry's shape.

    Returns rather than raises, so the test can report ALL of them at once. One
    conflict fixed at a time, over nine datasets, is nine runs.
    """
    seen: dict[str, tuple[str, str | None, tuple[str, ...] | None]] = {}
    problems: list[str] = []
    for dataset, declaration in declarations:
        key = _key_of(declaration)
        if key is None:
            problems.append(f"{dataset}: a dimension with no `key` — it cannot be conformed to anything")
            continue
        label, values = _label_of(declaration), _values_of(declaration)
        if key not in seen:
            seen[key] = (dataset, label, values)
            continue
        first_dataset, first_label, first_values = seen[key]
        if label != first_label:
            problems.append(
                f"dimension `{key}` is labelled {first_label!r} in `{first_dataset}` and "
                f"{label!r} in `{dataset}`. One key, two labels: the same column is headed "
                "two different things on two reports and a clerk comparing them cannot tell."
            )
        if first_values is not None and values is not None and first_values != values:
            only_first = sorted(set(first_values) - set(values))
            only_here = sorted(set(values) - set(first_values))
            problems.append(
                f"dimension `{key}` offers {len(first_values)} values in `{first_dataset}` and "
                f"{len(values)} in `{dataset}` — only in `{first_dataset}`: {only_first}; "
                f"only in `{dataset}`: {only_here}. Two reports sliced by this dimension cover "
                "different populations and both foot internally."
            )
        # The FIRST declaration stays the reference, so a third dataset is
        # reported against the same baseline rather than against its neighbour.
    return problems


def assert_conformed(declarations: Iterable[tuple[str, Any]]) -> None:
    """`check_conformed`, as a refusal. Raises `DimensionConflict` naming each."""
    problems = check_conformed(declarations)
    if problems:
        raise DimensionConflict(
            "CR-142 `P0.17` — a dimension is declared two ways:\n  · " + "\n  · ".join(problems)
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P0.17 (05-prototype/09 Reports Build Brief.pdf p9 + §7.2 p83-84)
# screens: none
# generated: 2026-09-26 by lane REP-P0B
# checklist: A✔ B=n/a C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — `check_conformed` was run against a hand-built conflicting pair before it was run against anything real, and returned both sentences.
# exceptions: (1) a DIFFERENT KEY for the same idea (`service` vs `utility`) is structurally invisible to this check and the docstring says so rather than implying coverage — that one is the register's, reviewed · (2) `values: None` (a live lookup) never conflicts with an enumerated set, because BR-REP-006 makes deferring to the lookup the CORRECT declaration
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

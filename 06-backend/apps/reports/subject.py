# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 2 · P2.14 (the Subject parameter — ONE parameter
#           on two definitions, four grains).  Screens: 2·1 head · 2·1 grain
#           line.  `P2.15` (the unit grain) and `P2.24` read this.
# Rules:    CLAUDE.md hard rule 8 (an address lives on `premises`; a UNIT
#           REFINES A PREMISES BY LABEL and declares no address column of its
#           own — every other entity walks to the premises) · BR-CUS-068
#           (`kind='master'` is a COLUMN on an ordinary accounts row) ·
#           B14 rule 31 (no database id is ever the visible value of a field) ·
#           B14 rule 33 (a FACT is six words)
# Tests:    06-backend/tests/test_rep_p2_14_subject.py
# Impacts:  apps/reports/runner.py (`_DEFINITION_BOOKKEEPING` already carries
#           `subject`/`subjects`) · apps/reports/migrations/0003_seed_catalogue.py
#           (seeds them onto `statement` and `account_ledger`) ·
#           apps/reports/api.py (the payload the head reads)
# ───────────────────────────────────────────────────────
"""FOUR SUBJECTS, ONE PARAMETER, AND MASTER IS NOT A FIFTH VALUE.

WHAT WAS ALREADY THERE — MEASURED, NOT ASSUMED
──────────────────────────────────────────────
The task reads as though the Subject parameter is unbuilt. It is half built,
and the half that exists is the half nothing checks:

  · `reports/0003_seed_catalogue.py` seeds `filters["subject"] = "account"` and
    `filters["subjects"] = ["account", "customer", "premises", "unit"]` onto
    the two keys `FOUR_SUBJECT_KEYS` names — `statement` and `account_ledger`.
  · `runner._DEFINITION_BOOKKEEPING` already lists `subject` and `subjects`, so
    both pass `validate()` untouched and neither reaches a dataset's filters.

So the PARAMETER exists as stored data on two rows. **Nothing reads it.** There
is no vocabulary, no validation, no selector, no grain, and nothing anywhere
that refuses a fifth value — a stored string nothing honours, which is
hard-won law 1 written into a migration instead of a comment. This module is
the reading half.

WHY MASTER IS NOT A FIFTH SUBJECT, AND WHY THAT NEEDED SAYING
─────────────────────────────────────────────────────────────
A master account is the obvious candidate for a fifth value: it behaves
differently on a bill, it covers several units, and a clerk asks for "the
master statement" in those words. It is nevertheless **an ordinary row of
`accounts` with `kind='master'`** (`BR-CUS-068`), selected on `accounts.id`
exactly like any other account. A fifth subject would therefore be a SECOND
lookup returning rows the first one already returns — two code paths over one
table, which is where two reports come to disagree about one customer.

What IS different is what the PREMISES subject does with it. p12: *"the
premises subject marks the master row and never merges it."* A building whose
common areas are billed to a master account has that account among its rows;
the report MARKS it so a reader can see which line is the owner's and which
are the tenants', and it does not fold the master's figures into the
building's totals, because that would count the same money twice.

WHY THE UNIT SUBJECT'S HEAD IS TWO FIELDS AND NOT ONE
─────────────────────────────────────────────────────
CLAUDE.md hard rule 8: an address is stored on `premises` and NOWHERE else,
and *"a unit refines a premises by LABEL, not by address"*. So a unit has no
address to show. Its head is the premises' address WALKED TO, plus the unit's
own label — `1408 Elm Street · Apt 3B` — and `head_from` says exactly that in
two parts rather than pretending a `unit_address` exists. A single field here
would be the first place in the product to imply one.

⚠ **`selects_on` IS A QUERY COLUMN AND NEVER TRAVELS TO A SCREEN.** B14 rule
31 — *"no Databse ID on screen - that is a rule"* — so `payload()` deliberately
omits it. The screen needs to know a subject EXISTS and what one row of it is;
the column it selects on is this module's business and a test asserts the wire
does not carry it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: The four, in the order p12 draws them. Also `0003_seed_catalogue.SUBJECTS`,
#: and a test asserts the two agree — a vocabulary declared twice is a
#: vocabulary that drifts.
SUBJECTS: tuple[str, ...] = ("account", "customer", "premises", "unit")


class UnknownSubject(ValueError):
    """A subject value no lookup answers.

    ⚠ **IT RAISES RATHER THAN FALLING BACK, AND THAT IS THE WHOLE POINT.**
    `BR-SHL-011` says an unrecognised LIST filter falls back rather than 4xx —
    correct there, because a dropped filter widens a set a clerk can see. A
    subject is not a filter: it decides WHAT THE REPORT IS ABOUT. Falling back
    to `account` would answer a different question from the one asked with a
    confident head above it, which p13 calls *"worse than one that refuses"*.
    """


@dataclass(frozen=True)
class Subject:
    """One of the four grains the two definitions are drawn at."""

    name: str
    #: The column the lookup selects on. A QUERY detail — never on the wire.
    selects_on: str
    #: `P2.23`'s line under the title. A FACT in four words (B14 rule 33).
    grain: str
    #: What the head composes its title from, in order. Two parts for a unit,
    #: because hard rule 8 gives a unit a LABEL and a premises the ADDRESS.
    head_from: tuple[str, ...]
    #: True on the subject that must MARK a `kind='master'` row rather than
    #: merge it — the premises subject, and only that one.
    marks_master: bool = False

    def as_dict(self) -> dict[str, Any]:
        """What a screen may read. ⚠ NO `selects_on` — B14 rule 31."""
        return {
            "name": self.name,
            "grain": self.grain,
            "head_from": list(self.head_from),
            "marks_master": self.marks_master,
        }


_SUBJECTS: dict[str, Subject] = {
    "account": Subject(
        name="account",
        selects_on="accounts.id",
        grain="One row per account",
        head_from=("account_no", "customer_name"),
    ),
    "customer": Subject(
        name="customer",
        selects_on="customer_id",
        grain="One row per customer",
        head_from=("customer_name",),
    ),
    "premises": Subject(
        name="premises",
        selects_on="premises_id",
        grain="One row per premises",
        head_from=("premises_address",),
        # p12: *"the premises subject marks the master row and never merges it."*
        marks_master=True,
    ),
    "unit": Subject(
        name="unit",
        selects_on="unit_id",
        grain="One row per unit",
        # Hard rule 8: the building's address, walked to, plus the unit's own
        # label. Never a `unit_address`, which does not exist and must not.
        head_from=("premises_address", "unit_label"),
    ),
}

#: The value a definition carrying no `subject` is drawn at. Stated as a
#: constant because `0003` seeds `SUBJECTS[0]` and a reader should not have to
#: infer that the first of a tuple is a default.
DEFAULT = SUBJECTS[0]


def resolve(raw: Any) -> Subject:
    """The subject this value names, or `UnknownSubject`.

    ⚠ **`master` IS REFUSED BY NAME AND THE REFUSAL POINTS AT `account`.** A
    bare *"unknown subject 'master'"* tells a reader that the thing they asked
    for does not exist, which is false and sends them to build it. What is true
    is that it is already served: a master account is an ordinary row and the
    `account` subject returns it.
    """
    if not isinstance(raw, str):
        raise UnknownSubject(
            f"subject must be one of {', '.join(SUBJECTS)} — got {type(raw).__name__}"
        )
    name = raw.strip()
    if name == "master":
        raise UnknownSubject(
            "'master' is not a subject: a master account is an ordinary accounts "
            "row with kind='master', so it is reported at the 'account' subject "
            "like any other, and the 'premises' subject marks it."
        )
    found = _SUBJECTS.get(name)
    if found is None:
        raise UnknownSubject(
            f"unknown subject {name!r} — this report is drawn at "
            f"{', '.join(SUBJECTS)}"
        )
    return found


def offered(definition_filters: Any) -> tuple[str, ...]:
    """The subjects THIS definition offers, from its own stored `subjects`.

    A definition that names none offers none — it is a single-grain report and
    the control must not appear on it. Returning all four for such a report
    would be a slicer that changes nothing, which is hard-won law 2's mirror.
    """
    if not isinstance(definition_filters, dict):
        return ()
    raw = definition_filters.get("subjects")
    if not isinstance(raw, (list, tuple)):
        return ()
    return tuple(name for name in raw if isinstance(name, str) and name in _SUBJECTS)


def payload() -> dict[str, Any]:
    """The vocabulary a screen reads. Serves the declaration, never a summary."""
    return {
        "subjects": [_SUBJECTS[name].as_dict() for name in SUBJECTS],
        "count": len(SUBJECTS),
        "default": DEFAULT,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 Phase 2 · P2.14 (05-prototype/09 Reports Build Brief.pdf p12 read as an image per B14 rule 42)
# screens: 2·1 head and grain line
# generated: 2026-09-27 by lane REP-P2-MODEL
# checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_rep_p2_14_subject.py was shown red on all nine cases before this file existed
# exceptions: (1) the parameter was already SEEDED by reports/0003 and already passed through `runner._DEFINITION_BOOKKEEPING`; what was missing was every reader of it, which is recorded in the docstring rather than rebuilt · (2) `selects_on` is deliberately absent from `payload()` (B14 rule 31)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

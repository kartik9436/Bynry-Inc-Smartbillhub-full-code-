# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-REP-7052 — no statement names what it is about. `Subject.head_from`
#          has been published since `P2.14` and is read by NOTHING, on the server
#          or on the screen; the shipped account statement has never named the
#          account either.
# Screens: 2·1 Report viewer — the page-head roll-up.
# Rules:   CLAUDE.md hard rule 8 (an address lives on `premises`; a UNIT REFINES
#          A PREMISES BY LABEL and declares no address of its own) ·
#          B14 rule 31 (no database id is ever the visible value of a field) ·
#          B14 rule 33 (a FACT is six words; RATIONALE is ZERO words on screen) ·
#          BR-REP-043 (the subject scopes the set) · BR-REP-038.
# Tests:   06-backend/tests/test_def_rep_7052_subject_head.py
# Impacts: apps/reports/statement.py (passes `head=`) · apps/reports/queries.py
#          (`_report(head=)`) · apps/reports/report_seams.py (the three label
#          reads) · 07-frontend/src/features/reports/ReportSubjectHead.tsx
# ───────────────────────────────────────────────────────
"""WHAT THIS REPORT IS ABOUT, COMPOSED FROM THE SUBJECT'S OWN DECLARATION.

THE PLUG-IN POINT, WHICH IS THE WHOLE REASON THIS IS A FILE AND NOT SIX LINES
────────────────────────────────────────────────────────────────────────────
A new subject publishes a correct head by doing exactly two things, and neither
of them is on a screen:

    1 · `subject.py` already declares its `head_from` — the FIELDS, in order.
    2 · register a resolver here under the subject's name; it is handed the
        `subject_id` and the read model's own view, and returns
        `{field: value}` for the fields that subject declares.

`compose()` then orders them, drops the ones that could not be resolved, and
publishes ONE wire shape. **No screen holds a table of which report shows what**
— the viewer renders the values it is handed, joined, and knows nothing about
accounts, units or premises. That is the property that makes this general: a
subject added on the server appears in the head without a front-end change.

⚠ **NOTHING HERE IS A SENTENCE AND NOTHING HERE IS TRANSLATED.** A head is the
NAME of a record — `AC-2026-00032 · Marisol Vega`, `1408 Elm Street · Apt 3B` —
and a name is the same in eleven languages. B14 rule 33 caps a FACT at six
words; two or three name-parts is what every subject declared draws.

⚠ **B14 RULE 31, AND IT IS THE REASON A RESOLVER RETURNS WORDS AND NOT IDS.**
The `subject_id` travels in the URL, where a clerk never reads it, exactly as
`statement._subject_id_of` records. Every value published here is a label a
person already recognises — an account NUMBER, a customer's display name, a
premises address, a unit label. A resolver that returned a uuid would put a
database id on screen, which is the one thing rule 31 forbids by name.

⚠ **A FIELD THAT CANNOT BE RESOLVED IS DROPPED AND NEVER GUESSED.** A line
posted before the books carried a customer has no holder to name; a premises
with no address read gives nothing. The head then carries the parts it has, and
a head with NO parts is published as `None` — so the screen renders nothing
rather than an empty separator, and never a placeholder standing in for a fact
this module could not establish.

⚠ **AND `head_from` IS THE SUBJECT'S, NOT THIS FILE'S.** A resolver may return
more keys than the subject declares and the extras are ignored; `compose` walks
`subject.head_from` in its own order. Hard rule 8 is enforced by that ordering
and by `subject.py`: a unit's head is the BUILDING's address plus the unit's
LABEL, in that order, and there is no `unit_address` for a resolver to return.
"""

from __future__ import annotations

from typing import Any, Callable

from apps.reports import report_seams as seams, subject as subject_module

#: `subject name -> (subject_id, view) -> {field: value}`.
#:
#: ⚠ **A SUBJECT WITH NO RESOLVER PUBLISHES NO HEAD, AND THAT IS A STATED
#: ABSENCE RATHER THAN A CRASH.** `customer` and `premises` are absent today
#: because `apps/reports/statement.py` refuses both by name — there is no
#: running-record read model at either grain — so a resolver for them would be
#: a control over a query that never runs (hard-won law 2's mirror). The lane
#: building those subjects adds one entry each, here, and nothing else moves.
HEAD_RESOLVERS: dict[str, Callable[[Any, Any], dict[str, Any]]] = {}


def register(name: str) -> Callable[[Any], Any]:
    """Declare the resolver for one subject. Used as a decorator."""

    def take(resolver: Callable[[Any, Any], dict[str, Any]]) -> Callable[..., Any]:
        HEAD_RESOLVERS[name] = resolver
        return resolver

    return take


@register("account")
def _account_head(subject_id: Any, view: Any) -> dict[str, Any]:
    """An account's number and whose it is.

    ⚠ **THE NUMBER AND NOT THE ID** (B14 rule 31) — `account_labels` answers
    with `accounts.account_no`, which is what the clerk typed into the chooser
    and what the customer reads on their bill.

    ⚠ **THE HOLDER IS ASKED FOR ONCE AND IS NOT WALKED PER ROW.** The head names
    one record, so one lookup answers it; the `occupant` COLUMN on a unit
    statement is a different question and is answered per line, at posting time,
    for the reason `dimension_seam.customer_labels` records at length — a unit
    outlives its tenants and a join through today's holder re-attributes
    history.
    """
    key = str(subject_id)
    head: dict[str, Any] = {"account_no": seams.account_labels([key]).get(key)}
    customer_id = seams.customer_id_for_account(key)
    if customer_id:
        head["customer_name"] = seams.customer_labels([customer_id]).get(str(customer_id))
    return head


@register("unit")
def _unit_head(subject_id: Any, view: Any) -> dict[str, Any]:
    """The BUILDING's address plus the unit's own LABEL — hard rule 8.

    ⚠ **BOTH COME OUT OF THE READ MODEL AND NEITHER IS LOOKED UP AGAIN.**
    `apps.ledger.reporting.unit_ledger` already walks the unit to its premises
    and publishes `premises_label` and `unit_label`; re-deriving them here would
    be a second answer to *where is this unit*, and a map and an envelope
    disagreeing is precisely what hard rule 8 exists to prevent.

    ⚠ **THERE IS NO `unit_address` AND THERE MUST NEVER BE ONE.** A unit refines
    a premises by LABEL; the address is the building's, walked to.
    """
    if not isinstance(view, dict):
        return {}
    return {
        "premises_address": view.get("premises_label"),
        "unit_label": view.get("unit_label"),
    }


def compose(
    chosen: subject_module.Subject, subject_id: Any, view: Any
) -> dict[str, Any] | None:
    """The head this run publishes, or `None` when there is nothing to say.

    `None` on three different facts, all of which mean *say nothing*: no record
    was named, this subject has no resolver, or every field it declares came
    back empty. A head is a claim about which record a page of money belongs to
    and a partial one is worse than none — so the screen is handed either a name
    a clerk recognises or nothing at all.
    """
    if subject_id in (None, ""):
        return None
    resolver = HEAD_RESOLVERS.get(chosen.name)
    if resolver is None:
        return None
    try:
        resolved = resolver(subject_id, view) or {}
    except Exception:  # pragma: no cover — a head never breaks a report
        # ⚠ **A HEAD IS DECORATION ON THE MONEY PATH AND MUST NOT BE ABLE TO
        # BREAK IT.** A seam that raises would otherwise turn a perfectly good
        # statement into an error page over a label.
        return None
    fields = [
        {"field": name, "value": str(resolved[name])}
        for name in chosen.head_from
        if resolved.get(name) not in (None, "")
    ]
    if not fields:
        return None
    return {"subject": chosen.name, "fields": fields}


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-REP-7052 (05-prototype/09 Reports Build Brief.pdf p69–p71 read as images per B14 rule 42 — R24a draws `100244 · Ruiz, Marisol` and R24d's own prose reads *"The head reads 1408 Elm Street · Unit 3"*)
# screens: 2·1 Report viewer — the page-head roll-up
# generated: 2026-09-28 by lane REP-STMT-SCREEN
# checklist: A✔ B✔ C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — `grep -rn "head_from" 07-frontend/src` returned NOTHING and `runner.run("statement", …).payload` carried no `head` key, on real PostgreSQL 16, before this file existed
# exceptions: (1) `customer` and `premises` have no resolver because `statement.py` REFUSES both subjects by name today; the lane building them adds one entry each to `HEAD_RESOLVERS` · (2) nothing here is translated — a record's NAME is the same in eleven languages (B14 rule 35 is about catalogues, not about names)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

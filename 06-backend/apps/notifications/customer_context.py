# ── Trace ──────────────────────────────────────────────
# Change:   CR-190-BRC10 MOVEIN-MSG — PO 2026-10-22, decision log *"Move-in
#           messaging and the welcome email: four answers…"* (answer 4: *"give
#           the activation date , first bill date and no due date required"*)
#           and *"Money in emails shows the currency symbol…"* (ruled 3: the
#           deposit email uses the shared customer-details builder).
# Defects:  DEF-NOT-10440 (welcome prints `——` four times) · DEF-NOT-10441
#           (deposit email greets nobody at no address)
# Rules:    CLAUDE.md hard rule 8 (the address is the PREMISES', walked to) ·
#           hard rule 1 (tenant scoping — every read below is the owner's own
#           tenant-scoped read) · BR-TEN-013 (no foreign ORM; owners' callables
#           resolved BY NAME) · B14 rule 31 (no id is ever a visible value) ·
#           OQ-344 (a cycle's bill date: the bill day, in the month after the
#           period ends) · BR-TEN-043 (no wall clock — the activation date is
#           an argument)
# Tests:    06-backend/tests/test_cr190_movein_messages.py
# Impacts:  apps/notifications/customer_events.py (welcome, deposit, plan change)
# ───────────────────────────────────────────────────────
"""ONE place a customer letter learns who it is for and where their service is.

`{first_name}`, `{customer_name}`, `{account_no}` and `{service_address}` are
the four tokens `catalogs._RECIPIENT` puts in the palette of every customer
message. Until `CR-190-BRC10` each writer composed them itself — billing,
payments, metering, work and transfers each with their own split of the name
and their own walk to the premises — and the move-in welcome composed none, so a
new customer's first email read *"Welcome, ——."* at *"——"*.

This module is the shared answer. A writer that has an account id calls
`customer_context(account_id)` and merges the result UNDER its own facts, so a
caller holding a snapshotted value (an issued bill's stamped name) still wins.

WHAT IT DECIDES, AND WHY
────────────────────────────────────────────────────────────────────────────
* **`first_name`** — the first word of the name a person is greeted by: the
  judgment `payments.receipts` recorded on 2026-09-07 and `billing.delivery_seam`
  reused, so a customer is greeted the same way by every letter. Two refinements,
  both recorded in the decision log (2026-10-22, CR-190 MOVEIN-MSG): a name
  written surname-first (`Smith, Pat`) greets `Pat`, as `work.visit_notices`
  already does; and a COMPANY is greeted by its whole name — *"Welcome, Acme."*
  is a greeting, *"Welcome, Acme Holdings LLC."* is the company's name, and the
  first word of a legal name is neither.
* **`service_address`** — the premises' street, then the unit's LABEL, then the
  town, then the state and postcode: `1408 Elm St · A, Austin, TX 78704`. The
  same composition `billing.gather._service_address` prints on the bill, plus the
  unit label a multi-unit building needs (hard rule 8: a unit refines a premises
  by label, never by address). **A missing part is dropped, never filled.**
* **`account_no`** — the NUMBER, never the id (B14 rule 31); a blank number is
  `None`, which prints the named absence rather than an empty space.

Every value that cannot be read is `None`, and the renderer prints its named
absence (OQ-117). Nothing here invents a value.

THE FIRST BILL DATE
────────────────────────────────────────────────────────────────────────────
`first_bill_date(account_id, activated_on)` asks METERING — which owns cycles
and derives every period (CR-029 D4) — for the account's cycle as of the
activation day: `billing_cycle_for_unit(unit, as_of=activated_on)`. Its
`next_bill_on` is OQ-344's rule (*"the bill day, in the month after the period
ends"*, PO 2026-08-23) applied to the period the customer moved in during — the
day the run that bills their first part-period will default to. Worked: a
Monthly cycle first run 1 Aug, bill day 5, a customer activated 12 Oct → period
1–31 Oct → first bill **5 November**.

It is the cycle's DEFAULT, which a clerk may override on the run (D9), so it is
the date a customer should expect, not a promise; the welcome says when the
first bill is *issued*, never when anything is *due* (the PO: *"no due date
required"*). **`None` — no unit (an owner's account hangs off the premises), no
cycle, two cycles, a cycle with no schedule or no bill day — means the welcome
OMITS the sentence** (`catalogs` marks the token optional; the renderer drops
its paragraph). Nothing is guessed: a 30-day month nobody configured is a date
nobody will bill on.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from apps.notifications import customers_seam

#: The four palette tokens this module fills. Named once so a caller and a test
#: read the same set; `catalogs._RECIPIENT` is the authority they mirror.
CUSTOMER_TOKENS = ("first_name", "customer_name", "account_no", "service_address")

#: `customers.kind` for an organisation (B2 r9 #1: person | company).
KIND_COMPANY = "company"

#: The metering read behind the first bill date, named once (G20 harvests it).
METERING_MODULE = "metering"
CYCLE_READ = "billing_cycle_for_unit"


def greeting_name(name: str | None, kind: str | None = None) -> str | None:
    """The name a letter greets — see the module docstring for the judgment."""
    text = (name or "").strip()
    if not text:
        return None
    if kind == KIND_COMPANY:
        return text
    if "," in text:
        before, after = (part.strip() for part in text.split(",", 1))
        if after:
            return after.split()[0]
        # DEF-NOT-10542 — no given name after the comma (`Miller,`): greet the
        # whole name WITHOUT the comma, never `Hi Miller,,`.
        return before or None
    return text.split()[0]


def service_address_line(parts: dict[str, Any] | None) -> str | None:
    """`{line1, city, state, postal_code, unit_label}` → one line, or None."""
    if not parts:
        return None

    def text(key: str) -> str | None:
        value = parts.get(key)
        return value.strip() or None if isinstance(value, str) else None

    street = text("line1")
    label = text("unit_label")
    head = f"{street} · {label}" if street and label else street
    region = " ".join(part for part in (text("state"), text("postal_code")) if part) or None
    joined = ", ".join(part for part in (head, text("city"), region) if part)
    return joined or None


def _context_from(identity: dict[str, Any] | None) -> dict[str, Any]:
    one = identity or {}
    name = one.get("customer_name") or None
    return {
        "first_name": greeting_name(name, one.get("customer_kind")),
        "customer_name": name,
        "account_no": one.get("account_no") or None,
        "service_address": service_address_line(one.get("service_address")),
    }


def customer_contexts(account_ids: Any) -> dict[str, dict[str, Any]]:
    """The four customer tokens for MANY accounts — a fixed number of statements.

    Every id asked for is a key, so a caller never has to handle a missing one:
    an account this tenant does not hold gets four `None`s, exactly what an
    unreadable one gets.
    """
    ids = [str(a) for a in (account_ids or []) if a not in (None, "")]
    found = customers_seam.message_identities(ids) if ids else {}
    return {key: _context_from(found.get(key)) for key in ids}


def customer_context(account_id: Any) -> dict[str, Any]:
    """The four customer tokens for ONE account (all `None` without one)."""
    if account_id in (None, ""):
        return {token: None for token in CUSTOMER_TOKENS}
    return customer_contexts([account_id])[str(account_id)]


def _resolve(module: str, attribute: str) -> Any:
    return customers_seam._resolve(module, attribute)


def account_cycle(account_id: Any, as_of: date | None) -> dict[str, Any]:
    """Metering's answer for the account's ONE cycle on `as_of`, or `{}`.

    `{code, name, bill_day, frequency, period_start, period_end, next_bill_on}`
    (`metering.selectors.billing_cycle_for_unit`). `{}` for an account with no
    unit (an owner's account hangs off the premises), no cycle, or two.
    """
    if account_id in (None, "") or as_of is None:
        return {}
    identity = customers_seam.message_identities([account_id]).get(str(account_id)) or {}
    unit_id = identity.get("unit_id")
    if not unit_id:
        return {}
    read = _resolve(METERING_MODULE, CYCLE_READ)
    if read is None:  # pragma: no cover - metering publishes it
        return {}
    return dict(read(unit_id, as_of=as_of) or {})


def first_bill_date(account_id: Any, activated_on: date | None) -> date | None:
    """The cycle's default bill date for the period the account activated in.

    `None` whenever metering cannot place the account on exactly one scheduled
    cycle — see the module docstring; the caller then omits the sentence.
    """
    if activated_on is None:
        return None
    value = account_cycle(account_id, activated_on).get("next_bill_on")
    if not value:
        return None
    try:
        found = date.fromisoformat(str(value))
    except ValueError:
        return None
    # A first bill is never dated before the service it bills began.
    return found if found >= activated_on else None

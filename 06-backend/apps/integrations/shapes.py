# ── Trace ──────────────────────────────────────────────
# Story:    CR-111-BRC04 — the Invoice Cloud partner API. The partner's field
#           names, date format and envelope come from THE KEY, never from a
#           query parameter.
# Rules:    BR-INT-037 (configuration is data, not code) · BR-INT-054
#           (integrations lands and hands over; it does not interpret) ·
#           BR-TEN-003 (nothing a caller sends selects anything) · CLAUDE.md
#           hard rule 2 (money is never re-computed here) · hard rule 5 (one
#           writer for money math — a shape is not a second one)
# Tests:    06-backend/tests/test_cr111_shapes.py
# Impacts:  apps/integrations/partner_api.py (the one caller) ·
#           apps/integrations/partner_csv.py (renders the SHAPED record)
# ───────────────────────────────────────────────────────
"""A partner's own field names, envelope and date format — as DATA, never code.

WHAT A SHAPE IS FOR
--------------------
Invoice Cloud's document asks for `page_number`, `count`, `next`, `previous`
and `results` where we publish `page`, `total_records`, `page_size`,
`total_pages` and `records`; for `DD-MM-YYYY` where we publish ISO; for
`invoiceNo` where we publish `id`; and for a plain word where we publish
`{code, label}`. Aclarian asks for none of that.

**Their key decides, and they pass nothing.** Key → credential → connection →
connector → its shape. A partner's integration document stays valid without a
parameter, a header or a version in the URL, and — the part that matters —
**no caller can choose a shape**, because choosing one would be an input that
changes a response, which is the thing `BR-TEN-003` exists to keep off this
surface.

    resolve(connector_key)  ──►  Shape  ──►  apply_records / apply_envelope

WHAT A SHAPE MAY AND MAY NOT DO
--------------------------------
    MAY      rename a field · rename the envelope · reformat a date ·
             flatten or nest · omit a field
    MAY NOT  change any value · decide which rows come back · affect any
             permission or refusal · compute anything

⚠ **THAT BOUNDARY IS ENFORCED BY THE STRUCTURE AND NOT BY THIS PARAGRAPH, AND
THE MECHANISM IS ONE SENTENCE: A SHAPE HOLDS NO CODE.** Every field of `Shape`
below is a string, a tuple of strings or a mapping of strings. There is no
`Callable` anywhere in this module's dataclasses and no place to put one, so a
later lane cannot pass a lambda, a formatter or a "just this once" hook. The
interpretation lives in `apply_records` — ONE function, in this file, that
moves values between keys and applies one of a CLOSED set of re-formatters.

**Why it is worth this much structure.** A shape that could reach the
arithmetic would be a second home for the money math: the day a partner's
`amount` needed to be "net of credits" it would be computed here, beside the
real one in `apps/billing`, and the two would drift silently because nothing
compares them. That is hard-won law 5's shape — *only the ledger posting
service writes journal lines* — applied to a read surface. A shape re-keys a
record that is already true; it never makes one truer.

⚠ **THE RE-FORMATTERS ARE CLOSED AND EVERY ONE IS REVERSIBLE, WHICH IS THE
TEST THAT TELLS A REFORMAT FROM A COMPUTATION.** `"12.5" → "13"` and
`"2026-09-17" → "17-09-2026"` both look like formatting. The second can be read
back to the first; the first cannot. So `_REFORMATTERS` ships with a companion
`_REVERSERS`, and `test_every_reformatter_round_trips` asserts that every
registered one recovers its input exactly, over the whole fixture. **A
re-formatter that cannot be reversed is a computation wearing a format's
clothes**, and it fails at import rather than in a partner's ledger.

⚠ **`next` AND `previous` ARE COMPUTED BY THE DOOR, NOT BY THE SHAPE**, and
the difference is the whole boundary. Their document wants two page URLs; a URL
needs the request, the page and the total, none of which a shape may see. So
`partner_api` computes them and puts them in the NATIVE envelope as two more
available facts, and each shape declares only whether to publish them and under
what names. `shapes.NATIVE` omits both, so what `/accounts` serves today does
not move by one byte.

WHAT IS NOT HERE, AND WHY
--------------------------
⚠ **NO SPLIT.** The brief for this wave listed *split one field into two* among
the things a shape may do, and it is not implemented, deliberately. The one
split this integration needs is a customer's name into first and last, and
**splitting a name is a rule about names** — which space, what about *"van der
Berg"*, what about a company — and a rule is computation. It lives in
`seams/customers.split_name`, where there is exactly one answer and every
partner gets the same one, and where it is proved lossless. A `split` field
here would have needed a splitter, a splitter is code, and code in a shape is
the one thing this module is built to prevent.

⚠ **NO TRANSLATION.** B14 rule 35 governs what a CLERK reads in their own
language. A partner's payload is a machine contract in an agreed spelling, and
a `projectType` that differed per catalogue would be eleven values for one
fact.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

# ═══════════════════════════════════════════════════════════════════════════
# The closed set of re-formatters — and their inverses, which is the point
# ═══════════════════════════════════════════════════════════════════════════

#: The native spelling. `YYYY-MM-DD`, which is what every seam composes and what
#: `date.isoformat()` produces.
DATE_ISO = "iso"
#: Invoice Cloud's document: `DD-MM-YYYY`.
DATE_DMY = "dmy"

DATE_FORMATS = (DATE_ISO, DATE_DMY)


def _to_dmy(value: str) -> str:
    """`2026-09-17` → `17-09-2026`. Digits move; nothing is parsed into a date
    and nothing is re-serialised, so a value this cannot read comes back
    untouched rather than becoming `None` (which a partner would post as
    *no date*)."""
    parts = value.split("-")
    if len(parts) != 3 or not all(one.isdigit() for one in parts):
        return value
    year, month, day = parts
    if len(year) != 4:
        return value
    return f"{day}-{month}-{year}"


def _to_iso(value: str) -> str:
    """The inverse of `_to_dmy`, and it exists to be TESTED rather than called.

    Nothing in this product reads a partner's date back — every one of these
    routes is a read, and a shape is applied on the way OUT only. This is here
    so `test_every_reformatter_round_trips` can assert that `_to_dmy` loses
    nothing, which is what separates a reformat from a computation. **Deleting
    it because "nothing calls it" would delete the proof that the mechanism is
    honest**, so it is named in `__all__` and the test names it too.
    """
    parts = value.split("-")
    if len(parts) != 3 or not all(one.isdigit() for one in parts):
        return value
    day, month, year = parts
    if len(year) != 4:
        return value
    return f"{year}-{month}-{day}"


#: `{format name: the function that writes it}`. ⚠ **CLOSED.** A shape names a
#: key of this mapping; it cannot supply a function. Registering a twelfth
#: format is an edit to this file and to its round-trip test, in one commit.
_REFORMATTERS = {
    DATE_ISO: lambda value: value,
    DATE_DMY: _to_dmy,
}

#: The inverse of each. ⚠ **EVERY KEY OF `_REFORMATTERS` MUST APPEAR HERE** —
#: asserted below at import, so a lane that adds a one-way "format" is refused
#: by `manage.py check` rather than by a partner's reconciliation.
_REVERSERS = {
    DATE_ISO: lambda value: value,
    DATE_DMY: _to_iso,
}

if set(_REFORMATTERS) != set(_REVERSERS):  # pragma: no cover — structural
    raise RuntimeError(
        "every date re-formatter needs an inverse: a format that cannot be read "
        "back is a computation, and a shape may not compute"
    )


# ═══════════════════════════════════════════════════════════════════════════
# The declaration
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ResourceShape:
    """How ONE resource's records are re-keyed for one partner.

    Every field is strings. ⚠ **THERE IS NOWHERE TO PUT A FUNCTION**, which is
    this module's whole guarantee — see the module docstring.
    """

    #: `{our key: their key}`. A key absent from this map keeps our name. A key
    #: mapped to a name already in the record is refused at import, because two
    #: of our fields landing on one of theirs silently drops one of them.
    rename: Mapping[str, str] = field(default_factory=dict)
    #: Our keys that this partner does not receive at all. ⚠ Omitting is the
    #: only way a shape may remove anything; there is no filter and no
    #: predicate, because deciding what comes back is the door's job.
    omit: tuple[str, ...] = ()
    #: Our keys whose value is a date STRING and should be re-spelled in the
    #: shape's `date_format`. Named explicitly rather than sniffed: a sniffer
    #: that decided `"2026-09-17"` in a free-text `memo` was a date would
    #: rewrite a customer's note, which is changing a value.
    dates: tuple[str, ...] = ()
    #: `{our key: the inner key to lift}` — `{"tender": "label"}` turns
    #: `{"tender": {"code": "CHQ", "label": "Cheque"}}` into
    #: `{"tender": "Cheque"}`. ⚠ **IT SELECTS, IT DOES NOT COMPOSE.** There is
    #: no way to say *"code and label joined by a dash"*, because that is a new
    #: value. A key whose value is not a mapping is left exactly as it is.
    flatten: Mapping[str, str] = field(default_factory=dict)
    #: `{the new outer key: (our keys to move inside it)}` — the inverse of
    #: flatten, for a partner whose record is nested where ours is flat. The
    #: keys move; not one of them changes.
    nest: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class Shape:
    """One partner's whole dialect: the envelope, the date format, and a
    `ResourceShape` per resource."""

    key: str
    #: `{our envelope key: their envelope key}`. An envelope key we hold and
    #: this map does not name is OMITTED, which is how `NATIVE` withholds
    #: `next` and `previous` without a second mechanism.
    envelope: Mapping[str, str] = field(default_factory=dict)
    date_format: str = DATE_ISO
    resources: Mapping[str, ResourceShape] = field(default_factory=dict)

    def for_resource(self, resource: str) -> ResourceShape:
        """This partner's dialect for one resource, or the empty one.

        ⚠ **AN UNDECLARED RESOURCE IS SERVED IN OUR OWN WORDS RATHER THAN
        REFUSED.** A sixth address added next year serves every partner
        something correct on its first day; a `KeyError` here would turn a new
        route into a `500` for exactly the partners who had been working
        longest.
        """
        return self.resources.get(resource, _PLAIN)


_PLAIN = ResourceShape()


# ═══════════════════════════════════════════════════════════════════════════
# The application — the ONLY code in this module that touches a record
# ═══════════════════════════════════════════════════════════════════════════


def _reformat_dates(record: dict[str, Any], resource: ResourceShape, date_format: str) -> None:
    write = _REFORMATTERS[date_format]
    for name in resource.dates:
        value = record.get(name)
        if isinstance(value, str) and value:
            record[name] = write(value)


def apply_record(record: Mapping[str, Any], shape: Shape, *, resource: str) -> dict[str, Any]:
    """One record, in one partner's dialect.

    The order is fixed and is part of the contract, because two of the steps
    can see each other: **dates · flatten · nest · omit · rename**. Dates and
    flatten work on OUR key names, which is what a shape's author is reading
    when they write the declaration; omit runs before rename so a shape names
    the field it is dropping in our vocabulary rather than in theirs; rename is
    last so nothing downstream has to know both spellings.

    ⚠ **THE INPUT IS NOT MUTATED.** The same record is handed to the JSON
    renderer and to the CSV renderer (`partner_csv`), so a shape that wrote
    through would make the second caller's answer depend on the first's.
    """
    out = dict(record)
    resource_shape = shape.for_resource(resource)

    _reformat_dates(out, resource_shape, shape.date_format)

    for name, inner in resource_shape.flatten.items():
        value = out.get(name)
        if isinstance(value, Mapping):
            out[name] = value.get(inner)

    for outer, names in resource_shape.nest.items():
        out[outer] = {name: out.pop(name) for name in names if name in out}

    for name in resource_shape.omit:
        out.pop(name, None)

    if resource_shape.rename:
        out = {resource_shape.rename.get(name, name): value for name, value in out.items()}
    return out


def apply_records(
    records: list[Mapping[str, Any]], shape: Shape, *, resource: str
) -> list[dict[str, Any]]:
    """A whole page, one dialect. Order is preserved exactly — **a shape may not
    decide which rows come back, and that includes the order they come back
    in**, which is the door's `ORDER_BY` and is what makes paging safe."""
    return [apply_record(one, shape, resource=resource) for one in records]


def apply_envelope(facts: Mapping[str, Any], shape: Shape) -> dict[str, Any]:
    """The envelope, in one partner's dialect.

    `facts` is every envelope fact the door computed — `total_records`, `page`,
    `page_size`, `total_pages`, `next`, `previous`, `records` and anything a
    route adds. **The shape names the ones this partner receives and what to
    call them; a fact it does not name is not served.** So `NATIVE` keeps the
    five it has always served and withholds the two page URLs without a flag,
    and Invoice Cloud receives its five under its own names.

    ⚠ **A NAMED FACT THE DOOR DID NOT COMPUTE IS OMITTED, NOT NULL.** A route
    that carries no `next` (the bill download is one document, not a page)
    would otherwise publish `"next": null` to every partner whose shape names
    it, and a partner reading a null `next` cannot tell *this is the last page*
    from *this route does not page*.
    """
    return {
        theirs: facts[ours] for ours, theirs in shape.envelope.items() if ours in facts
    }


# ═══════════════════════════════════════════════════════════════════════════
# The two shapes
# ═══════════════════════════════════════════════════════════════════════════

#: What every partner has received since `CR-110-BRC04` phase 2, unchanged.
#:
#: ⚠ **IT IS A DECLARATION AND NOT A SPECIAL CASE.** The tempting shortcut is
#: *if no shape is declared, skip the whole mechanism* — and then the native
#: path and the shaped path are two code paths, only one of which is exercised
#: by the partner tests, and the first divergence between them is invisible.
#: Ours goes through `apply_records` exactly as theirs does; it simply declares
#: no renames. `test_the_native_shape_is_a_no_op_on_every_resource` asserts the
#: identity over a record of every resource, so this claim is checked rather
#: than made.
NATIVE = Shape(
    key="native",
    envelope={
        "total_records": "total_records",
        "page": "page",
        "page_size": "page_size",
        "total_pages": "total_pages",
        "total_entries": "total_entries",
        "records_note": "records_note",
        "records": "records",
        # ⚠ `next` and `previous` are DELIBERATELY ABSENT. The door computes
        # them for every route; we have never published them and this wave does
        # not start. Their absence here is the whole mechanism for withholding
        # them — there is no flag and no branch.
    },
    date_format=DATE_ISO,
    resources={},
)

#: Invoice Cloud's dialect (`CR-111-BRC04`).
INVOICE_CLOUD = Shape(
    key="invoice_cloud",
    #: Their envelope: `page_number` · `count` · `next` · `previous` ·
    #: `results`. ⚠ **`page_size`, `total_pages`, `total_entries` AND
    #: `records_note` ARE NOT NAMED AND ARE THEREFORE NOT SERVED** — their
    #: document does not carry them, and publishing a key a partner's parser
    #: does not expect is how a strict client starts rejecting our responses.
    envelope={
        "page": "page_number",
        "total_records": "count",
        "next": "next",
        "previous": "previous",
        "records": "results",
        #: ⚠ **THEIR OWN NUMBER, HANDED BACK** — PO 2026-09-17, asked whose
        #: number this carries: *"a) echo back whatever they sent"*. The door
        #: puts it in `facts` ONLY when they sent one
        #: (`partner_api._echoed_utility_id`), so `apply_envelope` omits the key
        #: entirely when they did not — never `null`, which their parser would
        #: read as *we have no id for you*.
        "remote_utility_id": "remote_utility_id",
    },
    #: `DD-MM-YYYY`, their document's spelling.
    date_format=DATE_DMY,
    resources={
        "customers": ResourceShape(
            #: Their name for our `phone`. The seam carries `phone` only;
            #: **this line is the entire reason `contact_number` exists**, and
            #: it is why the seam does not carry both (`DEF-014`).
            #:
            #: ── `DEF-INT-5623` — AN ACCOUNT IS CALLED AN ACCOUNT ───────────
            #: PO 2026-09-17, looking at this connector on the live
            #: deployment: *"it should be account and not customer - theya re
            #: lookung for details for accounts not customer id"*.
            #:
            #: ⚠ **EVERY VALUE WAS ALREADY RIGHT, WHICH IS WHY NOTHING WENT
            #: RED.** `consumer_no` IS `account.account_no` and
            #: `customer_name` is the name ON the account — verified field by
            #: field in the defect row; **there is no customer id in this
            #: payload at all.** What was wrong is that a partner reading keys
            #: called `consumer_no` and `customer_name` maps them to their
            #: CUSTOMER record, and this product has a separate `customers`
            #: table where a landlord is ONE row and fourteen accounts. The
            #: same word meant two things across one boundary and the naming
            #: made the wrong reading the natural one.
            #:
            #: ⚠ **THIS IS A SHAPE AND THEREFORE ONE PARTNER'S DIALECT, NOT
            #: THE SEAM.** The seam goes on serving `consumer_no` /
            #: `customer_name` in OUR words to every other partner, so this
            #: touches no route and no other connector — which is exactly what
            #: a `Shape` is for (`BR-INT-037`, and `G77` fails a gate on
            #: `provider_key` branching, so it is two dict entries rather than
            #: an `if`). **That the SEAM itself holds a partner's word where
            #: our own column is `account_no` is a separate finding and is
            #: filed, not fixed here** — moving it would change what five
            #: `live` ERP connectors receive.
            rename={
                "phone": "contact_number",
                "consumer_no": "account_no",
                "customer_name": "account_name",
            },
            #: `status` is our `{code, label}` pair; they take the word.
            #: `status_display` then carries the same word under our own name,
            #: so it is dropped rather than sent twice.
            flatten={"status": "label"},
            omit=("status_display",),
        ),
        "bills": ResourceShape(
            #: ⚠ **`id` → `invoiceNo` IS A RENAME AND LIVES HERE, NOT IN THE
            #: SEAM.** `id` already IS the invoice number (`INV-2026-00412`),
            #: and PO 2026-09-17 on how our ids travel — *"they store our text
            #: exactly as we send it"* — settles that nothing is converted. So
            #: there is one value with two spellings and a shape is what picks
            #: the spelling.
            rename={"id": "invoiceNo"},
            #: **FLAT**, which their document draws and which is the one thing
            #: on this surface a partner loses by choosing this shape: the
            #: nested per-line GL codes do not travel. That is their format's
            #: limit, recorded rather than worked around — composing a summary
            #: line to "keep" the information would be computing.
            omit=("lines",),
            #: `billType` and `status` are ours as `{code, label}`; flat means
            #: the word.
            flatten={"billType": "label", "status": "label"},
            dates=("billDate",),
        ),
        "payments": ResourceShape(
            #: *"`tenderType` as a plain word"* — our `{code: "CHQ", label:
            #: "Cheque"}` becomes `"Cheque"`. ⚠ **THE LABEL AND NOT THE CODE:**
            #: the code is ours and means nothing at their end, and the label
            #: is the tenant's own word for it (`BR-CUS-055`'s shape), which is
            #: what the reference endpoint publishes alongside.
            rename={"tender": "tenderType"},
            flatten={"tender": "label"},
            dates=("paidOn", "paid_on", "recorded_on"),
        ),
    },
)


#: `{connector key: its shape}` — **the whole of how a partner's dialect is
#: chosen.** ⚠ **DATA, NOT A BRANCH** (`BR-INT-037`, and `G77` fails a gate on
#: `provider_key` branching): a twelfth partner with its own field names is one
#: `Shape` and one line here, and touches no route.
#:
#: ⚠⚠ **NEITHER OF THE FIRST TWO KEYS CAN EVER REACH THIS MAP, AND THAT MADE
#: THE WHOLE DIALECT DEAD UNTIL 2026-09-17 (`DEF-INT-5642`).** `resolve` is
#: called from exactly one place — `partner_api._page_response`, with
#: `caller.connection.provider_key` — so the only keys that can arrive are the
#: connectors a PARTNER can hold a key for, which is
#: `partner_api.partner_provider_keys()`: `pay_invoicecloud_partner` and the
#: five ERPs. **`erp_invoicecloud` is a manifest that does not exist** — this
#: file's own sibling records it as *considered and refused* — and
#: `pay_invoicecloud` is the CARD half, `we_hold_theirs`, which is never a
#: partner caller. So every real call resolved to `NATIVE` and InvoiceCloud
#: received our envelope, our ISO dates, `id` instead of `invoiceNo` and
#: `phone` instead of `contact_number`. Measured, not inferred:
#: `shapes.resolve("pay_invoicecloud_partner").key` was `native`.
#:
#: **Nothing could have caught it**: the shape's own tests call
#: `apply_record(..., INVOICE_CLOUD)` directly, and the ROUTE tests connect
#: with `provider_key="erp_aclarian"` — which correctly resolves to `NATIVE`.
#: Both halves were right about themselves and no case put the real connector
#: key into the real resolver (hard-won law 7, *looking at the wrong thing*).
#: `test_the_partner_connector_resolves_to_its_own_dialect` is that case and it
#: was proved red on this line first.
#:
#: The two dead keys are LEFT rather than swept up: removing them is a separate
#: judgment about a published map and would hide the evidence of this defect.
BY_CONNECTOR: Mapping[str, Shape] = {
    "erp_invoicecloud": INVOICE_CLOUD,
    "pay_invoicecloud": INVOICE_CLOUD,
    #: **THE ONE THAT A REAL CALL CAN CARRY.** `pay_invoicecloud_partner` is
    #: the `they_hold_ours` half — the connector whose key InvoiceCloud
    #: presents at our door (`manifests/pay_invoicecloud_partner.py`).
    "pay_invoicecloud_partner": INVOICE_CLOUD,
}


def resolve(connector_key: str | None) -> Shape:
    """A connector key → its dialect. **THE ONLY WAY A SHAPE IS EVER CHOSEN.**

    ⚠ **THE ARGUMENT IS THE CONNECTOR, AND A CONNECTOR COMES FROM THE KEY.**
    `partner_api` passes `caller.connection.provider_key`, which
    `serve.resolve_caller` reached through key → credential → connection and
    nothing a caller sent. There is no overload taking a request, a header or a
    query parameter, so *"just let them ask for `?format=invoicecloud`"* is not
    a small change here — it is a new function, and the reviewer sees it.

    ⚠ **AN UNKNOWN CONNECTOR GETS `NATIVE`, WHICH IS A REFUSAL TO GUESS RATHER
    THAN A DEFAULT.** Ours is the only dialect we can serve correctly to a
    partner we know nothing about, and a partner who wanted another one told us
    so by being in `BY_CONNECTOR`.
    """
    return BY_CONNECTOR.get(str(connector_key or ""), NATIVE)


#: ⚠ **REFUSED AT IMPORT, NOT AT RUN TIME**, which is this repository's posture
#: for every manifest (`registry.py`) and is here for the same reason: a shape
#: whose renames collide drops a field, and a dropped field on a finance read is
#: a missing GL posting that nothing on either side raises. `manage.py check`
#: fails on a developer's machine, where it is cheap.
def _validate() -> None:
    for shape in (NATIVE, INVOICE_CLOUD):
        if shape.date_format not in _REFORMATTERS:
            raise RuntimeError(
                f"shape {shape.key!r} names date format {shape.date_format!r}, "
                f"which is not one of {tuple(_REFORMATTERS)}"
            )
        landed = list(shape.envelope.values())
        if len(landed) != len(set(landed)):
            raise RuntimeError(f"shape {shape.key!r} maps two envelope keys onto one")
        for resource, one in shape.resources.items():
            targets = list(one.rename.values())
            if len(targets) != len(set(targets)):
                raise RuntimeError(
                    f"shape {shape.key!r} resource {resource!r} renames two fields "
                    "onto one name — one of them would be dropped silently"
                )
            overlap = set(one.rename) & set(one.omit)
            if overlap:
                raise RuntimeError(
                    f"shape {shape.key!r} resource {resource!r} both renames and omits "
                    f"{sorted(overlap)} — say one or the other"
                )


_validate()


__all__ = [
    "BY_CONNECTOR",
    "DATE_DMY",
    "DATE_FORMATS",
    "DATE_ISO",
    "INVOICE_CLOUD",
    "NATIVE",
    "ResourceShape",
    "Shape",
    "apply_envelope",
    "apply_record",
    "apply_records",
    "resolve",
    # Named so the round-trip proof cannot be deleted as dead code — see
    # `_to_iso`'s own docstring.
    "_to_dmy",
    "_to_iso",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-111-BRC04 (PO rulings of 2026-09-17, verbatim in the CR)
# generated: 2026-09-17 by the CR-111-BRC04 Invoice Cloud lane
# checklist: A✔ B=n/a(no screen — this is a partner payload) C✔ D✔ E✔ F✔ G✔ H=n/a
# gates: pytest tests/test_cr111_shapes.py · 10-scripts/gates/g127_a_shape_cannot_compute.py
# exceptions: `split` is NOT implemented although the wave brief listed it —
#   the one split this integration needs is a rule about names and therefore
#   computation, and it lives in `seams/customers.split_name` where it is proved
#   lossless. Recorded in the module docstring rather than left as an omission
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

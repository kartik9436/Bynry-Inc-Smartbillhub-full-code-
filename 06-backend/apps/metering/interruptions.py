# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-008 (EP-CWP-03) — the interruption record and its
#           affected-area rule · US-CWP-007 (what a report creates) ·
#           US-CWP-009 (what a stranger tracks). Screens: CWP-006 · CWP-007 ·
#           CWP-012 · the Interruption section of the staff request detail
# Rules:    BR-CWP-027 (the reporter need not be a customer and the address is
#           FREE TEXT resolved later — demanding an exact premises match would
#           refuse the person standing over a burst main) · BR-CWP-012 (the
#           record lives in `metering` and the portal reads it through a seam —
#           B2 §2, the owning module owns its data) · CLAUDE.md hard rule 1
#           (RLS FORCE — migration `0046_rls_interruptions`)
# Tests:    06-backend/tests/test_us_cwp_008_interruption.py
# Impacts:  apps/metering/models.py (the import that registers this model) ·
#           apps/metering/interruption_service.py · apps/portal/seams/
#           metering_seam.py · migrations/0045_cwp_interruptions.py
# ───────────────────────────────────────────────────────
"""`interruptions` — the record nothing in this product held until today.

⚠ **THE TABLE IS `interruptions`, PLURAL, AND `03-field-map.md` §2 CALLS IT
`interruption`.** Every table this schema already has is plural — `premises`,
`connections`, `work_orders`, `service_requests`, `portal_settings` — and the
field map writes entity names in the singular throughout (`help_answer`, `tip`,
`service_centre`). The code wins and the field map is stamped, dated, by the
wave that built it (`10-execution-plan.md` §0's rule).

WHAT IS NEW HERE, AND IT IS NOT THE COLUMNS
-------------------------------------------
`EP-CWP-03` says it plainly: *"THIS IS THE NEW THINKING IN THE WHOLE BLUEPRINT.
Not the record — the affected-area rule."* An interruption is *"Elm St,
1400–1500"* and something has to turn that into a set of premises. That
something is `resolve_affected_premises` below, and it is deliberately in this
module rather than in a query, because the parse of a house number out of a
free-text address line is arithmetic and not SQL.

THREE THINGS THE COLUMNS SAY OUT LOUD
-------------------------------------
* **`location_text` is free text and `premises_id` is NULL until a clerk
  resolves it** (`BR-CWP-027`, `US-CWP-007` TC-2). An address that matches no
  premises is ACCEPTED — never a refusal.
* **`reporter_name` / `reporter_phone` are on the row, not on a customer.** The
  reporter need not be a customer and usually is not.
* **The clock does not close a record — a crew does** (`US-CWP-008` TC-6). An
  `expected_back_on` in the past changes no status; only `set_status` does.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from django.db import models
from django.db.models import Q

from apps.metering import models as metering_models
from core.dbfields import uuid7_pk

# ── The six kinds (03-field-map.md § interruption) ──────────────────────────
KIND_NO_WATER = "no_water"
KIND_LEAK_OR_BURST = "leak_or_burst"
KIND_LOW_PRESSURE = "low_pressure"
#: ⚠ **ROUTES TO A PHONE NUMBER, NEVER TO A QUEUE.** No row of this table ever
#: carries it: `report_a_problem` answers the emergency number and writes
#: nothing (`US-CWP-007` TC-3). It is in the vocabulary because the FORM offers
#: it, and a form that quietly accepts *"smell of gas"* and queues it behind a
#: missed collection is worse than no form.
KIND_GAS_SMELL = "gas_smell"
KIND_MISSED_COLLECTION = "missed_collection"
KIND_DAMAGED_METER = "damaged_meter"

#: In the order `CWP-006` draws the radio list.
KINDS: tuple[str, ...] = (
    KIND_NO_WATER,
    KIND_LEAK_OR_BURST,
    KIND_LOW_PRESSURE,
    KIND_GAS_SMELL,
    KIND_MISSED_COLLECTION,
    KIND_DAMAGED_METER,
)
#: What may reach a row. `gas_smell` is offered and never stored.
STORABLE_KINDS: tuple[str, ...] = tuple(k for k in KINDS if k != KIND_GAS_SMELL)

# ── The three statuses, in order ────────────────────────────────────────────
STATUS_LOOKING = "looking_into_it"
STATUS_CREW_ON_SITE = "crew_on_site"
STATUS_RESOLVED = "resolved"
STATUSES: tuple[str, ...] = (STATUS_LOOKING, STATUS_CREW_ON_SITE, STATUS_RESOLVED)

#: Who may follow whom. `resolved` is terminal: `US-CWP-008` TC-4 — *"resolve an
#: interruption already resolved → refused; the second resolution is not
#: recorded as a new event."* A crew arriving after somebody guessed the job was
#: done is a real thing, so `crew_on_site` may follow `looking_into_it` and the
#: reverse is allowed too; only the closing move is one-way.
ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    STATUS_LOOKING: (STATUS_CREW_ON_SITE, STATUS_RESOLVED),
    STATUS_CREW_ON_SITE: (STATUS_LOOKING, STATUS_RESOLVED),
    STATUS_RESOLVED: (),
}


class Interruption(models.Model):
    """One thing that is off, leaking or broken, and who it touches."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")

    #: `RP-26-0412` — the whole record of the interaction for somebody who has
    #: no account (`BR-CWP-028`). Allocated from the tenant's own
    #: `interruption_report` series inside the creating transaction
    #: (`BR-TEN-035`). NULLABLE only because a clerk-raised row could predate a
    #: series that a tenant has not been seeded yet; every row this product
    #: writes carries one, and `create_interruption` refuses rather than
    #: inventing a number.
    reference = models.TextField(null=True, blank=True)

    kind = models.TextField()
    status = models.TextField(default=STATUS_LOOKING)
    reported_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)

    #: ⚠ FREE TEXT (`BR-CWP-027`). *"Water coming up through the pavement
    #: outside number 1412"* is a location; so is *"the corner of Elm and
    #: Third"*. No premises match is required and none is attempted at write.
    location_text = models.TextField()

    #: Resolved by a CLERK, not by the form (`US-CWP-007` TC-2). Metering's own
    #: table, so not a cross-module FK.
    premises = models.ForeignKey(
        metering_models.Premises,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="premises_id",
        related_name="interruptions",
    )

    #: ⚠ **THE PIECE WITH NO PRECEDENT ANYWHERE IN THE SCHEMA** — a street plus
    #: a number range, `{"street": "Elm St", "from": 1400, "to": 1500}`. JSON
    #: rather than three columns because a later shape (a polygon, a route, a
    #: list of streets) must not cost a migration on a live table, and JSON
    #: rather than `jsonb`-only because the default test suite runs on SQLite
    #: (CLAUDE.md law 14) and Django's `JSONField` is `jsonb` on PostgreSQL and
    #: text on SQLite with the same Python value either way.
    affected_area = models.JSONField(null=True, blank=True)

    #: ⚠ **THE REPORTER NEED NOT BE A CUSTOMER**, so these are columns on the
    #: interruption and not a link to anybody.
    reporter_name = models.TextField(null=True, blank=True)
    reporter_phone = models.TextField(null=True, blank=True)

    expected_back_on = models.DateTimeField(null=True, blank=True)

    #: ⚠ **RETIRED BY `CR-072` ON 2026-09-04 — NOTHING READS OR WRITES IT, AND
    #: IT IS KEPT FOR EXACTLY ONE RELEASE.**
    #:
    #: It was a cross-module FK metering → customers (B2 §2's reviewed
    #: interface set), one-to-one, and being one-to-one is what FORCED a second
    #: interruption row per report: twelve people ringing about one burst main
    #: produced twelve "interruptions". `CR-072` §4 reverses the direction —
    #: **one report is one request, and many requests may point at one
    #: interruption** — so the live link is `service_requests.interruption_id`.
    #:
    #: **It survives this release because `CR-072` §7 states the rollback that
    #: way**: *"the FK reversal is a new nullable column beside the old one, so
    #: the previous behaviour is a code revert with no data loss"*. The wave
    #: that removes it is the FIRST one to touch this table after `CR-072`
    #: ships — named here so its removal is a plan and not a discovery, which
    #: is the difference between this column and dead surface.
    service_request = models.ForeignKey(
        "customers.ServiceRequest",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="service_request_id",
        related_name="+",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "interruptions"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "reference"],
                condition=Q(reference__isnull=False),
                name="uq_interruptions_tenant_reference",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="ix_interruptions_status"),
        ]

    def __str__(self) -> str:  # pragma: no cover — admin/debug convenience
        return f"{self.reference or self.pk} {self.kind} {self.status}"


# ── The affected-area rule ──────────────────────────────────────────────────

#: A leading house number, with or without a letter suffix: `1408`, `1408A`,
#: `1408-B`. Everything after it is the street.
_HOUSE_NUMBER = re.compile(r"^\s*(\d{1,6})\s*[-A-Za-z]?\s+(.*)$")


def house_number(address_line: str | None) -> int | None:
    """The leading house number of a free-text address line, or None.

    `"1408 Elm St"` → `1408`. `"Elm St"` → None — a premises with no number
    cannot be inside a number RANGE, and saying so is better than guessing it
    is.
    """
    if not address_line:
        return None
    match = _HOUSE_NUMBER.match(address_line)
    return int(match.group(1)) if match else None


def normalise_area(area: Any) -> dict[str, Any] | None:
    """`{"street": …, "from": …, "to": …}` from whatever a caller passed.

    A street alone is a valid area (*"Cedar Row"*, no numbers): it means the
    whole street. `from`/`to` are optional and are put in order if a clerk
    types them backwards, which is a typing accident and not a refusal.
    """
    if not isinstance(area, dict):
        return None
    street = str(area.get("street") or "").strip()
    if not street:
        return None
    lo = area.get("from")
    hi = area.get("to")
    lo = int(lo) if str(lo or "").strip().isdigit() else None
    hi = int(hi) if str(hi or "").strip().isdigit() else None
    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo
    return {"street": street, "from": lo, "to": hi}


def resolve_affected_premises(tenant_id: Any, area: Any) -> list[Any]:
    """The premises *"Elm St, 1400–1500"* names — **and nobody else**.

    `US-CWP-008` TC-2/TC-3, and TC-3 is the one that shapes the signature: an
    area naming a street with no premises **resolves to an empty set and the
    record is still valid**. *"An interruption can exist before we know who it
    touches."* So this returns a list and never raises.

    TWO STEPS, AND THE SPLIT IS DELIBERATE.

    1. **The street narrows it in SQL** — `address_line__icontains`, inside the
       tenant (RLS is on the table as well, hard rule 1; the explicit filter is
       what makes the query readable rather than what makes it safe).
    2. **The number range is decided in PYTHON**, by `house_number` above.
       `address_line` is one free-text column — `"1408 Elm St"` — and no
       portable SQL splits a leading integer off it. PostgreSQL could
       (`substring(… from '^\\d+')::int`); SQLite, which the default suite runs
       on, could not, and a rule that behaves differently on the two databases
       is CLAUDE.md law 14 wearing a different hat.

    COST, stated rather than assumed: one indexed-ish scan of the tenant's
    premises whose address line contains the street, then a parse per row. A
    utility under three thousand connections has at most a few dozen premises on
    one street. This is not a page of a list and is not paginated.

    ⚠ **A STREET WITH NO NUMBERS MEANS THE WHOLE STREET**, including premises
    whose address line carries no number at all. A street WITH numbers excludes
    those, because a premises we cannot place cannot be shown to be inside a
    range.
    """
    shaped = normalise_area(area)
    if shaped is None:
        return []
    rows = list(
        metering_models.Premises.objects.filter(
            tenant_id=tenant_id, address_line__icontains=shaped["street"]
        ).order_by("address_line")
    )
    lo, hi = shaped["from"], shaped["to"]
    if lo is None and hi is None:
        return rows
    inside: list[Any] = []
    for row in rows:
        number = house_number(row.address_line)
        if number is None:
            continue
        if lo is not None and number < lo:
            continue
        if hi is not None and number > hi:
            continue
        inside.append(row)
    return inside


def affected_unit_count(premises_rows: Iterable[Any]) -> int:
    """How many units sit on those premises — the second figure the staff
    screen shows beside the address count. Zero is a real answer: a single
    dwelling with no unit rows is still an affected premises."""
    ids = [row.id for row in premises_rows]
    if not ids:
        return 0
    return metering_models.Unit.objects.filter(premises_id__in=ids).count()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-008@47a78561 (EP-CWP-03 story + BR-CWP-001..096 snapshot)
# generated: 2026-09-04 by the CR-068 wave B build lane
# checklist: A✔ B✔ C✔ D=n/a(model half; the API is customers/service_request_api.py) E✔(the staff detail's Interruption section) F✔ G✔ H=deferred(the 🔒 half is migrations/0046_rls_interruptions.py — review-ledger row)
# gates: pytest tests/test_us_cwp_008_interruption.py · makemigrations --check clean · run_gates
# exceptions: the table is `interruptions` and 03-field-map.md §2 writes `interruption` — the code wins and the field map is stamped · `service_request_id` is a NEW cross-module FK metering → customers, REPORTED for the B2 §2 reviewed set exactly as work_orders.account_id was
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

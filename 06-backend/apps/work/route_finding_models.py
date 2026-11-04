# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 lane FINDINGS — what a meter reader finds on a route
#           (RW-21 *Raise it*, RW-18 *Different meter*), kept on the server.
# Rules:    BR-WRK-067 (PO 2026-10-22, verbatim *"if a rule is set work order
#           will get created , if not user can create the work order"*) ·
#           BR-MET-1202 (PO 2026-10-22 — where it was captured is its own fact,
#           `lat`/`lng` only, never an address) · CLAUDE.md hard rules 1
#           (RLS ENABLE + FORCE, `work/0049`), 6 (idempotent on the key minted
#           at capture), 8 (no address column: the stop walks to its premises)
# Tests:    06-backend/tests/test_cr187_route_findings.py ·
#           06-backend/tests/test_cr187_route_findings_pg.py
# Impacts:  apps/work/models.py (one import line registers it) ·
#           apps/work/route_findings.py · work/0048, work/0049
# ───────────────────────────────────────────────────────
"""`work_route_findings` — a finding a reader reported on a meter route.

WHY WORK OWNS IT AND NOT METERING
────────────────────────────────────────────────────────────────────────────
The finding arrives through the READS door (`POST work/mobile/reads/sync`,
kind `finding`) because that is where the handset sends everything it
captures on a route — its photographs included, which already land as route
photos (`metering.field_read_photos`). But nothing about a finding is a
reading: it is a request for WORK. The rule that turns it into a job is
Work's (`rules_models.WorkOrderRule`), the job is Work's, and the office reads
it on Work's *From the field* tab. Kept in metering, Work would have had to
WRITE a metering row to link the job back (`G78` refuses that), or the link
would have lived in a second table. So the reads door hands the item to
`apps.work.route_findings.receive` by name (`metering.seams.resolve`) and Work
writes its own row.

ONE FINDING, AT MOST ONE JOB
────────────────────────────────────────────────────────────────────────────
`status` is `open` until a job exists, then `work_order_created` with the job
in `work_order` and HOW it came — `by_rule` (the rule in `rule`) or `by_hand`
(the person in `converted_by`). The move is a conditional UPDATE on
`status = 'open'` inside the raise's SAVEPOINT (`route_findings._convert`), so
two people pressing *Create work order* at once raise ONE job: the second
UPDATE matches no row and its savepoint — job and all — rolls back.

⚠ **NO ADDRESS COLUMN** (hard rule 8). The stop is `premises`; its address is
reached by walking. `lat`/`lng` are where the PHONE was (`BR-MET-1202`), are
`G85`-scoped to those two names exactly, and are never shown as the
property's place.
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q

from core.dbfields import uuid7_pk

#: RW-21 *What did you find?* — the six it draws, in its order — and RW-18's
#: mismatch (*the badge here is not the one on the list*), which the handset
#: sends as a finding with its answer in `detail`. ⚠ **A CLOSED LIST IN CODE,
#: AND THAT IS A JUDGMENT RECORDED RATHER THAN A RULING:** nothing rules
#: whether a utility edits it (R82 made the can't-read reasons DATA; nothing
#: said the same of findings). A rule matches on these words, so they must be
#: one list the server owns; a utility-editable list is a later change that
#: would move this tuple into a table without moving any row.
FINDING_LEAK = "leak"
FINDING_DAMAGED_METER = "damaged_meter"
FINDING_BROKEN_SEAL = "broken_seal"
FINDING_SUSPECTED_TAMPER = "suspected_tamper"
FINDING_UNSAFE_ACCESS = "unsafe_access"
FINDING_SOMETHING_ELSE = "something_else"
FINDING_METER_MISMATCH = "meter_mismatch"
FINDING_KINDS: tuple[str, ...] = (
    FINDING_LEAK,
    FINDING_DAMAGED_METER,
    FINDING_BROKEN_SEAL,
    FINDING_SUSPECTED_TAMPER,
    FINDING_UNSAFE_ACCESS,
    FINDING_SOMETHING_ELSE,
    FINDING_METER_MISMATCH,
)
#: MQ-033 (`CR-192-BRC10`, `BR-MET-1217`) — a job raised because a reader's
#: ANSWER to a utility's read-format question matched the answer its
#: `raise_work` names (PO 2026-10-24, *"an answer raises a job of a
#: utility-chosen type, linked back to the reading"*). ⚠ **STORED, NEVER
#: OFFERED**: it is not in `FINDING_KINDS`, so the handset cannot send it,
#: `receive` refuses it, and no Work rule can be written on it — the format's
#: question already named its job. Only `raise_for_read_answer` writes it.
FINDING_READ_ANSWER = "read_answer"
STORED_FINDING_KINDS: tuple[str, ...] = (*FINDING_KINDS, FINDING_READ_ANSWER)

#: RW-21 *How urgent?* — the reader's word, stored AS SAID. It sets nothing:
#: a rule names its own priority, and a person creating the job by hand picks
#: one. Which tenant priority *Now* means is not ruled (the field raise's
#: `URGENCIES` carries the same caveat).
FINDING_URGENCIES: tuple[str, ...] = ("now", "this_week", "routine")

FINDING_OPEN = "open"
FINDING_WORK_ORDER_CREATED = "work_order_created"
FINDING_STATUSES: tuple[str, ...] = (FINDING_OPEN, FINDING_WORK_ORDER_CREATED)

CONVERTED_BY_RULE = "by_rule"
CONVERTED_BY_HAND = "by_hand"
#: MQ-033 — raised by the read format's question, not a rule and not a person.
CONVERTED_BY_READ_FORMAT = "by_read_format"
CONVERSIONS: tuple[str, ...] = (CONVERTED_BY_RULE, CONVERTED_BY_HAND, CONVERTED_BY_READ_FORMAT)


class WorkRouteFinding(models.Model):
    """`work_route_findings` — one finding, as the reader reported it."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: The handset's key, minted at capture (hard rule 6). Unique per tenant:
    #: a resent item answers the first finding and stores nothing.
    key = models.TextField()
    kind = models.TextField()
    urgency = models.TextField(null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    note_source = models.TextField(null=True, blank=True)
    #: RW-18's answer and codes (`mismatch`, `scanned_code`, the listed meter's
    #: number) — what a *meter mismatch* finding is about. Never an address.
    detail = models.JSONField(default=dict, blank=True)
    #: The route photographs' ids (`metering.field_read_photos`), as declared.
    photo_ids = models.JSONField(default=list, blank=True)
    #: ⚠ Cross-module FKs work → metering / assets, READ only (Work writes
    #: none of them — `G78`). The stop is a PREMISES, never a meter (R74).
    route = models.ForeignKey(
        "metering.Route", on_delete=models.PROTECT, null=True, blank=True,
        db_column="route_id", related_name="+",
    )
    premises = models.ForeignKey(
        "metering.Premises", on_delete=models.PROTECT, null=True, blank=True,
        db_column="premises_id", related_name="+",
    )
    asset = models.ForeignKey(
        "assets.Asset", on_delete=models.PROTECT, null=True, blank=True,
        db_column="asset_id", related_name="+",
    )
    #: `BR-MET-1202` — where the PHONE was at capture. Evidence, never an address.
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    accuracy_m = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    #: The device clock at capture (R92) and the server's on arrival.
    captured_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    #: WHO captured it — from the item's `capture_token`, never the courier.
    captor = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True,
        db_column="captor_id", related_name="+",
    )
    captor_technician = models.ForeignKey(
        "work.Technician", on_delete=models.PROTECT, null=True, blank=True,
        db_column="captor_technician_id", related_name="+",
    )
    status = models.TextField(default=FINDING_OPEN)
    work_order = models.ForeignKey(
        "work.WorkOrder", on_delete=models.PROTECT, null=True, blank=True,
        db_column="work_order_id", related_name="+",
    )
    conversion = models.TextField(null=True, blank=True)
    rule = models.ForeignKey(
        "work.WorkOrderRule", on_delete=models.SET_NULL, null=True, blank=True,
        db_column="rule_id", related_name="+",
    )
    converted_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True,
        db_column="converted_by", related_name="+",
    )
    converted_at = models.DateTimeField(null=True, blank=True)
    #: Everything the handset sent, as sent (`07-endpoints.md` §0 rule 1).
    received_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "work_route_findings"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "key"], name="uq_work_route_findings_key"),
            models.CheckConstraint(
                condition=Q(kind__in=STORED_FINDING_KINDS), name="ck_work_route_findings_kind"
            ),
            models.CheckConstraint(
                condition=Q(urgency__isnull=True) | Q(urgency__in=FINDING_URGENCIES),
                name="ck_work_route_findings_urgency",
            ),
            models.CheckConstraint(
                condition=Q(status__in=FINDING_STATUSES), name="ck_work_route_findings_status"
            ),
            # A created finding says how; an open one carries no job.
            models.CheckConstraint(
                condition=(
                    Q(status=FINDING_OPEN, work_order__isnull=True, conversion__isnull=True)
                    | Q(status=FINDING_WORK_ORDER_CREATED, conversion__in=CONVERSIONS)
                ),
                name="ck_work_route_findings_converted",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "received_at"], name="ix_route_findings_queue"),
        ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-187-BRC10 lane FINDINGS — BR-WRK-067, BR-MET-1202 (decision log 2026-10-22 "TWO PO RULINGS")
# generated: 2026-10-22 by lane FINDINGS
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(work/0048 + work/0049 are 🔒 migration ordering / RLS; ledger row owed by the coordinator)
# gates: G78 · G85 · pytest tests/test_cr187_route_findings*.py (SQLite and PostgreSQL 16)
# exceptions: the finding kinds are a closed list in code — a judgment, reported
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

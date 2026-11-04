# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-020 §4 · US-INT-021 §4 (the five runs) · US-TEN-019
#           (the sample set and its honest report).  Screens: S8 (the
#           Integrations card grid) · S142 (a connection and its runs)
# Change:   CR-083 — PO 2026-09-07, verbatim: *"Im okay with this - please
#           add- Step 30, Integrations"*.  The four-part plan that sentence
#           approved is written out in 12-governance/02-decision-log.md,
#           2026-09-07, "THE INTEGRATIONS SAMPLE-DATA PLAN IS APPROVED".
# Rules:    BR-INT-018 (an outcome is COMPUTED from the counts and the far
#           end's confirmation — never typed) · BR-INT-039 (a run row is
#           append-only) · BR-INT-020 D (a delivery's key is the provider's
#           event id COMPOSITE with the payment/return marker) · BR-LED-004
#           (one recorded, idempotent handover per period + target) ·
#           BR-LED-017 (a period is exported only once it is CLOSED) ·
#           BR-TEN-013 (a cross-module write goes through the owning module's
#           own service function) · BR-TEN-056/057 (the sample set; the tag on
#           the owning row) · BR-TEN-060 (a block that could not run is a
#           NAMED line) · BR-TEN-063 (atomic per module, idempotent, audited) ·
#           BR-TEN-066 (removal is partial-and-named) · CLAUDE.md hard rule 1
#           (tenant scoping) · hard rule 4 (financial immutability) · hard-won
#           law 1 (a claim the product cannot support is not made on a screen)
# Tests:    06-backend/tests/test_cr082_integrations_sample_data.py
# Impacts:  apps/tenancy/sample_data.py (the SAMPLE_MODULES row) ·
#           apps/integrations/services.py (the three seams) ·
#           apps/integrations/management/commands/seed_integration_runs.py
#           (reads the mailbox spec from here, so there is one of it)
# ───────────────────────────────────────────────────────
"""`integrations`' block of the sample set — three connections and their history.

WHY THIS FILE EXISTS (CLAUDE.md hard-won law 2, measured)
──────────────────────────────────────────────────────────────────────────────
`apps/integrations/sample_runs.py` — five runs, written through the real
services so `BR-INT-018` computes every outcome word — has been finished and
good since 2026-09-04, and `"integrations"` appeared in
`apps/tenancy/sample_data.SAMPLE_MODULES` **zero times**. So the only tenant
that ever held an integration run was one somebody had typed
`manage.py seed_integration_runs` at by hand; every tenant provisioned through
the real sign-up path read **0** on every integrations table. Built, and not
wired.

This file is the wiring, and it deliberately writes NO new run: `seed_runs`
below is `sample_runs.seed_runs`, unchanged, because two seeders for one set of
rows is two sources of truth (hard-won law 5).

WHAT A SEEDED TENANT GETS, AND WHY EACH PIECE IS THERE
──────────────────────────────────────────────────────────────────────────────
* **Three connections, not one.** One row is not a list — a clerk cannot see
  what the card grid does with a second category until there is one. The three
  are the mail server the bills go out on, the meter-reading import and the
  bank's lockbox file, which is what a utility actually lives on. Every one of
  them is a provider with an adapter already in `apps/integrations/adapters/`;
  none is invented for the demo.
* **Five runs on the mailbox** — 93/93 succeeded, 93/86/7 partial with the
  seven refused addresses NAMED, 93/0 unconfirmed, a leak-path test and the
  manual test that FAILED carrying the mail server's own sentence about a
  password.
* **One landed payment notification** (`payment_webhook_events`) and **one
  recorded accounting handover** (`export_batches`), because the run fixture
  writes runs only and those two tables would otherwise still read 0 on a
  screen that has a tile for each.

⚠ **EVERY CONNECTION'S STATUS IS `untested`, AND THAT IS A DECISION RATHER
THAN AN OVERSIGHT.** No adapter is registered in this release, so nothing here
can have tested anything; a green tick on the card grid would be a claim the
product cannot support, on a screen, which is hard-won law 1 in its most
expensive form. `services.connect` writes `untested` for exactly this reason
and this file does not override it.

⚠ **THE DEMO CARRIES A RUN THAT FAILED AND NOBODY SHOULD "FIX" IT.** A demo
where everything succeeded teaches a clerk nothing about the screen they will
actually need — the same principle that leaves the third billing cycle
unbilled. If a test objects to a failed run in the fixture, the test is wrong.

⚠ **NO OUTCOME WORD, STATUS OR KEY IS TYPED IN THIS FILE.** The run outcomes
are `BR-INT-018`'s arithmetic (`services.finish_run`); the delivery's status is
`payments.webhooks.land_delivery`'s; its dedupe key is built by
`inbound.dedupe_key` from the manifest's declared natural key; the export
batch's content hash and batch number are `ledger.exports`'. A fixture that
typed any of them would go green while the rule it exists to demonstrate was
broken — `US-INT-021` TC-2's *"trivially satisfied by a stub"*.

IDEMPOTENCE, AND THE TWO TABLES THAT CANNOT BE CORRECTED (`BR-TEN-063`)
──────────────────────────────────────────────────────────────────────────────
The connections key on `(tenant, provider_key, environment)` — the database's
own `uq_integration_connection_key_env` — so a replay finds them and writes
nothing. `integration_run` and `export_batches` are APPEND-ONLY (`BR-INT-039`,
hard rule 4): a second seeding cannot correct the first and must not pretend
to, so each checks for its own fixture's mark first and declines. A landed
delivery is deduped by `uq_payment_webhook_events_event` and answers
`landed=False` on a replay, which is the same posture one layer down.

⚠ **THREE TABLES HAVE NO `is_sample` COLUMN AND THE COLUMN IS OWED**
(`BR-TEN-057`). `integration_connection` could carry one; `integration_run` is
a partitioned, append-only parent and `export_batches` is a signed financial
record, so neither ever will. Removal is therefore keyed on the fixture's own
labels — a NARROWER key, so a connection the utility made itself is never
touched — and everything append-only is reported RETAINED BY NAME, which is
`BR-TEN-066`'s partial-and-named answer. This is the divergence
`wizard_parks`, `disconnect_cases` and `account_protections` already carry,
reported the same way rather than papered over.

WHAT THIS BLOCK CANNOT SUPPLY FOR ITSELF, AND SAYS SO (`BR-TEN-060`)
──────────────────────────────────────────────────────────────────────────────
The accounting handover needs a CLOSED month with balanced books
(`BR-LED-017`, `BR-LED-007`). This block runs LAST in `SAMPLE_MODULES`, after
both billing cycles and all the money, which is the only position where the
first cycle's accounting month can honestly be shut and handed over. If the
ledger refuses — an unbalanced period, a month already exported, no ledger at
all — the refusal is logged as one sentence naming what is missing and the
other pieces still land. It is never an exception that takes the connections
down with it.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone as dt_timezone
from typing import Any

from django.db import transaction

from apps.integrations import models, sample_runs
from core.tenancy import current_tenant_id

logger = logging.getLogger("smartbillhub.integrations")


# ══════════════════════════════════════════════════════════════════════════
# THE THREE CONNECTIONS
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THE LABEL IS THE IDENTITY REMOVAL KEYS ON**, so it is a constant here
# rather than a sentence composed at the call site. It is also what a clerk
# reads on the card, so it is written as a person would write it and carries
# no rule id or internal code (B14 rule 31/32).
#
# ⚠ **CONFIG HOLDS NON-SECRET FIELDS ONLY.** `services.connect` refuses a
# secret-kind field by name (`BR-INT-003`) — the password, the API key and the
# folder password below are absent on purpose, and a seeded connection
# therefore has no credential and could not be tested even if an adapter were
# registered. That is the honest state for a fixture: it is CONFIGURED, not
# CONNECTED-AND-PROVEN.

#: The mailbox the bills go out on. Its five runs are the support call the demo
#: is read down the telephone (`sample_runs.DEMO_TRACE`).
MAILBOX = {
    "provider_key": "email_smtp",
    "label": "Billing mailbox",
    "cadence": models.CADENCE_MANUAL,
    "config": {
        "host": "mail.example.invalid",
        "port": "587",
        "username": "billing@example.invalid",
        "send_from": "billing@example.invalid",
    },
}

#: Where the readings come from. `nightly`, because a meter cloud is polled on
#: a schedule and a demo that showed every connection as `manual` would hide
#: the one column on the card grid that says when a thing next runs.
METER_CLOUD = {
    "provider_key": "meters_neptune360",
    "label": "Water meter cloud",
    "cadence": models.CADENCE_NIGHTLY,
    "config": {"site_id": "SITE-4417"},
}

#: The bank's lockbox file. `source` is a `select` field and its value is from
#: the manifest's own option list — a value outside it would be a demo teaching
#: a setting that does not exist. There is no `file_format`: CSV is the one
#: format, so there is no picker (`DEF-INT-10702`; it seeded `bai2` until then).
LOCKBOX = {
    "provider_key": "bank_lockbox_file",
    "label": "Lockbox file from the bank",
    "cadence": models.CADENCE_MANUAL,
    "config": {
        "label": "Lockbox file from the bank",
        "source": "sftp",
        "sftp_host": "sftp.bank.example.invalid",
        "sftp_username": "utility",
        "sftp_path": "/outgoing/lockbox",
        "column_mapping": {},
    },
}

SEEDED_CONNECTIONS: tuple[dict[str, Any], ...] = (MAILBOX, METER_CLOUD, LOCKBOX)

#: Every label this block writes — the removal key, derived from the specs
#: above so the two cannot drift apart.
SEEDED_LABELS: frozenset[str] = frozenset(str(one["label"]) for one in SEEDED_CONNECTIONS)


# ══════════════════════════════════════════════════════════════════════════
# THE ONE LANDED PAYMENT NOTIFICATION
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **IT IS LANDED AND NOT APPLIED, WHICH IS THE WHOLE OF `BR-INT-058`.** The
# inbound door records that a partner told us something and STOPS: reading it,
# deciding what it means and writing a payment is the runbook's half and is
# not built. A fixture that also recorded a payment would demonstrate a
# boundary the product does not have.
#
#: The kiosk's own reference for the notification, fixed so a walkthrough can
#: quote it. The row's actual key is COMPOSITE (`BR-INT-020` D) and is built by
#: `inbound.dedupe_key` from the manifest, never typed here.
KIOSK_PROVIDER = "payments_kiosk"
KIOSK_OPERATION = "payments"
KIOSK_EVENT_ID = "K-88231"
KIOSK_RECEIVED_AT = datetime(2026, 8, 4, 18, 22, tzinfo=dt_timezone.utc)
#: What the kiosk network posted, in its own vocabulary — `CASH` is one of the
#: words `payments_kiosk`'s tender vocabulary maps, not one of ours.
KIOSK_BODY: dict[str, Any] = {
    "eventId": KIOSK_EVENT_ID,
    "type": "payment",
    "kioskId": "KIOSK-07",
    "accountNumber": "A-10432",
    "amount": "84.00",
    "currency": "USD",
    "tender": "CASH",
    "takenAt": "2026-08-04T18:21:44Z",
}


# ══════════════════════════════════════════════════════════════════════════
# THE ONE RECORDED ACCOUNTING HANDOVER
# ══════════════════════════════════════════════════════════════════════════
#
#: ⚠ **THE MONTH EXPORTED IS THE MONTH THE FIRST CYCLE WAS *BILLED* IN, NOT
#: THE MONTH IT *MEASURED* — AND THAT IS A CORRECTION, MEASURED (2026-09-07).**
#: The obvious choice is June, the first period the demo bills. It is wrong:
#: the demo issues June's bills on **2 July** (`core.sample_fixture.PERIODS`,
#: `bill_on`), so the earliest journal entry a seeded tenant holds is dated
#: 2026-07-02 and **June contains no entries at all**. A June batch was
#: recorded on a proof tenant and came back with **0 rows and the content hash
#: of an empty list** — a perfectly lawful, perfectly useless handover, and one
#: no gate could have objected to. July, on the same tenant, carries **9
#: summary rows**. The accounting month is the month the money HIT THE BOOKS.
#: The period is therefore derived from `bill_on` and never typed.
EXPORT_TARGET = "csv"
#: The moment the handover was made, an INPUT rather than a clock read
#: (`BR-TEN-043`): a tenant seeded today and one seeded next month must carry
#: the same date on the same batch.
EXPORT_MADE_AT = datetime(2026, 8, 3, 10, 15, tzinfo=dt_timezone.utc)
CLOSED_AT = datetime(2026, 8, 3, 9, 40, tzinfo=dt_timezone.utc)
#: `close_period` demands a REASON whenever the checklist is short of complete
#: (`BR-LED-018` — WARN + CONFIRM, never a silent close and never a lockout).
#: A demo tenant's checklist always is, so one is always supplied.
CLOSE_REASON = (
    "Every bill in this month has gone out and the money for them is in, so the month is shut "
    "and can go to the books."
)


def _tenant_id() -> Any:
    return current_tenant_id()


def _accounting_month() -> tuple[date, date] | None:
    """The calendar month the FIRST cycle's bills were issued in — the month the
    books actually have entries in.

    `core.sample_fixture.PERIODS` is the authority for how many cycles the demo
    carries and when each one bills; this asks it rather than copying a date,
    so a fixture that moves its cycles moves this with them.
    """
    from core import sample_fixture as fixture

    billed = tuple(one for one in fixture.PERIODS if one.get("billed"))
    if not billed:
        return None
    issued_on: date = billed[0]["bill_on"]
    start = issued_on.replace(day=1)
    end = (start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    return start, end


# ══════════════════════════════════════════════════════════════════════════
# THE SEAM BODIES
# ══════════════════════════════════════════════════════════════════════════


def ensure_connection(actor: Any, spec: dict[str, Any]) -> tuple[Any, bool]:
    """The connection for `spec`, made through `services.connect` if it is absent.

    Returns `(row, created)`. The lookup is the database's own unique key
    (`tenant`, `provider_key`, `environment`), so a tenant that connected this
    provider itself keeps ITS row and this block writes nothing — which is the
    right answer: a fixture must never overwrite a utility's real mail server.
    """
    from apps.integrations import services

    tenant_id = _tenant_id()
    existing = services.connection_for(tenant_id, str(spec["provider_key"]))
    if existing is not None:
        return existing, False
    row = services.connect(
        actor=actor,
        tenant_id=tenant_id,
        provider_key=str(spec["provider_key"]),
        environment=models.ENVIRONMENT_PRODUCTION,
        label=str(spec["label"]),
        config=dict(spec["config"]),
        cadence=str(spec["cadence"]),
    )
    return row, True


def _seed_delivery() -> int:
    """One landed kiosk notification, through payments' own door.

    Returns 1 when this call wrote the row and 0 when the key was already
    present — `land_delivery` answers `landed=False` for a replay, which is the
    same idempotence the door itself relies on.
    """
    from apps.integrations import registry as integration_registry
    from apps.integrations import inbound
    from apps.integrations.seams import payments as payments_seam

    manifest = integration_registry.REGISTRY.get(KIOSK_PROVIDER)
    if manifest is None:  # pragma: no cover — the manifest is registered at ready()
        logger.info(
            "sample data (CR-083): no payment notification was landed — the %r provider is "
            "not registered, so there is no operation to take its dedupe key from",
            KIOSK_PROVIDER,
        )
        return 0
    operation = next((one for one in manifest.operations if one.name == KIOSK_OPERATION), None)
    if operation is None:  # pragma: no cover — declared in the manifest
        return 0
    landing = payments_seam.land_inbound_delivery(
        provider=KIOSK_PROVIDER,
        # ⚠ COMPUTED, NOT TYPED. `BR-INT-020` D makes the key the provider's
        # event id composite with the payment/return marker, and the marker
        # comes from the operation's DECLARED natural key.
        event_id=inbound.dedupe_key(operation, KIOSK_EVENT_ID),
        body=dict(KIOSK_BODY),
        received_at=KIOSK_RECEIVED_AT,
        audit_after={"job": "integrations.sample_data", "operation": operation.name},
    )
    return 1 if landing.landed else 0


def _seed_export_batch(actor: Any) -> int:
    """June, closed and handed to the books once — through ledger's own service.

    Returns 1 when a batch was recorded, 0 otherwise. Every refusal is a
    LOGGED SENTENCE naming what is missing (`BR-TEN-060`) and never an
    exception: the connections above are the block's main deliverable and an
    unbalanced demo ledger must not take them down with it.
    """
    from apps.integrations.seams import ledger as ledger_seam

    period = _accounting_month()
    if period is None:
        logger.info(
            "sample data (CR-083): no accounting handover was recorded — the fixture declares "
            "no billed period, so there is no finished month to hand over"
        )
        return 0
    period_start, period_end = period

    # ── the month must be CLOSED first (BR-LED-017) ──────────────────────────
    # A savepoint, because on PostgreSQL a refused statement aborts the whole
    # transaction and this block's connections are already written into it
    # (CLAUDE.md law 14). The suite's SQLite has no such state, so the version
    # without this passes every test and loses the connections in production.
    try:
        with transaction.atomic():
            ledger_seam.close_period(
                actor=actor,
                period_start=period_start,
                period_end=period_end,
                closed_at=CLOSED_AT,
                reason=CLOSE_REASON,
            )
    except Exception as exc:  # noqa: BLE001 — an already-closed month is the common case
        logger.info(
            "sample data (CR-083): %s … %s was not closed by this block (%s: %s). If it is "
            "already closed that is the replay path and the handover below still runs",
            period_start,
            period_end,
            type(exc).__name__,
            exc,
        )

    try:
        with transaction.atomic():
            batch = ledger_seam.create_export_batch(
                actor=actor,
                period_start=period_start,
                period_end=period_end,
                target=EXPORT_TARGET,
                created_at=EXPORT_MADE_AT,
            )
    except Exception as exc:  # noqa: BLE001 — BR-TEN-060: named, never swallowed
        logger.info(
            "sample data (CR-083): no accounting handover was recorded for %s … %s (%s: %s). "
            "A batch is refused over an open month, books that do not foot, or a window "
            "already handed over — the last of which is this block's own replay",
            period_start,
            period_end,
            type(exc).__name__,
            exc,
        )
        return 0
    return 0 if batch is None else 1


def seed_sample_records(actor: Any) -> int:
    """`BR-TEN-056/057` — this module's block: three connections and a history.

    Returns the number of rows it CREATED, which is 0 on a replay — and 0 is
    success here, not a skip. `BR-TEN-063` makes this atomic per module and the
    orchestrator opens that transaction; the savepoints inside are law 14's,
    not a second one.
    """
    written = 0
    mailbox: Any = None
    for spec in SEEDED_CONNECTIONS:
        row, created = ensure_connection(actor, spec)
        if spec is MAILBOX:
            mailbox = row
        written += 1 if created else 0

    # The five runs — `sample_runs` unchanged, because two seeders for one set
    # of rows is two sources of truth (hard-won law 5). It returns [] when its
    # own trace id is already present: `integration_run` is append-only, so a
    # replay cannot correct the first seeding and does not pretend to.
    if mailbox is not None:
        written += len(sample_runs.seed_runs(mailbox))

    written += _seed_delivery()
    written += _seed_export_batch(actor)
    return written


def seed_sample_records_note() -> str:
    """The sentence `S62` renders beside this block, read AFTER it ran."""
    tenant_id = _tenant_id()
    connections = models.IntegrationConnection.objects.filter(
        tenant_id=tenant_id, label__in=sorted(SEEDED_LABELS)
    ).count()
    runs = models.IntegrationRun.objects.filter(tenant_id=tenant_id).count()
    return (
        f"{connections} connections, {runs} runs — including one that failed, which is what "
        "the Runs screen is for"
    )


def remove_sample_records() -> dict[str, Any]:
    """`BR-TEN-061/066` — remove what is free, report the rest BY NAME.

    ⚠ **A CONNECTION WITH RUNS IS RETAINED, AND SO IS EVERY RUN.**
    `integration_run` is append-only (`BR-INT-039`) — a trigger refuses DELETE
    on PostgreSQL and the service refuses on every vendor — so a connection
    those rows point at cannot go either. It is switched OFF instead, which is
    the strongest honest answer: nothing more will run on it and the record of
    what already did survives.

    ⚠ **THE LANDED NOTIFICATION AND THE ACCOUNTING HANDOVER ARE NOT TOUCHED AT
    ALL.** They are payments' and ledger's rows, and both tables are financial
    records this module may not write to, let alone delete from (hard rule 4,
    `BR-TEN-013`). They are reported as retained so the operator reads what is
    still there rather than discovering it later.
    """
    tenant_id = _tenant_id()
    removed = 0
    retained: list[dict[str, Any]] = []
    for row in models.IntegrationConnection.objects.filter(
        tenant_id=tenant_id, label__in=sorted(SEEDED_LABELS)
    ):
        if models.IntegrationRun.objects.filter(
            tenant_id=tenant_id, connection_id=row.id
        ).exists():
            if row.enabled:
                row.enabled = False
                row.status = models.STATUS_OFF
                row.save(update_fields=["enabled", "status", "updated_at"])
            retained.append(
                {
                    "label": f"the {row.label} connection",
                    "reason": (
                        "runs have been recorded against it and a run is a permanent record "
                        "that may never be deleted. The connection is switched off instead, "
                        "so nothing more goes out on it"
                    ),
                }
            )
            continue
        row.delete()
        removed += 1
    if models.IntegrationRun.objects.filter(tenant_id=tenant_id).exists():
        retained.append(
            {
                "label": "the integration runs",
                "reason": (
                    "every attempt is a permanent record of what we sent and what the far "
                    "end said, and permanent records are never deleted"
                ),
            }
        )
    return {"removed": removed, "retained": retained}


def sample_record_count() -> int:
    """How many sample connections this module holds right now, read live."""
    return int(
        models.IntegrationConnection.objects.filter(
            tenant_id=_tenant_id(), label__in=sorted(SEEDED_LABELS)
        ).count()
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-083 (PO 2026-09-07 — *"Im okay with this - please add- Step 30, Integrations"*) · US-INT-020 §4 · US-TEN-019
# generated: 2026-09-07 by the CR-083 integrations sample-data lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint of its own) E=n/a(S62 and S8 render it) F✔ G✔ H=n/a(no money math; the export batch is the ledger's own service)
# gates: pytest tests/test_cr082_integrations_sample_data.py · G68 (the plant on PostgreSQL) · G78 unaffected (this module writes only its own tables)
# exceptions: three tables carry no `is_sample` column and the column is OWED — removal keys on the fixture's own labels, and every append-only row is retained BY NAME (BR-TEN-066)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

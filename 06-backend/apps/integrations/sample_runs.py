# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-020 §4 Test Data · US-INT-021 §4 — the Brazos Bend
#           `email_smtp` runs the walkthrough clicks: 1 Sep 93/93 succeeded ·
#           1 Aug 93/86/7 partial with the seven addresses named · 1 Jul 93/0
#           unconfirmed · a manual test run failed, trace `A7F3C9E1`.
#           Screens: S142
# Rules:    BR-INT-018 (the outcome is COMPUTED from the counts and the far
#           end's confirmation — this fixture NEVER types the word) ·
#           BR-INT-039 (append-only: a replay writes new rows, it does not
#           edit) · CLAUDE.md hard rule 1 (written under tenant context)
# Tests:    06-backend/tests/test_us_int_020_runs.py (reads the same builder) ·
#           10-scripts/render-checks/cr069-c-run-record.mjs (the consumer)
# Impacts:  apps/integrations/management/commands/seed_integration_runs.py
# ───────────────────────────────────────────────────────
"""The five runs the demo is read down the phone about.

⚠ THE FIXTURE NEVER TYPES AN OUTCOME WORD. Every run below is written through
`services.start_run` / `services.finish_run` with counts and a `confirmed`
flag, and the outcome is whatever `BR-INT-018` computes from them. That is
deliberate: a fixture that wrote `outcome="unconfirmed"` directly would make
the walkthrough green while the rule it exists to demonstrate was broken —
the exact shape `US-INT-021` TC-2 calls *"trivially satisfied by a stub"*.

⚠ AND IT IS IDEMPOTENT BY ADDITION, NOT BY UPDATE. `integration_run` is
append-only (`BR-INT-039`), so a second seeding cannot correct the first. It
therefore checks whether the fixture's trace ids are already present and does
nothing when they are — the only honest replay for an append-only table.

The trace id `A7F3C9E1` is FIXED here and generated everywhere else: the demo
is a support agent being read eight characters over the telephone, and a
random one cannot be written into a walkthrough. `start_run` generates; this
fixture overwrites the value on the still-open row, which is lawful because
the row is not finished yet and the append-only rule binds from `finished_at`.
"""

from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from typing import Any

from apps.integrations import models, services

#: The support reference the walkthrough types, and the one the PO is read.
DEMO_TRACE = "A7F3C9E1"

#: The leak-path run's own reference (`US-INT-020` TC-6). It is a SEPARATE run
#: from the support call above on purpose: the demo's failed test carries the
#: mail server's own sentence about a password, and the cross-tenant quote is a
#: different provider message on a different day. Putting both on one row would
#: have made the demo prove TC-6 by accident and TC-6 prove nothing.
LEAK_TRACE = "C4D5E6F7"

#: The seven the 1 August send could not deliver (`US-INT-020` §4). Account
#: numbers are the customer's own number, never a database id (B14 rule 31).
SEVEN = (
    ("A-10432", "j.ortiz@example.invalid", "No such mailbox"),
    ("A-10518", "d.whitfield@example.invalid", "No such mailbox"),
    ("A-10677", "p.nakamura@example.invalid", "Domain not found"),
    ("A-10703", "s.abbott@example.invalid", "Mailbox full"),
    ("A-10744", "r.delgado@example.invalid", "No such mailbox"),
    ("A-10810", "m.fitzgerald@example.invalid", "Domain not found"),
    ("A-10922", "c.brennan@example.invalid", "No such mailbox"),
)

#: The leak-path fixture (`US-INT-020` TC-6): a mail server quoting ANOTHER
#: utility's customer back at us. Stored scrubbed and rendered on one screen.
LEAK = (
    "550 5.1.1 relay refused for account 4471-0021 at 1408 Pecan St, "
    "Lone Star Ridge — contact postmaster@lonestarridge.example"
)


def _at(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=dt_timezone.utc)


def _open_run(connection: Any, *, operation: str, direction: str, trigger: str,
              started: datetime, trace: str | None = None) -> models.IntegrationRun:
    """A run row, back-dated, with its trace id fixed when the demo needs one.

    ⚠ `started_at` IS PART OF THE COMPOSITE PRIMARY KEY (`tenant_id,
    started_at, id` — it is the partition key, B2 r22), so Django refuses it in
    `save(update_fields=…)`: *"the following fields … are primary keys"*. It is
    also `auto_now_add`, so a value handed to `create()` is discarded. The one
    way to back-date is a queryset `UPDATE`, which is lawful here because the
    run is not finished yet — the append-only trigger fires only once
    `finished_at` is set.

    ⚠ AND THE ROW MUST THEN BE RE-READ. The in-memory object still holds the
    OLD `started_at`, which is two thirds of its primary key, so a later
    `save()` would build a `WHERE` clause matching nothing and write nothing at
    all — silently. Measured 2026-09-04: without the re-read, `finish_run`
    returned a run whose outcome was correct in memory and absent from the
    database.
    """
    run = services.start_run(
        connection=connection, operation=operation, direction=direction, trigger=trigger
    )
    changes: dict[str, Any] = {"started_at": started}
    if trace is not None:
        changes["trace_id"] = trace
    models.IntegrationRun.objects.filter(
        tenant_id=run.tenant_id, id=run.id, started_at=run.started_at
    ).update(**changes)
    return models.IntegrationRun.objects.get(tenant_id=run.tenant_id, id=run.id)


def seeded(tenant_id: Any) -> bool:
    """Has this fixture already been written? Append-only, so a replay adds."""
    return models.IntegrationRun.objects.filter(
        tenant_id=tenant_id, trace_id=DEMO_TRACE
    ).exists()


def seed_runs(connection: models.IntegrationConnection) -> list[models.IntegrationRun]:
    """The five runs, newest last, each closed through the real service.

    Returns an empty list, having written nothing, when the fixture is already
    present. `integration_run` is append-only, so a replay cannot correct the
    first seeding and must not pretend to.
    """
    if seeded(connection.tenant_id):
        return []
    written: list[models.IntegrationRun] = []

    # 1 July — the provider answered and would not say how many it accepted.
    # 93 attempted, nothing else claimed. `confirmed=False` is the whole story:
    # BR-INT-018 turns this into `unconfirmed`, never `succeeded`, never
    # `failed`, and the tiles read dashes rather than zeroes.
    july = _open_run(connection, operation="send_message", direction="outbound",
                     trigger="scheduled", started=_at(2026, 7, 1, 6, 3))
    written.append(
        services.finish_run(
            july, attempted=93, succeeded=0, failed=0, skipped=0, confirmed=False,
            summary="We handed over 93 messages and the provider did not say how many it accepted.",
        )
    )

    # 1 August — 86 went, seven were refused, and the seven are NAMED.
    august = _open_run(connection, operation="send_message", direction="outbound",
                       trigger="scheduled", started=_at(2026, 8, 1, 6, 2))
    written.append(
        services.finish_run(
            august, attempted=93, succeeded=86, failed=7, skipped=0, confirmed=True,
            summary="Seven addresses were refused by the mail server.",
            items=[
                {"ref": ref, "detail": address, "outcome": "failed", "provider_text": said}
                for ref, address, said in SEVEN
            ],
        )
    )

    # 1 September — every message accepted, and the far end said so.
    september = _open_run(connection, operation="send_message", direction="outbound",
                          trigger="scheduled", started=_at(2026, 9, 1, 6, 2))
    written.append(
        services.finish_run(
            september, attempted=93, succeeded=93, failed=0, skipped=0, confirmed=True,
            summary="Every message was accepted by the mail server.",
        )
    )

    # 2 September — the leak path (TC-6). A mail server quoting a DIFFERENT
    # utility's customer back at us, stored scrubbed by the seam and rendered
    # on this one screen to this one tenant.
    leak = _open_run(connection, operation="send_message", direction="outbound",
                     trigger="manual", started=_at(2026, 9, 2, 9, 40), trace=LEAK_TRACE)
    written.append(
        services.finish_run(
            leak, attempted=1, succeeded=0, failed=1, skipped=0, confirmed=True,
            summary="The mail server refused to relay the message.",
            provider_error=LEAK,
            items=[{"ref": "TEST", "detail": "alex@brazosbend.example", "outcome": "failed",
                    "provider_text": LEAK}],
        )
    )

    # 3 September — the manual test the support call is about, with the mail
    # server's OWN sentence underneath ours (frame 52.2).
    test = _open_run(connection, operation="send_message", direction="outbound",
                     trigger="manual", started=_at(2026, 9, 3, 14, 11), trace=DEMO_TRACE)
    written.append(
        services.finish_run(
            test, attempted=1, succeeded=0, failed=1, skipped=0, confirmed=True,
            summary="The mail server rejected the password.",
            provider_error="535 5.7.8 AUTHENTICATION FAILED",
            items=[
                {
                    "ref": "TEST",
                    "detail": "alex@brazosbend.example",
                    "outcome": "failed",
                    "provider_text": "535 5.7.8 AUTHENTICATION FAILED",
                }
            ],
        )
    )
    return written


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-020 §4 · US-INT-021 §4 (EP-INT-06)
# generated: 2026-09-04 by the CR-069 wave C build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a(fixture data, no money)
# gates: pytest tests/test_us_int_020_runs.py (the same builder drives the tests) · the walkthrough
# exceptions: `started_at` and `trace_id` are set on the STILL-OPEN row — lawful on every vendor, and the reason is in the docstring
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-027 (EP-INT-07) — the dated warning, CR-069 wave H task H2
# Rules:    BR-INT-042 (P6 — credentials have a lifecycle, not a moment:
#           `expires_at` on every credential; a sweep that warns DAYS AHEAD
#           WITH THE DATE; a renewal path that keeps the whole run history) ·
#           BR-INT-054 as amended 2026-09-06 (**scheduling is Runbooks'** —
#           this module does not decide when this runs) · BR-INT-015 (a
#           failure surfaces, never silently) · BR-INT-008 (integrations
#           sends nothing itself) · BR-INT-003 (a secret is never logged,
#           never returned, never in an error message) · BR-TEN-081 (the
#           utility's own clock decides what day it is) · BR-TEN-043 (event
#           time is the CALLER's, never a clock read down here) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 7 (audit)
# Tests:    06-backend/tests/test_us_int_027_expiry.py
# Impacts:  apps/integrations/jobs.py (`integration.sweep_expiry` handler) ·
#           apps/integrations/selectors.py (the card carries `expiry`) ·
#           apps/integrations/seams/tenancy.py (whose calendar) ·
#           07-frontend/src/features/integrations/ConnectionDetailPage.tsx
# ───────────────────────────────────────────────────────
"""A credential's last eleven days — the warning, and the word for lapsed.

⚠ **THIS MODULE DOES NOT DECIDE WHEN IT RUNS, AND THAT IS A RULING RATHER THAN
A STYLE CHOICE.** `BR-INT-054` was sharpened by the PO on 2026-09-06 —
*"We want integration scope about building a conn crore , managing keys/secret,
managing lifecycle of connect - while business logic , scheduling , processing
we will take it in run book."* Integrations keeps three things: building a
connection, holding keys and secrets, the lifecycle of a connection. **Deciding
when to look is SCHEDULING and belongs to Runbooks.**

So `sweep_expiry()` below is a plain callable that something else invokes. It
reads no clock of its own, holds no cron expression, computes no `next_run_at`,
and knows nothing about nightly, midnight, timezone spreading or catch-up. It
takes the moment it is being run FOR as a parameter and answers what it found.
`CR-069` §20.4 puts wave H whole on the integrations side with exactly this
sentence attached: *"its sweep body is triggered by Runbooks' scheduler once G
moves — that is integrations work running on a shared clock, not a split of
ownership."*

**If you are here to add a schedule, you are in the wrong module.** The queue
and the worker (`jobs.py`) are how a connection's work RUNS and stay here; what
decides that it should run tonight does not.

THE RULE THIS IMPLEMENTS, IN ITS OWN WORDS
-------------------------------------------
`BR-INT-042`: *"Credentials have a lifecycle, not a moment. `expires_at` on
every credential; a nightly sweep that warns days ahead with the date in words
(eleven days before, on the dashboard and by email); a renewal path that keeps
the connection's whole run history … Break this and every connector dies
quietly at three in the morning, once."*

Four states, and the boundaries are closed at both ends so nothing falls between
them:

    ok        `expires_at` is beyond the window, or there is no `expires_at`
    warning   `expires_at` is inside the window and still in the future
    lapsed    `expires_at` has passed
    unknown   there is no active credential to have an opinion about

⚠ **`expires_at IS NULL` IS `ok` FOR EVER, NOT `ok` FOR NOW.** An SMTP password
a utility typed has no expiry date because it genuinely does not expire — the
mail server will accept it until somebody changes it. Warning about it would
teach a clerk that this box lies, and the next warning they ignore would be the
real one. `US-INT-027` states this directly and the sweep skips those rows
before it looks at anything else.

WHAT THE SWEEP MAY SAY, AND WHAT IT MAY NOT
--------------------------------------------
It writes exactly two things: `expiry_warned_on` on the credential (so it says
it once a day) and, when a credential has actually lapsed, the connection's
status word. It writes **no run row** — a sweep that looked at a credential's
date never dialled a provider, and `IntegrationRun` is the record of a
CONNECTION's own activity with a far end (`BR-INT-054`(3)). A row saying *we
read a column* would make the runs table on S142 unreadable, which is the table
the exit test is about.

⚠ **AND IT NEVER PUTS A SECRET ANYWHERE (BR-INT-003).** Nothing in this file
reads `payload_enc`; it does not import `credential_secrets` and has no reason
to. What it handles is a DATE and a version NUMBER. The masked hint is the most
identifying thing that reaches a screen or an audit row, exactly as elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from apps.integrations import models
from apps.integrations.registry import REGISTRY, Manifest, Registry
from apps.integrations.seams import tenancy as tenancy_seam
from core import audit as core_audit
from core.tenancy import current_tenant_id

#: The four words a credential's lifecycle can be in. Closed vocabulary — a
#: screen picks its sentence from these and never re-derives them from a date,
#: so the boundary between *warning* and *lapsed* exists in ONE place.
STATE_OK = "ok"
STATE_WARNING = "warning"
STATE_LAPSED = "lapsed"
STATE_UNKNOWN = "unknown"
EXPIRY_STATES = (STATE_OK, STATE_WARNING, STATE_LAPSED, STATE_UNKNOWN)

#: Audit actions. A credential change is exactly the kind of act an auditor
#: asks about, so these sit beside wave E's `integration.credential_rotated`
#: and carry the same shape: the version number and the masked hint, never a
#: payload (BR-INT-003, CLAUDE.md hard rule 7).
AUDIT_EXPIRY_WARNED = "integration.credential_expiry_warned"
AUDIT_EXPIRY_LAPSED = "integration.credential_lapsed"

#: `BR-INT-042` — the connection's word once the secret is no longer usable.
#: `STATUS_NOT_WORKING` already exists (wave A) and already renders as *Not
#: working* with its own sentence; a lapse is not a new STATE, it is a new
#: REASON for one this product already has. Inventing `status = "expired"`
#: would have meant every screen, filter and count in the module learning a
#: sixth word for a situation the fifth already covers.
LAPSED_SENTENCE_KEY = "integrations.expiry.lapsed"


@dataclass(frozen=True)
class ExpiryView:
    """What a screen is allowed to know about a credential's lifecycle.

    Deliberately NOT the credential row: a selector that returned the model
    would put `payload_enc` one attribute access away from a serialiser.
    """

    state: str
    #: The lapse moment, or None when this credential does not expire.
    expires_at: datetime | None
    #: Whole days from the moment asked about until `expires_at`. Negative once
    #: it has passed; None when there is nothing to count to.
    days_left: int | None
    #: The window this provider asked for, in days — the manifest's own number.
    window_days: int
    #: The active credential's version, for the audit trail and the screen's
    #: *version 2* line. A number, never an id (B14 rule 31).
    version: int | None

    @property
    def warns(self) -> bool:
        return self.state in (STATE_WARNING, STATE_LAPSED)

    def as_dict(self) -> dict[str, Any]:
        """The wire shape. `expires_at` travels as ISO-8601 and the SCREEN
        formats it in the tenant's regional format — a date rendered by the
        server would be a second formatting path (BR-SHL-023)."""
        return {
            "state": self.state,
            "expires_at": None if self.expires_at is None else self.expires_at.isoformat(),
            "days_left": self.days_left,
            "window_days": self.window_days,
            "version": self.version,
        }


def _window_days(manifest: Manifest | None) -> int:
    """The provider's own warning window, or the fourteen-day default.

    An unknown provider gets the default rather than zero: `BR-INT-037` says
    the registry refuses unknown keys at the service boundary, so reaching here
    with None means something upstream is already wrong — and answering "no
    warning" would turn one fault into a silent one.
    """
    return 14 if manifest is None else int(manifest.expiry_warning_days)


def view_for(
    connection: models.IntegrationConnection,
    *,
    now: datetime,
    registry: Registry = REGISTRY,
    credential: models.IntegrationCredential | None = None,
) -> ExpiryView:
    """The lifecycle state of THIS connection's active credential at `now`.

    `now` is a PARAMETER and never a clock read (BR-TEN-043) — the same
    discipline `notifications.queue_staff_alert` states about `finished_at`. It
    is also what makes the whole of this testable without freezing a clock.
    """
    manifest = registry.get(connection.provider_key)
    window = _window_days(manifest)
    row = credential
    if row is None:
        row = (
            models.IntegrationCredential.objects.filter(
                connection=connection, is_active=True, slot=models.CREDENTIAL_SLOT_PRIMARY
            )
            .only("version", "expires_at", "expiry_warned_on")
            .first()
        )
    if row is None:
        # No active credential at all. Not `ok` — `ok` is a claim that the
        # secret is good, and there isn't one. The card already says *Not set
        # up* through its own state word; this simply declines to add a second,
        # contradictory opinion.
        return ExpiryView(STATE_UNKNOWN, None, None, window, None)
    if row.expires_at is None:
        # An SMTP password. It does not expire, so there is nothing to warn
        # about — for ever, not for now. See the module docstring.
        return ExpiryView(STATE_OK, None, None, window, row.version)
    remaining = row.expires_at - now
    # Whole days, rounded DOWN, so "eleven days" means eleven whole days are
    # left rather than ten and a half dressed up as eleven. `//` on a timedelta
    # floors toward negative infinity, which is also what we want past the
    # boundary: four hours after a lapse is `-1`, not `0`.
    days_left = remaining.days if remaining >= timedelta(0) else -((-remaining).days + 1)
    if remaining <= timedelta(0):
        state = STATE_LAPSED
    elif remaining <= timedelta(days=window):
        state = STATE_WARNING
    else:
        state = STATE_OK
    return ExpiryView(state, row.expires_at, days_left, window, row.version)


@dataclass(frozen=True)
class SweepOutcome:
    """What one sweep found and did — the shape a caller reports on.

    ⚠ `notified` is a THREE-valued fact and the third value matters: `False`
    means notifications declined or could not be reached, and the reason is on
    `notify_note`. `seams/notifications.py` makes the same point about counts
    — *"a screen that renders those the same tells a utility nothing is waiting
    when the truth is that nobody looked."*
    """

    looked_at: int
    warned: int
    already_warned_today: int
    lapsed: int
    notified: int
    notify_note: str | None = None
    declined: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "looked_at": self.looked_at,
            "warned": self.warned,
            "already_warned_today": self.already_warned_today,
            "lapsed": self.lapsed,
            "notified": self.notified,
            "notify_note": self.notify_note,
            "declined": self.declined,
        }


def sweep_expiry(
    *,
    actor: Any = None,
    now: datetime,
    today: date | None = None,
    registry: Registry = REGISTRY,
) -> SweepOutcome:
    """Look at every active credential in THIS tenant and say what is due.

    ⚠ **A CALLABLE, NOT A SCHEDULE.** Read the module docstring: under
    `BR-INT-054` as amended on 2026-09-06, deciding *when* to look is Runbooks'
    work. This function is what Runbooks (today: `jobs.run_sweep_expiry_job`,
    or a person, or a test) INVOKES. It contains no cron, reads no clock and
    sets no `next_run_at`.

    `now` is the moment being swept for and `today` is the tenant's own
    calendar date for the once-a-day rule. `today=None` asks this function to
    resolve it through the tenancy seam; when the seam cannot answer, the sweep
    **declines rather than guesses** — a warning dated against the wrong
    calendar tells a utility its mailbox lapses on a day it does not.

    Runs inside the caller's tenant context (CLAUDE.md hard rule 1): every
    query below is an ordinary tenant-scoped queryset and RLS FORCE is the
    guard underneath it.

    ⚠ **THAT PARAGRAPH WAS A COMMENT CLAIMING A GUARANTEE AND NOT THE
    GUARANTEE — hard-won law 1, `DEF-INT-5568`.** The credential read below
    named `is_active` and `expires_at` and no tenant at all, so on SQLite (which
    has no RLS, law 14) a sweep run for one utility warned about every
    utility's keys, and the whole suite was green. Two things make this a
    per-tenant callable rather than a cross-tenant sweep, and both were already
    true: the docstring's first line says *every active credential in THIS
    tenant*, and its only caller — `jobs.run_sweep_expiry_job` — is dispatched
    by `core.jobs` inside `tenant_context(record["tenant_id"])`. So
    `BR-TEN-074`'s shape (per-tenant context, per-tenant transaction) is
    satisfied ABOVE this function; what was missing is the second strand, which
    `runners/serve.py::_connection_for` spells out in this module's own words.

    **With NO tenant open it DECLINES rather than sweeping everybody**
    (hard-won law 3): a warning is an email to a utility's admins, and sending
    every utility's admins every utility's expiry dates is worse than a sweep
    that did not run and said so.
    """
    tenant_id = current_tenant_id()
    if tenant_id is None:
        return SweepOutcome(
            looked_at=0,
            warned=0,
            already_warned_today=0,
            lapsed=0,
            notified=0,
            declined=(
                "no utility was open, so nothing was looked at. A sweep with no tenant "
                "would warn every utility's admins about every utility's keys."
            ),
        )
    calendar_day = tenancy_seam.today() if today is None else today
    if calendar_day is None:
        return SweepOutcome(
            looked_at=0,
            warned=0,
            already_warned_today=0,
            lapsed=0,
            notified=0,
            declined=(
                "the utility's own calendar could not be read, so nothing was warned. "
                "A date on the wrong calendar is worse than one that has not arrived."
            ),
        )

    # Only credentials that CAN lapse. `expires_at__isnull=True` never reaches
    # the loop at all, so an SMTP password cannot be warned about even by a
    # future bug in the state machine above.
    rows = list(
        models.IntegrationCredential.objects.filter(
            tenant_id=tenant_id, is_active=True, expires_at__isnull=False
        ).select_related("connection")
    )
    warned = 0
    already = 0
    lapsed = 0
    due: list[tuple[models.IntegrationCredential, ExpiryView]] = []
    for row in rows:
        connection = row.connection
        view = view_for(connection, now=now, registry=registry, credential=row)
        if not view.warns:
            continue
        if view.state == STATE_LAPSED:
            lapsed += _mark_lapsed(actor, connection, row, view)
        if row.expiry_warned_on == calendar_day:
            # Said already today. The whole of "never twice for the same day".
            already += 1
            continue
        _record_warning(actor, connection, row, view, calendar_day)
        warned += 1
        due.append((row, view))

    notified, note = _notify_admins(actor=actor, due=due, on=calendar_day)
    return SweepOutcome(
        looked_at=len(rows),
        warned=warned,
        already_warned_today=already,
        lapsed=lapsed,
        notified=notified,
        notify_note=note,
    )


def _record_warning(
    actor: Any,
    connection: models.IntegrationConnection,
    row: models.IntegrationCredential,
    view: ExpiryView,
    on: date,
) -> None:
    """Stamp the day we said it, and write the audit row an auditor asks for.

    ⚠ The stamp and the audit row go together on purpose. A stamp with no audit
    row is a silent product decision; an audit row with no stamp is a warning
    that arrives again tomorrow morning and again tomorrow afternoon.
    """
    models.IntegrationCredential.objects.filter(pk=row.pk).update(expiry_warned_on=on)
    row.expiry_warned_on = on
    core_audit.money_action(
        actor,
        AUDIT_EXPIRY_WARNED,
        "integration_connection",
        connection.id,
        after={
            "provider_key": connection.provider_key,
            "version": view.version,
            # The DATE, which is the whole content of the warning, and the
            # count of days, which is what makes it readable. No hint, no
            # payload, nothing that identifies the secret itself (BR-INT-003).
            "expires_at": None if view.expires_at is None else view.expires_at.isoformat(),
            "days_left": view.days_left,
            "window_days": view.window_days,
            "warned_on": on.isoformat(),
        },
    )


def _mark_lapsed(
    actor: Any,
    connection: models.IntegrationConnection,
    row: models.IntegrationCredential,
    view: ExpiryView,
) -> int:
    """The connection stops claiming to work once its secret has lapsed.

    Returns 1 when this call CHANGED the word, 0 when it was already right —
    so a second sweep on the same day does not report a lapse twice, and the
    audit trail carries one row for one event.

    ⚠ **IT DOES NOT TOUCH `enabled`, AND IT DOES NOT CANCEL ANYTHING.** This is
    `BR-INT-016`'s discipline read across: bills rest `queued` and the
    dispatcher already surfaces them as config-missing through
    `provider_seam.channel_route`, which answers `provider_not_connected`
    because there is no usable credential. Nothing is lost and nothing is sent;
    the moment a utility re-authorises, the queue drains on its own.
    """
    if connection.status == models.STATUS_NOT_WORKING:
        return 0
    before = connection.status
    connection.status = models.STATUS_NOT_WORKING
    connection.last_test_ok = False
    connection.last_test_text = None  # the screen composes the sentence, not us
    connection.save(
        update_fields=["status", "last_test_ok", "last_test_text", "updated_at"]
    )
    core_audit.money_action(
        actor,
        AUDIT_EXPIRY_LAPSED,
        "integration_connection",
        connection.id,
        before={"status": before},
        after={
            "status": connection.status,
            "provider_key": connection.provider_key,
            "version": view.version,
            "expires_at": None if view.expires_at is None else view.expires_at.isoformat(),
        },
    )
    return 1


#: The neighbour's published write, named once so the contract is greppable
#: from both sides (G20 harvests these). ⚠ **NOTIFICATIONS DOES NOT PUBLISH
#: THIS YET** — see `_notify_admins`.
NOTIFICATIONS_EXPIRY_NOTICE = "queue_expiry_notice"


def _notify_admins(
    *, actor: Any, due: list[tuple[Any, ExpiryView]], on: date
) -> tuple[int, str | None]:
    """One message to the System Admins, queued through notifications.

    ⚠ **INTEGRATIONS SENDS NOTHING ITSELF (`BR-INT-008`).** Even here — where
    the thing being warned about IS the mailbox — the message goes on the
    queue and the dispatcher sends it. That is not ceremony: the mailbox about
    to lapse is frequently the only one connected, so a direct send would try
    to deliver the warning through the very credential it is warning about.

    ⚠ **AND NOTIFICATIONS PUBLISHES NO SUCH CALLABLE TODAY, SO THIS RETURNS
    `(0, <why>)` AND SAYS SO OUT LOUD.** `queue_staff_alert` is the nearest
    thing that exists and it is a BULK-SUMMARY shape — it refuses a
    `failed_count` below 1 and renders as *N of M failed*, so calling it here
    would put *"Sign-in about to lapse: 1 of 1 failed"* in the bell. A message
    that misdescribes what happened is worse than one that has not been built,
    which is why this declines in words rather than borrowing a shape that
    does not fit.

    The screens do NOT depend on this: the dated warning reaches a clerk on
    S142 and on the S7 attention strip either way, and those are what
    `BR-INT-042`'s exit test asks for. `DEF-INT-4214` carries the missing half.
    """
    if not due:
        return 0, None
    from apps.integrations.seams import notifications as notifications_seam

    published = notifications_seam._resolve(NOTIFICATIONS_EXPIRY_NOTICE, kind="services")
    if published is None:
        return 0, (
            f"{len(due)} connection(s) were warned on screen and no message was queued: "
            "notifications publishes no expiry notice yet (DEF-INT-4214). The warning "
            "is on the dashboard and on the connection, which is where the rule's exit "
            "test looks."
        )
    queued = 0
    for _row, view in due:  # pragma: no cover — unreachable until the seam lands
        try:
            published(actor=actor, expires_at=view.expires_at, on=on)
        except Exception:  # noqa: BLE001 — a notice that fails must not lose the stamp
            continue
        queued += 1
    return queued, None


__all__ = [
    "AUDIT_EXPIRY_LAPSED",
    "AUDIT_EXPIRY_WARNED",
    "EXPIRY_STATES",
    "ExpiryView",
    "LAPSED_SENTENCE_KEY",
    "NOTIFICATIONS_EXPIRY_NOTICE",
    "STATE_LAPSED",
    "STATE_OK",
    "STATE_UNKNOWN",
    "STATE_WARNING",
    "SweepOutcome",
    "sweep_expiry",
    "view_for",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-027 (EP-INT-07 — the dated warning) · BR-INT-042 · BR-INT-054 as amended 2026-09-06
# generated: 2026-09-06 by the CR-069 wave H build lane
# checklist: A✔ B✔ C✔ D✔(the sweep is reachable as `integration.sweep_expiry`; the state rides on the card) E✔(ConnectionDetailPage's WarningBox and the S7 strip read `expiry`) F✔ G✔ H=n/a(no 🔒 path — nothing here reads `payload_enc`)
# gates: pytest tests/test_us_int_027_expiry.py · G32 (the lapsed sentence key resolves in all eleven catalogues) · G77 (no `provider_key ==` here — the window is manifest data)
# exceptions: the admin MESSAGE is NOT queued — notifications publishes no expiry notice and the nearest existing callable is a bulk-summary shape that would misdescribe the event. Declined in words, filed as DEF-INT-4214, and the sweep reports `notified: 0` with the reason rather than a silent zero
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

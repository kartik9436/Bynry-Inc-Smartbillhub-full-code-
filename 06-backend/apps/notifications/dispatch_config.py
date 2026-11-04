# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-004 (Settings → Notifications tab: the delivery/dispatch home
#           — the CONFIG half: batch size, quiet-hours window, channel
#           activation, and the audited edit)   Screens: S8
# Rules:    BR-TEN-041 (#8 — the Notifications tab IS the dispatch home) ·
#           BR-NOT-005 (batch size/cadence are tenant-config, never a code
#           constant) · BR-BIL-016 (batch default 500) · BR-NOT-009 (quiet
#           hours, default 08:00–21:00 tenant time; print/PDF exempt) ·
#           BR-NOT-010 (v1 channels: print live · email W6 · SMS v1.1) ·
#           BR-TEN-016 (a settings edit is audited, before→after) ·
#           BR-IDN-009 (server-enforced role gating is THE gating) ·
#           CLAUDE.md rule 1 (tenant scoping; RLS FORCE) · rule 7 (audited)
# Tests:    06-backend/tests/test_us_not_004_dispatch_config.py ·
#           06-backend/tests/test_us_not_004_dispatch_config_isolation.py
# Impacts:  apps/notifications/dispatcher.py (reads this row EVERY cycle, so a
#           saved change takes effect at the next hand-off — T7-17 step 4)
# ───────────────────────────────────────────────────────
"""The tenant's dispatch configuration — read by the dispatcher, edited on S8.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file decides the HOURS during which
a utility's customers may be emailed and texted (BR-NOT-009), which is a
compliance control, and it is the one write path into a tenant-scoped table.
AI-authored 2026-08-15 under the PO ruling of 2026-08-09 ("AI will do it; we
will review it later as human"); row in 12-governance/09-human-review-ledger.md.

B1 boundary: this module owns `notification_settings` and this file is the only
write path into it. BR-TEN-031 puts the settings FRAMEWORK in tenancy and the
settings CONTENT in the owning module — the S8 tab is tenancy's screen, these
four values are notifications'.

╔══════════════════════════════════════════════════════════════════════════╗
║  READ EVERY CYCLE. NOTHING HERE IS CACHED, AND NOTHING IS A CONSTANT.    ║
╚══════════════════════════════════════════════════════════════════════════╝

US-NOT-002 TC-2 and T7-17 both turn on the same sentence: *"config read per
dispatch cycle"*. A dispatcher that read the batch size once at process start
would honour a change only after a restart, and the utility that raised its
batch size to clear a backlog would watch nothing happen. So `dispatch_settings`
is called at the top of each cycle and its result is used for that cycle only.

The half of that rule which is NOT this file's is worth stating because it is
easy to get backwards: a batch already handed to a provider is a FACT (T7-17
step 3). Re-reading the config never claws one back or re-cuts it; it decides
the size of the NEXT hand-off. That belongs to the dispatcher and is asserted
there.

────────────────────────────────────────────────────────────────────────────
THE ROW IS CREATED ON FIRST READ, WITH THE RATIFIED DEFAULTS
────────────────────────────────────────────────────────────────────────────
A tenant that has never opened S8 has no row. It still has a configuration:
BR-BIL-016 says 500 and BR-NOT-009 says 08:00–21:00, and those are the column
defaults on `NotificationSettings` — ONE home for each ratified figure, so a
`.get(key, 500)` here would be a second copy free to drift from the tenant's own
screen (the mistake `apps/billing/settings_seam.py` documents at length).

`dispatch_settings()` therefore get-or-creates. There is deliberately no
"unset" state: an absent row and a defaulted row must not be two behaviours,
because the dispatcher would have to interpret the difference and nothing rules
on what it means.

────────────────────────────────────────────────────────────────────────────
WHAT AN EDIT MAY AND MAY NOT DO
────────────────────────────────────────────────────────────────────────────
* **System Admin only** (US-NOT-004 TC-5; A1: Settings screens are System
  Admin). Enforced HERE with `@require_role`, in the service, so it holds for
  every endpoint, job and shell that forgot to gate (BR-SHL-025).
* **Batch size > 0** (TC-6). Refused in the service AND by the CHECK
  constraint: a zero would make the dispatcher select nothing and look, from
  every screen, exactly like a provider outage.
* **A window must end after it starts.** `21:00–08:00` is refused rather than
  read as "wraps midnight" — see the model's constraint comment.
* **Email and SMS activation are settable, print is not.** BR-BIL-036 makes
  print the floor; there is no column to turn it off.
* **One audit row per save** (`notification_settings.updated`), carrying only
  the fields that ACTUALLY changed, before→after. T7-16 and T7-17 both assert
  "ONE audit row" with exactly that shape.

WHAT THIS FILE DOES NOT DO
--------------------------
* **It does not dispatch, and it does not decide whether a moment is inside the
  window.** It stores two wall-clock times. Turning them into "may this row go
  out now?" needs the tenant's ZONE, which is a tenancy read
  (`apps/notifications/tenancy_seam.py`), and belongs to the dispatcher.
* ⚠ **[AMENDED 2026-08-18] It DOES hold the four A15 "(opt)" toggles now.**
  This bullet used to defer them to OQ-205 (*"names no seeded default"*); the
  PO closed it (2026-08-17, C-13 verbatim: *"keep them default to start with
  Utility will amake them off"* → BR-NOT-022) — DEFAULT ON, reversing the
  off-by-default recommendation. One consumer is wired
  (`receipt_on_record_payment_election`, read by `apps/payments/receipts.py`);
  the other three are stored and editable with their consumers honestly
  reported unbuilt on the wire and on the screen.
* **It does not report provider status.** US-NOT-004 §5 marks that
  `computed-display`, read from integrations; it lives in
  `apps/notifications/provider_seam.py` and is not stored here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Any

from django.db import transaction

from apps.notifications import models
from core import audit, errors
from core import tenancy as core_tenancy
from core.permissions import SYSTEM_ADMIN, require_role

#: Hard rule 7 · field map §1 (*"`audit_log` `notification_settings.updated`"*).
#: `entity.action`, the dotted grammar `core.audit` documents, and the exact
#: string T7-16 step 1 and T7-17 step 2 both name.
AUDIT_ACTION = "notification_settings.updated"
AUDIT_ENTITY = "notification_settings"

#: The editable field names, in the order the S8 card shows them. Named once so
#: the audit diff, the validation and the read all walk the same list — a field
#: added to one and forgotten in another is how a setting becomes editable and
#: unaudited.
EDITABLE_FIELDS: tuple[str, ...] = (
    "dispatch_batch_size",
    "quiet_hours_start",
    "quiet_hours_end",
    "email_dispatch_active",
    "sms_dispatch_active",
    # ── the four A15 "(opt)" send-time elections, in A15's own order ────────
    # ADDED 2026-08-18 (CR-009 C-13, OQ-205 CLOSED — PO: *"keep them default to
    # start with Utility will amake them off"*). Stored on the same row, edited
    # through this same audited write, DEFAULT ON per the ruling.
    "receipt_on_record_payment",
    "credit_notice_email",
    "bookkeeper_copies",
    "lockbox_receipts",
)

#: The four elections, named once so the API, the screen and the validation
#: walk one list (the EDITABLE_FIELDS discipline, scoped to the subset).
ELECTION_FIELDS: tuple[str, ...] = (
    "receipt_on_record_payment",
    "credit_notice_email",
    "bookkeeper_copies",
    "lockbox_receipts",
)


@dataclass(frozen=True)
class DispatchSettings:
    """One tenant's dispatch configuration, as of this read.

    Frozen because a dispatch cycle must not be able to edit its own governing
    config halfway through: the cycle reads once, uses that snapshot for its
    hand-offs, and the NEXT cycle reads again (T7-17 steps 3–4).
    """

    dispatch_batch_size: int
    quiet_hours_start: time
    quiet_hours_end: time
    email_dispatch_active: bool
    sms_dispatch_active: bool
    # The four A15 elections (BR-NOT-022, default ON — PO 2026-08-17, C-13).
    receipt_on_record_payment: bool
    credit_notice_email: bool
    bookkeeper_copies: bool
    lockbox_receipts: bool

    def channel_is_active(self, channel: str) -> bool:
        """Is this channel's SEND switched on for this tenant?

        Print is always True and has no column: BR-BIL-036 makes it the floor
        (US-NOT-003 — *"print/PDF — live v1"*). Email and SMS answer from their
        flags, which ship False until W6 and v1.1 respectively.

        NOTE what this does NOT answer: whether a PROVIDER exists to send
        through. A tenant can switch email on at W6 and still have no mailbox
        connected — US-NOT-003 TC-5, *"rows stay queued; config-missing surfaced
        on the dispatch home"*. That question is the provider seam's.
        """
        if channel == models.CHANNEL_PRINT:
            return True
        if channel == models.CHANNEL_IN_APP:
            # ⚠ ALWAYS ON, AND WITH NO COLUMN — the same shape as print, for a
            # different reason (BR-NOT-019, PO 2026-08-17).
            #
            # An activation flag exists to defer a SEND until the platform or
            # the tenant is ready for it. In-app has nothing to be ready for:
            # no vendor, no credentials, no connection to make, no cost and no
            # outside party. A flag here would be a switch with nothing behind
            # it in the OTHER direction from the usual defect — not a promise
            # of a feature that does not exist, but an off-switch for the only
            # channel that works.
            #
            # This is NOT the same as "a utility cannot control their staff
            # notifications". Which EVENTS notify anybody is BR-NOT-017's
            # SET-12 matrix, per event and per channel, and that is where a
            # utility turns things off. A tenant-wide kill switch here would
            # silently disable every event's in-app delivery from a different
            # screen, which is exactly the two-doors problem BR-NOT-017 exists
            # to end.
            return True
        if channel == models.CHANNEL_PORTAL:
            # ⚠ ALWAYS ON AND WITH NO COLUMN, for the in-app reason directly
            # above and not for print's (`CR-084`, 2026-09-07). An activation
            # flag defers a SEND until the platform or the tenant is ready for
            # it; publishing a document to the customer's own portal has nothing
            # to be ready for — no vendor, no credentials, no connection, no
            # cost. A tenant-wide flag here would be an off-switch on a second
            # screen for something Settings → Notifications already switches per
            # event, which is the two-doors problem BR-NOT-017 exists to end.
            return True
        if channel == models.CHANNEL_EMAIL:
            return self.email_dispatch_active
        if channel == models.CHANNEL_SMS:
            return self.sms_dispatch_active
        return False


class DispatchConfigRefused(Exception):
    """This configuration cannot be saved, and here is why — in a clerk's words.

    Deliberately NOT a `core.errors` catalog exception for the VALUE refusals:
    those carry an HTTP status, and this service is called by jobs as well as by
    endpoints. The ROLE refusal is different and does use the catalog
    (`AuthError` AUTH-002 via `@require_role`), because "you may not do this" is
    the same answer in every context.
    """


def _tenant_id() -> Any:
    """Hard rule 1: no tenant table is touched without `app.tenant_id` set.

    Refuse loudly rather than run an unscoped query and leave RLS as the only
    thing between one tenant's send window and another's. Same guard, same
    error, as `apps/notifications/services.py`.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _row() -> models.NotificationSettings:
    """This tenant's settings row, created with the ratified defaults if absent.

    `get_or_create` rather than `.first() or a dict of defaults`: the defaults
    live on the model's columns and nowhere else, so a tenant that has never
    opened S8 and a tenant that opened it and saved nothing are the same row and
    the same behaviour.
    """
    row, _ = models.NotificationSettings.objects.get_or_create(tenant_id=_tenant_id())
    return row


def dispatch_settings() -> DispatchSettings:
    """This tenant's dispatch configuration. Called at the top of every cycle."""
    row = _row()
    return DispatchSettings(
        dispatch_batch_size=int(row.dispatch_batch_size),
        quiet_hours_start=row.quiet_hours_start,
        quiet_hours_end=row.quiet_hours_end,
        email_dispatch_active=bool(row.email_dispatch_active),
        sms_dispatch_active=bool(row.sms_dispatch_active),
        receipt_on_record_payment=bool(row.receipt_on_record_payment),
        credit_notice_email=bool(row.credit_notice_email),
        bookkeeper_copies=bool(row.bookkeeper_copies),
        lockbox_receipts=bool(row.lockbox_receipts),
    )


def receipt_on_record_payment_election() -> bool:
    """THE published read for BR-PAY-024's staff election (C-13's one wired
    consumer). `apps/payments/receipts.py` resolves this BY NAME at record time
    — payments never touches this module's ORM (B1 / BR-TEN-013).

    Reads the row fresh on every call, like the dispatcher does: a clerk who
    switches receipts off must not have the next counter payment obey a cached
    yesterday. Tenant scoping is `_row()`'s (hard rule 1).
    """
    return bool(_row().receipt_on_record_payment)


def _validated(field: str, value: Any) -> Any:
    """One submitted value → its stored form, or the refusal explaining why not."""
    if field == "dispatch_batch_size":
        if isinstance(value, bool) or not isinstance(value, int):
            raise DispatchConfigRefused(
                f"the dispatch batch size must be a whole number of messages, not "
                f"{value!r}. It is the size of each hand-off to a provider (BR-BIL-016), "
                "so a value nobody can count is a hand-off nobody can size."
            )
        if value <= 0:
            raise DispatchConfigRefused(
                f"a dispatch batch size of {value} would hand the provider nothing on "
                "every cycle (US-NOT-004 TC-6). The queue would fill, no message would "
                "leave, and every screen would show a provider outage that is not "
                "happening. The seeded default is "
                f"{models.SEEDED_BATCH_SIZE} (BR-BIL-016)."
            )
        return value
    if field in ("quiet_hours_start", "quiet_hours_end"):
        if not isinstance(value, time):
            raise DispatchConfigRefused(
                f"{field} must be a time of day, not {value!r}. BR-NOT-009's send window "
                "is wall-clock TENANT time — 08:00–21:00 by default — and a value that is "
                "not a time cannot be compared against a tenant's clock."
            )
        return value
    if field in ("email_dispatch_active", "sms_dispatch_active"):
        if not isinstance(value, bool):
            raise DispatchConfigRefused(
                f"{field} is on or off, not {value!r}. It governs whether this platform "
                "makes provider calls on that channel at all (US-NOT-003), so a value "
                "that is neither is refused rather than coerced."
            )
        return value
    if field in ELECTION_FIELDS:
        if not isinstance(value, bool):
            raise DispatchConfigRefused(
                f"{field} is on or off, not {value!r}. It is one of A15's four send-time "
                "elections (BR-NOT-022) — a default for whether the send happens, and a "
                "value that is neither on nor off is refused rather than coerced."
            )
        return value
    raise DispatchConfigRefused(  # pragma: no cover - unreachable via update_dispatch_settings
        f"{field!r} is not a dispatch setting. The editable set is "
        f"{', '.join(EDITABLE_FIELDS)}."
    )


def _audit_value(value: Any) -> Any:
    """A settings value in a form the audit payload can carry losslessly."""
    return value.isoformat() if isinstance(value, time) else value


@require_role(SYSTEM_ADMIN, br_ref="BR-TEN-041")
def update_dispatch_settings(*, actor: Any, **changes: Any) -> DispatchSettings:
    """Save an S8 Notifications edit. Admin-gated, validated, audited, atomic.

    Pass only the fields being changed. A field submitted with the value it
    already holds is not a change and does not appear in the audit payload —
    T7-16 and T7-17 each assert ONE audit row carrying the before→after of what
    actually moved, and a payload padded with unchanged fields makes the next
    reader hunt for the edit.

    Returns the configuration as it now stands, so a caller never has to
    re-read to find out what it saved.

    Raises `DispatchConfigRefused` for a value the tenant can fix, and
    `AuthError` AUTH-002 for a caller who may not make the edit at all
    (US-NOT-004 TC-5: a Billing Clerk's batch-size edit is server-rejected, not
    merely hidden).
    """
    unknown = sorted(set(changes) - set(EDITABLE_FIELDS))
    if unknown:
        raise DispatchConfigRefused(
            f"{', '.join(unknown)} is not a dispatch setting. The editable set is "
            f"{', '.join(EDITABLE_FIELDS)} (US-NOT-004 §5 + BR-NOT-022's four "
            "elections). Provider status is read from integrations and is not stored "
            "here."
        )
    if not changes:
        raise DispatchConfigRefused(
            "no dispatch setting was named, so there is nothing to save. An empty save "
            "would write an audit row saying a System Admin changed the send window and "
            "leave no way to see that they did not."
        )

    with transaction.atomic():
        row = _row()
        before: dict[str, Any] = {}
        after: dict[str, Any] = {}
        for field, raw in changes.items():
            value = _validated(field, raw)
            current = getattr(row, field)
            if current == value:
                continue
            before[field] = _audit_value(current)
            after[field] = _audit_value(value)
            setattr(row, field, value)

        # The window is validated as a PAIR, after both ends are applied: an
        # edit that moves the start past the old end is only legal alongside the
        # matching move of the end, and checking each value alone would refuse a
        # lawful 09:00–20:00 save that arrives as two fields.
        if row.quiet_hours_start >= row.quiet_hours_end:
            raise DispatchConfigRefused(
                f"a send window of {row.quiet_hours_start:%H:%M}–{row.quiet_hours_end:%H:%M} "
                "ends before it starts. This is refused rather than read as 'wraps "
                "midnight': BR-NOT-009 exists to stop a utility texting late-payment "
                "reminders at 23:00, and one transposed pair of times would switch that "
                "protection into its opposite for every customer at once. Whether a "
                "window may legitimately cross midnight is not ruled anywhere — refusing "
                "to store one decides nothing and is reversible."
            )

        if not before:
            # Every submitted field already held its submitted value. Nothing is
            # written and nothing is audited: the trail records changes, and a
            # row saying "before == after" is noise a reviewer has to read.
            return dispatch_settings()

        row.save(update_fields=[*before.keys(), "updated_at"])
        # Hard rule 7, in the SAME transaction — a changed send window cannot
        # stand without its trail row (core.audit fails loudly).
        audit.money_action(
            actor, AUDIT_ACTION, AUDIT_ENTITY, str(row.pk), before=before, after=after
        )

    return dispatch_settings()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-004@3c1f8ab (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/10-notifications/06-epics/EP-NOT-01-outbound-queue.md — US-NOT-004 §1/§3/§5 — · 10-notifications/02-business-rules.md — BR-NOT-005/009/010 — · 10-notifications/03-field-map.md §1 · 08-qa/01-e2e/journeys/T7-16-quiet-hours-window-change.md + T7-17-dispatch-batch-size-change.md)
# generated: 2026-08-15 by story-coder (W3 notifications delivery-core lane — the dispatch-config slice)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the S8 Notifications endpoints are not in this lane; the service is role-gated so an unbuilt endpoint cannot become an ungated one) E=deferred(no-frontend-half — the S8 tab lives under 07-frontend/src/features/tenancy/, which this lane was instructed not to touch; REPORTED so the gap is owned rather than assumed) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_not_004_dispatch_config.py · the
#         role gate, the batch-size floor and the window refusal were each
#         proved RED by removal before being trusted green (hard-won law 7) —
#         verbatim transcripts in the lane report
# exceptions: (1) [AMENDED 2026-08-18] THE FOUR A15 "(opt)" TOGGLES ARE BUILT,
#         DEFAULT ON — OQ-205 CLOSED by the PO (C-13: "keep them default to
#         start with Utility will amake them off"; the ruling REVERSED the
#         off-by-default recommendation and that was the PO's call). One
#         consumer is wired (receipt_on_record_payment → apps/payments/
#         receipts.py through the published read here); the other three are
#         stored and editable with unbuilt consumers REPORTED on the wire —
#         hard-won law 2 is satisfied by the wired reader plus the honest note,
#         never by a silent column.
#         (2) NO PROVIDER-STATUS READOUT here — US-NOT-004 §5 marks it
#         `computed-display` over integrations connections; it lives in
#         `apps/notifications/provider_seam.py`, which reports "cannot answer"
#         because `apps/integrations` holds three docstrings and no models.
#         (3) A WINDOW THAT WRAPS MIDNIGHT CANNOT BE STORED. Refused in the
#         service and by `ck_notification_settings_quiet_window`. Not a ruling —
#         a refusal to invent one; REPORTED.
#         (4) THE DISPATCH-HOME DASHBOARD (counts, failures list, re-queue) is
#         US-NOT-013 and is NOT here. This file is the config half of S8 tab 7
#         only; the story itself splits them the same way.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

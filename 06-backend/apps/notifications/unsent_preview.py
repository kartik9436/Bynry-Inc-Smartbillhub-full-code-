# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CWP-nnnn (2026-09-05) — ⚠ `nnnn` IS A PLACEHOLDER, NOT A TYPO:
#           this lane may not write to the defect register, so the row is handed
#           over in `scratchpad/lane-NOTIF-defects.md` and its id is allocated at
#           merge (`10-scripts/allocate.py defect`). Fill it in here in the same
#           diff that files the row. — a customer reaching portal enrolment
#           step 2 waits for a six-digit code that is minted, written to the
#           outbound queue, and readable by nobody. Nothing sends it (no SMS or
#           email adapter) and the back-office queue lists Type, Sent by,
#           Status, Recipient, Tries and What went wrong — and no body. A beta
#           tenant with no provider cannot complete a single enrolment.
# Ruling:   12-governance/02-decision-log.md 2026-09-05, "A way back, and how
#           the one-time code becomes testable in beta" §2. PO: *"Atleast show
#           me 6 digit code on this screen - so that I can copy and paste it
#           during enrolement"*, then *"you decide how to handle text message
#           part"* — the disclosure design was delegated and is recorded there.
# Rules:    BR-NOT-005 (a row with no provider rests `queued`; the queue is the
#           only send path) · BR-BIL-026 / BR-NOT-025 (a row renders from the
#           version PINNED on it, never from "the latest") · BR-AUD-003 (the
#           standard audit row) · BR-AUD-006 (PII enters an audit row masked) ·
#           B14 rule 32 (no rule id or internal code in clerk-facing copy) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 7 read as: a credential
#           disclosure is audited exactly as a money action is · hard-won law 3
#           (the unsafe option must be the one you type)
# Tests:    06-backend/tests/test_notif_unsent_preview.py
# Impacts:  apps/notifications/api.py (`GET /outbound` serves the open channels
#           in its vocabulary, so the screen needs no per-row probe) ·
#           07-frontend/src/features/notifications/UnsentMessagePanel.tsx
# ───────────────────────────────────────────────────────
"""What is waiting to go out — shown ONLY while nothing could have sent it.

╔══════════════════════════════════════════════════════════════════════════╗
║  THE GATE IS *THIS TENANT HAS NO PROVIDER CONNECTED FOR THIS CHANNEL*,   ║
║  AND IT IS DELIBERATELY NOT AN ENVIRONMENT FLAG. DO NOT "SIMPLIFY" IT.   ║
╚══════════════════════════════════════════════════════════════════════════╝

A flag — `SHOW_MESSAGE_BODIES=1`, a `DEBUG` branch, a per-tenant tick-box — is a
thing somebody has to remember to turn OFF, and hard-won law 3 says the unsafe
option must be the one you type. **This gate is self-disarming:** the condition
that makes a body safe to show — *nothing could have delivered it, so nobody
else can be holding it* — is exactly the condition that makes showing it
necessary. It cannot be left on by accident in production, because connecting a
provider is the first thing a live utility does, and connecting one closes this
door with no edit, no deploy and nobody remembering.

The corollary is the part a later lane will be tempted to remove: **there is no
override.** No query parameter, no header, no role, no setting re-opens the body
once a provider is connected. If that ever needs to change it is a ruling, not a
refactor.

⚠ **AND THE CODE IS NOT SKIPPED INSTEAD, WHICH WAS THE QUICKER OPTION AND WAS
REFUSED.** The account number, the postcode and the surname are all printed on
the paper bill; the code is the only thing that is not. Dropping it for a tenant
with no provider would turn self-serve enrolment into *anyone holding a bill
gets the login*.

WHY IT FAILS CLOSED IN BOTH DIRECTIONS
--------------------------------------
`provider_seam.provider_status(channel)` answers `None` when integrations cannot
answer at all, and that module already refuses to render `None` as *not
connected*. This one takes the same position and takes it the SAFE way:

    connected      → do not disclose (somebody else may hold the message)
    cannot tell    → do not disclose (we do not know that they do not)
    not connected  → disclose

`in_app` lands in the middle branch by construction — it has no integrations
category because its provider is this platform (`BR-NOT-019`) — and that is the
right answer twice over: an in-app message is delivered, so its recipient can
already read it.

For `email` a configured tenant SMTP sender ALSO closes the gate, with or
without an integrations connection. The ruling names both doors — *"connect
Twilio or an SMTP sender and the body stops showing"* — and
`sender_config.smtp_configured` is where an SMTP sender is recorded here.

WHAT IS SHOWN, AND WHY IT IS SOMETIMES FACTS RATHER THAN A BODY
----------------------------------------------------------------
A row that carries a PINNED template version renders exactly as the dispatcher
would have rendered it, from that pinned version — never from "the latest"
(`BR-BIL-026`).

The portal's rows carry no pin, and that is not a bug to route around: no
`portal_enrolment_code` template has been written, so `services._pinned` stamps
the unresolved marker and `rendering.render_for_dispatch` refuses. **Rendering
something anyway would be this platform inventing a document**, which is the one
thing that module exists to refuse. So the honest answer is the FACTS the writer
stamped on the row — `outbound_messages.render_context` — which for an enrolment
code is the code itself, its lifetime and what it is for.

That is not a fallback invented here. `apps/portal/models.py` already says it in
as many words, of `portal_one_time_code.outbound_message_id`: *"The demo reads
the code from that row's render context while W6 is not activated."* This module
is that read, with a gate and an audit row around it.

⚠ THE AUDIT ROW RECORDS THAT A DISCLOSURE HAPPENED AND NEVER WHAT WAS DISCLOSED
--------------------------------------------------------------------------------
Hard rule 7 names money actions; a credential is the same principle and this is
the reading that earns it — a one-time code is the whole of the portal's defence
at the door (`BR-CWP-103`), so who read one and when is a fact the utility must
be able to recover.

**The code itself never enters `audit_log`.** Putting it there would create a
second, longer-lived copy of a secret whose entire design is that it lives for
ten minutes in one row, and `audit_log` outlives the code by years. The row
carries the message, the channel, the kind and the masked recipient — enough to
say *who read the code that went to •••4218 at 14:07* and nothing more.

⚠ A DISCLOSURE IS AN ACT, WHICH IS WHY IT IS A ROUTE AND NOT A COLUMN
----------------------------------------------------------------------
If the body rode on `GET /outbound` it would be disclosed fifty rows at a time,
to anyone who opened the page, and the audit row would either be written fifty
times or mean nothing. One click, one row, one audit entry.
"""

from __future__ import annotations

from typing import Any

from apps.notifications import models, provider_seam, rendering, tenancy_seam
from core import audit

#: Hard rule 7 · the dotted `entity.action` grammar `core.audit` documents.
AUDIT_ACTION = "outbound_message.body_disclosed"
AUDIT_ENTITY = "outbound_message"

#: WHY the body is or is not shown. CODES, never prose — a screen groups on
#: these and picks its own sentence out of its own catalogue (`DEF-335`: the
#: provenance stays on the wire, the sentence is the catalogue's).
OPEN_NO_PROVIDER = "no_provider_connected"
CLOSED_PROVIDER_CONNECTED = "provider_connected"
CLOSED_PROVIDER_UNKNOWN = "provider_status_unknown"

#: What a row had to say for itself when there is no rendered body.
BODY_RENDERED = "rendered_from_the_pinned_wording"
BODY_FACTS_ONLY = "no_wording_published_so_the_facts_are_shown"
BODY_NOTHING = "nothing_was_stored_to_show"

#: The i18n keys this file's answers carry, named once so `G18` can read the
#: catalogue and the code against each other in one grep. A key with no
#: catalogue entry renders to a clerk as a raw dotted string — which is the
#: other defect this lane is fixing, so it is not repeated here.
KEY_BY_REASON: dict[str, str] = {
    OPEN_NO_PROVIDER: "notifications.unsent.noProvider",
    CLOSED_PROVIDER_CONNECTED: "notifications.unsent.providerConnected",
    CLOSED_PROVIDER_UNKNOWN: "notifications.unsent.providerUnknown",
}
#: ⚠ **`BODY_RENDERED` HAS NO KEY, AND THAT IS THE RULE RATHER THAN AN
#: OMISSION.** B14 rule 32 gives a section ONE sentence, and when the letter is
#: on the screen there is nothing left to explain — a caption over a visible
#: message is the description budget spent on nothing. A key nobody renders is
#: also a dead key in eleven catalogues (G18 direction A), so not minting one
#: is the same decision twice.
KEY_BY_BODY_STATE: dict[str, str | None] = {
    BODY_RENDERED: None,
    BODY_FACTS_ONLY: "notifications.unsent.bodyFactsOnly",
    BODY_NOTHING: "notifications.unsent.bodyNothing",
}


def _email_sender_is_set() -> bool:
    """Has this tenant recorded a mail server of its own?

    Imported at CALL time and never allowed to raise: a sender card that cannot
    be read must not decide a disclosure by accident. A failure answers **True**
    — *treat it as connected* — because the safe direction here is to show
    LESS, and every other branch in this module leans the same way.
    """
    try:
        from apps.notifications import sender_config

        # The CONNECTOR's answer since 2026-10-22 (`DEF-NOT-10534`): a mail
        # server lives on Connectors only, so "has one of its own" is whether
        # a Custom SMTP connection exists there, whatever its state.
        status = sender_config.sender_status()
        if status is None:
            return True  # nobody could answer — fail closed, as above
        return bool(status.get("connected"))
    except Exception:  # noqa: BLE001 — a broken read fails CLOSED, never open
        return True


def channel_disclosure(channel: str) -> tuple[bool, str]:
    """`(may the body be shown, why)` for ONE channel, for THIS tenant.

    The whole gate lives here and nowhere else, so a second caller cannot
    acquire a second opinion about the same question.
    """
    if channel == models.CHANNEL_EMAIL and _email_sender_is_set():
        return False, CLOSED_PROVIDER_CONNECTED
    try:
        status = provider_seam.provider_status(channel)
    except Exception:  # noqa: BLE001 — see below; a raise is `cannot tell`
        # ⚠ **THIS IS ALSO WHY THE QUEUE STILL DRAWS WHEN INTEGRATIONS IS
        # BROKEN.** `disclosable_channels()` runs on every `GET /outbound`, and
        # `provider_seam.provider_status` does not catch — so an exception from
        # integrations would take out the whole *Messages needing attention*
        # list, which is the screen a clerk opens BECAUSE something is wrong.
        # A raise is treated as `cannot tell`, like every other unknown here.
        status = None
    if not isinstance(status, dict):
        # `None` is NOT "not connected" — it is "nobody could answer", and the
        # two must never render the same (`provider_seam` states the rule).
        return False, CLOSED_PROVIDER_UNKNOWN
    if status.get("connected"):
        return False, CLOSED_PROVIDER_CONNECTED
    return True, OPEN_NO_PROVIDER


def disclosable_channels() -> tuple[str, ...]:
    """The channels whose bodies may be read right now, for the queue list.

    Served WITH the list so the screen can offer the control on exactly the
    rows it will work for, without a probe per row. Four channels, four reads,
    once per page — not once per row.
    """
    return tuple(one for one in models.CHANNELS if channel_disclosure(one)[0])


def _facts(row: models.OutboundMessage) -> list[dict[str, str]]:
    """The facts the WRITER stamped on this row, in a person's words.

    `rendering.token_label` turns `expires_in_minutes` into *Expires in
    minutes*. It is derived from the name rather than looked up in a label
    table, and that is this repo's own ruling on the question: *"a hand-kept
    label map is a list that goes stale the first time a palette gains a token,
    and a missing entry there would print a raw identifier"*.

    ⚠ **THE VALUE IS FORMATTED THE WAY THE LETTER FORMATS IT — `DEF-NOT-4413`,
    2026-09-07.** This was `str(value)`, and `str(value)` was RIGHT for every
    value this panel had ever been pointed at: a portal enrolment code, its
    lifetime and its purpose are all strings. `DEF-PAY-4409` put a payment
    receipt's figures on the same column, and the panel then printed **`Balance
    0.000000`** and **`Date 2026-09-07 00:00:00-05:00`** two inches under a
    letter reading *your balance is now 0.00 USD* — six decimals where CLAUDE.md
    hard rule 2 says money DISPLAYS at two, and a raw timestamp where BR-TEN-017
    says a date wears the tenant's Regional format.

    `rendering._rendered_value` is the ONE path that already does both, and it
    is called rather than copied: a second money formatter is how the letter and
    the panel beside it start disagreeing about the same figure. A value it
    cannot render — a float, which rule 2 forbids — falls back to `str` here
    rather than taking the panel down, because this screen's job is to SHOW a
    clerk what is stored, including something that should not be.
    """
    stored = rendering.decode_context(row.render_context)
    formats, _problems = tenancy_seam.regional_formats()
    facts: list[dict[str, str]] = []
    for name, value in sorted(stored.items()):
        if value is None or str(value) == "":
            continue
        try:
            text, _problem = rendering._rendered_value(
                str(name),
                value,
                currency=formats.get("currency"),
                date_format=formats.get("date_format"),
                # CR-190-BRC10 — the same $45.00 the email will print.
                locale=rendering.money_locale(
                    row.template_language or formats.get("language"), formats.get("country")
                ),
                number_format=formats.get("number_format"),
            )
        except rendering.RenderRefused:  # a float on the column rule 2 forbids
            text = str(value)
        facts.append({"label": rendering.token_label(str(name)), "value": text})
    return facts


def _rendered(row: models.OutboundMessage) -> tuple[str | None, str | None]:
    """The subject and body from the row's PINNED version, or `(None, None)`.

    A refusal is an answer, not an error: an unpinned row is exactly the portal
    enrolment row, and the facts branch is what it gets. Nothing here reaches
    for "the latest published version" — that is the substitution `BR-BIL-026`
    forbids and `render_for_dispatch` already refuses.
    """
    try:
        artifact = rendering.render_for_dispatch(row)
    except rendering.RenderRefused:
        return None, None
    except Exception:  # noqa: BLE001 — a render fault must not break the panel
        return None, None
    return artifact.subject, artifact.body


def _mask(address: str | None) -> str | None:
    """The recipient, enough to recognise and not enough to reuse (BR-AUD-006).

    `+15125550142` → `•••0142`; `sam@example.com` → `s•••@example.com`. Nothing
    here is a security boundary — the full address is already on the row a clerk
    is looking at — it keeps the AUDIT ROW to what an audit row needs.
    """
    if not address:
        return None
    if "@" in address:
        name, _, domain = address.partition("@")
        return f"{name[:1]}•••@{domain}"
    return f"•••{address[-4:]}" if len(address) > 4 else "•••"


def preview(row: models.OutboundMessage, *, actor: Any) -> dict[str, Any]:
    """Disclose ONE queued message's content, or say why it is not shown.

    ALWAYS answers — a closed gate is a 200 with `disclosable: false` and no
    content, not a refusal — because *a provider is connected* is a normal,
    correct state that the screen has to be able to explain, not an error.

    Writes `audit_log` on the disclosing branch only. There is nothing to record
    about a request that was shown nothing.
    """
    may_show, reason = channel_disclosure(row.channel)
    answer: dict[str, Any] = {
        "message_id": str(row.pk),
        "channel": row.channel,
        "source_type": row.source_type,
        "status": row.status,
        "disclosable": may_show,
        "reason": reason,
        "message_key": KEY_BY_REASON[reason],
        "subject": None,
        "body": None,
        "facts": [],
        "body_state": None,
        "body_state_key": None,
    }
    if not may_show:
        return answer

    subject, body = _rendered(row)
    facts = _facts(row)
    if body:
        state = BODY_RENDERED
    elif facts:
        state = BODY_FACTS_ONLY
    else:
        state = BODY_NOTHING
    answer["subject"] = subject
    answer["body"] = body
    answer["facts"] = facts
    answer["body_state"] = state
    answer["body_state_key"] = KEY_BY_BODY_STATE[state]

    # Hard rule 7's reading for a credential. The CONTENT is deliberately absent
    # from this row — see the module docstring — and every value below is a
    # machine fact or a masked address, so nothing here is prose a clerk reads
    # (B14 rule 32, G71).
    audit.write_row(
        action=AUDIT_ACTION,
        entity_type=AUDIT_ENTITY,
        entity_id=str(row.pk),
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        after={
            "channel": row.channel,
            "source_type": row.source_type,
            "status": row.status,
            "recipient": _mask(row.recipient_address),
            "shown": state,
        },
    )
    return answer


# ── Lifecycle ─────────────────────────────────────────────
# packet: decision log 2026-09-05 §2 (the ruling) · apps/notifications/provider_seam.py (the three channel states) · apps/integrations/seams/notifications.py (provider_connection_status) · apps/portal/credentials.py queue_code + models.PortalOneTimeCode (what is stamped on the row)
# generated: 2026-09-05 by the NOTIF lane
# checklist: A✔ B✔ C✔ D✔(unsent_api.py) E✔(UnsentMessagePanel.tsx) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/test_notif_unsent_preview.py · both directions of the gate proved by test, with the connected direction proved by CONNECTING a provider rather than by patching this module
# exceptions: (1) NO OVERRIDE EXISTS, deliberately — see the docstring. (2) The audit row never carries the code.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

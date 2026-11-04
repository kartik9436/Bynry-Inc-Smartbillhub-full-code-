# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-004 (Settings → Notifications — CR-009 C-12: the tenant
#           SENDER CONFIG, stored and on screen, ahead of any live send)
#           Screens: S8 (Settings → Notifications, the "Email sender" card)
# Rules:    BR-NOT-023 (SMTP-first: the tenant's own SMTP is the default
#           sender source, platform ESP the fallback WHEN IT LANDS — PO
#           2026-08-17, C-12) · BR-NOT-013 (no live sending is switched on by
#           any of this; dispatch posture unchanged) · BR-NOT-005 (queue only)
#           · BR-TEN-016 (a settings edit is audited before→after) ·
#           BR-IDN-009 (server-enforced role gating) · CLAUDE.md rule 1
#           (tenant scoping) · rule 7 (audited) · 🔒 webhook-keys class:
#           credentials handling
# Tests:    06-backend/tests/test_settings_move_smtp_in_connectors.py (test_cr_009_c12_sender_config.py retired 2026-10-22 with the form it tested)
# Impacts:  apps/notifications/settings_api.py (GET|PATCH /notification-sender)
#           · apps/notifications/provider_seam.py (channel_route's email
#           problem now names the sender source) ·
#           07-frontend/src/features/notifications/SettingsNotificationsTab.tsx
# ───────────────────────────────────────────────────────
"""The tenant's EMAIL SENDER configuration — the plug, stored before the socket.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file handles CREDENTIAL MATERIAL
(the CLAUDE.md 🔒 "webhook keys" class: how a secret is stored and who may
change it). AI-authored 2026-08-18 under the PO ruling of 2026-08-09 ("AI will
do it; we will review it later as human"); row in
12-governance/09-human-review-ledger.md; glob added to
10-scripts/gates/human_owned.txt in the same commit.

╔══════════════════════════════════════════════════════════════════════════╗
║  PO 2026-08-17, C-12 verbatim: "12 - A ✅ both: tenant's own SMTP          ║
║  (Office365/Gmail) as default" — and the standing ruling it plugs into:   ║
║  "the moment we take the decison on ESP or SMTP from existing email of    ║
║  Utilities, we just need to plug it ; rest of the infra will work".       ║
╚══════════════════════════════════════════════════════════════════════════╝

**WHAT THIS IS:** the per-tenant STORAGE and SCREEN for the SMTP half of that
decision — host, port, username, a SECRET REFERENCE and the "from" address —
plus the one resolution rule (`sender_route`): **the tenant's own SMTP when it
is configured, else the platform ESP when that lands.** It is the socket the
PO described; the adapter that will read it is still not built, deliberately.

**WHAT THIS IS NOT — NO LIVE SENDING IS SWITCHED ON BY ANY OF IT.**
`email_dispatch_active` is untouched, `provider_seam.adapter("email")` still
resolves to nothing, BR-NOT-013 stands, and a tenant that fills this card in
completely has changed WHAT WOULD BE USED, never WHETHER anything sends. The
card and the wire both say so.

────────────────────────────────────────────────────────────────────────────
⚠ RETIRED 2026-09-04 — THE MAIL PASSWORD IS TYPED INTO THE PRODUCT NOW.
────────────────────────────────────────────────────────────────────────────
This section used to describe `smtp_secret_ref`: a column holding the NAME of
a secret in the deployment's own store (`SMTP_PASSWORD_BRAZOSBEND`, a vault
path) rather than the password, *"because this repo has NO crypto kernel"*.

**It has had one since 24 August** (`core/crypto.py`), so `CR-069`'s `C35` and
`US-INT-026` fold this card into the connection model instead of building
beside it. From `integrations/0004_c35_fold_sender_secret_ref`:

  * the password lives in `integration_credential.payload_enc`, encrypted,
    versioned, and destroyed the moment the connection is disconnected;
  * `smtp_secret_ref` IS NULL ON EVERY ROW and **is read by nothing** — that
    migration is the last thing that ever read it, and this comment is the
    `# retired` marker `US-INT-026` TC-4 greps for;
  * connecting email is a form and a test on Settings → Integrations, **not a
    deployment**. Nobody puts a variable on a host any more.

**What did NOT change, and it is the reason the four columns below are still
here:** the migration COPIED host, port, username and from-address into the
connection's config rather than moving them, so this card keeps rendering
while `US-INT-004`'s read-model takes over. Dropping a column in the same
commit that stops reading it leaves no way back if the copy was wrong.

NO SPF/DKIM VERIFICATION EITHER. The CR asks for a *verified* from-address;
verification needs DNS lookups and a provider probe that do not exist here,
so `from_address_verified` is served as `false` with the reason, never
implied (hard-won law 1).

────────────────────────────────────────────────────────────────────────────
⚠ RETIRED 2026-10-22 — THE MAIL SERVER LIVES IN CONNECTORS AND NOWHERE ELSE.
────────────────────────────────────────────────────────────────────────────
PO, verbatim (decision log 2026-10-22, *Corrected bills* Q4): *"We have to move
everything in connector not any other place"* — superseding the 2026-08-30
*"Email sender (SMTP) - create seperate tab under notification"* for the SMTP
tab (`DEF-NOT-10534`). The host, port, user and sender were typed in TWO places
and only one of them was ever read: `integrations/adapters/email_smtp.py` reads
the Connectors connection, and this file's columns fed a status sentence.

So, from this commit:
  * **nothing here writes.** `update_sender_config` is gone; the settings API
    refuses every one of `RETIRED_FIELDS` BY NAME (`settings_api.py`);
  * **`sender_route()` reads the connector** through integrations' published
    `email_sender_status` (BR-TEN-013: the owner's callable, never its ORM);
  * the five `notification_settings` columns are **read by nothing**.
    `integrations/0016` copied any value only they held into the connector,
    once, audited; `models.py` lists them for removal.
"""

from __future__ import annotations

from typing import Any

#: The five `notification_settings` columns that used to hold a mail server.
#: Read by nothing since 2026-10-22; a write naming any of them is refused by
#: name (`settings_api.py`), and `integrations/0016` moved what they held.
RETIRED_FIELDS: tuple[str, ...] = (
    "smtp_host",
    "smtp_port",
    "smtp_username",
    "smtp_secret_ref",
    "sender_from_address",
)

#: Nothing about the mail server is editable here any more — it is Connectors'.
EDITABLE_FIELDS: tuple[str, ...] = ()

#: The catalogue key of the refusal a clerk reads: *"Set this on Connectors."*
REFUSAL_KEY = "notifications.sender.movedToConnectors"

#: The two answers `sender_route` gives, as codes a screen can group on.
MODE_TENANT_SMTP = "tenant_smtp"
MODE_NOT_CONNECTED = "not_connected"

#: The integrations callable this file reads (`apps.integrations.services`).
STATUS_READ = "email_sender_status"


def sender_status() -> dict[str, Any] | None:
    """The connector's own answer, or None when integrations cannot answer.

    Resolved at CALL time through `provider_seam._resolve`, the idiom every
    read across this boundary uses. None is not *not connected* — it is
    *nobody could answer*, and the two must never render the same.
    """
    from apps.notifications import provider_seam

    read = provider_seam._resolve(provider_seam.PROVIDER_MODULE, STATUS_READ)
    if read is None:
        return None
    answer = read()
    return dict(answer) if answer is not None else None


def sender_route() -> dict[str, Any]:
    """WHICH mail server email goes through, read from the CONNECTOR.

    ⚠ IT READS NO `notification_settings` COLUMN, AND A TEST SAYS SO.
    `tests/test_settings_move_smtp_in_connectors.py` asserts this file names
    no retired column outside `RETIRED_FIELDS` and that the route follows a
    change made on Connectors.

    The sentence is a water clerk's (DEF-2472: no rule id, no instruction
    pointing at the page it is on); provenance is the machine field.
    """
    status = sender_status() or {}
    connected = bool(status.get("connected"))
    host = status.get("host")
    sender = status.get("send_from")
    provider = status.get("provider_name")
    route: dict[str, Any] = {
        "mode": MODE_TENANT_SMTP if connected else MODE_NOT_CONNECTED,
        "configured": connected,
        "active": bool(status.get("active")),
        "provider_key": status.get("provider_key"),
        "provider_name": provider,
        "host": host,
        "send_from": sender,
        "status": status.get("status"),
        # Provenance for support and review, off the sentence (DEF-335).
        "route_br_ref": "BR-NOT-023 · BR-INT-005 · decision log 2026-10-22",
    }
    if connected:
        where = f"{provider} ({host})" if host else str(provider)
        route["detail"] = f"Email goes through {where}" + (
            f", sending as '{sender}'." if sender else "."
        )
    else:
        route["detail"] = "No mail server is connected."
    return route


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-004@cr009c12 (12-governance/02-decision-log.md → 2026-08-17 C-12 verbatim + CR-009 conflict-1 ruling ("the moment we take the decison … we just need to plug it") · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-023 · apps/notifications/provider_seam.py (the seam the future adapter plugs into) · apps/tenancy/services.py `ein` (the stored-credential precedent this file deliberately does NOT extend))
# generated: 2026-08-18 by story-coder (CR-009 C-section lane)
# checklist: A✔ B✔ C✔ D✔(GET|PATCH /notification-sender in settings_api.py) E✔(the S8 "Email sender" card) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: tests/test_cr_009_c12_sender_config.py — the role gate proved RED as an Executive; the secret-reference heuristic by submitting "hunter2 with spaces"; the no-live-send posture by asserting channel_route("email").dispatchable stays False with a fully configured sender
# exceptions: (1) THE SECRET IS A REFERENCE, NEVER THE VALUE — no crypto kernel exists and the ein "plain for now" posture is deliberately not extended to a live credential; the operator places the secret in the host's store under the stored name. HUMAN-REVIEW-PENDING states this is the judgment to review. (2) NO SPF/DKIM VERIFICATION — served as `from_address_verified: false` with the reason, never implied. (3) NO ADAPTER AND NO SEND: this is C-12's PLUG; BR-NOT-013 and email_dispatch_active are untouched.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

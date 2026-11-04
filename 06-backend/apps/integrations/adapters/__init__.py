"""The key → adapter-class registry, bound to the manifest registry at ready().

Adding a REAL adapter is adding ONE file here and ONE line to `ADAPTERS`
below (US-INT-015). The manifest registry refuses to bind an adapter to a
coming-soon provider (BR-INT-001), and the conformance kit
(`apps/integrations/conformance.py`) runs every class listed here, unchanged.

⚠ THIRTEEN ADAPTERS ARE LISTED. `CR-198-BRC10` (2026-10-29) added Twilio,
the first whose credential is the platform's own. GIS Lane D (2026-10-07) added the Census
geocoder, whose card could not be connected without one (`DEF-INT-10006`).
`CR-173-BRC10` (2026-10-07) added New World /
Logos's outbound half — the first adapter that places a file over SFTP, with
the one real SFTP client (`apps/integrations/sftp.py`). `CR-115-BRC05`
(2026-09-17) added the two email
service providers — the first pair here that can put a utility's BILL in a
consumer's inbox over somebody else's network, and the first whose `202`/`200`
means ACCEPTED and never DELIVERED. Wave M (2026-09-06) added the city's address
service, the first that is called INLINE — a latency budget instead of a
queue, and a list that is OFFERED rather than loaded; wave K the same day
added the water meter cloud —
the first connector whose credential is EXCHANGED for a ten-minute token rather
than presented, and the first that walks a provider in windows and pages; wave J
the same day added the accounting export target (the first OUTBOUND file
adapter, and the first that dials nothing at all for its commonest
destination); wave H had added the two mailboxes a utility signs in to
(Microsoft 365 and Google Workspace), and wave I the bank folder just before.
⚠ THIS LINE SAID *ONE* UNTIL WAVE H'S COMMIT, WITH THREE IN THE DICTIONARY
BELOW, *FIVE* UNTIL WAVE J, *SIX* UNTIL WAVE K, *SEVEN* UNTIL WAVE M AND *EIGHT* UNTIL
`CR-115-BRC05`'s email lane — the same shape as B14's
rule count, which has been wrong five times: adding the adapter and updating
the sentence that counts them are two acts and only the first feels like the
work (law 1). **A test asserts the number now**, so the next time this goes
stale it goes red instead.
The paragraph below
is wave E's and is kept because its warning about a REAL customer credential
applies to a refresh token exactly as it applied to a mail password.

⚠ ONE ADAPTER WAS LISTED AT WAVE E, AND IT WAS THE WHOLE OF THAT LAUNCH. Until
2026-09-04 this dictionary was EMPTY and every LIVE card's connect was refused
with *Cannot be connected yet.* — the product could show a mail-server card and
could not store the password. `email_smtp` is now bound, so **Custom SMTP is
the one provider on this deployment a utility can actually connect**; every
other LIVE card still answers that refusal, from this same dictionary and not
from a branch.
⚠ **THAT LAST SENTENCE WAS TRUE ON 2026-09-04 AND IS NOT TRUE NOW** — nine more
adapters are bound and the newest two are the ESPs above. The paragraph is kept
for its CREDENTIAL warning, which is undiminished, and this line is here because
a present-tense claim left standing is exactly the shape law 1 is about.

⚠ WHAT THAT COMMIT ALSO DID, STATED PLAINLY BECAUSE IT IS THE POINT OF THE
GUARD LIST: from here a REAL customer credential is stored. `core/crypto.py`'s
four self-made judgments — where the key comes from, what happens when it is
absent, how rotation works, randomised-not-deterministic — are still awaiting
a human signature, and the ledger row now states the mail-password figure a
reviewer is owed. That is the standing protocol (PO 2026-08-09: *"AI will do
it; we will review it later as human"*), not an exception to it. The DELETION
path was written first and shipped in the same commit, which is the ordering
`US-INT-025` TC-6 exists to keep.

The kit's fixture adapters live in `conformance.py` and are bound only inside
a test (`services.connect` reads the registry, so a test binds a fixture,
exercises the path, and unbinds it).

This is the second of the two places `provider_key` may legitimately appear
as data in code (`10-scripts/gates/g77_provider_key_branches.py`).
"""

from __future__ import annotations

from apps.integrations import registry as _registry
from apps.integrations.adapters.accounting_file import AccountingFileAdapter
from apps.integrations.adapters.base import Adapter
from apps.integrations.adapters.bank_lockbox_file import BankLockboxFileAdapter
from apps.integrations.adapters.email_google import EmailGoogleAdapter
from apps.integrations.adapters.email_microsoft import EmailMicrosoftAdapter
from apps.integrations.adapters.email_postmark import EmailPostmarkAdapter
from apps.integrations.adapters.email_sendgrid import EmailSendgridAdapter
from apps.integrations.adapters.email_smtp import EmailSmtpAdapter
from apps.integrations.adapters.erp_newworld import ErpNewWorldAdapter
from apps.integrations.adapters.geocoder_census import CensusGeocoderAdapter
from apps.integrations.adapters.gis_city import GisCityAdapter
from apps.integrations.adapters.meters_neptune360 import MetersNeptune360Adapter
from apps.integrations.adapters.payments_sandbox import PaymentsSandboxAdapter
from apps.integrations.adapters.sms_twilio import SmsTwilioAdapter

#: `manifest key → adapter class`. ONE line per real connector, and adding a
#: connector is this line plus one file — `P1`, the requester's own test for
#: the whole change request (*"every time such integration comes we dont want
#: to change our integration framework"*).
ADAPTERS: dict[str, type[Adapter]] = {
    "email_smtp": EmailSmtpAdapter,
    #: CR-068 phase 5 — the SECOND adapter, and the first that is not a
    #: network client at all. PO ruling 2026-09-05: beta ships the whole
    #: payment journey behind a test provider while the real ones wait for the
    #: integration work. It binds here like any other, which is the point:
    #: Worldpay will be this line with a different word in it.
    "payments_sandbox": PaymentsSandboxAdapter,
    #: CR-069 wave I — the THIRD adapter, and the first inbound one. It opens a
    #: bank's folder and says what it is connected to; it reads no row out of a
    #: file, because `BR-INT-054` as amended puts what a row MEANS in Runbooks.
    #: ⚠ Binding it here is what makes *Bank & lockbox file* connectable at
    #: all — until this line the card was live, the manifest was registered,
    #: and every connect was refused *Cannot be connected yet.* from this same
    #: dictionary (hard-won law 2: built is not wired).
    "bank_lockbox_file": BankLockboxFileAdapter,
    #: CR-069 wave H (phase 3, US-INT-005) — the two BYO MAILBOXES, and
    #: the pair is what proves the framework claim above rather than
    #: merely asserting it: they are two files of about thirty lines,
    #: each declaring a send URL and a message shape, over one shared
    #: `OAuthMailboxAdapter`. Nothing in `services.py`, `api.py`,
    #: `runtime.py` or any screen changed to admit them.
    "email_microsoft": EmailMicrosoftAdapter,
    "email_google": EmailGoogleAdapter,
    #: CR-069 wave J — the SIXTH adapter, and the first OUTBOUND file one. It
    #: shapes a journal file and places it; it never decides what belongs in
    #: one, because `BR-INT-054` as amended puts that in Runbooks. ⚠ Binding it
    #: here is what makes *Accounting export file* connectable at all — until
    #: this line the card was live, the manifest was registered, and every
    #: connect was refused *Cannot be connected yet.* from this same dictionary
    #: (hard-won law 2: built is not wired).
    "accounting_file": AccountingFileAdapter,
    #: CR-069 wave K (phase 4, US-INT-028 · 031 · 035) — the water meter cloud,
    #: and the first connector whose credential is exchanged for a SHORT-LIVED
    #: token rather than presented. Nothing in `services.py`, `api.py` or any
    #: screen changed to admit it: the ten-minute lifetime, the seven-day
    #: window, the three page sizes, the poll schedule and the four unsafe
    #: defaults are all declarations on its manifest.
    "meters_neptune360": MetersNeptune360Adapter,
    #: CR-069 wave M (phase 4, US-INT-042) — the city's address service, and
    #: the first adapter called INLINE: no job row, a latency budget instead of
    #: a deadline-less queue, and a result that is OFFERED rather than loaded
    #: (`C15`, `C16`). ⚠ Binding it here is what makes *City GIS* connectable
    #: at all — until this line the card was live, the manifest was registered,
    #: and every connect was refused *Cannot be connected yet.* from this same
    #: dictionary (hard-won law 2: built is not wired).
    "gis_esri": GisCityAdapter,
    #: GIS Lane D (PO GIS review gap 13, 2026-10-07) — the TWELFTH adapter.
    #: The Census card was LIVE, declared a test action, and every Connect was
    #: refused *Cannot be connected yet.* from this dictionary — and
    #: `live_calls.provision` connects through the same door, so the row
    #: `DEF-INT-4251` asked for could never have been created (`DEF-INT-10006`).
    "geocoder_census": CensusGeocoderAdapter,
    #: `CR-115-BRC05` — the NINTH and TENTH adapters, and the first two that
    #: hand a utility's BILL to somebody else's network. They are two files of
    #: about two hundred lines over one shared `EspEmailAdapter`, which is the
    #: same claim wave H's mailbox pair made and the reason the second ESP was
    #: cheap: nothing in `services.py`, `api.py`, `runtime.py` or any screen
    #: changed to admit either of them.
    #:
    #: ⚠ **BINDING THEM IS WHAT MAKES THE TWO CARDS LIVE**, and that is the
    #: whole of `DEF-INT-4224`: `register_adapter` refuses a coming-soon
    #: provider, so the manifests' dispositions moved in this same commit or
    #: the product would not start. A card a utility can press with nothing
    #: behind it is the defect the blueprint files in its own right (p146).
    #:
    #: ⚠ **WHAT IS LIVE IS SENDING, AND NOT DELIVERY REPORTING.** Neither
    #: feedback door is open — SendGrid's signature is `DEF-INT-5630` and
    #: Postmark's Basic password cannot be minted (`DEF-INT-5634`) — so
    #: `delivered`, `bounced_hard`, `bounced_soft`, `complained` and
    #: `unsubscribed` stay unwritten and `delivery_counts`' *not reported*
    #: sentence stays true. Stated here rather than implied (hard-won law 2).
    "sendgrid": EmailSendgridAdapter,
    "postmark": EmailPostmarkAdapter,
    #: CR-173-BRC10 — the half of New World / Logos WE dial: the day's receipt
    #: file placed in the City's SFTP folder. The two halves the City dials
    #: need none, and are unchanged.
    "erp_newworld": ErpNewWorldAdapter,
    #: `CR-198-BRC10` (2026-10-29) — the THIRTEENTH adapter, and the first whose
    #: credential is the PLATFORM's (`platform_holds_ours`): ONE shared Twilio
    #: account, server-held, texting for every utility (PO ruling 4B). Binding
    #: it is what lifts the card from `coming_soon · v1.1`.
    "sms_twilio": SmsTwilioAdapter,
}


def register_all(registry: _registry.Registry | None = None) -> _registry.Registry:
    """Bind every listed adapter to its manifest. Refused by name for a
    coming-soon provider or an unknown key — at load, never at run time."""
    target = registry if registry is not None else _registry.REGISTRY
    for key, adapter in ADAPTERS.items():
        if getattr(adapter, "key", None) != key:
            raise _registry.ManifestError(
                f"manifest refused — {key}: adapter {adapter.__name__} declares key "
                f"{getattr(adapter, 'key', None)!r}"
            )
        target.register_adapter(key, adapter)
    return target


__all__ = ["ADAPTERS", "Adapter", "register_all"]

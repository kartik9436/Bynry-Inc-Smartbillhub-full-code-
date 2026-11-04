# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-020 (EP-INT-06) — the run record. §1's PROPOSED mitigation:
#           *"the adapter (P2, the anti-corruption layer) SCRUBS a provider
#           message of email addresses, account numbers and postal addresses
#           before it becomes `provider_error`"*. TC-6 is its leak-path fixture.
#           Screens: S142 (the one screen `provider_error` reaches)
# Rules:    BR-INT-040 (P4 — a run states its numbers; per-item results, never
#           a batch boolean) · BR-INT-039 (the run is the durable record) ·
#           CLAUDE.md hard rule 1 (RLS cannot see inside a text column, which
#           is the whole reason this file exists)
# Tests:    06-backend/tests/test_us_int_020_runs.py (TC-6 and the shapes) ·
#           10-scripts/gates/g84_provider_error_scrubbed.py (every writer of
#           `provider_error` goes through the seam)
# Impacts:  apps/integrations/services.py (`scrub()` is this module's front
#           door and the ONE seam every writer passes) · apps/integrations/
#           runs.py (the read model that renders the scrubbed text)
# ───────────────────────────────────────────────────────
"""The scrub — what a provider said, with other people's details taken out.

WHY A WHOLE FILE FOR ONE FUNCTION
---------------------------------
`integration_run.provider_error` is the one column in this product where
ANOTHER TENANT'S DATA CAN ARRIVE. Nobody writes it: a mail server does, by
quoting the message it refused, and a bulk provider does, by quoting the batch
it rejected. Row-level security cannot help — RLS decides which ROWS a tenant
reads, and this leak is INSIDE a row the tenant is entitled to. So the guard
has to be at the moment the text is stored, and it has to be one place a grep
can find (`services.scrub`, which is this module's front door).

WHAT IT TAKES OUT, AND WHAT IT DELIBERATELY LEAVES
--------------------------------------------------
Out: an email address · an account-number-shaped token · a street address and
the place name that follows it · a post-office box. Each becomes `••••`.

Left, verbatim: the provider's status code, their own sentence, their
diagnostic. *"535 5.7.8 AUTHENTICATION FAILED"* survives whole — that string
is the entire reason support asks for this column, and a scrub that ate it
would make the column pointless while still being called a mitigation.

⚠ IT IS A REDUCTION, NOT A GUARANTEE, AND THE DOCSTRING SAYS SO ON PURPOSE
(hard-won law 1). A provider can put a customer's NAME in a message and no
pattern here will catch it. The two guarantees that do not depend on a regular
expression are the ones the story actually rests on: `provider_error` is never
in a list payload, an audit row or a notification, and it is rendered on one
screen to the owning tenant only. This function narrows the blast radius of
the text that does get stored; it does not make the column safe to broadcast,
and no document may say that it does.

⚠ THE ORDER OF THE RULES IS LOAD-BEARING. `1408 Pecan St` begins with a
four-digit number, so the street rule must run BEFORE the account-number rule
or the address is left as `•••• Pecan St` — the street still named, which is
the half that identifies the customer.
"""

from __future__ import annotations

import re

#: What a masked value looks like on screen. Four dots, the same mark the
#: credential hint uses (`••••3F9A`), so a clerk who has seen one knows this one.
MASK = "••••"

#: An email address. Deliberately broad on the local part — a provider quotes
#: whatever the sender typed, including the addresses this product refused.
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")

#: The words that end a street line in the United States. A closed list, not a
#: guess: a token outside it is not treated as an address at all, because a
#: false positive here eats the provider's own sentence.
_STREET_WORDS = (
    "St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Blvd|Boulevard|Way|Ct|Court|"
    "Pl|Place|Ter|Terrace|Cir|Circle|Hwy|Highway|Pkwy|Parkway|Trl|Trail|Sq|Square"
)

#: A street address: a house number, up to four capitalised words, a street
#: word — and then, optionally, the comma-separated place that follows it,
#: because *"1408 Pecan St, Lone Star Ridge"* names the customer's town and the
#: town is the half that tells you which utility they belong to.
_STREET = re.compile(
    r"\b\d{1,6}\s+(?:[A-Z][\w'\-]*\.?\s+){0,4}"
    rf"(?:{_STREET_WORDS})\b\.?"
    r"(?:\s*,\s*[A-Z][\w'\-]*(?:\s+[A-Z][\w'\-]*){0,3})?",
    re.UNICODE,
)

#: A post-office box, which carries no street word at all.
_PO_BOX = re.compile(r"\bP\.?\s?O\.?\s+Box\s+\d+\b", re.IGNORECASE)

#: An account-number-shaped token: two or more groups joined by hyphens
#: (`4471-0021`, `555-0142`) — that alternative FIRST, or `4471` is masked on
#: its own and the number reads `••••-••••` — or four or more digits together.
#: ⚠ NOT a bare run of three (`550`) and NOT a dotted status (`5.7.8`) — those
#: are the provider's own codes and taking them out would be the failure this
#: module's docstring warns about.
_ACCOUNT = re.compile(r"\b\d{2,}(?:-\d{2,})+\b|\b\d{4,}\b")

#: How much of a provider's message is kept at all. A mail server that answers
#: with a kilobyte of its own configuration is not telling support anything,
#: and an unbounded column is a place to hide a payload.
MAX_LENGTH = 2000

#: ── `DEF-INT-10019` · 2026-10-07 · A PROVIDER'S OWN ERROR CODE IS LEFT ──────
#: Cloudflare refuses with the body `error code: 1010`, and `1010` is FOUR
#: digits, so `_ACCOUNT` masked it and the run row read `403, error code: ••••`
#: — the one number that says *which* firewall rule refused us, gone. The
#: docstring above already leaves *"the provider's status code … their
#: diagnostic"* verbatim; this is that rule reaching a code the account
#: pattern caught by shape. **Narrow on purpose:** only digits IMMEDIATELY
#: after the words `error code` survive; every other four-digit run is still
#: masked, so an account number quoted anywhere else in the same message is not.
_PROVIDER_CODE_BEFORE = re.compile(r"error\s+code\s*:?\s*$", re.IGNORECASE)


def _mask_unless_provider_code(text: str, match: re.Match[str]) -> str:
    if _PROVIDER_CODE_BEFORE.search(text[max(0, match.start() - 16) : match.start()]):
        return match.group(0)
    return MASK


def scrub(text: str | None) -> str | None:
    """A provider's words with other people's details replaced by `••••`.

    Idempotent: scrubbing an already-scrubbed string returns it unchanged, so
    a value that passes the seam twice is not damaged. Never raises — a
    provider's bytes are the least trustworthy input this product has, and a
    scrub that threw would lose the run row along with the message.
    """
    if text is None:
        return None
    if not isinstance(text, str):  # a provider handed us something else entirely
        text = str(text)
    cleaned = text.strip()
    if cleaned == "":
        return None
    cleaned = _EMAIL.sub(MASK, cleaned)
    cleaned = _PO_BOX.sub(MASK, cleaned)
    cleaned = _STREET.sub(MASK, cleaned)  # BEFORE the account rule — see the docstring
    cleaned = _ACCOUNT.sub(lambda m: _mask_unless_provider_code(cleaned, m), cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    if len(cleaned) > MAX_LENGTH:
        cleaned = cleaned[:MAX_LENGTH].rstrip() + "…"
    return cleaned


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-020 (EP-INT-06 §1 the PROPOSED mitigation + TC-6) · 03-field-map.md line 152
# generated: 2026-09-04 by the CR-069 wave C build lane
# checklist: A✔ B✔ C✔ D=n/a(no route of its own) E=n/a F✔ G✔ H=n/a(no money, no RLS policy — the guard is textual and its limits are stated)
# gates: pytest tests/test_us_int_020_runs.py -k scrub · G89 (every provider_error writer goes through services.scrub)
# exceptions: this is a REDUCTION and not a guarantee — stated in the docstring, and the two real guarantees (never in a list/audit/notification payload; one screen, owning tenant only) are asserted in the tests
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

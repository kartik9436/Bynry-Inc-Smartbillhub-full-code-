# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-014 (EP-CWP-04) — check and send, and where paperless
#           consent is taken. Screens: CWP-009
# Rules:    BR-CWP-087 / CR-068 R5 (paperless is a RECORDED CONSENT — a
#           timestamp, **the wording version**, and a way to withdraw) ·
#           03-field-map.md `portal_consent.wording_version`, verbatim: *"The
#           version of the words they actually saw. A consent without it is
#           not a consent"* · CR-068 R4 (print stays the floor: bills,
#           receipts, notices and plan letters are ALWAYS printed) ·
#           US-CWP-014 TC-3 (copy claiming paperless stops paper bills FAILS
#           REVIEW — the screen must say *"we print them as well"*)
# Tests:    06-backend/tests/test_us_cwp_014_check_and_send.py TC-1, TC-3
# Impacts:  apps/portal/services.py (what is written to the consent row) ·
#           07-frontend/src/portal/guest/CheckAndSend.tsx (what is shown) ·
#           07-frontend/src/i18n/locales/*.json (the eleven catalogues)
# ───────────────────────────────────────────────────────
"""THE VERSIONS OF THE WORDS, AND THE ONE PLACE THEY ARE NAMED.

A consent row records `wording_version`. That string is worthless unless
somebody can still find out what the words WERE, so this file is the register:
one entry per version, naming the catalogue keys that composed the sentence a
person read and the date it came into use. A version is **append-only** — the
words a person agreed to cannot be edited afterwards, because then the row no
longer records what they saw.

⚠ **CHANGING THE SENTENCE MEANS A NEW VERSION, NEVER AN EDIT.** If
`portal.consent.paperless.label` is reworded, `paperless-v1-2026-09` still
describes the old words and `paperless-v2-…` describes the new ones. That is
the whole reason the column exists, and it is the failure the field map's
sentence is written against.

⚠ **WHY THE TEXT ITSELF IS NOT STORED HERE.** The words live in the eleven
locale catalogues (B14 rule 35 — a catalogue is written in its own language,
not translated from English), and a person consented in the language they were
reading. Copying the English into this file would create a second copy that
drifts, and it would be the wrong copy for ten of the eleven. What is recorded
is the VERSION and the KEYS; what a reviewer looks up is the catalogue at that
version's commit.

⚠ **AND THE HELPER SENTENCE IS PART OF THE CONSENT, NOT DECORATION.** `CR-068`
R4 keeps print as the floor and `US-CWP-014` TC-3 fails any copy that claims
otherwise, so `portal.consent.paperless.helper` — *we print them as well* — is
listed in the version's keys. A version whose label was agreed without it would
be a consent to something the product does not do.
"""

from __future__ import annotations

from typing import Any

#: The screen the release-1 consent is taken on. `03-field-map.md`:
#: `CWP-009` for a new connection, `CWP-025` for a withdrawal.
SCREEN_NEW_CONNECTION = "CWP-009"

#: The current version. `US-CWP-014` §4 names this literal as test data.
PAPERLESS_CURRENT = "paperless-v1-2026-09"

#: version → what composed it. Append only; never edit an entry in place.
VERSIONS: dict[str, dict[str, Any]] = {
    PAPERLESS_CURRENT: {
        "kind": "paperless",
        "in_use_from": "2026-09-04",
        "keys": (
            "portal.consent.paperless.legend",
            "portal.consent.paperless.label",
            "portal.consent.paperless.helper",
        ),
    },
}


def current_version(kind: str = "paperless") -> str:
    """The version a consent taken RIGHT NOW carries.

    Read at the moment of the write, never passed in by the client: a browser
    that could name its own wording version could record a consent against
    words it never showed anybody.
    """
    for version, entry in VERSIONS.items():
        if entry["kind"] == kind:
            return version
    raise KeyError(f"no consent wording registered for {kind!r}")


def is_known(version: Any) -> bool:
    """Is this a version this product has ever shown? Used by the tests, and by
    anything that reads a row back and wants to know whether it can be traced."""
    return str(version) in VERSIONS

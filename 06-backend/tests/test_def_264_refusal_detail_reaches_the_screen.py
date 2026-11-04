# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-004 (CR-009 C-12 — the S8 dispatch + sender cards)
#           Screens: S8 (Notifications tab)
# Rules:    BR-NOT-023 (the SMTP secret is a REFERENCE, never the password) ·
#           BR-SHL-020 (the server sends a KEY and PARAMS; the screen renders
#           the sentence) · 🔒 webhook-keys class
# ───────────────────────────────────────────────────────
"""DEF-264 — the refusal a person reads must contain the reason the server sent.

Every refusal on the S8 Notifications tab rendered as the same nine words:

    "That dispatch setting was refused."

`settings_api._refused` puts the whole explanation in `params["detail"]` —
including the one C-12 exists to prove a person sees, *"…never the password
itself. The password never enters this product's database."* — and the
catalogue string for `notifications.dispatch.refused` had no `{{detail}}`
placeholder in ANY of the eleven locales, so i18next dropped every one of those
sentences on the floor. The sibling key `notifications.queue.refused` has read
*"This message could not be queued: {{detail}}"* since it was written.

**WHY THE TEST LIVES ON THIS SIDE OF THE TREE.** The two halves of the failure
are a Python dict and a JSON catalogue, and no gate compares them: G15 proves
the eleven catalogues agree with each other (all eleven agreed, and all eleven
were equally wrong) and G18 proves the key EXISTS (it did). The missing
comparison is *the params a server refusal carries against the placeholders the
string interpolates*, and only the server knows the first half. Precedent for a
backend test reading `07-frontend/`: `tests/test_def_114_picker_vocabulary.py`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from apps.notifications import settings_api

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

LOCALES = Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "i18n" / "locales"
ELEVEN = (
    "en",
    "es",
    "es-MX",
    "de",
    "hi",
    "fr-FR",
    "id-ID",
    "it-IT",
    "ja-JP",
    "ko-KR",
    "pt-BR",
)


def catalogue(code: str) -> dict[str, str]:
    return json.loads((LOCALES / f"{code}.json").read_text(encoding="utf-8"))


def placeholders(value: str) -> set[str]:
    return set(re.findall(r"\{\{([^{}\s]+)\}\}", value))


def test_def_264__the_secret_reference_refusal_travels_with_its_whole_sentence(brazos, dana):
    """The exact keystrokes that found it: a password pasted where a NAME goes."""
    response = api_call(
        settings_api.notification_settings,
        "patch",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        # ⚠ MOVED AGAIN 2026-10-22 (`DEF-NOT-10534`): the sender card is gone
        # and a mail-server field is now refused by name, with no detail. The
        # nearest live refusal carrying `detail` is an unknown dispatch
        # setting, on the same `notifications.dispatch.refused` key.
        # ⚠ THE SUBJECT MOVED 2026-09-04, THE PROPERTY DID NOT (`US-INT-026`).
        # The keystrokes that found DEF-264 were a password pasted into
        # `smtp_secret_ref`; that field is retired, so the refusal it produced
        # no longer exists. The defect was never ABOUT that field — it was
        # about a refusal whose sentence never reached the screen — so the
        # test keeps its property and takes the nearest live refusal from the
        # same service: a port outside TCP.
        data={"colour": "teal"},
    )
    assert response.status_code >= 400
    assert response.data["message_key"] == "notifications.dispatch.refused"
    detail = response.data["params"]["detail"]
    assert "is not a dispatch setting" in detail


def test_def_264__every_locale_interpolates_the_detail_the_server_sends(brazos, dana):
    """The property, in the direction no gate reads: **a param the server sends
    that the catalogue never interpolates is a sentence nobody will ever see.**

    Written over the params of a REAL refusal envelope rather than over a
    hard-coded `{"detail"}`, so a refusal that grows a second param is covered
    without editing this file.

    Red proof, verbatim, before the eleven catalogues were fixed:

        AssertionError: notifications.dispatch.refused drops {detail} in
        en, es, es-MX, de, hi, fr-FR, id-ID, it-IT, ja-JP, ko-KR, pt-BR — the
        server's sentence never reaches the screen
    """
    response = api_call(
        settings_api.notification_settings,
        "patch",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={"colour": "teal"},
    )
    key = response.data["message_key"]
    sent = set(response.data["params"])
    assert sent, "this test has no subject unless the refusal carries params"

    dropped = [code for code in ELEVEN if not sent <= placeholders(catalogue(code).get(key, ""))]
    assert dropped == [], (
        f"{key} drops {{{','.join(sorted(sent))}}} in {', '.join(dropped)} — the "
        "server's sentence never reaches the screen"
    )


def test_def_264__the_sibling_key_that_got_it_right_is_the_pattern_and_stays_right(brazos):
    """`notifications.queue.refused` is where the shape was copied FROM. It is
    asserted here so the two refusal keys can never drift apart again — the
    whole defect was one of them being written without the other in view."""
    for code in ELEVEN:
        strings = catalogue(code)
        assert "detail" in placeholders(strings["notifications.queue.refused"]), code
        assert "detail" in placeholders(strings["notifications.dispatch.refused"]), code


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-264 (12-governance/10-defect-log.csv row DEF-264 in full · apps/notifications/settings_api.py `_refused` · apps/notifications/api.py KEY_QUEUE_REFUSED · 07-frontend/src/i18n/locales/*.json)
# generated: 2026-08-18 by the CR-008/CR-009 defect lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST on the unfixed catalogues (the failure is quoted in the docstring above); GREEN after the eleven-locale edit. No browser was run by this lane — the coordinator owns the walkthroughs.
# exceptions: (1) this file reads `07-frontend/src/i18n/locales/*.json` from a backend test on purpose: the comparison it makes needs BOTH halves and neither G15 nor G18 can see the server side. The standing prevention — a gate that fails when any server `message_key` carries params the catalogue never interpolates — is owed and is recorded on the defect row; this test closes the two notifications refusal keys only.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

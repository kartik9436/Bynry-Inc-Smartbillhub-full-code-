# ── Trace ──────────────────────────────────────────────
# Change:  CR-139-BRC07 `P5.8` — the door the Scan source calls,
#          `POST /billing/remittance/parse`. Drawing: p067 ① and p068 ②.
# Rules:   CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2 (the barcode
#          carries MINOR UNITS and the conversion is `remittance.py`'s, never a
#          float) · BR-SHL-020 (a plain sentence, never a raw code) ·
#          hard-won law 7 (each case answers *what would make this pass
#          wrongly*)
# Tests:   this file. The grammar itself is `tests/test_cr139_p5_remittance.py`
#          (21 cases, no database at all) and is NOT re-asserted here.
# ───────────────────────────────────────────────────────
"""The scan door — **it verifies and refuses; there is no parse-loosely mode.**

⚠ **THIS FILE DELIBERATELY DOES NOT RE-TEST THE GRAMMAR.**
`test_cr139_p5_remittance.py` already owns the mod-43 check character, the
worked line, the mis-scan, the empty scan and the unencodable character, in 21
cases that need no database. What is NEW here is the DOOR: that a caller gets
the three fields as a screen can use them, and that each of `remittance.py`'s
four refusals arrives as a refusal rather than as a 500 or a best guess.
"""

from __future__ import annotations

import pytest

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

pytestmark: list = []


def _post(brazos, dana, body):
    """The endpoint, through the router that mounts it.

    ⚠ **`resolve()` FIRST, AND IT IS NOT DECORATION.** Hard-won law 2 in its
    URL form: an endpoint no router mounts is a feature that does not exist,
    and every test that called the VIEW FUNCTION directly would still pass.

    ⚠ **AND `force_authenticate` RATHER THAN `request.user = …`** — DRF's own
    `Request.user` runs the authenticators and overwrites whatever the
    underlying Django request carried, so the shortcut silently 401s and a test
    ends up measuring `assert 401 == 422` against a correct permission check
    (`test_cr087_b3_matched_premises_narrowing.py` records the same near-miss).
    """
    from django.urls import resolve
    from rest_framework.test import APIRequestFactory, force_authenticate

    from apps.billing import remittance_api

    assert resolve("/api/v1/billing/remittance/parse").func is remittance_api.remittance_parse

    request = APIRequestFactory().post("/api/v1/billing/remittance/parse", body, format="json")
    force_authenticate(request, user=dana.user)
    request.tenant_role = "system_admin"
    request.tenant_id = brazos.id
    with tenant_ctx(brazos):
        return remittance_api.remittance_parse(request)


#: The blueprint's own worked line: account `ACC-1042`, bill `BL-2608-0117`,
#: `14218` minor units and the mod-43 check character.
GOOD = "ACC-1042$BL-2608-0117$14218%"


@pytest.mark.django_db
def test_cr139_p5_8_a_good_scan_comes_back_as_three_fields(brazos, dana):
    """What the form fills, and the figure it fills with.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** asserting only the two strings. So
    the AMOUNT is asserted in both forms — the decimal string a form takes and
    the minor units the barcode literally carried — because an endpoint that
    returned `14218` as the amount would satisfy a loose check and would key a
    payment of fourteen thousand dollars.
    """
    response = _post(brazos, dana, {"line": GOOD})
    assert response.status_code == 200, response.data
    assert response.data["account_no"] == "ACC-1042"
    assert response.data["invoice_no"] == "BL-2608-0117"
    # Hard rule 2 — a decimal STRING, and `142.18` rather than `14218`.
    assert response.data["amount"] == "142.18"
    assert response.data["amount_minor"] == 14218


@pytest.mark.django_db
@pytest.mark.parametrize(
    "line",
    [
        # One character wrong — the case `P5.14` exists for. Under a parser
        # that did not verify, this points at a real bill belonging to
        # somebody else.
        "ACC-1042$BL-2608-0117$14219%",
        # Two fields instead of three.
        "ACC-1042$14218%",
        # A decimal separator, which is a character two locales read two ways.
        "ACC-1042$BL-2608-0117$142.18%",
    ],
)
def test_cr139_p5_8_a_mis_scan_is_refused_rather_than_guessed(brazos, dana, line):
    """`P5.14` — *a mis-scan fails visibly*.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** a 500. An unhandled
    `RemittanceError` is also "not a 200", so the status is asserted as a
    VALIDATION refusal specifically — a crash would tell the clerk nothing and
    would put the failure in a log nobody is reading.
    """
    response = _post(brazos, dana, {"line": line})
    assert response.status_code == 422, response.data


@pytest.mark.django_db
@pytest.mark.parametrize("body", [{"line": ""}, {"line": "   "}, {}])
def test_cr139_p5_8_an_empty_scan_is_designed_rather_than_discovered(brazos, dana, body):
    """`P5.15` — *a scan with no barcode fails visibly rather than silently
    keying nothing*.

    A scanner that reads no barcode sends NO CHARACTERS AT ALL, so an empty
    input is the ordinary shape of a failed scan and not an edge case.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** accepting the empty line and
    answering three empty strings, which is a 200 that fills a form with
    nothing and reads on screen as a bill with no account.
    """
    response = _post(brazos, dana, body)
    assert response.status_code == 422, response.data


@pytest.mark.django_db
def test_cr139_p5_8_the_refusal_carries_a_sentence_and_not_a_raw_code(brazos, dana):
    """BR-SHL-020, and `G32`'s defect avoided rather than inherited.

    The `message_key` is a LITERAL at the raise site in `remittance_api.py`,
    because `G32` resolves a key only where the helper is defined in the same
    file — it reported **0 unresolved** truthfully over 21 live refusals that
    reached a clerk as silence.
    """
    response = _post(brazos, dana, {"line": "ACC-1042$BL-2608-0117$14219%"})
    assert response.status_code == 422
    # The ratified B12 r1 / 11b §3 G1 envelope is FLAT — six keys, always
    # present. (The first draft of this case read `response.data["error"]` and
    # failed loudly, which is the good outcome: a case asserting an ABSENCE
    # would have passed silently over the same mistake.)
    assert response.data["message_key"] == "workflow.scan.refused"
    # The specifics travel in `detail` so support can see WHICH of the four
    # ways the scan failed, without the clerk reading an id.
    assert "check character" in response.data["params"]["detail"]


@pytest.mark.django_db
def test_cr139_p5_8_the_door_writes_nothing(brazos, dana):
    """A scan produces a ROW for the importer, and hard rule 7 is about a money
    ACTION — reading a barcode is not one.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** nothing much — this is a weak
    check and it is here anyway, because the *two answers to one question*
    risk this phase keeps filing is exactly a second write path appearing on a
    read door. It goes red the day somebody records the scan here instead of
    letting the importer do it.
    """
    from apps.payments import models as payment_models

    with tenant_ctx(brazos):
        before_payments = payment_models.Payment.objects.count()
    assert _post(brazos, dana, {"line": GOOD}).status_code == 200
    with tenant_ctx(brazos):
        assert payment_models.Payment.objects.count() == before_payments

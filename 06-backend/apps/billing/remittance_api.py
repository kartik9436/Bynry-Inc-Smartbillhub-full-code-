# ── Trace ──────────────────────────────────────────────
# Change:   CR-139-BRC07 — the payments blueprint's phase 5, the server half of
#           `P5.8`. ⚠ The task row is titled *the Scan source, switched on*
#           and the CARD IS NOT — `P5.10`'s bars are owed — but this door is
#           live and tested either way. Drawing: p067 ① and p068
#           ②, read as IMAGES at 2.0 (B14 rule 42).
# Story:    no story — 4·3a's Extract stage gains a fifth source card.
# Rules:    CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2 (money is a
#           DECIMAL STRING; the line carries MINOR UNITS and the conversion is
#           `remittance.py`'s, never a float) · BR-SHL-020 (a plain sentence,
#           never a raw code) · B8/LAW 0 (thin: parse → call → serialize)
# Tests:    06-backend/tests/test_cr139_p5_8_scan_parse.py
# Impacts:  config/urls.py (one `include`) · apps/billing/remittance.py (the
#           grammar, which this does NOT re-implement) ·
#           07-frontend/src/components/workflow/ScanInput.tsx (its only caller)
# ───────────────────────────────────────────────────────
"""One door, so the scan grammar lives in ONE place.

    POST /billing/remittance/parse   {"line": "ACC-1042$BL-2608-0117$14218%"}

⚠ **WHY A ROUND TRIP AT ALL, WHEN A SCANNER IS A KEYBOARD.** `CR-139-BRC07` §6
is explicit about it: *"`P5.8` calls `apps.billing.remittance.parse()` — do not
re-derive the grammar; that is the whole reason it is a module."* The
alternative is a second Code 39 mod-43 implementation in TypeScript, and two
implementations of a check character are two things that can disagree about
whether a scan was mis-read — on a path whose entire job is to catch a mis-read.

⚠ **IT VERIFIES AND REFUSES; THERE IS NO *PARSE LOOSELY* MODE.**
`remittance.parse` raises on an empty scan, a bad check character, a wrong field
count and a non-digit amount, and every one of those reaches the clerk as a
sentence rather than as a filled form. `P5.14`'s outcome is *"a mis-scan fails
visibly"* and `P5.15`'s is *"the empty case is designed, not discovered"*.

⚠ **THIS WRITES NOTHING.** A scan produces a ROW for the payments importer to
take through its own mapping, rules, dry run and receipt — *"everything after it
is the runner"* (p068 ②). Nothing here touches `payments`, and hard rule 7 is
about a money ACTION, which reading a barcode is not.
"""

from typing import Any

from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.billing import remittance
from core import errors
from core.permissions import AnyTenantRole
from core.tenancy import require_tenant


@api_view(["POST"])
@permission_classes([AnyTenantRole])
def remittance_parse(request: Any) -> Response:
    """`POST /billing/remittance/parse` — what the scanner just typed, taken apart.

        line   REQUIRED — the characters the wedge sent, guards included

    Answers the three fields and the amount as a DECIMAL STRING beside the
    minor units it was read from. The string is what the form fills (hard rule
    2: money never travels as a JSON number), and the minor units travel too so
    a caller can show the clerk exactly what the barcode said.
    """
    require_tenant(request)
    payload = request.data if isinstance(request.data, dict) else {}
    line = payload.get("line")
    if not isinstance(line, str) or not line.strip():
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            # A LITERAL key at the RAISE SITE — `G32` can only resolve one
            # defined in the same file, and reported 0 unresolved over 21 live
            # refusals that reached a clerk as silence.
            message_key="workflow.scan.refused",
            field_errors=[{"field": "line", "code": errors.VAL_REQUIRED}],
        )
    try:
        scanned = remittance.parse(line)
    except remittance.RemittanceError as bad:
        # ⚠ **A REFUSAL, NOT A 500 AND NOT A BEST GUESS.** `remittance.parse`
        # raises a `ValueError` subclass whose message says WHICH of the four
        # ways the scan failed; it is handed to the clerk as the `detail` of a
        # catalogue sentence, exactly as `BR-SHL-020` requires.
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="workflow.scan.refused",
            params={"detail": str(bad)},
            field_errors=[{"field": "line", "code": errors.VAL_FORMAT}],
        ) from bad
    return Response(
        {
            "account_no": scanned.account_no,
            "invoice_no": scanned.invoice_no,
            # Hard rule 2: the decimal STRING is what a form fills and what the
            # wire carries. `Remittance.amount` is `Decimal(minor) / 100`, which
            # is exact — there is no float anywhere on this path.
            "amount": str(scanned.amount),
            "amount_minor": scanned.amount_minor,
            "check": scanned.check,
        }
    )


urlpatterns = [
    path("billing/remittance/parse", remittance_parse),
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-139-BRC07 §4 row `P5.8` · blueprint p067–p068 as images at 2.0 · apps/billing/remittance.py (`P5.10`)
# generated: 2026-09-23 by LANE P5-SCREENS
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_cr139_p5_8_scan_parse.py
# exceptions: none — this endpoint writes nothing and owns no rule; the grammar is `remittance.py`'s and is not re-implemented here or in TypeScript
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

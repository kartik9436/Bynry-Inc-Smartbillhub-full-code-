# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-716 — S90 tells a clerk a cut account is still accruing base
#          charges; BR-CUS-103 made that false on 2026-08-25
# Rules:   BR-CUS-103 (base charges STOP at the cut; PO 2026-08-25, OQ-380,
#          answer "no") · B18 §5.8.1 (the drawn tile and its caption) ·
#          hard-won law 1 (a comment claiming a guarantee is not the guarantee)
# Files:   apps/customers/disconnect_reads.py ::
#          CUT_ACCRUAL_CAPTION_SUPERSEDED ·
#          07-frontend/src/features/customers/DisconnectsTab.test.tsx ·
#          07-frontend/src/features/customers/DisconnectsTab.tsx
# ───────────────────────────────────────────────────────
"""DEF-716 — the S90 tile's caption, and the rename that had to land twice.

**The defect.** B18 §5.8.1 draws the `CUT, AWAITING PAYMENT` tile with a caption
asserting that a cut account keeps accruing its base charge, and calls it *"a
money statement"*. **BR-CUS-103 (PO 2026-08-25, closing OQ-380, answer "no")
ruled the opposite** — base charges STOP at the cut — and it did so without
touching the file that says otherwise. The server's absence constant was named
`CUT_ACCRUAL_UNVERIFIED` and carried the code string
`cut_base_accrual_unverified`, which was **wrong in two ways**: the accrual is
no longer unverified, and what settled it settled it in the OPPOSITE direction.

**Why the rename needed a test rather than care.** The code string is hardcoded
in `07-frontend/src/features/customers/DisconnectsTab.test.tsx` as a fixture of
the server's payload, and a fixture is not an assertion: **measured on
2026-08-25, changing the server's code and leaving the frontend's copy on the
old spelling produced 19 passed, 3 todo — a completely green frontend suite over
a half-landed rename.** So the pin lives here, where one process can read both
files, and the two halves cannot drift.

**What this file refuses to let happen, each for its own reason:**

  · the old code string surviving anywhere — on either side (§1, §2);
  · the superseded caption being QUOTED in served copy. The `detail` rides the
    tile's `title` attribute, so a clerk reads it: quoting the old sentence to
    stamp it SUPERSEDED puts the false sentence back on the screen. The verbatim
    old wording belongs in source comments, which nobody renders (§3);
  · the replacement OVER-CLAIMING in the other direction. Base stopping is
    real; the $75.00 reconnection fee still does not reach the balance
    (**DEF-708, open** — `disconnects.FEE_NOT_POSTED`), so a caption implying a
    cut account's balance is complete would replace one false statement with
    another. The tile says what the figure IS and stops (§4);
  · the absence going unwired. A constant nothing serves is a note, not a guard
    (hard-won law 2) — §5 drives the real KPI payload.
"""

from datetime import date
from pathlib import Path

import pytest

from apps.customers import disconnect_reads
from apps.customers import disconnects

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The frontend file that hardcodes the server's code string as a fixture.
TAB_TEST = (
    REPO_ROOT / "07-frontend" / "src" / "features" / "customers" / "DisconnectsTab.test.tsx"
)
TAB = REPO_ROOT / "07-frontend" / "src" / "features" / "customers" / "DisconnectsTab.tsx"

#: The spelling DEF-716 retires. Kept as a literal HERE — in a test, where it
#: cannot reach a screen — because the whole point is to detect its return.
RETIRED_CODE = "cut_base_accrual_unverified"

#: B18 §5.8.1's drawn caption. Same reason: this is the sentence that must never
#: be printed, so the one place it may appear is the assertion forbidding it.
FALSE_CAPTION = "still accruing base charges"


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE SERVER'S HALF
# ══════════════════════════════════════════════════════════════════════════
def test_def_716__the_server_code_string_no_longer_implies_doubt():
    """The absence names the RULE that settled it, not a question."""
    absence = disconnect_reads.CUT_ACCRUAL_CAPTION_SUPERSEDED
    assert absence["code"] == "cut_accrual_caption_superseded"
    assert absence["code"] != RETIRED_CODE
    assert "BR-CUS-103" in absence["br_ref"], (
        "the absence must cite the rule that settled the question — a caption "
        "withheld with only a B18 reference still reads as unverified"
    )
    assert "SUPERSEDED" in absence["detail"]
    assert not hasattr(disconnect_reads, "CUT_ACCRUAL_UNVERIFIED"), (
        "the old constant is renamed, not aliased: an alias lets the retired "
        "spelling keep flowing to whatever still imports it"
    )


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE FRONTEND'S HALF — THE PIN THAT DID NOT EXIST
# ══════════════════════════════════════════════════════════════════════════
def test_def_716__the_frontend_fixture_carries_the_same_code_string():
    """⚠ **THE CHECK DEF-716 WAS MISSING, AND WHY IT LIVES HERE.**

    `DisconnectsTab.test.tsx` hardcodes the server's code string as a FIXTURE,
    and a fixture asserts nothing: half-landing this rename leaves the frontend
    suite fully green (measured — 19 passed, 3 todo, on the old spelling against
    the new server). Nothing on either side can see the other, so the pin has to
    be a test that opens both files.
    """
    source = TAB_TEST.read_text(encoding="utf-8")
    code = disconnect_reads.CUT_ACCRUAL_CAPTION_SUPERSEDED["code"]
    assert f'"{code}"' in source, (
        f"{TAB_TEST.name} does not carry the server's code string {code!r}. A rename that "
        "lands on one side only is the defect DEF-716 recorded: both halves move in one "
        "commit."
    )
    # The retired spelling may survive only inside a comment explaining the
    # supersession — never as a value.
    assert f'"{RETIRED_CODE}"' not in source


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE COPY A CLERK ACTUALLY READS
# ══════════════════════════════════════════════════════════════════════════
def test_def_716__served_copy_never_quotes_the_superseded_caption():
    """The SUPERSEDED stamp is a source convention, not a screen one.

    `detail` rides the tile's `title`, so it is rendered. Quoting B18's caption
    in order to mark it superseded puts the false sentence in front of the
    clerk, which is the defect — and `DisconnectsTab.test.tsx`'s own
    `expect(html).not.toContain(...)` catches it, which is how this was found
    while fixing it.
    """
    for field in ("code", "br_ref", "detail"):
        assert FALSE_CAPTION not in disconnect_reads.CUT_ACCRUAL_CAPTION_SUPERSEDED[field]

    # The frontend's rendered tile caption, likewise.
    assert FALSE_CAPTION not in _rendered_caption_defaults()


def _rendered_caption_defaults() -> str:
    """The `defaultValue` strings `DisconnectsTab.tsx` renders for the tiles."""
    source = TAB.read_text(encoding="utf-8")
    body = source.split("export function disconnectsKpis", 1)[1]
    return body.split("\n}\n", 1)[0]


# ══════════════════════════════════════════════════════════════════════════
# 4 · AND IT DOES NOT OVER-CLAIM IN THE OTHER DIRECTION
# ══════════════════════════════════════════════════════════════════════════
def test_def_716__the_replacement_makes_no_claim_about_the_balance():
    """DEF-708 is still open: the reconnection fee does not reach the ledger.

    So the tile may say the service is off and may NOT say, or imply, that what
    these customers owe is settled or complete. A caption that traded one false
    statement for another would close this defect by committing it again.
    """
    detail = disconnect_reads.CUT_ACCRUAL_CAPTION_SUPERSEDED["detail"]
    # The disclaimer is MADE, not merely available to be inferred.
    assert "nothing about what those customers owe" in detail.lower()
    # And no figure is fabricated into the tooltip: the tile is a COUNT, and a
    # money amount here would be a second arithmetic nobody derived.
    assert "$" not in detail

    # ⚠ **THAT CHANGE HAS HAPPENED — DEF-708, 2026-08-27.** This assertion read
    # `FEE_NOT_POSTED["code"] == "reconnection_fee_not_posted"` under the note
    # *"the fee genuinely is still unposted — if that ever changes, this test is
    # the reminder that the caption may then say more."* The fee IS posted now.
    #
    # **THE CAPTION STILL SAYS NOTHING ABOUT WHAT THEY OWE, AND ITS SILENCE IS
    # STILL RIGHT — for a different reason, which is why this test survives
    # rather than being deleted.** It used to be silent because the money was
    # missing; it is silent now because **a COUNT IS NOT A SUM**: this tile
    # counts cases in the `cut` state and never computed a balance. So the
    # assertion moves from *"the fee is unposted"* to *"the reason given is no
    # longer the fee"* — a caption that blamed a closed defect would be
    # hard-won law 1 pointing backwards.
    assert disconnects.FEE_POSTED["code"] == "reconnection_fee_posted_to_ar"
    assert "DEF-708" not in detail, "the caption must not cite a defect that is fixed"
    assert "count of cases is not a sum" in detail


# ══════════════════════════════════════════════════════════════════════════
# 5 · WIRED, NOT MERELY DEFINED (hard-won law 2)
# ══════════════════════════════════════════════════════════════════════════
def test_def_716__the_absence_rides_the_real_kpi_payload(growth_plan, identity_seam):
    """Driven through `kpi_strip`, not read off the constant."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        kpis = disconnect_reads.kpi_strip(as_of=date(2026, 8, 25))
    absence = kpis["cut_awaiting_payment_unavailable"]
    assert absence["code"] == disconnect_reads.CUT_ACCRUAL_CAPTION_SUPERSEDED["code"]
    assert FALSE_CAPTION not in absence["detail"]
    # The figure itself is a count and asserts nothing about money.
    assert isinstance(kpis["cut_awaiting_payment"], int)

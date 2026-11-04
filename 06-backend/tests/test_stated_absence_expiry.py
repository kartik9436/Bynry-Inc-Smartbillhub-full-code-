# ── Trace ──────────────────────────────────────────────
# Defects: DEF-474 (the account Overview said bills had no read endpoint while
#          the same page's Bills tab read one) · DEF-470 (the Accounts list said
#          no open bill's due date was served, and `GET /invoices` served
#          `due_date`) — and the CLASS both belong to
# Rules:   hard-won law 1 (a comment claiming a guarantee is not the guarantee)
#          and its mirror, which G38's docstring states outright: **a screen
#          claiming an ABSENCE is not the absence** · BR-CUS-016 / BR-CUS-048
#          (ageing is DERIVED, never stored) · BR-CUS-034 (customers keeps no
#          copy of a billing row)
# Files:   07-frontend/src/features/customers/accountDetailTabs.tsx ·
#          AccountsListPage.tsx · 10-scripts/gates/g38_stated_absences.py ·
#          12-governance/10-defect-log.csv
# ───────────────────────────────────────────────────────
"""The half of G38 that was missing: a tracked absence has to EXPIRE.

**G38 checks that a stated absence carries a tracking id. Nothing checks whether
the absence is still true.** Its own docstring is explicit that it cannot —
*"not the truth of the sentence; no source-reading check can know that, and a
gate that pretends to would be worse than none (DEF-182)"* — and it is right.
But there is one property a machine CAN read, and it is the property the id was
added for:

    the row a note cites is supposed to be the row whose CLOSING kills the note.

So when that row closes and the note is still on the screen, **the note has
outlived its own expiry date and nothing said so.** That is DEF-474 and DEF-470
exactly. Both sentences were TRUE when written; both were falsified by another
lane shipping the thing they said was missing; both sat on a screen for days
with every gate green, and both were found by a human sweep and by nothing else.

Two checks, aimed at the two halves:

  **1 · An absence citing a CLOSED row is a note nobody re-read.** Not a
  ratchet — an exact set. A new one fails, and so does a fixed one that leaves
  its entry behind, because the entry is the only record of who owes the
  re-read. It is deliberately noisy in ONE direction: closing a defect that a
  screen cites turns this red, which is the whole mechanism.

  **2 · The two absences DEF-470 left standing are asserted to be still true.**
  The register's own words: *"The real remaining gap is the ROLL-UP: GET
  /accounts serves past_due_60_plus as null (not computed) and nothing
  aggregates ageing per account, which is a different sentence from the one on
  screen."* The screen now says exactly that. **The day a lane computes the
  figure, this goes RED** and the KPI's *"Not counted yet"* has to change with
  the fact — which is the guard DEF-470 never had.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from apps.customers import selectors

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "07-frontend" / "src"
DEFECT_LOG = REPO_ROOT / "12-governance" / "10-defect-log.csv"
OPEN_QUESTIONS = REPO_ROOT / "12-governance" / "01-open-questions.md"

#: G38's own attribute. `ArrivesWith` renders `tracks` as `data-tracks` — the id
#: is for us and never for the reader (DEF-332, PO 2026-08-19).
TRACKS = re.compile(r'tracks=\{?"([A-Z]{2,3}-\d+)"')

#: ⛔ **THE NOTES WHOSE TRACKER HAS ALREADY CLOSED, MEASURED 2026-08-26.**
#: Every one is a screen still stating an absence whose expiry date has passed.
#: **None is this lane's to rewrite** — they are five modules' — and several may
#: turn out to be correct with a re-pointed reason, which is precisely the
#: re-read that has to happen and has not.
#:
#: **Deleting an entry is what fixing one looks like.** Adding one requires
#: closing a defect that a live screen cites, and the RED you get for it is the
#: mechanism working: go and read the sentence.
#:
#: The nine are filed as **DEF-740**, which owns the re-read.
EXPIRED_TRACKERS = {
    # DEF-475 closed when CR-028 served `GET /assets/{id}/reads`. Both notes
    # were re-pointed at a DIFFERENT still-true gap and kept the old id.
    ("features/customers/AccountUsageTab.tsx", "DEF-475"),
    ("features/metering/ReadDetailDrawer.tsx", "DEF-475"),
    # DEF-127 (the ledger balance) is `fixed`; two wizards still cite it.
    ("features/customers/DisconnectWizard.tsx", "DEF-127"),
    ("features/customers/TransferWizard.tsx", "DEF-127"),
    # DEF-691 is `wontfix` — a decided absence, which is a different sentence
    # from a waiting one and should probably not be an `ArrivesWith` at all.
    ("features/customers/DisconnectWizard.tsx", "DEF-691"),
    # OQ-346 is CLOSED in the registry; the tab still waits on it.
    ("features/customers/MoveOutsTab.tsx", "OQ-346"),
    # DEF-560 is `fixed-in-part` — the note may be tracking the unfixed part,
    # which is exactly the thing to check rather than to assume.
    ("features/metering/CommonAreasTab.tsx", "DEF-560"),
    ("features/metering/UnitDetailPage.tsx", "DEF-592"),
    ("features/rating/PlanWizard.tsx", "DEF-445"),
}


def _defect_status() -> dict[str, str]:
    with DEFECT_LOG.open(newline="", encoding="utf-8") as handle:
        return {row["id"]: row["status"] for row in csv.DictReader(handle)}


def _open_question_is_closed(oq_id: str) -> bool:
    for line in OPEN_QUESTIONS.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"| {oq_id} "):
            return "CLOSED" in line or "✅" in line
    return False


def _production_sources() -> list[Path]:
    out = []
    for path in sorted(FRONTEND_SRC.rglob("*.ts")) + sorted(FRONTEND_SRC.rglob("*.tsx")):
        rel = path.relative_to(FRONTEND_SRC).as_posix()
        if rel.endswith((".test.tsx", ".test.ts")) or "i18n/locales" in rel:
            continue
        out.append(path)
    return out


def _tracked_absences() -> set[tuple[str, str]]:
    """(file, id) for every stated absence on a production screen."""
    found = set()
    for path in _production_sources():
        rel = path.relative_to(FRONTEND_SRC).as_posix()
        for match in TRACKS.finditer(path.read_text(encoding="utf-8")):
            found.add((rel, match.group(1)))
    return found


# ══════════════════════════════════════════════════════════════════════════
# 1 · A NOTE WHOSE TRACKER HAS CLOSED IS A NOTE NOBODY RE-READ
# ══════════════════════════════════════════════════════════════════════════
def test_every_stated_absence_cites_a_row_that_is_still_open():
    """⚠ **THE CHECK DEF-474 AND DEF-470 WERE BOTH MISSING.**

    G38 made the id mandatory so that *"closing that row is what points a reader
    at every screen still claiming it"*. Nothing pointed. This is the pointer.
    """
    statuses = _defect_status()
    expired = set()
    unknown = set()
    for rel, tracker in _tracked_absences():
        if tracker.startswith("DEF-"):
            status = statuses.get(tracker)
            if status is None:
                unknown.add((rel, tracker))
            elif status != "open":
                expired.add((rel, tracker))
        elif _open_question_is_closed(tracker):
            expired.add((rel, tracker))

    assert unknown == set(), (
        "a screen states an absence tracked by a defect id that is not in "
        f"`12-governance/10-defect-log.csv` at all: {sorted(unknown)}"
    )
    assert expired == EXPIRED_TRACKERS, (
        "the set of stated absences whose tracking row has CLOSED has changed.\n"
        f"  newly expired (go and read the sentence): {sorted(expired - EXPIRED_TRACKERS)}\n"
        f"  no longer expired (delete the entry):     {sorted(EXPIRED_TRACKERS - expired)}\n"
        "A closed row means the thing the screen is waiting for has arrived, been "
        "decided, or been re-pointed. Any of the three changes what the screen "
        "should say — which is DEF-474 and DEF-470 in one sentence."
    )


# ══════════════════════════════════════════════════════════════════════════
# 2 · DEF-470's REMAINING ABSENCE, ASSERTED TRUE
# ══════════════════════════════════════════════════════════════════════════
def test_def_470__the_past_due_60_roll_up_is_still_uncounted():
    """`accounts_rollup()` still serves `past_due_60_plus` as null. Still true?

    ⚠ **AMENDED 2026-09-28 (PO ruling · `DEF-CUS-7700`) — THE TILE THIS CASE
    WAS NAMED AFTER NO LONGER EXISTS, AND THE ASSERTION DOES.** The paragraph
    below is kept because it records why the null is deliberate, and every
    sentence of it about the SCREEN is now false: `S17`'s strip is four tiles
    counted by account STATUS, `PAST DUE 60+` is not one of them, and
    `customers.accounts.rollup.pastDueWhy` has been retired from all eleven
    catalogues. **What this case still guards is the FIELD** — the server
    sends null rather than a bucket-derived undercount — and its expiry is
    unchanged: the day somebody computes the figure it goes RED, and whatever
    renders it by then has to move with it (hard-won law 1).

    DEF-470's sentence was *"no open bill's due date is served"*, which stopped
    being true when `GET /invoices` shipped `due_date` and a server-derived
    `past_due`. The screen now names the gap that is real — the tenant-wide
    ROLL-UP — and `apps/customers/selectors.accounts_rollup` returns
    `past_due_60_plus: None` on purpose, because a count from opening buckets
    alone undercounts every account whose 60+ position came from an issued bill.

    **This assertion is the expiry date the last sentence did not have.** The day
    somebody computes the figure it goes RED, and the tile's copy — and
    `customers.accounts.rollup.pastDueWhy`, which explains the blank in the
    clerk's own language — have to move with it.
    """
    source = (REPO_ROOT / "06-backend/apps/customers/selectors.py").read_text(encoding="utf-8")
    assert '"past_due_60_plus": None,' in source, (
        "`accounts_rollup()` now computes `past_due_60_plus`. Nothing renders it "
        "today (PO ruling 2026-09-28 replaced S17's five tiles with four counted "
        "by account status), so the first thing to decide is WHERE the figure "
        "goes — and whatever names it must say what it includes, because a "
        "bucket-derived count undercounts every account whose 60+ position came "
        "from an issued bill. Then delete this assertion."
    )
    assert hasattr(selectors, "accounts_rollup")


def test_def_470__no_endpoint_aggregates_ageing_per_account():
    """The second half of DEF-470's real gap, with its own expiry date.

    The AGEING COLUMN is served (`selectors.ageing_cells`, BR-CUS-048's four
    bands from the account's own opening buckets). What is NOT served is a
    tenant-wide ageing aggregate — and B18's `oldest 184 days` caption needs the
    same open-invoice position the roll-up does. If a lane adds one, the KPI
    strip has a figure to show and this test says so.
    """
    source = (REPO_ROOT / "06-backend/apps/customers/selectors.py").read_text(encoding="utf-8")
    for name in ("def ageing_rollup", "def account_ageing_totals", "def ageing_summary"):
        assert name not in source, (
            f"`{name}` exists now — the S17 KPI strip can stop saying the 60+ "
            "figure cannot be counted. Read the tile's copy before closing this."
        )


# ══════════════════════════════════════════════════════════════════════════
# 3 · DEF-474's SENTENCE IS GONE, AND STAYS GONE
# ══════════════════════════════════════════════════════════════════════════
def test_def_474__the_overview_no_longer_claims_bills_have_no_read_endpoint():
    """The false sentence, pinned dead.

    `customers.account.arrives.recentBills` told the clerk the last-four-bills
    panel *"joins it once that list has a read endpoint"* while the same page's
    Bills tab read `GET /invoices` with `f.account_id`. The panel is built now
    (`accountDetailTabs.RecentBillsPanel`) and the key is retired. This is a
    string check and it is worth exactly what a string check is worth — DEF-421
    escaped one by rephrasing — so it sits BESIDE check 1, which is the general
    mechanism, not instead of it.
    """
    tabs = (FRONTEND_SRC / "features/customers/accountDetailTabs.tsx").read_text(encoding="utf-8")
    assert "getInvoices(" in tabs, (
        "the Recent bills panel no longer reads `GET /invoices` — DEF-474's fix "
        "has been reverted, or the panel has moved without this pin moving with it"
    )
    for path in _production_sources():
        source = path.read_text(encoding="utf-8")
        assert (
            "customers.account.arrives.recentBills" not in source
        ), f"{path.relative_to(FRONTEND_SRC)} renders the retired DEF-474 key"
    for catalogue in sorted((FRONTEND_SRC / "i18n" / "locales").glob("*.json")):
        assert "customers.account.arrives.recentBills" not in catalogue.read_text(
            encoding="utf-8"
        ), f"{catalogue.name} still carries the string DEF-474 retired"


# ── Trace footer ───────────────────────────────────────
# packet: DEF-474 · DEF-470 · DEF-740 (12-governance/10-defect-log.csv) ·
#         10-scripts/gates/g38_stated_absences.py (the half this completes)
# generated: 2026-08-26 by lane ACCTSTALE (the Accounts stale-copy sweep)
# gates: check 1 was proved RED by adding `("features/customers/MoveInsTab.tsx",
#        "DEF-664")` to the expected set — `no longer expired (delete the
#        entry): [('features/customers/MoveInsTab.tsx', 'DEF-664')]` — and by
#        removing a real entry, which reports it under `newly expired`. Check 2
#        was proved RED by pointing it at a string `selectors.py` does not hold.
# exceptions: check 1 is an EXACT SET rather than G38's ratchet, deliberately:
#        a ratchet lets a newly-expired note hide behind a fixed one, and the
#        whole point is that each expiry is a specific screen somebody has to
#        re-read · the nine entries are five modules' and are REPORTED, not
#        rewritten here — several may be correct with a re-pointed reason, and
#        deciding that per screen is the re-read itself · check 3 is a string
#        check and is documented as one; DEF-421 escaped a string check by
#        rephrasing, which is why it is the third check and not the first ·
#        DEF-474's own RED could not be re-staged: the panel was already built
#        by the W3 billing lane before this lane opened the file, so this pins
#        the fix rather than proving it
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

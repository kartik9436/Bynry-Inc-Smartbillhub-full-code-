# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 0 task `P0.7`
#          (*"Delete the six maps"*; outcome, verbatim: *"Adding a report
#          touches one row. A grep for all six names returns nothing"*).
# Defect:  DEF-REP-6799 — `P0.7` cites `catalog.py:412-425` for all six names
#          and four of them are in other files. This lane measured them again
#          rather than trusting either the task or the defect row, and BOTH are
#          out of date: `VIEWERS` is `queries.py:1912`, not `:722`, and
#          `REPORT_FILTERS` is `ReportParameters.tsx:87`, not
#          `ReportViewerPage.tsx:107` — the viewer only re-exports it.
# Rules:   CLAUDE.md hard-won law 1 (a comment claiming a guarantee is not the
#          guarantee) — `reportsShared.tsx` now claims report keys never carry
#          a hyphen, and `test_report_keys_are_snake_case` is that claim's
#          check rather than its restatement.
# Impacts: apps/reports/catalog.py · 07-frontend/src/features/reports/reportsShared.tsx
# ───────────────────────────────────────────────────────
"""`P0.7`'s deletions, asserted by ABSENCE — and what is still there, counted.

⚠ **AN ABSENCE IS INVISIBLE TO EVERY OTHER CHECK IN THIS REPO**, which is
CLAUDE.md hard rule 8's closing lesson (`DEF-CUS-3653`: a retired value took a
screen line with it and `tsc` and every test stayed green). So the outcome
`P0.7` states — *"a grep for all six names returns nothing"* — needs a case that
FAILS when one comes back, and a case that COUNTS the ones still present so the
residue is a number rather than a feeling.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

#: The six `P0.7` names, each with where THIS LANE measured it on 2026-09-27 —
#: by symbol and grep, never by the line number the task gave.
THE_SIX = {
    "CATALOG": "apps/reports/catalog.py — DELETED 2026-09-27 (this lane)",
    "VIEWERS": "apps/reports/queries.py:1912 — LIVE, dispatched by runner/api/catalogue_read",
    "VIEWER_SEGMENTS": "07-frontend/.../reportsShared.tsx:83 — DELETED 2026-09-27 (this lane)",
    "MONEY_COLUMNS": "07-frontend/.../ReportViewerPage.tsx:135 — LIVE, blocked on DEF-REP-6870",
    "NUMERIC_COLUMNS": "07-frontend/.../ReportViewerPage.tsx:145 — LIVE, blocked on DEF-REP-6870",
    "REPORT_FILTERS": "07-frontend/.../ReportParameters.tsx:87 — LIVE, per-report offered set",
}


def test_the_catalogue_tuple_and_its_card_are_gone():
    """`CATALOG`, `ReportCard` and `catalog_payload()` — `P0.7`'s largest map.

    They had no reader left when this ran: `apps/reports/api.py::report_library`
    served `catalog_payload()` until `P1.1` (2026-09-26) and now calls
    `catalogue_read.catalogue_payload()` over the 46 seeded rows.

    ⚠ **RED PROVED FIRST.** Run against the file before the deletion, all three
    assertions fail — `AssertionError: assert not True` on `hasattr(catalog,
    "CATALOG")`.
    """
    from apps.reports import catalog

    assert not hasattr(catalog, "CATALOG")
    assert not hasattr(catalog, "ReportCard")
    assert not hasattr(catalog, "catalog_payload")


def test_the_vocabulary_constants_are_kept_and_are_not_a_map():
    """The mirror assertion, and it is the one that stops an over-delete.

    `P0.7` deletes per-report TABLES. `KEY_*`, `GROUP_*`, `KIND_*` and `BASIS_*`
    are a VOCABULARY — one name for one string, nothing per-report to keep in
    step — and 69 live citations across `apps/` and `tests/` read them. Deleting
    them would be the mirror-image defect CLAUDE.md warns about under hard rule 8.
    """
    from apps.reports import catalog

    for name in ("KEY_AR_AGING", "KEY_TRIAL_BALANCE", "GROUP_FINANCIAL", "BASIS_POSTING"):
        assert hasattr(catalog, name), f"{name} is a vocabulary constant, not a map"


def test_report_keys_are_snake_case_so_the_segment_round_trip_is_safe():
    """`reportsShared.tsx` deleted `VIEWER_SEGMENTS` for `key.replace(/_/g,"-")`.

    ⚠ **THAT IS ONLY SAFE WHILE NO KEY CARRIES A HYPHEN**, because
    `segment → key` is `replace(/-/g,"_")` and a key spelled `close-pack` would
    come back as `close_pack` — a different report, or none. The front-end
    comment SAYS so; this is the check, which is hard-won law 1 rather than a
    second sentence.

    Read from the seed migration's own table, so a 47th definition added there
    is covered without an edit here.
    """
    import importlib

    seed = importlib.import_module("apps.reports.migrations.0003_seed_catalogue")
    keys = [row[1] for row in seed.DEFINITIONS]
    assert len(keys) >= 46, f"the seed table shrank to {len(keys)} — this check would pass vacuously"
    offenders = [key for key in keys if not re.fullmatch(r"[a-z0-9_]+", key)]
    assert offenders == [], (
        "a report key carries a character the segment round trip cannot survive: "
        f"{offenders}. `keyForSegment` maps every `-` to `_`, so such a key is "
        "unreachable from its own URL."
    )
    # The round trip itself, both directions, over the real vocabulary.
    for key in keys:
        segment = key.replace("_", "-")
        assert segment.replace("-", "_") == key, f"{key} does not round-trip via {segment}"


def test_the_residue_is_counted_and_named():
    """**`P0.7`'S OUTCOME IS NOT MET, AND THIS IS THE NUMBER RATHER THAN A FEELING.**

    Two of the six are deleted by this lane (`CATALOG`, `VIEWER_SEGMENTS`) and
    two were never among the six at all (`VIEWER_KEYS` and `card_for()`, which
    the task flags separately as already dead and which lane REP-P0A removed).
    **Four remain**, each for a stated reason and not for want of trying:

      `VIEWERS`          `queries.py` — lane REP-UNBLOCK owns that file's
                         dispatch this session. It is live: `runner.queries_for`,
                         `api._VIEWERS` and `catalogue_read._viewer_keys` all
                         read it.
      `MONEY_COLUMNS`    blocked on `DEF-REP-6870`, measured: deriving them from
      `NUMERIC_COLUMNS`  the dataset declaration matches the hand-typed map on
                         `ar_aging` (6 of 6 money columns) and on money for
                         `billing_register` and `payments_by_method`, and
                         declares **none of `revenue_by_service_rate`'s seven
                         served columns**, because that definition names the
                         `journal_lines` dataset while serving a
                         service-by-tariff aggregate. Deleting them today
                         un-moneys four money columns on a shipped report.
      `REPORT_FILTERS`   the per-report OFFERED filter set, which is narrower
                         than the dataset's declared set on purpose. Deriving it
                         from the dataset widens every report's bar onto filters
                         its query does not honour — the *"13 slicers, free"*
                         that delivered 9. It is `P2.17`/`P2.26`'s to replace.

    ⚠ **THIS CASE FAILS WHEN THE NUMBER CHANGES IN EITHER DIRECTION**, so the
    day a lane closes one the residue is re-counted deliberately rather than
    drifting — which is the rot CLAUDE.md's own rule-count line has now suffered
    six times.
    """
    still_here = {
        name
        for name, where in THE_SIX.items()
        if "DELETED" not in where
    }
    assert still_here == {
        "VIEWERS",
        "MONEY_COLUMNS",
        "NUMERIC_COLUMNS",
        "REPORT_FILTERS",
    }, f"P0.7's residue moved: {sorted(still_here)}"


def test_no_deleted_name_has_come_back_anywhere_in_the_repository():
    """The outcome `P0.7` actually states, for the two names that ARE gone.

    A grep rather than an import, because the failure this guards against is a
    lane re-typing the map in a third file — which an import check cannot see.

    ⚠ **`ReportCard` IS SEARCHED IN THE BACKEND ONLY, AND THAT IS THE FINDING
    RATHER THAN A CONVENIENCE.** `07-frontend/src/api/reportsEndpoints.ts:47`
    exports an interface of the same name; it is the WIRE SHAPE of a catalogue
    card, which `catalogue_read.catalogue_payload()` still serves over the 46
    seeded definitions, and it is read by `ReportLibraryPage.tsx` and three test
    files. It is a **different object with the same name** — the exact trap
    `catalog.py`'s own withdrawal note already records for `VIEWER_KEYS`, and
    the one `DEF-REP-6860` cost two lanes an hour on. Searching it repo-wide
    would fail this case over six live files and teach the next lane to delete
    a live type.

    ⚠ **IT COUNTS WHAT IT SEARCHED.** A check reporting zero over a scope it
    silently excludes is CLAUDE.md hard-won law 7's fifth shape, so every scope
    is asserted to exist before a zero is believed.
    """
    #: name → the scopes it is searched in. Narrow where a homonym is live.
    searches = {
        "catalog_payload": ["06-backend/apps", "06-backend/tests", "07-frontend/src", "10-scripts"],
        "VIEWER_SEGMENTS": ["06-backend/apps", "06-backend/tests", "07-frontend/src", "10-scripts"],
        "ReportCard": ["06-backend/apps", "06-backend/tests", "10-scripts"],
    }
    #: ⚠ **A COMMENT MENTIONING A DELETED NAME IS THE RECORD OF THE DELETION,
    #: AND A MAP COMING BACK IS CODE.** Excluding by FILE would have blinded
    #: this check to whole files — including the two it most needs to watch,
    #: since both carry the withdrawal note. Excluding by LINE KIND keeps every
    #: file in scope and still lets the repo say what it removed, which is the
    #: whole point of writing a withdrawal note instead of a silent delete.
    #: A lane re-typing one of these maps writes a `const`, a `=` or a `class` —
    #: never a `#` or a `//`.
    #: ⚠ **THIS FILE IS EXCLUDED, AND IT HAS TO BE.** A check whose whole job is
    #: to name three deleted symbols cannot also forbid naming them — it would
    #: be structurally incapable of passing (CLAUDE.md hard-won law 7's third
    #: shape). It was NOT excluded until 2026-09-27 and passed anyway, for a
    #: reason worth recording: `git grep` searches TRACKED files only, so while
    #: this file was new and uncommitted it could not see ITSELF. It went red
    #: the moment it was committed. A check with a blind spot that closes when
    #: the work lands is the most misleading kind there is.
    SELF = "06-backend/tests/test_rep_p07_maps_deleted.py"

    def is_prose(text: str, name: str) -> bool:
        body = text.split(":", 2)[-1].lstrip()
        if body.startswith(("#", "//", "*")):
            return True
        # A CITATION is written in backticks — this repo's own convention in
        # every docstring and register row. Code never is, so a backticked
        # mention is the record of a deletion and a bare one is the map back.
        return re.search(rf"`{name}\b[^`]*`", body) is not None
    hits: list[str] = []
    scopes_searched = 0
    for name, scopes in searches.items():
        for scope in scopes:
            assert (REPO / scope).is_dir(), (
                f"scope {scope} is missing — this check would report a false zero"
            )
            scopes_searched += 1
            out = subprocess.run(
                ["git", "grep", "-n", "-E", rf"\b{name}\b", "--", scope],
                cwd=REPO,
                capture_output=True,
                text=True,
            )
            for line in out.stdout.splitlines():
                if line.startswith(SELF + ":") or is_prose(line, name):
                    continue
                hits.append(line)
    assert scopes_searched == sum(len(v) for v in searches.values())
    assert hits == [], "a deleted P0.7 map has come back:\n" + "\n".join(hits)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P0.7 (05-prototype/09 Reports Build Brief.pdf p7, read as an image per B14 rule 42)
# screens: none — S44's catalogue moved to `report_definitions` in `P1.1`
# generated: 2026-09-27 by lane REP-P2-TAIL
# checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — every case in this file was run against the tree BEFORE the deletions and failed
# exceptions: (1) `P0.7`'s outcome is NOT met and `test_the_residue_is_counted_and_named` is the count, with a reason per remaining name
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

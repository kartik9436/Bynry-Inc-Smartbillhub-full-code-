# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 §8.2 · lane REP-WIRE — the ten dataset queries, wired.
# Defects:  DEF-REP-6894 (six built queries reachable from nothing)
#           DEF-REP-6895 (the notifications dataset cannot be registered at all)
# Covers:   apps/reports/queries.py DATASET_QUERIES / DATASET_STREAMS ·
#           apps/reports/report_seams.py · apps/reports/runner.queries_for
# Rules:    hard-won law 2 (built is not wired) · hard-won law 7 (a check that
#           reports zero over a scope it excludes) · brief §8.2 p91 (two paths,
#           a page and a stream) · BR-REP-001 (a money report names its basis)
# ───────────────────────────────────────────────────────
"""EVERY SEEDED DEFINITION EITHER RESOLVES A QUERY OR REFUSES BY NAME.

⚠ **THIS FILE EXISTS BECAUSE NOTHING ASKED THE QUESTION.** Ten dataset queries
were built between 2026-09-26 and 2026-09-27 by six lanes; each lane's own suite
passed — 25, 25 and 51 cases among them — and every one of those suites imported
its query DIRECTLY. Not one of them asked whether a REPORT could reach it. On
2026-09-27, eighteen of the forty-six seeded definitions raised
`DatasetNotExecutable` naming datasets that were built, measured on real
PostgreSQL 16 and green. That is hard-won law 2 exactly, and law 7's
*reporting zero over a scope it silently excludes*: the per-dataset suites were
truthfully green over a scope that did not contain the registry.

⚠ **IT FAILS NAMING THE REPORT AND NEVER WITH A COUNT.** `assert served == 18`
tells the next reader that something is wrong and not which report a clerk
cannot open; every assertion here carries the keys.

⚠ **AND IT COUNTS BOTH SIDES AND CHECKS THE SUM.** SERVED plus REFUSED must
equal the catalogue's own total, so a definition cannot fall out of both
buckets and be reported by neither — which is the fault this repository files
more than any other.

⚠ **NOTHING HERE IS SKIPPED.** A `pytest.skip` on a missing fixture is a false
pass wearing a green tick.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

from apps.reports import datasets, queries, runner

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _seeded_catalogue():
    """The seeded catalogue, read from the MIGRATION that writes it.

    ⚠ Read from the file rather than from the table on purpose: this test's
    subject is *"is every report a utility can be shown reachable"*, and the
    migration is the definitive list of what is shipped. A table read would
    silently answer over whatever this run happened to seed.
    """
    path = pathlib.Path(__file__).resolve().parents[1] / (
        "apps/reports/migrations/0003_seed_catalogue.py"
    )
    spec = importlib.util.spec_from_file_location("rep_seed_catalogue", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return tuple((row[1], row[5], row[2], row[6]) for row in module.DEFINITIONS)


CATALOGUE = _seeded_catalogue()

#: The catalogue's own size, read from the same place. A literal here would be
#: the count that rots (this repository's most-filed fault); the point of the
#: number is that SERVED + REFUSED must reach it.
CATALOGUE_TOTAL = len(CATALOGUE)


def test_the_catalogue_is_the_forty_six_the_brief_names():
    """A guard on the guard: if the seed shrinks, every count below shrinks
    with it and would still pass. §8.2: *"46 reports sit on 9 datasets."*"""
    assert CATALOGUE_TOTAL == 46, f"the seed now holds {CATALOGUE_TOTAL} definitions"


def test_every_definition_resolves_a_query_or_names_why_not():
    """⚠ **THE ONE THAT WOULD HAVE CAUGHT `DEF-REP-6894` ON THE DAY.**

    `runner.queries_for` returning None is `DatasetNotExecutable` — *no query
    exists for this dataset at all* — and on 2026-09-27 that was FALSE of six
    datasets and eighteen reports. The failure names every report it happened
    to, because *eighteen* is not something a reader can act on.
    """
    unreachable = [
        f"{key} — {name!r}, on dataset {dataset!r}"
        for key, dataset, name, _basis in CATALOGUE
        if runner.queries_for(key, dataset) is None
    ]
    assert not unreachable, (
        "these reports resolve no query, so GET /reports/<key> answers "
        "DatasetNotExecutable over a dataset that may well be built:\n  " + "\n  ".join(unreachable)
    )


def _classify(key: str, dataset: str) -> tuple[str, str]:
    """`(verdict, detail)` for one report — SERVED with its row count, or
    REFUSED with the sentence the owning query publishes."""
    query = runner.queries_for(key, dataset)
    if query is None:
        return "NO QUERY", "runner.queries_for returned None"
    try:
        payload = runner.run(key).payload
    except queries.DatasetCannotServe as refusal:
        return "REFUSED", refusal.reason
    except runner.DatasetNotExecutable as exc:
        return "NO QUERY", str(exc)
    return "SERVED", f"{len(payload.get('rows') or ())} row(s)"


@pytest.fixture()
def _a_tenant(brazos):
    """One provisioned tenant. Every report below runs inside its context —
    hard rule 1: never touch a tenant table without `app.tenant_id` set."""
    return brazos


def test_every_definition_is_served_or_refused_and_the_two_sum_to_the_catalogue(_a_tenant, capsys):
    """THE DELIVERABLE: a verdict per report, both totals, and their sum.

    ⚠ **BOTH NUMBERS ARE PRINTED AND THE SUM IS ASSERTED.** A run that reported
    only *"18 served"* would read identically whether the other twenty-eight
    refused with a sentence or fell through every branch and were counted by
    nobody. `G32` reported `0 unresolved` that way over twenty-one live
    refusals.
    """
    served: list[tuple[str, str]] = []
    refused: list[tuple[str, str]] = []
    broken: list[str] = []

    with tenant_ctx(_a_tenant):
        for key, dataset, name, _basis in CATALOGUE:
            verdict, detail = _classify(key, dataset)
            if verdict == "SERVED":
                served.append((key, detail))
            elif verdict == "REFUSED":
                refused.append((key, detail))
            else:
                broken.append(f"{key} ({name}) on {dataset}: {detail}")

    with capsys.disabled():
        print(f"\n  SERVED  {len(served)}")
        for key, detail in served:
            print(f"    {key:<28} {detail}")
        print(f"  REFUSED {len(refused)}")
        for key, detail in refused:
            print(f"    {key:<28} {detail[:96]}…")
        print(f"  TOTAL   {len(served)} + {len(refused)} = {len(served) + len(refused)}")
        print(f"  CATALOGUE {CATALOGUE_TOTAL}")

    assert not broken, "these reports reach no query at all:\n  " + "\n  ".join(broken)
    assert len(served) + len(refused) == CATALOGUE_TOTAL, (
        f"{len(served)} served + {len(refused)} refused does not reach the "
        f"catalogue's {CATALOGUE_TOTAL}; a definition was counted by nobody"
    )


def test_every_refusal_carries_a_sentence_a_reader_can_act_on(_a_tenant):
    """⚠ A REFUSAL WITHOUT A REASON IS A 501 WEARING A NAME.

    `catalog.py`'s posture, quoted: *a viewer that opens onto a reason is a
    screen pretending to be a report* — and the reason has to say which read
    model would answer it, or the next reader writes the query that already
    exists somewhere else.
    """
    thin: list[str] = []
    with tenant_ctx(_a_tenant):
        for key, dataset, _name, _basis in CATALOGUE:
            verdict, detail = _classify(key, dataset)
            if verdict != "REFUSED":
                continue
            if len(detail.split()) < 25 or key not in detail and detail.strip() == "":
                thin.append(f"{key}: {detail!r}")
    assert not thin, "these refusals do not say enough for a reader to act on:\n  " + "\n  ".join(
        thin
    )


def test_a_served_report_states_the_basis_its_catalogue_row_states(_a_tenant):
    """`BR-REP-001` — and the constant `queries.BASIS_EVENT` is asserted here
    rather than believed. A comment claiming a guarantee is not the guarantee
    (hard-won law 1)."""
    #: The seed's three codes against the read models' own finer words. The
    #: mapping is the seed's `basis_label` column made mechanical: *As at*,
    #: *Read date* and *Effective date* are three facts that all date on the
    #: EVENT basis.
    event_words = {"event", "as_at", "raised", "effective", "read"}
    wrong: list[str] = []
    with tenant_ctx(_a_tenant):
        for key, dataset, _name, basis in CATALOGUE:
            verdict, _detail = _classify(key, dataset)
            if verdict != "SERVED":
                continue
            served = runner.run(key).payload.get("basis")
            assert served, f"{key} states no basis at all (BR-REP-001)"
            if basis is None:
                continue
            if basis == "event" and served not in event_words:
                wrong.append(f"{key}: seeded 'event', served {served!r}")
            elif basis != "event" and served != basis:
                wrong.append(f"{key}: seeded {basis!r}, served {served!r}")
    assert not wrong, "the basis on the wire disagrees with the seeded row:\n  " + "\n  ".join(
        wrong
    )


def test_a_page_and_a_stream_are_two_functions_and_never_one(_a_tenant):
    """§8.2 p91: *"the left path never fetches more than a page; the right path
    never holds one."* A stream that took a `per` is how the billing register's
    export shipped a valid-looking fifty rows of a 38,000-row report."""
    import inspect

    for code, stream in queries.DATASET_STREAMS.items():
        assert inspect.isgeneratorfunction(stream), (
            f"{code}'s stream is not a generator, so an export would hold the "
            "whole result in memory"
        )
        assert (
            queries.DATASET_QUERIES.get(code) is not stream
        ), f"{code} reaches its page and its file through ONE function"


def test_every_registered_dataset_is_one_the_registry_declares():
    """⚠ **AN ENTRY KEYED ON A DATASET `datasets.py` DOES NOT DECLARE IS DEAD
    CODE, AND `notifications` IS THAT CASE TODAY (`DEF-REP-6895`).**

    `runner.bind` looks the definition's dataset up in `BY_CODE` and raises
    before `queries_for` is consulted, so such an entry answers no call that can
    happen. This test is what stops one being added as a reassurance.
    """
    undeclared = sorted(set(queries.DATASET_QUERIES) - set(datasets.BY_CODE))
    assert not undeclared, (
        "these DATASET_QUERIES keys name no declared dataset and can never be "
        f"reached: {undeclared}"
    )
    undeclared_streams = sorted(set(queries.DATASET_STREAMS) - set(datasets.BY_CODE))
    assert not undeclared_streams, f"unreachable DATASET_STREAMS keys: {undeclared_streams}"


def test_no_dataset_key_shadows_a_live_screens_viewer():
    """⚠ **`api._VIEWERS` SPLATS `queries.VIEWERS` AFTER ITS OWN HARDCODED
    KEYS**, so a `VIEWERS` entry named `account_ledger` or `by_premises` would
    REPLACE a live screen's handler — silently, with every test green. The
    dataset fallback reaches the same keys without that hazard, which is why
    this lane registered datasets and added nothing to `VIEWERS`."""
    from apps.reports import api

    hardcoded = ("account_ledger", "by_premises")
    collided = [key for key in hardcoded if key in queries.VIEWERS]
    assert not collided, (
        "these keys are handled by a dedicated screen in api._VIEWERS and "
        f"queries.VIEWERS would override them through the dict merge: {collided}"
    )
    for key in hardcoded:
        assert key in api._VIEWERS, f"{key} lost its dedicated handler"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 §8.2 (05-prototype/09 Reports Build Brief.pdf p91 read as an image per B14 rule 42)
# screens: S44 · S46 — the catalogue and the viewer
# generated: 2026-09-27 by lane REP-WIRE
# checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST, through pytest in a worktree at the pre-change tip — `test_every_definition_resolves_a_query_or_names_why_not` failed naming all EIGHTEEN unreachable reports, and `test_every_definition_is_served_or_refused_and_the_two_sum_to_the_catalogue` failed on the same eighteen.
# exceptions: (1) row COUNTS are printed rather than asserted non-zero here — a provisioned tenant holds what provisioning seeds, and asserting a figure this file does not control is a test that goes red when a seeder changes. The non-zero proof on a populated tenant is `10-scripts/rep_wire_catalogue_run.py` · (2) `notifications` is absent from both registries and the absence is ASSERTED rather than described (`DEF-REP-6895`)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

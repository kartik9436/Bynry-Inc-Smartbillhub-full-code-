# ── Trace ──────────────────────────────────────────────
# Change:   CR-014 — every journey must have a WORKING fixture. This file holds
#           the one property no cohort test can see: that the seeder a booted
#           stack calls can actually CALL the builder it names.
# Defect:   DEF-570 (2026-08-22) — `seed_journey_fixture._extension` calls every
#           group-3/4 builder as `builder(tenant, actor)` while the two group-4
#           builders were authored as `builder(actor)`, so all four second-tenant
#           seeders raised `TypeError: ensure_maple_creek_cohort() takes 1
#           positional argument but 2 were given` on a booted stack. Their tests
#           passed throughout, because the tests call the builders DIRECTLY and
#           only the seeder uses the two-argument seam.
# Rules:    hard-won law 2 (built is not wired) · DEF-108 (a fixture that cannot
#           be produced must refuse by NAME, and a TypeError names nothing).
# Red-proof: written against the live bug and shown RED first — the failure is
#           quoted in the commit message and the W11 lane report, 2026-08-22.
# ───────────────────────────────────────────────────────
"""Can every registered seeder, and every builder it names, actually be called?

DEF-570 is hard-won law 2 in a fixture: four seeders were registered, reviewed,
recorded as BUILT and counted in CR-014's coverage figure, and not one of them
had ever executed — the coverage number counted a registry entry, and the tests
covered the builders by a different door than the seeder uses. Nothing in the
suite compared the two doors.

This file is that comparison, and it is deliberately cheap: no database, no
fixtures, no Django. It asks two questions of the file `boot_stack.sh` runs:

  1. every seeder in `SEEDERS` accepts `(tenant, actor)`;
  2. every builder named in an `_extension(tenant, actor, "…")` call exists on
     the cohort module and accepts `(tenant, actor)` too.

Both are signature questions, so they answer for journeys whose cohort needs a
live Postgres and a demo tenant — which is exactly the set that is expensive to
run and therefore the set that rots.
"""

from __future__ import annotations

import importlib.util
import inspect
import re
from pathlib import Path

import pytest

SEEDER_PATH = (
    Path(__file__).resolve().parents[2] / "08-qa" / "01-e2e" / "stack" / "seed_journey_fixture.py"
)
EXTENSION_CALL = re.compile(r"_extension\(\s*tenant,\s*actor,\s*\"([a-z0-9_]+)\"", re.S)


def _seeder():
    spec = importlib.util.spec_from_file_location("seed_journey_fixture_contract", SEEDER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_cr014_every_registered_seeder_takes_tenant_and_actor():
    """`seed_one` calls `seeder(tenant, actor)`. Nothing else checks that."""
    module = _seeder()
    wrong = []
    for journey_id, seeder in sorted(module.SEEDERS.items()):
        try:
            inspect.signature(seeder).bind(object(), object())
        except TypeError as exc:
            wrong.append(f"{journey_id} → {seeder.__name__}{inspect.signature(seeder)}: {exc}")
    assert not wrong, (
        "these registered seeders cannot be called the way seed_one calls them "
        "(seeder(tenant, actor)) — on a booted stack each is a TypeError, not a "
        "fixture:\n  " + "\n  ".join(wrong)
    )


def test_cr014_every_extension_builder_takes_tenant_and_actor():
    """DEF-570 itself: `_extension` passes two arguments to the cohort builder.

    Read from the SOURCE rather than from a hand-kept list, so a builder added
    tomorrow is covered without anybody remembering this file exists.
    """
    from tests import journey_cohort_fixtures as cohort

    names = sorted(set(EXTENSION_CALL.findall(SEEDER_PATH.read_text(encoding="utf-8"))))
    assert names, (
        "no `_extension(tenant, actor, \"…\")` call was found in the seeder — either the "
        "seam was renamed (update this pattern) or the group-3/4 seeders are gone"
    )
    wrong = []
    for name in names:
        builder = getattr(cohort, name, None)
        if builder is None:
            wrong.append(f"{name} — named by _extension and ABSENT from journey_cohort_fixtures")
            continue
        try:
            inspect.signature(builder).bind(object(), object())
        except TypeError as exc:
            wrong.append(f"{name}{inspect.signature(builder)}: {exc}")
    assert not wrong, (
        "DEF-570's shape: _extension calls builder(tenant, actor) and these builders "
        "cannot take that call, so every journey routed through them raises TypeError "
        "on a booted stack while their own tests stay green:\n  " + "\n  ".join(wrong)
    )


# ── The refusals, and the number they must not inflate ─────────────────────


def test_cr014_every_absent_surface_journey_refuses_by_name():
    """A registered refusal must REFUSE — and say what is missing.

    The failure mode this guards is a refusal that stops refusing: someone adds
    the surface, or edits the seeder, and the journey starts printing ✔ over a
    cohort nobody re-checked. Each of these raises `CannotSeed` carrying the
    ABSENCE in its own words, so a boot log names the missing feature rather
    than saying "failed".
    """
    module = _seeder()
    assert module.SURFACE_ABSENT, "the refusal registry is empty — did it get renamed?"
    for journey_id, reason in sorted(module.SURFACE_ABSENT.items()):
        seeder = module.SEEDERS.get(journey_id)
        assert seeder is not None, (
            f"{journey_id} refuses by name but is not in SEEDERS, so a boot prints the "
            "generic 'no fixture seeder' and the reason is lost"
        )
        with pytest.raises(module.CannotSeed) as refusal:
            seeder(object(), object())
        message = str(refusal.value)
        assert reason.split("\n")[0][:60] in message
        assert "REFUSAL BY NAME" in message


def test_cr014_a_refusal_is_never_counted_as_coverage():
    """DEF-108, turned on CR-014's own scoreboard.

    Registering a refusal makes a boot log honest and must not make the
    COVERAGE FIGURE dishonest. If `--check` counted these, the number the CR
    reports would rise while not one journey became runnable — a green tick for
    an unbuilt feature, which is the exact thing this whole change exists to
    remove.
    """
    import io
    import contextlib

    module = _seeder()
    activated = set(module.activated_journeys())
    refusing = {jid for jid in activated if jid in module.SURFACE_ABSENT}
    registered = {jid for jid in activated if jid in module.SEEDERS}
    assert refusing, "no activated journey refuses by name — this test would be vacuous"

    # ⚠ THE FIGURE IS READ OFF `check_only`'s OWN OUTPUT, never recomputed here.
    # The first version of this test derived `working` itself and stayed green
    # when check_only was mutated to count the refusals — a test that
    # reimplements the thing it is checking agrees with itself, whatever the
    # product does. This reads the line a person reads.
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        module.check_only()
    import re

    def reported(label: str) -> int:
        match = re.search(rf"^{re.escape(label)}\s*\.+\s*(\d+)", captured.getvalue(), re.M)
        assert match is not None, (
            f"--check no longer prints a {label!r} line; this test reads the figure a "
            f"person reads, so a renamed line is a real failure. Output:\n"
            f"{captured.getvalue()[:400]}"
        )
        return int(match.group(1))

    reported_working = reported("with a WORKING fixture")
    reported_refusing = reported("refusing BY NAME")
    assert reported_refusing == len(refusing)
    assert reported_working == len(registered - refusing), (
        f"--check reports {reported_working} covered out of {len(registered)} registered "
        f"seeders while {len(refusing)} of them REFUSE. Counting a refusal as coverage moves "
        "CR-014's own number up and leaves every one of those journeys exactly as unrunnable "
        "— DEF-108 in the scoreboard."
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))

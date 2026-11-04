# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-038 (the Assets door) · US-WRK-037 · US-WRK-051
# Defects:  DEF-AST-4120 (`maintenance_index` never left the server) ·
#           DEF-WRK-4098 / DEF-WRK-4119 (the wire shape three screens guessed)
# Rules:    CLAUDE.md hard-won law 1 (a comment claiming a guarantee is not the
#           guarantee) · law 7 (`--report` the blind spot; a check must be able
#           to fail) · B12 r1
# ───────────────────────────────────────────────────────
"""**`_envelope` IS A BOUNDARY THAT RENAMES EVERYTHING AND DISCARDS THE REST,
AND NOTHING ASSERTED EITHER FACT UNTIL THREE SCREENS SHIPPED BLANK.**

`apps/work/api._envelope` takes a selector's page dict — `{rows, page, per,
total, …}` — and returns `{count, next, previous, results}`. Two things follow,
and each has now cost a live screen:

* **The names change.** Four front-end wrappers were typed from the dict that
  goes IN rather than the one that comes OUT, so `data.rows` was `undefined` and
  `Work → Rules`, `Settings → Labour rates` and the asset detail's Maintenance
  history all drew empty tables over rows this function had just served.
* **Every other key is dropped.** `_envelope` builds a FRESH dict; it does not
  update `result`. `asset_work_orders` set `result["maintenance_index"]` and
  passed `result` in, so the index never reached the browser and every WORK
  ORDER cell in the maintenance history was a dash — with `tsc`, every gate and
  9,810 backend tests green over it.

These cases pin BOTH halves of the contract at the only place both are visible.
They are cheap, they run on the default suite, and they go red on either
regression — which is more than the type system can offer, because a TypeScript
generic on `client.get<T>()` is an assertion the compiler believes rather than a
check anything performs.

⚠ **WHAT THESE CASES DO NOT COVER, SAID PLAINLY (law 7's blind-spot clause).**
They assert the envelope's SHAPE, not that every view uses it correctly. A view
that forgets the spread is caught here only if it is one of the three named
below. The general form is caught on the client side, by
`07-frontend/src/api/paginated.ts` asserting the envelope at runtime, and on the
build side by `10-scripts/gates/g114_list_envelope.py` refusing a second
description of it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from apps.work import api as work_api

API_SOURCE = Path(work_api.__file__).read_text(encoding="utf-8")


def view_source(name: str) -> str:
    """The TEXT of one view function out of `apps/work/api.py`.

    ⚠ **`inspect.getsource(getattr(work_api, name))` DOES NOT WORK HERE AND
    LOOKED LIKE IT DID.** `@api_view` replaces the module attribute with DRF's
    own `view(request, *args, **kwargs)` wrapper, so `getsource` returns nine
    lines of `self.dispatch(...)` for every view in this file — the same nine
    lines each time. A first draft of this test asserted `"_envelope(request"
    in source` against that and failed for all three views with a message
    saying they *"no longer use the envelope"*, which is false and points at
    the wrong file.

    It is worth writing down because it is hard-won law 7's *looking at the
    wrong thing* in miniature: had the assertion been `not in` rather than
    `in`, this check would have passed on every view for ever, over a wrapper
    that can never contain the string it was searching for.
    """
    match = re.search(rf"^def {re.escape(name)}\(.*?(?=^(?:@|def )|\Z)", API_SOURCE, re.M | re.S)
    assert match is not None, f"{name} is not defined in apps/work/api.py"
    return match.group(0)


def test_envelope_emits_exactly_four_keys_and_renames_them() -> None:
    """`rows`→`results`, `total`→`count`, and NOTHING else survives."""

    class _Req:
        @staticmethod
        def build_absolute_uri() -> str:
            return "http://testserver/api/t/work/rules?page=1"

    result = {
        "rows": [{"id": "r1"}, {"id": "r2"}],
        "page": 1,
        "per": 50,
        "total": 2,
        "pages": 1,
        # ⚠ THE KEY THAT PROVES THE DISCARD. A view that sets an extra fact on
        # the selector's dict and hands it over loses it silently.
        "maintenance_index": {"m1": "WO-4908"},
    }
    body = work_api._envelope(_Req(), result)

    assert sorted(body) == ["count", "next", "previous", "results"]
    assert body["count"] == 2
    assert body["results"] == result["rows"]
    # The renames, stated as assertions rather than as a comment (law 1).
    assert "rows" not in body
    assert "total" not in body
    assert "page" not in body
    assert "per" not in body
    # And the discard, which is the half that cost `DEF-AST-4120`.
    assert "maintenance_index" not in body


@pytest.mark.parametrize(
    ("view_name", "extra_key"),
    [
        # Every view in this module that carries a fact BESIDE the page. Each
        # must SPREAD `_envelope` rather than pass its dict through it.
        ("work_orders_awaiting_approval", "oldest_waiting"),
        ("templates", "counts"),
        # ⚠ THE ONE THAT DID NOT, FOR THE LIFE OF WAVE M.
        ("asset_work_orders", "maintenance_index"),
    ],
)
def test_views_with_an_extra_fact_spread_the_envelope(view_name: str, extra_key: str) -> None:
    """A view carrying an extra key must build `{**_envelope(...), ...}`.

    ⚠ **THIS READS SOURCE, AND THAT IS A DELIBERATE TRADE WORTH NAMING.** The
    honest version of this check calls each view through the test client with a
    seeded tenant, and that is what `tests/test_us_wrk_038_asset_door.py` is
    for. What it cannot do is fail for the RIGHT REASON: an empty maintenance
    index and a dropped one serialise identically, so a request-level assertion
    over a fixture with no maintenance entries passes on the bug. Reading the
    call site asks the question the defect actually turns on — *does this view
    hand `result` to `_envelope`, or spread its output?* — and fails naming the
    view.
    """
    source = view_source(view_name)
    assert "_envelope(request" in source, f"{view_name} no longer uses the envelope"
    assert f'"{extra_key}"' in source, f"{view_name} no longer carries {extra_key}"
    assert "**_envelope(request" in source, (
        f"{view_name} carries {extra_key!r} beside a page but passes its dict THROUGH "
        f"_envelope, which builds a fresh four-key dict and copies nothing else — so "
        f"{extra_key!r} never reaches the client (DEF-AST-4120). Spread it: "
        f"{{**_envelope(request, result), {extra_key!r}: ...}}"
    )


def test_the_client_and_the_server_agree_on_the_four_names() -> None:
    """The front end's ONE declaration must spell the same four keys.

    ⚠ **THE TWO HALVES OF THIS CONTRACT LIVE IN DIFFERENT LANGUAGES AND NOTHING
    JOINED THEM UP**, which is the whole reason four wrappers could describe a
    payload the server has never sent. `paginated.ts` carries `PAGINATED_KEYS`
    as data precisely so this assertion can exist.
    """
    from pathlib import Path

    source = Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "api" / "paginated.ts"
    text = source.read_text(encoding="utf-8")
    declared = text.split("PAGINATED_KEYS = [", 1)[1].split("]", 1)[0]
    names = sorted(part.strip().strip('"').strip("'") for part in declared.split(",") if part.strip())
    assert names == ["count", "next", "previous", "results"], (
        "07-frontend/src/api/paginated.ts and apps/work/api._envelope disagree about the "
        "list envelope. They are the two halves of one contract; moving one without the "
        "other is DEF-WRK-4119."
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-AST-4120 / DEF-WRK-4119 (the blank-screens lane, 2026-09-05)
# generated: 2026-09-05 by the blank-screens lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_def_ast_4120_envelope_extras.py — shown RED on the
#        pre-fix `asset_work_orders` and on a `rows` key in paginated.ts first
# exceptions: the spread check reads SOURCE, and says above why a request-level
#             assertion cannot fail for the right reason here
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

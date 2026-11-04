#!/usr/bin/env python3
"""G127 — a partner's response SHAPE may re-key a record and may never compute one.

WHAT THIS REFUSES, AND WHY IT IS A GATE RATHER THAN A PARAGRAPH
----------------------------------------------------------------
`apps/integrations/shapes.py` turns OUR record into a partner's dialect: it
renames a field, renames the envelope, reformats a date, flattens, nests, and
omits. `CR-111-BRC04` states the boundary in the other direction too — **a shape
may not change any value, decide which rows come back, affect any permission or
refusal, or compute anything** — and the module is built so that the boundary is
structural: a `Shape` holds strings and mappings of strings, and there is
nowhere to put a lambda.

**A structure is only structural while somebody keeps it that way.** The change
that breaks this is small, reasonable and arrives under pressure: a partner
needs `amount` net of credits, a `Callable` field is one line, and from then on
the money math has a second home beside `apps/billing` with nothing comparing
the two. That is hard-won law 5's shape — *only the ledger posting service
writes journal lines* — reached through a read surface, and it would pass every
test in this repository because the shaped value would be whatever the shape
said it was.

So this gate asserts the three properties the design rests on:

  1 · **NO CALLABLE REACHES A SHAPE.** No annotation in the module names
      `Callable`, and no shape instance holds a value that is callable. The
      second half is what catches a lane that sneaks a function into a dict
      without annotating it.
  2 · **EVERY RE-FORMATTER IS REVERSIBLE.** `_REFORMATTERS` and `_REVERSERS`
      hold the same keys, and every registered pair round-trips. **That is the
      test that tells a reformat from a computation**: `2026-09-17 →
      17-09-2026` can be read back and `12.5 → 13` cannot.
  3 · **THE MODULE REACHES NO DATA.** It imports no model, no queryset, no
      Django and nothing from `apps.*`. A shape that could reach a row could
      decide which rows come back.

PROVED RED FIRST, THROUGH `run_gates`' REGISTRY PATH AND NOT `python3 <gate>`
------------------------------------------------------------------------------
`DEF-GOV-3733`: two gates were shown red and green by `python3 <gate>.py`, which
exercises `__main__` and never the path `run_gates` uses, and both were
announced green while the suite reported `gate crashed: module has no attribute
run`. Each of the three checks below was broken in the module and watched fail
through `run_gates.py --only G127` before this file was trusted; the failures
are quoted in the lane report.

⚠ **WHAT WOULD MAKE THIS GATE PASS WRONGLY — asked per law 7, and one answer
was real.** *The module is not there, or is renamed, and the gate reports SKIP
over nothing.* A SKIP reads like a pass in a suite of a hundred lines. So the
absence of `shapes.py` is a **FAIL** and not a SKIP: this gate exists because a
named module makes a guarantee, and a guarantee whose module has vanished is not
a guarantee that no longer applies — it is one nobody is keeping. The only SKIP
is `06-backend` itself being absent, which is a front-end-only checkout.

Second answer: *the gate imports the module and a broken module raises, which
some runners read as an error rather than a failure.* Import failure is caught
and returned as FAIL with the exception, so a shape that cannot load is a red
line rather than a crash.
"""

from __future__ import annotations

import ast
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
BACKEND = REPO / "06-backend"
MODULE = BACKEND / "apps" / "integrations" / "shapes.py"

#: Imports a shape may not carry. A shape that can reach a row can decide which
#: rows come back, which is the door's job.
FORBIDDEN_IMPORT_ROOTS = ("django", "apps", "rest_framework", "core")


def _tree() -> ast.Module:
    return ast.parse(MODULE.read_text(encoding="utf-8"))


def callable_annotations(tree: ast.Module) -> list[str]:
    """Every annotation in the module that names `Callable`.

    Textual on the ANNOTATION only, which is the whole surface a dataclass
    field declares — `Callable[..., str]`, `typing.Callable`, `abc.Callable` and
    a bare `Callable` all read the same way here.
    """
    found: list[str] = []
    for node in ast.walk(tree):
        annotation = getattr(node, "annotation", None)
        if annotation is None:
            continue
        text = ast.unparse(annotation)
        if "Callable" in text:
            name = getattr(getattr(node, "target", None), "id", None) or "<field>"
            found.append(f"{name}: {text}")
    return found


def forbidden_imports(tree: ast.Module) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_IMPORT_ROOTS:
                    found.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in FORBIDDEN_IMPORT_ROOTS:
                found.append(node.module)
    return found


def _values(value: object) -> list[object]:
    """Every leaf of a shape's declaration, flattened."""
    if isinstance(value, dict):
        out: list[object] = []
        for key, inner in value.items():
            out.append(key)
            out.extend(_values(inner))
        return out
    if isinstance(value, (list, tuple, set)):
        out = []
        for inner in value:
            out.extend(_values(inner))
        return out
    return [value]


def selftest() -> bool:
    """The gate's own checks, proved on invented input (`DEF-182`).

    A gate whose verdict cannot be shown to bite is worth nothing, and
    `_assert_registry_sane` runs this before the suite trusts the answer.
    """
    good = ast.parse("x: str = 'a'\nfrom dataclasses import dataclass\n")
    bad = ast.parse("from typing import Callable\nx: Callable[[str], str] | None = None\n")
    if callable_annotations(good) or not callable_annotations(bad):
        return False
    if forbidden_imports(good) or not forbidden_imports(
        ast.parse("from apps.billing import models\n")
    ):
        return False
    # A callable hiding in a declaration with no annotation at all.
    if not any(callable(one) for one in _values({"a": {"b": len}})):
        return False
    return not any(callable(one) for one in _values({"a": {"b": "c"}, "d": ("e",)}))


def run() -> tuple[str, str]:
    if not BACKEND.is_dir():
        return "SKIP", "06-backend is not present"
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not hold — it cannot tell a Callable "
            "annotation from a plain one, so its verdict is worthless (DEF-182)"
        )
    if not MODULE.is_file():
        # ⚠ FAIL, not SKIP. See the docstring: a guarantee whose module has
        # vanished is one nobody is keeping, and a SKIP reads like a pass.
        return "FAIL", (
            "apps/integrations/shapes.py is gone. A partner's dialect is data "
            "BY CONSTRUCTION and this gate is the thing that keeps it so; if the "
            "module moved, move this gate in the same commit"
        )

    tree = _tree()
    if (annotations := callable_annotations(tree)):
        return "FAIL", (
            f"shapes.py declares a Callable: {annotations[0]}. A shape holds no code — "
            "a shape that can run a function is a second home for the money math, "
            "beside apps/billing, with nothing comparing the two (hard-won law 5)"
        )
    if (imports := forbidden_imports(tree)):
        return "FAIL", (
            f"shapes.py imports {imports[0]!r}. A shape reaches no data: one that "
            "could read a row could decide which rows come back, which is the door's job"
        )

    sys.path.insert(0, str(BACKEND))
    try:
        from apps.integrations import shapes  # noqa: PLC0415
    except Exception as broken:  # pragma: no cover — reported, never raised
        return "FAIL", f"shapes.py does not import: {type(broken).__name__}: {broken}"

    #: Property 2 — every re-formatter is reversible.
    writers, readers = shapes._REFORMATTERS, shapes._REVERSERS
    if set(writers) != set(readers):
        return "FAIL", (
            f"re-formatters {sorted(set(writers) ^ set(readers))} have no inverse. "
            "A format that cannot be read back is a COMPUTATION wearing a format's "
            "clothes, and a shape may not compute"
        )
    probes = ("2026-09-17", "2026-01-01", "1999-12-31")
    for name in writers:
        for probe in probes:
            if readers[name](writers[name](probe)) != probe:
                return "FAIL", (
                    f"re-formatter {name!r} does not round-trip {probe!r} — it loses "
                    "information, which makes it a computation rather than a format"
                )

    #: Property 1, second half — no callable reached a declared shape.
    declared = [shapes.NATIVE, shapes.INVOICE_CLOUD]
    for shape in declared:
        leaves = _values(dict(shape.envelope))
        for resource in shape.resources.values():
            for part in (resource.rename, resource.flatten, resource.nest):
                leaves.extend(_values(dict(part)))
            leaves.extend(_values(tuple(resource.omit)))
            leaves.extend(_values(tuple(resource.dates)))
        if (runnable := [one for one in leaves if callable(one)]):
            return "FAIL", (
                f"shape {shape.key!r} holds a callable ({runnable[0]!r}) in its "
                "declaration — a shape is data, and data does not run"
            )

    #: Property 3's other half, proved rather than inferred: the native shape is
    #: an exact identity. A shape that quietly touched a value would be caught by
    #: the suite, but this is the one claim the whole mechanism rests on and it
    #: costs one comparison.
    probe = {"id": "INV-1", "amount": "142.1800", "billDate": "2026-09-17"}
    for resource in ("bills", "customers", "payments"):
        if shapes.apply_record(probe, shapes.NATIVE, resource=resource) != probe:
            return "FAIL", (
                f"the native shape is not an identity on {resource!r} — what this "
                "surface has served since CR-110-BRC04 would have moved"
            )

    resources = sum(len(one.resources) for one in declared)
    return "PASS", (
        f"{len(declared)} shape(s) over {resources} resource declaration(s): none holds a "
        f"Callable in an annotation or in a value, none of the {len(writers)} re-formatters "
        f"loses information over {len(probes)} probes, shapes.py imports nothing from "
        f"{'/'.join(FORBIDDEN_IMPORT_ROOTS)}, and the native shape is an exact identity on "
        "bills, customers and payments"
    )


if __name__ == "__main__":  # pragma: no cover
    verdict, detail = run()
    print(f"{verdict}: {detail}")
    sys.exit(0 if verdict in {"PASS", "SKIP"} else 1)

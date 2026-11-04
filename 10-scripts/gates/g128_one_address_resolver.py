#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    CR-115-BRC05 §6 lane 1 — *"ONE PATH DECIDES AN API'S URL"*.
# Defects:  DEF-INT-5502 (the endpoint column blank on every connector) ·
#           DEF-INT-4259 (the wrong host of two reached a browser page policy) ·
#           DEF-INT-5488 (a `host_field` naming a field nobody declares) ·
#           DEF-INT-5612 (the screen shows an address three adapters never dial) ·
#           DEF-INT-5613 (the set-up screen re-derived it in TypeScript and
#           answered differently on 9 of 91 operations) ·
#           DEF-INT-5614 (a fourth hardcoded `base_url`) ·
#           DEF-INT-5615 (a fifth and a sixth, in the GIS module).
# Rules:    CR-115-BRC05 §3 risk 2 (*"a fourth URL source is exactly how it went
#           blank on every connector before"*) · BR-INT-037 (data, never a
#           branch on a provider key) · CLAUDE.md hard-won law 7 (prove it RED
#           in the harness that will run it; a check that passes wrongly; a
#           blind spot with no number beside it).
# Tests:    selftest() below · 06-backend/tests/test_cr115_one_address.py ·
#           10-scripts/cr115_one_address_enumeration.py
# Impacts:  06-backend/apps/** · 07-frontend/src/**
# ───────────────────────────────────────────────────────
"""G128 — ONE FUNCTION DECIDES AN OPERATION'S ADDRESS, AND IT LIVES IN ONE FILE.

WHY THIS GATE EXISTS
--------------------
`CR-115-BRC05` §3 lists three named regression risks and this is the second:

    **The endpoint column** — a fourth URL source is exactly how it went blank
    on every connector before (`DEF-INT-5502`), and how the wrong host reached
    a browser page policy (`DEF-INT-4259`).

On 2026-09-17 there were **seven** places that decided where an operation's
call goes, and the brief named three. The four it did not name were found by
looking: `live_calls.host_for` (`DEF-INT-5614`), `gis.py::_adapter` and
`gis_parcels.py::layer_config` (`DEF-INT-5615`), and a TypeScript function that
printed a dash on **9 of 91 operations** where the connection view printed an
address (`DEF-INT-5613`). None of them was written carelessly; each was written
by a lane that could not see the other six.

The ladder now lives in `apps/integrations/addressing.py`. This gate is what
stops an eighth.

WHAT IT READS, AND WHY IT IS NOT A GREP FOR A FUNCTION NAME
-----------------------------------------------------------
⚠ **A GATE THAT GREPS FOR `resolve_address` PASSES OVER AN INLINED COPY**, and
an inlined copy is precisely how all seven of these arose — nobody imported a
resolver and then ignored it; they each wrote three lines that looked obvious.
So this gate looks for the SHAPE of deciding an address, in two ways:

**A · Nothing outside `addressing.py` touches `Operation.host_field`.**
`host_field` is the NAME of the config key that holds an operation's address.
Reading it is the first move of every resolver that has ever been written here,
in every spelling — `settings.get(op.host_field)`, `field = op.host_field` then
`config[field]`, `getattr(operation, "host_field", "base_url")`. Refusing the
ATTRIBUTE rather than the subscript catches all three, including the variable
form an AST check of the subscript alone would walk straight past. `getattr`
with the literal name is refused too, because that is the spelling
`page_policy` actually used.

**B · Nothing reads a mapping keyed by a DECLARED ADDRESS FIELD NAME.**
`config.get("base_url")`, `settings["tile_url"]`, `conn.config["sftp_host"]`.
The names are not typed here: they are read out of
`06-backend/apps/integrations/manifests/*.py` with `ast`, every `Field(...)`
whose `kind` is `host` or `url`. So a manifest that adds a nineteenth *Service
address* is covered the day it lands rather than the day somebody remembers
this file — which is the same reasoning `DEF-INT-5589` cost us once already.

**C · The front end reads what the server resolved.** A computed member access
mentioning `host_field`, or a settings read keyed by one of those same names,
is the TypeScript half of the same mistake and is `DEF-INT-5613` exactly.

WHAT WOULD MAKE THIS GATE PASS WRONGLY — SAID OUT LOUD (law 7 habit 2)
-----------------------------------------------------------------------
  1. **An inlined copy that mentions neither `host_field` nor a declared field
     name** — for instance `config.get(self.MY_OWN_CONSTANT)`. Check A and
     check B both miss it. Nothing mechanical can catch that; what narrows it
     is that such a copy cannot be written without first deciding WHICH key to
     read, and every key that exists is a declared field name. **It is stated
     here rather than left implied, because a check whose blind spot is not
     written down is one a reader assumes has none.**
  2. **The name in a comment.** A docstring explaining the old defect mentions
     `settings[operation.host_field]` in prose. Check A is AST-based and cannot
     see a comment. Check C is textual, so it strips block and line comments
     first — and this file's own self-test proves the stripping, because
     `ConnectorSetupPage.tsx` carries exactly such a paragraph today.
  3. **A skipped scope reported as zero.** `adapters/` is excluded from check B
     — five registered adapters read an address by a literal of their own and
     three ignore the configured address entirely, which is `DEF-INT-5612` and
     is a behaviour change, not this refactor's. ⚠ **THE COUNT IS PRINTED
     BESIDE THE VERDICT**, because `G32` reported `0 unresolved` truthfully
     over 21 live refusals it could not see and that is the shape being avoided.
  4. **`host` as a literal.** `email_smtp` declares a field called `host`, and
     `.get("host")` appears eleven times in `apps/` about HTTP headers and
     policy rows that have nothing to do with a connector. It is excluded from
     check B BY NAME; the operation path through it is still covered by check A.

ZERO TOLERANCE, NO RATCHET
--------------------------
There is no baseline file, deliberately: a baseline is where an eighth resolver
gets parked. A genuine exception goes in `ALLOWED` below BY NAME, with its
defect id beside it, and is read by a person at review. Six entries on the day
this landed, every one carrying a filed row.

PROVEN RED FIRST (law 7), THROUGH `run_gates`' REGISTRY PATH AND NOT
`python3 g128….py` (`DEF-GOV-3733`) — see the report of 2026-09-17.

Python 3.12 stdlib only. Safe to run from any cwd.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
APPS = REPO / "06-backend" / "apps"
MANIFESTS = APPS / "integrations" / "manifests"
FRONTEND = REPO / "07-frontend" / "src"

#: The one file allowed to climb the ladder. Everything else asks it.
OWNER = "apps/integrations/addressing.py"

#: The attribute that names an operation's address field. Touching it is the
#: first move of every resolver this repository has ever grown.
HOST_FIELD = "host_field"

#: `host` is a field name AND an ordinary word. Excluded from check B by name —
#: see the docstring, false pass 4.
TOO_GENERIC = frozenset({"host"})

#: Genuine exceptions, keyed by **FILE and WHAT IS READ — never by line
#: number**, each with the defect that carries it. A row here is a decision
#: somebody wrote down, not a place a new one may be parked.
#:
#: ⚠ **IT WAS KEYED `path:line` FOR ABOUT AN HOUR ON 2026-09-17 AND WENT RED THE
#: FIRST TIME A SIBLING TOUCHED ONE OF THESE FILES.** Lane 3's GIS fix added
#: thirteen lines above `gis.py::_adapter`; the read moved from 264 to 277 and
#: this gate reported a second resolver where nothing had changed. A false FAIL
#: is kinder than a false pass and it is still the wrong answer — and in a suite
#: carrying 48 standing reds it is exactly where a TRUE one goes to hide
#: (hard-won law 7). **A line number is not a fact about a file; it is a fact
#: about everything above it.**
#:
#: ⚠ **THE COST OF THE COARSER KEY IS PRINTED RATHER THAN HIDDEN:** a SECOND
#: read of the same field in an already-pardoned file is pardoned too. `run()`
#: reports how many occurrences each entry currently matches, so a number that
#: GROWS is visible to a reader even though no gate can refuse it.
ALLOWED: dict[str, str] = {
    "apps/integrations/selectors.py  reads Operation.host_field": (
        "serves the NAME of the field to a screen and resolves nothing — the set-up "
        "screen shows which box holds the address"
    ),
    "apps/integrations/registry.py  reads Operation.host_field": (
        "DEF-INT-5488 — validates that the name is a declared address field, and names "
        "it in the refusal"
    ),
    "apps/integrations/gis.py  reads a mapping by the address field 'base_url'": (
        "DEF-INT-5615 — picks a recorded transport; filed, out of a no-behaviour-change refactor"
    ),
    "apps/integrations/gis_parcels.py  reads a mapping by the address field 'base_url'": (
        "DEF-INT-5615 — the layer address, and `layer_url` is a key no form can write"
    ),
    "apps/integrations/management/commands/seed_gis_city.py  reads a mapping by the address field 'base_url'": (
        "a SEEDING command comparing before it writes; it is the writer, not a reader"
    ),
    "apps/integrations/sending_domain.py  reads a mapping by the address field 'sending_domain'": (
        "CR-115-BRC05 — `sending_domain` is declared `kind=\"host\"` on the two ESP "
        "manifests, so it is in this gate's name set, and it is NOT AN ADDRESS ANYTHING "
        "DIALS. It is the DNS domain a utility's mail claims to come FROM — the subject "
        "of `check_domain_verified`, the thing an IT team publishes records for, and the "
        "name the stored answer is keyed on. **No URL is derived from it anywhere**: both "
        "ESP adapters build their endpoint from `base_url` through `_url()`, inside "
        "`adapters/`, which is this gate's declared exemption. So `addressing.py` still "
        "owns every address that is dialled, and adding a second JOB to that file — "
        "resolve a domain that is not an endpoint — is the muddle the one-resolver rule "
        "exists to prevent, not an instance of it"
    ),
}

SKIP_DIRS = frozenset({"migrations", "__pycache__", "tests", "fixtures"})
#: Excluded from check B, with its number printed. See false pass 3.
ADAPTER_DIR = "adapters"

#: Reads. `.get(key)`, `[key]`. A `dict(...)` construction is not a read and
#: must not be one, or `LIVE_CALL_DEFAULTS = {"base_url": …}` would be refused.
GETTERS = frozenset({"get", "setdefault", "pop"})


def address_field_names(manifest_sources: dict[str, str]) -> set[str]:
    """Every field name any manifest declares with kind `host` or `url`.

    Read out of the manifest FILES rather than typed here, so a nineteenth
    *Service address* is covered the day it lands (`DEF-INT-5589` is the day
    that mattered). `ast` only — this gate never imports Django.
    """
    found: set[str] = set()
    for source in manifest_sources.values():
        try:
            tree = ast.parse(source)
        except SyntaxError:  # pragma: no cover — a broken manifest is another gate's
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            if node.func.id != "Field":
                continue
            words = {
                kw.arg: kw.value.value
                for kw in node.keywords
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str)
            }
            if words.get("kind") in ("host", "url") and words.get("name"):
                found.add(str(words["name"]))
    return found - TOO_GENERIC


def _touches_host_field(node: ast.AST) -> bool:
    """`x.host_field` or `getattr(x, "host_field", …)` — every spelling of
    *give me the name of this operation's address field*."""
    if isinstance(node, ast.Attribute) and node.attr == HOST_FIELD:
        return True
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and node.args
        and isinstance(node.args[-1] if len(node.args) > 1 else None, object)
    ):
        for arg in node.args[1:2]:
            if isinstance(arg, ast.Constant) and arg.value == HOST_FIELD:
                return True
    return False


def _literal_key(node: ast.AST) -> str | None:
    """The string key this expression READS a mapping by, or None."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr in GETTERS and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                return first.value
    # ⚠ **`ast.Load` IS LOAD-BEARING.** `config["base_url"] = value` is a WRITE
    # and is how `seed_gis_city` provisions a connection; a gate that read it as
    # a resolver would refuse the one command that puts an address there.
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.ctx, ast.Load)
        and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, str)
    ):
        return node.slice.value
    return None


def python_findings(source: str, *, where: str, names: set[str]) -> list[str]:
    """`path:line  why` for every second resolver in one Python file."""
    if where == OWNER:
        return []
    out: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:  # pragma: no cover
        return [f"{where}: will not parse ({exc.msg})"]
    in_adapters = f"/{ADAPTER_DIR}/" in f"/{where}"
    for node in ast.walk(tree):
        if _touches_host_field(node):
            out.append(f"{where}:{node.lineno}  reads Operation.host_field")
            continue
        if in_adapters:
            continue
        key = _literal_key(node)
        if key is not None and key in names:
            out.append(f"{where}:{node.lineno}  reads a mapping by the address field {key!r}")
    return out


def adapter_reads(files: dict[str, str], names: set[str]) -> int:
    """HOW MANY address reads live in `adapters/` — the excluded scope, counted.

    A declared blind spot with no number attached is indistinguishable from an
    empty one (law 7, `G32`'s shape). This is `DEF-INT-5612`'s size.
    """
    total = 0
    for where, source in files.items():
        if f"/{ADAPTER_DIR}/" not in f"/{where}":
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:  # pragma: no cover
            continue
        for node in ast.walk(tree):
            key = _literal_key(node)
            if key is not None and key in names:
                total += 1
    return total


_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT = re.compile(r"(?m)^\s*//.*$")
#: A COMPUTED member access mentioning the field name — `settings[op.host_field]`,
#: `settings?.[operation.host_field ?? "base_url"]`.
_TS_COMPUTED = re.compile(r"\[[^\]\n]*\bhost_field\b[^\]\n]*\]")


def ts_findings(source: str, *, where: str, names: set[str]) -> list[str]:
    """The TypeScript half. ⚠ COMMENTS ARE STRIPPED FIRST — a docstring
    explaining `DEF-INT-5613` quotes the very expression it refuses, and a gate
    that fired on its own explanation would be untrustworthy and would be
    silenced (false pass 2)."""
    text = _LINE_COMMENT.sub("", _BLOCK_COMMENT.sub("", source))
    out: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if _TS_COMPUTED.search(line):
            out.append(f"{where}:{number}  indexes settings by host_field")
            continue
        if "settings" not in line:
            continue
        for name in names:
            if f'"{name}"' in line or f"'{name}'" in line:
                out.append(f"{where}:{number}  reads settings by the address field {name!r}")
                break
    return out


def _key(finding: str) -> str:
    """`<path>  <what was read>` — the FILE and the FACT, never the line.

    `findings()` writes `path:line  reason`; this drops the `:line`. See
    `ALLOWED` for the hour that cost and why the coarser key is the right trade.
    """
    where, _, reason = finding.partition("  ")
    return f"{where.rsplit(':', 1)[0]}  {reason}".strip()


def _every(
    python: dict[str, str], typescript: dict[str, str], names: set[str]
) -> list[str]:
    found: list[str] = []
    for where, source in sorted(python.items()):
        found.extend(python_findings(source, where=where, names=names))
    for where, source in sorted(typescript.items()):
        found.extend(ts_findings(source, where=where, names=names))
    return found


def check(
    python: dict[str, str], typescript: dict[str, str], names: set[str]
) -> list[str]:
    return [one for one in _every(python, typescript, names) if _key(one) not in ALLOWED]


def pardoned(
    python: dict[str, str], typescript: dict[str, str], names: set[str]
) -> dict[str, int]:
    """How many occurrences each `ALLOWED` entry is currently pardoning.

    ⚠ **A NUMBER THAT GROWS IS A SECOND RESOLVER IN AN ALREADY-PARDONED FILE**,
    which the file-and-fact key cannot refuse. Printing it is the most this gate
    can do and it is more than saying nothing — law 7: a declared blind spot
    with no number beside it is indistinguishable from an empty one.
    """
    counts = {key: 0 for key in ALLOWED}
    for one in _every(python, typescript, names):
        key = _key(one)
        if key in counts:
            counts[key] += 1
    return counts


# ── the self-test's sources: one per way this gate could be wrong ───────────
MANIFEST = (
    'MANIFEST = Manifest(\n'
    '    key="acme",\n'
    '    fields=(\n'
    '        Field(name="base_url", label="Service address", kind="url"),\n'
    '        Field(name="sftp_host", label="Host", kind="host"),\n'
    '        Field(name="api_key", label="Key", kind="secret"),\n'
    '        Field(name="host", label="Host", kind="host"),\n'
    '    ),\n'
    ')\n'
)
#: The shape every one of the seven resolvers had.
RED_ATTRIBUTE = 'value = (settings or {}).get(op.host_field) or None\n'
#: ⚠ THE VARIANT AN AST CHECK OF THE SUBSCRIPT ALONE WALKS PAST.
RED_VARIABLE = 'field = operation.host_field\nvalue = dict(conn.config or {}).get(field)\n'
#: The spelling `page_policy` really used.
RED_GETATTR = 'field = str(getattr(operation, "host_field", "base_url"))\n'
#: An inlined copy that never says `host_field`.
RED_LITERAL = 'base = str(dict(conn.config or {}).get("base_url") or "")\n'
#: Asking the one resolver — must PASS.
CLEAN = 'found = addressing.resolve_address(manifest, op, settings=settings)\nvalue = found.value\n'
#: ⚠ CONSTRUCTING a defaults dict is not READING one — `LIVE_CALL_DEFAULTS`
#: would be refused by a gate that could not tell them apart. Must PASS.
CLEAN_LITERAL_KEY = 'LIVE_CALL_DEFAULTS = {"geocoder_census": {"base_url": CENSUS_HOST}}\n'
#: `host` is an ordinary word — eleven unrelated reads in `apps/`. Must PASS.
CLEAN_GENERIC = 'value = row.get("host")\n'
#: ⚠ WRITING an address is what `seed_gis_city` is FOR. Must PASS.
CLEAN_WRITE = 'config["base_url"] = base_url\n'
#: The TypeScript that was `DEF-INT-5613`.
RED_TS = 'const value = card.connection?.settings?.[operation.host_field ?? "base_url"];\n'
#: ⚠ THE SAME EXPRESSION IN A DOCSTRING EXPLAINING THE DEFECT. Must PASS, or
#: this gate fires on its own explanation and gets silenced.
CLEAN_TS_COMMENT = (
    "/**\n"
    " * It read `card.connection.settings[operation.host_field ?? \"base_url\"]`\n"
    " * and stopped there.\n"
    " */\n"
    "const value = operation.endpoint;\n"
)


def selftest() -> bool:
    names = address_field_names({"m.py": MANIFEST})
    if names != {"base_url", "sftp_host"}:  # `host` is too generic, `api_key` is not an address
        return False

    def py(source: str) -> list[str]:
        return check({"a.py": source}, {}, names)

    def ts(source: str) -> list[str]:
        return check({}, {"a.tsx": source}, names)

    return (
        bool(py(RED_ATTRIBUTE))
        and bool(py(RED_VARIABLE))  # the variable form an AST subscript check misses
        and bool(py(RED_GETATTR))
        and bool(py(RED_LITERAL))  # an inlined copy that never says host_field
        and not py(CLEAN)
        and not py(CLEAN_LITERAL_KEY)  # building a dict is not reading one
        and not py(CLEAN_GENERIC)  # `host` is an ordinary word
        and not py(CLEAN_WRITE)  # writing an address is not resolving one
        and not check({OWNER: RED_ATTRIBUTE}, {}, names)  # the owner may climb the ladder
        and bool(ts(RED_TS))
        and not ts(CLEAN_TS_COMMENT)  # a comment quoting the defect is not the defect
        # ⚠ **A PARDONED SITE STAYS PARDONED WHEN A SIBLING ADDS LINES ABOVE
        # IT.** This is the case that was broken for an hour on 2026-09-17.
        and not check({"apps/integrations/gis.py": RED_LITERAL}, {}, names)
        and not check({"apps/integrations/gis.py": "\n" * 40 + RED_LITERAL}, {}, names)
        # ...and the same expression in a file nobody pardoned still bites.
        and bool(check({"apps/integrations/somewhere_new.py": RED_LITERAL}, {}, names))
    )


def _read(root: Path, suffixes: tuple[str, ...], base: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if path.suffix not in suffixes or not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name.endswith((".test.ts", ".test.tsx", ".dom.test.tsx")):
            continue
        out[str(path.relative_to(base))] = path.read_text(encoding="utf-8")
    return out


def run() -> tuple[str, str]:
    if not APPS.is_dir():
        return "SKIP", "06-backend/apps is not present"
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not hold — it cannot tell a second address "
            "resolver from a call to the one resolver, so its verdict is worthless (DEF-182)"
        )
    manifest_sources = _read(MANIFESTS, (".py",), MANIFESTS)
    if not manifest_sources:
        return "FAIL", (
            "apps/integrations/manifests holds no manifest — the address field names are "
            "read from those files, so with none this gate checks half of what it claims "
            "and would report a truthful zero over nothing (law 7)"
        )
    names = address_field_names(manifest_sources)
    if not names:
        return "FAIL", (
            f"{len(manifest_sources)} manifest(s) declare no field of kind host or url — "
            "check B would pass over every inlined resolver, silently"
        )
    python = _read(APPS, (".py",), REPO / "06-backend")
    typescript = _read(FRONTEND, (".ts", ".tsx"), REPO / "07-frontend")
    skipped = adapter_reads(python, names)
    counts = pardoned(python, typescript, names)
    new = check(python, typescript, names)
    if new:
        first = new[0]
        return "FAIL", (
            f"{first} — an operation's address is decided in ONE place, "
            f"apps/integrations/addressing.py, and a second is how the endpoint column went "
            f"blank on every connector (DEF-INT-5502) and how the wrong host reached a "
            f"browser policy (DEF-INT-4259)"
            + (
                f" (+{len(new) - 1} more: {', '.join(_key(one) for one in new[1:4])})"
                if len(new) > 1
                else ""
            )
        )
    return "PASS", (
        f"{len(python)} Python and {len(typescript)} front-end file(s) read; "
        f"{len(names)} declared address field name(s) from {len(manifest_sources)} manifest(s); "
        f"nothing outside {OWNER} reads Operation.host_field or a mapping keyed by one of "
        f"those names ({len(ALLOWED)} allowed by FILE AND FACT, never by line number, "
        f"pardoning {sum(counts.values())} occurrence(s) — "
        + ", ".join(
            f"{key.split('  ')[0]}×{n}" for key, n in sorted(counts.items()) if n
        )
        + "; a count that GROWS is a second resolver in a pardoned file, which the key "
        "cannot refuse and this line makes visible); "
        f"⚠ {skipped} address read(s) in apps/integrations/adapters/ were NOT checked — that "
        "scope is DEF-INT-5612 and is a behaviour change, not this refactor; self-test: the "
        "attribute, variable, getattr, inlined-literal and TypeScript forms all bite, a dict "
        "being BUILT does not, and a docstring quoting the defect does not"
    )


if __name__ == "__main__":  # pragma: no cover
    verdict, detail = run()
    print(f"{verdict}: {detail}")
    sys.exit(0 if verdict in {"PASS", "SKIP"} else 1)

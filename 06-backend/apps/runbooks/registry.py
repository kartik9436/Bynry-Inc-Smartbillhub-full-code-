# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-015 · US-RBS-002 (EP-RBS-01) — CR-075 wave B task B2: one
#           Python module per runbook, discovered at AppConfig.ready(), refused
#           AT LOAD when the declaration is wrong.
# Rules:    BR-RBS-001 (kind declared at creation) · BR-RBS-002 (a Check is
#           CONSTRUCTED without action ports) · BR-RBS-021 (twelve blocks) ·
#           BR-RBS-023 (a step declares its mode) · BR-RBS-024 (one category
#           from the fixed sixteen) · BR-RBS-025 (a category with no runbook is
#           never drawn as a filter) · BR-RBS-027 (a runbook may require one
#           other Check)
# Tests:    06-backend/tests/test_us_rbs_015_conformance.py (TC-RBS-15,
#           TC-RBS-19, the add-one-module claim)
# Impacts:  apps/runbooks/apps.py (ready() calls load) ·
#           apps/runbooks/definitions/ · apps/runbooks/engine/executor.py
# ───────────────────────────────────────────────────────
"""The registry — a developer adds ONE Python module and it appears here.

That sentence is `US-RBS-015`, and it is the whole reason `RBS-004` and
`RBS-006` are RENDERERS rather than pages: **runbook twenty-three costs one
Python module and no frontend change.** This file is where a module becomes a
runbook the product knows about, and — more importantly — where a module that
declares the contract wrongly stops the process from starting.

REFUSED AT LOAD, NEVER AT RUN TIME
-----------------------------------
`load()` runs inside `AppConfig.ready()`. Every refusal is therefore a
`RunbookContractError` raised during startup, naming the module and what is
wrong with it. The five the execution plan names, and each is proved red before
it was trusted green (`TC-RBS-15`, `TC-RBS-19`, hard-won law 7):

  * **an unknown category** — `category = "Misc"` (`BR-RBS-024`);
  * **a report block outside the twelve** — refused at run CLOSE by
    `contract.validate_report`, and a definition whose report cannot be
    validated on the conformance fixture is refused here (`BR-RBS-021`);
  * **a Check with a port** — `BR-RBS-002`, the module's whole safety promise;
  * **a step with no mode** — `BR-RBS-023`;
  * **a missing unit of work** — `BR-RBS-019`.

⚠ **THIS DOES NOT DISCOVER, AND THAT IS A DIVERGENCE FROM THE EXECUTION PLAN'S
`B2` — RECORDED HERE RATHER THAN APPLIED SILENTLY.** The obvious build is
`pkgutil.iter_modules()` + `importlib.import_module()`, and `US-RBS-015`'s
promise reads like a request for exactly that. **It was written that way first
and `G115` refused it, by file and line** — its rule 3 permits a dynamic import
only where the argument is a string LITERAL beginning `apps.runbooks.`, because
a computed module name is a hole a static census cannot follow, and that census
is the module's own boundary. Weakening a gate to save one line per runbook is
the wrong trade; wave A's own note says so — *do not weaken it, do not park
anything in it*.

**So a runbook module names itself in `definitions.DEFINITION_MODULES`, one
line, and the conformance suite fails if a file on disk is missing from that
tuple.** Forgetting the line is a RED test naming the file. A discovery loop's
failure mode is the opposite and worse: it silently registers whatever is
present, including a half-finished module a lane left behind.

⚠ **AND A REGISTRY THAT HOLDS NOTHING REPORTS THAT IT HOLDS NOTHING.**
`describe()` returns the count and the keys, and the conformance suite prints
both. Wave B ships **zero** definitions — the first is wave C's
`configuration_check.py` — so a suite that said only *PASSED* over an empty
registry would be `G5` calling 192 skips a pass, one repository along. What is
proved instead is the MECHANISM: `load()` is handed a module built by the test
that declares one runbook, and the runbook appears — and a separate case reads
`definitions/`'s directory listing and fails naming any `.py` file the tuple
does not carry.
"""

from __future__ import annotations

from types import ModuleType

from apps.runbooks import definitions, models
from apps.runbooks.contract import RunbookContractError, RunbookDefinition

#: The package a runbook module lives in — one module per runbook.
DEFINITIONS_PACKAGE = "apps.runbooks.definitions"

#: The attribute a runbook module exposes. One name, so a module that declares
#: something else is silent rather than half-registered — `_load` refuses it.
DEFINITION_ATTR = "RUNBOOK"


class RunbookRegistry:
    """Every runbook this product knows, keyed by `key`, refused at load.

    Deliberately an object rather than a module-level dict: the conformance
    suite builds throwaway registries over throwaway packages, and a global dict
    shared with the live one would make a test's sabotage visible to every other
    test in the session.
    """

    def __init__(self) -> None:
        self._by_key: dict[str, RunbookDefinition] = {}

    # -- registering -------------------------------------------------------

    def register(self, definition: RunbookDefinition) -> RunbookDefinition:
        """Add one runbook. A duplicate key is refused, naming both.

        The definition has ALREADY validated itself — every contract refusal
        happens in `RunbookDefinition.__post_init__`, at construction, which is
        the import of the module. This method adds the one check a single
        definition cannot make about itself: that its key is free.
        """
        if not isinstance(definition, RunbookDefinition):
            raise RunbookContractError(
                f"{definition!r} is not a RunbookDefinition. A runbook module declares "
                f"{DEFINITION_ATTR} = RunbookDefinition(...) and nothing else."
            )
        existing = self._by_key.get(definition.key)
        if existing is not None and existing is not definition:
            raise RunbookContractError(
                f"two runbooks declare the key {definition.key!r} ({existing.name!r} and "
                f"{definition.name!r}). A key is how a run, a work item and a cutover plan item "
                "all point at one runbook; two of them would silently share a history."
            )
        self._by_key[definition.key] = definition
        return definition

    # -- reading -----------------------------------------------------------

    def get(self, key: str) -> RunbookDefinition:
        try:
            return self._by_key[key]
        except KeyError:
            raise RunbookContractError(f"no runbook is registered under the key {key!r}") from None

    def all(self) -> tuple[RunbookDefinition, ...]:
        """Every registered runbook, in key order so a list is stable to read."""
        return tuple(self._by_key[key] for key in sorted(self._by_key))

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_key))

    def checks(self) -> tuple[RunbookDefinition, ...]:
        return tuple(d for d in self.all() if d.is_check)

    def actions(self) -> tuple[RunbookDefinition, ...]:
        return tuple(d for d in self.all() if not d.is_check)

    def categories_in_use(self) -> tuple[str, ...]:
        """The categories that actually hold a runbook, in the fixed sixteen's order.

        ⚠ **THIS IS WHAT A CHIP ROW IS BUILT FROM, AND NEVER THE SIXTEEN**
        (`BR-RBS-025`, `TC-RBS-20`). A chip that filters to an empty list is
        dead UI — hard-won law 2 — and the library draws **eight chips for
        twelve templates** precisely because eight categories hold one. Wave D
        renders it; the derivation lives here so there is one answer rather than
        one per screen.
        """
        held = {d.category for d in self._by_key.values()}
        return tuple(c for c in models.CATEGORIES if c in held)

    def describe(self) -> dict[str, object]:
        """What is registered, as a number and a list, for a check to PRINT.

        A conformance suite that reports PASS over an empty registry has told
        the reader nothing (hard-won law 7: a check's output must distinguish
        pass from fail TO A READER). This is what it prints beside its verdict.
        """
        return {
            "count": len(self._by_key),
            "keys": list(self.keys()),
            "checks": len(self.checks()),
            "actions": len(self.actions()),
            "categories_in_use": list(self.categories_in_use()),
        }

    # -- loading -----------------------------------------------------------

    def load(self, modules: "tuple[ModuleType, ...] | None" = None) -> tuple[str, ...]:
        """Register what every declared runbook module holds. Returns their names.

        `modules` defaults to `definitions.DEFINITION_MODULES` — the tuple a
        runbook module adds one line to. **Any contract error propagates**: this
        is called from `AppConfig.ready()`, so a bad module stops the process
        from starting, which is what *refused at load* means.

        ⚠ **NO DYNAMIC IMPORT.** See the module docstring: a computed module
        name is a hole `G115`'s static census cannot follow, and the census is
        this module's boundary. The modules arrive already imported, by the
        plain `from apps.runbooks.definitions import x` line in the package's
        `__init__`, which a census reads exactly as it reads any other import.

        An EMPTY tuple is not an error — wave B ships no runbook and wave C
        lands the first — but it is not silent either: `describe()` reports the
        count and the conformance suite prints it.
        """
        loaded: list[str] = []
        for module in definitions.DEFINITION_MODULES if modules is None else modules:
            name = getattr(module, "__name__", repr(module))
            self._load(module, name)
            loaded.append(name)
        return tuple(loaded)

    def _load(self, module: ModuleType, module_name: str) -> None:
        definition = getattr(module, DEFINITION_ATTR, None)
        if definition is None:
            raise RunbookContractError(
                f"{module_name} is in {DEFINITIONS_PACKAGE} and declares no "
                f"{DEFINITION_ATTR}. A module here IS a runbook; one that is not would be "
                "imported at startup and do nothing, which reads as a shipped runbook to "
                "everybody but the registry (hard-won law 2)."
            )
        self.register(definition)

    def validate_requires(self) -> None:
        """`BR-RBS-027` — every `requires` names a registered **Check**.

        Run AFTER loading rather than in `__post_init__`, because import order
        is not declaration order: a runbook may legitimately require a Check
        whose module is imported later in the alphabet. A dangling `requires`
        found here still stops startup — the caller is `ready()`.

        The runbook it names must be a **Check**: `requires` runs it first, as
        its own run, and a failed requirement stops the caller with *"Never
        reached"* on every later step. Requiring an Action would mean a Check
        could cause a write by naming one.
        """
        for definition in self.all():
            if definition.requires is None:
                continue
            required = self._by_key.get(definition.requires)
            if required is None:
                raise RunbookContractError(
                    f"runbook {definition.key!r} requires {definition.requires!r}, which is not "
                    "registered. A requirement is run FIRST as its own run and linked from step "
                    "1 (BR-RBS-027); one that does not exist would leave every later step "
                    "reading 'Never reached' for ever."
                )
            if not required.is_check:
                raise RunbookContractError(
                    f"runbook {definition.key!r} requires {definition.requires!r}, which is an "
                    "Action. A requirement is a CHECK (BR-RBS-027): requiring an Action would "
                    "let a Check cause a write by naming one, and BR-RBS-002 is gone."
                )

    # -- tests only --------------------------------------------------------

    def clear(self) -> None:
        """Empty the registry. Used by the conformance suite, never by the product."""
        self._by_key.clear()


#: The one live registry. `AppConfig.ready()` fills it; wave D's endpoints and
#: wave C's renderers read it.
registry = RunbookRegistry()


def register(definition: RunbookDefinition) -> RunbookDefinition:
    """Module-level convenience so a definition module reads as one statement."""
    return registry.register(definition)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-015 · US-RBS-002 (EP-RBS-01; CR-075 wave B task B2)
# generated: 2026-09-06 by the CR-075 wave B build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint in wave B — the routes are wave D) E=n/a(no screen — the renderers are wave C) F✔ G✔ H=n/a(no 🔒 path)
# gates: pytest tests/test_us_rbs_015_conformance.py · G115 (the import census)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

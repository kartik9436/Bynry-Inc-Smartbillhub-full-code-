# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — the plugin shape the PO asked for)
#           Screens: — (pure code; a refusal surfaces via billing's S31.3)
#           No US-ID is cited in this header ON PURPOSE — see errors.py.
# Rules:    BR-RAT-044 (every tariff_model is a module behind ONE price(...)
#           interface; the registry is CLOSED AT IMPORT TIME — models are code,
#           never tenant data) · BR-RAT-045 (charge amount rules, same shape) ·
#           BR-RAT-019 (capacity joined the model enum after v1 scoping without
#           moving a surrounding rule — the precedent this generalises)
# Golden:   GT-1 · GT-2 · GT-5 · GT-8 (priced through the registry, unchanged)
# Tests:    06-backend/tests/test_us_rat_015_plugins.py
# Impacts:  apps/rating/pricing/models/** · apps/rating/pricing/amount_rules/**
#           · apps/rating/engine.py 🔒
# ───────────────────────────────────────────────────────
"""HUMAN-OWNED (CLAUDE.md 🔒 "rating math (B4)"). HUMAN-REVIEW-PENDING — AI-authored under the PO ruling of 2026-08-09 ("AI will do it; we will review it later as human"). Row in 12-governance/09-human-review-ledger.md; not RATIFIED without a recorded human sign-off.

The two plugin registries — closed at import, fail-closed on lookup.

Serves US-RAT-015. This is the whole answer to *"a new rate shape is a new
module, not an engine edit"*: the price-usage stage never names a model, it asks
this registry for one.

TWO PROPERTIES, BOTH TESTED, NEITHER DECORATIVE
-----------------------------------------------
1. **Closed at import time** (BR-RAT-044). `apps/rating/pricing/__init__.py`
   imports the plugin packages and then SEALS both registries. After that any
   `register(...)` raises `RegistryClosed`. Models are code; no tenant row, no
   runtime string and no settings key can add or replace an implementation
   (US-RAT-015 TC-7). This is the boundary a tenant-authored formula (EP-RAT-07)
   must plug INTO, never around.
2. **Fail closed on lookup** (US-RAT-015 TC-5, hard-won law 3). A `tariff_model`
   value with no registered plugin RAISES, naming the model and listing what is
   registered. It never prices as 0 and never falls back to flat. The unsafe
   option is the one you would have to type.

WHAT A PLUGIN IS
----------------
A callable, nothing more:
  pricing model  ->  price(subscription, usage, config) -> tuple[LineCandidate, ...]
  amount rule    ->  amount(charge) -> Decimal                 (NUMERIC(18,6))
Both return UNROUNDED values. Rounding is a finalization concern and never a
plugin concern (BR-RAT-003 / B4.4) — `LineCandidate` exists so that is
structural rather than a rule in a comment (US-RAT-015 TC-6).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar

from apps.rating.pricing import errors

T = TypeVar("T", bound=Callable[..., object])


class Registry(Generic[T]):
    """A name -> implementation map that stops accepting entries at import end."""

    def __init__(self, kind: str, missing_error: type[Exception]) -> None:
        self._kind = kind
        self._missing_error = missing_error
        self._entries: dict[str, T] = {}
        self._sealed = False

    # -- write side: import time only ---------------------------------------

    def register(self, name: str, implementation: T) -> T:
        """Add a plugin. Callable from a module body at import time and nowhere
        else — after `seal()` this raises (BR-RAT-044, US-RAT-015 TC-7)."""
        if self._sealed:
            raise errors.RegistryClosed(
                f"the {self._kind} registry is closed at import time (BR-RAT-044): "
                f"{name!r} cannot be registered at runtime. A new {self._kind} is a "
                "new module imported by apps/rating/pricing/__init__.py, never a "
                "tenant row and never a patched-in callable."
            )
        if name in self._entries:
            raise errors.RegistryClosed(
                f"{self._kind} {name!r} is already registered by "
                f"{self._entries[name].__module__}: one name, one module."
            )
        self._entries[name] = implementation
        return implementation

    def seal(self) -> None:
        """Close the registry. Idempotent, so a re-import cannot re-open it."""
        self._sealed = True

    # -- read side ----------------------------------------------------------

    @property
    def sealed(self) -> bool:
        return self._sealed

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def resolve(self, name: str) -> T:
        """The plugin for `name`, or a REFUSAL naming what was asked for.

        Never returns a default. US-RAT-015 TC-5: an unregistered model stops the
        run rather than pricing as zero or silently falling back to flat.
        """
        try:
            return self._entries[name]
        except KeyError:
            raise self._missing_error(
                f"no {self._kind} plugin registered for {name!r}; registered: "
                f"{', '.join(self.names()) or '(none)'}. A {self._kind} the engine "
                "does not implement is a refusal, never a zero (BR-RAT-044/045)."
            ) from None


#: `tariff_versions.model` -> pricing plugin (BR-RAT-044).
PRICING_MODELS: Registry[Callable[..., object]] = Registry(
    "tariff model", errors.UnknownPricingModel
)

#: `charges.amount_rule` -> amount plugin (BR-RAT-045).
AMOUNT_RULES: Registry[Callable[..., object]] = Registry(
    "charge amount rule", errors.UnknownAmountRule
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-015@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — recomputed 2026-08-10)
# generated: 2026-08-10 by story-coder (rating-engine lane — EP-RAT-05)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden✔ · pytest tests -m "not golden and not isolation"✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔ · run_gates 14 PASS/0 FAIL/1 SKIP✔
# exceptions: BR-RAT-044/045 are PROPOSED (not yet PO-ratified) — this file implements the SHAPE they describe and changes no arithmetic, which is exactly what US-RAT-015 says the story is. If the PO amends the interface, the plugins move; no figure does.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

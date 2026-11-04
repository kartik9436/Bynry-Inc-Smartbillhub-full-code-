# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — the modular shape the PO asked for)
#           Screens: — (pure code)
#           No US-ID is cited in this header ON PURPOSE — see errors.py.
# Rules:    BR-RAT-044 (pricing-model registry, CLOSED AT IMPORT TIME) ·
#           BR-RAT-045 (charge-amount-rule registry, same) · BR-BIL-037 (the
#           stage contracts) · BR-BIL-039 (every stage pure)
# Golden:   GT-1 · GT-2 · GT-3 · GT-5 · GT-8 · GT-10 · GT-11 — B5 ❄️ FROZEN
# Tests:    06-backend/tests/test_us_rat_015_plugins.py (the seal)
# Impacts:  apps/rating/engine.py 🔒 (imports this package and nothing below it)
# ───────────────────────────────────────────────────────
"""The pricing package — the registries that seal at import.
HUMAN-OWNED (CLAUDE.md 🔒 "rating math (B4)"). HUMAN-REVIEW-PENDING —
AI-authored under the PO ruling of 2026-08-09 ("AI will do it; we will
review it later as human"). Row in 12-governance/09-human-review-ledger.md.
This file holds no arithmetic; it is guarded because it decides WHICH
plugin prices a tariff, and a wrong answer there is a wrong bill.
"""

from apps.rating.pricing import amount_rules, models, registry

models._register()
amount_rules._register()
registry.PRICING_MODELS.seal()
registry.AMOUNT_RULES.seal()

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-015@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — recomputed 2026-08-10)
# generated: 2026-08-10 by story-coder (rating-engine lane — EP-RAT-05)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure package) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔ · run_gates 14 PASS/0 FAIL/1 SKIP✔
# exceptions: `_register()` is imported across a package boundary despite its leading underscore — deliberate: it marks "import-time only, not part of the plugin API" while still being callable from the one module allowed to call it. Making it public would invite a second caller and a second seal.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

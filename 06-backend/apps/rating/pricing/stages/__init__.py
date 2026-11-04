# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core) · EP-BIL-01 (BR-BIL-037 stages 3·4·5)
#           Screens: — (pure code)
#           No US-ID is cited in this header ON PURPOSE — see ../errors.py.
# Rules:    BR-BIL-037 (named stages in one fixed total order; one input and one
#           output contract each; only the orchestrator knows the sequence) ·
#           BR-BIL-039 (stages 1–5 are pure: no writes, no external calls, no
#           clock) · BR-BIL-038 (however the engine is restructured inside,
#           GT-1..61 come out identical)
# Golden:   GT-1 · GT-2 · GT-3 · GT-5 · GT-10 · GT-11 — B5 ❄️ FROZEN
# Tests:    06-backend/tests/test_us_rat_012_engine.py (per-stage, from
#           fixtures, with no database and no other stage present)
# Impacts:  apps/rating/engine.py 🔒 (the only caller that knows the order)
# ───────────────────────────────────────────────────────
"""HUMAN-OWNED (CLAUDE.md 🔒 "rating math (B4)"). HUMAN-REVIEW-PENDING — AI-authored under the PO ruling of 2026-08-09 ("AI will do it; we will review it later as human"). Row in 12-governance/09-human-review-ledger.md; not RATIFIED without a recorded human sign-off.

The engine's stages, in order, and the constant that IS the order.

    normalize -> price_usage -> apply_charges -> finalize -> apply_discounts
              -> compute_tax -> assemble

(`apply_discounts` joined 2026-08-22 — DEF-502: the pipeline had NO discount
stage, so `discount_pricing`'s tested arithmetic was priced by nothing. It runs
after `finalize` because a scoped discount is a percentage of the PRINTED
amounts (BR-RAT-068), and before `compute_tax` because R6 precedes R7 and each
tax then picks its own base (BR-RAT-071/106). On a bill with no discounts it is
the identity, which is every B5 fixture.)

Each stage is a pure function taking its predecessor's output and returning one
frozen contract, so any of them can be run from a fixture with no database and
no other stage present (BR-BIL-039, US-BIL-029 TC-2). No stage calls another —
`apps/rating/engine.py` is the only module that knows the sequence, which is
what BR-BIL-037 means by "only the orchestrator knows the sequence".

HOW THESE MAP ONTO THE SEVEN-STAGE BILL RUN (BR-BIL-037)
--------------------------------------------------------
The bill run's stages 1 (resolve-subscription) and 2 (measure-consumption) are
billing's, and 6 (assemble-document) and 7 (post-to-ledger) are billing's too —
none of them is here, and the PO has held them. Rating owns 3·4·5:

    run stage 3 price-usage     -> normalize + price_usage
    run stage 4 apply-charges   -> apply_charges
    run stage 5 apply-discounts -> finalize + apply_discounts
    run stage 6 compute-tax     -> compute_tax + assemble

(Run stages renumbered 2026-08-22 with the DEF-502 boundary move: BR-BIL-037 as
amended names EIGHT stages, apply-discounts fifth; assemble-document and
post-to-ledger are 7 and 8. `finalize` maps into stage 5 because the discount
is computed over the finalized amounts — BR-RAT-068's "percentage of what is
printed".)

`normalize` is the engine's own front door (the gates that make the seam's
inputs safe to price), `finalize` is the single rounding boundary and `assemble`
reports totals. They are rating-internal sub-stages: the run's seven stages are
not renumbered by them, exactly as US-BIL-029 warns that the seven stages and
the five S31 wizard steps do not renumber each other.

STAGE_ORDER below is data, not folklore (US-BIL-029 TC-4): a test asserts the
engine executes exactly this sequence, so removing a stage fails a test rather
than silently skipping work.
"""

STAGE_ORDER: tuple[str, ...] = (
    "normalize",
    "price_usage",
    "apply_charges",
    "finalize",
    "apply_discounts",
    "compute_tax",
    "assemble",
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — recomputed 2026-08-10)
# generated: 2026-08-10 by story-coder (rating-engine lane — EP-RAT-05)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔ · run_gates 14 PASS/0 FAIL/1 SKIP✔
# exceptions: BR-BIL-037 is PROPOSED (derived, not yet PO-ratified) and names SEVEN run stages; this package implements only the three rating owns, split into six rating-internal sub-stages. The mapping is stated above rather than assumed. Bill-run stages 1·2·6·7 are billing's and are explicitly OUT of this lane (PO hold, 2026-08-10).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

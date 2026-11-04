# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-029 (the run's internal shape)   Screens: S31.2 · S31.3
# Rules:    BR-BIL-037 (seven named stages in one fixed total order; a stage
#           receives its predecessor's output and NOTHING else; only the
#           orchestrator knows the sequence) · BR-BIL-039 (stages 1–5 pure)
# ───────────────────────────────────────────────────────
"""The bill run's stages. Billing owns 1, 2, 6 and 7; rating owns 3, 4 and 5.

    1 resolve-subscription  -> SubscriptionContext   billing   (here)
    2 measure-consumption   -> MeasuredUsage         billing   (here)
    3 price-usage           -> PricedLines           rating 🔒
    4 apply-charges         -> ChargedLines          rating 🔒
    5 compute-tax           -> TaxedLines            rating 🔒
    6 assemble-document     -> the stamped bill      billing
    7 post-to-ledger        -> the balanced handoff  billing (emits only)

Stages 3–5 are reached through `apps/billing/rating_seam`, and WHICH function
depends on how many services the account has:

    price_bill(services=…)   every service on the plan, ONE tax pass  ← the run
    price_period(tariff=…)   one service point                        ← B5 GT-1..11

`price_bill` is the run's path. A plan is a BUNDLE (PO ruling 2026-08-11) and
stage 1 hands stage 3 a TUPLE of tariffs, so a bill covering electric + water
is priced in one call whose tax runs once over the combined base — B5 GT-17's
shape (five services, one base of 221.90, one line per authority) and B4.2's
2026-08-11 re-signing, which requires the printed lines to foot against the
printed tax.

    THIS PARAGRAPH USED TO SAY something else, and it was wrong: that stages
    3–5 "are reached through price_period, which runs them as one priced pass".
    True of a single-service account and of every fixture that existed; false
    for the multi-service bill the contracts had described since they were
    written, where no entry point existed at all. DEF-032, and hard-won law 1
    exactly — the sentence described a guarantee nothing provided.

Billing does not import rating's internals and never re-implements its
arithmetic: GT-1..61 exist once.

BR-BIL-037's "only the orchestrator knows the sequence" is why this package
exports the stages and not a `run_all()`. A stage that knew what came next
would be a stage that could be wrong about it.
"""

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-029@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md ·
#         07-billing/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W3 bill-run lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — a package docstring) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · the stages themselves are covered by
#         tests/test_us_bil_029_stages.py
# exceptions: exports the stages and NOT a run_all() — BR-BIL-037 says only the
#         orchestrator knows the sequence, and a stage that knew what came next
#         would be a stage that could be wrong about it
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

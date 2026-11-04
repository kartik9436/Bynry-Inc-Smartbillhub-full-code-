# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-02 (US-RAT-007 configures the percent and its basis) ·
#           EP-RAT-05 (the engine prices it)
#           Screens: S11 step 3's "% of another service" card
# Change:   CR-130-BRC07 — a percentage of another service can be a percentage
#           of its MONEY or of its METER (PO ruling 2026-09-22)
# Rules:    BR-RAT-1030 (NEW — the two bases) · BR-RAT-015 ❄️ SUPERSEDED
#           2026-09-08 by CR-081 · BR-RAT-032 (one price is ONE 0→∞ tier)
# Impacts:  apps/rating/models.py (the column's default) ·
#           apps/rating/pricing/contracts.py (ModelConfig) ·
#           apps/rating/services.py (validation) ·
#           apps/rating/selectors.py (pricing_inputs + the derived basis list) ·
#           apps/rating/pricing/models/percent_of_service.py (the arithmetic)
# ───────────────────────────────────────────────────────
"""The two percent bases, stated ONCE for the whole module.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 money math (B4/CLAUDE.md sensitive
paths), AI-authored under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. Implements signed law, never invents it.

WHY A MODULE OF ITS OWN, WHICH IS TWO CONSTANTS AND A TUPLE
------------------------------------------------------------
Five files need this vocabulary and they sit on opposite sides of the Django
boundary: `models.py` needs it for a column default, the PURE pricing plugin
needs it to branch, and `services`/`selectors` need it to validate and to
publish. A constant written twice is the shape this repo keeps paying for —
`seams.service_bills_from_a_register`'s own note calls a hand-kept second copy
*"the fifteenth copy, and it would go green on the day the seed changed
underneath it"*.

This module imports NOTHING — no Django, no models, not even its own package —
so `apps.rating.models` can read it at app-load time for a column default.

⚠ **CORRECTED 2026-09-30 (gate triage T6) — THE `human_owned.txt` SENTENCE BELOW IS
HISTORY, NOT THE CURRENT STATE, and it was only ever about the OLD path.** This
file, under `pricing/`, IS matched by `06-backend/apps/rating/pricing/**/*.py`.

⚠ **IT LIVES UNDER `pricing/` FOR A REASON THAT IS NOT TIDINESS.** It was
written at `apps/rating/percent_basis.py` first, and **no glob in
`10-scripts/gates/human_owned.txt` matches that path** — so `G7` would have
reported CONFORM over a money-path file that declares itself HUMAN-OWNED. That
is an escape this repo has already paid for four times, each recorded in that
file's own lines (`issue.py`, `decisions.py`, `read_analysis.py`,
`resolution.py`), always with the same sentence: *the file already carried the
marker and the ledger row and no glob here matched it*. A lane may not add
itself to that list — the list's header makes that a PO ruling — but it may
put the file where the existing glob already reaches, and
`06-backend/apps/rating/pricing/**/*.py` reaches here.

WHAT THE TWO VALUES MEAN, IN THE PRODUCT OWNER'S OWN WORDS (2026-09-22)
------------------------------------------------------------------------
    "if water charge is $100, and %age is 80% then sewer cahrge will be $80"
                                                            -> `charge`

    "if Water usage will be 100 gallan %age is 80% then sewer uage will be 80
     gallan = sewer charge will be 80 X { flat rate or tiered rate}"
                                                            -> `usage`

`usage` is what every schedule in the product does today (`CR-081`, PO re-sign
2026-09-08) and is what every existing row is backfilled to BY NAME. `charge`
is the arithmetic this product did until 2026-09-08 and is being put back
BESIDE it as a choice, not in front of it: ❄️ `GT-17` ($36.00), `GT-20`
($54.00), `GT-25` ($27.00) and `GT-26` ($27.00) are untouched.

⚠ **NO SERVICE CODE APPEARS ANYWHERE IN THIS MODULE OR IN ANYTHING THAT READS
IT** — PO ruling 2026-09-22, verbatim: *"dont hard code anything - use logic to
derive it so that it is flexible and handle any scenario."* What a schedule may
take a percentage of is derived from what the tenant has switched on and from
what the chosen basis can actually supply (`selectors.percent_basis_options`).
"""

from __future__ import annotations

#: A percentage of the basis service's metered QUANTITY, priced on THIS
#: schedule's own rate — one 0→∞ block (flat) or a ladder. `CR-081`'s basis and
#: the default for every row that predates `CR-130-BRC07`.
PERCENT_BASIS_USAGE = "usage"

#: A percentage of the basis service's usage-charge DOLLARS. This schedule
#: states no rate of its own and one is REFUSED BY NAME if sent — a percentage
#: of money has no price per gallon behind it.
PERCENT_BASIS_CHARGE = "charge"

#: The whole vocabulary. Anything else is refused; there is no third basis and
#: no silent fallback, because a basis guessed on a money path is a wrong bill
#: that looks right.
PERCENT_BASES: tuple[str, ...] = (PERCENT_BASIS_USAGE, PERCENT_BASIS_CHARGE)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-130-BRC07 §3 (the wire contract, written before either lane built to it)
# generated: 2026-09-22 by the CR-130-BRC07 rating-backend lane (wave A)
# checklist: A✔ B=deferred(no-frontend-half — the frontend reads the same two values off the API, wave B) C✔ D=deferred(no-API-half — pure module) E=deferred(see B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

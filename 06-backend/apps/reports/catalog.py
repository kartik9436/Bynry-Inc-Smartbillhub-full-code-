# ── Trace ──────────────────────────────────────────────
# Story:    US-REP-001 (S44 Report library — the full canned catalog + routing,
#           nothing re-implemented)   Screens: S44
# Rules:    BR-REP-002 (every card opens a READ-MODEL) · BR-REP-003 / BR-REP-005
#           (the remittance and export surfaces are LEDGER-owned — S44 routes,
#           never re-implements) · BR-REP-007 (the canned set includes the six
#           audit-added reports) · BR-REP-021 (the five column-unratified
#           reports render via the GENERIC viewer in v1) · BR-REP-001 (a money
#           report names its date basis) · BR-REP-023 (the access-review report
#           is System Admin + Executive only)
# Tests:    06-backend/tests/test_us_rep_canned_reports.py
# Impacts:  apps/reports/api.py (serves it at GET /reports) ·
#           07-frontend/src/features/reports/ReportLibraryPage.tsx (renders it)
# ───────────────────────────────────────────────────────
"""THE S44 CATALOGUE — every report this product knows about, and its state.

US-REP-001 §5 names this a *"canned-report registry (code-defined catalog; no
tenant table)"*, and that is what this file is: one Python tuple, ratified from
A14 §Report library plus the prototype card set plus BR-REP-007's six additions.

⚠⚠ **SUPERSEDED 2026-09-26 — THERE IS A TENANT TABLE NOW, AND THIS TUPLE IS NOT
IT (`CR-142-BRC07` Phase 0).** `report_definitions` holds **46** platform rows,
`report_categories` holds **6 groups and 19 sub-groups**, and both are seeded by
`apps/reports/migrations/0003_seed_catalogue.py`. The sentence above is quoted
from `US-REP-001` and was true when it was written; it is kept rather than
edited because it is a QUOTATION, and the amendment is here.

⚠ **THAT PARAGRAPH DESCRIBED THE OPEN WORLD UNTIL 2026-09-27 AND IS REPLACED.**
It read *"`GET /reports` still serves `catalog_payload()` — this tuple's 23
cards in three groups"*, and named `P1.1` as the switch that had not happened.
`P1.1` LANDED on 2026-09-26: `apps/reports/api.py::report_library` calls
`catalogue_read.catalogue_payload()` over the 46 seeded `report_definitions`
rows, and the tuple it described was deleted the next day by `P0.7`.

**IT IS WORTH THE SPACE BECAUSE IT WAS WRONG IN THE MOST EXPENSIVE DIRECTION.**
A lane reading it would have believed the catalogue still came from this file
and gone looking here for a card that is a row in a table — CLAUDE.md's own
prime-directive warning that *a closed question's body goes on describing the
open world, and the body is what a lane actually reads*, in a module docstring
rather than in a register row. Nothing re-checks a paragraph; what found this
one was `tests/test_rep_p07_maps_deleted.py` grepping for a symbol it had just
deleted, which is the habit rather than the tool.

**SO: DO NOT ADD A CARD HERE.** A new report is a row in `report_definitions`.
This tuple is frozen, it is read by exactly one function
(`apps/reports/api.py:report_library`), and `P1.1` deletes it.

════════════════════════════════════════════════════════════════════════════
WHY THE CATALOGUE IS SERVED BY THE SERVER AND NOT HARDCODED IN THE SCREEN
════════════════════════════════════════════════════════════════════════════
The registry is code-defined, so a client copy would compile. It is served
anyway, and the reason is the ONE thing a client cannot know:

    WHICH OF THESE REPORTS THIS DEPLOYMENT CAN ACTUALLY PRODUCE, AND WHY NOT.

A card grid drawn from a client-side list shows twenty-three confident tiles and
discovers on click that thirteen of them answer nothing. Worse, the by-premises
report answers `available: false` **and is CORRECT to** — no journal line
records a premises (US-LED-002 is unbuilt) — and a client list has no way to say
so. Every card here therefore carries `available` and, when false, a `reason`
the screen renders as a sentence: *"This report needs a dimension the ledger
does not record yet."* An honest refusal beats a confident empty report, which
is the whole posture S60 already ships.

This makes `GET /reports` an endpoint no signed document contracts. **REPORTED**
— A11 gives `GET /reports/{key}`, 11b §2.11 gives `/reports/schedules`,
`/history`, `/datasets` and `/custom`, and none of the five is an index. The
posture it takes is BR-REP-006's own (*a vocabulary is read LIVE, never
hardcoded into a client*), which `apps/reports/api.py` already cites when it
makes an unknown key enumerate the served set.

════════════════════════════════════════════════════════════════════════════
FOUR KINDS OF CARD, AND THE ROUTING RULE THAT SEPARATES THEM
════════════════════════════════════════════════════════════════════════════
`VIEWER`   this module answers it at `GET /reports/{key}` and S46 renders it.
`ROUTE`    another module owns the STORY and the surface. BR-REP-003/BR-REP-005
           are explicit: S44 **routes** to S56/S59/S60/S41 and reports never
           re-implements them — two implementations of a trial balance is two
           trial balances. The same rule sends the user-activity card to S61
           (BR-REP-021: it IS the audit dataset, deduped) and the rate-change
           card to S11's own history list.
`GENERIC`  BR-REP-021: the five column-unratified reports (disconnect &
           reconnect, meter inventory, PUC quarterly, rate-change history,
           user-activity) render through the GENERIC viewer when their data
           exists. Where it does not, the card is unavailable with its reason —
           never an invented column set.
`ABSENT`   the report is real, the rule is ratified, and the data it needs is
           not in this product yet. The card states which read is missing.

Nothing here is a 501 and nothing is a dead link: an unavailable card does not
open a viewer at all, because a viewer that opens onto a reason is a screen
pretending to be a report.
"""

# ── The report keys this module answers ─────────────────────────────────────
# The two ledger-owned keys keep the strings `apps/reports/api.py` already
# registered (derived from US-LED-009/010 §4's export-filename fixtures — see
# that file's docstring). The new ones follow the same grammar: the report's
# name, snake_cased, as it appears in its own IS-11 filename segment.
KEY_ACCOUNT_LEDGER = "account_ledger"
KEY_BY_PREMISES = "by_premises"
KEY_AR_AGING = "ar_aging"
KEY_BILLING_REGISTER = "billing_register"
KEY_REVENUE_BY_SERVICE = "revenue_by_service_rate"
KEY_PAYMENTS_BY_METHOD = "payments_by_method"

# ── The `journal_lines` dataset's own four (2026-09-26, lane DS-LEDGER) ─────
# The strings are `migrations/0003_seed_catalogue.py`'s, verbatim, because the
# seeded definition row is what `runner.resolve()` looks the key up by — a
# constant here that disagreed with the seed would refuse every run with
# `definition not found` while reading perfectly in this file.
#: R15 · Finance › Ledger · drawn p055. Also opens S56.
KEY_TRIAL_BALANCE = "trial_balance"
#: R16 · Finance › Ledger · drawn p056. The one that was wholly dark.
KEY_JOURNAL_EXPORT = "journal_export"
#: R18 · Finance › Income · drawn p057. Also opens S41.
KEY_TAX_REMITTANCE = "tax_remittance"
#: R21 · Finance › Ledger · drawn p058.
KEY_CLOSE_PACK = "close_pack"

GROUP_FINANCIAL = "financial"
GROUP_OPERATIONS = "operations"
GROUP_COMPLIANCE = "compliance"

KIND_VIEWER = "viewer"
KIND_ROUTE = "route"
KIND_GENERIC = "generic"
KIND_ABSENT = "absent"

#: BR-REP-001's two labels. A card whose `basis` is None carries no money and
#: therefore names no basis — BR-REP-001's scope is money numbers (US-REP-008 §1
#: says so in as many words).
BASIS_POSTING = "posting"
BASIS_CLEARING = "clearing"


# ⚠ `ReportCard`, `CATALOG` AND `catalog_payload()` STOOD HERE UNTIL 2026-09-27
# AND ARE DELETED (`CR-142-BRC07` `P0.7`, lane REP-P2-TAIL). They were three of
# the six hand-typed maps the task names, and they are removed now rather than
# in Phase 0 because until `P1.1` landed they were still the catalogue.
#
# **THEY HAD NO READER LEFT, AND THAT WAS MEASURED RATHER THAN ASSUMED.**
# `apps/reports/api.py::report_library` served `catalog_payload()` until
# 2026-09-26; it now calls `catalogue_read.catalogue_payload()` over the 46
# seeded `report_definitions` rows. A grep of `06-backend`, `10-scripts` and
# `07-frontend` for `catalog_payload`, `ReportCard` and this file's `CATALOG`
# returned this file and nothing else.
#
# ⚠ **WHAT IS KEPT, AND WHY IT IS NOT FURNITURE.** The `KEY_*`, `GROUP_*`,
# `KIND_*` and `BASIS_*` constants above stay: 69 live citations across
# `apps/` and `tests/` read them, and they are a VOCABULARY rather than a map —
# one name for one string, with nothing per-report to keep in step. The six
# maps `P0.7` names are the per-report tables, and a tuple of 23 cards was the
# largest of them.
#
# **DO NOT PUT A CARD BACK HERE.** A new report is a row in
# `report_definitions` (`apps/reports/models.py`), seeded by
# `migrations/0003_seed_catalogue.py` and read by `catalogue_read.py`.


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-REP-001@c6c35b2 (04-docs/05-modules/12-reports/06-epics/EP-REP-01-report-center.md §US-REP-001 · 12-reports/02-business-rules.md BR-REP-002/003/005/007/021/023 · 04-docs/01-spec/14-reports-and-exports.md §Report library · 05-prototype/UtilityBilling.html lines 4088-4113)
# screens: S44
# generated: 2026-08-16 by story-coder (reports lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_us_rep_canned_reports.py asserted the catalogue before this module existed and failed on ImportError. ruff✔ black✔ pytest✔ run_gates✔
# exceptions: (1) `GET /reports` — the catalogue index — IS NOT CONTRACTED by A11 or 11b and is minted here. REPORTED. The reason it is served rather than compiled into the client is the one fact a client cannot know: which reports THIS deployment can produce and why not · (2) THIRTEEN of the TWENTY-THREE cards ship `available: false`, each naming the read that would close it. None is a 501 and none opens a viewer — a viewer that opens onto a reason is a screen pretending to be a report · (3) the two ledger-owned keys keep the strings `apps/reports/api.py` registered on 2026-08-11, which were derived from US-LED-009/010 §4 export-filename fixtures and are still unratified
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

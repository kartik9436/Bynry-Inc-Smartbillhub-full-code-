# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 1 · P1.1 (the catalogue comes out of the table)
#           · P1.2 (the `q` · `group` · `service` filters, read SERVER-SIDE)
#           · P1.8 (the tenant's enabled services ride on the SAME answer).
#           Screens: S44
# Rules:    BR-REP-006 (a vocabulary is read LIVE, never hardcoded into a
#           client) · BR-REP-019 (origin is three closed values) · BR-SHL-025
#           (a control this deployment cannot honour is STATED, not hidden) ·
#           NFR-3 (universal server pagination — no endpoint is exempt) ·
#           NFR-5 (no hard caps anywhere) · CLAUDE.md hard rule 1 (the tenant
#           is named in the queryset as well as in the policy) · B14 rule 31
#           (no database id is ever the visible value of a field) · rule 33
#           (a FACT is six words)
# Tests:    06-backend/tests/test_rep_p1_catalogue.py
# Impacts:  apps/reports/api.py (`report_library` serves this) ·
#           apps/reports/catalog.py — ⚠ this line named the function this read
#           replaced until 2026-09-27; `CATALOG`, `ReportCard` and
#           `catalog_payload()` were DELETED that day (`P0.7`, lane
#           REP-P2-TAIL) and the citation is amended rather than left pointing
#           at a symbol that no longer exists. `catalog.py` now holds the KEY_*
#           / GROUP_* / KIND_* / BASIS_* vocabulary and nothing else ·
#           07-frontend/src/features/reports/ReportLibraryPage.tsx
# ───────────────────────────────────────────────────────
"""THE CATALOGUE, OUT OF `report_definitions` AND `report_categories`.

`P0.6` seeded forty-six definitions and twenty-five categories and deliberately
switched nothing over to read them: `GET /reports` went on serving
`apps/reports/catalog.py`'s frozen tuple of twenty-three. This file is the
switch, and it is `P1.1` rather than `P0.x` for a reason that file states in its
own words — the screen used to name every card through
`t("reports.card.<key>.name")`, so serving the forty-six without the screen
would have drawn six unlabelled headings and twenty-three raw snake_case keys.

WHERE A REPORT'S NAME COMES FROM NOW, AND WHY NOT FROM A LOCALE CATALOGUE
────────────────────────────────────────────────────────────────────────
**The row.** The brief puts it in one sentence on p21: *"The server sends no
title — the name is an i18n key today, and becomes `report_definitions.name` at
`P0.1`."* And p5 says what that buys: *"Until a report's name comes out of a
row, no utility can ever author one"*, because a utility cannot edit our locale
catalogues. A name that lives in eleven JSON files is a name only we can give.

So this serves `name`, and the precedence is the one the tables already declare:

    report_tenant_settings.name_override      what THIS utility calls it
    report_definitions.name_i18n[locale]      a translation, when one exists
    report_definitions.name                   what we called it

⚠ **`name_i18n` IS EMPTY ON ALL FORTY-SIX ROWS AND THAT IS NOT AN OVERSIGHT.**
B14 rule 35: a catalogue is written in its own language, never a mechanical
translation of English. Eleven languages × (46 names + 6 groups + 19 sub-groups)
is 506 strings and not one of them is a lane's to author — `reports/0003` says
so in its own docstring and declines, and this file declines for the same
reason. The column is the slot they land in when somebody who speaks those
languages writes them.

⚠ **NINE NAMES ARE ALREADY TRANSLATED AND NOTHING HERE THROWS THEM AWAY.**
`reports.card.<key>.name` exists in all eleven catalogues for the twenty-three
old cards, and nine of those keys survive into the forty-six — `ar_aging`,
`account_ledger`, `billing_register`, `disconnect_reconnect`,
`payments_by_method`, `rate_change_history`, `read_completeness`,
`revenue_by_service_rate`, `trial_balance`. The SCREEN prefers that authored
copy for a PLATFORM card and falls back to the served name; a tenant's own row
always renders its own name, so a utility naming its report `ar_aging` gets its
name and not ours. That is not translating anything — it is moving copy a
person already wrote, and it is why this switch costs a Japanese clerk nothing.

WHAT MAKES A CARD AVAILABLE
───────────────────────────
Whether its dataset can be executed today. Six of the nine datasets have no
query yet (`P0.5`'s own note), so a definition on one of them is a card that
opens nothing and says so — the posture `catalog.py` already shipped and which
`US-REP-001 TC-4` asserts. **An empty table is a claim**, and *"nobody is 90+
days overdue"* is a different sentence from *"this product cannot tell you"*.

⚠ **THE REASON SENTENCE IS NOW SIX WORDS AND IT USED TO BE A PARAGRAPH.** B14
rule 33 caps a FACT at six and puts RATIONALE at ZERO words on screen. The
twenty-three-card catalogue rendered sentences like *"The trend needs twelve
months of billed totals and nothing publishes them a month at a time"* on the
face of a card — which is rationale, and rule 33 says it is REMOVED rather than
shortened. Every unavailable card now carries one key,
`reports.library.unavailableGeneric`, which already reads *"This report cannot
be produced yet."* in all eleven catalogues: six words exactly, authored in each
language, and no new string anywhere.

ORIGIN IS THREE VALUES AND THE SUB-TAB IS TWO, AND THE MAP IS WRITTEN OUT
────────────────────────────────────────────────────────────────────────
`BR-REP-019` closes origin at three — `built_in` · `mine` · `shared` — and the
dropdown register marks it SIGNED. The screen shows **two** sub-tabs, Standard
and Custom, and the PO's ruling is that origin is *not* a filter at all: *"a
filter dropdown hides that you can author a report at all."* So:

    sub-tab Standard  →  origin built_in   →  tenant_id IS NULL   (ours)
    sub-tab Custom    →  origin mine|shared →  tenant_id = me      (theirs)

`mine` and `shared` are one sub-tab because both are this utility's own work;
the difference between them is an OWNER column inside the Custom list (1·2B,
p22) and never a different place to look. Serving `origin` per card is what
lets that column exist in Phase 5 without a second read.

PAGING, AND WHY THE DEFAULT PAGE HOLDS THE WHOLE CATALOGUE
──────────────────────────────────────────────────────────
`NFR-3` admits no exceptions and the drawing puts a pager under the grid, so
this pages. The drawn *"Rows per page 20 · 1–20 of 45 · Page 1 of 3"* is a
drawn NUMBER, and B14 rule 37 makes every number in a wireframe an illustration
— so the default is the product's own `DEFAULT_PAGE_SIZE`, **50**, which is one
of B14 rule 16's five ratified sizes and holds all forty-five grid cards on one
page today. The control is real, the machinery is real, and nothing is cut.
`NFR-5`: there is no maximum here, only a page.
"""

from __future__ import annotations

from typing import Any, Iterable

#: B14 rule 16's ratified set. Mirrored from the front end's `PAGE_SIZES`
#: rather than re-chosen: a sixth size is a product decision, not a read's.
PAGE_SIZES: tuple[int, ...] = (50, 100, 200, 500, 1000)
DEFAULT_PAGE_SIZE = 50

#: The sub-tab vocabulary. Two values, because the SCREEN has two sub-tabs —
#: see the module docstring for the map onto `BR-REP-019`'s three origins.
ORIGIN_STANDARD = "standard"
ORIGIN_CUSTOM = "custom"
SUB_TABS: tuple[str, ...] = (ORIGIN_STANDARD, ORIGIN_CUSTOM)

#: `BR-REP-019`'s three, served per card.
ORIGIN_BUILT_IN = "built_in"
ORIGIN_MINE = "mine"
ORIGIN_SHARED = "shared"

#: A definition another module already owns the SCREEN for. `BR-REP-003` /
#: `BR-REP-005`: reports ROUTES and never re-implements — two implementations of
#: a trial balance is two trial balances.
#:
#: ⚠ **FIVE, WHERE `catalog.py` HAD SIX, AND THE SIXTH IS A REAL LOSS THAT IS
#: FILED RATHER THAN PAPERED OVER.** The old tuple routed a `by_premises` card
#: to `S60`, and the forty-six hold no `by_premises` row — so the catalogue
#: stops being a door to a screen that is live, routed and tested. It is not
#: orphaned (`AppShell.tsx:317` lists `/reports/by-premises` as a nav child, so
#: the sidebar still opens it) and a forty-seventh platform row is the seed's to
#: add and not this read's to invent. `DEF-REP-6816`.
#:
#: The other five moved keys with the seed and are mapped here by their NEW key:
#: `sales_tax_remittance` → `tax_remittance`, `user_activity_audit` →
#: `audit_trail`. Same report, same screen, different row.
ROUTE_SCREENS: dict[str, str] = {
    "trial_balance": "S56",
    "account_ledger": "S59",
    "tax_remittance": "S41",
    "audit_trail": "S61",
    "rate_change_history": "S11",
}

#: The badge on the card's first line — the drawing's own eyebrow. It is the
#: SUB-GROUP's name (p20: every card reads `PAYMENTS`, `ARREARS`, `RECOVERY`
#: above its title), so there is no badge vocabulary to maintain and no seventh
#: hand-typed map. A definition with no sub-group falls back to its group.

#: One key, six words, eleven languages, already authored. See the docstring.
REASON_NOT_PRODUCIBLE = "report_dataset_has_no_query"

#: ⚠ **THE SECOND REASON, AND IT IS A DIFFERENT FACT TO A DIFFERENT READER**
#: (lane REP-WIRE, 2026-09-27). `report_dataset_has_no_query` means *the engine
#: for this whole dataset is not built* and waits for a dataset lane.
#: `report_grain_is_not_this_dataset_grain` means the engine IS built, is
#: measured and serves its siblings, and declines THIS definition because the
#: drawing asks a different question of the data — which waits for a ruling
#: about which dataset the report belongs on, or for a read model at its grain.
#: Twenty-eight of the forty-six are in the second state today and only that
#: second sentence sends the next reader anywhere useful.
#:
#: ⚠ **NO NEW LOCALE KEY IS NEEDED AND THAT WAS CHECKED, NOT ASSUMED.**
#: `ReportLibraryPage` renders `reports.library.reason.<code>` with
#: `reports.library.unavailableGeneric` as its `defaultValue`, so a code with no
#: catalogue entry reads *"This report cannot be produced yet"* in all eleven
#: languages — which is true of both states. A sentence naming the grain would
#: be RATIONALE on screen and B14 rule 33 puts that at zero words.
REASON_GRAIN_NOT_SERVED = "report_grain_is_not_this_dataset_grain"


def _viewer_keys() -> frozenset[str]:
    """The PER-REPORT viewers — four of them, shipped and measured.

    ⚠ **THIS DOCSTRING USED TO CLAIM IT READ `runner.queries_for` AND IT NEVER
    DID (`DEF-REP-6866`).** It said *"so this file cannot drift from what the
    viewer will actually do when the card is clicked"*, and it returned
    `frozenset(queries.VIEWERS)` — half the answer. Hard-won law 1, word for
    word: a comment claiming a guarantee is not the guarantee.

    **What it cost:** `runner.queries_for` has TWO lookups — the per-report map,
    then the DATASET's own query, which is the brief's whole arithmetic (*"46
    reports sit on 9 datasets"*). A tenant-authored report has a new key by
    construction, so it is in neither map, and EVERY custom report was drawn as
    a dead card reading *"This report cannot be produced yet"* over a report the
    runner would have served perfectly. Correct while every row was one of ours;
    wrong the first day a utility saved one.

    It is still used — for the `kind` a card carries, which distinguishes a
    report with its OWN viewer from one served by its dataset. Availability now
    asks `runner.queries_for`, which is what the old sentence promised.
    """
    from apps.reports import queries

    return frozenset(queries.VIEWERS)


def _enabled_service_codes(vocabularies: dict[str, Any]) -> frozenset[str]:
    """The tenant's own enabled services, off the answer we are already giving.

    `P1.8` in one line: `parameter_vocabularies()` already puts the enabled set
    on this very response for the S46 parameter bar, so the catalogue's service
    filter reads it from there. **No second request and no second source** —
    two reads of one vocabulary is the drift `BR-REP-006` exists to prevent.
    """
    services = vocabularies.get("services") or []
    return frozenset(
        str(row.get("code")) for row in services if isinstance(row, dict) and row.get("code")
    )


def _offered_for(service_codes: Iterable[str], enabled: frozenset[str]) -> bool:
    """Whether a definition is offered to a tenant with THIS service set.

    EMPTY means every service, which is not the same as "all eleven": a report
    that names no service is about the utility rather than about one of its
    products, and a water-only tenant must still see its own trial balance.

    A report that names services is offered when the tenant has AT LEAST ONE of
    them. That is `P0.3`'s outcome — *"a water utility stops being shown gas
    reports"* — and the ANY rather than ALL is deliberate: a combined
    electric-and-gas report is worth showing to a utility that sells one of the
    two, with the half it does not sell simply empty.
    """
    names = [str(code) for code in service_codes if str(code)]
    if not names:
        return True
    return any(code in enabled for code in names)


def _matches_query(card: dict[str, Any], needle: str) -> bool:
    """`?q=` — the search the drawing puts in the toolbar.

    ⚠ **IT SEARCHES THE NAME A PERSON CAN SEE, AND THE GROUP THEY CAN SEE.**
    Not the key: a clerk typing *ageing* is looking for the card that says
    Ageing, and matching `ar_aging` would also hand them every card whose
    snake_case key happens to contain their letters — which is B14 rule 31's
    subject one step along (a database-shaped string is not the value of a
    field, and it is not searchable text either).
    """
    haystack = " ".join(
        str(card.get(field) or "")
        for field in ("name", "group_name", "sub_group_name")
    ).casefold()
    return needle.casefold() in haystack


def _page_size(raw: Any) -> int:
    """One of B14 rule 16's five, or the default. An unknown value FALLS BACK.

    `BR-SHL-024`: an unknown preference reads as absent. A stale bookmark
    carrying `per=25` gets the catalogue rather than a 422, which is the same
    posture `f.period` takes on the dashboard and for the same reason — a
    screen that refuses a bookmark is a locked front door.
    """
    try:
        value = int(str(raw))
    except (TypeError, ValueError):
        return DEFAULT_PAGE_SIZE
    return value if value in PAGE_SIZES else DEFAULT_PAGE_SIZE


def _page_number(raw: Any) -> int:
    try:
        value = int(str(raw))
    except (TypeError, ValueError):
        return 1
    return value if value >= 1 else 1


def _origin_of(row: Any, user_id: Any) -> str:
    """`BR-REP-019`'s three values for one row."""
    if row.tenant_id is None:
        return ORIGIN_BUILT_IN
    owner = getattr(row, "owner_user_id", None)
    if owner is not None and user_id is not None and str(owner) == str(user_id):
        return ORIGIN_MINE
    return ORIGIN_SHARED


def _categories(tenant_id: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The groups with their sub-groups, in seeded order, plus a code index.

    The tenant's own categories are read beside the platform's — a utility that
    inserts *Board pack* sees it here with no release, which is `P0.2`'s own
    outcome and the reason this is a table rather than three constants.
    """
    from django.db.models import Q

    from apps.reports.models import ReportCategory

    rows = list(
        ReportCategory.objects.filter(Q(tenant_id=tenant_id) | Q(tenant_id=None)).order_by(
            "sort_order", "code"
        )
    )
    # A tenant row outranks the platform row it shadows, exactly as
    # `runner.resolve()` ranks definitions.
    by_code: dict[str, Any] = {}
    for row in rows:
        if row.code not in by_code or row.tenant_id is not None:
            by_code[row.code] = row

    groups: list[dict[str, Any]] = []
    for row in sorted(by_code.values(), key=lambda r: (r.sort_order, r.code)):
        if row.parent_code is not None:
            continue
        subs = [
            {"code": sub.code, "name": sub.name, "name_i18n": dict(sub.name_i18n or {})}
            for sub in sorted(by_code.values(), key=lambda r: (r.sort_order, r.code))
            if sub.parent_code == row.code
        ]
        groups.append(
            {
                "code": row.code,
                "name": row.name,
                "name_i18n": dict(row.name_i18n or {}),
                "sub_groups": subs,
            }
        )
    return groups, by_code


def catalogue_payload(
    params: Any = None,
    *,
    vocabularies: dict[str, Any] | None = None,
    user_id: Any = None,
    role: Any = None,
) -> dict[str, Any]:
    """`GET /reports` — the S44 catalogue, filtered and paged SERVER-SIDE.

    ⚠ **EVERY FILTER IS READ HERE AND NONE IS READ IN THE SCREEN.** `P1.2`'s
    own words, and the reason is `NFR-3` rather than tidiness: a screen that
    filters an array it was handed has to be handed the whole array, and the
    endpoint it asks is then one a tenant can outgrow. Filtering in the read is
    what makes the page underneath it honest.
    """
    from django.db.models import Q

    from apps.reports import role_gate
    from apps.reports.models import ReportDefinition, ReportTenantSetting
    from core import tenancy as core_tenancy

    mapping = _as_mapping(params)
    tenant_id = core_tenancy.current_tenant_id()
    vocabularies = vocabularies or {}
    enabled = _enabled_service_codes(vocabularies)
    # Imported here rather than at module scope: `runner` imports `slicers`,
    # which imports `datasets`, and a top-level cycle through this file is the
    # reason `_viewer_keys` was lazy in the first place.
    from apps.reports import queries as reports_queries
    from apps.reports import runner as reports_runner

    viewer_keys = _viewer_keys()

    groups, by_code = _categories(tenant_id)
    group_codes = [group["code"] for group in groups]

    overlays = {
        setting.definition_id: setting
        for setting in ReportTenantSetting.objects.filter(tenant_id=tenant_id)
    }

    rows = list(
        ReportDefinition.objects.filter(Q(tenant_id=tenant_id) | Q(tenant_id=None)).order_by(
            "group_code", "sub_group_code", "key"
        )
    )
    # Copy-on-write: a tenant's row REPLACES the platform row it copied, by key.
    by_key: dict[str, Any] = {}
    for row in rows:
        if row.key not in by_key or row.tenant_id is not None:
            by_key[row.key] = row

    cards: list[dict[str, Any]] = []
    for row in by_key.values():
        # ── `P5.7` · `BR-REP-019` · PRIVATE BY DEFAULT, ON THE READ ────────
        # ⚠ **THIS FILE READ `visibility` ZERO TIMES UNTIL 2026-09-27
        # (`DEF-REP-6864`).** The column landed in `P0.1`, the CHECK constraint
        # with it, the control on 2·4 in `P5.4` — and nothing ever filtered on
        # it, so a half-finished report appeared on every colleague's catalogue
        # the moment it was saved, which is the exact thing the ruling exists to
        # prevent. Found by signing a second user in and looking (law 6); no
        # test could see it, because every test had one user.
        #
        # ⚠ **RLS CANNOT DO THIS ONE, AND IT IS WORTH SAYING WHY.** §8.1's
        # sentence — *"row-level security does that work, not a second set of
        # rules nobody maintains"* — is about the TENANT boundary, and it holds:
        # `reports/0002` keeps one utility's rows away from another's, and
        # `10-scripts/rep_p5_isolation_and_savepoint_proof.py` proves it three
        # ways on real PostgreSQL. **Visibility is a boundary INSIDE one
        # tenant**, between two colleagues who share a database session's
        # `app.tenant_id`, and the policy has no notion of a user at all. Making
        # it one would mean a second GUC (`app.user_id`) set on every request
        # and read by every policy — a real option, and a platform-wide decision
        # rather than this lane's. It is recorded on `DEF-REP-6864` so the
        # choice is made deliberately rather than inherited.
        if (
            row.tenant_id is not None
            and getattr(row, "visibility", None) == "private"
            and str(getattr(row, "owner_user_id", "") or "") != str(user_id or "")
        ):
            continue
        # ── `P5.9` · `BR-REP-023` · THE ROLE FLOOR, ON THE READ ───────────
        # ⚠ **ABSENT, NOT GREYED, AND NOT "UNAVAILABLE WITH A REASON".** The
        # two neighbours below take the same posture for the tenant overlay and
        # for a service the utility does not have, and it is B14 rule 33's:
        # RATIONALE is zero words on screen, so a Billing Clerk is not shown a
        # card explaining that the card is not theirs. Greying it would also be
        # hard-won law 2's mirror — a live control that refuses — and the list
        # of restricted reports is itself worth not publishing.
        #
        # ⚠ **THE CARD AND THE CLICK MUST AGREE, WHICH IS WHY `api.report()`
        # ASKS THE SAME FUNCTION.** A catalogue that hides a report while its
        # address still serves it is a door left open beside a door painted
        # over; a viewer that refuses a report the catalogue drew is the defect
        # in the other direction. One function, two call sites.
        if not role_gate.may_run(getattr(row, "min_role", None), role):
            continue
        overlay = overlays.get(row.id)
        if overlay is not None and not overlay.enabled:
            # `P0.3`'s whole purpose: the utility switched this one off. It is
            # not "unavailable with a reason" — it is not in the catalogue.
            continue
        if not _offered_for(row.service_codes or (), enabled):
            continue

        filters = dict(row.filters or {})
        if filters.get("renders_as") == "tab":
            # p20 annotation ①: *"45, not 46 — the forty-sixth answer is the
            # Dashboard TAB, which is in the strip rather than in the grid. A
            # card pointing at a sibling tab is noise."* The row stays in the
            # table and the runner still resolves it; the GRID does not draw it.
            continue

        group = by_code.get(row.group_code)
        sub_group = by_code.get(row.sub_group_code) if row.sub_group_code else None
        # ⚠ **ONE FUNCTION, ASKED ONCE — `DEF-REP-6866`.** The catalogue and
        # the viewer must agree about whether a card opens onto anything, and
        # the only way to guarantee that is to ask the code the viewer runs.
        # `queries_for` falls back to the DATASET's query, which is what turns
        # a utility's own report from a dead card into a live one.
        # ⚠ **A QUERY IS NOT AN ANSWER, AND UNTIL 2026-09-27 THIS LINE SAID IT
        # WAS.** `queries_for` reports whether the DATASET has an engine; a
        # dataset query may still decline one DEFINITION by name, and twenty-
        # eight of the forty-six do. When the last six datasets were registered
        # this expression made every card in the catalogue claim to be
        # producible, and twenty-eight of them refused the instant they were
        # clicked — a viewer that opens onto a reason is a screen pretending to
        # be a report. Both questions are asked now, of the same functions the
        # viewer runs, so the card and the click cannot disagree.
        grain_refusal = reports_queries.definition_refusal(row.key, row.dataset)
        available = row.key in ROUTE_SCREENS or (
            reports_runner.queries_for(row.key, row.dataset) is not None
            and grain_refusal is None
        )
        cards.append(
            {
                "key": row.key,
                # The name a person reads, already resolved. The screen never
                # re-derives this; see the docstring for the precedence.
                "name": (overlay.name_override if overlay and overlay.name_override else row.name),
                "name_overridden": bool(overlay and overlay.name_override),
                "name_i18n": dict(row.name_i18n or {}),
                "group": row.group_code,
                "group_name": group.name if group else row.group_code,
                "sub_group": row.sub_group_code,
                # The drawing's eyebrow is the SUB-GROUP's name, so there is no
                # badge vocabulary to keep.
                "badge": (sub_group.name if sub_group else (group.name if group else "")),
                "origin": _origin_of(row, user_id),
                "available": available,
                # ⚠ **`kind` IS DERIVED THE SAME WAY `available` IS, AND THE
                # SCREEN READS BOTH** (`DEF-REP-6866`). `ReportLibraryPage`
                # draws a LINK only for `kind === "viewer" && available`, so a
                # card left at `absent` is a dead card however available it
                # says it is — which is how a utility's own report stayed
                # unclickable after `available` was corrected. Two derivations
                # of one fact is how they came to disagree; there is one now.
                "kind": (
                    "route"
                    if row.key in ROUTE_SCREENS
                    else "viewer"
                    if available
                    else "absent"
                ),
                "routes_to_screen": ROUTE_SCREENS.get(row.key),
                "basis": filters.get("basis"),
                "basis_label": filters.get("basis_label"),
                "reason_code": (
                    None
                    if available
                    else (
                        REASON_GRAIN_NOT_SERVED
                        if grain_refusal is not None
                        else REASON_NOT_PRODUCIBLE
                    )
                ),
                # Engineering prose for the log and the tooltip; the SENTENCE a
                # person reads is the screen's, keyed on `reason_code` (TD-16).
                "reason_detail": (
                    None
                    if available
                    else (grain_refusal or f"dataset {row.dataset!r} has no query yet")
                ),
                "service_codes": list(row.service_codes or ()),
                "pinned": bool(overlay.pinned) if overlay else False,
            }
        )

    total = len(cards)
    available_count = sum(1 for card in cards if card["available"])

    # ── the three filters, server-side (P1.2) ──────────────────────────────
    #
    # ⚠ **ORDER MATTERS AND IT IS NOT THE ORDER THE TASK TABLE LISTS THEM IN.**
    # The three FILTERS narrow first; the SUB-TAB is counted over what they
    # left, and only then does it cut. The first draft counted the sub-tabs
    # before the filters, so a search for *ageing* showing one card left the
    # strip reading `Standard · 45` — a tab promising forty-five over a grid
    # holding one. Caught by this file's own case, which was written from what
    # the screen should say rather than from what the code did.
    group_filter = str(mapping.get("group") or "").strip()
    if group_filter:
        cards = [card for card in cards if card["group"] == group_filter]

    service_filter = str(mapping.get("service") or "").strip()
    if service_filter:
        # A card offered for EVERY service stays in a filtered list: the filter
        # asks "what can I run for water", and a report that is not about a
        # service at all is runnable for every one of them.
        cards = [
            card
            for card in cards
            if not card["service_codes"] or service_filter in card["service_codes"]
        ]

    needle = str(mapping.get("q") or "").strip()
    if needle:
        cards = [card for card in cards if _matches_query(card, needle)]

    # ⚠ **BOTH SUB-TAB COUNTS ARE SERVED, NOT JUST THE ACTIVE ONE, AND CALLOUT
    # ④ IS THE WHOLE REASON.** *"Custom reads 0 on day one and that is the
    # point — an empty sub-tab is how a clerk learns they can author a
    # report."* A strip that only counts the tab you are standing on reads
    # `Standard · 45` beside a bare `Custom`, and the clerk learns nothing
    # without clicking the thing that would teach them. Found by looking at the
    # running screen, which is the only check in this repo that reads it.
    origin_counts = {
        ORIGIN_STANDARD: sum(1 for card in cards if card["origin"] == ORIGIN_BUILT_IN),
        ORIGIN_CUSTOM: sum(
            1 for card in cards if card["origin"] in (ORIGIN_MINE, ORIGIN_SHARED)
        ),
    }

    sub_tab = str(mapping.get("origin") or ORIGIN_STANDARD)
    if sub_tab not in SUB_TABS:
        sub_tab = ORIGIN_STANDARD
    wanted = (
        (ORIGIN_BUILT_IN,) if sub_tab == ORIGIN_STANDARD else (ORIGIN_MINE, ORIGIN_SHARED)
    )
    cards = [card for card in cards if card["origin"] in wanted]

    count = len(cards)

    # ── the page (NFR-3) ───────────────────────────────────────────────────
    per = _page_size(mapping.get("per"))
    page = _page_number(mapping.get("page"))
    pages = max(1, -(-count // per))  # ceil, without float
    page = min(page, pages)
    start = (page - 1) * per
    paged = cards[start : start + per]

    # Only the groups that have something in them (1·2B annotation ④) — a
    # heading over nothing is furniture, and after a filter most of six are.
    drawn = {card["group"] for card in paged}
    return {
        "groups": [group for group in groups if group["code"] in drawn],
        # ⚠ **THE SHAPE OF THE CATALOGUE, NOT OF THIS PAGE.** p20 callout ① and
        # a defect found by looking rather than by a test: the screen used to
        # count sub-groups from `groups`, which holds only the groups the
        # CURRENT page draws — so the Custom sub-tab, which draws none, read
        # *"45 reports · 6 groups · 0 sub-groups"*. The catalogue still has
        # nineteen whichever sub-tab you are on.
        "group_total": len(groups),
        "sub_group_total": sum(len(group["sub_groups"]) for group in groups),
        # The whole vocabulary for the group filter's own dropdown, which must
        # offer every group and not only the ones this page happens to show.
        "group_options": [
            {"code": group["code"], "name": group["name"], "name_i18n": group["name_i18n"]}
            for group in groups
            if group["code"] in group_codes
        ],
        "cards": paged,
        # `available`/`total` describe the CATALOGUE and never the page: the
        # sub-line states the shape of the catalogue (p20 annotation ①), and a
        # roll-up that described a page would describe the pager instead.
        "available": available_count,
        "total": total,
        "count": count,
        "page": page,
        "per": per,
        "pages": pages,
        "origin": sub_tab,
        "origin_counts": origin_counts,
        "q": needle,
        "group": group_filter,
        "service": service_filter,
    }


def _as_mapping(params: Any) -> dict[str, Any]:
    """A flat `{name: value}` from a `QueryDict`, a dict, or nothing.

    ⚠ `dict(QueryDict)` YIELDS LISTS AND THE DIFFERENCE IS SILENT — the same
    trap `runner._as_mapping` records: `{"q": ["ageing"]}` where every reader
    here expects a string, so `str(...)` would search for the text `['ageing']`
    and find nothing, on a screen that looks like it is working.
    """
    if params is None:
        return {}
    flatten = getattr(params, "dict", None)
    if callable(flatten):
        return dict(flatten())
    return dict(params)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 Phase 1 · P1.1 · P1.2 · P1.8 (05-prototype/09 Reports Build Brief.pdf p9-p10, p19-p21 read as IMAGES per B14 rule 42)
# screens: S44
# generated: 2026-09-26 by lane REP-P1
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_rep_p1_catalogue.py could not import this module before it existed, and `GET /reports` answered 23 cards in 3 groups
# exceptions: (1) `name_i18n` is EMPTY on all 46 seeded rows and nothing here authors it — B14 rule 35, 506 strings, not a lane's to write · (2) the sixth route target, `by_premises`, has no row among the 46 and the catalogue therefore stops being a door to S60 — FILED as DEF-REP-6816, not invented here · (3) the default page size is 50 rather than the drawn 20: B14 rule 37 makes a drawn number an illustration, and 50 is one of rule 16's five ratified sizes
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

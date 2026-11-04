# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · the `audit_log` DATASET QUERY (brief §7.1 — "datasets
#           are code, definitions are data"; §7.2 — a dataset states ONE grain;
#           §7.5 — the read path; §08 — "every arrow into the database passes
#           through a reviewed dataset").
#           Drawings read as IMAGES (B14 rule 42): p066 (R35 Audit Trail and
#           R36 Access Review, both in full), p051 (R8 Bill Delivery),
#           p083–p086 (§7.2/§7.2.1/§7.2.2/§7.2.4), p087 (§7.5 + §7.6),
#           p090–p092 (§08).
# Story:    US-REP-002 (S46 report viewer — the generic render, which A14's R-2
#           note names as the home of *User activity audit*). R35 Audit Trail
#           is the ONE of the three definitions seeded here whose drawn grain
#           is *one audit event*.
# Rules:    CLAUDE.md hard rule 1 (tenant scoping — `current_tenant_id()` on
#           every queryset, RLS FORCE; `audit_log` is RLS-FORCED per BR-AUD-007)
#           · **hard rule 4 — `audit_log` IS APPEND-ONLY (BR-AUD-002) AND THIS
#           FILE WRITES NOTHING AT ALL** · hard rule 7 (a money ACTION writes
#           `audit_log`; a READ is not an action and writes none) · NFR-3
#           (universal server pagination — `limit`/`offset`/`sort` in SQL) ·
#           NFR-5 (no hard caps) · BR-AUD-002 (append-only) · BR-AUD-003 (the
#           row payload standard) · BR-AUD-006 (PII enters MASKED only; there
#           is no unmask path and none is added here) · BR-AUD-012 / BR-AUD-013
#           (retention and the hot window) · BR-AUD-019 / BR-RBS-015 (a named
#           automation never borrows a user identity) · BR-REP-024 (never a 0
#           where a figure could not be computed) · BR-TEN-043 (the business
#           date is an argument, never a clock) · B14 rule 31 (no database id is
#           ever the visible value of a field) · B14 rule 33 (RATIONALE is ZERO
#           WORDS ON SCREEN)
# Tests:    06-backend/tests/test_rep_audit_log_dataset.py
#           10-scripts/ds_accounts_audit_notifications_cost.py (the PostgreSQL
#           measurement — hard-won law 14: the suite runs on in-memory SQLite)
#           10-scripts/rep_ds_accounts_rls_proof.py (tenant isolation, two tenants)
# Impacts:  apps/reports/datasets.py (`AUDIT_LOG.paginates`, `.columns`,
#           `.measures` — REP-UNBLOCK owns that file this session and this lane
#           REPORTS rather than registers) · apps/audit/selectors.py (the S61
#           VIEWER's read, which stays; this is the same fact shaped for a
#           report and it edits nothing there)
# ───────────────────────────────────────────────────────
"""THE `audit_log` DATASET — **one row per AUDIT EVENT**, paged and sorted in SQL.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — the audit trail is what a regulator and a disputing
customer are shown. Row in `12-governance/09-human-review-ledger.md`, written
before the review rather than after it.

═══════════════════════════════════════════════════════════════════════════════
⚠ THREE REPORTS ARE SEEDED ONTO THIS DATASET AND **ONE** OF THEM IS A REPORT
  ABOUT AUDIT EVENTS
═══════════════════════════════════════════════════════════════════════════════

| report | the drawing's own source line | one row is | verdict |
|---|---|---|---|
| **R35** Audit Trail | `Compliance › Audit · audit log · Event date` | one AUDIT EVENT | ✅ **served here** |
| **R36** Access Review | `Compliance › Audit · identity + audit · As at` | one USER | ❌ refused by name |
| **R8** Bill Delivery | `Billing › Delivery · notifications · —` | one OUTBOUND MESSAGE | ❌ refused by name — see `apps/notifications/notifications_dataset.py` |

⚠ **R36 IS THE ONE THAT WOULD HAVE BEEN WRONG IN A WAY THAT DEFEATS THE REPORT
ENTIRELY, AND IT IS WORTH STATING IN FULL.** Its four tiles are `USERS 9 ·
ACTIVE 8 · NEVER SIGNED IN 1 · CAN APPROVE MONEY 3`. **A user who has never
signed in has written NO audit events**, so a query at this grain — however it
is grouped — cannot produce that row at all. The `NEVER SIGNED IN` tile would
read `0` over a real dormant account, and `0` on a security report reads as
*nothing to look at*. The report exists to find exactly the row this grain
cannot see.

The refusals are DATA, not prose: `UNSERVABLE_HERE` names each report, the
grain its drawing states, the read model its facts live in, and the measured
evidence. `refuse(code)` raises with all of it.

═══════════════════════════════════════════════════════════════════════════════
⚠ THE REGISTRY'S COLUMN LIST FOR THIS DATASET HOLDS THREE REPORTS' COLUMNS
═══════════════════════════════════════════════════════════════════════════════
`reports/datasets.py::AUDIT_LOG` declares eleven columns. **Four of them are
not facts about an audit event and no query at this grain can serve them**, and
they are the columns of the two reports refused above:

* `channel`, `status`, `reason` — **R8's**, and they live on
  `notifications.outbound_messages` (`channel`, `status`, `last_error`).
  `audit_log` has no such columns; grep the model.
* `last_sign_in_at`, `added_by` — **R36's**, and they live on
  `identity.tenant_memberships` (`last_active_at`, `invited_by`). The registry's
  own comment calls them *"the two facts §05's identity row names, as ATTRIBUTES
  on this dataset rather than as a tenth dataset of their own"*. **They are not
  attributes of an audit event.** A dataset states one grain (§7.2); an
  attribute belongs to the grain or it belongs to another dataset.
* `actor_role` — identity's too. An audit row records WHO acted, and a role is
  a property of the user TODAY, not of the act. Serving today's role against a
  year-old event would say a clerk was an administrator when they were not.

This query serves the seven R35 draws and **publishes the other four as named
gaps rather than as nulls with no explanation** (BR-REP-024). The registry needs
amending and REP-UNBLOCK owns that file this session — reported, not edited.

═══════════════════════════════════════════════════════════════════════════════
⚠ THE MONEY-EVENTS TILE IS NOT DERIVABLE, AND IT IS SERVED AS `None` WITH A
  REASON RATHER THAN AS A PLAUSIBLE NUMBER
═══════════════════════════════════════════════════════════════════════════════
R35's third tile reads `MONEY EVENTS 1,884`. **Nothing in this table marks a row
as a money action.** Measured, in the code rather than taken from the brief:

    core/audit.py::money_action  → calls write_row(...) with exactly the same
    arguments a settings change uses. There is no `is_money` column, no flag in
    the payload, and `AuditLog` (apps/audit/models.py) carries
    id · tenant_id · actor_user_id · actor_kind · actor_label · actor_version ·
    action · entity_type · entity_id · before · after · created_at — and
    nothing else.

The classification would have to come from the **US-AUD-002 event-code
catalog**, and `apps/audit/selectors.py`'s own module docstring says it in as
many words: *"both are properties of the US-AUD-002 EVENT-CODE CATALOG, which
is not built (no catalog exists in this module). Classifying codes here would
invent that catalog."*

So a prefix match on `payment.` / `invoice.` would be this module inventing that
catalog, and the number it produced would be **reported to a compliance officer
as a fact**. BR-REP-024 says a figure that cannot be computed is `None` beside a
named reason, and that is what `money_events` is. `GAP_MONEY_EVENTS_UNCLASSIFIED`
carries the reason, and `OQ-REP-12742` is the question.

═══════════════════════════════════════════════════════════════════════════════
THE RETENTION TILE — THE HONEST PART, AND THE DRAWN FIGURE IS AN ILLUSTRATION
═══════════════════════════════════════════════════════════════════════════════
The brief's warning on p066, verbatim from the image: *"The retention tile is
the honest part and it belongs here, not on a form. The first row is the only
place cheque 4417 survives, and it is pruned on schedule with every other row —
ruled 23 Sep, no row type exempt. The Correct-reference screen says nothing
about it; this report shows the oldest date it holds."*

Three things follow and all three are built:

**① THE PERIOD IS READ, NOT TYPED.** The drawing shows `12 months`. B14 rule 37:
a figure drawn in a wireframe is an ILLUSTRATION, never a fact to build to.
`retention()` reads `core.archival.RETENTION_MONTHS`, which is **84** on this
deployment (`RETENTION_YEARS = 7`). Hard-coding 12 would have shipped a
compliance tile understating the trail's life by six years.

**② THE OLDEST DATE IS A FACT AND IS MEASURED.** `MIN(created_at)` over this
tenant's rows, in SQL. It is `None` on a tenant with no rows — which is a real
answer and a different thing from a date nobody could compute.

**③ THE SCREEN SAYS NOTHING ABOUT WHY.** Hard rule 4's retention ruling (PO
2026-09-23, verbatim: *"keep the same rule s; when audit log is delete - it is
deleted thats okay"*) makes `audit_log` carry ONE retention rule with **no row
type exempt**, and forbids any document, screen or docstring describing this
path as a permanent record of an old value — not until it is answered, but
**ever**. B14 rule 33 puts RATIONALE at ZERO WORDS ON SCREEN. **Those two rules
agree, and the honest build is SILENCE:** this query publishes the PERIOD and
the OLDEST DATE — two facts — and no sentence explaining either. A tile that
explained the policy would break rule 33 while trying to obey the ruling.

⚠ **THE WORKED CASE THE PO WAS SHOWN AND ACCEPTED:** a clerk types cheque 4471
as 4417 on 8 August and corrects it on 9 August. Under the retention in force
there is no record anywhere, a retention period later, that it ever read 4417,
and a customer quoting their own cheque matches nothing. `CorrectionRetentionNote`
was DELETED from all eleven catalogues for saying so on screen; nothing here
resurrects it.

═══════════════════════════════════════════════════════════════════════════════
BEFORE AND AFTER TRAVEL AS STORED — MASKED, NEVER UNMASKED (BR-AUD-006)
═══════════════════════════════════════════════════════════════════════════════
R35's drawn row is `Corrected reference · PMT-2609-000418 · 4417 → 4471`, so the
BEFORE and AFTER columns carry the values themselves. They are served **exactly
as stored**. PII enters the table masked and there is no unmask path anywhere in
this module; this file adds none, and a report is the last place one should be.

⚠ **AND R35 DRAWS A SEVENTH COLUMN, `WHERE`, WHICH IS THE MODULE.** The drawn
values are *Payments · Billing · Billing*. `audit_log` records the entity TYPE
and nothing else, and mapping a type to a module is B2 §2's module map — which
lives in a document and in no code this query can read. A partial map would
label some rows and leave others blank for no reason a reader could see, so the
module is ABSENT with `GAP_WHERE_IS_THE_MODULE_AND_NO_MAP_EXISTS` rather than
guessed, and `entity` still says what was acted on.

⚠ **`entity_ref` IS A NAMED ABSENCE AND NOT A UUID.** B14 rule 31: no database
id is ever the visible value of a field, and the drawing shows `PMT-2609-000418`
and `Run BR-2609-04`. `audit_log.entity_id` is a bare uuid with no FK — the
table is deliberately un-joined so it survives a tenant purge (BR-AUD-015) — so
turning it into a series number means one lookup per ENTITY TYPE across eleven
modules, and no such resolver exists. `entity_ref` is `None` with
`GAP_ENTITY_REF_IS_NOT_RESOLVED` rather than the uuid rendered as text, because
a uuid on screen breaks rule 31 and a uuid labelled *Object* is worse than an
absence: a compliance officer cannot look it up either way, and one of the two
looks like an answer.

═══════════════════════════════════════════════════════════════════════════════
IT PAGES AND SORTS IN SQL, AND EVERY QUERY STARTS FROM A TIME FLOOR
═══════════════════════════════════════════════════════════════════════════════
Brief §7.5 (p087). `per` cuts the page with `[offset:offset+limit]` on a
QuerySet — one `LIMIT/OFFSET` — and `sort` is `order_by(*order_terms(...))`.
**Nothing is sorted or sliced in Python anywhere in this file.**

⚠ **THE TABLE IS RANGE-PARTITIONED MONTHLY ON `created_at` (BR-AUD-012), SO THE
WINDOW IS NOT A CONVENIENCE — IT IS WHAT MAKES THE QUERY CHEAP.** A read with no
`from` scans every partition. `BR-AUD-013` already says every audit query starts
from a time floor and `apps/audit/selectors.py` enforces it with the 2-year hot
window; this query keeps that posture and **publishes which floor it used**, so
a report over a range the floor cut short says so instead of quietly showing
less.

⚠ **`audit_log_dataset_stream()` TAKES NO `page` AND NO `per`.** An export
cannot inherit a screen's fifty rows because there is no argument through which
to pass them. `NFR-5` forbids a ceiling on that branch and there is none.

**`totals` IS A SQL AGGREGATE OVER THE WHOLE FILTERED SET, NEVER OVER THE
PAGE**, so R35's tiles foot to the report whether a page is cut or not.

═══════════════════════════════════════════════════════════════════════════════
ADDITIVITY (§7.2.2, read as an image on p085)
═══════════════════════════════════════════════════════════════════════════════
* `events` (the count) — **FULLY ADDITIVE.** An event happened once, at one
  moment; counts of events sum freely in every direction, including across
  time. It is the one measure in this lane's three datasets that does.
* `actors` (distinct) — **NON-ADDITIVE.** It is a COUNT DISTINCT and must be
  recomputed from its components, never summed: September's 9 actors plus
  October's 9 actors is not 18 people. This is §7.2.2's *"must be recomputed
  from its components, never averaged"* row, and a footer that totals it shows
  an em-dash and this reason.
* `money_events` — **would be fully additive; it is not served** (see above).

═══════════════════════════════════════════════════════════════════════════════
WHAT IT WILL NOT DO
═══════════════════════════════════════════════════════════════════════════════
**It writes nothing, and here that is a database guarantee rather than a
promise.** `audit_log` carries an append-only trigger (BR-AUD-002, migration
0001) and no UPDATE or DELETE path exists in this module. There is no INSERT,
UPDATE, DELETE or `save()` below either.

**It never falls back to zero.** BR-REP-024.

**It states no clock.** `start`/`end` are arguments (BR-TEN-043).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from django.db.models import Count

from apps.audit import selectors as audit_selectors
from apps.audit.models import AuditLog
from core import archival
from core.pagination import order_terms
from core.tenancy import current_tenant_id

#: BR-REP-001. R35's eyebrow is `Event date` — the moment the act was recorded,
#: which is `audit_log.created_at`, stamped by the store at INSERT and the
#: table's own partition key. There is no second date on this grain and none is
#: invented.
BASIS = "event"

#: What a caller may order by. Four, because four are what R35's drawing puts a
#: sortable column on, and they are the same four the S61 viewer already
#: declares (`audit_selectors.AUDIT_LIST_SORTS`) so the report and the screen
#: cannot disagree about what `actor` means.
#:
#: ⚠ **EVERY TUPLE ENDS IN A UNIQUE COLUMN.** A page is a window over an ORDER;
#: without a total order two equal rows swap between pages and a compliance
#: officer sees one event twice and another never. `id` closes every tuple, and
#: `core.pagination.order_terms` refuses to add a tiebreak silently.
#:
#: ⚠ **`created_at` IS IN EVERY TUPLE BESIDE `id`, AND THAT IS THE PARTITION
#: KEY DOING WORK.** The table's primary key is (tenant_id, created_at, id), so
#: an order ending `created_at, id` is the key's own order and the planner can
#: walk partitions in sequence instead of sorting the whole trail.
AUDIT_SORTS: tuple[str, ...] = ("when", "actor", "action", "entity")
AUDIT_DEFAULT_SORT = "when"
#: US-AUD-004's ratified default: newest first.
AUDIT_DEFAULT_DIRECTION = "desc"
AUDIT_SORT_COLUMNS: dict[str, tuple[str, ...]] = {
    "when": ("created_at", "id"),
    "actor": ("actor_user_id", "created_at", "id"),
    "action": ("action", "created_at", "id"),
    "entity": ("entity_type", "created_at", "id"),
}

#: The filters this query HONOURS — R35's drawn five, in the registry's
#: spelling. `object` in the drawing is `entity` here, which is what both the
#: registry and `audit_selectors.AUDIT_FILTERS` call it.
AUDIT_FILTERS: tuple[str, ...] = ("from", "to", "actor", "action", "entity")

#: ⚠ Declared by `AUDIT_LOG.filters` in the registry and NOT honoured here:
#: they are R8's and R36's. See `GAP_FOUR_COLUMNS_BELONG_TO_OTHER_GRAINS`.
AUDIT_FILTERS_NOT_HONOURED: tuple[str, ...] = ("channel", "status")


# ── BR-REP-024: named gaps, never a silent zero and never a plausible number ──

GAP_MONEY_EVENTS_UNCLASSIFIED = {
    "code": "no_column_marks_an_audit_row_as_a_money_action",
    "br_ref": "CLAUDE.md hard rule 7 · BR-AUD-004 · US-AUD-002 (the event-code catalog)",
    "detail": (
        "R35's MONEY EVENTS tile counts money actions. core/audit.py's `money_action` calls "
        "`write_row` with exactly the arguments a settings change uses, and `AuditLog` carries "
        "no flag, class or catalog reference — so a money row and a settings row are "
        "indistinguishable in this table. The classification is a property of the US-AUD-002 "
        "event-code catalog, which apps/audit/selectors.py states is NOT BUILT. Guessing it "
        "from an action-code prefix would invent that catalog and report the guess to a "
        "compliance officer as a fact, so no figure is published."
    ),
    "wanted_reads": ("the US-AUD-002 event-code catalog, with BR-AUD-004's six classes",),
}

GAP_ENTITY_REF_IS_NOT_RESOLVED = {
    "code": "an_audit_row_holds_a_uuid_and_no_human_reference",
    "br_ref": "B14 rule 31 · BR-AUD-015",
    "detail": (
        "R35 draws the Object column as PMT-2609-000418 and Run BR-2609-04 — series numbers. "
        "audit_log.entity_id is a bare uuid with NO foreign key, deliberately, so the trail "
        "survives a tenant purge (BR-AUD-015). Turning it into a series number needs one "
        "resolver per entity_type across eleven modules and none exists. The reference is "
        "absent rather than served as a uuid, because B14 rule 31 forbids a database id as the "
        "visible value of a field and a uuid under a column headed Object looks like an answer "
        "a compliance officer could follow. entity_type travels, so the row still says WHAT was "
        "acted on."
    ),
    "wanted_reads": ("a per-entity_type reference resolver, which no module publishes",),
}

GAP_WHERE_IS_THE_MODULE_AND_NO_MAP_EXISTS = {
    "code": "the_module_an_entity_belongs_to_is_not_recorded_or_derivable",
    "br_ref": "brief p066 (R35's drawn WHERE column) · B2 §2 (the module map)",
    "detail": (
        "R35 draws a WHERE column reading Payments, Billing, Billing. That is the MODULE the "
        "acted-on thing belongs to, and audit_log records the entity TYPE (payment, invoice, "
        "bill_run) and nothing else. Mapping a type to a module is B2 §2's module map, which "
        "lives in a document and in no code this query can read; the eleven modules own "
        "hundreds of entity types between them and a partial map would label some rows and "
        "leave others blank for no reason a reader could see. `entity` travels, so the row "
        "still says WHAT was acted on, and the module is absent rather than guessed."
    ),
    "wanted_reads": ("a code-level entity_type → module map, which no module publishes",),
}

GAP_FOUR_COLUMNS_BELONG_TO_OTHER_GRAINS = {
    "code": "four_declared_columns_are_not_facts_about_an_audit_event",
    "br_ref": "brief §7.2 (a dataset states ONE grain)",
    "detail": (
        "reports/datasets.py::AUDIT_LOG declares channel, status, reason, actor_role, "
        "last_sign_in_at and added_by. None is a column of audit_log. channel/status/reason are "
        "R8's and live on notifications.outbound_messages; last_sign_in_at/added_by are R36's "
        "and live on identity.tenant_memberships as last_active_at/invited_by; actor_role is a "
        "property of the user TODAY, and serving it against a year-old event would state that a "
        "clerk was an administrator when they were not. They are absent rather than null, and "
        "the registry needs amending."
    ),
    "wanted_reads": (
        "apps.notifications.notifications_dataset",
        "apps.identity.models.TenantMembership",
    ),
}


def _window_floor_problem(floor: datetime, start: date | None) -> dict[str, Any] | None:
    """Published when the requested window starts BEFORE the floor that applied.

    ⚠ **A CHECK THAT REPORTS ZERO OVER A SCOPE IT SILENTLY EXCLUDES IS THE
    SHAPE THIS REPO FAILS IN** (hard-won law 7's fifth clause, and `G32`'s
    `0 unresolved` over 21 live refusals). `BR-AUD-013` bounds every audit query
    by a time floor, so a report asked for *last five years* on a hot query
    truthfully returns two — and two years of events look exactly like two years
    of events. The number it left out gets a sentence beside the number it
    found.
    """
    if start is None or start >= floor.date():
        return None
    return {
        "code": "the_window_asked_for_starts_before_the_floor_that_applied",
        "br_ref": "BR-AUD-013 · BR-AUD-012",
        "detail": (
            f"This report was asked for events from {start.isoformat()} and the query floor was "
            f"{floor.date().isoformat()}. Every audit query is bounded by a time floor: the "
            "two-year hot window by default, the retention horizon when `archive` is asked for. "
            "Rows before the floor are not counted here. Pass archive=True to read to the "
            "retention horizon."
        ),
        "wanted_reads": (),
    }


@dataclass(frozen=True)
class AuditEventRow:
    """One audit event, in the dataset's own declared column names.

    ⚠ **`actor` IS ONE OF THREE THINGS AND THE THIRD IS A NULL THAT MEANS
    SOMETHING.** A person (`actor_id` + name), a NAMED automation (`actor_kind`
    + `actor_label`, and **no id at all** — BR-RBS-015: it never borrows a user
    identity), or an unnamed system job (every actor field null, which is what
    BR-AUD-003 has always meant). The three are kept apart rather than collapsed
    into a string, because *System* and *a clerk whose name we failed to fetch*
    are different facts and only one of them is a person.

    ⚠ **`before` AND `after` ARE SERVED EXACTLY AS STORED.** PII enters this
    table MASKED (BR-AUD-006) and there is no unmask path anywhere in this
    module; none is added here.

    ⚠ **`entity_ref` IS `None`.** See `GAP_ENTITY_REF_IS_NOT_RESOLVED` — a uuid
    is not a reference (B14 rule 31).
    """

    event_id: str
    event_at: datetime
    actor_id: str | None
    actor: str | None
    actor_kind: str | None
    actor_version: str | None
    action: str
    entity: str
    entity_ref: str | None
    before: Any
    after: Any
    summary: str
    window: str


# ═══════════════════════════════════════════════════════════════════════════
#  THE TWO THIS DATASET CANNOT SERVE — REFUSED BY NAME, WITH WHAT EACH NEEDS
# ═══════════════════════════════════════════════════════════════════════════

UNSERVABLE_HERE: dict[str, dict[str, Any]] = {
    "access_review": {
        "report": "R36 Access Review",
        "drawn_source": "Compliance › Audit · identity + audit · As at",
        "drawn_grain": "one USER",
        "why_not_here": (
            "This dataset's grain is one audit EVENT. R36's row is a person — USER · ROLE · "
            "ADDED · ADDED BY · LAST SIGN-IN · APPROVE MONEY · STATUS — and its tiles are "
            "USERS 9 · ACTIVE 8 · NEVER SIGNED IN 1 · CAN APPROVE MONEY 3. "
            "⚠ A USER WHO HAS NEVER SIGNED IN HAS WRITTEN NO AUDIT EVENTS, so this grain cannot "
            "produce that row at any grouping: the NEVER SIGNED IN tile would read 0 over a real "
            "dormant login, and 0 on a security report reads as nothing to look at. The report "
            "exists to find precisely the row this grain is blind to."
        ),
        "needs_read_model": (
            "apps.identity.models.User",
            "apps.identity.models.TenantMembership",
            "apps.identity.models.RolePermission (for CAN APPROVE MONEY)",
        ),
        "evidence": (
            "TenantMembership carries `status` (invited | active | deactivated), `invited_at`, "
            "`invited_by` and `last_active_at`, whose own column comment reads \"null renders "
            "'Never'\" — so LAST SIGN-IN and NEVER SIGNED IN are answerable from identity ALONE, "
            "without reading audit at all. The drawing's `identity + audit` source line "
            "overstates what audit contributes; measured, the four tiles and six of the seven "
            "columns are identity's. CAN APPROVE MONEY is a permission on the row's ROLE, in "
            "identity.RolePermission."
        ),
        "warning_obeyed": (
            "p066, verbatim: \"Ten staff is the whole ICP, so this is nine rows and not a "
            "paginated list — and it is still served paginated, because NFR-3 admits no "
            "exceptions and the four places that claimed one are the defect DEF-PAY-4221 exists "
            "to close.\" So the identity-grain read that serves R36 MUST page, at nine rows, and "
            "must not acquire an \"it is small\" exemption."
        ),
        "security_note": (
            "⚠ R36 READS IDENTITY, SO A LEAK IS A SECURITY DEFECT. BR-REP-023 restricts this "
            "report to System Admin and Executive. ⚠ THIS SENTENCE READ 'AND NOTHING ENFORCES "
            "IT TODAY' UNTIL 2026-09-27, WHEN P5.9 BUILT THE ENFORCEMENT — it is now "
            "apps/reports/role_gate.py, read from report_definitions.min_role, asked twice: "
            "the catalogue leaves the card OUT for a role below the floor, and GET "
            "/reports/access_review refuses with 403. It is NOT in this query, deliberately — "
            "a dataset query answers WHAT the rows are and a role floor is a property of the "
            "DEFINITION, so putting it here would gate one report and leave the next one "
            "unguarded. Walked at 1440 on 2026-09-27: a Billing Clerk is drawn 44 cards of 45 "
            "and refused at the address; an Executive and a System Admin are drawn all 45."
        ),
    },
    "bill_delivery": {
        "report": "R8 Bill Delivery",
        "drawn_source": "Billing › Delivery · notifications · —",
        "drawn_grain": "one OUTBOUND MESSAGE (one document, on one channel)",
        "why_not_here": (
            "R8 is SEEDED on `audit_log` and DRAWN from `notifications`, which is a TENTH "
            "dataset the registry does not hold. Its row is ACCOUNT · CUSTOMER · CHANNEL · "
            "ADDRESS · SENT · STATUS · REASON and its tiles are SENT · DELIVERED (95%) · "
            "BOUNCED · RETURNED POST. None of those is a property of an audit event: a bounce "
            "is a provider's answer about a message, not an act anybody performed, and no audit "
            "row is written when an email bounces."
        ),
        "needs_read_model": ("apps.notifications.models.OutboundMessage",),
        "evidence": (
            "outbound_messages carries channel, status, recipient_address, sent_at, "
            "returned_at, last_error, unavailable_reason and account_id — every column R8 draws, "
            "at exactly its grain (\"one row per document per CHANNEL\", BR-BIL-016). "
            "`apps/notifications/notifications_dataset.py` is that query and it is built."
        ),
        "warning_obeyed": (
            "p051, verbatim: \"The address column walks to premises — an address is stored in "
            "one place and every other entity derives it. Nothing here holds its own copy.\" "
            "Obeyed in the notifications query; see its docstring for the one place that "
            "sentence is narrower than it looks."
        ),
    },
}


class UnservableFromThisDataset(ValueError):
    """Raised when a caller asks this dataset for a report it does not state.

    ⚠ **IT RAISES RATHER THAN RETURNING AN EMPTY LIST.** An empty result reads
    as *no rows matched*, which is a legitimate answer a compliance officer will
    act on; a refusal naming the report, the grain and the read model is the
    only output a reader can tell apart from a working report.
    """


def unservable_reason(code: str) -> dict[str, Any]:
    """The refusal row for one report key, or `KeyError` if it is not refused."""
    return dict(UNSERVABLE_HERE[code])


def refuse(code: str) -> None:
    """Raise `UnservableFromThisDataset` naming the report and what it needs."""
    row = UNSERVABLE_HERE[code]
    raise UnservableFromThisDataset(
        f"{row['report']} is seeded on the `audit_log` dataset and states the grain "
        f"'{row['drawn_grain']}'. This dataset states 'one audit event'. "
        f"{row['why_not_here']} It needs: {', '.join(row['needs_read_model'])}."
    )


def _tenant_id() -> Any:
    return current_tenant_id()


def retention() -> dict[str, Any]:
    """R35's RETENTION tile — **two facts and not one word of rationale.**

    ⚠ **THE PERIOD IS READ FROM `core.archival`, NEVER TYPED.** The drawing says
    `12 months`; B14 rule 37 makes a drawn figure an illustration, and
    `RETENTION_MONTHS` is 84 on this deployment. A hard-coded 12 would have
    shipped a compliance tile understating the trail's life by six years.

    ⚠ **`oldest` IS `None` ON A TENANT WITH NO ROWS, AND THAT IS A REAL ANSWER**
    — different from a date that could not be computed (BR-REP-024). It is one
    indexed `MIN` over the partition key.

    ⚠ **THERE IS NO `note`, NO `caveat` AND NO `detail` KEY, DELIBERATELY.**
    Hard rule 4's retention ruling forbids describing this path as a permanent
    record of an old value, and B14 rule 33 puts RATIONALE at ZERO WORDS ON
    SCREEN. The honest build is silence: the tile states the period and the
    oldest date it holds, and claims nothing. A caller that adds a sentence here
    breaks rule 33 while trying to obey the ruling.
    """
    oldest = (
        AuditLog.objects.filter(tenant_id=_tenant_id())
        .order_by("created_at")
        .values_list("created_at", flat=True)
        .first()
    )
    return {
        "months": archival.RETENTION_MONTHS,
        "oldest_at": oldest,
    }


def _base(
    *,
    start: date | None,
    end: date | None,
    actor_id: Any,
    action: str | None,
    entity_type: str | None,
    archive: bool,
    **unhonoured: Any,
) -> tuple[Any, datetime]:
    """The filtered set and the floor that applied — hard rule 1 first.

    ⚠ **THE TENANT FILTER IS THE FIRST CLAUSE AND IS NOT OPTIONAL.** RLS FORCE
    is on this table (BR-AUD-007) and would refuse a cross-tenant row anyway,
    but a queryset that relies on the database to be the only guard is wrong the
    day somebody runs it as an owner.

    ⚠ **THE FLOOR IS RETURNED, NOT SWALLOWED.** `BR-AUD-013` bounds every audit
    query; a caller that asked for more than the floor allows gets a problem row
    saying so rather than a shorter report that looks complete.

    ⚠ **AN UNHONOURED FILTER RAISES.** `channel` and `status` are R8's columns
    and this table has neither; accepting one and ignoring it would serve the
    whole trail under a chip reading *Email*.
    """
    named = {key for key, value in unhonoured.items() if value not in (None, "")}
    if named:
        raise UnservableFromThisDataset(
            "the `audit_log` dataset query does not honour "
            + ", ".join(sorted(named))
            + ". Those are R8 Bill Delivery's columns and they live on "
            "notifications.outbound_messages, not on audit_log — see "
            "`apps/notifications/notifications_dataset.py`. Serving the whole trail under a "
            "channel chip would be a live screen behind a broken control."
        )

    floor = audit_selectors.window_floor(archive=archive)
    rows = AuditLog.objects.filter(tenant_id=_tenant_id(), created_at__gte=floor)
    if start is not None:
        rows = rows.filter(created_at__date__gte=start)
    if end is not None:
        rows = rows.filter(created_at__date__lte=end)
    if actor_id is not None:
        rows = rows.filter(actor_user_id=actor_id)
    if action:
        rows = rows.filter(action=str(action))
    if entity_type:
        rows = rows.filter(entity_type=str(entity_type))
    return rows, floor


def _shape(row: Any, names: dict[str, str], floor: datetime) -> AuditEventRow:
    """One stored audit row, in the dataset's declared column names."""
    actor_id = str(row.actor_user_id) if row.actor_user_id else None
    return AuditEventRow(
        event_id=str(row.id),
        event_at=row.created_at,
        # The NAMED-automation branch is tested first and the order is
        # load-bearing — `_actor_payload`'s own reasoning, kept rather than
        # re-derived: reading a named automation as a PERSON would print a
        # staff name against an automation's act.
        actor_id=None if row.actor_kind is not None else actor_id,
        actor=row.actor_label if row.actor_kind is not None else (names.get(actor_id or "")),
        actor_kind=row.actor_kind,
        actor_version=row.actor_version,
        action=row.action,
        entity=row.entity_type,
        entity_ref=None,  # GAP_ENTITY_REF_IS_NOT_RESOLVED — never the uuid
        before=row.before,
        after=row.after,
        summary=audit_selectors.summarize(row.before, row.after),
        window=audit_selectors.window_of(row, hot_floor=floor),
    )


def _shape_all(materialised: list[Any], floor: datetime) -> list[AuditEventRow]:
    """ONE batched actor-name read, then the rows. Never one query per row.

    Cross-module READ, the same Eng disposition `apps/audit/selectors.py`
    already records for this exact lookup: `actor_names` resolves
    `actor_user_id` to a display name through identity's model, read-only, one
    bulk query per page, never a write across the boundary (B1).
    """
    actor_ids = [row.actor_user_id for row in materialised if row.actor_user_id]
    names = audit_selectors.actor_names(_tenant_id(), actor_ids)
    return [_shape(row, names, floor) for row in materialised]


def audit_log_dataset(
    *,
    start: date | None = None,
    end: date | None = None,
    actor_id: Any = None,
    action: str | None = None,
    entity_type: str | None = None,
    archive: bool = False,
    page: int = 1,
    per: int | None = None,
    sort: str | None = None,
    direction: str = AUDIT_DEFAULT_DIRECTION,
    **unhonoured: Any,
) -> dict[str, Any]:
    """THE dataset query — R35 Audit Trail. One row per audit event, paged in SQL.

    `per=None` is the whole filtered set. `per` is an integer page size; the
    CALLER clamps it (`core.pagination.clamp_page_size`) and this function does
    not invent one (`NFR-5`).

    ⚠ **FOR AN EXPORT, CALL `audit_log_dataset_stream()`** — it takes no `page`
    and no `per`.

    **`totals` IS A SQL AGGREGATE OVER THE WHOLE FILTERED SET AND NEVER OVER THE
    PAGE**, so R35's tiles foot to the report whether a page is cut or not.
    """
    rows, floor = _base(
        start=start,
        end=end,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        archive=archive,
        **unhonoured,
    )

    aggregated = rows.aggregate(
        event_count=Count("id"),
        # NON-ADDITIVE (§7.2.2): a COUNT DISTINCT is recomputed from its
        # components, never summed. September's 9 actors plus October's 9 is
        # not 18 people.
        actor_count=Count("actor_user_id", distinct=True),
    )
    total_events = int(aggregated["event_count"])

    problems: list[dict[str, Any]] = [
        dict(GAP_MONEY_EVENTS_UNCLASSIFIED),
        dict(GAP_ENTITY_REF_IS_NOT_RESOLVED),
        dict(GAP_FOUR_COLUMNS_BELONG_TO_OTHER_GRAINS),
        dict(GAP_WHERE_IS_THE_MODULE_AND_NO_MAP_EXISTS),
    ]
    floor_problem = _window_floor_problem(floor, start)
    if floor_problem is not None:
        problems.append(floor_problem)

    ordered = rows.order_by(
        *order_terms(sort, direction, columns=AUDIT_SORT_COLUMNS, default=AUDIT_DEFAULT_SORT)
    )

    served_page = max(1, int(page or 1))
    if per is None:
        window = ordered
        pages = 1
    else:
        size = max(1, int(per))
        pages = max(1, -(-total_events // size))
        served_page = min(served_page, pages)
        offset = (served_page - 1) * size
        window = ordered[offset : offset + size]

    return {
        "basis": BASIS,
        "grain": "one audit event",
        "rows": tuple(_shape_all(list(window), floor)),
        "totals": {
            # Fully additive (§7.2.2) — an event happened once, at one moment.
            "events": total_events,
            # Non-additive — recomputed, never summed.
            "actors": int(aggregated["actor_count"]),
            # BR-REP-024: NOT DERIVABLE, and never a 0 and never a guess.
            "money_events": None,
        },
        # Two facts. No rationale (B14 rule 33 · hard rule 4's retention ruling).
        "retention": retention(),
        "window_floor": floor,
        "page": served_page,
        "per": per,
        "pages": pages,
        "total": total_events,
        "problems": tuple(problems),
    }


#: How many rows one round trip of the export fetches. A BUFFER, not a cap
#: (`NFR-5`): the loop runs until the cursor is exhausted.
STREAM_CHUNK = 2_000


def audit_log_dataset_stream(
    *,
    start: date | None = None,
    end: date | None = None,
    actor_id: Any = None,
    action: str | None = None,
    entity_type: str | None = None,
    archive: bool = False,
    sort: str | None = None,
    direction: str = AUDIT_DEFAULT_DIRECTION,
    **unhonoured: Any,
) -> Iterator[AuditEventRow]:
    """EVERY row of the filtered set, streamed — **no `page`, no `per`.**

    ⚠ **THE ABSENCE OF THOSE TWO PARAMETERS IS THE WHOLE DESIGN.** An export
    cannot inherit a screen's fifty rows because there is no argument through
    which to pass them; a flag would have had that bug, a missing parameter
    cannot.

    ⚠ **`NFR-5` — NO CAP ANYWHERE ON THIS PATH.** `STREAM_CHUNK` is a fetch
    buffer rather than a ceiling.

    The order is applied IN SQL, the same `order_terms` the page uses, so the
    file and the screen sort identically.
    """
    rows, floor = _base(
        start=start,
        end=end,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        archive=archive,
        **unhonoured,
    )
    ordered = rows.order_by(
        *order_terms(sort, direction, columns=AUDIT_SORT_COLUMNS, default=AUDIT_DEFAULT_SORT)
    )
    buffer: list[Any] = []
    for row in ordered.iterator(chunk_size=STREAM_CHUNK):
        buffer.append(row)
        if len(buffer) >= STREAM_CHUNK:
            yield from _shape_all(buffer, floor)
            buffer = []
    if buffer:
        yield from _shape_all(buffer, floor)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 · the `audit_log` dataset query (05-prototype/09 Reports Build Brief.pdf p051, p066 read as IMAGES per B14 rule 42; §7.2/§7.2.2/§7.2.4 p083–p086; §7.5/§7.6 p087; §08 p090–p092)
# screens: S46 (the viewer) — R35 Audit Trail
# generated: 2026-09-27 by lane DS-ACCOUNTS
# checklist: A✔ B✔ C✔ D=deferred(registration is lane REP-UNBLOCK's this session — `apps/reports/datasets.py` and `queries.py`; this lane adds NO endpoint and says so rather than claiming one) E✔(the S46 viewer renders every dataset and needs nothing new — the frontend half is owed nothing by this file) F✔ G✔ H=deferred(HUMAN-REVIEW-PENDING — the row is in 12-governance/09-human-review-ledger.md, dated 2026-09-27, written BEFORE the review)
# gates: RED PROVED FIRST, THROUGH pytest. Three mutations, three reds: the retention tile hard-coded to the drawing's `12 months` (the deployment's figure is 84 — six years understated on a compliance tile) · `money_events` served as a `payment.`-prefix guess (the fixture holds three rows such a guess would count) · `entity_ref` served as `str(row.entity_id)` (B14 rule 31). Restored and re-run GREEN: 51 passed. Isolation on real PostgreSQL 16: `rep_ds_accounts_rls_proof.py` — `audit_log` ENABLE+FORCE on the partitioned PARENT, 3,807 own rows beside the neighbour's 0.
# exceptions: (1) R36 Access Review and R8 Bill Delivery are REFUSED BY NAME in `UNSERVABLE_HERE` — R36's grain is one USER and a never-signed-in user writes no audit events, R8's is one outbound message · (2) `money_events` is served as None with a named reason: no column marks a money action and the US-AUD-002 catalog is not built (`OQ-REP-12742`) · (3) `entity_ref` is None rather than a uuid — B14 rule 31 · (4) four of the registry's eleven declared columns are other grains' and are absent rather than null · (5) this file writes nothing, and `audit_log` refuses writes at the database besides (BR-AUD-002)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

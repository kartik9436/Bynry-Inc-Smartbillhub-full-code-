# ── Trace ──────────────────────────────────────────────
# Story:   CR-112 — the City's address register becomes the source of addresses.
#          This file is THE RUN: pull once, match in our database, write only
#          what the utility turned on, and report what it did.
# Rules:   BR-INT-072 (the snapshot: read the page size, outSR always,
#          all-or-nothing, throttled, resumable) · BR-INT-073 (the match and the
#          re-derivation) · BR-INT-074 (preview does everything and writes
#          NOTHING) · BR-MET-1173 (the keys, and what a replaced key leaves
#          behind) · BR-INT-039 (every attempt is a durable record) ·
#          BR-INT-038 (an adapter translates and decides nothing) · hard rule 1
#          (tenant scoping) · hard rule 7 (every money action writes audit_log —
#          this writes none, and says so) · hard-won law 14 (a SAVEPOINT, and it
#          is proved on PostgreSQL) · PO rulings 2026-09-17 nos. 1–10
# Tests:   06-backend/tests/test_cr112_gis_parcels.py
# Impacts: apps/metering/selectors.gis_reconciliation_set (the owning module's
#          read) · apps/metering/services.update_premises (the write, through
#          metering's own service — no cross-module write, B2 §2)
# ───────────────────────────────────────────────────────
"""The parcel reconciliation run — one pull, one pass, and a preview that lies about nothing.

THE SHAPE, AND WHY `preview` IS NOT A SECOND CODE PATH
--------------------------------------------------------
`run()` takes `mode` — **preview** or **apply** — and `started_by`, which is
either the schedule or a named person. **Both modes do exactly the same work**:
the same pull, the same match, the same classification, the same disposition
lookup. They differ in one place, `_persist`, which `preview` does not call.

⚠ **THAT IS `BR-RBS-003`'s RULE BORROWED ON PURPOSE.** A preview built as its
own branch is a second implementation that proves nothing about the first, and
it drifts the first time somebody fixes a bug in one of them. Here a preview
cannot disagree with the apply it previews, because up to the last step it *is*
the apply.

**A PREVIEW WRITES NOTHING — NOT THE KEYS, NOT THE FIELDS, NOT THE STAMP.** The
verified stamp is the one people argue about: it looks like metadata rather than
data. It is a write, it is durable, and a preview that left it behind would mean
running a preview twice told you something different the second time.

WHAT IT WRITES WHEN IT DOES WRITE, AND WHAT IT NEVER WRITES
--------------------------------------------------------------
Writes: the two keys, the replaced-key history, `gis_status`, the verified
stamp, and **only those address fields the utility has explicitly turned on**.
Ruling 9 — *"c) never touch by default"* — so on a fresh tenant that last set is
EMPTY and the run changes no addresses at all. That is correct and intended, and
`report["headline"]` says so in words rather than leaving a clerk to infer it
from two zeroes.

Never writes: anything on a City record we have no premises for (ruling 8 —
*"c) ignore"*, not even a work item), anything back to the City (ruling 10), and
no map tile of any kind (ruling 1).

⚠ **NO `audit_log` ROW IS WRITTEN FROM HERE, AND THAT IS NOT AN OVERSIGHT.**
Hard rule 7 binds MONEY actions. This writes no money field — it cannot: the
three that decide tax are not in `PREMISES_FIELDS` at all. The writes it does
make go through `metering.services.update_premises`, which is metering's own
audited service, so each one is audited by the module that owns the row. A
second audit row written here would be the same act recorded twice.

⚠ **THE `batch.landed` EVENT IS NOT EMITTED HERE, AND THE REASON IS A BLAST
RADIUS RATHER THAN A SHORTAGE OF TIME.** `apps/runbooks/definitions/
gis_reconciliation.py` reads a landed batch and its trigger row names
`batch.landed`; verified 2026-09-17, that event is emitted by **nothing**, and
**seven** runbooks name it — `gis_reconciliation`, `bank_reconciliation`,
`returned_payments`, `leak_alert`, `cash_application`, `read_validation` and
`payments/runbook_reads`. Every one of them declares **manual and schedule**
instead and says so in its own docstring, so none is broken today.

Emitting the general event from a GIS pull would start six unrelated runbooks on
a wave scoped to addresses. So this run hands off to its OWN runbook by name
through `hand_off_to_runbook`, and the general event stays `CR-069` wave O's,
where the other six can be considered together. **The hand-off is a real call
and not a note** (hard-won law 1): `tests/test_cr112_gis_parcels.py` asserts the
runbook is started with this run's batch, and hard-won law 2's lesson about
holds applies — the day wave O lands, that test is what says this line can go.

WHAT WOULD MAKE THIS RUN REPORT WRONGLY (hard-won law 7, habit 2)
-------------------------------------------------------------------
* **A run that examined nothing and a run that found nothing wrong.** Every
  count in the report is present even at zero, and `city_rows_ignored` exists so
  ruling 8's deliberate silence carries a number.
* **A half pull read as a mass deletion.** `gis_layer.walk` raises rather than
  returning a partial snapshot, and this stops the run on it without writing.
* **A field the City renamed** reading as blank on every row and reconciling as
  *blank theirs* over the whole register. The run REFUSES when the snapshot
  reports the parcel or point field missing, rather than filing 40,000
  differences.
* **A preview that is quietly an apply.** `_persist` is the only writer and the
  mode test is on its first line; `test_a_preview_writes_absolutely_nothing`
  counts rows before and after.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from django.db import DatabaseError, transaction
from django.utils import timezone

from apps.integrations import gis_layer, gis_match
from apps.integrations.seams import runbooks as runbooks_seam
from core import errors

#: The two modes `F` asks for. **`preview` is the default**, because hard-won
#: law 3 says the unsafe option must be the one somebody types.
PREVIEW = "preview"
APPLY = "apply"
MODES = (PREVIEW, APPLY)

#: Who set it going. A person's NAME travels with the run, because *"a schedule
#: did it"* and *"D. Whitfield did it at 4pm"* are different answers to the
#: question somebody asks a week later.
BY_SCHEDULE = "schedule"
BY_PERSON = "person"


#: ── `DEF-INT-9846` / `DEF-INT-5620` · THE CITY REFUSED US, SAID BY WHICH WAY ─
#: One catalogue key per `gis_layer.REFUSED_*` word, shared by the address
#: search (`gis.search`), the pick's re-check (`gis.create_premises`) and this
#: run, so the three surfaces cannot word one refusal three ways. B14 rule 33:
#: a FACT, six words or fewer. `HEADLINES` is the same sentence in English for
#: the run row's `summary`, which support reads and no screen translates.
REFUSAL_KEYS = {
    gis_layer.REFUSED_KEY: "integrations.gis.city_rejected_key",
    gis_layer.REFUSED_MOVED: "integrations.gis.city_layer_moved",
    gis_layer.REFUSED_ERROR: "integrations.gis.city_service_error",
    # `DEF-INT-10019` — a 403 that is not ArcGIS's JSON: a firewall or CDN in
    # front of the City (Cloudflare's `error code: 1010`), never our key.
    gis_layer.REFUSED_FIREWALL: "integrations.gis.city_firewall_blocked",
}
REFUSAL_HEADLINES = {
    gis_layer.REFUSED_KEY: "The city rejected our key.",
    gis_layer.REFUSED_MOVED: "The city's map layer has moved.",
    gis_layer.REFUSED_ERROR: "The city's service had an error.",
    gis_layer.REFUSED_FIREWALL: "The city's firewall blocked us.",
}


class GisRunRefused(Exception):
    """The run stopped before writing anything, and this says why."""


def config_from_connection(config: Mapping[str, Any]) -> gis_layer.LayerConfig:
    """The City-specific facts, read off the CONNECTION (`BR-INT-037`).

    ⚠ **NOTHING ANN ARBOR-SPECIFIC IS HARD-CODED ANYWHERE IN THIS MODULE.**
    The URL, the layer, and which field is the parcel id and which the point id
    are per-tenant configuration. PO, verbatim: *"So adding an API is data, not
    code"*. Another city with a differently-named layer connects the same
    connector and types different field names into the same form.

    **WHERE EACH VALUE COMES FROM ON THE FORM.** `base_url` is the connector's
    *Service address*, which became `kind="url"` in `DEF-INT-5589` on this same
    day — before that it was `kind="host"` and **could not hold a layer address
    at all**, because an ArcGIS layer is named by its PATH
    (`…/FeatureServer/0`). `field_mapping` is the `mapping_editor` field added
    beside it, the kind `bank_lockbox_file` already uses for a file's column
    mapping; it carries `parcel_field`, `point_field` and any of the six value
    fields a city spells differently.

    `layer_url` is read first and `base_url` second, so a connection that keeps
    a separate layer address works and one that does not falls back to the
    service address. An unmapped key keeps this file's default, and
    `Snapshot.attributes_missing` reports any the city's rows do not carry — so
    a wrong mapping STOPS the run rather than reconciling every row as blank.
    """
    layer_url = str(config.get("layer_url") or config.get("base_url") or "").strip()
    if not layer_url:
        raise GisRunRefused("this connection names no layer to read")
    # ⚠ **ONE READER OF `field_mapping`, NOT TWO** (`DEF-INT-5618`). The merge
    # below used to live here and the live address search had no equivalent at
    # all, so a city that renamed its parcel field was obeyed by the nightly
    # run and ignored by the clerk's search. Moved to `gis_layer` — which the
    # search can import without a cycle — and called from both. The refusal
    # above stays HERE, because a reconciliation with no layer to read must
    # stop and a search builds its own query address.
    return gis_layer.field_names_from(config.get("field_mapping"), layer_url=layer_url)


def _policy_from(settings: Mapping[str, Any] | None) -> dict[str, str]:
    """Which fields the utility turned on. **Absent means never touch.**

    Ruling 9. A tenant that has configured nothing gets `{}` here, every field
    resolves to `never_touch` in `gis_match.disposition_for`, and the run
    changes no addresses at all on its first night.
    """
    return {
        str(key): str(value)
        for key, value in dict((settings or {}).get("gis_field_dispositions") or {}).items()
    }


# ═══════════════════════════════════════════════════════════════════════════
# The write — the ONLY place in this module that changes a row
# ═══════════════════════════════════════════════════════════════════════════

#: ── 2026-09-17 · `DEF-INT-5629` ─────────────────────────────────────────────
#: **WHAT ONE ROW MAY DO TO A RUN.** Each of these costs the row it happened on
#: and nothing else; the savepoint below is what makes that true on PostgreSQL.
#:
#: ⚠ **IT IS A NAMED LIST AND NOT `except Exception`, AND THE DIFFERENCE IS THE
#: WHOLE POINT.** `_persist` calls `metering.services.update_premises`, which
#: raises a PRODUCT refusal for everything a 40,000-row apply legitimately
#: meets — a value the validator will not take (`ValidationError`), a rule that
#: stopped the row (`BizError`), a premises deleted between the read and the
#: write (`NotFoundError`, via `deny_as_not_found`) — and a `DatabaseError` for
#: a constraint. Until this list existed only the LAST of those was caught, so
#: the first row metering refused ended the run and `rows_refused` could never
#: reach 1 by any of the other three.
#:
#: ⚠ **AND `AuthError` IS DELIBERATELY ABSENT.** A role refusal is a property of
#: the ACTOR and not of a row: if this actor may not write premises then every
#: row fails, and swallowing it would report *40,000 rows refused* for a run
#: that was never allowed to start — a check that cannot fail wearing the
#: clothes of a report (hard-won law 7, habit 2). `SysError` is absent for the
#: same reason. Both end the run.
#: `tests/test_cr112_gis_parcels_pg.py::test_an_authorisation_refusal_stops_the_run_rather_than_counting_40000`
#: is what holds this line, and it goes red the day somebody widens the tuple.
_ROW_REFUSALS: tuple[type[BaseException], ...] = (
    DatabaseError,
    errors.ValidationError,
    errors.BizError,
    errors.NotFoundError,
)

#: What a refused row says, in the same plain English this file's `headline` and
#: `detail` already use. ⚠ **NO MESSAGE KEY AND NO ERROR CODE TRAVELS WITH IT**
#: — B14 rule 32 keeps a rule id or an internal code out of clerk-facing copy,
#: and `VAL-002 (metering.unknown_field)` beside a property number is exactly
#: that. What the clerk needs is WHICH rows and roughly why; the detail is in
#: the audit trail on the property itself.
_REFUSAL_REASONS: tuple[tuple[type[BaseException], str], ...] = (
    (errors.NotFoundError, "That row is no longer there."),
    (errors.ValidationError, "A value was not accepted."),
    (errors.BizError, "A rule stopped this row."),
    (DatabaseError, "The database refused this row."),
)

#: How many refused rows are NAMED before the run reports only a number.
#: `BR-RBS-035`'s shape — a row for what it acted on and a COUNT for the rest —
#: borrowed on purpose: `rows_refused: 37` over 40,000 rows tells nobody WHICH
#: 37, and a list of 40,000 is a report nobody can open.
REFUSALS_NAMED = 50


def _reason_for(exc: BaseException) -> str:
    for kind, sentence in _REFUSAL_REASONS:
        if isinstance(exc, kind):
            return sentence
    return "This row was refused."


def _persist(
    actor: Any,
    report: gis_match.MatchReport,
    *,
    update_premises: Callable[..., Any],
    update_unit: Callable[..., Any],
    now: Any = None,
) -> tuple[dict[str, int], list[dict[str, str]]]:
    """Apply what the run decided. **Never called in `preview` mode.**

    Returns the counts and the refused rows, NAMED — see `REFUSALS_NAMED`.

    ⚠ **EACH ROW IS ITS OWN SAVEPOINT, AND ON POSTGRESQL THAT IS THE ONLY
    OPTION RATHER THAN THE TIDY ONE (hard-won law 14).** One refused row must
    not lose the other 39,999. `try: … except …: continue` around a bare
    statement works on SQLite — which is what `config/settings/test.py` runs, in
    memory — and on PostgreSQL the first failure ABORTS THE WHOLE TRANSACTION:
    every later query raises `InFailedSqlTransaction` and the run is lost at
    COMMIT having reported success. The nested `transaction.atomic()` below is
    the SAVEPOINT that makes the `continue` mean what it reads as.
    **Do not "simplify" it away.** `tests/test_cr112_gis_parcels_pg.py` proves
    it against real PostgreSQL, because the default suite cannot — and it is
    proved by SABOTAGE: take the `with transaction.atomic():` line out and
    `test_one_refused_row_does_not_lose_the_others` fails with
    `TransactionManagementError` while the whole SQLite suite stays green.

    ⚠ **THE SAVEPOINT IS NOT ONLY FOR `DatabaseError`, WHICH IS WHAT
    `DEF-INT-5629` COST.** The exception the writer hands back is very often NOT
    a database error: a service that catches a constraint and re-raises it as a
    sentence a clerk can read leaves the transaction ABORTED and gives you a
    `ValidationError`. Catching that OUTSIDE a savepoint would count the row and
    then lose every row after it. The savepoint rolls back on **any** exception
    leaving the block, which is why the catch list can name product refusals at
    all — `_ROW_REFUSALS` above says which, and says which are deliberately not
    on it.
    """
    stamped = now or timezone.now()
    counts = {"keys_taken": 0, "keys_replaced": 0, "fields_applied": 0,
              "verified_stamped": 0, "rows_refused": 0}
    refusals: list[dict[str, str]] = []

    changes: dict[tuple[str, Any], dict[str, Any]] = {}
    #: The premises NUMBER or the unit's, carried beside the patch so a refused
    #: row can be named without the database id B14 rule 31 forbids on screen.
    labels: dict[tuple[str, Any], str] = {}

    for decision in report.key_decisions:
        if decision.action not in ("take", "replace", "keep"):
            continue
        key = (decision.level, decision.row_id)
        patch = changes.setdefault(key, {})
        labels.setdefault(key, decision.label)
        column = "gis_parcel_id" if decision.level == "premises" else "gis_point_id"
        if decision.action == "take":
            patch[column] = decision.new_key
            counts["keys_taken"] += 1
        elif decision.action == "replace":
            patch[column] = decision.new_key
            # ⚠ **WHAT IT WAS AND WHEN IT CHANGED (`BR-MET-1173`).** A wrong key
            # means faithfully copying the wrong parcel's data for ever, and
            # this pair is the only way anybody finds out why six months later.
            # Written on `replace` and never on `take`: a first key is not a
            # change, and recording one would make every new row look churned.
            patch[f"{column}_was"] = decision.old_key
            patch["gis_key_changed_at"] = stamped
            counts["keys_replaced"] += 1
        # ⚠ A row the City CONFIRMED — on `keep` as much as on `take`. The stamp
        # answers *when did the City last agree this row exists*, and a row
        # whose key resolved unchanged was confirmed just as much as one that
        # was matched for the first time.
        patch["gis_verified"] = True
        patch["gis_verified_at"] = stamped
        counts["verified_stamped"] += 1

    for difference in report.to_apply:
        key = (difference.level, difference.row_id)
        patch = changes.setdefault(key, {})
        labels.setdefault(key, difference.label)
        patch[difference.field_name] = difference.theirs
        counts["fields_applied"] += 1

    for (level, row_id), patch in changes.items():
        if row_id is None:
            continue
        write = update_premises if level == "premises" else update_unit
        try:
            # THE SAVEPOINT. See the docstring above before touching this.
            with transaction.atomic():
                write(actor, row_id, patch)
        except _ROW_REFUSALS as exc:
            # Safe ONLY because the savepoint above has already rolled back —
            # on ANY exception leaving the block, not only a database one.
            # Outside one, this `continue` would poison every later statement.
            counts["rows_refused"] += 1
            if len(refusals) < REFUSALS_NAMED:
                refusals.append(
                    {
                        "level": level,
                        "label": labels.get((level, row_id), ""),
                        "reason": _reason_for(exc),
                    }
                )
            continue
    return counts, refusals


# ═══════════════════════════════════════════════════════════════════════════
# The run
# ═══════════════════════════════════════════════════════════════════════════


def run(
    actor: Any = None,
    *,
    connection_config: Mapping[str, Any],
    ours: Mapping[str, Any],
    mode: str = PREVIEW,
    started_by: str = BY_SCHEDULE,
    started_by_name: str | None = None,
    settings: Mapping[str, Any] | None = None,
    transport: Callable[[str, float], Any] | None = None,
    api_key: str | None = None,
    pace: Callable[[int], None] | None = None,
    update_premises: Callable[..., Any] | None = None,
    update_unit: Callable[..., Any] | None = None,
    hand_off: Callable[..., Any] | None = None,
    now: Any = None,
    max_pages: int | None = None,
) -> dict[str, Any]:
    """Pull once, match in our database, write only what was turned on.

    `ours` is `metering.selectors.gis_reconciliation_set()`'s answer — our whole
    register in two queries. `transport` is an ARGUMENT rather than a patch
    target, which is `adapters/gis_city.py`'s established shape and the reason a
    rename cannot silently disconnect a test from the thing it tests.

    ⚠ **`max_pages` — A PERSON TESTING THE CITY BY HAND (`DEF-INT-9849`, PO GIS
    review gap 3).** The walk stops after that many pages and the report says
    *Stopped after N of M pages* in its headline, carries `complete: False`, and
    puts the City's total beside the pages read. **An APPLY with a page limit is
    REFUSED** before anything is dialled: `BR-INT-072` ruling 4 is all or
    nothing for a WRITE, and a register reconciled against three of its seventy
    pages would queue every premises on the other sixty-seven as *no parcel
    matched its address*. A preview writes nothing, so a part of the register is
    a true answer to the question the person asked — as long as it says so.
    """
    if mode not in MODES:
        raise GisRunRefused(f"{mode!r} is not a mode; it is one of {MODES}")
    if max_pages is not None and mode == APPLY:
        raise GisRunRefused("a page limit is for a preview only; an apply reads the whole register")
    if started_by == BY_PERSON and not started_by_name:
        # A person started it and we did not record which person. That is the
        # question somebody asks a week later, so it is refused rather than
        # recorded as anonymous.
        raise GisRunRefused("a person started this run and no name was recorded")

    layer = config_from_connection(connection_config)
    policy = _policy_from(settings)

    # ── 1 · the pull. ALL OR NOTHING (`BR-INT-072`, ruling 4) ───────────────
    try:
        snapshot = gis_layer.walk(
            layer, transport=transport, api_key=api_key, pace=pace,
            stop_after_pages=max_pages,
        )
    except (gis_layer.LayerIncomplete, gis_layer.LayerRefused) as exc:
        # ⚠ **THE RUN STOPS AND CHANGES NOTHING.** A half snapshot reconciles as
        # *the City deleted the addresses it did not send*, and under a
        # disposition that applied blanks it would do exactly that to us.
        #
        # `DEF-INT-9846` — and when the City REFUSED us, the report says which
        # refusal, by catalogue key, so a rotated key and a moved layer are not
        # the same red box. `None` for silence and for our own reading of a
        # well-formed answer; the screen then keeps its general sentence.
        reason = getattr(exc, "reason", None)
        return {
            "mode": mode,
            "started_by": started_by,
            "started_by_name": started_by_name,
            "stopped": True,
            "stop_reason_key": REFUSAL_KEYS.get(reason) if reason else None,
            "headline": REFUSAL_HEADLINES.get(reason, "The city's register could not be read in full."),
            "detail": str(exc),
            # `DEF-INT-10019` — `"<status>, <first 200 characters of the body>"`
            # when the City (or something in front of it) refused us; the run
            # row's `provider_error`, so who refused is readable afterwards.
            "provider_error": getattr(exc, "evidence", None),
            "applied": {},
            # A stopped run wrote nothing, so it refused nothing — the key is
            # present at zero so a reader never has to ask whether it exists.
            "refusals": [],
            "counts": {},
        }

    # ⚠ **A RENAMED FIELD WOULD READ AS BLANK ON EVERY ROW** and reconcile as
    # *blank theirs* across the whole register. Stop, rather than file 40,000
    # differences that all say the same wrong thing.
    critical = {layer.parcel_field, layer.point_field}
    missing = sorted(critical.intersection(snapshot.attributes_missing))
    if missing and len(snapshot):
        return {
            "mode": mode,
            "started_by": started_by,
            "started_by_name": started_by_name,
            "stopped": True,
            "headline": "The city's register does not carry the fields we were told to read.",
            "detail": f"not found on their rows: {', '.join(missing)}",
            "applied": {},
            "refusals": [],
            "counts": {"city_rows": len(snapshot)},
        }

    # ── 2 · the match, in OUR database, with no further calls out (ruling 4) ─
    report = gis_match.reconcile(
        snapshot=snapshot,
        premises=list(ours.get("premises") or ()),
        units_by_premises=dict(ours.get("units_by_premises") or {}),
        policy=policy,
    )

    # ── 3 · the write, and ONLY in apply ────────────────────────────────────
    applied: dict[str, int] = {}
    refusals: list[dict[str, str]] = []
    if mode == APPLY:
        applied, refusals = _persist(
            actor, report,
            update_premises=update_premises or _refuse_writer("premises"),
            update_unit=update_unit or _refuse_writer("unit"),
            now=now,
        )

    fields_never_touch = sum(
        1
        for name in gis_match.PREMISES_FIELDS
        if gis_match.disposition_for(name, gis_match.CONFLICT, policy)
        == gis_match.NEVER_TOUCH
    )
    queued = [one for one in report.key_decisions if one.action == "queue"]
    # Which City parcel each of our rows was compared against, so a difference
    # names the parcel as well as the premises (`DEF-INT-9848` — runbook 20's
    # *Parcel* column). The key a row KEEPS or TAKES; an old key otherwise.
    parcel_of = {
        (one.level, str(one.row_id)): (one.new_key or one.old_key or None)
        for one in report.key_decisions
    }

    # ── `DEF-INT-9849` · A PART OF THE REGISTER SAYS IT IS A PART ───────────
    complete = bool(snapshot.complete)
    total_pages = snapshot.total_pages
    partial_sentence = ""
    if not complete:
        partial_sentence = (
            f"Stopped after {snapshot.pages} of {total_pages} pages. "
            if total_pages is not None
            else f"Stopped after {snapshot.pages} pages; the city has more. "
        )

    # ── the hand-off (`BR-INT-074`) ─────────────────────────────────────────
    # ⚠ **A REAL CALL AND NOT A NOTE** (hard-won law 1). The batch has landed;
    # runbook 20 is what reconciles it, and until this line existed the runbook
    # stopped at step 1 with *"Nothing has landed yet"*. A PREVIEW hands off
    # nothing, because a preview writes nothing and there is no landed batch to
    # reconcile — starting a runbook over a snapshot that was never stored
    # would be the write the mode exists to prevent.
    handed_off: dict[str, Any] = {}
    if mode == APPLY:
        handed_off = runbooks_seam.hand_off_gis_batch(
            {"source": "gis", "rows": len(snapshot), "pages": snapshot.pages},
            start=hand_off,
        )

    return {
        "handed_off": handed_off,
        "mode": mode,
        "started_by": started_by,
        "started_by_name": started_by_name,
        "stopped": False,
        # `DEF-INT-9849` — `False` when a person asked for fewer pages than the
        # City holds. Never `True` over a part of the register.
        "complete": complete,
        # ⚠ The sentence ruling 9 makes necessary — see `MatchReport.headline`.
        "headline": partial_sentence
        + report.headline(fields_never_touch=fields_never_touch),
        "applied": applied,
        "counts": {
            "city_rows": len(snapshot),
            "city_pages": snapshot.pages,
            # The City's whole register in pages: equal to `city_pages` on a
            # complete walk, larger on a stopped one, `None` when it would not say.
            "city_pages_total": total_pages,
            "city_page_size": snapshot.page_size,
            "premises_examined": report.premises_examined,
            "units_examined": report.units_examined,
            "differences_found": len(report.differences),
            "differences_to_apply": len(report.to_apply),
            "fields_set_to_never_touch": fields_never_touch,
            "queued": len(queued),
            "unmatched_ours": report.unmatched_ours,
            # Ruling 8 — *"c) ignore"*. Counted here and nowhere else, so the
            # deliberate silence has a number attached to it (law 7).
            "city_rows_ignored": report.city_rows_ignored,
            # ⚠ **OUR BUG, NOT THE CITY'S.** A key changing on a row we have
            # already changed means our matching is unstable; the City does not
            # renumber a parcel nightly.
            "thrash": len(report.thrash_candidates),
        },
        "thrash_rows": list(report.thrash_candidates),
        # ⚠ **THE ROWS THE WRITE REFUSED, BY NAME (`DEF-INT-5629`).** A run that
        # reports `rows_refused: 37` and nothing else is a number a clerk cannot
        # act on — they cannot tell one refused row from another, and the run
        # looks the same as one that refused 37 different rows last night.
        # Capped at `REFUSALS_NAMED`; the COUNT in `applied` is always whole.
        # Empty on a preview, which writes nothing and therefore refuses nothing.
        "refusals": refusals,
        "queue": [
            {"level": one.level, "label": one.label, "reason": one.reason,
             "candidates": list(one.candidates)}
            for one in queued
        ],
        "differences": [
            {"level": one.level, "label": one.label, "field": one.field_name,
             "parcel": parcel_of.get((one.level, str(one.row_id))),
             "ours": one.ours, "theirs": one.theirs,
             "class": one.difference_class, "disposition": one.disposition}
            for one in report.differences
        ],
    }


def _refuse_writer(level: str) -> Callable[..., Any]:
    """An apply with no writer bound REFUSES rather than silently doing nothing.

    Hard-won law 2's shape: a mode called `apply` that quietly applied nothing
    would pass every test and be absent in production.
    """

    def refuse(*_args: Any, **_kwargs: Any) -> None:
        raise GisRunRefused(f"apply was asked for and no {level} writer is bound")

    return refuse


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-112 (the ten PO rulings of 2026-09-17, decision log of that date)
# generated: 2026-09-17 by the CR-112 GIS build lane
# checklist: A✔ B=PARTIAL(the Run now control is not built — see the report) C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_cr112_gis_parcels.py · tests/test_cr112_gis_parcels_pg.py (PostgreSQL only — law 14)
# exceptions: `batch.landed` is deliberately NOT emitted here — seven runbooks name that event and a GIS pull is not the place to start six unrelated ones; the hand-off to THIS runbook is by name and is tested
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

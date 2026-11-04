# ── Trace ──────────────────────────────────────────────
# Change:   CR-042 — "in all imports - we need 2 option on step 1 insert,
#           insert & update; replace option is not required" (PO, 2026-08-27).
#           SUPERSEDES CR-038 W7 task 3 — "we need insert, insert update,
#           repalce option in step 1 of wirzard" (PO, 2026-08-26) — the same
#           person, six days apart, and W7's own finding is what produced it.
# Rules:    BR-MET-127 (a SUPERSEDING mode meeting a BILLED read refuses BY NAME,
#           the rest of the batch posts) · BR-MET-016 (the duplicate key is
#           meter+date+channel) · BR-MET-129 (a warned reading POSTS) ·
#           BR-MET-210 (two modes, that order, those words, step 1, ONE
#           control) · OQ-418 CLOSED BY REMOVAL ·
#           CLAUDE.md hard rule 4 + B2 DB-6 (financial immutability — a
#           correction is a NEW ROW pointed at by `superseded_by_id`, NEVER an
#           UPDATE) · CR-036 (g) (the mode is a PREMISE, chosen at stage 1)
# Impacts:  services.stage_read_batch (records it) ·
#           services.validate_read_batch (re-judges the duplicate outcome
#           against it) · services.commit_read_batch (acts on it).
# ───────────────────────────────────────────────────────
"""THE TWO WRITE MODES, FOR READS.

**WHY THIS IS ITS OWN MODULE AND NOT A BRANCH IN `validation.py`.** The rule
engine answers one question — *is this reading sound?* — and its answer must
not depend on what the operator intends to do with the file. The write mode
asks a different question: *given a reading already on file at this key, what
did the clerk mean?* CR-036 (g) is the PO's own framing, verbatim: *"you need
at step 1 or 2 itself - this is important decision how you will process the
data and upload it"* — the mode is a **premise**, not a verdict. So the engine
judges, and this module re-reads ONE of its outcomes (`duplicate`, committed
scope) in the light of the premise.

**THE TWO MODES, AS CR-038 R2 STATES THEM MINUS THE MODE CR-042 WITHDREW,
QUOTED NOT SUMMARISED:** *"For reads the modes NEVER edit a committed row (hard
rule 4): `insert` refuses committed duplicates; `insert & update` SUPERSEDES a
committed duplicate as a correction, reason stamped."*

| mode | a key with NO reading on file | a key WITH an unbilled reading | a key with a BILLED reading |
|---|---|---|---|
| `insert`  | writes | **ERROR** — BR-MET-016, unchanged | **ERROR** — BR-MET-016, unchanged |
| `upsert`  | writes | supersedes (a correction, reason stamped) | **refused by name** — BR-MET-127 |

⛔ **`replace` IS WITHDRAWN — CR-042, PO 2026-08-27, AND OQ-418 IS CLOSED BY
REMOVAL.** PO verbatim: *"in all imports - we need 2 option on step 1 insert,
insert & update; replace option is not required"*.

**Nothing is lost on THIS rail, and that is measurable rather than reassuring.**
`upsert` and `replace` did the same thing to every row: R2's two sentences
(*"supersedes a committed duplicate"* / *"supersedes everything the file
carries"*) describe the same set of rows, because a file only carries what it
carries. What would have distinguished them is what `replace` does to readings
**on file and NOT in the file** — and for reads there was never a lawful answer
to guess at, since *retiring a meter reading* is either a delete (forbidden —
hard rule 4) or a supersede-by-nothing (a correction with no corrected value,
which is not a thing). That was OQ-418, and removing the mode dissolves it.

⚠ **THE OTHER RAIL IS NOT THE SAME CASE AND MUST NOT BE READ AS ONE.** On
`import_runs` (premises · units · assets · accounts) `replace` DID have distinct
behaviour — BR-MET-099's deactivate-what-is-missing — so there the option is
withdrawn and **the behaviour is kept, unreachable**, with **OQ-580** asking the
PO how a utility retires a premise it no longer serves. A lane reading this
module's clean deletion and applying it there would destroy a signed capability.

⚠ **AND THE MODE IS STILL A COLUMN.** Batches written before 2026-08-27 may hold
`write_mode="replace"`; they are read back unchanged and the screen prints a
withdrawn-label rather than a raw id. `normalize()` REFUSES the value on the way
IN — see its own docstring for why coercing it to `insert` would be worse than
an error.

⚠ **NOTHING HERE EVER UPDATES A COMMITTED ROW.** `supersede` means what it
means everywhere else in this module: `_close_head` writes the two closure
columns on the old head and a NEW row is inserted. That is the only shape
CLAUDE.md hard rule 4 and B2 DB-6 permit. It is why the withdrawn mode was
always spelled *replace-as-supersede*, and it is why `insert & update` is the
correct name for what survives: nothing is ever updated in place.
"""

from __future__ import annotations

from typing import Any

from . import validation

#: The TWO modes, in the order the PO named them (BR-MET-210 clause 2).
#: `insert` is FIRST and is the default because it is the only one that cannot
#: alter a reading already on file: a clerk who never touches the control gets
#: the safe mode (hard-won law 3 — the unsafe option must be the one you type).
READ_WRITE_MODES = ("insert", "upsert")
DEFAULT_READ_WRITE_MODE = "insert"

#: ⛔ **WITHDRAWN, NOT FORGOTTEN — CR-042.** Named in code because the refusal
#: must be able to name it. A caller sending `replace` is not a caller who
#: typo'd: it is a stale client, or a batch row written before 2026-08-27 being
#: replayed. *"Unknown value"* would tell them they made a mistake; the truth is
#: that the mode existed and was removed.
WITHDRAWN_READ_WRITE_MODES = ("replace",)

#: The modes that treat "already on file" as the EXPECTED state of a row.
#:
#: ⚠ **THIS TUPLE IS WHY BR-MET-127 SURVIVED CR-042, AND IT WAS MEASURED.** The
#: rule was written as *"Replace mode meets a billed read"* and this tuple read
#: `("upsert", "replace")`. The billed-read refusal attaches to whatever is in
#: HERE, never to a mode by name — so withdrawing `replace` removed a mode and
#: not a protection. `test_cr042__BR_MET_127s_billed_refusal_survives_the_
#: removal` asserts that against `upsert` directly, with no pipeline in the way.
SUPERSEDING_MODES = ("upsert",)

#: The outcome this module writes, beside the engine's own. It is a separate
#: rule name rather than an edit to `duplicate`'s detail so a reader of
#: `rule_outcomes` can always see BOTH facts: the engine found a duplicate, and
#: the premise said what to do about it.
RULE_WRITE_MODE = "write_mode"

#: What the commit does with the row. Stored in the outcome's detail as
#: `action`, re-derived at commit against the head as it is THEN (a head can be
#: superseded between the dry run and the commit — the rehearsal is a
#: rehearsal, never the authority).
ACTION_WRITE = "write"  # no head at this key: an ordinary insert
ACTION_SUPERSEDE = "supersede"  # an unbilled head: a correction row
ACTION_REFUSE_BILLED = "refuse_billed"  # BR-MET-127: named, and the batch posts
ACTION_BLOCKED = "blocked"  # insert mode met a head — BR-MET-016's ERROR stands

#: The reason string `commit_read_batch` reports for a BR-MET-127 refusal.
SKIP_REASON_BILLED = "billed_read_refused"

#: The supersede reason stamped on every correction this rail mints. CR-038 R2
#: requires a reason ("*reason stamped*") and `_supersede_row`/`_close_head`
#: both take one; a bulk correction with a blank reason would leave an audit
#: trail that cannot say why the old head was closed.
SUPERSEDE_REASON = "import write mode — corrected by a later reading in the same upload"


def normalize(raw: Any) -> str | None:
    """The stage-1 value, or `None` when it is not one of the two.

    Returns `None` rather than falling back to the default: a caller that sent
    `"upserts"` must be told, not quietly given `insert` and a batch that
    refuses every duplicate it was meant to correct.

    ⚠ **AND `replace` IS REFUSED HERE TOO, WHICH IS THE POINT WORTH STATING.**
    It would be easy to be "kind" to a withdrawn value and map it onto `upsert`,
    which is what it used to do on this rail. Do not. On the OTHER rail
    `replace` retired records the file no longer carried, and a client that
    cannot tell the two rails apart — a script, a replayed payload — would be
    told its retirement request succeeded when nothing was retired. **A wrong
    belief about a destructive operation is worse than an error**, and an empty
    answer here becomes a named refusal one frame up.

    An ABSENT value still takes the default: not choosing is not the same as
    choosing something that no longer exists.
    """
    if raw is None or raw == "":
        return DEFAULT_READ_WRITE_MODE
    text = str(raw).strip().lower()
    return text if text in READ_WRITE_MODES else None


def committed_duplicate_id(outcomes: list[dict[str, Any]] | None) -> str | None:
    """The id of the committed head the engine's `duplicate` rule named.

    ⚠ Reads the ENGINE's outcome rather than re-querying: the head this answers
    about is the one the row was actually judged against, so the screen and the
    plan can never describe two different readings. Both committed scopes count
    — an exact key match (`committed`) and BR-MET-016's second clause
    (`same_cycle_unchanged_value`), which is a reading on file for the same
    meter, register and cycle carrying the same number.
    """
    for entry in outcomes or []:
        if entry.get("rule") != validation.RULE_DUPLICATE:
            continue
        detail = entry.get("detail") or {}
        if detail.get("scope") in ("committed", "same_cycle_unchanged_value"):
            existing = detail.get("existing_read_id")
            if existing:
                return str(existing)
    return None


def plan(
    *,
    write_mode: str,
    head_id: str | None,
    head_is_billed: bool = False,
    head_label: str | None = None,
    same_day: bool = False,
) -> dict[str, Any]:
    """What this row does at commit, and the sentence that says why.

    `head_label` is the reading NAMED — BR-MET-127 is explicit that the refusal
    *"names the reading"*, so the caller passes the words a clerk would
    recognise (`"M-4021 · 2026-07-31 · total"`) and this returns them attached
    to the outcome rather than leaving the screen to reassemble them.
    """
    if head_id is None:
        return {"action": ACTION_WRITE, "write_mode": write_mode}
    if same_day and write_mode not in SUPERSEDING_MODES:
        # ⚠ **BR-MET-1189 (PO 2026-10-04, DEF-WRK-9642) — A SECOND READING OF
        # THE SAME REGISTER ON THE SAME DATE IS KEPT.** PO verbatim: *"take the
        # reading records in register and use date and highest consumption
        # reading if it is apprved and validated"*. Under `insert` it is
        # written beside the one on file and `counted_reading` decides which
        # counts; nothing on file is touched. `insert & update` still means a
        # CORRECTION and still supersedes (below) — that is the clerk's stated
        # premise, not a second reading. BR-MET-016's second clause (the same
        # value again inside the cycle, a DIFFERENT date) is not this case and
        # still blocks.
        return {
            "action": ACTION_WRITE,
            "write_mode": write_mode,
            "beside_read_id": head_id,
            "reason": "second_reading_same_day",
        }
    if write_mode not in SUPERSEDING_MODES:
        # BR-MET-016's ERROR stands untouched. `insert` means what it says:
        # a reading already on file for this meter, date and register is NOT
        # written over, and the clerk resolves the row (reject / skip / the
        # `override` disposition) before the batch posts.
        return {
            "action": ACTION_BLOCKED,
            "write_mode": write_mode,
            "existing_read_id": head_id,
            "existing_read": head_label,
            "reason": "already_on_file",
        }
    if head_is_billed:
        # ⚖️ BR-MET-127 (PO 2026-08-26), verbatim: *"(a) refuse by name — a
        # money correction should never be minted as a side effect of a bulk
        # upload; the clerk opens each through the billed door, deliberately"*.
        # WARNING and not ERROR **by the rule's own words**: *"the refusal is a
        # row outcome, never a batch failure"*, and an ERROR would stop the
        # other 1,179 rows posting (`_unresolved_errors` gates the whole post).
        return {
            "action": ACTION_REFUSE_BILLED,
            "write_mode": write_mode,
            "existing_read_id": head_id,
            "existing_read": head_label,
            "reason": SKIP_REASON_BILLED,
            "door": "correct_billed_read",
        }
    return {
        "action": ACTION_SUPERSEDE,
        "write_mode": write_mode,
        "existing_read_id": head_id,
        "existing_read": head_label,
    }


def outcome(detail: dict[str, Any]) -> validation.Outcome:
    """The plan as a rule outcome the row can carry.

    Severity, and the reason for each:
      * `write`           → OK. The premise changed nothing about this row.
      * `blocked`         → OK **here**, because `duplicate` already carries the
                            ERROR (BR-MET-016). Two ERRORs for one fact would
                            double-count the row in every KPI on the screen.
      * `supersede`       → WARNING. Something on file is about to be corrected;
                            BR-MET-129 says a warned row POSTS, which is exactly
                            what should happen, and the flag travels onto the
                            committed read so the correction is visible after.
      * `refuse_billed`   → WARNING. BR-MET-127: a row outcome, never a batch
                            failure. The row does not post and the result names
                            it — see `commit_read_batch`'s `skipped_rows`.
    """
    action = detail.get("action")
    if action in (ACTION_SUPERSEDE, ACTION_REFUSE_BILLED):
        severity = validation.WARNING
    else:
        severity = validation.OK
    return validation.Outcome(RULE_WRITE_MODE, severity, detail)


def apply(outcomes: list[Any], detail: dict[str, Any]) -> list[Any]:
    """The engine's outcomes, re-judged against the premise, plus the premise's
    own outcome appended.

    ⚠ **THIS IS THE ONE PLACE A RULE'S SEVERITY IS CHANGED BY SOMETHING OTHER
    THAN THE RULE, AND CR-036 (g) IS THE SANCTION FOR IT**, verbatim:
    *"The severity and the action of a rule may legitimately DEPEND on the
    write mode"*. The PO's own screenshot is the proof — `PRM.ADDRESS_ON_FILE`
    firing **9,881** times with action *Skip on load*, under a mode where
    *"already on file" is the EXPECTED state of every row, and a skip would
    defeat the mode entirely*.

    So under `upsert` the engine's committed-duplicate ERROR becomes a
    WARNING. Three things make that safe rather than a severity laundry:
      1. it happens for the committed scopes ONLY — an intra-batch duplicate
         (the same key twice in one file) is still an ERROR under every mode,
         because no premise makes a file that contradicts itself acceptable;
      2. the original verdict is not erased — `superseded_by_write_mode` is
         stamped into the outcome's own detail, so the row still says the
         engine found a duplicate and says who overruled its severity;
      3. WARNING is not a pass. BR-MET-129 posts the row **with the flag
         attached**, so the correction is visible on the committed read
         afterwards, which is the whole point of a corrections upload.
    """
    action = detail.get("action")
    if action in (ACTION_SUPERSEDE, ACTION_REFUSE_BILLED):
        rejudged = []
        for entry in outcomes:
            if entry.rule == validation.RULE_DUPLICATE and (entry.detail or {}).get("scope") in (
                "committed",
                "same_cycle_unchanged_value",
            ):
                rejudged.append(
                    validation.Outcome(
                        entry.rule,
                        validation.WARNING,
                        {
                            **(entry.detail or {}),
                            "engine_severity": entry.severity,
                            "superseded_by_write_mode": detail.get("write_mode"),
                        },
                    )
                )
            else:
                rejudged.append(entry)
        outcomes = rejudged
    return list(outcomes) + [outcome(detail)]


def read_label(*, meter_no: Any, read_at: Any, channel: Any) -> str:
    """`"M-4021 · 2026-07-31 · total"` — the words BR-MET-127's refusal names.

    Assembled in ONE place so the staged row's flag, the commit's skip reason
    and the screen all print the same three facts in the same order. A missing
    part is rendered as `?` rather than dropped: a refusal naming
    `"M-4021 · ? · total"` still tells the clerk which meter to open, and a
    refusal that silently shortens itself hides which fact was unavailable.
    """
    date_part = getattr(read_at, "date", None)
    stamp = date_part() if callable(date_part) else read_at
    return " · ".join(
        str(part) if part not in (None, "") else "?" for part in (meter_no, stamp, channel)
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-042 (PO 2026-08-27 · BR-MET-210 · OQ-418 closed by removal · OQ-580) — SUPERSEDES CR-038 W7 task 3's packet (CR-038 R2 · CR-036 (g) · BR-MET-127 · BR-MET-129 · BR-MET-016 · CLAUDE.md hard rule 4 / B2 DB-6)
# generated: 2026-08-26 by the CR-038 W7 one-rail lane · amended 2026-08-27 by the CR-042 lane
# checklist: A✔ B✔(the stage-1 control is components/workflow/WriteModeChoice.tsx, mounted by UploadReadsWizard AND by ImportWorkflowPage — CR-042 made it ONE control) C✔(tests/test_cr042_write_modes.py, 11 cases; tests/test_cr038_w7_write_modes.py re-pointed) D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09 — migration 0036 is HUMAN-REVIEW-PENDING with its ledger row)
# gates: see the CR-042 lane report — RED proofs quoted verbatim for the constant, the refusal and the BR-MET-127 survival
# exceptions: `replace` is WITHDRAWN and refused rather than accepted-and-ignored; the reasoning is in `normalize()`'s own docstring · `apply()` changes a rule's SEVERITY, which is sanctioned by CR-036 (g) verbatim and bounded three ways (committed scopes only, the engine's verdict stamped not erased, WARNING still posts the flag) — the reasoning is in that function's own docstring
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

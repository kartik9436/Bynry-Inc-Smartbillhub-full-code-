# ── Trace ──────────────────────────────────────────────
# Change:   CR-049 task 8 — "Note a template or item change as a change: the
#           audit trail on the wording itself." The third clause of the PO's
#           sentence, and the only one of the three that was not a promise this
#           product had already made and not kept.
# Rules:    BR-NOT-027 part 3 (a change to a template is NOTED AS A CHANGE, so
#           the wording itself carries a trail — PO 2026-08-30) ·
#           BR-NOT-028 (PROPOSED, written by this lane and NOT ratified: the
#           trail is DERIVED from the append-only version rows and is never
#           stored a second time) · BR-BIL-026 (an edit is a new version; the
#           version is PINNED at send) · BR-NOT-025 (a pinned version is
#           archived, never deleted) · BR-BIL-027 (System Admin publishes) ·
#           BR-NOT-026 (two template table pairs behind one screen) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 4 (financial immutability
#           — nothing here writes) · rule 7 (every money action writes
#           audit_log — the template writes already do; this module adds no
#           write and therefore needs no new row) · hard-won law 1 (a comment
#           claiming a guarantee is not the guarantee) · law 5 (one generated
#           file — a second copy of the wording is a copy that can drift)
# Tests:    06-backend/tests/test_cr049_t8_template_change_trail.py
# Impacts:  apps/notifications/templates_api.py (serves `changed_fields` on
#           every version row and mounts
#           GET /template-catalog/{code}/changes/{version_id}) ·
#           apps/notifications/template_service.py (`save_draft`'s EXISTING
#           audit row gains `changed_fields` + `changed_from_version`; no new
#           row and no new table) · 07-frontend/src/features/notifications/
#           TemplateDetail.tsx (the version history's Changed cell and the
#           impact detail the pin count opens).
# ───────────────────────────────────────────────────────
"""What moved in the wording, and which sent documents still stand on the
wording it moved away from.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this module answers, to a System Admin and
ultimately to a regulator, *"which customers hold a letter written in wording
this utility has since changed?"*. A wrong answer here is not a broken screen: it
is a utility telling a regulator that nobody was affected by an edit that
affected three thousand people. That is the same class of authority
`frozen_documents.reproduce` carries when it decides whether a reproduction may
be called the original — one step earlier in the same chain. AI-authored
2026-08-30 under the PO ruling of 2026-08-09 (*"AI will do it; we will review it
later as human"*); row in `12-governance/09-human-review-ledger.md`, glob in
`10-scripts/gates/human_owned.txt`.

PO, 2026-08-30, verbatim — and the middle clause is this file's whole reason to
exist: *"any legal document when send - it is freezed - we should keep all
underline data, but actual leter and PDF should be freeze - **any changes to
tempalte or any items hsould be noted as changed**; that way it will keep the
santity of the legal documents; otherwie everytime we reproduce it using data in
table, we might change something about it and that is not correct"*.

╔══════════════════════════════════════════════════════════════════════════╗
║  WHAT THIS ADDS THAT VERSION HISTORY DOES NOT — measured, not assumed.   ║
╚══════════════════════════════════════════════════════════════════════════╝
The product already versions a template, and versions it well. `BR-BIL-026`
makes every edit a new append-only row; `notification_template_versions` keeps
every body; migration `0006`'s `trg_ntv_append_only` refuses to let a published
body, subject or preheader move; and the SET-10 history table lists every
version with its date, its author id and a COUNT of the messages pinned to it.
So *"the wording changed"* is already recorded and both wordings are already
readable. **This module is not a second version history and must never become
one.**

**TWO THINGS ARE MISSING, AND THE SECOND IS THE ONE THE PO's SENTENCE IS ABOUT.**

1. **WHAT MOVED.** Nothing in this product diffs two versions. Neither does the
   audit trail, and that is worth stating precisely because the register says
   otherwise: `template_service.save_draft` writes an `audit_log` row whose
   `after` holds the class, the variant, the new version number, the status and
   the effective date — **and not one character of the wording**. `OQ-255` says
   *"`audit_log` holds the before/after of `template.saved`"*, which is true of
   the ROW and false of the WORDING. Reading the audit trail tells you an edit
   happened and cannot tell you what it did, so a person asked *"did last
   March's edit touch the dispute-rights paragraph?"* had to open two versions
   and compare them by eye.
2. **WHICH ALREADY-SENT DOCUMENTS WERE BUILT ON THE WORDING THAT MOVED.** The
   history's `pinned_by` cell is a bare integer — *"pinned by 3,412 sent"* —
   with no way to reach a single one of them. A version list can say HOW MANY;
   it cannot say WHICH, and WHICH is what a regulator and a complaining customer
   actually ask. **It is only answerable at all since today**: `CR-049` tasks 2,
   3 and 4 gave every sent document a kept copy with an id, so an impact row can
   hand over the letter itself instead of a promise that one existed.

╔══════════════════════════════════════════════════════════════════════════╗
║  WHY THIS IS DERIVED AND NOT A SECOND TABLE (BR-NOT-028, PROPOSED)       ║
╚══════════════════════════════════════════════════════════════════════════╝
A "template change log" table is the obvious build, and here it would be wrong
for a reason that is a fact about this schema rather than a preference:

  * a published version's `body`, `subject`, `preheader`, `version`,
    `effective_from`, `template_id` and `tenant_id` **cannot be updated** —
    `notifications/0006`'s trigger raises on any of them, `billing/0019` does the
    same one module over, and `save_draft` only ever INSERTS;
  * a pin is frozen onto a sent row for ever (hard rule 4), and the version it
    names can never be deleted (`BR-NOT-025`, enforced at the database by
    `notifications/0017` since 2026-08-30).

Both inputs are immutable, so a diff computed today is the same diff computed on
the day of the edit, for ever. A stored copy could only ever disagree with the
rows it was copied from — hard-won law 5's *"one generated file … derive views on
demand, never commit them"*, in a database.

**WHAT IS GENUINELY NOT DERIVABLE IS LEFT ALONE.** *"Softened wording"* — the
author's own account of WHY — is a judgement a person makes, has no column, and
is `OQ-255`(b), open with the PO. This module never invents one: it reports which
FIELDS moved and by how many lines, and the screen goes on saying *"no change
note recorded"* exactly as it did before. A derived diff is not an author's note
and must not be dressed as one.

╔══════════════════════════════════════════════════════════════════════════╗
║  THE PIN IS POLYMORPHIC, AND THAT IS SAFE HERE — checked, not assumed.   ║
╚══════════════════════════════════════════════════════════════════════════╝
`BR-NOT-025` records the measurement: of 181 `outbound_messages` rows, **94
carry a BILL template's id**, because `template_id` is a plain UUID column
shared by two template systems (`BR-NOT-026`: two table pairs behind one
screen). This module filters by a specific notification version's `template_id`
AND its `version`, and a UUID does not collide, so a bill template's pins can
never be counted as this variant's.

What that does mean is stated rather than hidden: **this module answers for
NOTIFICATION templates only.** A bill template version holds a `layout_key` and
options — a layout choice, not wording — so its trail is a different and smaller
question, filed as `OQ-1165` rather than guessed at.

╔══════════════════════════════════════════════════════════════════════════╗
║  WHO COUNTS AS "ALREADY SENT" — and the two rows that never do.          ║
╚══════════════════════════════════════════════════════════════════════════╝
A row counts when it has a `sent_at` — the moment `dispatcher._mark_sent`
stamped it and it left the building. That is a FACT rather than a status word,
so it survives the status vocabulary growing (it has grown twice) and it can
never count a row that is still `queued`, which would tell a regulator a
customer holds a letter nobody has posted.

Two kinds are excluded, and both exclusions are IMPORTED from
`frozen_documents` rather than restated here, because two copies of a scope rule
are free to drift into two different answers:

  * an **in-app staff alert** — the PO ruled the channel out of the document
    freeze (*"we dont have to worry about in-app message those are mostly FYI"*)
    and it goes to a staff inbox, never to a customer (`BR-NOT-019`);
  * a **send test** — a rehearsal addressed to the person who pressed the
    button (`BR-NOT-024`'s third bucket).

Neither is a legal document, so neither belongs in an answer about who holds one.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Any

from apps.notifications import frozen_documents, models
from apps.notifications import template_models as tm
from apps.tenancy import document_store

#: The three fields a version can hold wording in. `body` exists on every class;
#: `subject` and `preheader` are email-only (A19 r8) and are NULL elsewhere — so
#: "this class has no subject" and "somebody emptied the subject" are different
#: rows and must stay different answers, which is what `_field_change`'s
#: None-versus-"" tests are for.
FIELD_BODY = "body"
FIELD_SUBJECT = "subject"
FIELD_PREHEADER = "preheader"

#: Reported in the order a person reads a letter, not alphabetically: what it is
#: about, the line under it, then the letter.
WORDING_FIELDS = (FIELD_SUBJECT, FIELD_PREHEADER, FIELD_BODY)

#: How many impacted documents `documents_on` returns in one page. The impact of
#: an edit to a chatty template is thousands of messages; a screen shows the
#: newest handful and the COUNT carries the rest. Never unbounded — this is the
#: query that would otherwise drag 3,412 rows through the process to draw one
#: panel, which is the mistake `document_store.manifest` already had to fix once
#: by pushing an upper bound into SQL.
IMPACT_PAGE = 20


@dataclass(frozen=True)
class FieldChange:
    """One wording field that moved between two versions.

    `lines_added` / `lines_removed` are a SIZE, not a summary. The words
    themselves are in the version rows and this module never paraphrases them: a
    diff rendered as prose would be this product putting words in an author's
    mouth, which is exactly what `OQ-255`(b) is open about.
    """

    field: str
    lines_added: int
    lines_removed: int
    #: The field had no value at all before (a subject line added to a class
    #: that had none), or has none now. Told apart from an ordinary edit because
    #: *"the subject line was removed"* and *"the subject line was reworded"*
    #: are different facts about a letter.
    added: bool
    removed: bool


@dataclass(frozen=True)
class VersionChange:
    """The change that CREATED one version — never the version itself."""

    version: int
    version_id: str
    previous_version: int | None
    fields: tuple[FieldChange, ...]
    changed_at: Any
    author_label: str

    @property
    def is_first_version(self) -> bool:
        """The first version of a variant supersedes nothing.

        It is NOT "no change", and the difference matters on screen: a blank
        would read as *"nobody wrote this"*, which is the false statement
        `DEF-2479` made this history stop making. The first version is the
        wording ARRIVING, and it says so.
        """
        return self.previous_version is None


@dataclass(frozen=True)
class SentOnVersion:
    """One already-sent document standing on a version's wording.

    ⚠ `document_id` is the KEPT COPY (`CR-049` tasks 2 and 3) or `None`. It is
    the difference between *"3,412 customers hold the old wording"* and *"here
    is the letter one of them is holding"*, and it is the reason this task
    waited for the document store rather than being built beside it.
    """

    message_id: str
    channel: str
    status: str
    sent_at: Any
    account_id: str | None
    document_id: str | None
    document_kept: bool
    display_name: str | None


def _lines(value: str | None) -> list[str]:
    return (value or "").splitlines()


def _field_change(field: str, before: str | None, after: str | None) -> FieldChange | None:
    """One field's movement, or `None` when it did not move.

    ⚠ **`None` AND `""` ARE DIFFERENT, AND BOTH ARE COMPARED AS TEXT.** A class
    with no subject holds NULL on every version, so it must report nothing at
    all rather than an empty change; a subject a person cleared to `""` DID move
    and must report a removal. The `is None` / `== ""` tests below are the only
    place that distinction lives, and collapsing them would make every SMS
    template claim its subject changed on every edit.
    """
    if before == after:
        return None
    was_blank = before is None or before == ""
    is_blank = after is None or after == ""
    if was_blank and is_blank:
        # NULL → "" or back. A schema detail; nothing a reader of the letter
        # could ever observe, so reporting it would be noise in a legal trail.
        return None
    diff = list(difflib.ndiff(_lines(before), _lines(after)))
    return FieldChange(
        field=field,
        lines_added=sum(1 for line in diff if line.startswith("+ ")),
        lines_removed=sum(1 for line in diff if line.startswith("- ")),
        added=was_blank,
        removed=is_blank,
    )


def changes_between(
    previous: tm.NotificationTemplateVersion | None,
    current: tm.NotificationTemplateVersion,
) -> tuple[FieldChange, ...]:
    """Which wording fields moved from `previous` to `current`.

    `previous=None` is the FIRST version of a variant: everything it holds is
    new, so every non-empty field is reported as ADDED rather than as an edit.
    """
    return tuple(
        change
        for change in (
            _field_change(
                field,
                None if previous is None else getattr(previous, field),
                getattr(current, field),
            )
            for field in WORDING_FIELDS
        )
        if change is not None
    )


def author_label(version: tm.NotificationTemplateVersion) -> str:
    """Who the change is attributed to — an id, or `platform seed`, never a name.

    Copied in SHAPE from `templates_api._author_label` and deliberately not
    imported from it: that module imports THIS one, and a service reaching back
    into its own route module for a helper is the import cycle that would end
    with the route as the home of a rule. `OQ-255`(a) is why neither can do
    better than an id — identity is another module's table and publishes no
    display-name read (B11 F-3).

    `platform seed` is a REAL answer rather than a fallback: provisioning writes
    `created_by = NULL` on purpose, because no person published those bodies.
    """
    who = version.published_by or version.created_by
    return str(who) if who else "platform seed"


def change_for(
    current: tm.NotificationTemplateVersion,
    previous: tm.NotificationTemplateVersion | None,
) -> VersionChange:
    """The change that created `current`, given the version it followed."""
    return VersionChange(
        version=current.version,
        version_id=str(current.pk),
        previous_version=previous.version if previous is not None else None,
        fields=changes_between(previous, current),
        changed_at=current.created_at,
        author_label=author_label(current),
    )


def previous_of(
    version: tm.NotificationTemplateVersion,
) -> tm.NotificationTemplateVersion | None:
    """The version immediately below this one in its variant's chain.

    ⚠ **NOT `version - 1`.** Version numbers are `Max(version) + 1` per variant
    and an unpinned DRAFT may be deleted (`template_service.delete_version`,
    US-NOT-006 TC-5), so a chain can legitimately read 1, 2, 4. Asking for the
    highest row BELOW this one is the only form that survives that; arithmetic
    would answer *"no previous version"* on a variant somebody tidied a draft
    out of, and the trail would silently start again from scratch on a letter
    that had been reworded four times.
    """
    return (
        tm.NotificationTemplateVersion.objects.filter(
            tenant_id=version.tenant_id,
            template_id=version.template_id,
            version__lt=version.version,
        )
        .order_by("-version")
        .first()
    )


def _messages_on(version: tm.NotificationTemplateVersion) -> Any:
    """Every queue row pinned to this exact version — tenant-scoped in the app layer.

    Scoped here AND by RLS, for the reason `document_store.for_source` states in
    its own words: the app-layer filter is provable on any vendor, the database
    refuses a foreign row only on PostgreSQL, and a guarantee that holds only
    where nobody tests it is hard-won law 1's shape.
    """
    return models.OutboundMessage.objects.filter(
        tenant_id=version.tenant_id,
        template_id=version.template_id,
        template_version=version.version,
    )


def _left_the_building(query: Any) -> Any:
    """Narrow a pin query to the rows a customer is actually holding.

    `sent_at__isnull=False` rather than `status="sent"`: the stamp is a fact
    about what happened, the status vocabulary is a word that has already grown
    twice, and a row that is `delivered` or `bounced` was still SENT. The two
    exempt kinds are imported, never restated — see the module docstring.
    """
    return query.filter(
        sent_at__isnull=False,
        channel__in=tuple(frozen_documents.FREEZE_CHANNELS),
    ).exclude(source_type__in=tuple(frozen_documents.FREEZE_EXEMPT_SOURCE_TYPES))


def documents_on(
    version: tm.NotificationTemplateVersion,
    *,
    limit: int = IMPACT_PAGE,
) -> tuple[int, tuple[SentOnVersion, ...]]:
    """*"Which already-sent documents were built on this wording?"* — count, then page.

    Returns the TOTAL first and the page second, in that order, because a caller
    that renders the page and forgets the total has silently answered a smaller
    question than the one it was asked.

    ⚠ **THE COUNT AND THE PAGE ARE THE SAME QUERY.** A total over one filter and
    a page over another is how a panel comes to say *"3 of 3,412"* about two
    different sets — which on this screen would be a false statement to a
    regulator rather than an off-by-one.
    """
    query = _left_the_building(_messages_on(version))
    total = query.count()
    rows = list(query.order_by("-sent_at", "-created_at")[:limit])
    return total, tuple(_impact_row(row) for row in rows)


def _impact_row(message: Any) -> SentOnVersion:
    """One sent message, with the kept copy of it if there is one.

    The lookup is `document_store.for_source` — tenancy's published door, the
    same one the reprint route reads. It answers `document_not_stored` rather
    than an empty success, so `document_kept=False` here is a STATEMENT and
    never an inference from a missing value.
    """
    lookup = document_store.for_source(
        source_type="outbound_message",
        source_id=message.pk,
    )
    document = lookup.document
    return SentOnVersion(
        message_id=str(message.pk),
        channel=message.channel,
        status=message.status,
        sent_at=message.sent_at,
        account_id=str(message.account_id) if message.account_id else None,
        document_id=str(document.id) if document is not None else None,
        document_kept=document is not None,
        display_name=document.display_name if document is not None else None,
    )


@dataclass(frozen=True)
class ChangeRecord:
    """The whole answer to *"what changed, and who is holding the old wording?"*

    Both halves in one object on purpose. The PO asked them as one question —
    *"noted as changed; that way it will keep the santity of the legal
    documents"* — and a caller able to fetch the first without the second will,
    which is the version history that already exists.
    """

    change: VersionChange
    superseded_version: int | None
    superseded_documents: int
    superseded_sample: tuple[SentOnVersion, ...]
    sample_truncated: bool


def record(version: tm.NotificationTemplateVersion, *, limit: int = IMPACT_PAGE) -> ChangeRecord:
    """The change that created this version, plus the impact on the one before it.

    ⚠ **THE IMPACT IS THE PREVIOUS VERSION'S, NOT THIS ONE'S**, and that is the
    whole point of the record. *"Who is affected by the edit I just published?"*
    means *"who is holding the wording I have just moved away from?"* — the
    documents pinned to THIS version already carry the new words and need no
    explaining to anybody.
    """
    previous = previous_of(version)
    if previous is None:
        return ChangeRecord(
            change=change_for(version, None),
            superseded_version=None,
            superseded_documents=0,
            superseded_sample=(),
            sample_truncated=False,
        )
    total, sample = documents_on(previous, limit=limit)
    return ChangeRecord(
        change=change_for(version, previous),
        superseded_version=previous.version,
        superseded_documents=total,
        superseded_sample=sample,
        sample_truncated=total > len(sample),
    )


def changed_field_names(
    current: tm.NotificationTemplateVersion,
    previous: tm.NotificationTemplateVersion | None,
) -> list[str]:
    """The field names that moved — the VALUE a table cell holds.

    A table cell holds a value and a control holds a label (PO ruling
    2026-08-30, after ten removals of prose from screens in one sitting). So
    this returns `["subject", "body"]`, the screen writes *"Subject · Letter"*,
    the sentence that explains it is the tooltip's — and the words themselves
    stay in the editor, where they belong.
    """
    return [change.field for change in changes_between(previous, current)]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-049 task 8 (sources: 12-governance/11-change-requests.md CR-049 step 5c task 8 + steps 6 / 6-bis / 6-ter · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-027 part 3 + BR-NOT-025 + BR-NOT-026 · 12-governance/01-open-questions.md OQ-255 · 06-backend/apps/notifications/migrations/0006_rls_w3_notification_templates.py, the trigger this whole derivation rests on)
# generated: 2026-08-30 by the CR-049 task 8 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — the decisive case (edit a published notice, then ask what changed and who holds the old wording) was run before this module existed and failed on ModuleNotFoundError; the route answered 404 before it was mounted; the sent-only narrowing was proved by dropping it and watching a QUEUED row and a SEND TEST appear in a regulator's answer. Verbatim transcripts in 06-backend/tests/test_cr049_t8_template_change_trail.py.
# exceptions: (1) NO CHANGE-RECORD TABLE. Both inputs are immutable by database trigger, so a stored copy could only drift from the rows it was copied from (hard-won law 5). BR-NOT-028 is PROPOSED, not CONFIRMED — this lane wrote the rule it derived and did not ratify it.
#         (2) NO AUTHOR'S NOTE IS INVENTED. "Softened wording" is OQ-255(b) and stays with the PO; this module reports FIELDS and LINE COUNTS and never paraphrases a body.
#         (3) NOTIFICATION TEMPLATES ONLY. A bill template version holds a layout choice rather than wording (BR-NOT-026), so its trail is a different and smaller question — OQ-1165, filed rather than guessed.
#         (4) THE AUTHOR IS AN ID. OQ-255(a) — identity is another module's table (B11 F-3) and publishes no display-name read.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

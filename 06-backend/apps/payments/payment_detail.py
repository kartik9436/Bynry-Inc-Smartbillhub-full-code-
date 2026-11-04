# ── Trace ──────────────────────────────────────────────
# Change:   CR-137-BRC07 · P3.1 (`GET /payments/{id}` — *"there is no such read,
#           which is why a payment has no address"*) and P3.4 (the `audit_log`
#           read behind the history panel — *"what makes Cancel honest: a
#           cancelled payment does not vanish"*). Blueprint
#           `05-prototype/06 Payments Page Blueprint.pdf` screen 2·2, p035 (on this
#           branch since `da07c7f8d`).
# Story:    US-PAY-004 (S33 · TC-7 isolation: *"a Brazos Bend payment id in the
#           detail URL 404s (RLS)"* — the one ratified test case that has always
#           described a detail address)   Screens: S33 · S35 · 2·2
# Rules:    CLAUDE.md hard rule 1 (tenant scoping — the read is scoped in the
#           app AND by RLS FORCE) · hard rule 2 (money is a decimal STRING
#           beside its CHAR(3)) · hard rule 7 (the trail this reads) ·
#           `NFR-3` (the history is paginated IN SQL) · B14 rule 31 (no
#           database id is the visible value of a field) · B14 rule 33
#           (rationale is ZERO words on screen) · B14 rule 35 (a catalogue is
#           written in its own language — the trail serves CODES, never English
#           composed here) · BR-AUD-010 (audit's per-entity read service) ·
#           BR-AUD-002 / BR-AUD-012 (append-only, and pruned) · BR-PAY-021
#           (both dates, always) · BR-TEN-042 (one currency per tenant)
# Tests:    06-backend/tests/test_cr137_p3_detail_cancel_receipt.py
# Impacts:  apps/payments/detail_api.py (the two doors) ·
#           apps/payments/selectors.payment_row (the eleven facts, reused
#           rather than restated) · apps/audit/selectors.entity_trail +
#           audit_row + actor_names (the trail, read through audit's own
#           published callables — no audit column is touched from here)
# ───────────────────────────────────────────────────────
"""ONE payment, at its own address — and what has happened to it.

THE SENTENCE THIS FILE EXISTS FOR
═════════════════════════════════
`paymentDetail.tsx` opens with a disclosure, not a page, and says why in its
own words: *"There is no `GET /payments/{id}` … There is no detail ROUTE
either."* It then lists what a page at its own URL would need and asks nobody
to re-derive it. **This is the first of those three things.**

THE READ TAKES A NUMBER *OR* AN ID, AND THE NUMBER IS WHY
═════════════════════════════════════════════════════════
⚠ **THE DRAWING PUTS THE `PMT-` NUMBER IN THE ADDRESS BAR**, verbatim on p035:
`agreed: /:tenant/payments/PMT-2609-000418`. B14 rule 31 says no database id is
ever the visible value of a field, and an address a clerk copies into a message
to a colleague is about as visible as a value gets. So `resolve_payment` accepts
**either** spelling and the front end links with the number:

  * a `PMT-` number — `uq_payments_no` makes it unique per tenant, so the lookup
    is exact and cannot become ambiguous later;
  * a uuid — because `applied_to`, the reversal link and every existing caller
    inside the product already hold ids, and a read that refused them would make
    every internal link go through a second lookup to print a nicer URL.

**Neither spelling widens what a caller can see.** Both filter on
`tenant_id=_tenant_id()` before anything else, and RLS FORCE is the second,
independent guarantee. US-PAY-004 TC-7 is the ratified case: another tenant's
payment id in the detail URL answers **404**, never 403 — existence never leaks.

THE ELEVEN FACTS ARE NOT RESTATED HERE
══════════════════════════════════════
`selectors.payment_row` already builds them and `PaymentDetailPanel` already
draws them. This read returns that row and ADDS the three things a page has that
a disclosure inside a list row cannot have: **the header strip**, **the history**
and **the actions' own preconditions**. A second copy of the row would be a
second place for the "Applied to" netting and the BR-PAY-021 date pair to drift
— which is the defect `appliedBills` already exists to prevent, one screen along.

THE HISTORY IS HONEST ABOUT BEING INCOMPLETE, AND IT SAYS SO IN A CODE
══════════════════════════════════════════════════════════════════════
⚠ **`audit_log` IS PRUNED AND NO ROW TYPE IS EXEMPT** — PO ruling 2026-09-23,
verbatim: *"keep the same rule s; when audit log is delete - it is deleted thats
okay"* (`OQ-1340` CLOSED, `CR-137-BRC07` §1). Two consequences and the second is
the one a builder trips on:

  1. **No screen, document or docstring may call this a permanent record.** Not
     *until it is answered* — **ever**. This file does not, and the sentence
     below is the only place it is discussed.
  2. **THE HONEST BUILD IS SILENCE, NOT A DISCLAIMER.** B14 rule 33 puts
     RATIONALE at ZERO words on screen, so the history panel explains no
     retention policy: it simply never claims permanence. The read carries
     `HISTORY_NOT_PERMANENT` on `unavailable[]` so the fact is in the payload,
     in the register and in this file — where a builder reads it — and **not**
     in a sentence a clerk has to read every time they open a payment.

**`unavailable[]` is a code list, never clerk copy.** Every other read in this
module uses `problems[]`/`unavailable[]` the same way: the screen groups on the
code and renders its own catalogue sentence, or renders nothing at all.

`NFR-3`: THE TRAIL IS PAGINATED IN SQL
══════════════════════════════════════
A busy payment's trail is unbounded — a recording, an allocation, a batch seal,
a reconciliation, a correction, a resend, a cancel, and every one of those again
on a payment somebody keeps working on. `history_queryset` returns a QuerySet
that audit ordered with `ix_audit_entity` and **this file never calls `list()` on
it**; `detail_api` hands it to `StandardPagination`, which takes the page in the
database. `apps/metering/connection_reads._history` materialises its whole trail
and is the shape this deliberately does not copy.
"""

from __future__ import annotations

import uuid as uuid_module
from importlib import import_module
from typing import Any

from django.db.models import QuerySet

from apps.payments import models, selectors
from core import errors
from core import tenancy as core_tenancy

#: What `unavailable[]` may carry on a detail read. Codes, not sentences — the
#: screen owns the words (B14 rule 33 / rule 35), and G32 has no `message_key`
#: to resolve because none of these is ever RAISED at a clerk.
#:
#: ⚠ `HISTORY_NOT_PERMANENT` is the `OQ-1340` ruling in machine-readable form.
#: It is NOT a disclaimer to render: see the module docstring.
HISTORY_NOT_PERMANENT = "history_is_pruned_like_every_audit_row"
HISTORY_UNREADABLE = "history_read_unpublished"
RECONCILIATION_HAS_NO_REFERENCE = "match_set_has_no_reference_series"
COUNTER_SESSION_UNREADABLE = "counter_session_read_unpublished"

#: audit's published per-entity read (BR-AUD-010) and its payload builder. Named
#: here so the two resolutions read as one contract rather than as two strings
#: scattered through the functions below.
AUDIT_MODULE = "audit"
AUDIT_TRAIL_READ = "entity_trail"
AUDIT_ROW_BUILD = "audit_row"
AUDIT_NAMES_READ = "actor_names"

#: The `entity_type` every payments audit row is written under — `services`,
#: `reversal`, `transfer`, `reapply` and `cheques` all pass the bare string
#: `"payment"`, and `core.audit.money_action` stores it verbatim.
AUDIT_ENTITY_PAYMENT = "payment"
#: `amendments.audit_shape`'s spelling for a correct-reference row (`DEF-PAY-10735`).
AMENDMENT_ENTITY_TYPE = "payments"

#: Keys of an audit row's `after` payload that are safe to show a clerk as the
#: drawing's NOTE column — the words a PERSON typed or chose, and nothing else.
#:
#: ⚠ **AN ALLOW LIST RATHER THAN THE WHOLE PAYLOAD, AND `summarize` IS WHY.**
#: `apps.audit.selectors.summarize` renders `key: old → new` for every changed
#: field; that is the ratified S61 Summary column and it is exactly wrong here.
#: It is English composed in Python, so the eleven catalogues cannot translate it
#: (B14 rule 35), it is far past rule 33's six words, and it prints raw column
#: names and — on some rows — raw ids at a clerk (rule 31). The history panel
#: shows WHAT happened as a code the screen translates, and the note the person
#: wrote. Anything else stays in `GET /audit-log`, which is the screen for it.
NOTE_KEYS = ("note", "reason", "memo")


def _tenant_id() -> Any:
    """CLAUDE.md rule 1 — no query is built without `app.tenant_id`.

    Refuses rather than defaulting, for `selectors._tenant_id`'s reason: with
    the GUC unset a PostgreSQL read matches **zero rows and reports success**,
    which is indistinguishable from a payment that does not exist.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """A neighbour's published callable, or None while it has not published one.

    Byte-for-byte `selectors._resolve`, and deliberately a second definition:
    importing a private helper across module files to save six lines is how
    `apps/payments/api._actor` became a dependency of two other API modules
    (`reversal_api` records what that cost).
    """
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _looks_like_uuid(reference: str) -> bool:
    try:
        uuid_module.UUID(str(reference))
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def resolve_payment(reference: Any) -> models.Payment | None:
    """This tenant's payment, addressed by its `PMT-` number or by its id.

    `None` — never a raise — when there is no such payment **in this tenant**.
    The caller turns that into 404, so a payment that does not exist and another
    tenant's payment are the same answer (US-PAY-004 TC-7, HR-1/G4).

    ⚠ **THE TENANT FILTER IS WRITTEN OUT EVEN THOUGH RLS FORCE IS ON.** Both
    guarantees, never one: RLS is absent on the SQLite developer tier the whole
    default suite runs on, so a test that proved isolation there would be
    proving nothing (hard-won law 7's *incapable of failing* shape).
    """
    tenant_id = _tenant_id()
    queryset = selectors.payment_queryset()
    text = "" if reference is None else str(reference).strip()
    if not text:
        return None
    if _looks_like_uuid(text):
        return queryset.filter(pk=text).first()
    # Not a uuid, so it can only be the number. Exact match: `uq_payments_no`
    # makes it unique per tenant, and a prefix or case-insensitive match would
    # turn one address into a search that could start resolving to two payments
    # the day a tenant's series changes shape.
    return queryset.filter(tenant_id=tenant_id, payment_no=text).first()


# ── the header strip (p035 ⑤ ⑥ and the two facts beside them) ───────────────
def _reconciled(payment: models.Payment) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    """⑥ WHERE THE BANK MATCHED IT — or an honest absence.

    ⚠ **THE DRAWING NAMES A REFERENCE THIS PRODUCT DOES NOT MINT.** p035 draws
    `BRM-2609-0041` under RECONCILED. `bank_rec_match_sets` has no code column
    and no series: `bankrec_read._match_set_panel` serves `match_set_id`, a bare
    uuid, which B14 rule 31 forbids putting on a screen. So this serves the
    facts that ARE established — the batch's own `DEP-` code, when it was
    matched, and how many bank lines and sibling batches the tie holds — and
    puts `RECONCILIATION_HAS_NO_REFERENCE` on `unavailable[]` rather than
    inventing a number or printing an id. FILED as `OQ-PAY-12602`.

    `None` is the ordinary answer and is not a fault: most payments are in no
    batch, and a batch that has not been reconciled has nothing to show.
    """
    batch_id = payment.deposit_batch_id
    if batch_id is None:
        return None, ()
    try:
        from apps.payments import bankrec_models as bankrec
        from apps.payments import bankrec_read
    except ImportError:  # pragma: no cover - defensive
        return None, ()
    batch = bankrec.DepositBatch.objects.filter(tenant_id=payment.tenant_id, pk=batch_id).first()
    if batch is None:
        return None, ()
    banked_not_matched = {
        "batch_code": batch.code,
        "batch_status": batch.status,
        "matched_at": None,
        "bank_line_count": None,
        "batch_count": None,
        "bank_posted_on": None,
        "reconciled_at": None,
        "reference": None,
    }
    # ⚠ THE BATCH'S OWN STATUS DECIDES WHETHER IT IS TIED, NOT THE LINK.
    # `bank_lines.deposit_batch_id` is write-once (migration 0005), so after
    # Unreconcile the batch is `unmatched` again while its old line still
    # points at it. Reading the link alone would call that batch matched.
    if batch.status not in (bankrec.BATCH_MATCHED, bankrec.BATCH_RECONCILED):
        # Banked but not tied to a statement yet. A real state, said as one.
        return banked_not_matched, ()
    # ⚠ DEF-PAY-10323 — A TIE HAS TWO SHAPES AND THIS READ ONCE KNEW ONE.
    # A CS-17 match SET lives in `bank_rec_match_members`; an ordinary 1:1
    # match lives on `bank_lines.deposit_batch_id` and has no set at all. This
    # read looked only for the set, so every batch reconciled 1:1 — the common
    # case — served `matched_at: null` and the page drew *Banked, not matched*
    # beside a *Cleared* status. S39's own readers already know both shapes
    # (`bankrec_read.batch_detail`), so this asks them rather than a third copy.
    panel = bankrec_read._match_set_panel(batch)
    if panel is not None:
        matched_at = panel["matched_at"]
        line_days = [row["posted_on"] for row in panel["bank_lines"] if row["posted_on"]]
        bank_line_count = len(panel["bank_lines"])
        batch_count = len(panel["batches"])
    else:
        line = bankrec_read._bank_line_row(
            bankrec.BankLine.objects.filter(tenant_id=batch.tenant_id, deposit_batch=batch).first()
        )
        if line is None:  # pragma: no cover - a matched batch always has its line
            return banked_not_matched, ()
        # A 1:1 link has no timestamp column of its own; the trail is the
        # single source of *when* (`DepositBatchEvent`'s docstring).
        matched_at = _last_event_at(bankrec, batch, bankrec.EVENT_MATCHED)
        line_days = [line["posted_on"]] if line["posted_on"] else []
        bank_line_count = 1
        batch_count = 1
    return {
        "batch_code": batch.code,
        "batch_status": batch.status,
        "matched_at": matched_at,
        # COUNTS, not ids — the drawing's own sub-line is *"Three batches, one
        # credit"*, which is a count and not a list of primary keys.
        "bank_line_count": bank_line_count,
        "batch_count": batch_count,
        # The BANK's date for this money — the latest statement line in the tie.
        "bank_posted_on": max(line_days) if line_days else None,
        "reconciled_at": (
            _last_event_at(bankrec, batch, bankrec.EVENT_RECONCILED)
            if batch.status == bankrec.BATCH_RECONCILED
            else None
        ),
        # ⚠ Null ON PURPOSE — see this function's docstring.
        "reference": None,
    }, (RECONCILIATION_HAS_NO_REFERENCE,)


def _last_event_at(bankrec: Any, batch: Any, event: str) -> str | None:
    """When `event` last happened to `batch`, read off its append-only trail."""
    row = (
        bankrec.DepositBatchEvent.objects.filter(
            tenant_id=batch.tenant_id, batch=batch, event=event
        )
        .order_by("-occurred_at", "-created_at")
        .first()
    )
    return None if row is None else row.occurred_at.isoformat()


#: `idempotency.SOURCE_AGENT`'s namespace — `agent|<provider key>:<their id>`.
_AGENT_KEY_PREFIX = "agent|"
INTEGRATIONS_MODULE = "integrations"
PROVIDER_NAME_READ = "provider_display_name"


def _agent_name(payment: models.Payment) -> str | None:
    """`DEF-PAY-10015` — the payment agent that took this payment, by name.

    Only an `agent` payment has one, and only the provider key its own
    idempotency key carries names it (`idempotency.inbound_payment_key`), so
    nothing is guessed: a counter payment still answers `None`. The name is
    the connector's own (`integrations.selectors.provider_display_name`).
    """
    if getattr(payment, "origin", None) != models.PAYMENT_ORIGIN_AGENT:
        return None
    key = str(getattr(payment, "webhook_key", None) or "")
    if not key.startswith(_AGENT_KEY_PREFIX) or ":" not in key:
        return None
    provider = key[len(_AGENT_KEY_PREFIX):].split(":", 1)[0]
    read = _resolve(INTEGRATIONS_MODULE, PROVIDER_NAME_READ)
    return None if read is None else read(provider)


def _reversed_for(payment: models.Payment) -> str | None:
    """`DEF-PAY-10016` — the reason this payment was taken back, or `None`.

    The original keeps its own status by design (`reversal.py`: a reversal is
    a NEW row, hard rule 4), so a returned ACH still reads *Cleared*. This is
    the fact beside it: the reversing row's reason CODE (`nsf`), which the
    status cell renders in the catalogue's words (*Returned by the bank*).
    """
    if payment.reverses_payment_id is not None:
        return None
    reversing = (
        models.Payment.objects.filter(
            tenant_id=payment.tenant_id, reverses_payment_id=payment.pk
        )
        .order_by("created_at")
        .values_list("reversal_reason", flat=True)
        .first()
    )
    return reversing or None


def _bounce_facts(after: Any) -> dict[str, Any]:
    """`DEF-PAY-10698` · LBX-04 — what a reversal's audit row says about the
    bank's words and the NSF penalty, in the shape the screen draws:
    *"Bank memo: NSF"*, *"+$30.00 NSF fee"*, or the reason it was unticked."""
    after = after if isinstance(after, dict) else {}
    fee = after.get("nsf_fee") if isinstance(after.get("nsf_fee"), dict) else None
    return {
        "bank_memo": after.get("bank_memo") or None,
        "nsf_fee_status": None if fee is None else fee.get("status"),
        "nsf_fee_amount": None if fee is None else fee.get("amount"),
        "nsf_fee_currency": None if fee is None else fee.get("currency"),
        "nsf_fee_invoice_no": None if fee is None else fee.get("invoice_no"),
        "nsf_fee_waived_reason": after.get("nsf_fee_waived_reason") or None,
    }


def _reversal_block(payment: models.Payment) -> dict[str, Any] | None:
    """`DEF-PAY-10698` · LBX-04 — the reversal of THIS payment, as a clerk reads it.

    The bank memo is the REVERSING row's own `memo` (written at INSERT, hard
    rule 4); the NSF penalty is what the reversal's audit row recorded — the fee
    bill's number and amount, or the reason the clerk unticked it. `audit_log`
    is pruned like every audit row (PO 2026-09-23), so after retention the fee
    half reads null while the fee BILL itself stays on the account forever.
    """
    if payment.reverses_payment_id is not None:
        reversing = payment
        original = payment.reverses_payment
    else:
        reversing = (
            models.Payment.objects.filter(
                tenant_id=payment.tenant_id, reverses_payment_id=payment.pk
            )
            .order_by("created_at")
            .first()
        )
        original = payment
    if reversing is None:
        return None
    facts = _bounce_facts(None)
    trail = history_queryset(original)
    if trail is not None:
        row = trail.filter(action__in=("payment.nsf", "payment.reversed")).first()
        if row is not None and isinstance(getattr(row, "after", None), dict):
            if str(row.after.get("reversal_payment_id")) == str(reversing.pk):
                facts = _bounce_facts(row.after)
    facts["bank_memo"] = reversing.memo or facts["bank_memo"]
    return {
        "reversal_no": reversing.payment_no,
        "reason": reversing.reversal_reason,
        **facts,
    }


def _till(payment: models.Payment) -> Any:
    """`DEF-PAY-10734` · L2-03 — the counter session this payment was taken into.

    `payments.counter_session_id` is written at INSERT by the counter door
    (`P2.13`, `DEF-PAY-6226`) and names the till; its `owner` is the clerk who
    opened it. A payment with no till answers `None`, and nothing is guessed
    from the origin — a transfer leg and a bounce are `entry` too.
    """
    session_id = getattr(payment, "counter_session_id", None)
    if session_id is None:
        return None
    from apps.payments import counter_session_models as tills

    return (
        tills.CounterSession.objects.filter(tenant_id=payment.tenant_id, pk=session_id)
        .select_related("owner")
        .first()
    )


def _clerk_name(owner: Any) -> str | None:
    """`identity.User.full_name`, else the e-mail — `counters._person`'s rule."""
    if owner is None:
        return None
    return (getattr(owner, "full_name", "") or "").strip() or getattr(owner, "email", None)


#: `DEF-PAY-10734` · L2-03 (b) — which kind of import brought this money, so
#: the Source cell can say *Lockbox* or *File* instead of the drawing's *Post*
#: (*"Mail"*) for every file. A LABEL only: `origin` stays `import` (CR-132's
#: ruling that the stored words do not move). `lockbox` and `csv` are
#: `payment_import_batches.source_kind`; a metering import run (the IMP-
#: series) is a FILE. The store-network NAME (*"Store · Hy-Vee"*) is served
#: beside this as `store_network` (PO 2026-10-30 Q6: it comes from the file's
#: Network column, never a screen field — `payments/0054`).
IMPORT_KIND_FILE = "file"


def _import_kind(payment: models.Payment) -> str | None:
    if getattr(payment, "origin", None) != "import":
        return None
    row = (
        models.PaymentImportRow.objects.filter(tenant_id=payment.tenant_id, payment_id=payment.pk)
        .select_related("batch")
        .first()
    )
    if row is not None and getattr(row.batch, "source_kind", None):
        return str(row.batch.source_kind)
    return IMPORT_KIND_FILE


def _source(payment: models.Payment) -> dict[str, Any]:
    """⑤ SOURCE — *"Counter, Digital or Post, and who or which provider"*.

    ⚠ **THE STORED WORD TRAVELS, NEVER THE DRAWN ONE** (`selectors.payment_row`
    records the PO's ruling of 2026-09-22 in full): the column holds `entry ·
    webhook · import` and the drawing's *Counter · Digital · Post* are LABELS
    that live in the eleven catalogues.

    **The second half — *who or which provider* — is `CR-136-BRC07`'s counter
    session, and this states its absence rather than guessing.** A payment taken
    at a counter is `entry`, and so is a transfer leg and a bounce; naming a
    clerk from the origin alone would be a claim nothing supports.
    """
    till = _till(payment)
    return {
        "origin": payment.origin,
        "origin_is_derived": bool(getattr(payment, "origin_is_derived", False)),
        # ⛔ SUPERSEDED 2026-10-30 (`DEF-PAY-10734`, L2-03): this read *"The
        # counter session is phase 2's to serve; until its link exists on this
        # row there is nobody to name"*. Phase 2 shipped `counter_session_id`
        # and the hold was never released, so a counter payment read *"taken by
        # Nobody named"*. A payment AGENT still names itself (`DEF-PAY-10015`);
        # otherwise the till's owner is the clerk and its code is the ref.
        "taken_by": _agent_name(payment) or (None if till is None else _clerk_name(till.owner)),
        "counter_session_ref": None if till is None else till.code,
        "import_kind": _import_kind(payment),
        # PO 2026-10-30 Q6 — the store network the file's Network column named;
        # the strip reads *Store · Hy-Vee*. Null on every other payment.
        "store_network": getattr(payment, "store_network", None),
        # ── CR-174-BRC10 · A PAYMENT AGENT'S HALF OF *WHO OR WHICH PROVIDER* ──
        # Where the customer stood (`kiosk`), which machine (`4471`) and, on a
        # returned payment's reversing row, the bank's own code (`R01`). All
        # three are columns written at INSERT; NULL on every payment no agent
        # took, and the screen draws nothing for a null rather than a dash.
        "channel": getattr(payment, "channel", None),
        "terminal": getattr(payment, "terminal", None),
        "return_code": getattr(payment, "return_code", None),
    }


# ── ⑦ the history panel (P3.4) ─────────────────────────────────────────────
def history_queryset(payment: models.Payment) -> QuerySet | None:
    """Every trail row this payment has, newest first — **as a QuerySet**.

    `None` when audit has not published its per-entity read, which the caller
    reports as `HISTORY_UNREADABLE` rather than as an empty history: *"we could
    not read it"* and *"nothing has happened"* are different facts and only one
    of them is safe to draw.

    ⚠ **IT IS NOT MATERIALISED HERE, AND THAT IS `NFR-3`.** `entity_trail`
    already orders on `ix_audit_entity` and takes no page of its own — its own
    docstring says *"callers paginate"*. Returning the QuerySet is what lets
    `StandardPagination` put `LIMIT/OFFSET` in the SQL. A `list()` here would
    read a payment's whole trail into memory to show a clerk ten rows, which is
    `GET /outstandings`' breach one screen along (`DEF-PAY-4221`).
    """
    trail = _resolve(AUDIT_MODULE, AUDIT_TRAIL_READ)
    if trail is None:  # pragma: no cover - audit has published this since W0
        return None
    # ⚠ `DEF-PAY-10735` (L3-05) — *"The change is not shown in the payment's
    # History."* `amendments.audit_shape` writes the correction under entity
    # type `payments` (plural) while every other payment row is `payment`, so
    # this read never met a single `payment.reference_amended` row. Both are
    # read, ORed in ONE query and ordered as before — the plural spelling is
    # already on stored rows (hard rule 4's audit half: history is not
    # rewritten), so changing the writer alone would leave every past
    # correction invisible.
    both = trail(payment.tenant_id, AUDIT_ENTITY_PAYMENT, payment.pk) | trail(
        payment.tenant_id, AMENDMENT_ENTITY_TYPE, payment.pk
    )
    return both.order_by("-created_at", "-id")


def _note_of(row: Any) -> str | None:
    """The drawing's NOTE column — what a PERSON wrote, or nothing.

    Only `NOTE_KEYS`, only from `after`, only when the value is a non-empty
    string. Everything else about the row is on `GET /audit-log`.
    """
    after = getattr(row, "after", None)
    if not isinstance(after, dict):
        return None
    for key in NOTE_KEYS:
        value = after.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _note_key_of(row: Any) -> str | None:
    """`DEF-PAY-10017` — the catalogue key for a NOTE that is a closed code.

    A reversal writes its `reason` as one of `REVERSAL_REASONS` (`nsf`), which
    is a code and not words a person typed; the history printed it raw. The
    same value `_note_of` picks is judged here, so the two cannot disagree:
    only a `reason` that is one of the four codes gets a key.
    """
    after = getattr(row, "after", None)
    if not isinstance(after, dict):
        return None
    for key in NOTE_KEYS:
        value = after.get(key)
        if isinstance(value, str) and value.strip():
            code = value.strip()
            if key == "reason" and code in models.REVERSAL_REASONS:
                return f"payments.reverse.reason.{code}"
            return None
    return None


def history_rows(rows: Any, tenant_id: Any) -> list[dict[str, Any]]:
    """ONE PAGE of the trail as `WHEN · WHAT · WHO · NOTE` (p035 ⑦).

    `rows` is the page `StandardPagination` already took — this function never
    queries for more of them.

    **`what` is the audit CODE, never a sentence.** `payment.recorded`,
    `payment.cancelled`, `payment.reversed`: the screen holds the words in all
    eleven catalogues (B14 rule 35), so the trail cannot end up half in English
    for a Spanish-speaking clerk. `apps.audit.selectors.audit_row` builds the
    actor in its ratified S61 shape and this adds nothing to it — a second actor
    resolver is what `_actor_payload`'s own warning is about.
    """
    page = list(rows or [])
    if not page:
        return []
    build_row = _resolve(AUDIT_MODULE, AUDIT_ROW_BUILD)
    lookup = _resolve(AUDIT_MODULE, AUDIT_NAMES_READ)
    if build_row is None:  # pragma: no cover - defensive
        return []
    payloads = [build_row(row, {}) for row in page]
    actor_ids = [
        payload["actor"]["id"]
        for payload in payloads
        if isinstance(payload.get("actor"), dict) and payload["actor"].get("id")
    ]
    names = lookup(tenant_id, actor_ids) if lookup is not None and actor_ids else {}
    history: list[dict[str, Any]] = []
    for row, payload in zip(page, payloads, strict=False):
        actor = payload.get("actor")
        if isinstance(actor, dict) and actor.get("id"):
            # B14 rule 31 — the NAME reaches the screen; the id does not. A
            # removed user keeps their history and the screen states the absence.
            who: dict[str, Any] | None = {
                "kind": "user",
                "name": names.get(actor["id"]) or actor.get("name"),
            }
        elif isinstance(actor, dict):
            who = {"kind": actor.get("kind"), "name": actor.get("name")}
        else:
            who = None
        history.append(
            {
                "at": payload["created_at"],
                "what": payload["action"],
                "who": who,
                "note": _note_of(row),
                "note_key": _note_key_of(row),
                # DEF-PAY-10698 · LBX-04 — on a reversal's row, the bank's words
                # and the NSF penalty (charged, or unticked with its reason).
                **_bounce_facts(getattr(row, "after", None)),
            }
        )
    return history


# ── the read itself ────────────────────────────────────────────────────────
def payment_detail(payment: models.Payment) -> dict[str, Any]:
    """`GET /payments/{id}` — everything screen 2·2 draws, minus the history page.

    The history is served BESIDE this by `detail_api`, because it is the one
    member of the payload that is paginated and a paginated member inside an
    unpaginated body is how an unbounded read hides (`NFR-3`).

    Keys, and where each comes from:

      `**payment_row(...)`  the eleven facts and the bill table, verbatim from
                            `selectors` — the same builder `GET /payments`
                            uses, so the page and the list can never disagree
      `source`              ⑤, `payments.origin` + the absence of a counter link
      `reconciled`          ⑥, the deposit batch and its tie, or null
      `actions`             what the four header controls may do to THIS row,
                            decided by the service rules and not by the screen
      `receipts`            every receipt row this payment has, and the copy
                            number the Resend modal will submit — which is also
                            what draws its ① *"Sent 09/21 11:42 by email and
                            text"*. Served HERE so the modal needs no second
                            read and so the number a clerk sends back is the
                            number the server showed them (hard rule 6 —
                            `receipt_resend.next_copy_no` says why that round
                            trip is the guarantee).
      `unavailable`         codes, never sentences
      `custom answers`      the utility's own payment fields, as typed on
                            Record payment (CR-161-BRC10 W5) — read-only
    """
    from apps.payments import custom_values, receipt_resend

    row = selectors.payment_row(payment)
    reconciled, reconcile_notes = _reconciled(payment)
    unavailable: list[str] = [HISTORY_NOT_PERMANENT, *reconcile_notes]
    if history_queryset(payment) is None:  # pragma: no cover - defensive
        unavailable.append(HISTORY_UNREADABLE)
    deliveries = receipt_resend.receipt_deliveries(payment)
    return {
        **row,
        "source": _source(payment),
        "reconciled": reconciled,
        "actions": action_availability(payment),
        # `DEF-PAY-10016` — why this money was taken back, as a reason CODE.
        "reversed_for": _reversed_for(payment),
        # DEF-PAY-10698 · LBX-04 — "Bank memo: NSF" and the NSF penalty.
        "reversal": _reversal_block(payment),
        "receipts": deliveries,
        "next_copy_no": receipt_resend.next_copy_no(deliveries),
        "unavailable": unavailable,
        # CR-161-BRC10 W5 — the answers typed on Record payment, shown
        # read-only by S33. Never read by anything that moves money.
        "custom_data": custom_values.for_display(payment),
    }


def action_availability(payment: models.Payment) -> dict[str, Any]:
    """Which of the four header controls this payment can take, and why not.

    ⚠ **THE SERVER DECIDES, AND THE SCREEN RENDERS THE DECISION** (BR-SHL-025:
    a refused control is shown DISABLED with its reason, never hidden). The
    blueprint asks for exactly this on p044: *"the control behaves differently by
    status"* — and a screen that worked the status rules out for itself would be
    a second copy of `cancel.refusal_for`, free to drift from the service that
    will actually refuse the click.

    Each value is `{"allowed": bool, "reason": <code> | None}`. The reason is a
    CODE; the sentence is the catalogue's.
    """
    from apps.payments import cancel  # local: cancel imports nothing from here

    cancel_refusal = cancel.refusal_for(payment)
    return {
        # The three amendable columns, in any status (hard rule 4 as narrowed by
        # the PO on 2026-09-02, `payments/0014`). Edit is therefore ALWAYS
        # available — ⚠ but the TENDER inside it is not, once the payment is
        # banked: deposit batches group by day AND tender, so changing it would
        # move the payment between two batches and rewrite two day totals
        # (`amendments.refuse_tender_change_once_batched`, and the database says
        # the same thing independently in `payments/0014`).
        #
        # ⚠ **THE FIELD IS NAMED RATHER THAN THE CONTROL DISABLED.** An earlier
        # draft of this line read `payment.deposit_batch_id is None or True`,
        # which is `True` for every payment that has ever existed — a condition
        # that cannot be false is hard-won law 7's *structurally incapable of
        # failing* shape, and it would have shipped green.
        "edit": {
            "allowed": True,
            "reason": None,
            "tender_locked": payment.deposit_batch_id is not None,
        },
        # A correction is a NEW ROW and needs nothing of this one.
        "correction": {"allowed": True, "reason": None},
        "cancel": {
            "allowed": cancel_refusal is None,
            "reason": cancel_refusal,
        },
        # A receipt can always be sent again — `Resend` touches no money.
        "receipt": {"allowed": True, "reason": None},
        # CR-175-BRC10 — Mark returned. `offered` is the TENDER (ACH only, the
        # PO's ruling of 2026-10-07); `allowed`/`reason` are this row's state.
        # Who may press it is the role's, and the service refuses everyone else.
        "mark_returned": _mark_returned_state(payment),
    }


def _mark_returned_state(payment: models.Payment) -> dict[str, Any]:
    """Can THIS payment be marked returned by the bank, and if not, why not.

    The reasons are the service's own refusals, as codes, so the button and
    `reversal.mark_ach_returned` cannot disagree: not ACH (not offered at all),
    a reversing row, money that never cleared, or already returned.
    """
    from apps.payments import reversal  # local: reversal imports nothing from here

    offered = getattr(payment.method, "code", None) == reversal.ACH_TENDER_CODE
    if payment.reverses_payment_id is not None or payment.amount <= 0:
        return {"offered": False, "allowed": False, "reason": "is_reversal"}
    if payment.status not in reversal.ACH_RETURNABLE_STATUSES:
        return {"offered": offered, "allowed": False, "reason": "not_cleared"}
    if models.Payment.objects.filter(
        tenant_id=payment.tenant_id, reverses_payment_id=payment.pk
    ).exists():
        return {"offered": offered, "allowed": False, "reason": "already_returned"}
    return {"offered": offered, "allowed": offered, "reason": None}


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-137-BRC07 §3 P3.1 + P3.4 · 05-prototype/06 Payments Page Blueprint.pdf
#         pp.18–20 (the task table) + p035 (screen 2·2) + p050 (what every act
#         writes) · 04-docs/05-modules/08-payments/06-epics/EP-PAY-01 US-PAY-004
#         §1 + TC-7 · 04-docs/05-modules/08-payments/02-business-rules.md
#         BR-PAY-021 · CLAUDE.md hard rules 1, 2, 7 · B14 rules 31, 33, 35
# generated: 2026-09-23 by the CR-137 P3-BACK lane
# checklist: A✔ B=deferred(P3.9 owns screen 2·2) C✔ D✔ E=deferred(P3.9) F✔ G✔
#            H=deferred(PO 2026-08-09)
# exceptions:
#   E1 ⚠ **THIS READ *"the blueprint PDF is NOT on this branch"* WHILE THIS LANE
#      WAS BUILDING, AND IT IS NO LONGER TRUE.** It was true at the pinned tip and
#      the drawing was read from `origin/claude/confirm-understanding-3ktufc`;
#      `da07c7f8d` put it on THIS branch at `05-prototype/06 Payments Page
#      Blueprint.pdf`, 2,905,141 bytes, sha256 `0cc31baf…`, and the copy read here
#      is byte-identical to it. `DEF-PAY-6230` is CLOSED. Read it from the branch.
#   E2 ⑥ RECONCILED serves `reference: null`. The drawing's `BRM-2609-0041` is a
#      series this product does not mint and `bank_rec_match_sets` has no code
#      column; an id there would breach B14 rule 31. Stated, not invented —
#      `OQ-PAY-12602`.
#   E3 ⑤ SOURCE serves `taken_by: null` — except on a payment agent's payment,
#      which names the agent (`DEF-PAY-10015`). The counter session is `CR-136-BRC07`'s
#      and its link does not exist on `payments` yet; `entry` alone does not name
#      a person (a transfer leg and a bounce are both `entry`).
#   E4 No screen copy is written here and none is owed: B14 rule 33 puts
#      rationale at ZERO words on screen, so the retention fact travels as the
#      `unavailable[]` CODE `history_is_pruned_like_every_audit_row` and the
#      panel says nothing at all (CR-137 §1.3).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

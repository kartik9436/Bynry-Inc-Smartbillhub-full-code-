# ── Trace ──────────────────────────────────────────────
# Change:   `06 Payments Page Blueprint.pdf` phase 1, tasks `P1.1`/`P1.2`/`P1.12`
#           — "Make what exists reachable": the lockbox/store file becomes an
#           EIGHTH target of the one import runner instead of a second pipeline.
#           PO ruling 2026-09-22, verbatim: *"we should not use second machine -
#           (a) Delete it if possible"*.
# Story:    US-PAY-003 (import a remittance file) · S-15 (the imports list)
# Rules:    BR-PAY-023 (staged import: per-row errors skip with a report) ·
#           BR-PAY-033 (an import takes the arrival date from the FILE) ·
#           BR-MET-096 (PO 2026-08-21: ONE runner, `target` parameterised — a
#           new target is a dict entry, never a second code path) ·
#           B1/B2 §2 + `G78`'s law (nothing outside a module writes its tables) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2 (money is
#           Decimal, 4 stored / 2 shown) · hard rule 4 (financial immutability —
#           which is why there is no `update_` and no `rollback_` below) ·
#           hard rule 6 (idempotency) · hard rule 7 (every money action audits) ·
#           hard-won law 14 (the SAVEPOINT is the caller's, per row)
# Tests:    06-backend/tests/test_pay_import_target.py
# Impacts:  apps/metering/seams.py (the three names) ·
#           apps/metering/import_runs.py (`TARGET_PAYMENTS`)
# ───────────────────────────────────────────────────────
"""Payments' INBOUND door for the one importer — `parts`' shape, money's rules.

⚠ **WHY THIS FILE EXISTS AT ALL: `payments` IS NOT METERING'S TABLE.** The
import runner lives in `apps/metering/import_runs.py` and a cross-module write
is forbidden (B1/B2 §2). `accounts` is customers' table and customers writes it;
`parts` is work's and work writes it; `payments` is ours and **we** write it.
That makes the boundary STRUCTURAL rather than a thing to be careful about —
there is no ORM statement in `apps/metering/` that names a payments table, so
there is nothing to review.

⚠ **IT IS UNDECORATED, FOR `DEF-1108`'s REASON.** A deferred load runs in a
BE-07 worker carrying `_JobActor` — an id and NO ROLE, by design — so a
`@require_role` writer would refuse every row of a four-hundred-line morning
file at the point the operator has already been told it is loading.
`import_runs.load()` checks the role ONCE, where a role still exists.

WHAT IS DELIBERATELY NOT HERE, AND EACH ABSENCE IS A RULE
---------------------------------------------------------
**No `update_payment_from_import`.** CLAUDE.md hard rule 4: no UPDATE on
payments. The runner's *Insert & update* mode would overwrite a payment on
file, so this target offers ONE write mode and the runner refuses the other by
name. (The rule's three narrowed columns — `confirmation`, `memo`, `method_id`
— move only through `POST /payments/{id}/correct-reference`, never through an
import.)

**No `rollback_payment_from_import`.** A posted payment cannot be unwritten;
it is reversed, which is a new row and a different act with different books.
`import_runs.rollback` therefore REFUSES this target by name and no rollback
point is ever created for it — so there is no control to press and nothing to
spend. Reads is the only other target that refuses outright.

**No second matcher.** What counts as a match is THIS module's answer and not
a second one. `match_account` below is the only ladder, and stage 3 (the
rehearsal the operator reads) and stage 4 (the write) both call it — `DEF-544`'s
law: a load that resolves against a different world than the one the operator
was shown is a defect in its own right, not a race.

⚠ **THE LADDER'S SECOND RUNG IS A REFUSAL AND THAT IS THE WHOLE POINT
(`P1.12`, CS-2 rule 2).** *A name-and-amount guess never commits on its own.*
A name is not an identifier; posting to the wrong customer breaks two accounts
silently and can only be undone by a reversal on one and a new payment on the
other. So a row matched only by the payer's name is reported as a SUGGESTION
for a person, is flagged at stage 3, and is **refused at the write** — it is
not quietly skipped, because money nobody chased is the failure `BR-PAY-023`'s
per-row report exists to prevent.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from core import errors

#: `customers.selectors.account_import_index` — the published read that keys
#: every account the way an import file references one. Named here rather than
#: inlined so the one place it is resolved is greppable.
CUSTOMERS_ACCOUNT_INDEX = ("customers", "account_import_index")

#: The six refusal keys this door raises. The runner turns each into the two
#: sentences a rejected row carries, and it looks them up BY KEY — so a key
#: added here without a sentence there degrades to a truthful generic pair
#: rather than crashing a run (the parts half's rule, followed not re-derived).
REFUSAL_NO_IDENTIFIER = "payments.import.no_identifier"
REFUSAL_ACCOUNT_NOT_ON_FILE = "payments.import.account_not_on_file"
REFUSAL_NAME_ONLY = "payments.import.name_only_match"
REFUSAL_AMOUNT_MISSING = "payments.import.amount_missing"
REFUSAL_AMOUNT_NOT_POSITIVE = "payments.import.amount_not_positive"
#: `DEF-PAY-10696` — the tenant has switched its Lockbox method off.
REFUSAL_LOCKBOX_METHOD_OFF = "payments.import.lockbox_method_off"

#: The seeded payment-method CODE an imported lockbox payment is recorded under
#: (`tenancy/fixtures/lookup_defaults.json` → `payment_methods` → `lockbox`).
#: Resolved by code against the tenant's own list, never by a row id.
LOCKBOX_METHOD_CODE = "lockbox"

#: `match_account`'s verdict words. `clean` is the ONLY one that may be written.
MATCH_CLEAN = "clean"
MATCH_REVIEW = "review"

#: How the account was found, for the receipt and for the row's sentence.
BY_ACCOUNT_NO = "account_no"
BY_NAME_ONLY = "name_only"


def payments_import_index() -> dict[str, dict[str, Any]]:
    """Every account, keyed the way an import file references one.

    ⚠ **AN UNWIRED SEAM REFUSES RATHER THAN RETURNING AN EMPTY INDEX.** An
    empty index answers *"no account matched"* for every row in the file —
    which is a sentence about four hundred customers' money produced by a
    missing import, not by anything the file says. `DEF-075`'s law: `None`
    means *this module cannot answer*, never *this module has nothing*.

    ⚠ **A TENANT WITH NO ACCOUNTS IS NOT THIS.** That index is legitimately
    empty and every row correctly reports that it names an account not on
    file. The two are told apart by asking whether the READ EXISTS, never by
    the size of what it returns.
    """
    from importlib import import_module

    module_name, attribute = CUSTOMERS_ACCOUNT_INDEX
    try:
        published = import_module(f"apps.{module_name}.selectors")
    except ImportError:  # pragma: no cover — customers ships in-tree
        published = None
    read = getattr(published, attribute, None) if published is not None else None
    if not callable(read):
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CUS-054",
            message_key="payments.import.accounts_unwired",
        )
    return dict(read() or {})


def match_account(
    *,
    account_ref: Any = None,
    payer_name: Any = None,
    index: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """One row down the ladder. Pure — it reads the index and decides nothing else.

    ⚠ **THE ORDER IS THE EPIC'S AND IT IS NOT A PREFERENCE.** The account the
    file NAMES is what the payer said the money is for. A bill reference would
    narrow it to one invoice, and the allocator's own rules (`BR-PAY-010`,
    tenant-configurable) decide that better than a remittance line does — so a
    bill number stays on the row as PROVENANCE and never becomes an allocation
    instruction. Turning a bank's reference field into a staff instruction
    would silently override every tenant's allocation policy, four hundred
    times a morning, on the strength of what a lockbox operator typed.

    Returns `{state, account_id, account_no, method, detail}`. **`state` is
    `clean` only when an identifier the utility issued was matched**; every
    other outcome is `review`, which stage 3 flags and the write refuses.
    """
    index = index or {}
    reference = str(account_ref or "").strip().lower()
    if reference:
        hit = index.get(reference) or index.get(f"ext:{reference}")
        if hit is not None:
            return {
                "state": MATCH_CLEAN,
                "account_id": hit["id"],
                "account_no": hit.get("account_no") or hit["id"],
                "method": BY_ACCOUNT_NO,
                "detail": f"account {hit.get('account_no') or hit['id']}, named by the file",
            }
        # ⚠ NOT an error in the sense of a broken file. The file named an
        # account this utility does not have — a legacy number, a typo, or an
        # account not migrated yet. A person decides; the money is real either
        # way, and it is still in the bank.
        return {
            "state": MATCH_REVIEW,
            "account_id": None,
            "account_no": None,
            "method": None,
            "detail": (
                f"the file names account {str(account_ref).strip()!r}, which is not on file "
                "here. Nothing is guessed from it."
            ),
        }

    name = str(payer_name or "").strip().lower()
    if name:
        # ⚠ **THE HEURISTIC. IT SUGGESTS AND IT NEVER COMMITS** — `P1.12`.
        # Deliberately blunt: the index carries the account number and the
        # utility's own legacy external reference, not the customer's name, and
        # an importer may not fetch names from another module row by row for a
        # four-hundred-line file. So this matches the ONE thing the index holds
        # that a payer name can legitimately equal — a legacy reference where
        # the "number" was often the household's name. A wider net would
        # produce more suggestions, and a suggestion this module cannot justify
        # is worse than none: every one is a row a person has to read and
        # dismiss.
        unique: dict[str, dict[str, Any]] = {}
        for key, entry in index.items():
            if key.startswith("ext:"):
                continue
            external = str(entry.get("external_ref") or "").strip().lower()
            if external and external == name:
                unique[str(entry["id"])] = entry
        if len(unique) == 1:
            only = next(iter(unique.values()))
            label = only.get("account_no") or only["id"]
            return {
                "state": MATCH_REVIEW,
                "account_id": only["id"],
                "account_no": label,
                "method": BY_NAME_ONLY,
                "detail": (
                    f"{str(payer_name).strip()!r} looks like account {label}. A name is not "
                    "an identifier, so this is a SUGGESTION: confirm it before the money is "
                    "posted."
                ),
            }
        return {
            "state": MATCH_REVIEW,
            "account_id": None,
            "account_no": None,
            "method": None,
            "detail": (
                f"{len(unique)} accounts could be {str(payer_name).strip()!r}. Nothing is "
                "chosen for you."
                if unique
                else f"nothing on file matches the payer {str(payer_name).strip()!r}."
            ),
        }

    return {
        "state": MATCH_REVIEW,
        "account_id": None,
        "account_no": None,
        "method": None,
        "detail": "this row names no account and no payer, so there is nothing to match it on.",
    }


def create_payment_from_import(*, actor: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """One import row → one payment, through this module's ONE writer.

    UNDECORATED on purpose — see this module's docstring. Raises `BizError` for
    a row it will not accept; the loader catches it per row INSIDE ITS OWN
    SAVEPOINT and reports the sentence, because on PostgreSQL a refused
    statement aborts the whole transaction and every row already written would
    be lost at COMMIT while the run reported success (CLAUDE.md law 14).

    ⚠ **`posted_at` COMES FROM THE FILE'S OWN ARRIVAL DATE, AND NO CLEARING
    DATE IS PASSED AT ALL.** `BR-PAY-033`, and `OQ-131`'s ruling behind it:
    lateness is judged on the day the money actually ARRIVED, never on the day
    a clerk got round to importing it. A lockbox date IS the day the bank
    received it. Where the file carried none, the caller's business day is the
    fallback — the PO's 2026-08-12 ruling, which *"forgives nothing"*: it is
    the recorded day, not a kind one. **The paid date is NOT a clearing date**
    (`CR-186-BRC10`, `payments/0051`): every payment is `posted` at entry and
    becomes `cleared` only when its deposit batch is reconciled with the bank
    statement, so this writer never claims one (`DEF-PAY-10696`, LBX-06 — this
    paragraph said the file's date was also the clearing date until then).

    ⚠ **THE TENDER IS `lockbox`, RESOLVED BY CODE — `DEF-PAY-10696`, LBX-06.**
    A lockbox file is cheques, cash and money orders the lockbox took, and the
    batch's *Totals by tender* must say so: the tester's six-row file reads
    **Lockbox · 6 · $870.50**. Until 2026-10-30 no method was passed and the
    comment here claimed *"the tenant's default tender"* — there is no such
    thing (`services._method` answers None for no code), so every imported
    payment carried a BLANK tender. A tenant that has DEACTIVATED its Lockbox
    method has said stop using it, so the row is refused by name
    (`REFUSAL_LOCKBOX_METHOD_OFF`) rather than written blank.

    ⚠ **THE IDEMPOTENCY KEY IS THE RUN AND THE ROW** (hard rule 6). A load
    retried after a crash between rows records each row once. That is the key
    reaching per ROW; the runner's own `uq_import_runs_idempotency` guards the
    FILE, and the two catch genuinely different things (`DEF-058`: two guards
    on one fact are one guard).

    ⚠ **AND `idempotency_source` IS ALSO WHAT WRITES `payments.origin`, WHICH
    IS NOW A DATABASE CHECK — verified against the tip on 2026-09-22, not
    assumed.** `record_payment` sets `origin=idempotency_source` with
    `origin_is_derived=False` (an OBSERVED origin, never a guess), and
    `payments/0030`'s `ck_payments_origin` rejects anything outside
    `entry | webhook | import` **by name, from every path**. `SOURCE_IMPORT` is
    `"import"`, so these rows are lawful — but a lane that "tidies" this
    argument away, or invents a prettier value like `"lockbox"`, gets an
    IntegrityError on every row of a morning's takings rather than a quiet
    NULL. The constraint landed the same day as this target; it was read rather
    than trusted.
    """
    from apps.payments import idempotency, services

    data = dict(payload or {})

    amount = _amount_of(data.get("amount"))
    verdict = data.get("match") or match_account(
        account_ref=data.get("account_ref"),
        payer_name=data.get("payer_name"),
        index=data.get("index") or payments_import_index(),
    )
    if verdict["state"] != MATCH_CLEAN:
        # ⚠ **REFUSED, NOT SKIPPED, AND THE DISTINCTION IS `BR-PAY-023`'s.**
        # A row that disappears is money nobody chased. A row that is REFUSED
        # carries its reason onto the receipt and into the failures download.
        key = (
            REFUSAL_NAME_ONLY
            if verdict.get("method") == BY_NAME_ONLY
            else REFUSAL_ACCOUNT_NOT_ON_FILE
            if str(data.get("account_ref") or "").strip()
            else REFUSAL_NO_IDENTIFIER
        )
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-PAY-023",
            message_key=key,
            params={"detail": verdict["detail"], "account": verdict.get("account_no") or ""},
        )

    moment = data.get("paid_at") or data.get("recorded_at")
    _require_lockbox_method()
    recorded = services.record_payment(
        actor,
        account_id=verdict["account_id"],
        amount=amount,
        posted_at=moment,
        # ⚠ **`lockbox`, BY CODE, NEVER BY ID** (`DEF-PAY-10696`). The template
        # offers no tender column — the remittance vocabulary real lockbox files
        # use has never carried one — so the file's tender is the lockbox
        # itself. A clerk who needs to say otherwise corrects the payment
        # through `POST /payments/{id}/correct-reference`, the ONE door hard
        # rule 4 opens for exactly this. No `cleared_at`: see the docstring.
        method_code=LOCKBOX_METHOD_CODE,
        confirmation=(str(data.get("reference") or "").strip() or None),
        memo=(str(data.get("memo") or "").strip() or None),
        idempotency_source=idempotency.SOURCE_IMPORT,
        idempotency_reference=data.get("idempotency_reference"),
        # PO 2026-10-30 Q6 — the file's **Network** cell (`Hy-Vee`): the row
        # banks in that network's own daily batch and reads *Store · Hy-Vee*.
        # A blank cell, or a file with no such column, is a lockbox row.
        store_network=(str(data.get("network") or "").strip() or None),
    )
    return {
        "id": str(recorded.payment_id),
        "payment_no": getattr(recorded, "payment_no", None),
        "account_no": verdict["account_no"],
        "amount": str(amount),
    }


def cheque_key(account_id: Any, amount: Any, reference: Any) -> tuple[str, str, str] | None:
    """The identity of ONE cheque: account · amount · reference — or None.

    `DEF-PAY-10697` (LBX-08). ⚠ **ALL THREE, AND NEVER THE REFERENCE ALONE:**
    two customers can each send cheque number 1042 — it is THEIR chequebook's
    number, not the utility's — so a reference on its own names nobody's money.
    A row with no reference has no instrument to compare and answers None.
    The amount is normalised to four places (hard rule 2) so `76.4` and
    `76.4000` are one cheque.
    """
    ref = str(reference or "").strip().lower()
    if not ref or account_id in (None, ""):
        return None
    try:
        money = Decimal(str(amount).strip()).quantize(Decimal("0.0001"))
    except (InvalidOperation, ValueError, ArithmeticError):
        return None
    return (str(account_id), str(money), ref)


def posted_cheques(keys: Any) -> dict[tuple[str, str, str], str]:
    """Which of these cheques are ALREADY recorded — key → its payment number.

    `DEF-PAY-10697` (LBX-08), read by stage 3 through
    `metering.seams.payments_posted_cheques` so the rehearsal can HOLD a row
    whose cheque this utility already has, before anybody presses commit.

    Bounded by the FILE, never by the ledger: it asks only about the accounts
    and references the file names (NFR-3 — nothing here grows with the
    tenant's payment history). A payment that was cancelled, failed or
    reversed — or that has a reversal row against it — is NOT counted: a
    bounced cheque that comes back from the bank and is re-presented is a
    second, real deposit of the same cheque.
    """
    from django.db.models import Exists, OuterRef
    from django.db.models.functions import Lower, Trim

    from apps.payments import models, services

    wanted = {one for one in (keys or ()) if one}
    if not wanted:
        return {}
    accounts = {account for account, _amount, _ref in wanted}
    references = {ref for _account, _amount, ref in wanted}
    reversal = models.Payment.objects.filter(reverses_payment_id=OuterRef("pk"))
    rows = (
        models.Payment.objects.filter(
            tenant_id=services._tenant_id(),
            account_id__in=accounts,
            type=models.PAYMENT_TYPE_PAYMENT,
            reverses_payment__isnull=True,
        )
        .exclude(
            status__in=(
                models.PAYMENT_CANCELLED,
                models.PAYMENT_FAILED,
                models.PAYMENT_REVERSED,
            )
        )
        .annotate(_ref=Lower(Trim("confirmation")), _reversed=Exists(reversal))
        .filter(_ref__in=references, _reversed=False)
        .values_list("account_id", "amount", "_ref", "payment_no")
    )
    found: dict[tuple[str, str, str], str] = {}
    for account_id, amount, ref, payment_no in rows:
        key = cheque_key(account_id, amount, ref)
        if key in wanted and key not in found:
            found[key] = payment_no or ""
    return found


def _require_lockbox_method() -> None:
    """Refuse the row, by name, when the tenant has no ACTIVE `lockbox` method.

    Asked here rather than left to `services._method`'s generic refusal so the
    rejected row carries a sentence a clerk can act on (switch Lockbox back on
    under payment methods) instead of the generic *"refused when it was
    written"* pair.
    """
    from apps.payments import services

    lookup = services._resolve("tenancy", "PaymentMethod", "models")
    if lookup is None:  # pragma: no cover — tenancy ships in-tree
        return
    if not lookup.objects.filter(
        tenant_id=services._tenant_id(), code=LOCKBOX_METHOD_CODE, active=True
    ).exists():
        raise errors.BizError(
            errors.BIZ_STATE, br_ref="BR-PAY-026", message_key=REFUSAL_LOCKBOX_METHOD_OFF
        )


def _amount_of(value: Any) -> Decimal:
    """The row's money, or a refusal naming which of the two problems it is.

    ⚠ **MONEY IS A `Decimal` AND NEVER A FLOAT** (CLAUDE.md hard rule 2). The
    cell has already been through stage 2's decimal parse, so this is the
    second line of defence rather than the first — and it is here because a
    writer that trusts its caller's parse is a writer that posts `None` as
    zero the first time a caller changes.
    """
    if value is None or str(value).strip() == "":
        raise errors.BizError(
            errors.BIZ_STATE, br_ref="BR-PAY-023", message_key=REFUSAL_AMOUNT_MISSING
        )
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, ValueError, ArithmeticError):
        raise errors.BizError(
            errors.BIZ_STATE, br_ref="BR-PAY-023", message_key=REFUSAL_AMOUNT_MISSING
        ) from None
    if amount <= 0:
        # A refund is a different act with different books and a different
        # door; a remittance file carrying a negative is a file we misread.
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-PAY-023",
            message_key=REFUSAL_AMOUNT_NOT_POSITIVE,
            params={"amount": str(amount)},
        )
    return amount


# ── Lifecycle ─────────────────────────────────────────────
# packet: 05-prototype/06 Payments Page Blueprint.pdf phase 1 (P1.1 · P1.2 · P1.12 · P1.22)
# generated: 2026-09-22 by lane P1-A
# checklist: A✔ B✔ C✔ D=n/a(no endpoint of its own — the runner's) E=n/a F✔ G✔ H✔(the amount is Decimal, refused not coerced)
# gates: pytest tests/test_pay_import_target.py
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

"""Idempotency keys for bill runs, the New Connect commit + inbound payment webhooks. HUMAN-OWNED (CLAUDE.md).
Unique-key shapes come from B2 (bill_runs: tenant+cycle+period; payments.webhook_key).

HUMAN-REVIEW-PENDING — this file stopped being a docstring-only stub on
2026-08-11, under the PO ruling of 2026-08-09 (*"AI will do it; we will review
it later as human"*). Row in 12-governance/09-human-review-ledger.md; it may
never reach lifecycle RATIFIED without a recorded human sign-off.

WHAT IS SIGNED, AND WHAT IS MECHANICS
-------------------------------------
The RULE is signed and is not reinterpreted here. BR-BIL-005 (CONFIRMED,
EP-BIL-01): *"Bill runs are idempotent — unique (tenant, cycle, period) key
blocks an identical re-run; blocked attempt shows who/when/link"*, enforced by
B2's `UNIQUE (tenant_id, idempotency_key)` on `bill_runs`. The MECHANICS — the
exact string those three facts are folded into — are Eng-Lead's (03-field-map:
*"key mechanics 🔒 Eng-Lead (r10 #15)"*) and are the only thing decided here.

    key = "<cycle uuid>|<period_start ISO>|<period_end ISO>"

Worked, so the figure is concrete rather than a description: cycle 07-A with id
`018f6f6a-0000-7000-8000-000000000001` over 1–30 June 2026 produces

    018f6f6a-0000-7000-8000-000000000001|2026-06-01|2026-06-30

and a second attempt at that same cycle and period is refused with the first
run's id, who ran it and when. A run over 1–31 July is a different string and
starts normally.

THREE PROPERTIES THE SHAPE IS CHOSEN FOR
----------------------------------------
  * **The cycle's UUID, never its CODE.** A tenant renaming cycle "07-A" to
    "2026-07-A" must not unlock a second run over the same month — the key must
    identify the same cycle, not the same label.
  * **ISO dates, never a locale format.** `date.isoformat()` is fixed-width,
    sorts, and cannot mean two things in two regions; a key that read
    "01/07/2026" would collide across tenant date-format settings (BR-TEN-020).
  * **The tenant is NOT in the string.** It is the other column of the unique
    constraint (`UNIQUE (tenant_id, idempotency_key)`), so folding it in as
    well would put the same fact in two places and let one drift from the
    other. The tenant is never client input either way (BR-TEN-003).

THERE ARE NOW THREE RUN SHAPES, sharing one unique index, and each leads with
something the other two cannot produce — so they can never collide whatever the
uuids are:

    cycle run   "<cycle uuid>|<start>|<end>"                   bill_run_key
    scoped run  "<cycle uuid>|<start>|<end>|scope|<codes>"      bill_run_key
    catch-up    "<parent key>|catch-up|<sorted account ids>"    catch_up_run_key
    one-time    "one-time|<account uuid>|<kind>|<start>|<end>"  one_time_run_key
                (+ "|<source>" when the bill answers to one event — the NSF
                fee per bounced payment, DEF-PAY-10740)

⚠ **THE SCOPED RUN IS AN EXTENSION OF THE CYCLE RUN'S STRING, NOT A FOURTH
SHAPE** (`DEF-BIL-5283`, BR-BIL-005's signed *"key = parent key + scope"*). It
cannot collide with a cycle run, because a cycle run's string has no `|scope|`
segment; it cannot collide with a catch-up, whose marker differs; and a
catch-up OF a scoped run nests correctly, because `catch_up_run_key` takes the
parent's whole string whatever shape it is.

⚠ **AND A FIFTH SHAPE THAT IS NOT A BILL RUN AT ALL — `new_connect_commit_key`,
added 2026-09-29 for `DEF-CUS-8021`.** It keys the New Connect commit on a
CLIENT-minted submit token and shares nothing with the four above but the
separator and the leading marker:

    new connect "new-connect|<submit token>"                new_connect_commit_key

It is here rather than in `apps/metering` on a judgment stated once: this file
is the one home for the answer to *"has this already been done?"*, and a second
home is how two paths start asking a different question. The counter-case — a
key whose shape a LANE has to settle with an outside party — is the one below,
and it does not apply: nothing outside this product issues a New Connect token.

`payments.webhook_key` is NOT here. Its shape is DB-12's second row and belongs
to the payments lane; inventing it in advance would be this module deciding a
question that lane has to ask the provider.
"""

from datetime import date
from typing import Any

#: The one separator, named once. `|` cannot occur in a UUID or an ISO date, so
#: the three parts stay unambiguous and the key is splittable by eye in a psql
#: session — which is where somebody debugging a refused run will be looking.
KEY_SEPARATOR = "|"


class IdempotencyKeyError(ValueError):
    """A key was asked for with a part missing. Refuses rather than composing a
    short key — two runs whose keys are both `"|2026-06-01|2026-06-30"` would
    collide across DIFFERENT cycles, which is the exact failure the key exists
    to prevent."""


#: What a SERVICE-SCOPED run's key carries on top of its cycle and period.
#: `DEF-BIL-5283`. Named for the same two reasons `CATCH_UP_MARKER` is: the two
#: halves of the string stay greppable, and nothing composes it as a bare
#: f-string on the other side of a module boundary.
SCOPE_MARKER = "scope"

#: Inside the scope segment only. A service code cannot contain a comma and the
#: catch-up key already joins its account ids this way, so one separator means
#: one thing in both.
SCOPE_ITEM_SEPARATOR = ","


def bill_run_key(
    *,
    cycle_id: Any,
    period_start: date,
    period_end: date,
    scope_services: Any = None,
) -> str:
    """BR-BIL-005's key for one bill run: cycle + period + SCOPE, tenant by constraint.

    ⚠ **2026-09-30 — NO NEW RUN PASSES `scope_services` ANY MORE (bulk bill run
    plan B3; PO: *"which servcies to be billed in unit /account is decied at
    run time -so this filter is of now use"*).** `runs.create_run` no longer
    takes a service scope, so every NEW run is keyed on the first branch below —
    `"<cycle uuid>|<start>|<end>"`, byte for byte what an unnarrowed run has
    always been keyed. **The `|scope|` branch is kept, unchanged, because rows
    written before the ruling carry it** and this function is the one written
    statement of how those stored strings were composed; nothing rewrites a
    stored key. A new whole-cycle run over a period an OLD scoped run covered is
    therefore a DIFFERENT string and the unique index cannot see the clash —
    `billing.run_scope`'s overlap refusal is the guard for that case. 🔒 This
    change is HUMAN-REVIEW-PENDING; its row is in
    `12-governance/09-human-review-ledger.md`.

    Pure and total: same inputs ⇒ same string, always, with no clock, no
    ordering assumption and no database read. That is what lets the caller
    check for the duplicate BEFORE inserting and still be backstopped by the
    unique index if it loses a race.

    ── `DEF-BIL-5283` · WHY THE SCOPE ENTERS THE KEY, AND THAT IT IS SIGNED ───
    **THIS IS NOT A NEW RULE AND IT IS NOT THIS MODULE'S JUDGEMENT.** BR-BIL-005
    is CONFIRMED (PO A-6/r1.3) in these words, `EP-BIL-01-bill-run.md`:

        *"Sub-run idempotency: key = parent key + scope; the original run's key
        is never re-used; mechanics 🔒 Eng-Lead."*

    The same sentence is in `07-pre-session-model.md`, `09-po-input-sheet.md`
    A-3 and `04-flows.md`. `catch_up_run_key` below has implemented it since it
    was written. **The rule was applied to one kind of scope and not the other**
    — a catch-up's scope is a subset of ACCOUNTS over the same cycle and period,
    and a Scope-step narrowing is a subset of SERVICES over the same cycle and
    period. They are the same shape and the signed rule covers both.

    **WHAT IT COST WHILE THE SCOPE WAS MISSING**, which is why the fix is here
    and not in a screen: a Water-only run for September consumed the key for
    that cycle and period, so the Sewer run behind it was refused as a duplicate
    — *correctly*, by a key that could not tell the two apart. No exclusion rows
    are written by a refusal, so those accounts never reached the held queue and
    no catch-up ever billed them. The clerk is told *"already run"*, which is
    true and useless.

    ── ⚠ AN UNNARROWED RUN IS KEYED EXACTLY AS IT WAS. THIS IS THE CONSTRAINT ──
    Every run on every tenant was keyed with three inputs. If the full-cycle key
    changed shape, every one of them would stop matching itself and the
    duplicate check would silently stop protecting the runs it was written for —
    a guard that fails OPEN, with no error anywhere. So the segment is APPENDED
    only when a scope exists, exactly as `CATCH_UP_MARKER` is, and
    `test_def_bil_5283_scope_in_the_run_key.py` pins the no-scope literal so a
    later refactor that "tidies" the separator goes red.

    ── THE SHAPE ────────────────────────────────────────────────────────────

        no scope   "<cycle uuid>|<start>|<end>"                     (unchanged)
        scoped     "<cycle uuid>|<start>|<end>|scope|<codes>"

    Worked: cycle `018f…0001` over 1–30 September, narrowed to water, gives

        018f6f6a-0000-7000-8000-000000000001|2026-09-01|2026-09-30|scope|water

    and the sewer run over the same cycle and period is a DIFFERENT string, so
    both bill. The unnarrowed September run is
    `018f…0001|2026-09-01|2026-09-30`, byte for byte what it is today.

    ── CANONICAL, BECAUSE THE OTHER DIRECTION DOUBLE-BILLS ──────────────────
    The codes are **sorted, de-duplicated and case-folded** before joining.
    Water+Sewer and Sewer+Water are ONE scope; keyed as two, the same run is
    runnable twice, which is `DEF-BIL-5283` with its sign flipped and worse —
    it double-bills where the original under-bills.

    ⚠ **CASE-FOLDING IS A DELIBERATE TRADE AND IT IS THE SAFE SIDE OF IT.** Two
    genuinely different catalogue codes differing only in case would fold into
    one key and one of the runs would be refused — under-billing. Two spellings
    of ONE code kept apart would key twice — double-billing. The second is worse
    (a customer is charged twice and the correction is a credit note per bill),
    and the first cannot arise on this product's data: service codes are the
    tenant catalogue's own lowercase values, and a mis-cased code resolves to
    ZERO service points at `_scope_units`, so such a run bills nobody rather
    than billing wrongly.

    ⚠ **`scope_services=[]` IS A NARROWING, NOT AN ABSENCE**, and keys
    differently from `None`. The pipeline already draws that distinction —
    `_readings_for` passes `service_codes=[]` through as *filter to no services*
    — so folding the two together here would let a bill-nothing run consume the
    whole cycle's key.

    The period is NOT validated here (start ≤ end is `runs.create_run`'s
    refusal, citing the proration window it protects). This function's only job
    is the string.
    """
    if cycle_id is None or period_start is None or period_end is None:
        raise IdempotencyKeyError(
            "a bill-run idempotency key needs the cycle and BOTH period dates "
            "(BR-BIL-005 keys on tenant + cycle + period). A key composed with a "
            "part missing would collide across different runs, which is the "
            "double-billing this key exists to prevent."
        )
    base = KEY_SEPARATOR.join((str(cycle_id), period_start.isoformat(), period_end.isoformat()))
    if scope_services is None:
        # BYTE-IDENTICAL to every key already stored. See the docstring: this
        # branch is the whole of the backwards compatibility and it is one line.
        return base
    return KEY_SEPARATOR.join((base, SCOPE_MARKER, scope_segment(scope_services)))


def scope_segment(scope_services: Any) -> str:
    """The canonical rendering of a service scope — sorted, deduped, folded.

    Separate and named so the canonicalisation can be tested on its own and so
    a caller comparing two scopes uses the SAME rule the key does. An empty
    result is legitimate and means *narrowed to nothing*; see the caller.
    """
    return SCOPE_ITEM_SEPARATOR.join(
        sorted(
            {str(code).strip().casefold() for code in (scope_services or ()) if str(code).strip()}
        )
    )


#: What a catch-up sub-run's key is made of, ON TOP of its parent's. BR-BIL-015
#: / US-BIL-006 §5: *"idempotency key = parent key + scope"*. Named so the two
#: halves of the string are greppable and so nothing composes it as a bare
#: f-string on the other side of a module boundary.
CATCH_UP_MARKER = "catch-up"


def catch_up_run_key(*, parent_key: str, account_ids: Any) -> str:
    """BR-BIL-005 at SUB-RUN granularity: the parent's key + the scope.

    HUMAN-OWNED · HUMAN-REVIEW-PENDING with the rest of this module.

    ── THE RULE, AND WHY THE PARENT'S KEY IS NOT ENOUGH ──────────────────────
    BR-BIL-015 (CONFIRMED, PO A-6 + r1.3): held accounts *"are billed via
    catch-up SUB-RUNS (parent-linked, scope-keyed idempotency — never a
    colliding re-run)"*. A catch-up bills the SAME cycle and the SAME period as
    its parent, so `bill_run_key` above returns the parent's own string for it
    — and the unique index would refuse the child as a duplicate of the run it
    is a child of. That is the whole reason the scope enters the key.

    ── THE SHAPE, WHICH IS THE ONLY THING DECIDED HERE ───────────────────────

        key = "<parent key>|catch-up|<sorted account uuids, comma-joined>"

    Worked, so the string is concrete: parent run 07-A over 1–31 July with
    cycle `018f…0001`, catching up ACC-1201 and ACC-1455 (ids `…a1` and `…b2`)
    gives

        018f…0001|2026-07-01|2026-07-31|catch-up|…a1,…b2

    and re-submitting THAT scope is refused with the first sub-run's id, who
    ran it and when (US-BIL-006 TC-5), while a catch-up over a DIFFERENT held
    subset is a different string and starts normally.

    ── THREE PROPERTIES THE SHAPE IS CHOSEN FOR ─────────────────────────────
      * **SORTED, and by string.** {A, B} and {B, A} are the same scope and must
        not be billable twice by reordering a checkbox list. Sorting the
        rendered uuids (rather than the objects) means the order does not depend
        on what type the caller happened to hold.
      * **DE-DUPLICATED.** A caller that passes the same account twice has named
        one scope, not two; folding the duplicate here stops a key that differs
        only by a repeat from unlocking a second sub-run over one account.
      * **The parent key travels WHOLE, not hashed.** The child's key contains
        its parent's, so a human reading `bill_runs.idempotency_key` in psql can
        see which run a catch-up belongs to without a join. The lineage is also
        a real FK (`parent_run_id`) — the key does not replace it, and the two
        agreeing is checked by `pending.create_catch_up_run`.

    An EMPTY scope is refused rather than keyed. A sub-run over no accounts
    would key as the parent's string plus a marker, issue nothing, and occupy
    the one slot a real catch-up needs.
    """
    if not parent_key:
        raise IdempotencyKeyError(
            "a catch-up sub-run's key is composed on its PARENT's key (BR-BIL-015 — "
            "parent key + scope) and no parent key was given. A key composed without it "
            "would not identify which run this is a catch-up FOR, and two parents' "
            "catch-ups over the same account ids would collide."
        )
    rendered = sorted({str(account_id) for account_id in (account_ids or ())})
    if not rendered:
        raise IdempotencyKeyError(
            "a catch-up sub-run is SCOPED to the held accounts it bills (BR-BIL-015) and "
            "this scope is empty. An empty scope would key as the parent run plus a "
            "marker, bill nobody, and take the one key a real catch-up over that parent "
            "needs."
        )
    return KEY_SEPARATOR.join((parent_key, CATCH_UP_MARKER, ",".join(rendered)))


#: What a ONE-TIME run's key is made of instead of a cycle. US-BIL-010..014
#: (first · final · ad-hoc · back-bill · penalty) bill ONE account over a window
#: a clerk names, and `bill_runs.cycle_id` is NULL on every one of them
#: (migration 0021), so `bill_run_key` above has no cycle to fold in.
ONE_TIME_MARKER = "one-time"


def one_time_run_key(
    *,
    account_id: Any,
    bill_type: str,
    period_start: date,
    period_end: date,
    source: str | None = None,
) -> str:
    """BR-BIL-005 for a run that has no cycle: the ACCOUNT and the KIND stand in.

    HUMAN-OWNED · HUMAN-REVIEW-PENDING with the rest of this module.

    ── THE RULE, AND WHY A ONE-TIME RUN NEEDS ITS OWN SHAPE ──────────────────
    BR-BIL-005 makes a run idempotent so that *"an identical re-run"* is refused
    with who/when/link rather than producing a second set of bills, and B2
    enforces it as `UNIQUE (tenant_id, idempotency_key)`. The signed key names
    the cycle — and a one-time bill has none (BR-BIL-020: the ad-hoc bill is the
    bulk wizard *"in single-account mode"*; BR-BIL-018 puts back-bills through
    the same door). So the SCOPE that identifies the run is the account, and the
    protection BR-BIL-005 exists to give is the protection a clerk most needs
    here: double-clicking "Create bill" is how one customer gets billed twice
    for one move-out, and a final bill is the last one anybody checks.

    ── THE SHAPE, WHICH IS THE ONLY THING DECIDED HERE ───────────────────────

        key = "one-time|<account uuid>|<bill_type>|<start ISO>|<end ISO>"

    Worked, so the string is concrete: a final bill for ACC-1042
    (`018f…a1`) covering 1–12 August 2026 gives

        one-time|018f…a1|final|2026-08-01|2026-08-12

    and a second attempt at that same account, kind and window is refused with
    the first run's id, who ran it and when. A back-bill for the same account
    over the same window is a DIFFERENT string and starts normally.

    ── FOUR PROPERTIES THE SHAPE IS CHOSEN FOR ──────────────────────────────
      * **THE MARKER LEADS.** `one-time|…` cannot collide with a cycle key
        (`<uuid>|<date>|<date>`) or a catch-up key (`…|catch-up|…`) whatever the
        uuids are, so the three run families share one unique index without any
        of them having to know the others' shapes.
      * **THE KIND IS IN THE KEY, and this is the load-bearing one.** A move-out
        on 12 August produces a FINAL bill for 1–12 Aug, and the same account
        and window can legitimately also carry a BACK-BILL for an unbilled
        period that overlaps it (BR-BIL-018 — an arbitrary past period) or a
        PENALTY bill for theft found in it (BR-BIL-019). Those are three
        different documents about three different facts. Keying without the kind
        would let the first of them block the other two, and the clerk would be
        told their theft bill was a duplicate of a final bill.
      * **THE ACCOUNT'S UUID, never its account NUMBER.** BR-TEN-035 makes the
        number a tenant-adjustable series; renumbering a customer must not
        unlock a second bill over a window they have already been billed for.
      * **The tenant is NOT in the string**, for the same reason `bill_run_key`
        leaves it out: it is the other column of the unique constraint, and the
        same fact in two places is a fact that can drift.

    ── `source`: ONE BILL PER EVENT, WHERE ONE DAY CAN HOLD SEVERAL ───────────
    `DEF-PAY-10740`, PO 2026-10-30 (decision log *"One NSF fee per bounced
    payment"*, item 1 — *"Two bounces on the same day: A"*). A `fee` bill is a
    one-day window, so the five-part key allows ONE fee bill per account per
    day. That is right for a reconnection fee (one cut a day) and wrong for the
    NSF penalty, which the PO ruled is owed PER BOUNCED PAYMENT. So a caller
    whose bill answers to a named event passes `source`, appended as a sixth
    part:

        one-time|<account uuid>|fee|2026-10-31|2026-10-31|nsf:<payment uuid>

    Worked: Clara Castillo's cheques $76.40 and $40.00 both return on 31 Oct,
    plan NSF $30.00 → two different keys → two fee bills, **$60.00**; the same
    payment asked twice → the same key → one bill and `DuplicateRun`.

    **`source=None` — every caller but the NSF fee — produces the five-part
    string BYTE FOR BYTE as before**, so no existing run's key moves, and a
    six-part key cannot equal a five-part one. A source containing `|` is
    refused: `a|b` as a source would be indistinguishable from two parts.

    ⚠ **WHAT THIS KEY DELIBERATELY DOES NOT PROTECT.** Two ad-hoc bills over
    DIFFERENT windows for one account are two different keys and both are
    allowed — correctly, because 1–15 July and 16–31 July are two real interim
    bills. Overlapping windows are NOT caught here and are not meant to be:
    `single.held_for_period` (BR-BIL-055) is where a colliding period is refused,
    it refuses on OVERLAP rather than equality, and it can see the pending queue
    that a pure string function cannot. A key is not a period calculus.
    """
    if account_id is None or period_start is None or period_end is None:
        raise IdempotencyKeyError(
            "a one-time bill run's idempotency key needs the ACCOUNT and BOTH period "
            "dates (BR-BIL-005 keys a run on tenant + scope + period; the scope of a "
            "one-time run is its account). A key composed with a part missing would "
            "collide across different bills, which is the double-billing this key "
            "exists to prevent — and on a final bill nobody looks again."
        )
    if not (bill_type or "").strip():
        raise IdempotencyKeyError(
            "a one-time bill run's idempotency key needs its BILL TYPE (B2 r10 #12). "
            "Without it a final bill would block the back-bill and the theft bill that "
            "the same account and window can legitimately also carry — three different "
            "documents about three different facts, refused as duplicates of each other."
        )
    parts = [
        ONE_TIME_MARKER,
        str(account_id),
        bill_type.strip(),
        period_start.isoformat(),
        period_end.isoformat(),
    ]
    if source is not None:
        if not str(source).strip() or KEY_SEPARATOR in str(source):
            raise IdempotencyKeyError(
                "a one-time run's SOURCE names the one event the bill is for (e.g. "
                "'nsf:<payment uuid>', DEF-PAY-10740). It must be non-empty and must not "
                "contain '|', or two different events could compose the same key."
            )
        parts.append(str(source).strip())
    return KEY_SEPARATOR.join(parts)


#: The fifth shape's marker. `new-connect|…` cannot collide with a cycle key
#: (`<uuid>|<date>|<date>`), a scoped one, a catch-up or a one-time run,
#: whatever the uuids are — the same leading-marker discipline every shape
#: above uses so one unique index can hold them all.
NEW_CONNECT_MARKER = "new-connect"


def new_connect_commit_key(*, submit_token: Any) -> str:
    """**CLAUDE.md hard rule 6 for the New Connect commit — `DEF-CUS-8021`.**

    HUMAN-OWNED · HUMAN-REVIEW-PENDING with the rest of this module.

    ── THE DEFECT THIS SHAPE EXISTS FOR, MEASURED RATHER THAN DESCRIBED ──────
    `POST /connections/commit` is the one press that writes a whole build. On
    2026-09-29 the identical payload was posted TWICE with the parcel box empty
    and answered **200 both times**: `CON-26-0130` and `CON-26-0131` — two
    connections, two customers, two master accounts, two properties at one
    address, and **two payments of $250.00, each posting its own balanced
    ledger pair.** With a parcel number typed the second press was refused
    `409 premises.external_ref_taken`, which is a UNIQUENESS CONSTRAINT and not
    idempotency: it refuses by accident of a different rule, only on the
    minority of builds that type a parcel, and it answers an ERROR where rule 6
    asks for the FIRST result.

    ── WHY A CLIENT TOKEN AND NOT A CONTENT HASH ────────────────────────────
    The four shapes above key on facts the SERVER can restate — a cycle, a
    period, an account. A New Connect commit has none: until it lands there is
    no connection, no premises (on the common `new_premise` scope) and no
    account, and the payload's own content is not an identity — two genuinely
    different builds at one address on one day can be byte-identical, and a
    clerk who corrects a typo between two presses would produce a different
    hash for what is plainly the same press. **So the identity has to come
    from the sender**, exactly as it does for the counter payment this repo
    already protects: `apps/payments/idempotency.py` composes
    `entry|<client token>` for US-PAY-001 TC-6, *"double-click Record ✓ → one
    row only"*. This is that precedent, one module over, and it is copied
    rather than re-reasoned.

    ── THE SHAPE, WHICH IS THE ONLY THING DECIDED HERE ───────────────────────

        key = "new-connect|<submit token>"

    Worked, so the string is concrete. A clerk opens New Connect, the wizard
    mints `3f2b91c4-0d55-4a7e-9a0b-1f5d2c7e8a10` once for that build, and both
    halves of a double-click send

        new-connect|3f2b91c4-0d55-4a7e-9a0b-1f5d2c7e8a10

    The first press writes `CON-26-0130` and stores its own answer on the row.
    The second finds that row, writes nothing, and returns the FIRST press's
    answer — one connection, one account, one customer, one premises, one
    payment of $250.00, one balanced ledger pair. A second build started from
    the wizard's front door mints a new token and is a different string.

    ── THREE PROPERTIES THE SHAPE IS CHOSEN FOR ─────────────────────────────
      * **THE TOKEN IS MINTED PER BUILD, NOT PER REQUEST.** A token minted at
        submit time would be a new string on every press and would protect
        nothing — it is the wizard's mount, the thing a clerk thinks of as
        *this build*, that the token names.
      * **THE TENANT IS NOT IN THE STRING.** It is the other column of the
        unique constraint (`UNIQUE (tenant_id, commit_key)` on `connections`),
        for the same reason `bill_run_key` leaves it out: the same fact in two
        places is a fact that can drift, and the tenant is never client input
        (BR-TEN-003). A token a clerk at one utility invents therefore cannot
        reach another utility's build at all.
      * **THE MARKER LEADS AND THE SEPARATOR IS `|`**, so the key stays
        splittable by eye in the psql session where somebody is debugging a
        refused duplicate. Same character and same reasoning as every shape
        above.

    ⚠ **WHAT THIS KEY DELIBERATELY DOES NOT PROTECT, STATED SO NOBODY READS IT
    AS MORE THAN IT IS.** Two builds at one address started from two separate
    openings of the wizard are two tokens and BOTH are allowed — correctly: a
    developer really can raise a second connection at one property, and
    `premises.external_ref` and `BR-CUS-1011`'s one-master-per-premises are
    where a genuine duplicate is refused on its own merits. A key is not a
    duplicate-detector; it makes ONE press idempotent.
    """
    token = str(submit_token or "").strip()
    if not token:
        raise IdempotencyKeyError(
            "a New Connect commit's idempotency key needs the wizard's SUBMIT TOKEN "
            "(CLAUDE.md hard rule 6). A key composed without it would be the bare "
            "string 'new-connect' for every build in the tenant, so the first build "
            "ever committed would block every later one — the mirror of the "
            "double-write this key exists to prevent, and the worse direction."
        )
    return KEY_SEPARATOR.join((NEW_CONNECT_MARKER, token))

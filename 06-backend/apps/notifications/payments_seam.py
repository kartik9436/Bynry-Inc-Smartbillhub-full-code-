# ── Trace ──────────────────────────────────────────────
# Epics:    EP-NOT-03 (the notice RECORD the generation service hands back) ·
#           EP-NOT-04 (the returned-mail event payments consumes)
#           Screens: S8 · S30 · S34 · S35
#           NOTE: no US-ID is cited in this header ON PURPOSE. G10 reads a
#           Trace-header US-ID as "this file ships that story's test cases";
#           this file ships two cross-module contracts, not a story. Same
#           precedent as apps/notifications/tenancy_seam.py.
# Rules:    BR-TEN-013 (a module NEVER touches another module's ORM; a
#           cross-module read resolves the owner's published callable) ·
#           B1 (cross-module WRITES are forbidden — payments writes payments'
#           tables, always, including when notifications hands it an event) ·
#           BR-PAY-018 (returned mail → bad-address flag → paper suppressed
#           until verified; balances unaffected) · BR-CUS-039 (every notice send
#           AND skip appends `notice_history`) · CLAUDE.md rule 1
# Tests:    06-backend/tests/test_def_128_notifications_api.py
# Impacts:  apps/notifications/api.py (GET /notices · POST /deliveries/returned)
# ───────────────────────────────────────────────────────
"""notifications → payments SEAM: the notice RECORD, and the returned-mail flag.

Two contracts, both resolved BY NAME at call time so nothing here imports
payments' internals (B1 / BR-TEN-013):

  apps.payments.notices.notice_history_count(...) -> int
  apps.payments.notices.notice_history_page(offset=, limit=, ...) -> list[dict]
    `notice_history` (B2 r12 #7) is PAYMENTS' table. It is the record a utility
    shows a regulator when a customer says they were never told, and it is what
    `GET /notices` serves — the notice history AND, filtered to the 48-hour
    tier, the certified-mail register.
    ⚠ **THESE TWO REPLACED `notice_history_for(limit=2000)` HERE ON 2026-09-19
    (`DEF-NOT-5750`).** The list took its page in Python behind a 2,000-row
    ceiling, so the 2,001st notice was unreachable on every page and `count`
    was a floor rather than a total. `NoticeHistoryWindow` below joins the two
    into the only two questions Django's paginator asks, so the page is taken
    in the DATABASE and there is no maximum left to be beyond.

  apps.payments.notices.notice_history_for(...) -> list[dict]
    The same record, *last N on one subject*, for a PANEL rather than a list —
    `collections_read.collection_context` draws the last 100 on one account.
    Kept, still published, and **not the way to serve a list**: paging it by
    raising `limit` re-creates `DEF-NOT-5750` exactly.

  apps.payments.returned_mail.mark_returned_bulk(...) -> tuple[ReturnResult, …]
    BR-PAY-018's other half. `apps/notifications/delivery_ops.mark_returned`
    stamps the queue row and EMITS a delivery-return event; payments is what
    turns that event into a needs-attention row and ASKS customers to raise the
    account's bad-address flag (`accounts.bad_address` is customers' column —
    `DEF-PAY-6342`), which is what the S21 banner reads.

╔══════════════════════════════════════════════════════════════════════════╗
║  THIS FILE EXISTS BECAUSE TWO MODULES EACH REPORTED THE SAME GAP AND      ║
║  NEITHER COULD CLOSE IT ALONE.                                            ║
╚══════════════════════════════════════════════════════════════════════════╝
`delivery_ops.py`'s trailer, verbatim (and its *"payments'"* was wrong — the
column is CUSTOMERS', `DEF-PAY-6342`): *"NOTHING HERE WRITES
`accounts.bad_address` (r12 #8 — payments'). `mark_returned` emits the
delivery-return event; **a caller that ignores it leaves the account
unflagged and nothing here can stop that.** REPORTED rather than fixed by a
cross-module write."* `apps/payments/returned_mail.py` is the module that
consumes it and had no caller. Both lanes were honest, both stopped at the
boundary, and the two halves sat unconnected for a day — which is hard-won
law 2 in the space BETWEEN two modules rather than inside one.

`flag_returned_addresses` below is the caller neither lane could write. It does
not write one row of payments' data: it hands payments' own published function
the events and payments writes its own table, which is exactly what B1 asks for.

────────────────────────────────────────────────────────────────────────────
AN UNWIRED SEAM REPORTS. IT NEVER ANSWERS ZERO.
────────────────────────────────────────────────────────────────────────────
DEF-075 is the reason this paragraph is here: a seam resolved to `None`, `None`
was read as *"this module has nothing"* when it meant *"this module cannot
answer"*, and a tenant holding an issued 108.88 USD bill changed its currency at
200 OK. `apps/billing/release.py` states the rule these functions follow — *"'0
of 1,122 hold an address' and 'we could not count' must never render the
same"* — so `notice_history()` returns `(rows, problems)` and a caller that
cannot resolve payments gets an EMPTY rows list beside a problem row saying so,
which the endpoint serves as `available: false`. A screen renders "we cannot
show this" rather than "this customer was never contacted".
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

#: The payments reads this module depends on, named once so each contract is
#: greppable from BOTH sides of the boundary — the discipline
#: `apps/notifications/tenancy_seam.py` states and G20 harvests.
PAYMENTS_MODULE = "payments"
#: r12 #7's `notice_history`, published by its ONLY writer's own module.
NOTICE_HISTORY_KIND = "notices"
#: The *last N on one subject* read. STILL PUBLISHED and still correct for a
#: panel; **it is no longer what `GET /notices` calls** — see `DEF-NOT-5750`.
NOTICE_HISTORY_READ = "notice_history_for"
#: The two reads a LIST stands on, added 2026-09-19 (`DEF-NOT-5750`). A page in
#: SQL and a real total, so nothing is beyond a page and `count` is a count.
NOTICE_HISTORY_COUNT = "notice_history_count"
NOTICE_HISTORY_PAGE = "notice_history_page"
#: BR-PAY-018's consumer — US-PAY-016's flow. The flag it ends in is
#: `accounts.bad_address`, which CUSTOMERS writes at payments' request.
RETURNED_MAIL_KIND = "returned_mail"
RETURNED_MAIL_WRITE = "mark_returned_bulk"

#: Problem codes. CODES, because a screen groups and a report counts on them.
NOTICE_HISTORY_UNAVAILABLE = "notice_history_read_unpublished"
RETURN_CONSUMER_UNAVAILABLE = "returned_mail_consumer_unpublished"


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """The owning module's callable, or None while it has not published one.

    getattr at CALL time — the idiom `apps/notifications/services.py`,
    `apps/notifications/tenancy_seam.py` and `apps/metering/seams.py` all use.
    No import statement binds notifications to payments' internals, and the day
    a lane moves a function this file needs no re-wiring.
    """
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


class NoticeHistoryWindow:
    """A page of payments' notice record, fetched WHEN THE PAGINATOR ASKS FOR IT.

    ⚠ **ADDED 2026-09-19 BY THE `DEF-NOT-5750` LANE, AND IT REPLACES A CAP.**
    Until today this seam called payments' `notice_history_for(limit=2000)` and
    handed the endpoint a built LIST, which DRF then sliced fifty rows out of.
    Two things were wrong with that and only one of them was visible: the list
    cost 2,000 dicts to draw fifty, and **the 2,001st notice was unreachable on
    every page** — `NFR-5` forbids a maximum anywhere, and a single dunning
    cycle over 40,000 accounts writes past 2,000 rows in one night.

    ⚠ **THE CAP COULD NOT BE DELETED ON ITS OWN**, which is why the defect was
    filed and left rather than patched: with the page still taken in Python,
    removing the ceiling turns a bounded 2,000-row build into an UNBOUNDED one.
    The cap and the page had to move in the same change, and this class is the
    join — the page reaches SQL and the ceiling goes.

    ════════════════════════════════════════════════════════════════════════
    WHY A SEQUENCE PROXY AND NOT A QUERYSET, AND NOT A `(rows, count)` PAIR
    ════════════════════════════════════════════════════════════════════════
    **Not a queryset:** `notice_history` is PAYMENTS' table (B2 r12 #7). A
    queryset handed across this boundary would be payments' ORM object living
    in notifications, and slicing it here would be notifications issuing SQL
    against a table it does not own — exactly what `B1` / `BR-TEN-013` forbid
    and what this whole file exists to avoid. **Nothing but `int` and `dict`
    crosses.**

    **Not a `(rows, count)` pair:** that shape needs the endpoint to build the
    `count`/`next`/`previous`/`results` envelope by hand, which already exists
    twice in this repo (`customers._prepaged`, `rating._prepaged`) and whose
    own docstring asks that a THIRD copy trigger a move into `core/` rather
    than be written. This shape needs no copy at all: `StandardPagination` is
    unchanged, so the envelope, the page links and `BR-SHL-011`'s clamp of an
    out-of-range page are byte-for-byte the ones every other list serves.

    Django's paginator asks an object list exactly two questions — `count()`
    and `[bottom:top]` — so answering those two is the whole contract. It costs
    **one `COUNT(*)` and one `LIMIT`/`OFFSET`**, whatever the record holds.

    ⚠ **`__iter__` REFUSES ON PURPOSE.** Without it Python falls back to the
    old sequence protocol and `list(window)` would walk `[0]`, `[1]`, `[2]` …
    one query per row, for ever — an unbounded read wearing the costume of the
    fix. A loud `TypeError` naming this defect is what a lane gets instead.
    """

    #: Django's `Paginator._check_object_list_is_ordered` reads this. The
    #: underlying read orders by `-occurred_on, -created_at` in SQL, so the
    #: answer is True and stating it is honest rather than merely quiet: a page
    #: taken over an unstable order repeats one row and hides another.
    ordered = True

    def __init__(self, *, count_read: Any, page_read: Any, filters: dict[str, Any]) -> None:
        self._count_read = count_read
        self._page_read = page_read
        self._filters = dict(filters)
        self._counted: int | None = None

    def count(self) -> int:
        """`COUNT(*)` through payments' published read — memoised for this request.

        Memoised because `StandardPagination.get_page_number` asks for
        `num_pages` (a count) and `Paginator.page` then asks again; two
        identical `COUNT(*)`s for one screen is a cost nobody chose. Django's
        `Paginator.count` is itself a `cached_property`, so this is belt and
        braces for a caller that builds two paginators over one window.
        """
        if self._counted is None:
            self._counted = int(self._count_read(**self._filters) or 0)
        return self._counted

    def __len__(self) -> int:
        return self.count()

    def __getitem__(self, window: slice) -> list[dict[str, Any]]:
        """`LIMIT`/`OFFSET` through payments' published read. Slices only.

        An integer index is refused rather than served: the paginator never
        asks for one, and answering it would be a second, silent way to read
        this table one row per query.
        """
        if not isinstance(window, slice):
            raise TypeError(
                "the notice record is read a PAGE at a time — index it with a slice. "
                "A single-row lookup here is one query per row (DEF-NOT-5750)."
            )
        if window.step is not None:
            raise TypeError(
                "a stepped slice of the notice record would be honoured by the OFFSET and "
                "silently ignored by the step, so it is refused rather than answered wrong."
            )
        start = int(window.start or 0)
        stop = window.stop
        if stop is None:
            raise TypeError(
                "an open-ended slice of the notice record is an UNBOUNDED read, which is "
                "the defect DEF-NOT-5750 removed rather than a way to read it. Ask for a "
                "page: `window[offset:offset + per]`."
            )
        return list(
            self._page_read(offset=start, limit=max(int(stop) - start, 0), **self._filters) or []
        )

    def __iter__(self) -> Any:
        raise TypeError(
            "the notice record is not iterated whole (DEF-NOT-5750). Iterating it would "
            "read every notice this utility has ever sent into one request's memory, which "
            "is the unbounded read the 2,000-row cap was standing in for. Take a page."
        )


class _EmptyNoticeHistoryWindow(NoticeHistoryWindow):
    """The window a caller gets when payments publishes nothing — EMPTY, never ZERO.

    DEF-075's rule, which this file's header states: *"we could not count"* and
    *"there is nothing"* must never render the same. This answers an empty page
    so a screen has something to draw, and the PROBLEM beside it is what says
    the record could not be opened — `available: false` on the response.
    """

    def __init__(self) -> None:
        super().__init__(count_read=lambda **_: 0, page_read=lambda **_: [], filters={})


def notice_history_window(
    *,
    account_id: Any = None,
    notice_type: str | None = None,
    tier: str | None = None,
    outcome: str | None = None,
) -> tuple[NoticeHistoryWindow, tuple[dict[str, Any], ...]]:
    """(window, problems) — what this utility has told its customers, A PAGE AT A TIME.

    ⚠ **THIS REPLACED `notice_history(…, limit=2000)` ON 2026-09-19
    (`DEF-NOT-5750`).** Hand the window to `StandardPagination` and it takes
    the page in the DATABASE; there is no ceiling anywhere on this path, so the
    2,001st notice — and the 200,001st — is on a page a clerk can open.

    Sends AND skips, because J4 step 2 requires every skip on the trail and an
    account excluded for a medical hold must never look like one nobody chased.

    Tenant scoping is payments' and cannot be lost here: both published reads
    filter on `app.tenant_id` under RLS FORCE and take no tenant argument, so
    this module issues no query and can widen no scope (hard rule 1).

    **BOTH halves must resolve or NEITHER is used.** A window that could count
    but not page — or page but not count — would serve a screen that disagrees
    with its own footer, so a half-published payments answers the same honest
    problem row as an unpublished one.
    """
    count_read = _resolve(PAYMENTS_MODULE, NOTICE_HISTORY_COUNT, kind=NOTICE_HISTORY_KIND)
    page_read = _resolve(PAYMENTS_MODULE, NOTICE_HISTORY_PAGE, kind=NOTICE_HISTORY_KIND)
    if count_read is None or page_read is None:
        missing = ", ".join(
            name
            for name, found in (
                (NOTICE_HISTORY_COUNT, count_read),
                (NOTICE_HISTORY_PAGE, page_read),
            )
            if found is None
        )
        return _EmptyNoticeHistoryWindow(), (
            {
                "code": NOTICE_HISTORY_UNAVAILABLE,
                "br_ref": "BR-CUS-039",
                "detail": f"apps.{PAYMENTS_MODULE}.{NOTICE_HISTORY_KIND} does not publish "
                f"{missing}, so this utility's notice record CANNOT BE READ. That is not "
                "the same fact as 'no notices were sent' and must never render as one: the "
                "answer is 'we cannot show you', because telling a clerk a customer was "
                "never contacted when the record simply could not be opened is how a "
                "disconnection gets defended on a false premise (DEF-075's shape).",
            },
        )
    return (
        NoticeHistoryWindow(
            count_read=count_read,
            page_read=page_read,
            filters={
                "account_id": account_id,
                "notice_type": notice_type,
                "tier": tier,
                "outcome": outcome,
            },
        ),
        (),
    )


def flag_returned_addresses(
    *, events: tuple[Any, ...], returned_on: Any, actor: Any = None
) -> tuple[list[dict[str, Any]], tuple[dict[str, Any], ...]]:
    """Hand payments the delivery-return events so IT sets the bad-address flag.

    (results, problems). `events` are `delivery_ops.DeliveryReturnEvent`s — the
    r12 #8 events notifications emits and does not act on.

    NOTHING HERE WRITES PAYMENTS' DATA. This calls payments' own published
    function, which writes payments' own table under payments' own idempotency
    key (`UNIQUE (tenant, outbound_message_id)`) — so a double-clicked bulk
    mark-returned over a stack of fourteen writes fourteen events, not
    twenty-eight, and the arbiter is the database rather than a check in Python
    that two clerks working the same stack would lose.

    An event with NO account (a staff-addressed report or bookkeeper row —
    `outbound_messages.account_id` is nullable for exactly those) is skipped
    with a reason rather than passed on: there is no account to flag, and
    payments' write requires one.
    """
    consume = _resolve(PAYMENTS_MODULE, RETURNED_MAIL_WRITE, kind=RETURNED_MAIL_KIND)
    if consume is None:
        return [], (
            {
                "code": RETURN_CONSUMER_UNAVAILABLE,
                "br_ref": "BR-PAY-018",
                "detail": f"apps.{PAYMENTS_MODULE}.{RETURNED_MAIL_KIND}."
                f"{RETURNED_MAIL_WRITE} is not published, so the queue rows were stamped "
                "returned and NO ACCOUNT WAS FLAGGED bad-address. The letters will keep "
                "going to the same address. Reported on the response rather than left to "
                "be inferred from a flag that never appeared.",
            },
        )
    pieces = []
    problems: list[dict[str, Any]] = []
    for event in events:
        if getattr(event, "account_id", None) is None:
            problems.append(
                {
                    "code": "return_event_has_no_account",
                    "br_ref": "BR-PAY-018",
                    "message_id": getattr(event, "message_id", None),
                    "detail": "this queue row belongs to no customer account (a scheduled "
                    "report or a bookkeeper copy — US-NOT-015), so there is no address to "
                    "flag. The row is stamped returned and nothing downstream happens.",
                }
            )
            continue
        pieces.append(
            {
                "account_id": event.account_id,
                "outbound_message_id": event.message_id,
                "channel": event.channel,
            }
        )
    if not pieces:
        return [], tuple(problems)
    results = consume(pieces=tuple(pieces), returned_on=returned_on, actor=actor)
    return (
        [
            {
                "event_id": getattr(result, "event_id", None),
                "account_id": getattr(result, "account_id", None),
                # `created=False` is a REPLAY, not a failure: this envelope was
                # already marked returned and the account is already flagged.
                "created": bool(getattr(result, "created", False)),
                "detail": getattr(result, "detail", None),
            }
            for result in (results or ())
        ],
        tuple(problems),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-014@a1f3c07 (sha1[:7] of the four sources this seam was authored from, concatenated in order: 04-docs/05-modules/10-notifications/06-epics/EP-NOT-04-delivery-ops.md — US-NOT-014 §5's delivery-return event → payments consumes — · EP-NOT-03-notices-contracts.md — US-NOT-009 §5's notice_history rows — · 04-docs/02-decisions/02-database-design-brief.md Addendum r12 #7 + #8 · 12-governance/10-defect-log.csv DEF-128, so a later change to any of them makes this stamp findable as stale in one grep. The packet names a STORY and not the defect because G1 requires one; the Epics header above is what G10 reads, and this file ships two cross-module contracts rather than a story's test cases)
# generated: 2026-08-16 by story-coder (DEF-128 notifications API lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · G20: ALL FOUR declared contracts resolve at the declared
#         kind (apps.payments.notices — `notice_history_for`, `notice_history_count`,
#         `notice_history_page` — and apps.payments.returned_mail) — no parked
#         row is needed for this seam · tests/test_def_128_notifications_api.py
#         drives the unwired branch of BOTH functions and asserts they REPORT
#         rather than answer zero (RED-proved by unpublishing each read) ·
#         tests/test_def_not_5750_notices_page_in_sql.py drives the HALF-published
#         branch that `NoticeHistoryWindow` added, and asserts the page is a
#         `LIMIT` rather than a returned row count
# amended: 2026-09-19 by the `DEF-NOT-5750` lane — `notice_history(limit=2000)`
#         became `notice_history_window`, which takes the page in payments' own
#         SQL. The 2,001st notice was unreachable on every page of `GET /notices`
#         (`NFR-5`), and the cap could not be removed on its own without turning
#         a bounded 2,000-row build into an unbounded one. Two new contracts,
#         both named in the constants above and in the module docstring.
# exceptions: (1) `notice_history_for` DID NOT EXIST until this lane and was
#         added to `apps/payments/notices.py` — the table's owning module and
#         its only writer. A read published from anywhere else would be
#         notifications reaching into payments' ORM (B1).
#         (2) THE RETURN CONSUMER IS CALLED FROM THE ENDPOINT, NOT FROM
#         `delivery_ops.mark_returned`. The service keeps its documented posture
#         — it emits the event and acts on nothing — so a batch caller can still
#         mark rows without triggering payments; the HTTP surface is where a
#         human asked for the whole BR-PAY-018 flow and gets it.
#         (4) `notice_history_for` IS STILL DECLARED AND STILL RESOLVES, and it
#         is no longer what `GET /notices` calls (2026-09-19). It is the *last N
#         on one subject* read `apps/payments/collections_read.py` uses for a
#         per-account panel; a LIST asks `notice_history_page` +
#         `notice_history_count`, which have no ceiling. Both are kept because
#         they answer different questions, not because one is a fallback.
#         (3) NO MEDICAL-HOLD READ AND NO BALANCE READ. Both are named as
#         arguments by `apps/notifications/notices.py` for reasons that have not
#         changed (customers publishes neither), and adding a guess here would
#         put a clinical fact and a money figure in the wrong module.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

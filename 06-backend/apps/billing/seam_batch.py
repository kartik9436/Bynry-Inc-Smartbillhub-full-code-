# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-002 (S31.2 findings — the prepare pass) · US-BIL-004
#           (phase 2 calculate)   Screens: S31 steps 2 and 4
# Rules:    B1 (cross-module reads go through SEAMS, never imports) ·
#           BR-BIL-039 (stages 1-5 are pure; `gather` is the only reader) ·
#           BR-RAT-007/017 (a tariff is resolved AT the service date — so a
#           key that omits the date is a wrong answer, not a slow one) ·
#           CLAUDE.md rule 1 (tenant scoping — the cache never outlives the
#           pass and therefore never outlives the tenant context)
# Change:   CR-051 task 22 — *"Give each of the 8 seams a plural form — ask
#           once for a thousand accounts, not a thousand times for one."*
# Tests:    06-backend/tests/test_cr051_run_scale.py (tc8, tc9)
# Impacts:  apps/billing/gather.py (`_resolve` consults this) ·
#           apps/billing/runs.py (`prepare_run` opens ONE cache per pass)
# ───────────────────────────────────────────────────────
"""CR-051 task 22 — ask the run's shared questions once, not once per account.

⚠ **THIS IS NOT A PRICING MODULE AND MAY NEVER BECOME ONE.** CR-051's second
hard rule (PO 2026-08-30, *"when you build billing logic ensueyou use r1 to r7
that we build and wire it"*) forbids a lane adding narrowing logic anywhere but
the R1–R7 chain, and it names the exact trap this file could be:

> *"a 'plural seam' is exactly where narrowing logic gets rebuilt by accident.
> A plural seam asks the SAME question for many accounts — it must not answer a
> different one."*

So the whole of this module is a MEMO. It calls the same seam, with the same
arguments, and returns what that seam returned. It contains no rule, no
fallback, no default and no best match. There is deliberately nothing here that
could disagree with a seam, because it never computes anything.

────────────────────────────────────────────────────────────────────────────
WHY, WITH THE MEASUREMENT (CR-051 task 21)
────────────────────────────────────────────────────────────────────────────
Measured on real PostgreSQL 16, `10-scripts/cr051_run_benchmark.py`, **with
row-level security ENFORCED** — the first figures published for this were taken
on a superuser connection, which is exempt from RLS and made the run look about
a quarter cheaper than it is (`DEF-2717`). These supersede them:

    accounts    ready    prepare   calculate     total   ms/account
         100       98      15.3s        1.5s     16.9s          172
       1,000      979     152.3s       16.3s    168.6s          172
       5,000    4,895     781.6s      108.3s    889.9s          182
      10,000    9,791    1899.6s      247.9s   2147.4s          219

⚠ **THE LAST TWO ROWS WERE TAKEN ON A MACHINE FIVE OTHER LANES WERE USING (load
5-7 on four cores), AND THE STATEMENT COUNT IS WHAT SAYS SO:** it is 111 per
account at every size, dead flat, while the wall clock drifts from 172 to 219
ms. A query count does not care what else the machine is doing; a wall clock
does. Read ~172 ms as the rate and the two larger figures as upper bounds.

**The prepare pass is 84% of the cost and it is where the seams are.** The CR
counted the shape before anyone timed it — *"Gathering ONE account opens 23
named cross-module reads through 8 seams; several are per SERVICE. At 10,000
accounts that is upwards of 230,000 round trips before a single row is
written"* — and the per-account count is almost exactly right: **24.0 named
cross-module reads per account**, measured, 23,493 over 979 accounts.

⚠ **THE "8 SEAMS" HALF IS AN UNDERCOUNT AND THE MEASUREMENT SAYS SO: THERE ARE
TWENTY.** `10-scripts/cr051_run_benchmark.py --seams` names every one. The
correction is recorded in `12-governance/02-decision-log.md` rather than only
here, because the CR's own figure is what a later reader would size work
against.

The saving is not subtle, because a small utility has a handful of PLANS and
exactly one set of regional settings. Asking *"what does plan P charge for
water?"* ten thousand times gets the same answer ten thousand times. Measured
at 1,000 accounts, before and after:

    prepare        152.3s -> 124.7s     (-18%)
    SQL statements 108,852 -> 84,487    (-22%)
    whole run      168.6s -> 140.3s     (172 -> 143 ms/account)
    per account    111 -> 86 statements (-22%, and flat at every size)
    seam calls     23,493 -> 10,832     (12,661 not made, 54%)

Measured the same way at all three sizes, so the saving is not one reading:
**100 accounts 16.9s -> 14.2s · 1,000 168.6s -> 140.3s · 5,000 889.9s ->
718.6s.** The statement figures are the ones to trust on a shared machine.

────────────────────────────────────────────────────────────────────────────
THE RULE FOR PUTTING A SEAM ON THIS LIST, AND IT IS STRICT
────────────────────────────────────────────────────────────────────────────
A seam may be memoised for one pass only when ALL of these hold:

1. **Its arguments fully determine its answer.** No hidden input — no clock, no
   request, no ambient state beyond the tenant context, which the pass holds
   fixed. `BATCHABLE` records the KEY for each entry, and a key that omits an
   argument is a wrong answer rather than a fast one (BR-RAT-007: a tariff
   resolved at the wrong service date is the defect this repo exists to avoid).
2. **The pass does not write what it reads.** `BR-BIL-039` makes stages 1-5
   pure and `gather` is the only reader in the run, so within one prepare pass
   nothing billing does can change any of these answers.
3. **Nothing mutates the answer.** Every call site was read before its seam
   went on the list; a caller that mutated a returned list would corrupt the
   next account through the shared object, and no test would necessarily see
   it. This is the reason the list is short and named rather than "cache
   everything that is hashable".

⚠ **AN ACCOUNT-KEYED SEAM IS NOT ON THIS LIST AND MUST NOT BE.** Each account
is gathered once per pass, so memoising `customers.covered_unit_ids(account)`
or `customers.service_off_windows(account, …)` saves nothing and buys a whole
new class of bug for it.

────────────────────────────────────────────────────────────────────────────
THE LINE BETWEEN THIS AND A CACHE, WHICH IS A PO RULING AND NOT A PREFERENCE
────────────────────────────────────────────────────────────────────────────
**A stored answer is forbidden. This is not a stored answer.** The PO ruled on
the prepare pass in these words (`12-governance/02-decision-log.md` 2026-08-30,
closing `OQ-843`, verbatim):

> *"it is dyanmic, so at the time of compute if data is changed, process will
> dynamically use it becuase it will collect data at that instansce"*

A clerk who fixes a plan and reloads must see the fix. So the run's findings
may NOT be computed once and served again — not in a table, not in Redis, not
on the model, not in a module-level dict. That row ends *"A lane may not reopen
this by proposing a cache."*

**What this module does is a different thing, and the difference is lifetime.**
The memo lives inside ONE computation and is destroyed in a `finally` before
the request returns (`pass_cache`, and tc9 asserts it). Within that one pass it
stops the SAME question being asked a thousand times; across two requests it
does not exist, so every request still collects its data at that instant —
which is precisely what the ruling asks for.

Stated as the rule a later lane needs, because this boundary is easy to cross
while believing you are following the same reasoning:

    ALLOWED    one pass asks a seam once instead of once per account
    FORBIDDEN  a second pass reusing anything the first one learned

⚠ **THIS APPLIES TO `GET /billing/runs/{id}/findings` TOO, AND IT IS THE SCREEN
THAT MADE THE QUESTION URGENT.** Measured (CR-051 task 26): at 1,000 accounts
the prepare pass costs 66,053 SQL statements and the findings screen costs
66,054 — **one statement apart**, because `selectors.findings_dict` calls
`prepared_for`, which IS the pass. So the memo already applies to the screen in
full (89,461 → 66,053, −26%) and no separate work is needed for it. What is NOT
available for that screen is a stored result, for the ruling above.

**AND THAT SAME RULING ASKED FOR THIS MODULE BY NAME**, which is worth reading
before deciding the screen is untouchable: *"The remainder is a PERFORMANCE
question and belongs to CR-051 task 21 — measure at 100, 1,000 and 10,000
accounts, then make the pass FASTER (plural seams, bulk write), never cache
it."* Plural seams ARE this file. So the memo is not a loophole in the ruling;
it is the work the ruling handed to CR-051. `tc18` holds both halves.

────────────────────────────────────────────────────────────────────────────
WHAT THIS DOES **NOT** FIX, STATED SO NOBODY READS IT AS DONE
────────────────────────────────────────────────────────────────────────────
**10,832 seam calls remain at 1,000 accounts, and 8,811 of them are seams asked
exactly ONCE per account.** `NOT_BATCHABLE_MEASURED` below names every one.
There is no duplication left in them for a memo to remove: a true plural form
needs the OWNING module to publish a `…_for_units(unit_ids)` or
`…_for_accounts(account_ids)` selector, and adding one to
`apps/metering/selectors.py` or `apps/customers/selectors.py` is that module's
to do, not billing's (B1: billing asks, the owner answers). That is `DEF-2704`,
raised rather than answered, and it is the second half of CR-051 task 22.

**So this file closes the repeated half of task 22 and states the size of the
half it does not close.** A comment claiming otherwise would be hard-won law 1
exactly: a note is not a plan.
"""

from __future__ import annotations

import functools

import threading
from contextlib import contextmanager
from typing import Any

from core import batch_reads as core_batch_reads

#: The seams this module may memoise for the length of ONE pass, and the reason
#: each is safe. `True` means "key on every argument"; the note records what the
#: answer actually depends on, so a reviewer can check the key against it.
#:
#: Read this table as the answer to CR-051's *"Find the eight; do not guess at
#: them"* — the eight are the seams a prepare pass asks repeatedly, and they were
#: found by counting the calls a real pass makes (`10-scripts/cr051_run_benchmark
#: .py`, and the per-seam count in 12-governance/02-decision-log.md), not by
#: reading the imports and picking likely-looking names.
BATCHABLE: dict[tuple[str, str], str] = {
    # ── TENANT-keyed: one answer for the whole run, asked once per account ──
    ("tenancy", "regional_settings"): (
        "the tenant's own settings — no arguments at all, so one answer per "
        "pass by construction. `gather._tenant_currency` asks it once per "
        "account and the currency of a tenant cannot change mid-pass."
    ),
    ("tenancy", "service_ids_by_code"): (
        "the PLATFORM service catalogue's `{code: id}` (BR-TEN-025), which "
        "stage 6 reads once per account to stamp `invoice_lines.service_id`. "
        "No arguments, and billing writes nothing to that catalogue — this is "
        "the only entry on this list reached from the CALCULATE half rather "
        "than the prepare pass, through `tenancy_seam._resolve`."
    ),
    ("tenancy", "bill_logo"): (
        "WHICH logo a bill is stamped with (`CR-172-BRC10`) — no arguments, "
        "the tenant's own logo reference, asked once per account by stage 6 "
        "and again at issue. One answer per pass, exactly as the regional "
        "settings above: a logo uploaded while a pass runs reaches the next "
        "pass, the same as a currency change would."
    ),
    ("tenancy", "service_names_by_code"): (
        "the same PLATFORM catalogue's `{code: name}` (`DEF-2852`), stamped "
        'into `bill_payload["services"]` once per account so the document '
        "can head a charge block *Water* instead of the service's UUID. Same "
        "shape and same safety as the entry above: no arguments, read-only, "
        "and a catalogue billing never writes to."
    ),
    # ── PLAN-keyed: a small utility has a handful of plans and thousands of
    #    accounts, so this is where the ten-thousand-to-three collapse happens ──
    ("rating", "plan_ref"): (
        "the published plan header for a plan id (BR-RAT-030). Read-only: "
        "`gather_account` reads `plan['id']`, `['name']` and `['version']` and "
        "writes nothing back."
    ),
    ("rating", "plan_rate_schedules"): (
        "the plan's bound schedules at a SERVICE DATE — the key carries the "
        "date, because BR-RAT-007 makes a schedule resolved at the wrong date "
        "a different answer rather than a stale one."
    ),
    ("rating", "plan_jurisdiction_pricing"): (
        "BR-RAT-102's outside-city factor and its per-service exemptions, "
        "stated by the PLAN. `gather._plan_jurisdiction` already treats it as "
        "a plain dict of facts."
    ),
    ("rating", "billable_charge_codes"): (
        "BR-RAT-117's recurring and auto-apply codes for a plan, at a date, "
        "for a customer class and a set of services — the same five-fact "
        "question as the taxes above."
    ),
    ("rating", "discount_treatments_for_taxes"): (
        "how each tax treats a discount (BR-RAT-106 / DEF-652), keyed on the "
        "tax ids. A run has as many distinct tax sets as it has plans."
    ),
    ("rating", "charge_price_boundaries"): (
        "the days a BASE charge code's price changes inside a bill period, for "
        "a set of services (CR-156-BRC10) — asked once per account by every "
        "splitting path (`midperiod.split_boundaries`, `backbill.groups_split_"
        "by_days`) with the SAME (services, start, end) for every account on a "
        "cycle. Read-only, and the price rows cannot change mid-pass: a save is "
        "a clerk's act on another request."
    ),
    ("rating", "pricing_inputs"): (
        "the rate-schedule version and its rows for a service at a date — the "
        "single heaviest read in the pass, and the one most obviously shared: "
        "every account on a plan resolves the identical version. Measured at "
        "2,937 calls over 979 accounts, of which 6 reach rating."
    ),
    ("rating", "pricing_inputs_for_version_id"): (
        "THE SAME PROJECTION, asked for a version the R1–R7 chain NAMED rather "
        "than one resolved by date (`resolution_switch`'s R2 fork, 2026-08-31). "
        "Its key is the whole question — version id, service date, size class — "
        "and it collapses on exactly the argument the entry above collapses on: "
        "a small utility has a handful of plans, so the accounts on one plan "
        "name one version between them. It is asked ONLY where the chain's "
        "version differs from the one already on the gathered tariff, which is "
        "0 of 47 accounts on the seeded utility today; the equal case is a "
        "provable no-op and issues no read at all."
    ),
    # ── Asked SEVERAL TIMES FOR ONE ACCOUNT: not a plural form across accounts
    #    but the same duplication, and the measurement found it ──
    ("customers", "covered_unit_ids"): (
        "BR-CUS-068's coverage, asked THREE TIMES for one account — once by "
        "`prepare_run`'s scope check, once by `readings_for_account` and once "
        "by `gather_account`, and `prepare_run`'s own comment says the "
        "repetition is deliberate because the other two are called from paths "
        "that loop never runs. It returns a `list[str]` that `gather."
        "covered_units` immediately copies into a tuple and never mutates, so "
        "one answer can serve all three."
    ),
    ("metering", "unit_row"): (
        "the unit row, asked TWICE for one account (`gather_account` and "
        "`_coverage_facts`) and read-only at every call site — nothing in "
        "`gather` assigns to a unit. Keyed on the unit id, so a master "
        "account's covered units each get their own answer."
    ),
}

#: Seams the measurement found are asked once per account and CANNOT be
#: memoised, recorded here because a list of what was tried and rejected is
#: worth more to the next lane than a list of what worked (hard-won law 1).
#:
#:   * `rating.plan_tax_rules` — was on the list above and is measured at 979
#:     asks and ZERO serves over 979 accounts. It takes `account_id` (DEF-383:
#:     the exemption CERTIFICATE is per account) and a `premises` dict, so the
#:     question is genuinely different for every account and the dict has no
#:     hash anyway. It is not a repeated question; it only looked like one.
#:   * `metering.billing_reads_for_unit`, `metering.connection_size_for`,
#:     `metering.service_points_for`, `metering.dispute_holds_for_unit`,
#:     `rating.unit_plan_assignments_in`, `rating.billable_discount_rules`,
#:     `customers.service_off_windows`, `customers.primary_contact_name` —
#:     each measured at exactly 1.0 calls per account. There is no duplication
#:     to remove: a plural form for these needs the OWNING module to publish a
#:     `…_for_units(unit_ids)` / `…_for_accounts(account_ids)` selector, which
#:     is that module's to write (B1). See `DEF-2704`, which carries the
#:     measured table and the nine names.
NOT_BATCHABLE_MEASURED = (
    "rating.plan_tax_rules",
    "metering.billing_reads_for_unit",
    "metering.connection_size_for",
    "metering.service_points_for",
    "metering.dispute_holds_for_unit",
    "rating.unit_plan_assignments_in",
    "rating.billable_discount_rules",
    "customers.service_off_windows",
    "customers.primary_contact_name",
)


class _PassCache:
    """One prepare pass's answers. Not thread-shared and not long-lived.

    A plain dict rather than Django's cache framework on purpose: this must be
    impossible to configure, impossible to persist and impossible to reach from
    another request. The instant the pass ends the object is unreferenced.
    """

    __slots__ = ("answers", "asked", "served")

    def __init__(self) -> None:
        self.answers: dict[Any, Any] = {}
        #: Per-seam counters, so a lane can see what the cache actually bought
        #: without instrumenting the ORM. Read by the benchmark and by tc8.
        self.asked: dict[str, int] = {}
        self.served: dict[str, int] = {}

    def call(self, name: str, found: Any, args: tuple, kwargs: dict) -> Any:
        key = _key(name, args, kwargs)
        if key is None:
            # An argument nothing can hash — a queryset, a list, a dict. The
            # call goes straight through. A cache that guessed at a key for an
            # unhashable argument would be a cache that answers the wrong
            # question, which is worse than no cache at any speed.
            self.asked[name] = self.asked.get(name, 0) + 1
            return found(*args, **kwargs)
        if key in self.answers:
            self.served[name] = self.served.get(name, 0) + 1
            return self.answers[key]
        self.asked[name] = self.asked.get(name, 0) + 1
        answer = found(*args, **kwargs)
        self.answers[key] = answer
        return answer

    def saved(self) -> int:
        """How many seam calls this pass did NOT have to make."""
        return sum(self.served.values())


def _key(name: str, args: tuple, kwargs: dict) -> Any:
    """A hashable key over EVERY argument, or None when there is not one.

    ⚠ **EVERY ARGUMENT, NO EXCEPTIONS.** Dropping one is how a cache starts
    answering a different question — BR-RAT-007's service date is the argument
    that would do it here, and a tariff priced at the wrong version is the
    defect the whole repository is arranged to prevent.
    """
    # ⚠ AND EVERY READ CONTEXT THAT IS PART OF THE QUESTION (`CR-167-BRC10`,
    # `BR-RAT-1066`): rating's plan reads answer for the plan VERSION in force
    # on the day `gather_account` opened (`plan_versioning.pricing_day`), so
    # `plan_rate_schedules(plan)` for a December segment and for a January one
    # are two questions. `None` when no context is open, so every key made
    # outside one is unchanged.
    try:
        key = (
            name,
            args,
            tuple(sorted(kwargs.items(), key=lambda pair: pair[0])),
            core_batch_reads.context_key(),
        )
        hash(key)
    except TypeError:
        return None
    return key


_STATE = threading.local()


def active() -> _PassCache | None:
    """The cache for the pass running on THIS thread, or None."""
    return getattr(_STATE, "cache", None)


@contextmanager
def pass_cache():
    """One cache for the duration of one prepare pass. Re-entrant, not nested.

    ⚠ **IT MUST NOT OUTLIVE THE PASS, AND THAT IS A PRODUCT RULE RATHER THAN A
    TIDINESS ONE.** `selectors.prepared_for` states it: *"Recomputed on every
    call and cached nowhere. A prepare pass reads meters, plans and accounts as
    they stand, and a clerk who fixes a plan and reloads must see the fix; a
    cached findings set would show them the world as it was when they first
    opened the wizard."* That promise is about the pass, and this keeps it: the
    clerk's reload is a new pass, a new cache, and the fix is visible.

    A nested call reuses the OUTER cache rather than starting a second one — one
    pass has one cache, and a second inside it would be two answers to one
    question with no way to say which the bill used.
    """
    existing = active()
    if existing is not None:
        yield existing
        return
    cache = _PassCache()
    _STATE.cache = cache
    try:
        yield cache
    finally:
        # `finally`, so an account that raises mid-pass cannot leave a cache
        # standing for the next request on this thread — which in a WSGI worker
        # is a different tenant (CLAUDE.md rule 1).
        _STATE.cache = None


def wrap(module: str, attribute: str, found: Any) -> Any:
    """`found`, memoised for this pass — or `found` itself.

    Called from `gather._resolve`, which is the ONE place billing turns a seam
    name into a callable, so nothing can reach a seam around this and nothing
    has to remember to use it (hard-won law 2: a thing you must remember to
    wire is a thing that is not wired).
    """
    cache = active()
    if cache is None or found is None or (module, attribute) not in BATCHABLE:
        return found
    name = f"{module}.{attribute}"

    # ⚠ **`functools.wraps` IS NOT COSMETIC HERE — WITHOUT IT THIS WRAPPER
    # SILENTLY REMOVED THE CONNECTION SIZE FROM EVERY PRICED BILL (`DEF-2387`).**
    # `gather._call_pricing_inputs` decided whether rating accepts a size by
    # counting `signature(resolver).parameters`, and the closure below has
    # exactly two — `*args` and `**kwargs` — so inside a prepare pass the probe
    # answered *"this rating cannot take a size"* and dropped it. The per-size
    # ladder `DEF-433` opened was therefore never selected on any bill produced
    # through a run: the sized tiers were in the database, `pricing_inputs`
    # returned them correctly when asked directly, and the bill priced on the
    # every-size ladder. No figure has ever moved, because every seeded schedule
    # in this repo has an empty size axis — the first schedule to carry one
    # (`CR-063`'s fire ladder) is what found this.
    #
    # `wraps` copies `__wrapped__`, and `inspect.signature` follows it, so the
    # probe now sees rating's real three parameters. It is the correct fix for
    # EVERY seam on this list rather than for the one that was caught: any
    # caller that introspects a seam is asking about the seam, not about the
    # memo, and a wrapper that answers for itself is a check that cannot fail.
    @functools.wraps(found)
    def batched(*args: Any, **kwargs: Any) -> Any:
        return cache.call(name, found, args, kwargs)

    return batched


__all__ = ["BATCHABLE", "active", "pass_cache", "wrap"]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-051@task22 (12-governance/11-change-requests.md §CR-051 task 22 and its SECOND HARD RULE · 04-docs/02-decisions/01-architecture.md B1 seams · BR-BIL-039)
# generated: 2026-08-31 by the CR-051 W2/W5/W6 backend lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — this lane touched no file under 07-frontend) F✔ G✔ H=n/a(not a 🔒 path: this module computes nothing and reaches no money callable, asserted by tests/test_cr051_run_scale.py::tc12)
# gates: ruff✔ black✔ · pytest tests/test_cr051_run_scale.py · golden 33/33 unchanged before and after
# exceptions: (1) the memo is opened by `runs.prepare_run` and not by its callers, so no caller can forget it (law 2) · (2) the UNIT-keyed seams are NOT closed by this file — a true plural form needs metering to publish a bulk selector, which is metering's to write (B1); recorded in the decision log and as an open question rather than as a comment
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

"""`DEF-CUS-6550` — the eight base-charge refusals a CLERK reads are short.

WHAT WENT WRONG
---------------
ACC-06's *The draft bill* panel prints the engine's refusal **verbatim**, on
purpose (`DEF-CUS-6464`: a paraphrase behind a catalogue key would be a second
copy of an engine message, free to drift from the engine). That is the right
design and it means the LENGTH is the engine's problem, not the screen's.

Walked in a browser on `brazosbend` account `A-10432` on 2026-09-24, what a
clerk actually read was **63 words over four sentences, the longest 32**:

    service electric: base charge code BASE-E prices per connection size and
    states no amount for size None. An unpriced size is REFUSED and never
    substituted (PO ruling 2026-08-28) — charging this connection another
    size's rate is not charging it for the connection it has. Price that size
    on the charge code, or record the connection's size. The run continues for
    every other account.

**B14 rule 32** forbids a rule id or internal code in clerk-facing copy.
**B14 rule 33** caps a FACT at six words, an INSTRUCTION at six words per
sentence, and puts RATIONALE — *why the product works this way* — at **zero
words on screen**. That message breaks all three, and it is one of EIGHT
siblings in two files that reach the same panel.

WHY NOTHING CAUGHT IT, AND WHY THIS FILE IS THE THING THAT WILL
---------------------------------------------------------------
B14 rules 32 and 33 are **RATIFIED and UNENFORCED** — their own status cells
say so — and no gate in this repository reads rendered output. `G33` does cap a
refusal at six words per sentence, but it walks **`en.json` values**, and these
sentences are composed in Python and quoted straight onto the screen. So they
sit in the one gap between the two checks that exist: `tsc`, `G15`, `G18` and
`G32` are all green over a 63-word paragraph.

This file closes that gap for the base-charge family by BUILDING each of the
eight sentences through the functions that compose them and reading the words.

⚠ **IT WAS PROVED RED BEFORE IT WAS TRUSTED GREEN** (CLAUDE.md hard-won law 7),
in the harness that runs it — `pytest`, not a `__main__` — both ways: with the
old 63-word sentence restored (`longest sentence is 32 words`) and with a
`BR-RAT-088` put back into a short one (`names BR-RAT-088`).
"""

from __future__ import annotations

import re
from decimal import Decimal

import pytest

from apps.billing import gather
from apps.rating import models, selectors
from apps.tenancy import models as tenancy_models

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


# ── WHAT RULE 33 ACTUALLY SAYS, AS TWO NUMBERS AND ONE PATTERN ──────────────
#
# A FACT is six words; an INSTRUCTION is six words PER SENTENCE and *"two
# sentences of six beat one sentence of twelve"*. `G33`'s own reading of the
# same ruling adds the second number — *"at most two sentences per message"* —
# and this file uses both, because a refusal is one fact followed by one
# instruction and there is no third thing it is for.
WORDS_PER_SENTENCE = 6
SENTENCES = 2

#: Sentence splitting is `G33`'s, deliberately crude and deliberately
#: GENEROUS: split on `.`/`!`/`?` followed by whitespace, count whitespace
#: tokens. A message that fails this counter is long by any reading of it. It
#: is copied rather than imported because `G33` lives in `10-scripts/gates`,
#: which the backend suite does not import — and two counters that disagree
#: would be worse than one, so any change here belongs in both.
_SENTENCE = re.compile(r"(?<=[.!?])\s+")

#: B14 rule 32 — *no rule id or internal code in clerk-facing copy*. The four
#: families CLAUDE.md's Screen IDs section mints, plus `CR-` (change requests,
#: which two of these sentences quoted) and a bare screen id like `S9` or `S11`
#: — the two this family named out loud.
#:
#: ⚠ **`S\d` NEEDS THE WORD BOUNDARY BEHIND IT**, or it matches the `S1` inside
#: a perfectly innocent code. Proved: the pattern is run against `BASE-E-COM`
#: and `W-58` below and must NOT fire.
#:
#: ⚠ **THE MODULE SEGMENT IS OPTIONAL AND THE TRAILING LOOKAHEAD IS
#: LOAD-BEARING**, both for CLAUDE.md's own reason: `DEF-154` and
#: `DEF-CUS-6550` are the same family, and without `(?!\d)` a five-digit id
#: reads as a four-digit one — which is `DEF-2804`, a real id read for a
#: different real id. It matters here because the id is printed in the failure
#: message a lane reads, and half an id sends them to the wrong rule.
_ID = re.compile(
    r"\b(?:BR|DEF|OQ|GT|TC|IS|ADR|CR)-(?:[A-Z]{3}-)?\d{1,5}(?!\d)|\bS\d{1,3}\b"
)

#: A dated ruling is RATIONALE wearing a citation's clothes — *"(PO ruling
#: 2026-08-28)"* was in the live sentence. Rule 33 puts the whole of why at
#: zero words, so a date has no business on the screen either.
_RULING_DATE = re.compile(r"\b20\d\d-\d\d-\d\d\b")


def assert_clerk_copy(text: str, *, what: str) -> None:
    """Refuse a clerk-facing sentence that breaks B14 rule 32 or rule 33."""
    assert text, f"{what}: there is no sentence at all"
    sentences = [part for part in _SENTENCE.split(text.strip()) if part.strip()]
    assert len(sentences) <= SENTENCES, (
        f"{what}: {len(sentences)} sentences, cap is {SENTENCES} — {text!r}"
    )
    for sentence in sentences:
        words = sentence.split()
        assert len(words) <= WORDS_PER_SENTENCE, (
            f"{what}: longest sentence is {len(words)} words, cap is "
            f"{WORDS_PER_SENTENCE} — {sentence!r}"
        )
    found = _ID.search(text)
    assert found is None, f"{what}: names {found.group(0)} to a clerk — {text!r}"
    dated = _RULING_DATE.search(text)
    assert dated is None, f"{what}: quotes the ruling date {dated.group(0)} — {text!r}"


# ════════════════════════════════════════════════════════════════════════════
# THE COUNTER ITSELF — because a check nobody can describe a FALSE PASS for is
# a check nobody understands (hard-won law 7, habit 2).
# ════════════════════════════════════════════════════════════════════════════
def test_the_counter_refuses_the_sentence_this_defect_was_filed_for():
    """The live 63-word paragraph, restored, must FAIL this file's own check."""
    live = (
        "service electric: base charge code BASE-E prices per connection size "
        "and states no amount for size None. An unpriced size is REFUSED and "
        "never substituted (PO ruling 2026-08-28) — charging this connection "
        "another size's rate is not charging it for the connection it has. "
        "Price that size on the charge code, or record the connection's size. "
        "The run continues for every other account."
    )
    with pytest.raises(AssertionError, match="sentences, cap is 2"):
        assert_clerk_copy(live, what="the sentence of 2026-09-24")


def test_the_counter_refuses_a_rule_id_in_a_short_sentence():
    """Six words a side and still unlawful, because rule 32 is separate."""
    with pytest.raises(AssertionError, match="names BR-RAT-088"):
        assert_clerk_copy(
            "Two base charges for electric. BR-RAT-088 picks the code.",
            what="a short sentence naming a rule",
        )


def test_the_counter_does_not_fire_on_a_charge_code_or_a_size():
    """A CHARGE CODE is the tenant's own word and MAY be shown.

    `BASE-E-COM` and `W-58` are what a clerk types into Plans & Rates; rule 32
    is about OUR ids — a rule number, a defect number, a screen id — not about
    the utility's own catalogue. A pattern that refused these would push the
    repair out of the sentence, which is the opposite of what rule 33 wants.
    """
    assert_clerk_copy(
        "BASE-E-COM has no price for W-58. Price it on the charge code.",
        what="a sentence naming the code and the size",
    )


# ════════════════════════════════════════════════════════════════════════════
# `gather._base_charge_for` — ONE REFUSAL, AND NO DATABASE IS NEEDED (from
# 2026-09-28: it had THREE while the plan and the rate schedule were still read)
# ════════════════════════════════════════════════════════════════════════════
def _refusal_of(*args, **kwargs) -> str:
    with pytest.raises(gather.GatherProblem) as raised:
        gather._base_charge_for(*args, **kwargs)
    return str(raised.value)


def test_no_base_charge_is_stated_anywhere():
    """⚠ **THE ONLY REFUSAL `_base_charge_for` STILL HAS, FROM 2026-09-28
    (`DEF-BIL-7170`).**

    Four cases stood here and are GONE because the refusals they measured are
    gone, not because their copy improved: *charge code vs plan*, *charge code
    vs plan and schedule*, *plan vs schedule with no charge code*, and the
    agreeing-fallback set. The PO retired both of the other two sources —
    *"we will never take default value from plan $8.0 - that is retired"* — so
    there is one input, and the only thing left to say is that nobody stated a
    base at all.

    ⚠ **AND THE REPAIR NO LONGER NAMES THE PLAN, WHICH IS WHY THAT ASSERTION
    IS INVERTED HERE.** It used to read *"Type it on the plan's services."*;
    under the ruling that sends a clerk to type a figure into the one column
    the product has stopped reading, so the bill would refuse again on the next
    run with nothing on screen to say why.
    """
    # ⚠ SUPERSEDED 2026-09-30: nobody stating a base no longer REFUSES — PO,
    # *"as a default you take 0 and complete the bill instead of refusing"*.
    # The clerk copy is now the `baseNotSet` warning's catalogue sentence
    # (contract §2: *"No base charge for {service}. Billed $0.00."*), and what
    # the backend owes it is a KEY and PARAMS with no prose in them.
    from apps.billing import bill_warnings

    assert gather._base_charge_for("electric", code_base=None) == Decimal("0")
    warning = bill_warnings.base_not_set("electric")
    assert warning["key"] == "billing.oneTime.warn.baseNotSet"
    assert set(warning["params"]) == {"service", "service_code"}
    assert "plan" not in " ".join(str(v) for v in warning["params"].values())


def test_the_agreeing_case_still_answers_a_figure_and_refuses_nothing():
    """The COPY changed and the arithmetic did not — this is what says so.

    `_base_charge_for` is on a money path (`DEF-154`: every bill charged
    `$0.00` when this function reached for the wrong column), so a copy lane
    proves the answers as well as the words.
    """
    assert gather._base_charge_for("water", code_base=Decimal("8.00")) == Decimal("8.00")
    # DEF-277 / PO 2026-08-19 — a STORED zero still bills $0.00 and refuses nothing.
    assert gather._base_charge_for("water", code_base=Decimal("0")) == Decimal("0")


# ════════════════════════════════════════════════════════════════════════════
# `rating.selectors.base_charge_from_charge_code` — FIVE REFUSALS, ON ROWS
# ════════════════════════════════════════════════════════════════════════════
def _service(code: str):
    """The PLATFORM catalogue row — `services` is not tenant-scoped (B2 r5 #1)."""
    return tenancy_models.Service.objects.get(code=code)


def _base_charge(env, *, code: str, classes=None, amount=None, sizes=None):
    """One `is_base` charge for water, with whatever shape the case needs."""
    with tenant_ctx(env.tenant):
        charge = models.Charge.objects.create(
            tenant=env.tenant,
            service=_service("water"),
            code=code,
            name=code,
            charge_type="recurring",
            amount_rule="flat",
            amount=amount,
            is_base=True,
            applies_to_customer_classes=classes or [],
        )
        for size_class, size_amount in (sizes or {}).items():
            models.ChargeCodeAmount.objects.create(
                tenant=env.tenant,
                charge=charge,
                size_class=size_class,
                amount=size_amount,
            )
    return charge


def _answer(env, **kwargs):
    with tenant_ctx(env.tenant):
        if "named_code" not in kwargs:
            # `DEF-RAT-9832` (PO 2026-10-06): only the code a schedule NAMES is
            # read, so each case names the one code it built — the sentences
            # under test are reached exactly as before. Two codes → none named.
            codes = list(
                models.Charge.objects.filter(is_base=True, service__code="water").values_list("code", flat=True)
            )
            kwargs["named_code"] = codes[0] if len(codes) == 1 else None
        return selectors.base_charge_from_charge_code("water", **kwargs)


def test_two_base_codes_both_apply(env):
    """⚠ AMENDED 2026-10-06 (`DEF-RAT-9832`). This asserted the pool's
    *"2 base charge codes for water."* — unreachable now: a schedule naming
    neither code takes neither, and the sentence is the not-named one."""
    _base_charge(env, code="BASE-W", amount=Decimal("8.00"))
    _base_charge(env, code="BASE-W-TWO", amount=Decimal("15.00"))
    answer = _answer(env, customer_class="residential")
    assert_clerk_copy(answer["refusal"], what="two base codes")
    assert answer["refusal_reason"] == selectors.BASE_NOT_NAMED


def test_the_account_s_customer_type_is_covered_by_no_charge(env):
    _base_charge(env, code="BASE-W-COM", classes=["commercial"], amount=Decimal("15.00"))
    answer = _answer(env, customer_class="residential")
    assert_clerk_copy(answer["refusal"], what="customer type not covered")
    assert answer["refusal_reason"] == "customer_class"
    assert "residential" in answer["refusal"]


def test_the_account_states_no_customer_type_at_all(env):
    _base_charge(env, code="BASE-W-COM", classes=["commercial"], amount=Decimal("15.00"))
    answer = _answer(env, customer_class=None)
    assert_clerk_copy(answer["refusal"], what="account has no customer type")
    assert answer["refusal_reason"] == "customer_class"
    # The repair is on the ACCOUNT, not on the charge — the two branches say
    # different things and that is why rule 33 did not collapse them into one.
    assert "account" in answer["refusal"]


def test_a_code_stating_both_a_flat_amount_and_a_size_table(env):
    _base_charge(
        env, code="BASE-W", amount=Decimal("8.00"), sizes={"W-58": Decimal("8.00")}
    )
    answer = _answer(env, customer_class="residential", size_class="W-58")
    assert_clerk_copy(answer["refusal"], what="flat amount and size table")
    assert "BASE-W" in answer["refusal"]


def test_a_size_the_code_does_not_price(env):
    """The sentence a clerk read on 30 of 74 open accounts on 2026-09-24."""
    _base_charge(env, code="BASE-W", sizes={"W-58": Decimal("8.00")})
    answer = _answer(env, customer_class="residential", size_class="W-2")
    assert_clerk_copy(answer["refusal"], what="unpriced size")
    assert "W-2" in answer["refusal"] and "BASE-W" in answer["refusal"]


def test_a_connection_whose_size_was_never_recorded(env):
    """⚠ **A DIFFERENT STATE FROM THE ONE ABOVE, AND IT SAYS SO NOW.**

    These two shared one 63-word sentence because it offered both repairs at
    once and could not tell which applied — and it printed the Python `None`
    to the clerk while doing it (*"states no amount for size None"*). Split,
    each is a fact and an instruction at six words a side.
    """
    _base_charge(env, code="BASE-W", sizes={"W-58": Decimal("8.00")})
    answer = _answer(env, customer_class="residential", size_class=None)
    assert_clerk_copy(answer["refusal"], what="size not recorded")
    assert "None" not in answer["refusal"]
    assert "size" in answer["refusal"]


def test_a_code_declared_the_base_that_states_no_amount(env):
    _base_charge(env, code="BASE-W", amount=None)
    answer = _answer(env, customer_class="residential")
    assert_clerk_copy(answer["refusal"], what="no amount at all")
    assert "BASE-W" in answer["refusal"]


def test_a_priced_size_still_answers_its_figure(env):
    """Again: the copy moved and the money did not."""
    _base_charge(env, code="BASE-W", sizes={"W-58": Decimal("8.00")})
    answer = _answer(env, customer_class="residential", size_class="W-58")
    assert answer["refusal"] is None
    assert Decimal(str(answer["amount"])) == Decimal("8.00")

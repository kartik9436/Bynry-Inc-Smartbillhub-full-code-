#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-4079 and DEF-MET-4081 (2026-09-05) — two defect rows filed
#           with severity `major`, which the register has not used since
#           2026-08-27, AFTER G46 had been taken green twice on the same day.
#           Seven rows on this branch, all the same word, all mapped major->high
#           by hand after the fact.
# Rules:    CLAUDE.md "Defect register" — the register is evidence, and a column
#           holding two vocabularies makes every count taken from it wrong
#           (DEF-1710/DEF-1711: "40 high open" was really 90).
#           12-governance/15-defect-register-truth.md §7 — the status column
#           holds nine values where six would do, and the recommended sequence
#           is "stop the tools emitting the losing spellings" WITHOUT rewriting
#           the rows that already carry them.
# Impacts:  10-scripts/file_defect.py (writes severity) ·
#           10-scripts/close_defect.py (writes status) ·
#           gates G30/G46 read these columns and keep their own read-side sets.
# ───────────────────────────────────────────────────────
"""The defect register's controlled vocabularies, in ONE place, in TWO halves.

WHY TWO HALVES AND NOT ONE SET
==============================
A gate and a writing tool are asking different questions about the same column,
and collapsing them into one set gets one of the two wrong every time:

* **A GATE READS 1,872 ROWS THAT ALREADY EXIST.** Thirty-seven of them carry a
  spelling the project has retired. Refusing those would make the gate red from
  birth, which is how a check earns a `# noqa` instead of a fix — G30 records
  exactly that lesson about its own first draft ("a gate that argues with the
  data it checks is a gate that gets switched off"). So the READ set is wide.

* **A TOOL WRITES ONE NEW ROW.** Nothing forces a new row to repeat a retired
  spelling, and every one that does adds to the 37. So the WRITE set is narrow.

Hence: `*_ACCEPTED_ON_READ` ⊇ `*_WRITABLE`. **Accept the old words on read,
refuse them on write.** That is the ratchet `12-governance/15-defect-register-
truth.md` §7 asks for in as many words, and it costs nobody a risky commit:

    "Do not rewrite 1,872 rows to enforce this. A mass rewrite of a file that
     ten lanes append to is precisely the operation this repo has lost work to
     more than once ... stop the tools emitting the losing spellings, let the 37
     affected rows be corrected as they are touched for other reasons, and drop
     the retired values from the gate's vocabulary only when the count reaches
     zero."

WHY A REFUSAL AND NEVER A SILENT CORRECTION
===========================================
`major` almost certainly means `high` — a lane mapped seven of them that way on
2026-09-05, reading each row and keeping the filer's intent. It is still not
this module's business to do it. G46 wrote the reason down when it was built and
it has not changed:

    "It does not guess a mapping and rewrite the row — `blocker` might mean
     `critical` and might mean something the filer could tell you and the script
     cannot. A gate that silently reassigns severities would destroy exactly the
     evidence the register exists for."

So a retired word is REFUSED, and the refusal NAMES the survivor. The lane
retypes four characters and the register keeps one vocabulary. What is not
guessed is not lost: the filer is still in the room at the moment of the refusal,
which is the whole reason for checking here rather than in a gate.

⚠ **THERE ARE THREE VOCABULARIES HERE AND THE THIRD DOES NOT HAVE TWO SETS.**
`category` was added on 2026-09-10 with 1,016 distinct strings already in the
column. A read SET cannot list 1,016 spellings, so its wide half is a COUNT that
G46 publishes on every run and a DATE that G46 ratchets from — same doctrine,
different mechanism, and the whole of it is written out at `# ── category ──`
below. **Read that block before assuming `CATEGORY_ACCEPTED_ON_READ` was
forgotten; its absence is the design.** (This paragraph exists because the
sentence above says `*_ACCEPTED_ON_READ ⊇ *_WRITABLE` as though it held for every
column, and a pointer that goes stale the day a third case arrives is the thing
CLAUDE.md's B14 rule-count line has now been wrong about five times.)

⚠ **AND ONLY THE TWO WORDS SOMEBODY ACTUALLY RULED ON CARRY A MAPPING.**
`blocker`, `trivial` and `cosmetic` were in the register too (12, 2 and 1 rows
on 2026-08-27) and NOBODY has ever ruled what they map to. They are refused with
the allowed list and no suggestion, because inventing "blocker means critical"
here would be this file doing the exact thing the paragraph above forbids.
"""
from __future__ import annotations

# ── severity ───────────────────────────────────────────────────────────────
#: The four the project reasons in. G46 enforces these on every row of the
#: register, so for severity the read set and the write set are the SAME — the
#: 271 second-vocabulary rows were normalised in the commit that registered G46,
#: and none has been lawful since.
SEVERITY_WRITABLE: frozenset[str] = frozenset({"critical", "high", "medium", "low"})
SEVERITY_ACCEPTED_ON_READ: frozenset[str] = SEVERITY_WRITABLE

#: Retired spellings WITH a ruled survivor. Both entries come from the same act:
#: on 2026-09-05 a lane mapped seven rows major->high and minor->low, reading
#: each one and keeping the filer's intent. Following that mapping rather than
#: inventing one is the point — see the module docstring.
SEVERITY_RETIRED: dict[str, str] = {"major": "high", "minor": "low"}

#: Retired spellings with NO ruled survivor. Named separately so the refusal can
#: say "this was a severity once and nobody has said what it becomes" instead of
#: quietly implying the value is a typo.
SEVERITY_RETIRED_UNMAPPED: frozenset[str] = frozenset({"blocker", "trivial", "cosmetic"})

# ── status ─────────────────────────────────────────────────────────────────
#: 12-governance/15-defect-register-truth.md §7, verbatim: "The recommended
#: vocabulary is six values: open · partially-fixed · fixed · wontfix ·
#: duplicate · invalid".
STATUS_WRITABLE: frozenset[str] = frozenset(
    {"open", "partially-fixed", "fixed", "wontfix", "duplicate", "invalid"}
)

#: The nine G30 and G46 accept, so the 37 rows carrying a retired spelling stay
#: lawful and no gate goes red over history. This set MUST stay a superset of
#: the writable one; `10-scripts/tests/test_register_vocabulary.py` asserts that
#: against the gates' own constants so the three copies cannot drift apart.
STATUS_ACCEPTED_ON_READ: frozenset[str] = STATUS_WRITABLE | frozenset(
    {"closed", "fixed-in-part", "reported"}
)

#: What a retired status should be written as instead, and WHY — the audit's
#: reasoning, one sentence each, because a refusal that only lists allowed values
#: makes the lane guess which one it meant.
STATUS_RETIRED: dict[str, str] = {
    "fixed-in-part": (
        "write `partially-fixed` — the same state under two spellings, and it is "
        "used nearly twice as often (22 rows against 12)"
    ),
    "reported": (
        "write `open` — the same state under two spellings, and `reported` has "
        "two rows and no distinct meaning"
    ),
    "closed": (
        "write `fixed` if the fault is gone, or `wontfix` / `duplicate` / "
        "`invalid` if the row was retired for some other reason — those three "
        "say precisely what `closed` leaves the reader to guess"
    ),
}


def _listed(values: frozenset[str]) -> str:
    return " · ".join(sorted(values))


def explain_severity(value: str) -> str | None:
    """None if `value` may be written; otherwise the refusal, in full.

    The refusal says the ALLOWED values, not merely that this one was wrong —
    a lane that is told "invalid severity" has to go and find the list, and a
    lane in a hurry writes the word that felt right last time, which is how the
    second vocabulary arrived one row at a time in the first place.
    """
    word = (value or "").strip().lower()
    if word in SEVERITY_WRITABLE:
        return None
    allowed = f"allowed: {_listed(SEVERITY_WRITABLE)}"
    if word in SEVERITY_RETIRED:
        survivor = SEVERITY_RETIRED[word]
        return (
            f"severity {value!r} is the register's OLD vocabulary. It was mapped "
            f"{word}->{survivor} on 2026-09-05 across seven rows, keeping each filer's "
            f"intent — so write {survivor!r} if that is what you mean. {allowed}. "
            f"(G46 refuses {word!r} once the row is on the branch; this refusal is the "
            f"same rule arriving while you can still say what you meant.)"
        )
    if word in SEVERITY_RETIRED_UNMAPPED:
        return (
            f"severity {value!r} was a severity in this register once and NOBODY has "
            f"ruled what it becomes — {_listed(SEVERITY_RETIRED_UNMAPPED)} were 12, 2 and "
            f"1 rows on 2026-08-27 and were normalised by hand. Choose from the four "
            f"yourself rather than letting a script guess. {allowed}."
        )
    if not word:
        return f"severity is empty. {allowed}."
    return f"severity {value!r} is not a severity this register uses. {allowed}."


def explain_status(value: str) -> str | None:
    """None if `value` may be written; otherwise the refusal, in full."""
    word = (value or "").strip().lower()
    if word in STATUS_WRITABLE:
        return None
    allowed = f"allowed: {_listed(STATUS_WRITABLE)}"
    if word in STATUS_RETIRED:
        return (
            f"status {value!r} is still ACCEPTED on rows that already carry it — "
            f"37 do — but it is not written any more: {STATUS_RETIRED[word]}. {allowed}. "
            f"(12-governance/15-defect-register-truth.md §7.)"
        )
    if not word:
        return f"status is empty. {allowed}."
    return f"status {value!r} is not a status this register uses. {allowed}."


# ── category ───────────────────────────────────────────────────────────────
# PO ruling 2026-09-10, verbatim: "we cannot manage what we cannot count."
#
# WHY THIS COLUMN NEEDED A VOCABULARY AND THE OTHER TWO DID NOT
# =============================================================
# `severity` arrived with nine spellings and was normalised in an afternoon.
# `category` was never given a vocabulary at all, and free text in a column
# nobody closes does not drift — it EXPLODES. Measured 2026-09-10 against the
# register at the branch tip:
#
#     2,395 rows · 1,016 DISTINCT category strings
#     last nine days alone: 1,143 rows · 538 distinct
#     580 of those rows sit in 485 categories used three times or fewer
#
# A column with 1,016 values is not a column, it is a second title field. Two
# independent attempts to bucket the SAME 1,140 rows disagreed by twenty points
# on the largest bucket, because both were guessing at free text — which is the
# measured form of the PO's sentence.
#
# WHY TWELVE, AND WHERE THEY CAME FROM
# ====================================
# They were derived FROM THE 1,016 STRINGS, not from anybody's head: the whole
# register was bucketed by `CATEGORY_HINT_RULES` below and the residue read by
# hand until every group of more than ~15 rows had a home. The twelve are the
# groups that survived, and each is spelled in a word the register already uses.
# The measured fit, over all 2,395 rows:
#
#     92% of rows land on one of the twelve from the CATEGORY STRING ALONE
#     99.7% once the ~30 opaque strings (`process`, `code`, `defect`,
#           `frontend`, `unknown` …) are read against the row's own TITLE
#     8 rows could not be placed at all
#
# ⚠ ONE FINDING IS WORTH MORE THAN THE LIST, AND IT IS WHY THE PO ASKED.
# The prior held that "the screen does not match its design" was ~32% of recent
# defects. It cannot be: only 23.9% of the last nine days' rows name a
# `07-frontend` or `05-prototype` surface AT ALL, so no screen-fidelity bucket
# can reach 32% however the free text is read. Measured with the twelve, the
# last nine days are 25.9% `check-that-does-not-check`, 17.4% `stale-record`,
# 16.9% `wrong-logic`, 10.9% `design-divergence`, 7.4% `copy-i18n`. **The 20-point
# disagreement was never about judgment — it was about counting free text**, and
# it is exactly what a fixed list stops.
#
# WHY THE READ SIDE IS OPEN AND NOT A WIDE SET
# ============================================
# `severity` and `status` each retired a handful of spellings, so the read set
# could list them. **1,016 cannot be listed**, and a gate that refused them would
# be red from birth over history nobody can rewrite — the thing this module's own
# docstring says gets a gate switched off. So for `category` the two halves are
# not two SETS, they are a set and a COUNT: anything is lawful on read, and G46
# publishes how many rows are outside the vocabulary every time it runs.
#
# ⚠ THE COUNT IS THE POINT, NOT A COURTESY. Hard-won law 7: "a declared blind
# spot with no NUMBER attached is indistinguishable from an empty one" — G32
# reported 0 unresolved over 21 live refusals it could not see. A gate that said
# only "category is not checked on read" would be that gate. It says how many.
#
# NOTHING IS REWRITTEN. Same ratchet as `status`: stop the tools emitting the
# losing spellings, let a row be recategorised when it is touched for some other
# reason, and narrow the read side only when the count reaches zero. A whole-file
# rewrite of a 2,395-row register that ten lanes append to is the exact damage
# hard-won law 11 exists to prevent.

#: The twelve. One line each, in the register's own words — a lane picking a
#: category reads THIS, so a definition that needs a second document is a
#: definition that will be guessed at instead.
CATEGORY_MEANING: dict[str, str] = {
    "design-divergence": (
        "what is on the screen does not match r10 or B14 — layout, styling, an "
        "affordance, a raw token or a database id where a person should see a name"
    ),
    "check-that-does-not-check": (
        "a gate, test, guard or fixture that cannot fail, cannot pass, looks at "
        "the wrong thing, reports zero over a scope it excludes, or was red and unread"
    ),
    "stale-record": (
        "the written record is wrong or overtaken — a doc, docstring, comment, "
        "spec, register body, citation, snapshot or version that no longer states the truth"
    ),
    "built-not-wired": (
        "the code exists and nothing reaches it, or a refusal outlived the screen "
        "it was holding — hard-won law 2, in both directions"
    ),
    "wrong-logic": (
        "the code runs and produces the wrong answer, the wrong shape or the "
        "wrong default — anything but a money figure, which is `money-math`"
    ),
    "not-built": (
        "something signed, ruled or specified was never built at all — no code, "
        "no screen, no seam; the absence is the defect"
    ),
    "money-math": (
        "a money or rate figure is wrong, wrongly rounded, wrongly displayed or "
        "posted wrongly — hard rule 2, B4/B5 and the ledger"
    ),
    "data-migration": (
        "the data at rest is wrong — schema, migration, seed or fixture content, "
        "a lost row, a constraint that does not hold"
    ),
    "copy-i18n": (
        "the words are wrong — wording, a missing catalogue key, an untranslated "
        "string, a term that means two things in one product"
    ),
    "access-tenancy": (
        "tenant scoping, RLS, a cross-tenant reach, a permission or an "
        "authentication check — hard rule 1"
    ),
    "performance": (
        "the work is done correctly and too slowly or too expensively — a "
        "timeout, a quadratic loop, an unbounded payload, a fixed cost nobody measured"
    ),
    "lane-collision": (
        "one lane undid, published or duplicated another's work — a shared file, "
        "a shared index, a shared register or an id taken twice; hard-won law 11"
    ),
}

#: The fixed list itself. A new row must carry one of these.
CATEGORY_WRITABLE: frozenset[str] = frozenset(CATEGORY_MEANING)

#: ⚠ THERE IS NO `CATEGORY_ACCEPTED_ON_READ` SET, AND ITS ABSENCE IS DELIBERATE.
#: 1,016 legacy spellings cannot be enumerated, so the read side is OPEN and the
#: blind spot is published as a number instead. This flag exists so a reader
#: grepping for the third read-set finds this sentence rather than concluding one
#: was forgotten (hard-won law 1: a comment claiming a guarantee is not the
#: guarantee — this one claims the opposite, on purpose).
CATEGORY_READ_IS_OPEN: bool = True

#: What the census counted when the vocabulary was written, so a later reader can
#: tell a ratchet that is working from one that is standing still.
CATEGORY_LEGACY_BASELINE: dict[str, object] = {
    "rows": 2395,
    "distinct_categories": 1016,
    # 99 rows already spell one of the twelve by accident of good taste —
    # `built-not-wired` 68, `performance` 10, `not-built` 8,
    # `check-that-does-not-check` 8, `design-divergence` 2, `stale-record` 2,
    # `wrong-logic` 1 — which is itself an argument that these are the words the
    # register was reaching for.
    "rows_outside_vocabulary": 2296,
    "measured_on": "2026-09-10",
}

#: The mapping that DERIVED the twelve, kept so the refusal can point a lane at
#: the survivor of the word it typed. Ordered — the first rule that matches wins,
#: and the order encodes the only judgments in this file: money before generic
#: wrongness, tenancy before generic wrongness, a broken CHECK before the thing
#: it was checking, and the WORDS on a screen before the screen's layout.
#:
#: ⚠ IT IS A HINT AT THE KEYBOARD AND NEVER A REWRITE. No row is ever
#: recategorised by this table; the filer is in the room and overrules it. That
#: is the same line `SEVERITY_RETIRED` draws — a script that reassigns a row
#: destroys the evidence the register exists for.
CATEGORY_HINT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("access-tenancy", ("tenant", "rls", "authz", "permission", "security",
                        "role-checked", "isolation", "clearance")),
    ("money-math", ("money", "arithmetic", "rounding", "precision", "undercharge",
                    "tariff", "proration", "decimal", "currency", "unissuable-bill",
                    "posted", "figure", "unruled money")),
    ("performance", ("performance", "timeout", "quadratic", "slow", "wall-clock",
                     "unbounded-payload", "orm-construction-cost", "scale-on-screen")),
    ("copy-i18n", ("copy", "i18n", "translat", "catalogue", "wording", "label",
                   "microcopy", "voice", "tone", "locale", "untranslated",
                   "mistranslation", "signpost", "description-budget",
                   "clerk-facing", "prose")),
    ("check-that-does-not-check", ("check", "gate", "guard", "test", "fixture",
                                   "assert", "harness", "proof", "false-positive",
                                   "false positive", "green", "red", "ratchet",
                                   "lint", "xfail", "flaky", "self-blind",
                                   "false-success", "unwatched", "coverage",
                                   "blind", "instrument", "not-idempotent",
                                   "masked-by-earlier-failure",
                                   "structurally-incapable", "measurement-grain")),
    ("lane-collision", ("lane", "shared-tree", "shared tree", "shared-file",
                        "shared-register", "revert", "clobber", "collision",
                        "duplicate-id", "id-collision", "commit", "merge",
                        "cross-lane", "publication", "wrong-tree-write",
                        "unreserved-id", "lost-work", "shared-mutable-state",
                        "stale-tree", "key-collision", "name-shadowing")),
    ("data-migration", ("migration", "seed", "schema", "data", "column", "fk",
                        "demo", "sample", "encoding", "truncation", "partition",
                        "constraint", "state-loss", "storage",
                        "counter-not-advanced", "silent-partial-write",
                        "dead-columns", "unassigned-field", "missing-crud")),
    ("stale-record", ("stale", "doc", "spec", "record", "claim", "comment",
                      "citation", "cite", "snapshot", "drift", "rot", "changelog",
                      "version", "pointer", "reference", "supersede", "superseded",
                      "contradiction", "honesty", "unverified", "false-claim",
                      "false-guarantee", "unproven", "attribution", "packet",
                      "vocabulary", "register", "status", "absence", "reporting",
                      "summary", "declaration", "pin", "ruling-not-in-code",
                      "ruling not propagated", "closed-question", "artifact",
                      "marker", "invisible-to-tooling", "false-alarm",
                      "not-reproduced", "unreproduced", "mis-diagnosed",
                      "stated-boundary", "rule-conflict", "rule-collision",
                      "rule-contradiction", "rule-vs-code", "rule-vs-expectation",
                      "duplicate-source", "duplicated-rule", "law-14",
                      "business-rule", "rule-ruling")),
    ("built-not-wired", ("wir", "dead-", "dead ", "no-caller", "unreachable",
                         "unrouted", "orphan", "door", "control", "registration",
                         "route", "unexercised", "never-executed", "no-consumer",
                         "unused", "entry-point", "unclaimed", "unowned", "no-read",
                         "unserved", "served-but-unwritable", "seam-not-published",
                         "no-terminal-path", "unsent-required-field",
                         "logged-not-shown", "served-and-unrendered",
                         "half-rendered", "unlinked", "no-reverse-check")),
    ("not-built", ("missing", "not-built", "unbuilt", "gap", "not-implemented",
                   "unimplemented", "not built", "half-built", "half-unbuilt",
                   "not-enforced", "unproduced", "requirement-not-built",
                   "ruled-not-built", "ruled-and-unbuilt", "deferred", "debt",
                   "backlog", "incomplete", "story", "half-implemented",
                   "one-sided-rule", "rule-half", "unconfigurable", "undercount",
                   "unusable-template", "boundary", "duplicate-implementation",
                   "duplication", "observability", "ruling-not-implemented",
                   "ruling-half-applied", "missing-half")),
    ("design-divergence", ("ui", "layout", "design", "prototype", "screen",
                           "style", "css", "render", "display", "b14",
                           "convention", "conformance", "fidelity", "divergence",
                           "r10", "responsive", "accessib", "usability", "ux",
                           "affordance", "presentation", "visual", "clipped",
                           "confusing", "raw-token", "raw-value", "raw-placeholder",
                           "internal-reference", "internal-id",
                           "internal-content-leak", "internal-reasoning",
                           "leaked-internals", "machine-token", "database-id",
                           "unit-presentation", "two-answers-one-screen",
                           "un-ported-markup", "phantom-token", "unlabelled-unit",
                           "asks-for-an-identifier")),
    # Anything a rule above did not claim, and that is not one of the ~30 opaque
    # strings, is the code getting the wrong answer. Named as the fallthrough
    # rather than left implicit so nobody reads the empty tuple as an oversight.
    ("wrong-logic", ()),
)

#: Category strings that say NOTHING about the failure mode — 187 rows carry one.
#: `suggest_category` returns None for these rather than sending a lane to
#: `wrong-logic` by the fallthrough above, because "process" is not a wrong
#: answer, it is no answer, and a confident wrong hint is worse than silence.
CATEGORY_OPAQUE: frozenset[str] = frozenset({
    "process", "code", "defect", "frontend", "backend", "unknown", "process/tooling",
    "tooling", "tooling-process", "process-record", "process-miss",
    "process-violation", "consistency", "environment", "configuration",
    "validation", "cascade", "worker-actor", "",
})


def suggest_category(value: str) -> str | None:
    """Which of the twelve the word `value` most likely means, or None.

    Used ONLY to make a refusal helpful. It never rewrites a row and never
    decides anything: the lane that typed the word is standing there and knows
    what it meant, which is the whole reason this check lives in the writer
    rather than in a gate.
    """
    word = (value or "").strip().lower()
    if word in CATEGORY_WRITABLE:
        return word
    if word in CATEGORY_OPAQUE:
        return None
    for bucket, keys in CATEGORY_HINT_RULES:
        if not keys:
            return bucket
        if any(k in word for k in keys):
            return bucket
    return None


def explain_category(value: str) -> str | None:
    """None if `value` may be written; otherwise the refusal, in full.

    Same shape as `explain_severity` / `explain_status`, and the same reason:
    a lane told only "invalid category" goes and invents the 1,017th spelling.
    This lists all twelve WITH their meanings, because a bare list of twelve
    hyphenated words is a list somebody guesses from.
    """
    word = (value or "").strip().lower()
    if word in CATEGORY_WRITABLE:
        return None

    listing = "; ".join(f"{name} = {CATEGORY_MEANING[name]}" for name in sorted(CATEGORY_WRITABLE))
    allowed = f"the twelve are — {listing}"

    if not word:
        return f"category is empty. {allowed}."

    guess = suggest_category(word)
    if guess:
        head = (
            f"category {value!r} is free text. The register holds 1,016 distinct "
            f"category strings and can be counted by none of them, so from the PO "
            f"ruling of 2026-09-10 — \"we cannot manage what we cannot count\" — a "
            f"new row carries one of twelve. Yours reads like {guess!r}; write that "
            f"if it is what you mean, and something else off the list if it is not."
        )
    else:
        head = (
            f"category {value!r} says nothing about HOW this defect got in — it "
            f"names a place or a process, not a failure mode, and 187 rows already "
            f"do. Pick the mode from the twelve; the place belongs in `surface`."
        )
    return (
        f"{head} {allowed}. (Rows already carrying a legacy category stay lawful "
        f"and are NOT rewritten — G46 counts them instead.)"
    )

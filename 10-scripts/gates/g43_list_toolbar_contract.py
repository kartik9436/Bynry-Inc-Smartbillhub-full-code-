#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:   CR-041 task 6 (PO 2026-08-27, twice, escalating) — *"tool bar -
#           descrption, search, filter, column seelctor, pagination, export - -
#           we need to ensure it behavios in a simialr way everywhere ... you
#           ahve to do - where else is this class used the same way. and create
#           a task list and fix all those not just report it"*
# Rules:    B14 rule 19 (a search placeholder names what the box matches) ·
#           B14 rule 18 (a description caps at 80% through `--desc-measure`) ·
#           BR-SHL-010 (the capability row IS the config)
# Defects:  DEF-510 (every list said "Search this list"; the field to fix it
#           landed and no screen was wired for five days) · DEF-900 (`max-w-prose`
#           is a real Tailwind utility and the WRONG cap) · DEF-950 (a prompt
#           must be TRUE — the reads box could not search the address r10 drew) ·
#           DEF-1006 (the `max-w-prose` sweep found 12 files where CR-041 said 4)
# ───────────────────────────────────────────────────────
"""G43 — the list toolbar's two written rules, held as ratchets.

WHY THIS GATE EXISTS
--------------------
**Every finding in CR-041 is a thing that was fixed once and recurred somewhere
else, because nothing asked the general question.**

* `.met-filters` was misused on three screens. It was diagnosed on 2026-08-26
  and again on 2026-08-27, each time with the conclusion written into the file,
  and **neither diagnosis asked where else**. The third site had never been
  looked at. The grep takes four seconds and nothing in this repo runs it.
* `searchPlaceholder` landed on `TableConfig` on 2026-08-22 to close DEF-510 —
  *"every list in the product says 'Search this list'"* — and **no screen was
  wired to it for five days**. Three of the keys were then minted in all eleven
  catalogues by a locale lane and still nothing rendered them.
* `max-w-prose` was identified as the wrong description cap by DEF-900, swept,
  and the sweep found four files where there are twelve (DEF-1006).

A comment does not sweep. A grep run by hand at the moment of a fix measures
that moment and decays from the next commit onward. **A ratchet asks on every
commit**, which is the only mechanism in this repo that has ever held a
whole-tree property still — G31's declared-class ceiling and G38's untracked
notes are the two precedents this file is built on.

WHAT IT CHECKS — TWO CLAUSES, DELIBERATELY DIFFERENT SHAPES
-----------------------------------------------------------
**(a) A list that declares `searchFields` declares `searchPlaceholder`. HARD,
     BASELINE ZERO.** This is an invariant, not a debt: all 23 searchable lists
     carry a prompt as of CR-041 task 2, so the first list that does not is a
     NEW violation and there is no legacy to grandfather. The 24th searchable
     list must bring its own sentence.

**(c) A DIMENSION CONTROL IN THE DOWNLOAD SLOT. HARD, BASELINE ZERO.**
     `DataTable` renders `downloadSlot` after its spacer, so for a long time it
     was the only right-aligned place a screen could put anything — and three
     screens put a `SegmentedFilter` there. **All three wrote the same sentence
     to explain it**: *"it rides in `downloadSlot` because that is the only slot
     the shared toolbar renders AFTER its spacer, i.e. the only one that is
     right-aligned."* Premises, then Units, then Reads. Nobody decided it; each
     lane found the same hole and stepped in it, and the row grew a control at a
     time until the Reads toolbar held eight controls plus two four-cell chip
     groups — ~1,360px against the ~1,150px a 1,440px laptop leaves — and
     wrapped, stranding Download CSV and the ▦ on a second line where the ▦'s
     panel opened off the left edge of the viewport (DEF-1085).

     `dimensionsSlot` is the slot those three comments were asking for, and this
     clause is what stops the fourth lane reaching for the right-aligned one
     again. Baseline zero: all three moved in DEF-1085's own commit, so there is
     no legacy to grandfather.

     ⚠ **THIS IS THE ONLY CLAUSE HERE THAT IS ABOUT CAPACITY, AND CAPACITY IS
     WHAT NOTHING OWNED.** DEF-896 asked whether the toolbar used the right
     CONTAINER; CR-041 asked whether the search box named its FIELDS; clause (a)
     asks whether a prompt EXISTS. None of them asks how much one row may hold.
     A jsdom render cannot see a wrapped row and no gate in this repo reads
     rendered output (hard-won law 6), so the width itself is unmeasurable here
     — but WHICH CONTROLS ARE IN WHICH SLOT is a source-level fact, and it is
     the fact the capacity decision actually rests on.

**(b) `max-w-prose` on a description. RATCHETED at the count that survived
     CR-041 task 5.** This one CANNOT be an invariant today: 50 occurrences
     remain across five files, 41 of them in the service-request family and 7 in
     a file another lane held. Failing on all of them would make this gate red
     from birth, which is how a check earns a `# noqa` instead of a fix (G31's
     own lesson, in its own words). The count may FALL and may never RISE, and a
     fall that is not banked in the baseline is also a failure — a ratchet that
     never tightens is a number nobody reads (DEF-490, thirty-one commits deep).

WHAT IT DELIBERATELY DOES NOT CHECK
-----------------------------------
**Whether a prompt is TRUE.** DEF-950's whole point is that r10 drew
`Meter #, address…` over a query that filters the meter number and nothing else.
No source-reading check can compare an English sentence to a Django `Q()`
expression, and **a gate that pretended to would be worse than none** (DEF-182:
a check whose output cannot distinguish pass from fail is worse than no check,
because it is trusted). Truth is held by the r11 discipline instead — read the
predicate, then write the copy, in that order and in one commit — and by the
gaps CR-041 filed rather than papered over (DEF-1001, DEF-1002, DEF-1003).

**Whether the placeholder KEY resolves to a sentence.** `G18` and `G27` already
own that in both directions, they do it better, and two checks over one fact
disagree the first time somebody edits either (G42's own reason for not
duplicating `_assert_registry_sane`).

COMMENTS ARE STRIPPED, AND THAT IS NOT FUSSINESS
------------------------------------------------
Six files now carry a comment explaining why `max-w-prose` is the wrong cap, and
two carry one explaining why a particular element keeps it. **Prose ABOUT the
rule must never satisfy or trip the rule** — G31 was tripped from a comment
twice and G37 carries the same guard. ⚠ LINE COMMENTS ARE STRIPPED FIRST
(DEF-741): a `//` line spelling a path with a star in it contains `/*`, so
stripping BLOCK first opens a comment that closes at the next `*/` anywhere
below and blanks every line between — 3,620 bytes across eight files, measured.

PROVED RED, THREE TIMES (hard-won law 7), each in a throwaway `git worktree` so
the shared tree was never mutated (r11 2d). The verbatim failures are in this
file's `# RED PROOF` blocks below, beside the clause each belongs to.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "07-frontend" / "src"

# ── CLAUSE (a) · B14 rule 19 — an invariant, baseline ZERO ─────────────────
#
# 23 of 23 searchable lists carried a prompt when this gate was written
# (CR-041 task 2; it was 7 of 23 that morning). There is no legacy set to
# grandfather, so this number is not a debt register — it is the rule.
#
# ⚠ DO NOT RAISE IT. A list whose prompt is genuinely "Search this list" does
# not exist: r10 draws that sentence on exactly one toolbar and B14 rule 19
# outranks it (see `SettingsReferenceData.tsx` for the stamped divergence and
# the rule-20 amendment that set the precedent).
UNPROMPTED_BASELINE = 0

# ── CLAUSE (b) · B14 rule 18 — a ratchet over a real backlog ───────────────
#
# 50 after CR-041 task 5 swept 15 of 65 (DEF-1006). What remains:
#   17  features/customers/ServiceRequestCapturePage.tsx
#   19  features/customers/ServiceRequestDetailPage.tsx
#    7  features/customers/moveShared.tsx      (another lane's file that session)
#    3  features/customers/ServiceRequestDocumentSettingsPage.tsx
#    2  features/customers/serviceRequestShared.tsx
#    1  features/customers/UnitPricingPanel.tsx    ← a KEPT one, see below
#    1  features/customers/parkedDrafts.tsx        ← a KEPT one, see below
#
# ⚠ TWO OF THE FIFTY ARE CORRECT AND ARE COUNTED ANYWAY, ON PURPOSE.
# `UnitPricingPanel.ROW_VALUE` and `parkedDrafts`' park note are VALUES, not
# descriptions — rule 18's own amendment exempts that shape — and each says so
# in its own file. They are not allowlisted here because an allowlist of
# individual elements is a second register that drifts from the first: the
# floor this number can honestly reach is 2, and the lane that reaches it
# lowers the baseline to 2 and writes that sentence here. Naming them in code
# would let a later edit turn a real violation into an exempt one silently.
#
# ⚠ LOWER THIS WHEN IT FALLS, IN THE SAME COMMIT THAT EARNS IT.
#
# ⚠ 50 → 31 on 2026-09-25, TIGHTENED (never widened), on the gate's own
# instruction: *"DOWN from 50 — lower `PROSE_CAP_BASELINE` to 31 in this file
# to bank the gain."* NONE of the nineteen is this lane's — every one was
# already earned at the branch tip and nobody lowered the number, which is the
# same slack the 65 → 58 note below records. Measured at the tip, the 31 that
# remain are:
#   11  features/customers/ServiceRequestCapturePage.tsx
#    7  features/customers/moveShared.tsx
#    4  features/customers/ServiceRequestDetailPage.tsx
#    3  features/customers/ServiceRequestDocumentSettingsPage.tsx
#    3  features/customers/serviceRequestShared.tsx
#    1  features/customers/RequestFeeHandoverModal.tsx
#    1  features/customers/UnitPricingPanel.tsx        ← a KEPT one, see above
#    1  features/customers/parkedDrafts.tsx            ← a KEPT one, see above
# `UnitPricingPanel.tsx` and `parkedDrafts.tsx` are still the two that are
# CORRECT and counted anyway, so the floor this number can honestly reach is
# still 2 and the paragraph above still holds.
#
# ⚠⚠ **THIS RATCHET FAILS ON AN IMPROVEMENT, AND A GOOD DAY LOOKS EXACTLY LIKE
# A BAD ONE.** Clause (b) is RED both when the count RISES and when it FALLS —
# the fall is the gate asking to be tightened, not a defect. **READ THE DETAIL
# LINE BEFORE TOUCHING THIS NUMBER.** It says `DOWN from N` on a fall and
# `N MORE than the baseline` on a rise, and the ONLY lawful response to a fall
# is to LOWER this integer to the measured count. **Never raise it to make the
# red go away**: that re-admits every `max-w-prose` the fall just removed —
# `65ch` where B14 rule 18 says 80% — and the next reader inherits a ratchet
# that has stopped ratcheting. Clauses (a) and (c) are the opposite shape:
# they are INVARIANTS at zero and must never move in either direction.
# 2026-10-24 · 29 -> 24: pre-release cleanup lane — measured 24 live
# `max-w-prose` on the branch tip; ratcheted down only, to bank the fall.
PROSE_CAP_BASELINE = 24
# ⚠ **LOWERED 31 → 29 ON 2026-09-30 (gate triage T6) — earned at the tip, held
# by nobody.** Clause (b) read `DOWN from 31` from 5e18b70a7 (2026-09-29, New
# Request in four steps, 2.399.0) onward. The number is the measurement.

#: `max-w-prose` as a WHOLE class token. It is REAL Tailwind and that is the
#: trap: it compiles, it renders, and it is `65ch` where rule 18 says 80%.
#:
#: ⚠ **`\b` IS THE WRONG BOUNDARY HERE AND THE SELF-TEST CAUGHT IT.** The first
#: draft was `\bmax-w-prose\b`, and `-` is a NON-word character, so `\b` matches
#: happily after the `e` of `prose` — `max-w-prose-ish` counted as a violation.
#: A class name is delimited by neither word chars nor hyphens, so that is what
#: the lookarounds say. Left recorded rather than quietly corrected: the
#: self-test bit on the gate's own author, which is the only reason it is right.
PROSE_CAP = re.compile(r"(?<![\w-])max-w-prose(?![\w-])")

# ── CLAUSE (c) · toolbar capacity — an invariant, baseline ZERO ────────────
#
# 0 after DEF-1085 swept Premises, Units and Reads into `dimensionsSlot`.
#
# ⚠ DO NOT RAISE IT. A screen that wants a dimension control right-aligned has
# `dimensionsSlot`, which is the DESIGNED second row. Raising this number would
# be re-opening DEF-1085 by arithmetic.
DIMENSION_IN_DOWNLOAD_BASELINE = 0

#: The JSX prop that opens the download slot, at a prop position (start of line
#: + whitespace), so a mention inside a string or a comment cannot open one.
DOWNLOAD_SLOT_OPEN = re.compile(r"^\s*downloadSlot=\{", re.M)

#: A dimension control. `SegmentedFilter` is the only one today; the set is
#: named rather than pattern-matched, exactly as `NOT_A_LIST_SCREEN` is, so a
#: second one is a deliberate edit here rather than a silent widening.
DIMENSION_CONTROLS = ("SegmentedFilter",)

#: A `TableConfig` object literal declares these as object KEYS. Anchored to a
#: line start + whitespace so a mention inside a string or a nested object of
#: another shape cannot answer for one.
DECLARES_SEARCH_FIELDS = re.compile(r"^\s*searchFields\s*:", re.M)
DECLARES_PLACEHOLDER = re.compile(r"^\s*searchPlaceholder\s*:", re.M)

#: `tableTypes.ts` DEFINES both fields and `DataTable.tsx` READS them; neither
#: is a list screen. Named rather than pattern-matched, exactly as G37
#: allowlists the shell's icon family by name (DEF-349's shape).
NOT_A_LIST_SCREEN = {
    "components/tableTypes.ts",  # the interface both fields are declared ON
    "components/DataTable.tsx",  # the consumer: `config.searchPlaceholder ?? …`
}


def _strip_comments(text: str) -> str:
    """Blank out comments, preserving offsets, LINE COMMENTS FIRST (DEF-741)."""
    text = re.sub(r"//[^\n]*", lambda m: " " * len(m.group(0)), text)
    return re.sub(r"/\*.*?\*/", lambda m: re.sub(r"\S", " ", m.group(0)), text, flags=re.S)


def _sources() -> list[tuple[str, str]]:
    """Every non-test source under `src/`, comments already blanked."""
    out: list[tuple[str, str]] = []
    for path in sorted(SRC.rglob("*.ts")) + sorted(SRC.rglob("*.tsx")):
        rel = str(path.relative_to(SRC))
        if ".test." in path.name or rel.startswith("i18n/"):
            continue
        out.append((rel, _strip_comments(path.read_text("utf-8", errors="replace"))))
    return out


def unprompted_lists(sources: list[tuple[str, str]]) -> list[str]:
    """Files declaring MORE `searchFields` than `searchPlaceholder`.

    ⚠ COUNTED PER FILE, NOT PER FILE-HAS-ONE, because two screens declare TWO
    tables in one file — `SettingsRoutesCyclesTab` (routes + cycles) and
    `PaymentsPage`. A `key in file` check would go green on a file whose second
    table has no prompt, which is the DEF-337/G37 lesson: check the thing that
    carries the guarantee, not a string that happens to appear in the file.
    """
    offenders: list[str] = []
    for rel, text in sources:
        if rel in NOT_A_LIST_SCREEN:
            continue
        fields = len(DECLARES_SEARCH_FIELDS.findall(text))
        prompts = len(DECLARES_PLACEHOLDER.findall(text))
        if fields > prompts:
            offenders.append(f"{rel} ({fields} searchFields, {prompts} searchPlaceholder)")
    return offenders


def _slot_body(text: str, open_at: int) -> str:
    """The source between a `downloadSlot={` and its MATCHING `}`.

    Brace-counted rather than regex'd, because the slot's body is JSX and holds
    braces of its own on every line. Comments are already blanked by
    `_strip_comments`, so a `}` inside one cannot close the span.

    ⚠ A brace inside a STRING LITERAL would still miscount, and that is
    accepted rather than hidden: the failure mode is a body that ends EARLY,
    which can only make this clause miss a violation, never invent one. A check
    that over-reports is the one that gets a `# noqa` (G31's lesson); a check
    that under-reports on a shape nothing in `src/` has today is a smaller debt,
    and the self-test pins the shape that matters.
    """
    depth = 0
    for i in range(open_at, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[open_at : i + 1]
    return text[open_at:]


def dimension_controls_in_download(sources: list[tuple[str, str]]) -> list[str]:
    """Every dimension control rendered inside a `downloadSlot`, file-qualified."""
    found: list[str] = []
    for rel, text in sources:
        for match in DOWNLOAD_SLOT_OPEN.finditer(text):
            body = _slot_body(text, text.index("{", match.start()))
            for control in DIMENSION_CONTROLS:
                if control in body:
                    line = text[: match.start()].count(chr(10)) + 1
                    found.append(f"{rel}:{line} ({control})")
    return found


def prose_caps(sources: list[tuple[str, str]]) -> list[str]:
    """Every live `max-w-prose`, one entry per occurrence, file-qualified."""
    found: list[str] = []
    for rel, text in sources:
        for match in PROSE_CAP.finditer(text):
            found.append(f"{rel}:{text[: match.start()].count(chr(10)) + 1}")
    return found


def selftest() -> list[str]:
    """Both clauses, shown to BITE on planted text before either is trusted.

    A gate that has never failed has not been shown to be able to. This runs
    every time, so a refactor that made either reader blind is a FAIL here
    rather than a silent green — G31's `grammar_corpus_selftest()` shape.
    """
    problems: list[str] = []

    # (a) bites a config with fields and no prompt …
    planted = "const c = {\n  screenId: 'S1',\n  searchFields: ['a'],\n}\n"
    if not (len(DECLARES_SEARCH_FIELDS.findall(planted)) > len(DECLARES_PLACEHOLDER.findall(planted))):
        problems.append("clause (a) does not bite a config with searchFields and no placeholder")
    # … and does NOT bite one that has both …
    ok = planted.replace("searchFields: ['a'],", "searchFields: ['a'],\n  searchPlaceholder: 'k',")
    if len(DECLARES_SEARCH_FIELDS.findall(ok)) > len(DECLARES_PLACEHOLDER.findall(ok)):
        problems.append("clause (a) bites a config that declares both — false positive")
    # … and is not answered by a COMMENT that mentions the field.
    commented = _strip_comments(planted + "// searchPlaceholder: 'k'\n")
    if len(DECLARES_SEARCH_FIELDS.findall(commented)) <= len(DECLARES_PLACEHOLDER.findall(commented)):
        problems.append("clause (a) accepts a COMMENTED placeholder as a real one")

    # (b) bites the class, and a comment about it does not count.
    if len(PROSE_CAP.findall('className="max-w-prose"')) != 1:
        problems.append("clause (b) does not find a live max-w-prose")
    if PROSE_CAP.findall(_strip_comments("// max-w-prose is the wrong cap\n")):
        problems.append("clause (b) counts a COMMENT naming the class")
    if PROSE_CAP.findall("className='max-w-prose-ish'"):
        problems.append("clause (b) matches a longer class containing the name")

    # (c) bites a SegmentedFilter inside a downloadSlot …
    bad = (
        "        downloadSlot={\n"
        "          <>\n"
        "            <SegmentedFilter name={'x'} options={[{ value: '' }]} />\n"
        "            <ListExportButton resource='reads' />\n"
        "          </>\n"
        "        }\n"
    )
    if not dimension_controls_in_download([("planted.tsx", bad)]):
        problems.append("clause (c) does not bite a SegmentedFilter inside downloadSlot")
    # … INCLUDING when a nested brace pair comes FIRST.
    #
    # ⚠ THIS FIXTURE EXISTS BECAUSE THE MUTATION TESTING FOUND THE GAP. A
    # matcher blinded to return at the FIRST `}` still passed every check above,
    # because the fixture's own `SegmentedFilter` sat before its first nested
    # brace and a truncated body still contained the word. A truncating matcher
    # under-reports, which is the direction this clause documents as accepted —
    # but "accepted" must not mean "undetectable", or the self-test is claiming
    # a bite it does not have (DEF-182, twice now in this repo).
    late = (
        "        downloadSlot={\n"
        "          <>\n"
        "            <ListExportButton resource={'reads'} state={state} />\n"
        "            <SegmentedFilter name='x' />\n"
        "          </>\n"
        "        }\n"
    )
    if not dimension_controls_in_download([("planted.tsx", late)]):
        problems.append("clause (c) truncates the slot body at the first nested brace")
    # … and does NOT bite the same control in `dimensionsSlot` right after one.
    good = (
        "        downloadSlot={<ListExportButton resource='reads' />}\n"
        "        dimensionsSlot={\n"
        "          <>\n"
        "            <SegmentedFilter name={'x'} options={[{ value: '' }]} />\n"
        "          </>\n"
        "        }\n"
    )
    if dimension_controls_in_download([("planted.tsx", good)]):
        problems.append("clause (c) reads PAST the download slot's closing brace")
    # … and a COMMENT naming the control in the slot does not trip it.
    commented = _strip_comments(
        "        downloadSlot={\n"
        "          {/* a SegmentedFilter used to be here */}\n"
        "          <ListExportButton resource='reads' />\n"
        "        }\n"
    )
    if dimension_controls_in_download([("planted.tsx", commented)]):
        problems.append("clause (c) counts a COMMENT naming the control")
    return problems


def run() -> tuple[str, str]:
    broken = selftest()
    if broken:
        return "FAIL", "the gate's own self-test did not bite: " + "; ".join(broken)

    sources = _sources()
    unprompted = unprompted_lists(sources)
    prose = prose_caps(sources)
    misplaced = dimension_controls_in_download(sources)

    note = (
        f"B14 rule 19: {len(unprompted)} searchable list(s) with no prompt "
        f"(baseline {UNPROMPTED_BASELINE}); "
        f"rule 18: {len(prose)} live `max-w-prose` (baseline {PROSE_CAP_BASELINE}); "
        f"toolbar capacity: {len(misplaced)} dimension control(s) in a download slot "
        f"(baseline {DIMENSION_IN_DOWNLOAD_BASELINE}); "
        "self-test: 10/10 clauses bite"
    )

    # ── RED PROOF · clause (a) ────────────────────────────────────────────
    # `searchPlaceholder` deleted from `PlansTab.tsx`, in a throwaway worktree:
    #
    #   FAIL: B14 rule 19: 1 searchable list(s) with no prompt (baseline 0);
    #   rule 18: 50 live `max-w-prose` (baseline 50); self-test: 6/6 clauses
    #   bite. 1 more than the baseline of 0. A list that declares searchFields
    #   and no searchPlaceholder prints the generic "Search this list", so the
    #   box never says what it matches (B14 rule 19, DEF-510). First:
    #   features/rating/PlansTab.tsx (1 searchFields, 0 searchPlaceholder)
    if len(unprompted) > UNPROMPTED_BASELINE:
        return (
            "FAIL",
            f"{note}. {len(unprompted) - UNPROMPTED_BASELINE} more than the baseline of "
            f"{UNPROMPTED_BASELINE}. A list that declares `searchFields` and no "
            f'`searchPlaceholder` prints the generic "Search this list", so the box never '
            f"says what it matches (B14 rule 19, DEF-510). ⚠ AND THE PROMPT MUST BE TRUE: "
            f"read the endpoint's own `q` clause and name the fields it really matches — "
            f"where the sentence a user would expect is wider than the query, file the gap "
            f"(DEF-950). Offender(s): {', '.join(unprompted)}",
        )

    # ── RED PROOF · clause (b), BOTH DIRECTIONS ───────────────────────────
    # UP — one `max-w-measure` reverted to `max-w-prose` in `WizardFrame.tsx`:
    #
    #   FAIL: B14 rule 19: 0 searchable list(s) with no prompt (baseline 0);
    #   rule 18: 51 live `max-w-prose` (baseline 50); self-test: 6/6 clauses
    #   bite. 1 MORE than the baseline. `max-w-prose` is a real Tailwind utility
    #   and the WRONG cap — 65ch where B14 rule 18 caps a description at 80%
    #   through `--desc-measure` (DEF-900). Use `max-w-measure`. First:
    #   components/WizardFrame.tsx:282
    #
    # DOWN — `serviceRequestShared.tsx`'s two converted with the baseline left
    # at 50:
    #
    #   FAIL: … rule 18: 48 live `max-w-prose` (baseline 50) … DOWN from 50 —
    #   lower PROSE_CAP_BASELINE to 48 in this file to bank the gain. A ratchet
    #   that never tightens is a number nobody reads (DEF-490).
    if len(prose) > PROSE_CAP_BASELINE:
        return (
            "FAIL",
            f"{note}. {len(prose) - PROSE_CAP_BASELINE} MORE than the baseline. "
            f"`max-w-prose` is a real Tailwind utility and the WRONG cap — `65ch` where "
            f"B14 rule 18 caps a description at 80% through `--desc-measure` (DEF-900). "
            f"Use `max-w-measure`. First: {prose[0]}",
        )
    if len(prose) < PROSE_CAP_BASELINE:
        return (
            "FAIL",
            f"{note}. DOWN from {PROSE_CAP_BASELINE} — lower `PROSE_CAP_BASELINE` to "
            f"{len(prose)} in this file to bank the gain. A ratchet that never tightens "
            f"is a number nobody reads (DEF-490), and this backlog is DEF-1006's.",
        )

    # ── RED PROOF · clause (c) ────────────────────────────────────────────
    # Run in a throwaway `git worktree` against the tree AS THE PRODUCT OWNER
    # PHOTOGRAPHED IT — before DEF-1085 swept the three screens. It names all
    # three, which is the point: this clause is not about the reads list, it is
    # about a hole three lanes stepped in one after another.
    #
    #   FAIL: B14 rule 19: 0 searchable list(s) with no prompt (baseline 0);
    #   rule 18: 50 live `max-w-prose` (baseline 50); toolbar capacity: 3
    #   dimension control(s) in a download slot (baseline 0); self-test: 10/10
    #   clauses bite. 3 more than the baseline of 0. A dimension control in
    #   `downloadSlot` grows B14 rule 12's row, which is the row that wrapped and
    #   drove the column picker off the left edge of the viewport (DEF-1085). Put
    #   it in `dimensionsSlot` — the DESIGNED second row, which is right-aligned
    #   and is what the three comments asking for 'the only slot rendered after
    #   the spacer' were reaching for. Offender(s):
    #   features/metering/PremisesListPage.tsx:461 (SegmentedFilter),
    #   features/metering/ReadsListPage.tsx:878 (SegmentedFilter),
    #   features/metering/UnitsListPage.tsx:748 (SegmentedFilter)
    if len(misplaced) > DIMENSION_IN_DOWNLOAD_BASELINE:
        return (
            "FAIL",
            f"{note}. {len(misplaced) - DIMENSION_IN_DOWNLOAD_BASELINE} more than the "
            f"baseline of {DIMENSION_IN_DOWNLOAD_BASELINE}. A dimension control in "
            f"`downloadSlot` grows B14 rule 12's row, which is the row that wrapped and "
            f"drove the column picker off the left edge of the viewport (DEF-1085). Put it "
            f"in `dimensionsSlot` — the DESIGNED second row, which is right-aligned and "
            f"is what the three comments asking for 'the only slot rendered after the "
            f"spacer' were reaching for. Offender(s): {', '.join(misplaced)}",
        )

    return "PASS", note


def main() -> int:
    status, message = run()
    print(f"{status}: {message}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

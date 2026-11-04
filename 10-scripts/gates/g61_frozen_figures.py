"""G61 — the ❄️ FROZEN B4/B5 FIGURES DID NOT MOVE. CR-052 task 19.

════════════════════════════════════════════════════════════════════════════
WHY THIS EXISTS, AND WHY IT IS NOT "RUN THE GOLDEN SUITE AGAIN"
════════════════════════════════════════════════════════════════════════════
CR-052 task 19 reads *"Golden suite unchanged, 33/33, asserted before and after
every wave"*, and every lane has honoured it by hand: run
`10-scripts/03-golden-verify.py` on both sides of the work and report both.

**G4 ALREADY COVERS THE "AFTER" HALF** — it runs that harness AND `pytest -m
golden` on every gate run, so a second gate that merely runs the suite would be
noise. This gate is the OTHER half, and building it started by asking what
running the suite twice actually proves.

**MEASURED, 2026-08-31, AND THE ANSWER IS: LESS THAN EVERYBODY THINKS.**

`10-scripts/03-golden-verify.py` opens exactly ONE file —
`04-docs/02-decisions/05-golden-tests.md` — and recomputes the arithmetic that
document states about itself. It never imports the engine and never touches
`06-backend/`. Two consequences follow and neither is obvious:

  1. **Around a CODE change the "before" run is a guaranteed no-op.** The
     harness cannot see code, so of course it says the same thing twice. The
     ritual proves nothing about the wave it brackets.
  2. **A frozen figure can be edited INLINE and the harness still says
     `33 PASS, 0 FAIL`** — because it checks that the document is consistent
     WITH ITSELF, and a lane that moves an input and its result together leaves
     it perfectly consistent.

Both were proved by mutation before this gate was written, and the second is
the one that matters:

  · **GT-3's base charge, `$30.50 → $31.00`, with the proration moved with it
    (`15/30 × 31.00 = 15.50`).** The harness's ENTIRE summary line came back
    byte-identical to the unmutated run:
        `golden-verify: 33 PASS, 0 FAIL | ruling-derived (part 3, NOT frozen):
         6 PASS, 0 FAIL | GT-1..16 self-consistency: 12 PASS, 0 FAIL,
         4 NOT-CHECKABLE | self-test: 8/8 guards bite`
    `$30.50` is not a dormant number: it is the empty-unit charge CLAUDE.md's
    own CR-052 section quotes (*"Six empty units at `$30.50` is `$183.00`
    against `$30.50`"*).
  · **GT-1's rate, `$0.12 → $0.13/kWh`, with all four dependent figures moved
    with it.** The headline `33 PASS, 0 FAIL` STILL did not move. The harness
    noticed only in two counters nobody quotes — `GT-1..16 self-consistency`
    went `11 PASS, 1 FAIL` off GT-10's cross-check, and its own `self-test`
    degraded to `7/8 guards bite`. **A GT with no cross-check has neither
    tripwire**, which is exactly why GT-3 was silent.

**So "before and after" is trying to ask a question the tool cannot answer, and
the question is a good one: DID THIS WAVE MOVE A SIGNED FIGURE?** CLAUDE.md is
explicit that it must not — *"Changing a signed rule or figure needs a finance
re-sign via HUMAN-GUIDE §6, never an inline edit"* — and until this gate,
**nothing in the repository enforced the words "never an inline edit"**. G1
comes closest and disclaims it in its own docstring: *"NOT checked here:
recomputing the packet hash against the CURRENT story+rules"* — the frozen-source
hash is written into every lifecycle trailer and verified by nobody, which is
hard-won law 1 in its purest form.

════════════════════════════════════════════════════════════════════════════
WHAT IT PINS, AND WHY FIGURES RATHER THAN THE FILE
════════════════════════════════════════════════════════════════════════════
A whole-file hash would go red on a typo fix, an added superseded stamp or a
reading-order note — all of which these two documents legitimately gain, and
all of which are how a gate earns the reputation that gets it disabled.

So this pins **the multiset of MONEY FIGURES** in the two frozen documents.
Prose is free; a number is not. `$30.50 → $31.00` goes red. Adding a sentence
does not.

**THE MANIFEST IS NOT SELF-UPDATING, AND THAT IS THE WHOLE DESIGN.** A gate
that rewrites its own baseline when it disagrees is a gate that agrees with
everything. `g61_frozen_figures.txt` changes only when a human has re-signed
through HUMAN-GUIDE §6, and the gate's failure message says so and names the
figures that appeared and disappeared, so the reviewer is looking at the
DIFFERENCE rather than at a hash.

    python3 10-scripts/gates/g61_frozen_figures.py
"""
import hashlib
import re
import sys
from pathlib import Path

import common

#: The two ❄️ FROZEN documents, finance-signed 2026-08-08.
FROZEN: tuple[str, ...] = (
    "04-docs/02-decisions/04-money-math-rules.md",
    "04-docs/02-decisions/05-golden-tests.md",
)

MANIFEST = Path(__file__).with_name("g61_frozen_figures.txt")

#: A MONEY FIGURE, and the shape is deliberately narrow.
#:
#: `$1,234.56` · `1,234.56` · `108.88` — two or more decimal places, with or
#: without a currency mark and thousands separators. NOT bare integers: the two
#: documents are full of rule numbers, section numbers, dates, tier boundaries
#: written as `0–2 kgal`, percentages written as `8.25%` and counts like
#: `1,213 accounts`, and a pattern that swept those in would go red every time
#: somebody renumbered a paragraph. A signed MONEY figure is written with its
#: cents in both documents, without exception — checked over all 33 GTs before
#: this pattern was chosen.
FIGURE = re.compile(r"(?<![\w.])\$?(\d{1,3}(?:,\d{3})*|\d+)\.(\d{2,6})(?![\d])")


def figures_in(text: str) -> list[str]:
    """Every money figure in `text`, normalised, in document order.

    Normalised so a thousands separator typed one day and not the next is not
    reported as a moved figure: `$1,234.56`, `1234.56` and `1,234.56` are ONE
    figure. What is NOT normalised is the number of decimal places — `8.30` and
    `8.300` are different statements about rounding (B4.4), and a gate that
    equated them would be blind to the one edit most likely to matter.
    """
    out = []
    for whole, frac in FIGURE.findall(text):
        out.append(f"{whole.replace(',', '')}.{frac}")
    return out


def _digest(figures: list[str]) -> str:
    """A hash of the figures AS A MULTISET, order-independent.

    Order-independent on purpose: moving a worked example to a different
    section is an editorial act; changing what it says is not. Sorted rather
    than summed, because a sum would collide (two figures could swap value and
    hash the same, which is precisely a moved figure).
    """
    joined = "\n".join(sorted(figures))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def measure(root: Path) -> dict[str, tuple[int, str, list[str]]]:
    out: dict[str, tuple[int, str, list[str]]] = {}
    for rel in FROZEN:
        path = root / rel
        if not path.exists():
            out[rel] = (0, "MISSING", [])
            continue
        figs = figures_in(path.read_text(encoding="utf-8"))
        out[rel] = (len(figs), _digest(figs), figs)
    return out


def read_manifest() -> dict[str, tuple[int, str]]:
    """`<count>  <sha256>  <path>` per line; `#` comments ignored."""
    pinned: dict[str, tuple[int, str]] = {}
    if not MANIFEST.exists():
        return pinned
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        count, digest, rel = line.split(None, 2)
        pinned[rel.strip()] = (int(count), digest)
    return pinned


def _difference(pinned_figs: list[str], now_figs: list[str]) -> tuple[list[str], list[str]]:
    """What appeared and what disappeared, as multisets.

    Reported instead of a bare "the hash differs", because a hash tells a
    reviewer that something moved and never which thing — and the reviewer is
    the person who has to decide whether it needs a re-sign."""
    from collections import Counter

    before, after = Counter(pinned_figs), Counter(now_figs)
    gone = sorted((after - before).elements()), sorted((before - after).elements())
    return gone[0], gone[1]


# ── SELF-SABOTAGE: this gate must be shown to bite on every run ─────────────
#
# The G56 precedent. A gate whose subject is a document nobody edits could rot
# for months and nobody would know; these two cases run in memory on every
# invocation, touch no file, and each must behave as stated or the gate FAILS
# ITSELF. The second is as important as the first: a gate that fires on prose
# is a gate somebody switches off.
SABOTAGES = (
    (
        "a moved money figure is CAUGHT",
        "Base proration 15/30 x 30.50 = 15.25",
        "Base proration 15/30 x 31.00 = 15.50",
        True,
    ),
    (
        "an edited SENTENCE is not (or this gate gets switched off)",
        "Base proration 15/30 x 30.50 = 15.25",
        "Base proration, 15/30 x 30.50 = 15.25, per B4.3",
        False,
    ),
)


def selftest() -> list[str]:
    problems = []
    for name, before, after, must_bite in SABOTAGES:
        moved = _digest(figures_in(before)) != _digest(figures_in(after))
        if moved != must_bite:
            problems.append(
                f"self-test BLIND: {name!r} — expected {'a difference' if must_bite else 'no difference'} "
                f"and got {'a difference' if moved else 'none'}"
            )
    return problems


def run() -> tuple[str, str]:
    root = common.REPO_ROOT
    now = measure(root)
    pinned = read_manifest()

    blind = selftest()
    if blind:
        return "FAIL", "; ".join(blind)

    if not pinned:
        listing = ", ".join(f"{rel.split('/')[-1]} {n} figure(s)" for rel, (n, _d, _f) in now.items())
        return "FAIL", (
            f"{MANIFEST.name} is missing — nothing is pinned, so this gate cannot answer "
            f"whether a signed figure moved. Measured now: {listing}. Write the manifest "
            "from a tree you have verified, never from one you are about to change."
        )

    # ⚠ THE MANIFEST AND ITS SIDECARS ARE TWO COPIES OF ONE FACT, so the first
    # thing checked is that they agree. Without this the digest could be
    # re-pinned while the `.figures` list stayed stale, and the failure message
    # below would name the wrong figures with total confidence — a check whose
    # output cannot be trusted is worse than no check (DEF-182).
    for rel, (want_count, want_digest) in pinned.items():
        side = MANIFEST.with_name(MANIFEST.stem + "." + rel.split("/")[-1] + ".figures")
        if not side.exists():
            return "FAIL", (
                f"{side.name} is missing — the manifest pins a digest for {rel} and nothing "
                "can say WHICH figures it stands for, so a failure could not name them."
            )
        listed = side.read_text(encoding="utf-8").split()
        if _digest(listed) != want_digest or len(listed) != want_count:
            return "FAIL", (
                f"{side.name} does not match the digest pinned for {rel} in {MANIFEST.name} "
                f"({len(listed)} figure(s) listed, {want_count} pinned). Re-pin BOTH in one "
                "act, from a tree you have verified."
            )

    problems = []
    for rel, (count, digest, figs) in now.items():
        if digest == "MISSING":
            problems.append(f"{rel}: FROZEN document is absent from the tree")
            continue
        if rel not in pinned:
            problems.append(f"{rel}: not pinned in {MANIFEST.name} — add it with a recorded re-sign")
            continue
        want_count, want_digest = pinned[rel]
        if digest == want_digest and count == want_count:
            continue
        appeared, disappeared = [], []
        pinned_path = MANIFEST.with_name(MANIFEST.stem + "." + rel.split("/")[-1] + ".figures")
        if pinned_path.exists():
            appeared, disappeared = _difference(
                pinned_path.read_text(encoding="utf-8").split(), figs
            )
        detail = ""
        if appeared or disappeared:
            detail = (
                f" — gone: {', '.join(disappeared[:8]) or 'none'}"
                f" | new: {', '.join(appeared[:8]) or 'none'}"
            )
        problems.append(
            f"{rel}: a ❄️ FROZEN figure MOVED ({want_count} figures pinned, {count} now){detail}. "
            "CLAUDE.md: a signed figure changes by finance re-sign through HUMAN-GUIDE §6, "
            f"NEVER by an inline edit. If the re-sign happened, record it and re-pin {MANIFEST.name} "
            "in the same commit."
        )

    total = sum(n for n, _d, _f in now.values())
    if problems:
        return "FAIL", common.summarize(problems)
    return "PASS", (
        f"{total} ❄️ frozen money figure(s) across {len(FROZEN)} finance-signed document(s) "
        f"unchanged; {len(SABOTAGES)}/{len(SABOTAGES)} self-sabotages behaved as stated"
    )


def main() -> int:
    status, detail = run()
    print(f"G61 frozen-figures: {status} — {detail}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

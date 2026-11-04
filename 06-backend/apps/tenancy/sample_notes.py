# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-3224 (high, 2026-09-02) — a service the tenant SELLS is dropped
#           from the sample estate and nothing on screen ever says so. The
#           seeder composes a correct sentence naming the service and the
#           reason and writes it to `logger.info`, a server log no clerk can
#           open. The block SUCCEEDS, so every surface is green.
# Rules:    BR-TEN-060 (a gap is NAMED, never swallowed) · B14 rule 31 (nothing
#           internal is ever visible to a utility user — not an id, not a rule
#           number, not a path) · CLAUDE.md law 2 (built is not wired)
# Story:    US-TEN-019 (sample data)                          Screens: S8 (SET-03)
# ───────────────────────────────────────────────────────
"""THE SENTENCE A SEEDER WANTS TO SAY TO A PERSON, MADE FIT FOR A SCREEN.

WHY THIS EXISTS
---------------
A sample-data block that FAILS already carries a sentence to the Sample data
panel. A block that SUCCEEDS could not: `apps/tenancy/sample_data.py` recorded
`detail=None` on every seeded block, so a run that built a whole estate and
deliberately left a service out of it had nowhere to say so. That is `DEF-3224`,
and it cost a round trip with the Product Owner — they ticked Electric, Water
and Sewer, the estate took water as its backbone, electric got no meter, no read
and no line on any of the 95 bills (not even its `$12.00` base, `$576.00` a month
across 48 units), and every surface reported success.

The sentences themselves are NOT written here. They are the seeder's own — the
`refused` reasons on `core.sample_fixture.EstatePlan` — and they are good: each
names the service and why it was left out, in words somebody can act on. This
module does one thing to them.

WHAT IT DOES, AND WHY IT IS NOT A TIDY-UP
------------------------------------------
**B14 rule 31 is RATIFIED and ENFORCED: nothing internal is ever visible to a
utility user** — not a rule number, not a module path, not a file name. PO,
2026-08-19, verbatim: *"Youa re also adding internal content and BR codes on
screen, that is not required."*

Three of the four refusal sentences carry one: the sewer-behind-no-water reason
opens with a frozen rating rule's id, the no-primary-unit reason cites a
CLAUDE.md hard rule in its middle sentence, and the register-versus-billed one
cites an open question's closure in its last. They were written for a log, where
that provenance is exactly right, and a log is where they have always gone.

So the reference comes off at the boundary where the sentence becomes screen
text, and it comes off in the way that leaves the best English:

  1. **Drop any sentence BUT THE LAST that carries a reference.** In every case
     measured that is the RATIONALE sentence — *why the product works this way* —
     which B14 rule 33 puts at zero words on screen anyway, and dropping it
     leaves the fact and the instruction standing:

         "gas: the tenant declares no primary unit of measure for it, so a
          meter would have to be created with a blank UoM. Set a primary UoM
          on Settings -> Services & UoM and load the sample data again"

  2. **The LAST sentence is never dropped — the reference is cut out of it
     instead**, and the punctuation and capitalisation around the cut are
     tidied.

⚠ **CLAUSE 2 IS THE LOAD-BEARING ONE AND IT WAS NOT IN THE FIRST DRAFT.** That
draft dropped any sentence carrying a reference, and on
`_MULTIPLIER_NO_FACTOR` — whose reference sits in its FINAL sentence — it
deleted *"set the factor on Settings -> Services & UoM and load the sample data
again"*. **That is the instruction**, and `G33`'s own failure output says it in
as many words: *"SHORTEN BY DELETING THE RATIONALE, NEVER THE INSTRUCTION …
cutting the second passes this gate and makes the message useless."* A rule that
CAN delete the instruction is the dangerous one, however good its prose is the
rest of the time, so the last sentence is now untouchable.

⚠ **THIS IS A BOUNDARY, NOT A LICENCE.** It does not make it safe to write a
rule id into a sentence bound for a screen; it makes the panel safe against the
ones already written in a file this lane does not own. The durable fix is for
the reason strings to lose their references at source, with the provenance in
the code comment beside them — which is what rule 31 actually asks for and what
`core/sample_fixture.py`'s owning lane can do in one edit.

⚠ **THE PATTERNS ARE G28's, AND A TEST HOLDS THEM TOGETHER.** They are declared
here rather than imported because application code may not import a gate script,
so `tests/test_def_3224_seeded_block_note.py` loads `G28`'s own list and asserts
this module's output produces zero hits against it. A pattern added to the gate
and not to this file turns that test red, which is the only thing that can keep
two copies of one list honest (hard-won law 1).
"""

from __future__ import annotations

import re

#: The internal-reference patterns, copied from `10-scripts/gates/
#: g28_internal_references.py` and held in step by the test named above, plus
#: the two that gate does not look for because no catalogue string has ever
#: carried them: a CLAUDE.md rule citation and a dotted module path.
_INTERNAL_REFERENCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    # BR-BIL-015, US-BIL-002, EP-TEN-05 … the module-scoped id grammar.
    # `\d{3,5}(?!\d)` per CLAUDE.md's five-digit ceiling — the lookahead is
    # load-bearing, or `BR-RAT-12345` reads as `BR-RAT-1234`.
    re.compile(r"\b(?:BR|US|EP|ADR)-[A-Z]{2,4}-\d{1,5}(?!\d)"),
    # OQ-168, DEF-307, GT-42, TD-17, IS-04, TC-5, CR-016 — the flat registers.
    re.compile(r"\b(?:OQ|DEF|GT|TD|IS|TC|CR)-\d{1,5}(?!\d)"),
    # `apps/notifications/bulk_summary`, `documents.py`, `apps.metering.services`
    re.compile(r"\bapps[/.][a-z_]+[/.]|[\w/]+\.py\b"),
    # `GET /billing/runs/{id}/findings`
    re.compile(r"\b(?:GET|POST|PUT|PATCH|DELETE)\s+/[\w/{}.-]+"),
    # `column bill_run_decisions.case`
    re.compile(r"\b(?:column|table)\s+[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*"),
    # A PO ruling or a dated PO quote — the WORDS, never a bare date.
    re.compile(
        r"PO ruling|Product Owner ruling|\bPO,?\s+20\d\d-\d\d-\d\d|"
        r"\bthe PO\b|ruled it on 20\d\d-|by Product Owner ruling"
    ),
    re.compile(r"hard-won law", re.IGNORECASE),
    # `CLAUDE.md rule 3`, `CLAUDE.md law 11`, and the bare file name.
    re.compile(r"CLAUDE\.md(?:\s+(?:hard\s+)?(?:rule|law)\s+\d+)?"),
)

#: A sentence ends at `.`, `!` or `?` followed by whitespace. `CLAUDE.md rule 3`
#: and `apps.metering.services` survive this split because their dots are
#: followed by a letter, not by a space.
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")


def carries_internal_reference(text: str) -> bool:
    """True when `text` holds anything B14 rule 31 keeps off a screen."""
    return any(pattern.search(text) for pattern in _INTERNAL_REFERENCE_PATTERNS)


def _strip_references(sentence: str) -> str:
    """The sentence with the references cut out and the seams tidied.

    Clause 2 above. It leaves a grammatical scar where clause 1 leaves clean
    prose, and it is used on the LAST sentence anyway, because a scar is a much
    smaller cost than a deleted instruction.
    """
    out = sentence
    for pattern in _INTERNAL_REFERENCE_PATTERNS:
        # The possessive goes with the reference: cutting `OQ-004` out of
        # "OQ-004's closure is …" and leaving "'s closure is …" reads as damage
        # rather than as a sentence.
        out = re.sub(pattern.pattern + r"(?:'s)?", "", out, flags=pattern.flags)
    # ❄️ and friends ride beside a rule id in these strings; a bare decoration
    # left behind reads as a typo. Then collapse the whitespace the cuts leave.
    out = re.sub(r"[❄️⚠🔒]️?", "", out)
    # A reference is usually the whole content of its bracket — "a SCALE factor
    # (BR-MET-143)" — and an empty pair left standing reads as a rendering bug.
    out = re.sub(r"\s*[(\[]\s*[)\]]", "", out)
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,.;:])", r"\1", out)
    out = out.strip()
    # A cut that took the opening word leaves a lower-case start; a screen
    # sentence begins with a capital. The leading `service:` label is left
    # alone — a service code is lower case on purpose.
    if out and ":" not in out[:20] and out[0].islower():
        out = out[0].upper() + out[1:]
    return out


def for_screen(text: str | None) -> str | None:
    """The seeder's sentence, fit to be rendered to a utility user.

    `None` and blank in, `None` out — so a caller can hand this whatever a seam
    returned without deciding first whether there was anything to say.
    """
    raw = (text or "").strip()
    if not raw:
        return None
    if not carries_internal_reference(raw):
        return raw
    sentences = [s.strip() for s in _SENTENCE_BREAK.split(raw) if s.strip()]
    # Clause 1 on everything but the last sentence, clause 2 on the last one.
    # The last sentence is where the instruction lives in every one of these
    # strings, and it is never dropped.
    last = sentences[-1]
    kept = [s for s in sentences[:-1] if not carries_internal_reference(s)]
    kept.append(_strip_references(last) if carries_internal_reference(last) else last)
    return " ".join(s for s in kept if s) or None

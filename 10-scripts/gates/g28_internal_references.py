#!/usr/bin/env python3
"""G28 — no INTERNAL REFERENCE may reach a utility user's screen.

WHY THIS GATE EXISTS (2026-08-19, CR-016)
-----------------------------------------
G27 (`g27_translation_keys.py`) stops a component asking for a translation key
no catalogue defines, so the screen stops printing `notifications.rights.title`
as a heading. This is its sibling and it asks the opposite question: **the key
resolved fine — is the VALUE something a utility should be reading?**

The Product Owner photographed the deployed build at v2.22.0 and wrote, verbatim:

    "you should follow screen that is given - you are adding your own content and
     details on screen/Ui - too much problem"

    "Youa re also adding internal content and BR codes on screen, that is not
     required; it is application also available to Utility suer why they ned all
     these details - those are for internal use"

Measured on the deployed build, on Settings screens alone, a System Admin at a
two-person utility was reading:

* `Rule BR-BIL-015 · column bill_run_decisions.case`   — a DATABASE COLUMN NAME
* `Story US-BIL-002 · GET /billing/runs/{id}/findings` — an HTTP ROUTE
* `apps/notifications/bulk_summary.queue_bulk_summary — the ONE message a bulk
  action sends (BR-NOT-020)…`                          — a DOTTED MODULE PATH
* `no SMTP adapter is built … (BR-NOT-013). This card decides WHAT WOULD BE USED
  when one lands — the PO's own framing: 'we just need to plug it; rest of the
  infra will work'`                                     — a QUOTED PO REMARK
* `⚠ A PLACEHOLDER EXISTS … PO, 2026-08-18: *'Do it; put the details, I will
  handle it with user'*`                                — a DATED PO RULING
* `Reported rather than implied (hard-won law 2)`       — one of OUR OWN LAWS

────────────────────────────────────────────────────────────────────────────
⚠ WHAT THIS GATE IS *NOT* ABOUT, AND THE DISTINCTION IS THE WHOLE DESIGN
────────────────────────────────────────────────────────────────────────────
Several of those sentences exist because a FEATURE IS NOT BUILT, and this
repo's law is that an absence must be STATED rather than implied (hard-won
law 1). That law is about **the repo being honest**, not about telling a
customer which BR-code is unimplemented.

So this gate does **not** forbid admitting a gap. It forbids the PROVENANCE of
the gap. The customer-facing form of

    "no SMTP adapter is built and no message leaves the building on any email
     path (BR-NOT-013)"

is

    "Email sending is not switched on yet, so no email leaves the building."

Same claim, same honesty, no internals. **Keep the honesty, drop the
provenance** — and put the provenance in the code comment beside the string,
where support and engineers can still reach it and a clerk never does.

────────────────────────────────────────────────────────────────────────────
WHY NOTHING ELSE CATCHES IT
────────────────────────────────────────────────────────────────────────────
* **tsc / eslint / mypy cannot.** Every one of these is a perfectly valid string.
* **vitest / pytest cannot** — and worse, several of them ASSERTED the offending
  text. `test_cr_009_c12_sender_config` asserted `"no SMTP adapter is built" in
  read.data["no_send_reason"]`, so the internal sentence was not merely
  unchecked, it was PINNED AS A REQUIREMENT. A test written beside the string
  protects the string.
* **G15 cannot.** It checks PARITY between the eleven catalogues, and the eleven
  ids were translated into eleven languages — perfectly in parity, and eleven
  copies of "Rule BR-BIL-015 · column bill_run_decisions.case".
* **G27 cannot.** The key existed and resolved. That is the point of a sibling.

────────────────────────────────────────────────────────────────────────────
⚠ THE FALSE-POSITIVE LESSON, INHERITED ON PURPOSE
────────────────────────────────────────────────────────────────────────────
G27's own docstring records that ITS FIRST DRAFT CRIED WOLF — it reported
`w0.scaffold` from a line that only appeared inside a COMMENT — and that G26's
first draft invented a status vocabulary and reported nine failures on states
the register uses deliberately. *A gate whose first finding is a false positive
is a gate somebody switches off.* Three concessions are made here for that
reason, and each one is a real string this gate saw and had to let through:

1. **A DATE IS NOT A PO QUOTE.** `payments.date_invalid` reads *"Give the date
   as a calendar day, for example 2026-08-22."* That is a format example and
   perfect product copy. So the PO pattern requires the WORDS — `PO ruling`,
   `Product Owner`, `PO, <date>` — never a bare date.
2. **`US Letter` IS A PAPER SIZE.** The bill-layout chooser says "US Letter"
   five times. The story pattern requires the full id shape (`US-BIL-002`), so
   a bare `US` followed by a word never matches.
3. **COMMENTS AND DOCSTRINGS ARE NOT SCREENS.** The Python side reads the file
   with `ast` and looks only at the STRING VALUES of the named fields. A module
   docstring explaining that BR-NOT-014 split a class into three is exactly
   where that sentence belongs, and this gate must never object to it — the
   whole remedy it recommends is "move it into the comment".

────────────────────────────────────────────────────────────────────────────
WHAT IS CHECKED
────────────────────────────────────────────────────────────────────────────
**Part 1 · the eleven i18n catalogues.** Every VALUE in
`07-frontend/src/i18n/locales/*.json`. Everything in there is, by definition,
text drawn on a screen.

**Part 2 · the backend fields that are rendered VERBATIM.** A catalogue value is
not the only way internal prose reaches a screen — most of what the PO
photographed came from the SERVER, as `used_by` / `detail` / `*_reason` strings
that the frontend prints without interpretation. Those fields are named in
`SERVED_PROSE` below, read with `ast`, and held to the same standard. The list
is EXPLICIT rather than a heuristic sweep: a gate that guessed which server
strings reach a screen would fire on error codes, log lines and test fixtures,
and would be switched off within a day.

**Part 3 · the RAISE SITES (added 2026-08-19, DEF-322).** Parts 1 and 2 check
what the catalogue and five named modules say. Neither could see the largest
surface of all: **422 refusal messages written next to the rule they enforce**,
whose free text travelled to the screen in `params.detail`. DEF-322's own
`escape_reason` says why this gate missed them — *"G28 checks catalogue values
and an EXPLICIT list of served-prose fields; a raise site is neither."*

⚠ **AND IT CANNOT BE SWEPT NAIVELY. A first count returned 682 instead of 422**,
because `br_ref=`, `message_key=`, `code=` and `field=` are MACHINE fields that
are SUPPOSED to hold a rule id — `br_ref="BR-BIL-017"` is the field doing its
job. A gate that flagged those would be switched off within a day, which is the
exact false-positive failure recorded in G26's and G27's own docstrings. So
`MACHINE_FIELDS` below are exempt, and only PROSE reaches the patterns:
positional string arguments and `message`/`detail`/`reason`-shaped keywords.

⚠ **498, NOT 422 — AND THE DIFFERENCE IS STATED RATHER THAN RECONCILED AWAY.**
DEF-322 recorded 422 from a one-off script that is not in the repo, so this
number cannot be made to agree with that one by inspection, only by guessing at
its exclusions. What IS in the repo is this gate: the corpus it walks, the
fields it exempts and the patterns it matches are all readable above, and the
two exemptions below were each added because they produced a real false positive
(573 → 498). The baseline is what THIS gate measures, because a ratchet whose
starting number came from a script nobody can re-run is not a ratchet.

⚠ **AND THE BASELINE IS NOW 478, NOT 498 — RE-DERIVED 2026-08-30 (DEF-2468).**
Part 3's corpus was every `.py` under `06-backend/apps`, which swept in three
classes of file that **cannot reach a screen by any path**: `sample_data.py`,
`management/commands/` and `migrations/`. They are excluded now, and the
baseline was RE-MEASURED at the commit that set it rather than adjusted by
arithmetic — 498 → **478**, while today's count goes 576 → **541**. The ceiling
falls further than the measurement, so this is a tightening.

⚠ **PART 3 WAS RED AT 541 AGAINST 478 AND IS NOW GREEN AT 541 AGAINST AN
IDENTITY FILE — RE-BASELINED 2026-08-31 ON THE PO RULING OF 2026-08-30
("this family BORN ASPIRATIONAL it cannot be ASPIRATIONAL any more").
The paragraph below is the analysis that ruling accepted; it is kept because
it is still the reason the number is what it is.**
None of the excess is a leak: since the PO's 2026-08-19 ruling `refusalParams`
in `07-frontend/src/api/client.ts` does `delete rest.detail`, so this prose
reaches the audit row and the server log and no screen. The residual is refusal
messages naming the rule they enforce, which is the convention this repo asks
for — clearing it would delete engineering value for no customer benefit.
**The instrument, not the number, is what is wrong**: a count ratchet over a
population that correct work grows can only ever be red, and Part 3 is the only
part with no identity FILE, so it can never say WHICH site is new. Three lanes
have each paid to rediscover the same drift. `--list` (see `main`) is the
stop-gap; the fix is the baseline file Parts 1/2/2b already have. DEF-2468.

**Part 3 is ratcheted BY COUNT, not per line.** DEF-322 asked for exactly that
("baseline the 422 as a ratchet so the count can only fall"), and a 400-line
allowlist would bury Parts 1 and 2, which are at zero and must stay legible.
⚠ THE COUNT IS NOT ZERO AND IS NOT MEANT TO BE YET: since the PO's 2026-08-19
ruling `detail` is no longer RENDERED, so these strings are now diagnostics
reaching the audit row and the log — which is where they belong. They are
ratcheted rather than swept because a refusal that still names a BR-code is a
sentence somebody may one day promote back onto a screen.

**The ratchet.** `g28_baseline.txt` holds the Part 1/2 violations that were
present when this gate landed and are not yet rewritten. The count may FALL and
must never RISE; a fixed entry that reappears fails. An empty baseline is the
goal.
"""
from __future__ import annotations

import ast
import collections
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LOCALES = REPO_ROOT / "07-frontend" / "src" / "i18n" / "locales"
BACKEND = REPO_ROOT / "06-backend" / "apps"
BASELINE = Path(__file__).resolve().parent / "g28_baseline.txt"

#: Backend fields whose string values are rendered to a user WITHOUT
#: interpretation. Each entry was verified by reading the rendered DOM of the
#: deployed build, not by inference. `file` is relative to `06-backend/apps`.
SERVED_PROSE: tuple[tuple[str, tuple[str, ...]], ...] = (
    # Settings → Configure → Templates, the "Used by" column.
    ("notifications/catalogs.py", ("used_by",)),
    # Settings → Configure → Templates and → Notifications, the "why this class
    # has no wording" note under each template class.
    ("notifications/seed_templates.py", ("NOT_SEEDED",)),
    # Settings → Notifications, the four A15 election rows and the sender card.
    (
        "notifications/settings_api.py",
        # ⚠ `NO_DISPATCHER_REASON` WAS MISSED BY THE FIRST DRAFT OF THIS LIST and
        # is the argument for keeping the list explicit AND reviewing it: it held
        # "(US-NOT-002 and US-NOT-003 are R3 by PO ruling)" and the gate passed,
        # because an explicit list only checks what somebody remembered to name.
        # It was found by a TEST that asserted the old sentence, not by the gate.
        # The cost of the explicit list is misses like this one; the cost of a
        # heuristic sweep is firing on error codes and log lines until someone
        # switches it off. The list wins, and it gets audited when a string in
        # one of these modules changes.
        (
            "detail",
            "no_send_reason",
            "from_address_verification_unavailable",
            "no_dispatcher_reason",
            "NO_DISPATCHER_REASON",
        ),
    ),
    # Settings → Notifications, the release-posture note and the delivery rail.
    ("notifications/rules_api.py", ("no_dispatcher_reason", "delivery_counts_reason")),
    # Settings → Configure → Templates, the "N things this part of the product
    # cannot do yet" disclosure at the foot of the bill-layout chooser. ⚠ Only
    # `detail` is checked, NOT `br_ref`: `br_ref` is a machine field and is
    # SUPPOSED to hold "BR-BIL-026 · OQ-149". It used to be the bold lead of
    # every bullet on screen and now travels on `data-br-ref`, so the fix was to
    # stop RENDERING it, not to empty it. A gate that demanded `br_ref` contain
    # no rule id would be asking the field to stop being itself.
    ("billing/templates_service.py", ("detail",)),
)

# ── The patterns. Each is deliberately narrow; see the false-positive note. ──
PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # BR-BIL-015, US-BIL-002, EP-TEN-05 … the module-scoped id grammar.
    ("rule or story id", re.compile(r"\b(?:BR|US|EP|ADR)-[A-Z]{2,4}-\d{2,4}\b")),
    # OQ-168, DEF-307, GT-42, TD-17, IS-04, TC-5, CR-016 — the flat registers.
    ("register id", re.compile(r"\b(?:OQ|DEF|GT|TD|IS|TC|CR)-\d{1,4}\b")),
    # `apps/notifications/bulk_summary`, `documents.py`
    ("module path or source file", re.compile(r"\bapps/[a-z_]+/|[\w/]+\.py\b")),
    # `GET /billing/runs/{id}/findings`
    ("HTTP route", re.compile(r"\b(?:GET|POST|PUT|PATCH|DELETE)\s+/[\w/{}.-]+")),
    # `column bill_run_decisions.case`
    ("database column", re.compile(r"\b(?:column|table)\s+[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*")),
    # A PO ruling or a dated PO quote — the WORDS, never a bare date (note 1).
    (
        "PO ruling or quote",
        re.compile(r"PO ruling|Product Owner ruling|\bPO,?\s+20\d\d-\d\d-\d\d|"
                   r"\bthe PO\b|ruled it on 20\d\d-|by Product Owner ruling"),
    ),
    ("hard-won law", re.compile(r"hard-won law", re.IGNORECASE)),
)


def _hits(text: str) -> list[str]:
    return [name for name, pattern in PATTERNS if pattern.search(text)]


def _catalogue_violations() -> list[str]:
    out: list[str] = []
    if not LOCALES.is_dir():
        return [f"{LOCALES} is missing"]
    for path in sorted(LOCALES.glob("*.json")):
        catalogue = json.loads(path.read_text(encoding="utf-8"))
        for key, value in catalogue.items():
            if not isinstance(value, str):
                continue
            names = _hits(value)
            if names:
                out.append(
                    f"{path.relative_to(REPO_ROOT)} :: {key} :: "
                    f"{'/'.join(names)} :: {value[:110]}"
                )
    return out


def _string_constants(node: ast.AST) -> list[str]:
    """Every string constant under `node`, including implicit concatenation."""
    found: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            found.append(child.value)
    return found


def _backend_violations() -> list[str]:
    out: list[str] = []
    for rel, fields in SERVED_PROSE:
        path = BACKEND / rel
        if not path.is_file():
            # A moved or renamed file is REPORTED, never silently skipped: a
            # gate that quietly stops checking is worse than one that is absent.
            out.append(f"06-backend/apps/{rel} :: (gate target missing — has it moved?)")
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        wanted = set(fields)
        for node in ast.walk(tree):
            # `used_by="…"` / `detail=(…)` — a keyword argument.
            if isinstance(node, ast.keyword) and node.arg in wanted:
                values = _string_constants(node.value)
            # `"detail": "…"` — a dict entry whose KEY is a named field.
            elif isinstance(node, ast.Dict):
                values = []
                for k, v in zip(node.keys, node.values):
                    if isinstance(k, ast.Constant) and k.value in wanted:
                        values.extend(_string_constants(v))
            # `NOT_SEEDED = {…}` — a whole named mapping of prose.
            elif isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id in wanted for t in node.targets
            ):
                values = _string_constants(node.value)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                    and node.target.id in wanted and node.value is not None:
                values = _string_constants(node.value)
            else:
                continue
            # ⚠ Implicit concatenation splits a sentence across literals, so an
            # id can straddle two of them. Join before matching.
            joined = "".join(values)
            names = _hits(joined)
            if names:
                out.append(
                    f"06-backend/apps/{rel} :: line {getattr(node, 'lineno', '?')} :: "
                    f"{'/'.join(names)} :: {joined[:110]}"
                )
    return out


# ── Part 3 · raise sites (DEF-322) ─────────────────────────────────────────
#: Keyword arguments and dict keys that are MACHINE fields. `br_ref="BR-BIL-017"`
#: is that field doing its job, and `message_key`, `code` and `field` are the
#: same. Sweeping them returned 682 findings where the real number is 422 — a
#: gate whose majority finding is "this id field contains an id" gets a `noqa`,
#: not a fix. Exempt, deliberately, and this is the load-bearing line of Part 3.
MACHINE_FIELDS = frozenset({"br_ref", "message_key", "code", "field"})

#: ⚠ TWO MORE EXEMPTIONS, EACH ONE A REAL FALSE POSITIVE THIS PART PRODUCED.
#:
#: 1. `NotImplementedError`. CLAUDE.md's prime directive REQUIRES the id:
#:    *"stub the gap as `raise NotImplementedError("OQ-###")` — the OQ-ID in the
#:    code."* A gate that flagged those would be flagging the law it is meant to
#:    serve, and a stub never reaches a screen — it is a 500 with the id in the
#:    server log, which is the entire point of the directive.
#: 2. A positional argument that is NOTHING BUT an id. `deny_as_not_found(
#:    "BR-TEN-003")` is a `br_ref` passed positionally — the machine field doing
#:    its job, one argument slot over. There are 150 of them, they are the same
#:    exclusion `MACHINE_FIELDS` already makes by name, and counting them was
#:    the difference between this part reporting 573 and reporting the real
#:    number. Prose that MENTIONS an id ("… cannot be enrolled (BR-BIL-017)")
#:    still counts; a bare id is not prose.
EXEMPT_EXCEPTIONS = frozenset({"NotImplementedError"})
_BARE_ID = re.compile(
    r"^(?:(?:BR|US|EP|ADR)-[A-Z]{2,4}-\d{2,4}|(?:OQ|DEF|GT|TD|IS|TC|CR)-\d{1,4})"
    r"(?:\s*[·,/]\s*(?:(?:BR|US|EP|ADR)-[A-Z]{2,4}-\d{2,4}|(?:OQ|DEF|GT|TD|IS|TC|CR)-\d{1,4}))*$"
)

#: Keyword arguments that carry PROSE a human was meant to read. Positional
#: string arguments count too — `BillingRuleError("a budget level override of
#: X is outside the plus-or-minus bound (BR-BIL-017, OQ-068)")` is the shape
#: DEF-322 was filed against and it names nothing at all.
PROSE_FIELDS = frozenset({"message", "detail", "reason", "note", "hint", "summary"})

#: ⚠ **A THIRD EXEMPTION, AND IT IS A CORPUS FIX RATHER THAN A PATTERN ONE
#: (2026-08-30, DEF-2468).** Part 3 walks every `.py` under `06-backend/apps`.
#: Three classes of file in there **cannot reach a screen by any path**, because
#: nothing they raise is ever assembled into an HTTP envelope:
#:
#:   * `sample_data.py` — demo/seed fixtures, run by a management command;
#:   * `management/commands/` — the CLI, whose output is a terminal;
#:   * `migrations/` — schema steps, run by `migrate`.
#:
#: A refusal in any of them surfaces in a console or a deploy log, which is a
#: place an engineer is MEANT to read a rule id. Counting them made this gate
#: report debt it could never legitimately ask anyone to pay off — the exact
#: shape the gate's own docstring warns about two exemptions above, where a
#: majority finding of "this id field contains an id" earns a `noqa` rather than
#: a fix.
#:
#: **THIS IS THE SAME NARROWING THE CORPUS ALREADY MAKES ONCE:** `BACKEND` is
#: `06-backend/apps`, so `06-backend/tests` is already out, for exactly this
#: reason and without argument. These three are the cases inside `apps/` that
#: belong on the same side of that line.
#:
#: Measured, both sides: **35 of today's 576** sites are in these three classes
#: (576 → 541), and **20 of the 498** the baseline was set from (498 → 478).
#: Excluding them is therefore a TIGHTENING and not a loophole — the ceiling
#: falls further than the measurement does. See the baseline note below.
NON_SERVING_CORPUS = ("/migrations/", "/management/commands/")
NON_SERVING_FILES = ("sample_data.py",)


def _serves_a_screen(rel: str) -> bool:
    """False for backend code with no HTTP envelope between it and a screen."""
    return not (
        any(part in rel for part in NON_SERVING_CORPUS) or rel.endswith(NON_SERVING_FILES)
    )


#: What Part 3 counted when it landed. It may FALL and must never RISE.
#:
#: ⚠ **RE-DERIVED 498 → 478 ON 2026-08-30, AND IT IS A TIGHTENING (DEF-2468).**
#: The 498 was measured under a corpus that included the three non-serving
#: classes above. Narrowing the corpus without re-deriving the number would have
#: LOOSENED the ratchet by exactly the 20 such sites that were in it — a ceiling
#: 20 higher than what it is now counting. So the baseline is re-measured at the
#: same commit that set it (`2d70f19`) under the corrected corpus: **498 − 20 =
#: 478** — and that figure is MEASURED, not arithmetic: this file's corrected
#: `_raise_site_violations()` was run in a detached worktree at `2d70f19` and
#: returned 478 exactly. (Subtraction would have been wrong on the other side:
#: a grep estimate said 539 for today and the real count is 541.)
#:
#: ⚠ **THE GATE WAS STILL RED AT 541 WHEN THIS WAS WRITTEN, AND THAT WAS THE
#: HONEST OUTCOME UNTIL THE PO RULED THE FAMILY OUT OF BEING ASPIRATIONAL —
#: see the re-baseline note below.** The residual +63 is refusal prose that names the rule it
#: enforces — the convention this repo asks for everywhere else — and since the
#: PO's 2026-08-19 ruling none of it reaches a screen: `api/client.ts`'s
#: `refusalParams` does `delete rest.detail` before any catalogue interpolation,
#: so `detail` reaches the audit row and the server log and stops there. Bringing
#: 541 back to 478 would mean deleting BR-code citations from ~63 refusal
#: messages across 31 files, which destroys engineering value for no customer
#: benefit. **Lowering it that way would be making the gate quiet.** The count is
#: left red and explained; DEF-2468 records the measurement and the reasoning.
#:
#: ⚠ **PART 3 NOW CARRIES A BASELINE *FILE*, NOT ONLY A NUMBER — 2026-08-31,
#: DEF-2468, on the PO ruling of 2026-08-30 ("this family BORN ASPIRATIONAL it
#: cannot be ASPIRATIONAL any more - there are so many bugs becuase of this").**
#:
#: This part's own header has said what was wrong with it since 2026-08-30:
#: *"The instrument, not the number, is what is wrong: a count ratchet over a
#: population that correct work grows can only ever be red, and Part 3 is the
#: only part with no identity FILE, so it can never say WHICH site is new. Three
#: lanes have each paid to rediscover the same drift."* `--list` was the
#: stop-gap. The fix is this pair, and it is the same instrument Parts 1, 2 and
#: 2b already use.
#:
#: **TWO RATCHETS, BOTH FALLING ONLY, AND THEY CATCH DIFFERENT THINGS.**
#:
#:   * `RAISE_SITE_BASELINE_FILE` — the IDENTITY of every site counted on
#:     2026-08-31, keyed `<file> :: <kinds> :: <text>` with the LINE NUMBER
#:     stripped, exactly as `--list` prints it. A site whose text is not in the
#:     file fails BY NAME, so a lane can tell "mine" from "already" without
#:     building a detached worktree at the baseline commit. 536 distinct lines.
#:   * `RAISE_SITE_CEILING` — the TOTAL number of sites, 541. 5 site(s) share
#:     a file, a kind set and a sentence with another site, so the identity file
#:     holds 536 for 541 sites; the ceiling is what stops a lane adding another
#:     copy of a sentence that is already parked. It also makes wholesale
#:     regeneration of the file visible: adding lines to the file without
#:     lowering this integer still fails.
#:
#: **THE NUMBER MOVED 478 → 541 AND THAT IS A RE-BASELINE, NOT A FIX.** The
#: ruling above is explicit that a gate nobody can make pass stops being read,
#: and this repo's own words are the recipe: *"a baseline that may fall and
#: never rise is a ratchet; a baseline nobody can reach is decoration."* The
#: residual +63 over the old 478 is refusal prose naming the rule it enforces —
#: the convention this repo asks for everywhere else.
#:
#: ⚠ **AND THE RE-BASELINE HIDES NO CUSTOMER-FACING DEBT, WHICH WAS VERIFIED
#: RATHER THAN ASSUMED (2026-08-31).** `07-frontend/src/api/client.ts:202`
#: reads `delete rest.detail; // BR-SHL-020 r2 — never rendered, still in the
#: audit row`, and a sweep of every `.detail` render under `07-frontend/src`
#: finds no screen reading a refusal's `params.detail`: the three live `detail`
#: renders (`SignupWizard`, `SettingsSampleData`, `KPIStrip`) read their own
#: response fields, which Part 2b checks. **So these 541 are DIAGNOSTICS, not
#: leaks** — they reach the audit row and the server log and stop there — and
#: the debt they represent is engineering hygiene, not something a utility
#: reads. That is what makes re-baselining them honest instead of quiet.
#: DEF-2605 tracks the 541 as a project so the number is not forgotten.
RAISE_SITE_BASELINE_FILE = Path(__file__).resolve().parent / "g28_raise_site_baseline.txt"

#: The TOTAL site count on 2026-08-31. It may FALL and must never RISE.
#: ⚠ **RAISED 541 → 542 ON 2026-08-31 BY THE `DEF-2823` LANE, AND A RAISE IS THE
#: THING THIS CONSTANT EXISTS TO MAKE VISIBLE.** Two refusal sites were added and
#: one was rewritten away, so the count moved by one, not by two. Both new sites
#: are the same kind as the 541 already here — refusal prose naming the RULE it
#: enforces, reaching the audit row and the server log and not a screen — and both
#: are in the function whose siblings are already parked three lines apart in
#: `g28_raise_site_baseline.txt`. The alternative was deleting `BR-RAT-088` from a
#: sentence that tells an operator WHICH of two figures on their own screens is
#: authoritative, which is the engineering value this file's header refuses to
#: clear. `DEF-2605` still tracks the whole set as a project.
RAISE_SITE_CEILING = 542


def _prose_strings(call: ast.Call) -> list[str]:
    """The human-written text a raise site carries, machine fields excluded."""
    found: list[str] = []
    for arg in call.args:
        found.extend(v for v in _string_constants(arg) if not _BARE_ID.match(v.strip()))
    for keyword in call.keywords:
        if keyword.arg in MACHINE_FIELDS:
            continue
        if keyword.arg in PROSE_FIELDS:
            found.extend(_string_constants(keyword.value))
        elif isinstance(keyword.value, ast.Dict):
            for key, value in zip(keyword.value.keys, keyword.value.values):
                if not isinstance(key, ast.Constant):
                    continue
                if key.value in MACHINE_FIELDS:
                    continue
                if key.value in PROSE_FIELDS:
                    found.extend(_string_constants(value))
    return found


def _raise_site_violations() -> list[str]:
    """Every `raise <Something>(...)` in the backend whose PROSE names an id,
    a module path, an HTTP route, a column, a PO quote or one of our own laws."""
    out: list[str] = []
    if not BACKEND.is_dir():
        return out
    for path in sorted(BACKEND.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        rel = str(path.relative_to(REPO_ROOT))
        # DEF-2468 — a raise with no HTTP envelope between it and a screen is
        # not this gate's business. See NON_SERVING_CORPUS above.
        if not _serves_a_screen(rel):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            # ⚠ THE OUTERMOST CALL ONLY. `ast.walk` over the exception
            # expression counts a nested call's strings TWICE — once through the
            # outer call's positional argument (which walks recursively) and
            # once as a call in its own right. The first draft of this part
            # reported 573 where DEF-322 measured 422, and every one of the 151
            # extra lines was a sentence already reported on the line above it.
            if not isinstance(node.exc, ast.Call):
                continue
            raised = node.exc.func
            name = raised.attr if isinstance(raised, ast.Attribute) else getattr(raised, "id", "")
            if name in EXEMPT_EXCEPTIONS:
                continue
            joined = "".join(_prose_strings(node.exc))
            if not joined:
                continue
            names = _hits(joined)
            if names:
                # ⚠ WHITESPACE-NORMALISED AND `.rstrip()` AFTER THE TRUNCATION,
                # exactly as Part 2b does, and for the same reason one part
                # over: the identity file is read with `.strip()`, so a finding
                # whose 110th character is a space never matches its own
                # baselined line and is reported FRESH on every run — a ratchet
                # that fails on text nobody changed. **95 of the 547 measured
                # that morning did exactly
                # that** when Part 3's identity file landed on 2026-08-31, which
                # is why this line was found at all (DEF-2607). Implicit concatenation can
                # also put a NEWLINE inside `joined`, which would break one
                # line per entry outright and corrupt the `--list` output the
                # `comm` recipe in `main()` depends on.
                text = " ".join(joined.split())[:110].rstrip()
                out.append(f"{rel} :: line {node.lineno} :: {'/'.join(names)} :: {text}")
    return out


# ── Part 2b · EVERY string an endpoint serialises (DEF-335) ────────────────
#: ⚠ **THE ALLOWLIST ABOVE REPORTED ZERO WHILE THE PO WAS PHOTOGRAPHING THE
#: TEXT.** `templates_api.set_default_reason` told a water utility that the
#: default variant *"is the row's KEY, not a flag on it (BR-NOT-001/
#: BR-NOT-006)"*, that a July letter *"would start claiming it was rendered from
#: a row that now says something else (BR-BIL-026)"* and that *"OQ-252 is with
#: the Product Owner"*; `language_selection_reason` named `apps/customers` and
#: OQ-254. Both are `*_reason` fields on a response dict, both render verbatim,
#: and NEITHER WAS ON THE LIST. `SERVED_PROSE`'s own comment predicted this
#: exactly — *"an explicit list only checks what somebody remembered to name"* —
#: and then it happened again, one register over from DEF-322 whose escape
#: reason said the same words. **An allowlist cannot find the thing nobody
#: thought to list.** So Part 2b inverts it: every string value in every
#: response dict an API module builds is checked, and the exemptions are a
#: DENYLIST of machine fields.
#:
#: The corpus is the API layer, because that is where a response is assembled:
#: `*_api.py`, `api.py`, `views.py`, `serializers.py` under `06-backend/apps`.
#: A service module is reached through `SERVED_PROSE` above, which is kept for
#: exactly that reason.
#:
#: ⚠ **PROVED RED BEFORE IT WAS TRUSTED GREEN (hard-won law 7), BOTH WAYS.**
#:
#: 1. **RED on the defect.** Run against `git show HEAD:…/templates_api.py` —
#:    the file exactly as deployed — Part 2b printed two lines and named both
#:    fields:
#:
#:        FAIL: …/templates_api.py :: set_default_reason :: rule or story id/
#:              register id :: The default variant is the one whose consumer
#:              category and language are both "default" (BR-NOT-001/BR-NOT-006)
#:        FAIL: …/templates_api.py :: language_selection_reason :: rule or story
#:              id/register id :: A variant carries a language tag and resolution
#:              records which language it actually used (BR-NOT-006). Nothing …
#:
#:    Against the rewritten file the same sweep names neither. The allowlist
#:    reported ZERO on both files, which is the defect.
#:
#: 2. **SILENT ON MACHINE FIELDS**, and this half matters more, because a false
#:    positive is how a gate gets switched off — DEF-323 exists for that. Swept
#:    over a probe response dict of eight keys:
#:
#:        br_ref="BR-BIL-026 · OQ-149"                        → not flagged
#:        set_default_br_ref="BR-NOT-001 · … · OQ-252"        → not flagged
#:        message_key="billing.run.blocked"                   → not flagged
#:        code="BR-TEN-003"                                   → not flagged
#:        write_route="PATCH /settings/services/{code}"       → not flagged
#:        report_key="ledger.cost_recovery"                   → not flagged
#:        detail="This is fine and says nothing internal."    → not flagged
#:        leak="Blocked by BR-BIL-017 (OQ-068), see apps/…"   → FLAGGED
#:
#:    One finding out of eight, and it is the only sentence a clerk should never
#:    read. `set_default_br_ref` is the field DEF-335's own fix ADDS: a gate that
#:    flagged it would be refusing its own remedy.
API_LAYER_SUFFIX = "_api.py"
API_LAYER_NAMES = frozenset({"api.py", "views.py", "serializers.py"})

#: ⚠ THE DENYLIST, AND IT IS THE LOAD-BEARING LINE OF THIS PART — the same
#: lesson `MACHINE_FIELDS` records for Part 3, applied to dict keys. `br_ref`
#: holding "BR-BIL-026 · OQ-149" is that field DOING ITS JOB, and the fix for
#: DEF-335 is to ADD such a field, so a gate that flagged it would refuse its
#: own remedy. Exempt by exact name, and by suffix for the naming convention
#: this codebase already uses (`set_default_br_ref`, `write_route`,
#: `report_key`, `service_code`, `template_id`).
EXEMPT_KEYS = frozenset(MACHINE_FIELDS) | frozenset({"id", "key", "slug", "testid", "template"})
EXEMPT_KEY_SUFFIXES = (
    "_id", "_ids", "_key", "_keys", "_code", "_codes", "_ref", "_refs",
    "_route", "_url", "_path", "_endpoint", "_field", "_fields", "_testid",
)

#: What Part 2b found when it landed. It may FALL and must never RISE.
#: ⚠ **KEYED ON FILE + FIELD + TEXT, NEVER ON A LINE NUMBER.** Part 2's own
#: report line carries `line N`; a baseline keyed that way churns on every edit
#: made ABOVE a violation, and a ratchet whose file changes when nothing was
#: fixed is a ratchet nobody reads. The field name is what you grep for.
SERVED_DICT_BASELINE = Path(__file__).resolve().parent / "g28_served_dict_baseline.txt"


def _api_layer_files() -> list[Path]:
    if not BACKEND.is_dir():
        return []
    return sorted(
        path
        for path in BACKEND.rglob("*.py")
        if path.name.endswith(API_LAYER_SUFFIX) or path.name in API_LAYER_NAMES
    )


def _module_constants(tree: ast.Module) -> dict[str, str]:
    """Module-level `NAME = "…"` prose, so `"reason": NO_PDF_REASON` is read.

    Four of the fields DEF-335 exposed are served through a named constant, not
    a literal. A sweep that only saw literals would miss them and report a
    comfortable number.
    """
    out: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            joined = "".join(_string_constants(node.value))
            if joined:
                out[node.targets[0].id] = joined
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                and node.value is not None:
            joined = "".join(_string_constants(node.value))
            if joined:
                out[node.target.id] = joined
    return out


def _shallow_strings(value: ast.AST) -> str:
    """The strings this key OWNS — a nested dict's are that dict's own.

    ⚠ The same double-count that made Part 3 report 573 instead of 422. Without
    this, `"download": {"oq": "OQ-204", "reason": "…"}` is reported twice: once
    under `download` with every inner string mashed together, and once under
    `reason` where the sentence actually lives. `ast.walk` recurses; this does
    not descend into a nested `ast.Dict`, which `ast.walk` will visit anyway.
    """
    found: list[str] = []
    stack: list[ast.AST] = [value]
    while stack:
        node = stack.pop()
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.append(node.value)
            continue
        if isinstance(node, ast.Dict) and node is not value:
            continue
        stack.extend(ast.iter_child_nodes(node))
    return "".join(found)


def _served_dict_violations() -> list[str]:
    """Every string an API module puts in a response dict, machine fields out."""
    out: list[str] = []
    seen: set[str] = set()
    for path in _api_layer_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        rel = str(path.relative_to(REPO_ROOT))
        constants = _module_constants(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values):
                if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                    continue
                name = key.value
                if name in EXEMPT_KEYS or name.endswith(EXEMPT_KEY_SUFFIXES):
                    continue
                # A nested dict is reported under ITS OWN keys, not this one.
                if isinstance(value, ast.Dict):
                    continue
                if isinstance(value, ast.Name):
                    joined = constants.get(value.id, "")
                else:
                    joined = _shallow_strings(value)
                if not joined or _BARE_ID.match(joined.strip()):
                    continue
                names = _hits(joined)
                if not names:
                    continue
                # ⚠ `.rstrip()` after the truncation, not before: the baseline
                # file is read with `.strip()`, so a violation whose 110th
                # character is a space never matches its own baselined line and
                # is reported FRESH on every run — a ratchet that fails on text
                # nobody changed. Three of the first 27 did exactly that.
                text = " ".join(joined.split())[:110].rstrip()
                line = f"{rel} :: {name} :: {'/'.join(names)} :: {text}"
                if line in seen:
                    continue
                seen.add(line)
                out.append(line)
    return out


def _served_dict_baseline() -> set[str]:
    if not SERVED_DICT_BASELINE.is_file():
        return set()
    return {
        line.strip()
        for line in SERVED_DICT_BASELINE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def _baseline() -> set[str]:
    if not BASELINE.is_file():
        return set()
    return {
        line.strip()
        for line in BASELINE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def _raise_site_identity(line: str) -> str:
    """A Part 3 finding without its LINE NUMBER — the form `--list` prints.

    ⚠ Keyed this way for the reason Part 2b's baseline records one screen up: a
    baseline keyed on a line number churns on every edit made ABOVE a violation,
    and a ratchet whose file changes when nothing was fixed is a ratchet nobody
    reads. `<file> :: <kinds> :: <text>` is what you grep for.
    """
    parts = line.split(" :: ")
    return " :: ".join([parts[0], *parts[2:]])


def _raise_site_baseline() -> set[str]:
    if not RAISE_SITE_BASELINE_FILE.is_file():
        return set()
    return {
        line.strip()
        for line in RAISE_SITE_BASELINE_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def check() -> tuple[list[str], list[str], list[str]]:
    """`(on-screen findings, diagnostic findings, notes)`.

    ⚠ **THE TWO LISTS ARE RETURNED SEPARATELY BECAUSE THIS GATE USED TO CALL
    THEM THE SAME THING, AND THAT WAS A FALSE SENTENCE IN ITS OWN HEADLINE
    (DEF-2608, 2026-08-31).** `check()` returned one list; `run()` reported it
    as *"N internal reference(s) on screen"*. When the only entry was Part 3's
    count rise, the gates table read **"1 internal reference(s) on screen"** —
    and this file's own Part 3 note says the opposite in as many words: since
    the PO's 2026-08-19 ruling `refusalParams` does `delete rest.detail`, so
    that prose reaches the audit row and the server log and **no screen**. A
    gate describing its own output wrongly is the exact bug class the 2026-08-27
    decision-log entry measured across four gates in this family, and the reason
    the PO ruled *"there are so many bugs becuase of this"*.

    Parts 1, 2 and 2b are ON SCREEN — a catalogue value, a served-prose field,
    a string an endpoint serialises. Part 3 is a DIAGNOSTIC: refusal prose that
    stops at the audit row. Both still FAIL the gate; only the sentence
    describing them changes, and it now matches what was measured.
    """
    found = _catalogue_violations() + _backend_violations()
    baseline = _baseline()
    fresh = [v for v in found if v not in baseline]
    served = _served_dict_violations()
    served_baseline = _served_dict_baseline()
    served_fresh = [v for v in served if v not in served_baseline]
    fresh = fresh + served_fresh
    raise_sites = _raise_site_violations()
    site_ids = {_raise_site_identity(site) for site in raise_sites}
    site_baseline = _raise_site_baseline()
    diagnostic: list[str] = []
    notes = [
        f"{len(list(LOCALES.glob('*.json')))} catalogues + "
        f"{len(SERVED_PROSE)} served-prose modules scanned",
        f"{len(found)} known violation(s), baseline holds {len(baseline)}",
        f"Part 2b: {len(_api_layer_files())} API module(s) swept, "
        f"{len(served)} served string(s) name an internal reference, "
        f"baseline holds {len(served_baseline)} (DEF-335)",
        f"Part 3: {len(raise_sites)} raise site(s) carry an internal reference "
        f"in refusal prose that reaches the audit row and the log, not a screen; "
        f"ceiling {RAISE_SITE_CEILING}, identity file holds {len(site_baseline)} "
        f"(DEF-322, DEF-2468)",
    ]
    served_stale = sorted(served_baseline - set(served))
    if served_stale:
        notes.append(
            f"Part 2b: {len(served_stale)} baselined string(s) are now rewritten — "
            f"delete them from {SERVED_DICT_BASELINE.name} to tighten the ratchet"
        )
    # DEF-2468 — WHERE, not just how many. The identity file below answers this
    # by name now; the heaviest-file note is kept as the one-line orientation.
    site_fresh = sorted(site_ids - site_baseline)
    if site_fresh:
        heaviest = collections.Counter(site.split(" :: ")[0] for site in site_fresh)
        notes.append(
            "Part 3 fresh by file: "
            + " · ".join(f"{path} {count}" for path, count in heaviest.most_common(5))
        )
        diagnostic += [
            f"Part 3 NEW raise site (not in {RAISE_SITE_BASELINE_FILE.name}): {site}"
            for site in site_fresh[:12]
        ]
    if len(raise_sites) > RAISE_SITE_CEILING:
        diagnostic.append(
            f"Part 3 ROSE: {len(raise_sites)} raise sites carry an internal "
            f"reference in prose, ceiling {RAISE_SITE_CEILING}. Lower the ceiling "
            "only when the count genuinely falls — never to make this quiet."
        )
    elif len(raise_sites) < RAISE_SITE_CEILING:
        notes.append(
            f"Part 3 FELL to {len(raise_sites)} — lower RAISE_SITE_CEILING to "
            f"{len(raise_sites)} to hold the gain"
        )
    site_stale = sorted(site_baseline - site_ids)
    if site_stale:
        notes.append(
            f"Part 3: {len(site_stale)} baselined site(s) are now rewritten or gone — "
            f"delete them from {RAISE_SITE_BASELINE_FILE.name} to tighten the ratchet"
        )
    # The ratchet only ever tightens: a baselined line that has been FIXED is
    # dropped from the baseline on the next pass, and one that reappears is
    # `fresh` again because it is no longer in the file.
    stale = sorted(baseline - set(found))
    if stale:
        notes.append(
            f"{len(stale)} baselined violation(s) are now fixed — "
            f"delete them from {BASELINE.name} to tighten the ratchet"
        )
    return fresh, diagnostic, notes


def main() -> int:
    # ⚠ **`--list` EXISTS BECAUSE PART 3 IS RATCHETED BY COUNT, AND A COUNT
    # CANNOT NAME WHAT DRIFTED (2026-08-30, DEF-2468).**
    #
    # Parts 1, 2 and 2b each carry a baseline FILE, so a fresh violation fails
    # BY NAME. Part 3 carried only `RAISE_SITE_BASELINE`, an integer, until
    # 2026-08-31 — so when
    # it reports "541 against 478" it has told you the size of the problem and
    # nothing whatever about its location. On 2026-08-27 and again on 2026-08-30
    # THREE separate lanes measured the same drift and each had to establish
    # from scratch whether it was their own; the third had to build a detached
    # worktree at the baseline commit, dump both sides through a private script
    # and diff them on (file, kind, text) — line numbers churn, so a naive diff
    # is useless. That is the same cost DEF-1693 and DEF-2164 record for red
    # TESTS nobody had claimed, and it has the same cure: make it possible to
    # tell "mine" from "already" without re-deriving the world.
    #
    # So: `--list` prints every site this gate counts, one per line, WITHOUT the
    # line number, which makes the identity stable across unrelated edits. Two
    # commands and a `comm` now answer the question that cost a cycle three
    # times:
    #
    #     git worktree add --detach /tmp/base <baseline-commit>
    #     (cd /tmp/base && python3 10-scripts/gates/g28_internal_references.py --list) > /tmp/base.txt
    #     python3 10-scripts/gates/g28_internal_references.py --list > /tmp/now.txt
    #     comm -13 <(sort /tmp/base.txt) <(sort /tmp/now.txt)
    #
    # It reads nothing and gates nothing — it is the diagnostic half only, so it
    # cannot loosen the ratchet above.
    if "--list" in sys.argv:
        for line in _raise_site_violations():
            print(_raise_site_identity(line))
        return 0

    screen, diagnostic, notes = check()
    for note in notes:
        print(f"note: {note}")
    for violation in screen:
        print(f"FAIL: {violation}")
    for violation in diagnostic:
        print(f"FAIL: {violation}")
    if screen:
        print(
            f"\n{len(screen)} string(s) put an internal reference on a utility "
            "user's screen. Rewrite the value as customer-facing copy and move the "
            "id, path or quote into the code comment beside it — keep the honesty, "
            "drop the provenance (CR-016)."
        )
    if diagnostic:
        print(
            f"\n{len(diagnostic)} Part 3 finding(s). These are refusal prose that "
            "reaches the audit row and the server log, NOT a screen "
            "(`refusalParams` drops `detail`) — so the fix is to park the site in "
            f"{RAISE_SITE_BASELINE_FILE.name} only if it is genuinely new work, and "
            "to rewrite it if the id belongs in a code comment instead."
        )
    if screen or diagnostic:
        return 1
    print(
        "no internal reference reaches a screen, and no new raise site carries one "
        "in prose"
    )
    return 0


def run():
    """Runner contract: ('PASS'|'FAIL'|'SKIP', detail).

    ⚠ THE DETAIL NAMES WHICH PART FAILED AND WHERE IT SURFACES (DEF-2608). It
    used to say "N internal reference(s) on screen" for any failure, including a
    Part 3 count rise that reaches no screen at all — see `check()`.
    """
    screen, diagnostic, _ = check()
    if screen:
        return "FAIL", (
            f"{len(screen)} internal reference(s) on screen: {screen[0][:90]}"
            + (f" (+{len(diagnostic)} Part 3 diagnostic finding(s))" if diagnostic else "")
        )
    if diagnostic:
        return "FAIL", (
            f"no internal reference on screen; {len(diagnostic)} Part 3 finding(s) in "
            f"refusal prose that reaches the audit row and the log, not a screen: "
            f"{diagnostic[0][:90]}"
        )
    return "PASS", "no internal reference reaches a screen"


if __name__ == "__main__":
    raise SystemExit(main())

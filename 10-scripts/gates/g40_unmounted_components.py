"""G40 — unmounted components. Added 2026-08-21 from `DEF-520`.

⚠ **THIS IS THE QUESTION `G13` CANNOT ASK, AND `DEF-520` IS WHAT IT COSTS.**
Hard-won law 2 says *"built is not wired"* and names G13 as the enforcement.
G13 asks *"does every optional prop have a non-test caller"* — a question about
PROPS. It has no question about MOUNTS. So on 2026-08-21 the product carried
twelve components under `07-frontend/src/components/workflow/**`, four live
endpoints and 39 backend tests for a five-stage import, **no screen rendered any
of it**, and G13 reported PASS. The PO deployed, clicked Import, and got the
previous wizard.

A sibling rather than a widening, deliberately: G13 is RATIFIED (PO 2026-08-11,
*"keep all four blocking"*) and its own docstring says a loosening there is a
change to a ratified decision. Adding a check is additive; editing G13's
question is not.

WHAT IT ASKS
------------
For every `export function <Uppercase>` in a non-test `.tsx` under
`07-frontend/src`: does at least one NON-TEST module render it as `<Name`?

Deliberately narrow, so that it means exactly what it says:

  * **Non-test callers only.** A component rendered only by its own test is the
    precise shape of `DEF-520` — `WorkflowRunner.test.tsx` rendered
    `WorkflowRunner` all day while nothing else did.
  * **`export function` only, not `const X = () => …`.** Every component in this
    repo is declared the first way; matching the second would need a parser and
    would buy nothing today. If that changes, this gate gets a second pattern
    and the baseline moves in the same commit.
  * **Rendering, not importing.** `import { Receipt }` proves nothing — a type
    import, a re-export or a dead line all satisfy it. `<Receipt` is the mount.

  * **A mount through a lookup table counts, and it did not until 2026-09-01
    (`DEF-2735`).** See the next section — this is the one widening this gate
    has ever had, and it was bought with a false alarm on four live icons.

THE FALSE ALARM THIS GATE RAISED, AND WHY THE WIDENING IS NARROW (DEF-2735)
--------------------------------------------------------------------------
⚠ **ON 2026-08-31 THIS GATE WENT RED ON FOUR COMPONENTS THAT WERE RENDERING ON A
SCREEN.** `BellIcon`, `DocumentIcon`, `MessageIcon` and `SignatureIcon` are drawn
by the Templates list, and they had been since the PO asked for icons in that
column on 2026-08-30 (*"on this screen for KInd - can you use Icons - it will
save real estate on screen"*). The mount is one level of indirection:

    const KIND_GLYPHS = [{ match: /e-?sign/i, icon: SignatureIcon }, …];
    …
    <glyph.icon />

`<SignatureIcon` appears nowhere, so the old single pattern could not see it.

**A false alarm here is not a harmless one.** `DEF-2735`'s own row concluded
*"either wire them or delete them"* — the honest reading of a red this gate is
trusted for — and acting on it would have DELETED four icons a clerk is looking
at. That is `DEF-174`'s shape exactly: remediating destructively on evidence
that was wrong. CLAUDE.md states the principle this gate has to answer to — *"a
check whose output cannot distinguish pass from fail is worse than no check,
because it is trusted."*

**So the widening is the narrowest one that answers the case, and it is
PER FILE.** A component counts as mounted when ONE file both

  1. renders a JSX **member expression** — `<something.PROP` — and
  2. assigns that component to a property of that same name — `PROP: Name`.

Both halves in the same module, which is what an icon table is and what an
accidental coincidence is not. Concatenating every file first (the way the
`<Name` search does) would let `<foo.icon />` in one screen mount an
`icon: DeadThing` in an unrelated one, which is a loosening, not a fix.

**What it still cannot see, stated so nobody assumes it:** a table built in file
A and rendered in file B, `React.createElement(Name)`, and a component reached
only through `props.children`. Those stay invisible and would still be reported.

THE SECOND FALSE ALARM, AND IT WAS ON A ROUTED SCREEN (`DEF-GOV-4009`)
---------------------------------------------------------------------
⚠ **ON 2026-09-05 THIS GATE WENT RED ON `ConnectionDetailPage`, WHICH IS ROUTED
AT `INT-02 · S142` AND HAS BEEN SINCE IT LANDED.** `App.tsx` imports it under
another name, because a second component of that name once existed:

    import { ConnectionDetailPage as IntegrationDetailPage } from "@/features/integrations/ConnectionDetailPage";
    …
    element: <IntegrationDetailPage />,   // INT-02 · S142

`<ConnectionDetailPage` appears nowhere in the repo, so the `<Name` search could
not see it — **exactly `DEF-2735`'s shape one level of indirection sideways**,
and with the same cost: the honest reading of this gate's red is *"wire it or
delete it"*, and acting on it would have deleted a screen a clerk opens.

**The clause is the narrowest one that answers the case, and it is PER FILE**,
for the reason the table clause is: a component counts as mounted when ONE file
both

  1. imports it under an alias — `import { Name as Alias } from …` — and
  2. renders `<Alias` in that same module.

Joining every file first would let an alias in one screen mount a dead export in
another. **Still invisible, and named so nobody assumes otherwise:** a default
import (`import Thing from …`, which binds no export NAME at all), a namespace
import, and `React.lazy(() => import(…))`.

THE THIRD FAULT WAS THE GATE'S INPUT, NOT ITS QUESTION (`DEF-CWP-3882`)
----------------------------------------------------------------------
⚠ **`_tsx_files()` USED `git ls-files`, SO IT READ THE INDEX FOR ONE HALF OF THE
QUESTION AND THE WORKING TREE FOR THE OTHER.** Tracked files were listed and then
read FROM DISK — so a lane at r11 step 3, with a new component and the new screen
that mounts it both still untracked, had its component invisible (not listed, so
never exported) **or**, in the shape that actually bit, its component tracked and
its mount not (listed, so read; the mount untracked, so never a caller). The gate
reported dead UI over a screen sitting in the working tree beside it, at the exact
moment r11 asks a lane to run it, and it could not tell that from the real thing.

**It walks the filesystem now**, so both halves of the question come from one
world. A file deleted in the working tree but still tracked correctly stops
counting — it is not there.

WHAT IT DOES NOT ASK, STATED SO NOBODY ASSUMES IT
-------------------------------------------------
It does not check that the renderer is itself reachable from a route. A chain of
three components nobody routes to would pass this and fail a human. That check
needs the router graph, and this gate is deliberately the cheap half that would
have caught the defect it was written for. `DEF-523` (no DOM test environment)
is the other half of the same hole.

RATCHET, NOT A BAR — the repo's own G23/G25/G29/G31 discipline. Three components
are unmounted today and each is named below with its reason. The number may FALL
and may never RISE; a fall must lower the baseline in the same commit, or the
gate keeps claiming debt that is already paid off.

PROVEN RED BEFORE TRUSTED GREEN (law 7): the self-test below re-runs the
detector with `App.tsx` withheld, which is the state the branch was in this
morning, and asserts the whole workflow kit shows up as unmounted. It printed
13 — the twelve kit components plus the page itself.

Python 3.12 stdlib only. Safe to run from any cwd.
"""

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "07-frontend" / "src"

#: Exact count, never a ceiling. Each entry carries WHY it is unmounted, so
#: that closing one is a deliberate act and so that a new arrival cannot hide
#: behind a round number.
#:
#:   * `Receipt`       — WFL-01 stage 5. Unreachable until a load can commit;
#:                       committing waits on the load endpoint (`DEF-520`).
#:   * `RollbackNotice`— the same screen's rollback callout, same reason. Drawing
#:                       it now would promise a 30-day rollback nothing honours.
#:   * `QuantityUnitField` — a FormModal field with no current caller.
#:
#: ⚠ The first two are the honest kind of unmounted: a component built to a
#: ruled design whose SERVER half does not exist yet. The third is the kind
#: `DEF-520` was about. The gate cannot tell them apart and does not pretend to
#: — that is what this comment is for.
# ⚠ **3 → 1 on 2026-08-22 (CR-023 W2).** `Receipt` and `RollbackNotice` were two
# of the three, and they were the shape this gate exists for: both were built,
# both had passing tests of their own, and stage 5 of WFL-01 — the screen that
# is the ONLY thing either of them draws — did not exist, so neither had ever
# rendered for a user. They are mounted by
# `features/metering/ImportWorkflowPage.tsx` now. `QuantityUnitField` is the
# one that remains.
# ⚠ **1 → 0 on 2026-09-01 (DEF-2735).** `QuantityUnitField` is mounted by
# `features/billing/billRunStep23.tsx` now, so the last baselined entry is paid
# off and the baseline falls with it in the same commit — the gate's own rule.
# **The baseline is zero, and zero is the number to defend.** A component that
# arrives unmounted fails on the commit that creates it; there is nothing left
# in here for a new one to hide behind.
# ⚠ **0 → 4 on 2026-10-13 (`DEF-GOV-10106`), AND IT IS NOT A LOOSENING.** The
# gate had drifted to 49 against this 0, red and unowned, while redesigns left
# their superseded components behind. 45 were triaged and closed (deleted as
# left over, or — `ReviewIcon` — restructured so a lookup the gate cannot read
# became one it can). These FOUR remained because each was a capability a user
# did not have, and whether to wire it or delete it changed what a user
# could DO — a product decision, not this gate's: `PricingShadowPanel`,
# `RunWizard`, `SettingsOwnedField` and `SettingsOwnedProvider`. The PO took
# all three decisions the same day (*"1a, 2A 3A"*, decision log *"THREE PO
# RULINGS ON THE LEFT-OVER SCREEN PIECES"*), and each left this list in the
# commit that wired it:
#   * 4 → 3 (2.577.0): `PricingShadowPanel` is mounted on the bulk bill run's
#     Check step again (`OQ-BIL-12791` → A).
#   * 3 → 0 (`OQ-WRK-12792` → A, `OQ-WRK-12793` → A): `RunWizard` is routed at
#     `/{tenant}/runbooks/{key}/run` by `features/runbooks/run/RunWizardPage.tsx`
#     and the setup page's run pop-up is deleted (`DEF-WRK-10123`);
#     `SettingsOwnedField` and `SettingsOwnedProvider` are rendered by
#     `features/runbooks/RunbookSettingsFields.tsx` on the Scope tab, the scope
#     dialog and the wizard (`DEF-WRK-10122`).
# **The baseline is zero again, and zero is the number to defend.**
UNMOUNTED_BASELINE = 0

COMPONENT = re.compile(r"^export function ([A-Z][A-Za-z0-9]*)\s*\(", re.M)

#: `<glyph.icon />` — a JSX member expression. Group 1 is the PROPERTY, which is
#: the half that names what was rendered; the object it hangs off is a local
#: whose name tells us nothing.
MEMBER_RENDER = re.compile(r"<[A-Za-z_$][\w$]*\.([A-Za-z_$][\w$]*)[\s/>]")


#: `import { ConnectionDetailPage as IntegrationDetailPage } from "…"` — group 1
#: is the braced clause, which is where every named import and every `as` in it
#: lives. Multi-line import blocks are ordinary here, hence DOTALL over `[^}]*`.
ALIAS_IMPORT = re.compile(r"import\s*\{([^}]*)\}\s*from", re.S)
ALIAS_PAIR = re.compile(r"([A-Za-z_$][\w$]*)\s+as\s+([A-Za-z_$][\w$]*)")


def _tsx_files() -> list[Path]:
    """Every `.tsx` under `07-frontend/src` **as it is on disk** (`DEF-CWP-3882`).

    Not `git ls-files`: that answers the question from the INDEX while the
    contents are read from the WORKING TREE, so an uncommitted screen is not a
    caller and an uncommitted component is not an export — one half of the
    question from each world. r11 step 3 runs this gate before the commit, which
    is precisely when the two disagree.
    """
    if not SRC.exists():
        return []
    return sorted(p for p in SRC.rglob("*.tsx") if p.is_file())


def _alias_mounted(text: str) -> set[str]:
    """Components this ONE module renders under an import alias (`DEF-GOV-4009`).

    Both halves must be in the SAME text: `import { Name as Alias }` and a
    `<Alias` render. Per file for the reason `_table_mounted` is per file — an
    alias bound in one screen must not mount a dead export in another.
    """
    mounted: set[str] = set()
    for clause in ALIAS_IMPORT.findall(text):
        for original, alias in ALIAS_PAIR.findall(clause):
            if not original[:1].isupper():
                continue
            if re.search(rf"<{re.escape(alias)}[\s/>]", text):
                mounted.add(original)
    return mounted


def _table_mounted(text: str) -> set[str]:
    """Components this ONE module renders through a lookup table (DEF-2735).

    Both halves must be in the SAME text: a `<x.PROP` member render, and a
    `PROP: Component` assignment. Kept per file on purpose — see the DEF-2735
    section above; joining every file first would let one screen's `<x.icon />`
    mount another screen's dead `icon:` entry.
    """
    props = set(MEMBER_RENDER.findall(text))
    if not props:
        return set()
    mounted: set[str] = set()
    for prop in props:
        for name in re.findall(rf"\b{re.escape(prop)}\s*:\s*([A-Z][A-Za-z0-9]*)\b", text):
            mounted.add(name)
    return mounted


def _unmounted(
    withhold: str | None = None,
    blind_to_tables: bool = False,
    blind_to_aliases: bool = False,
) -> list[tuple[str, str]]:
    """`(component, file)` for every export nothing non-test renders.

    `withhold` drops one file from the CALLER set only — the self-test uses it
    to reproduce a build where a mount does not exist yet.

    `blind_to_tables` disables the DEF-2735 indirection clause, and
    `blind_to_aliases` the DEF-GOV-4009 one. Both clauses can only ever REMOVE
    findings, so a green run proves nothing about either: a clause that matched
    nothing at all would look identical. The self-tests switch each off and
    require the findings to come back.
    """
    files = _tsx_files()
    source = [f for f in files if not f.name.endswith(".test.tsx")]
    exported: dict[str, Path] = {}
    for path in source:
        text = path.read_text(encoding="utf-8")
        for match in COMPONENT.finditer(text):
            exported.setdefault(match.group(1), path)
    callers = [f for f in source if withhold is None or f.name != withhold]
    texts = [f.read_text(encoding="utf-8") for f in callers]
    bodies = "\n".join(texts)
    indirect: set[str] = set()
    for text in texts:
        if not blind_to_tables:
            indirect |= _table_mounted(text)
        if not blind_to_aliases:
            indirect |= _alias_mounted(text)
    return sorted(
        (name, str(path.relative_to(SRC)))
        for name, path in exported.items()
        if name not in indirect and not re.search(rf"<{name}[\s/>]", bodies)
    )


def run():
    if not SRC.exists():
        return "SKIP", "nothing to check — 07-frontend/src not present"

    unmounted = _unmounted()
    count = len(unmounted)

    # ── SELF-TEST: does this gate BITE? ──────────────────────────────────
    # Withhold `App.tsx` — the router — and the whole workflow kit must appear,
    # because App.tsx is what renders `ImportWorkflowPage` and that page is what
    # renders the kit. This is the branch as it stood before DEF-520 was fixed.
    without_router = _unmounted(withhold="App.tsx")
    bites = len(without_router) - count
    if bites <= 0:
        return "FAIL", (
            "SELF-TEST FAILED: withholding App.tsx changed nothing, so this gate "
            "cannot tell a mounted component from an unmounted one"
        )

    # ── SELF-TEST 2 (DEF-2735, law 7): does the INDIRECTION clause bite? ──
    # The clause added on 2026-09-01 can only ever REMOVE findings, so a green
    # run proves nothing about it — a clause that matched nothing at all would
    # look identical. Run the detector blind to lookup tables: the components
    # that only a table mounts must come back, or the clause is silently doing
    # no work and the next dead icon walks through it.
    blind = _unmounted(blind_to_tables=True)
    table_only = sorted({name for name, _ in blind} - {name for name, _ in unmounted})
    if not table_only:
        return "FAIL", (
            "SELF-TEST FAILED: switching off the lookup-table clause (DEF-2735) changed "
            "nothing, so nothing in this repo is mounted that way and the clause is a "
            "widening that buys no case — delete it rather than carry a check that "
            "cannot be shown to bite"
        )

    # ── SELF-TEST 3 (DEF-GOV-4009, law 7): does the ALIAS clause bite? ───
    # Same argument as self-test 2, for the clause added on 2026-09-05: run the
    # detector blind to import aliases and the alias-only mounts must come back.
    # If none does, nothing in this repo is mounted that way and the clause is a
    # widening that buys no case.
    alias_blind = _unmounted(blind_to_aliases=True)
    alias_only = sorted({name for name, _ in alias_blind} - {name for name, _ in unmounted})
    if not alias_only:
        return "FAIL", (
            "SELF-TEST FAILED: switching off the import-alias clause (DEF-GOV-4009) changed "
            "nothing, so nothing in this repo is rendered under an alias and the clause is a "
            "widening that buys no case — delete it rather than carry a check that "
            "cannot be shown to bite"
        )

    if count > UNMOUNTED_BASELINE:
        newly = [f"{name} ({path})" for name, path in unmounted][:4]
        return "FAIL", (
            f"unmounted components ROSE by {count - UNMOUNTED_BASELINE}: {count} now, "
            f"{UNMOUNTED_BASELINE} baselined. A component nothing renders is dead UI — it "
            f"compiles, its own tests pass, and the feature does not exist (hard-won law 2, "
            f"DEF-520). Now: {', '.join(newly)}"
        )
    if count < UNMOUNTED_BASELINE:
        return "FAIL", (
            f"unmounted components FELL to {count} from {UNMOUNTED_BASELINE} — lower the "
            f"baseline in the SAME commit, or the ratchet keeps claiming debt already paid off"
        )

    return "PASS", (
        f"{count} component(s) rendered by nothing (at the baseline of {UNMOUNTED_BASELINE}), "
        f"read from the working tree not the index (DEF-CWP-3882); self-test: withholding "
        f"App.tsx surfaces {bites} more, switching off the lookup-table clause surfaces "
        f"{len(table_only)} ({', '.join(table_only)}) and switching off the import-alias "
        f"clause surfaces {len(alias_only)} ({', '.join(alias_only)}), so all three checks bite"
    )


if __name__ == "__main__":
    status, detail = run()
    print(f"{status}: {detail}")
    raise SystemExit(0 if status != "FAIL" else 1)

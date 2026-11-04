#!/usr/bin/env python3
"""G38 — a STATED ABSENCE cites the row that will kill it.

WHY THIS GATE EXISTS (DEF-445 · DEF-421 · DEF-467..473, 2026-08-21)
-------------------------------------------------------------------
The plan wizard's Deposits panel told staff, for weeks:

    "the category list is set up in the Accounts module, which is not built
     yet. No deposit is saved with this plan."

The Accounts module was built. That very wizard already RECEIVED the category
list and used it on step 1. The sentence was found by the Product Owner walking
the screen — *"Deposite unable to add"* — and by nothing else in this repo.

DEF-421 was the same shape one screen earlier, and its fix corrected only the
four notes that named *customer class* by name. DEF-445 survived because it
phrased the identical false premise differently. A sweep on 2026-08-21 then
found nine more across five modules, including one screen whose overview panel
said bills had no read endpoint while the SAME FILE's other tab read that
endpoint.

**Every gate in this repo is blind to it, and the reason is worth stating:**

  * `tsc` cannot type-check a claim about the world.
  * The component's own tests assert the panel RENDERS — and it does. Correct
    behaviour over an incorrect statement is invisible.
  * `G13` catches an unwired PROP, not a stale sentence.
  * `G23` counts deferral MARKS in Lifecycle trailers, not prose on screen.
  * A grep for the last false string never reaches the next one, because the
    next author writes the same false premise in different words. That is
    exactly how DEF-445 escaped DEF-421's fix.

Hard-won law 1 says a comment claiming a guarantee is not the guarantee. This
is the same law pointed the other way: **a screen claiming an ABSENCE is not
the absence**, and nothing re-checks one when the thing it waits for ships in
somebody else's lane.

WHAT THIS GATE CHECKS
---------------------
Not the truth of the sentence — no source-reading check can know that, and a
gate that pretends to would be worse than none (DEF-182). It checks the ONE
property that makes the sentence self-expiring:

    every `<ArrivesWith>` / `<ArrivesWithField>` passes `tracks="<ID>"`,
    naming the DEF or OQ that keeps the absence open.

With an id, closing that row is what points a reader at every screen still
claiming it. Without one, the note has no expiry and nothing notices — which
is DEF-445's prevention column, verbatim:

    "a stated absence should cite the OQ or DEF that keeps it open, so it
     expires when that closes — a note with no id behind it can outlive its
     reason indefinitely and nothing notices."

⚠ THE ID IS A `data-` ATTRIBUTE AND MUST NOT BE IN THE SENTENCE. The PO ruled
on 2026-08-19 that our internal ids do not belong on a customer's screen
(DEF-332), and `DEF-445` means nothing to a billing clerk at a two-person
utility. `ArrivesWith` renders `tracks` as `data-tracks`, invisible to the
reader and to a screen reader, present for us. The first fix of DEF-445 put the
id INSIDE the copy; this gate exists partly so the next one does not.

RATCHETED, NOT ALL-OR-NOTHING
-----------------------------
There are 96 of these notes and most predate the mechanism. Requiring the prop
in the TYPE would break every call site in one commit, and a change that big
gets a blanket id typed into it — the mechanism dies on arrival and the gate
measures a field nobody meant. So the prop is optional and the BASELINE below
is the count that carried no id on the day this was written. It may only fall.
A new note must carry one; an old note is a debt somebody has to price.

⚠ AND LOWERING IT IS PART OF THE FIX. If the count drops and the baseline does
not, the gate goes red and says so — a ratchet that never tightens is a number
nobody reads, which is the failure `surface_debt.txt` records about itself.

PROVED RED, TWICE
-----------------
1. Against the tree BEFORE the Wave B sweep, with `UNTRACKED_BASELINE = 84`:
   `FAIL: 96 stated absence(s) cite nothing (max 84)`.
2. With `tracks` deleted from `ArrivesWith`'s props — the way this mechanism
   would really be lost — the gate reports every call site as untracked and the
   count rises past the baseline. It cannot go green on a rendered-but-dropped
   attribute, which is the DEF-337/G37 lesson: check the thing that carries the
   guarantee, not a string that happens to appear in the file.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "07-frontend" / "src"

#: The components that RENDER a stated absence. Both take `tracks`.
NOTE_ELEMENTS = ("ArrivesWith", "ArrivesWithField")

#: Notes that still cite nothing, on 2026-08-21 after the Wave B sweep. THIS
#: NUMBER MAY ONLY FALL. It was 96 before the sweep; the sweep tracked twelve.
# 2026-08-21 · 84 -> 77 (DEF-490). The gate asked for this in its own output
# and nobody held it for a day. That is the DEF-490 lesson exactly: a gate
# that reports red either way stops being read, and a ratchet only ratchets
# when somebody turns it. Seven notes gained an id in the Wave B sweep.
# 2026-08-21 · 77 -> 76 (Wave G, CR-013 part 5). PLN-03 step 6 and PLN-02's
# Discounts tab each carried an untracked "not built yet" note while `OQ-300`
# was open. The question CLOSED, the step now binds, and the notes went with
# it — so the gain is real rather than a re-wording, and it is held here in the
# same commit that earned it rather than left for the next lane to notice.
# 2026-08-24 · 76 -> 74 (CR-030 W1d). `ImportAccountsWizard.tsx` is DELETED:
# the account import moved onto the one runner (BR-MET-096), G40 reported the
# old modal as newly unmounted, and it went. Its two untracked "not built yet"
# notes went with the file, so this is a real gain rather than a re-wording —
# and it is held in the same commit that earned it, per DEF-490.
# 2026-08-24 · 74 -> 72 (CR-030/031 W5 merge). The gain was NOT earned here and
# it was not earned today: `8c3a0600` deleted the two "Waiting on …" panels from
# the Accounts tab on a PO ruling ("Delete both boxes entirely"), and their two
# untracked notes went with them. That commit did not turn the ratchet, and
# THIRTY-ONE commits then passed at 72 with the baseline reading 74 — each of
# them running a gate that could not have caught a regression back up to 74.
# Bisected across 80 commits to name the source rather than assert one: 74 at
# `b0b25f0a`, 72 at `8c3a0600` and at every commit since.
# ⚠ THE LESSON IS ABOUT THE GATE, NOT THAT COMMIT. G38 reports DOWN-from-baseline
# as a FAIL precisely so the turn cannot be deferred — and it was deferred anyway,
# thirty-one times, because a lane reading "FAIL … DOWN from 74" hears good news
# and moves on. A slack ratchet is not a smaller ratchet; over those 31 commits it
# was NO ratchet, since two new untracked notes could have landed silently.
# ⚠ TWO LANES EACH LOWERED THIS BY ONE, FOR DIFFERENT ABSENCES, AND EACH WROTE
# 72 → 71 (merged 2026-08-27). At the merge I reasoned that two real decrements
# must land two below 72 and set this to 70. **THE GATE MEASURED 71** — verbatim:
# *"87 stated absence(s); 16 cite a DEF or OQ, 71 cite nothing (baseline 70).
# 1 more than the baseline."* So the figure here is the MEASUREMENT, not the
# arithmetic, and the arithmetic is written down because it was wrong: two
# comments each claiming the same decrement do not add up to two decrements, and
# whichever way that happened, the merged tree is what counts. Recorded as two
# lines anyway, because a ratchet whose history says "72 → 71" twice cannot be
# audited by reading it.
#
# 2026-08-27 · DEF-899. `metering.read.compliance.uploadedByIdOnly` — *"The stamp
# stores the uploader's internal id; their name is not served with it"* — was
# rendered on S29 and again on S28, and it was TRUE, which is why it survived.
# BR-MET-163 serves the name, so the absence no longer exists and the sentence is
# deleted from all eleven catalogues with it. PAID OFF, not reclassified.
#
# 2026-08-27 · BR-BIL-160 / OQ-530. The opening-balance lane paid off its own,
# independently, in the same hour.
#
# 2026-08-27 · 72 → 71 (DEF-899). One untracked stated absence is PAID OFF, not
# reclassified: `metering.read.compliance.uploadedByIdOnly` — *"The stamp stores
# the uploader's internal id; their name is not served with it"* — was rendered on
# S29 and again on S28, and it was TRUE, which is why it survived. BR-MET-163
# serves the name, so the absence it described no longer exists and the sentence
# is deleted from all eleven catalogues with it.
# 2026-08-27 · 71 → 69 (CR-043 finding 10). ⚠ **THIS DROP IS A MOVE, NOT A
# PAYMENT, AND THE DISTINCTION IS THE ONE THIS GATE CANNOT SEE.** The two
# `ArrivesWith` panels under the bills list — *Filters that arrive later* and
# *Export and column choices* — were DELETED on a PO ruling (2026-08-27,
# verbatim: *"you ahve to remove - Filters that arrive later … + Export and
# column choices"*). Neither feature was built. Scoring this the same as
# building them is precisely what this gate does, because a deleted note and a
# paid debt look identical from here.
# So the two absences they stated moved into the register in the same commit:
# `DEF-1062` (no cycle / billing-run / date-range filter) and `DEF-1063` (no
# export, no remembered column choices). **If either row is ever deleted
# without the feature landing, this baseline is lying by two.**
# The ruling that permits the move is narrow and is worth restating here,
# because a lane reading only the first half will delete the wrong things: an
# UNBUILT FEATURE is stated in the register; a SECTION WITH NO DATA IN IT still
# says so on screen (*"if there are nothing to report we have to show nothing to
# report"*). This gate counts the first kind, and only the first kind.
# ⚠ **AND THE MERGED FIGURE IS 69, WHICH IS AGAIN THE MEASUREMENT AND NOT THE
# ARITHMETIC.** Their side stood at 71 and mine at 69, and 71 − 2 happens to be
# 69 — but that agreement is a coincidence worth NOT relying on, for exactly the
# reason the note above this one gives: two lanes' decrements do not compose by
# addition. The tree was measured after the merge and reported *"85 stated
# absence(s); 16 cite a DEF or OQ, 69 cite nothing"*. That is the number.
# ⚠ **66 -> 65 ON 2026-09-03, AND THE FALL IS BANKED IN THE SAME COMMIT
# AS THE FIX (CR-059 CS-40, DEF-3504).** The S33 Record payments tab carried an
# `ArrivesWith` reading *"the list already answers a posted-date range and a
# cleared-date range, and this page cannot yet offer them: the shared filter bar
# renders option lists only"*. That was true when it was written and stopped
# being true in somebody else's lane: `TableFilterConfig` grew a `dateRange`
# descriptor, `FilterBar` draws it, and `paymentsFilters` now declares two
# ranges on the server's own param names. **The panel is deleted and its two
# keys are retired from all eleven catalogues** rather than left as dead
# entries, and `PaymentsPage.test` asserts they no longer resolve so the copy
# cannot come back quietly.
#
# ⚠ **THIS IS THE CASE THE GATE'S OWN HEADER IS ABOUT, ARRIVING EXACTLY AS
# IT PREDICTED.** *"A screen claiming an ABSENCE is not the absence, and nothing
# re-checks one when the thing it waits for ships in somebody else's lane."*
# Nothing did re-check it -- the Product Owner did, by walking the deployed
# build and saying *"I cannot filter payment by date"*. The note carried no
# `tracks` id, which is why it was in this 66 rather than expiring on its own;
# a note that had cited `DEF-3504` would have been pointed at the moment that
# row closed. That is the whole argument for the prop, made by the one note
# that did not carry it.
# ⚠ 58 → 54 on 2026-09-17, TIGHTENED (never widened), on the gate's own
# instruction: *"DOWN from 58 — lower UNTRACKED_BASELINE to 54 in this file
# to hold the gain. A ratchet that never tightens is a number nobody reads."*
# Four uncited absence sentences left the Plans & Rates wizard when
# `DEF-RAT-5719` replaced three over-long verdict strings and stopped
# rendering a fourth once per unmeasured figure.
# ⚠ 54 → 52 on 2026-09-19, TIGHTENED (never widened), on the gate's
# own instruction: *"DOWN from 54 — lower UNTRACKED_BASELINE to 52 in this
# file to hold the gain."* Two uncited absence notes left the CHARGE CODE
# wizard when this lane deleted them: the internal-description field, whose
# whole content was *"There is one description column today, so a staff-only
# one is not offered"*, and step 3's sample line, which spent thirty-one words
# saying the server formats amounts. Both were RATIONALE — B14 rule 33 puts
# that kind at ZERO words on screen — so neither was shortened; the screen
# stopped saying them at all, and the sample line shows the amount instead.
# ⚠ 52 → 47 on 2026-09-24, TIGHTENED (never widened), on the gate's own
# instruction: *"DOWN from 52 — lower UNTRACKED_BASELINE to 47 in this file to
# hold the gain."* **FOUR OF THE FIVE WERE ALREADY EARNED AT THE BRANCH TIP AND
# NOBODY HELD THEM** — measured at `a464877a0`, the gate read *"57 stated
# absence(s); 9 cite a DEF or OQ, 48 cite nothing"*, so the ratchet had been
# slack by four before this lane started. **The fifth is this lane's**
# (`DEF-CUS-6365`): the move-in review's *What this move-in will not write*
# panel, 60 words of RATIONALE citing nothing, deleted rather than shortened
# because B14 rule 33 gives that kind zero words on screen. The screen's other
# absence panel went too — *Nothing is delivered to the customer*, which DID
# cite `DEF-266`, which is why the CITED count moves 9 → 8 in the same commit
# and the total 57 → 55.
# ⚠ 47 → 44 on 2026-09-25, TIGHTENED (never widened), on the gate's own
# instruction: *"DOWN from 47 — lower UNTRACKED_BASELINE to 44 in this file to
# hold the gain."* **ALL THREE WERE ALREADY EARNED AT THE BRANCH TIP AND NOBODY
# HELD THEM** — none is this lane's. Measured file by file against the commit
# that set 47 (`73a646042`): the MOVE-OUT WIZARD went 2 → 0 at `2b5c1b4c6`
# (`DEF-CUS-6550`, `DEF-CUS-6551`, 2026-09-24 — the draft-bill refusal cut from
# 63 words to 10), and TAXES & REMITTANCE went 2 → 1 at `7f6cbae0a`
# (2026-09-24, Finance `P4.12`/`P4.11`/`P4.8`, when Close & export became two
# screens and five refusal sentences were deleted).
#
# ⚠⚠ **THIS RATCHET FAILS ON AN IMPROVEMENT, AND A GOOD DAY LOOKS EXACTLY LIKE
# A BAD ONE.** G38 is RED both when the count RISES and when it FALLS — the
# fall is the gate asking to be tightened, not a defect. **READ THE DETAIL
# LINE BEFORE TOUCHING THIS NUMBER.** It says `DOWN from N` on a fall and
# `N more than the baseline` on a rise, and the ONLY lawful response to a fall
# is to LOWER this integer to the measured count. **Never raise it to make the
# red go away**: that re-admits every absence the fall just removed, silently,
# and the next reader inherits a ratchet that has stopped ratcheting. This
# happened on the way to 47 — four of those five had been earned at the tip and
# held by nobody — and it happened again on the way to 44.
# 2026-10-01 · 42 -> 41: CR-156-BRC10 wave B rewrote CHG-02 and its untracked
# stated absence went with the old wizard.
# 2026-10-05 · 37 -> 36: CR-171-BRC10 P2.01 (lane MVI-LIST-UI) — the Move-ins
# list stopped printing its list-level absences under the table (S3/S4: the
# footnotes are gone and the rows they excused are rows now).
# 2026-10-24 · 36 -> 31: pre-release cleanup lane — measured 31 uncited
# stated absences on the branch tip (39 in all, 8 citing a DEF or OQ);
# ratcheted down only, to bank the fall.
UNTRACKED_BASELINE = 31
# ⚠ **LOWERED 44 → 42 ON 2026-09-30 (gate triage T6) — earned at the tip, held
# by nobody.** G38 read `DOWN from 44` from 3ede9b993 (2026-09-29, the One-time
# bill fixes, DEF-BIL-5252 and siblings) onward. The number is the measurement.
# ⚠ **LOWERED 65 → 58 ON 2026-09-15 to hold a gain SEVEN lanes' work earned and
# ONE of them was this one's.** `CR-094-BRC01` lane G removed
# `applicant.drivers_licence_absence` from the service-request payload in the
# commit that made it false — the PO ruled the driving licence capturable that
# day and it landed the same day (`BR-CUS-092`(a) finished). The other six came
# off the same wave's other lanes. **The number is the MEASUREMENT, not a claim
# about who earned it**: a ratchet banks whatever the tree actually holds, and
# leaving it at 65 would have let the next seven absences arrive for free.
# ⚠ Its sibling `applicant.date_of_birth_absence` went in the same commit and is
# NOT part of this drop, because it cited `DEF-638` and was therefore in the
# TRACKED bucket all along — which is the distinction this gate exists to make.
# ⚠ **LOWERED 67 → 66 ON 2026-09-01 (`DEF-3030`, CR-059 tasks 16 and 18), AND IT
# IS THE FIRST TIME AN ABSENCE CAME OFF THIS COUNT BECAUSE IT WAS *FALSE*
# RATHER THAN BECAUSE THE FEATURE LANDED UNDER IT.** S33's *Row and bulk
# actions* panel told a clerk, in eleven languages, that reversing a payment and
# issuing a refund *"are not built"* and that two decisions the Product Owner
# *"has not made yet"* were open. Both doors landed on 2026-09-01 (CR-059 tasks
# 15 and 17); the two questions were ruled on 2026-08-11 (`OQ-132`) and
# 2026-08-12 (`OQ-133`). The panel would have sat on the same page as the new
# Reverse control, contradicting it.
#
# ⚠ **AND IT IS THE CASE THIS GATE WAS ALWAYS MEANT TO CATCH AND CANNOT.** An
# untracked absence has no expiry, so nothing goes red the day the route it was
# waiting for is mounted — `DEF-3030`'s `escape_reason` says exactly that. This
# gate counts them; only a person reading the sentence beside the code can tell
# that one has stopped being true. The two panels left on that page each name
# what they wait for.
#
# The gate asked for this in its own words: *"DOWN from 67 — lower
# UNTRACKED_BASELINE to 66 in this file to hold the gain."* Measured after the
# deletion, not derived from it: *"81 stated absence(s); 15 cite a DEF or OQ, 66
# cite nothing"*.
#
# ⚠ **LOWERED 69 → 67 ON 2026-08-31 (CR-052 W3/W4 tasks 13 and 14), AND IT IS A
# MEASUREMENT AGAIN.** The gate asked for it in its own words — *"DOWN from 69 —
# lower UNTRACKED_BASELINE to 67 in this file to hold the gain. A ratchet that
# never tightens is a number nobody reads."* The two that came off are the two
# this repo had been telling itself about for months: the bill run's
# `one_template_pin_for_the_whole_run` notice (withdrawn the same commit the
# per-account resolution landed, task 13) and the delivery seam's "the ELECTION
# cannot be read on this deployment" (the two columns exist, task 14). Neither
# was deleted to move this number: each was deleted because it had stopped
# being true, which is hard-won law 1, and the tree was re-measured afterwards.
#
# ⚠ **RE-MEASURED 2026-08-31 BY A SECOND LANE (CR-051 W3/W4) AND IT IS STILL
# 67 — WHICH IS THE WHOLE POINT OF THE NOTE ABOVE.** That lane also removed two
# untracked absences: the *Charges to add* tab's empty table now cites
# `DEF-2596` (nothing on this server produces either of its two cases) and the
# estimate refusal cites `DEF-2597` (no screen sent the quantity the route has
# always accepted). **67 − 2 is not 65 here**, and the file's own warning says
# why: two lanes' decrements do not compose by addition, and the number is
# whatever the gate reports on the merged tree. It reported *"82 stated
# absence(s); 15 cite a DEF or OQ, 67 cite nothing"*. The baseline stays 67
# because the gate was RUN, not because the arithmetic worked out.

#: A DEF row or an open question. Nothing else is an expiry: a BR-id is a rule
#: that is CONFIRMED and will never "close", and a US-id is a story that may
#: ship without anyone revisiting the screen that waits on it.
TRACKS_ID = re.compile(r'tracks=(?:"|\{")(DEF-(?:[A-Z]{3}-)?\d+|OQ-(?:[A-Z]{3}-)?\d+)(?:"|"\})')

OPEN_TAG = re.compile(r"<(" + "|".join(NOTE_ELEMENTS) + r")\b")


def _strip_comments(text: str) -> str:
    """Blank out comments, so PROSE ABOUT this rule never satisfies or trips it.

    ⚠ NOT FUSSINESS — documenting an escape hatch by example tripped G31 from a
    comment, twice, and G37 carries the same guard for the same reason.
    """
    # ⚠ **LINE COMMENTS GO FIRST — DEF-741.** A `//` line that spells a path
    # with a star in it (`// see src/i18n/locales/*.json`) contains `/*`, so
    # stripping BLOCK first opens a comment there and closes it at the next
    # `*/` anywhere below, blanking every line between. Measured 2026-08-26:
    # 3,620 bytes of real code across eight files. The gate reports PASS on
    # what it cannot see, which is the failure mode this repo keeps hitting.
    text = re.sub(r"//[^\n]*", lambda m: " " * len(m.group(0)), text)
    return re.sub(r"/\*.*?\*/", lambda m: re.sub(r"\S", " ", m.group(0)), text, flags=re.S)


def _element_body(text: str, start: int) -> str:
    """The attributes of ONE JSX element, from `<Tag` to its closing `>`.

    Read by depth over `{}` rather than by finding the next `>`, because a
    perfectly ordinary prop — `message={t("x", { defaultValue: y > 0 })}` —
    contains one. A naive scan truncates the element and reports a tracked note
    as untracked, which is a gate lying in the direction that costs a lane an
    hour.
    """
    depth = 0
    i = start
    while i < len(text):
        char = text[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == ">" and depth == 0:
            return text[start:i]
        i += 1
    return text[start:]


def run() -> tuple[str, str]:
    untracked: list[str] = []
    total = 0
    tracked = 0

    for path in sorted(SRC.rglob("*.tsx")):
        rel = str(path.relative_to(SRC))
        if rel.endswith(".test.tsx"):
            continue
        text = _strip_comments(path.read_text("utf-8", errors="replace"))
        for match in OPEN_TAG.finditer(text):
            total += 1
            body = _element_body(text, match.start())
            line = text[: match.start()].count("\n") + 1
            if TRACKS_ID.search(body) is not None:
                tracked += 1
            else:
                untracked.append(f"{rel}:{line} <{match.group(1)}>")

    note = (
        f"{total} stated absence(s); {tracked} cite a DEF or OQ, "
        f"{len(untracked)} cite nothing (baseline {UNTRACKED_BASELINE})"
    )

    if len(untracked) > UNTRACKED_BASELINE:
        added = len(untracked) - UNTRACKED_BASELINE
        return (
            "FAIL",
            f"{note}. {added} more than the baseline. A note with no id behind it "
            f"outlives its reason and nothing notices (DEF-445). Pass "
            f'tracks="DEF-###" or tracks="OQ-###" — the row that will close it. '
            f"First: {untracked[0]}",
        )
    if len(untracked) < UNTRACKED_BASELINE:
        return (
            "FAIL",
            f"{note}. DOWN from {UNTRACKED_BASELINE} — lower UNTRACKED_BASELINE to "
            f"{len(untracked)} in this file to hold the gain. A ratchet that never "
            f"tightens is a number nobody reads.",
        )
    return "PASS", note


def main() -> int:
    status, message = run()
    print(f"{status}: {message}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

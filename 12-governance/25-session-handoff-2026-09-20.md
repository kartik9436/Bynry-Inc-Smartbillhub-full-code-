# 25 · Session handoff — 2026-09-20, overnight

**Written because this session may end mid-flight and the next one starts in a different chat.**
Hard-won law 10's test is not *"was a decision made"* but *"would the next agent, with only the
repo, build the same thing?"* Six lanes were still running when this was written, so everything
below is here so nobody reconstructs it from a conversation that no longer exists.

⚠ **THIS FILE IS A SNAPSHOT AND IT ROTS.** True at `ed11c1b64`, version `2.317.1`, branch
`claude/kind-wozniak-rl0uzt`. **The decision log, the registers and the execution plans outrank
it the moment they disagree.** Read it once for orientation, then work from the live files.

⚠ **THE SESSION DIED TWICE TONIGHT — ONCE TO A CONTAINER RESTART, ONCE TO A USAGE LIMIT.** Both
killed every lane. That is why the push discipline in §4 is stated as a rule rather than a
preference, and why §2's rulings were written down by the session that heard them instead of
being left with the lanes that were told to record them.

---

## 0 · Do these five things before you read anything else

1. **`./10-scripts/check_head_current.sh`** — first command, before reading a file or believing a
   grep. Local HEAD silently rewinds.
2. **If the tree differs from the tip, DO NOT assume it is only the pointer.** Tonight the shared
   tree twice held a **loaded revert** — once 29 files, once **2,554 lines of pure deletion**
   across nine files including four test files that were simply absent and a lane's freshly
   pushed audit. `git status` was clean for the untracked half. See §4.
3. **`ls 10-scripts/`** before writing any helper that touches a shared file. Lanes keep
   rewriting tools that already exist there.
4. **Read `12-governance/02-decision-log.md`, the section
   `## 2026-09-20 · SEVEN PO RATIFICATIONS FROM ONE SITTING`.** That is the spec every running
   lane is building to. It is nine subsections and it supersedes any paraphrase.
5. **Read `04-docs/02-decisions/12-engineering-plan.md` Addendum r11 step 0**, then the four
   registers. Rulings landed hourly today.

---

## 1 · Where the work stands

| | State |
|---|---|
| Branch | `claude/kind-wozniak-rl0uzt` |
| Version | `2.319.0` |
| Tip when written | `ed11c1b64`; **closed out at `5af03aa06`, 94 commits on the day** |
| Commits today | **65** |
| Lanes in flight | **NONE — all seven finished.** See §2a for what each left owing |

---

## 2 · The six lanes in flight, and what each owns

**Every one is building to a numbered subsection of the 2026-09-20 decision-log entry.** If a
lane is gone when you read this, restart it from that subsection — NOT from this table, which is
a summary.

| Lane | Spec | Owns these files — do not edit them from elsewhere | State |
|---|---|---|---|
| **Request action bar** | §1 + §8 | `ServiceRequestDetailPage.tsx` | ⏳ running |
| ~~**Navigation**~~ | §8 | — | ✅ **DONE `2.317.2`** — the request number opens the request; the move record exits to its own tab |
| **Transfer step 2** | — | `TransferWizard.tsx` | ⏳ running |
| ~~**New request form**~~ | §3 | — | ✅ **DONE `2.318.1`** — a draft saves from a name alone; the grid pairs and keeps rule 39's rhythm |
| **Parked panel** | §5 | `parkedDrafts.tsx`, `move_reads.py` windows | ⏳ running — Transfers and Disconnects already landed |
| **Move-out record** | §6 + §7 | `MoveRecordPage.tsx` (the rest of it) | ⏳ running — the audit has landed |

**Already landed and pushed today — do NOT redo:**
the Accounts header across ten tabs · the Transfers tab rebuild · the transfer record page ·
final-bill proration (`$18.50 → $7.40` on a 12-of-30-day close) · the landlord warning
(`BR-CUS-1082` reversed to warn-and-allow) · the Approve dialog's evidence-gated radios ·
the request number as a working door · Park offered from Submitted only · the Disconnects and
Transfers lists carrying their own parked drafts · the move-out record audited against the page
it is actually drawn on.

⚠ **ONE LANE'S SCOPE WAS SPLIT AND ONE PAIR WAS MERGED, DELIBERATELY.** The request-detail work
had picked up five PO asks in one PR — it is now two lanes. The move-out audit and rebuild were
two lanes — they are one, with the audit pushed BEFORE any build, so the measured comparison
survives a death the build does not.

⚠ **THE APPROVE DIALOG LANE ALSO FINISHED** (`2.317.1`): each outcome radio now carries its own
verdict, greyed with the server's own sentence as visible text rather than a hover title, and the
disconnect branch is untouched and pinned by a test because `OQ-356` is open.

⚠ **TWO CORRECTIONS THIS SESSION MADE TO ITS OWN BRIEFS, BOTH CAUGHT BY LANES:**
**(a) The backend's `QUEUE_*` values are NOT tab slugs.** They are underscored (`move_ins`,
`new_connects`); the front end's `?tab=` reads `ACCOUNTS_TAB_IDS`, which is hyphenated
(`move-ins`, `move-outs`), and **no translator exists anywhere**. Route through
`parkedHomePath()` — the map park, discard and resume already share — bridging from
`JOB_SHAPES["kind"]`, where four of five values are already its keys and only `connection` vs
`new_connect` needs a named case.
**(b) The drawing draws the request number as plain text with a labelled `↗ Open` button**
(p085, rendered at scale 6). The product departed from it deliberately: B14 rule 15 makes our row
action an unlabelled eye, and the PO had already ruled the identical complaint one list over
(*"can you imporve the interaction design"*). Four of six registers already linked their
reference; Requests was the odd one out. The divergence is stamped at the call site.

---

## 2a · ALL SEVEN LANES FINISHED. WHAT THEY LEFT OWING

**Every lane pushed.** Nothing was lost to the two deaths. What follows is what is NOT done,
because that is the only part a next session needs.

| Owed | Where |
|---|---|
| **KPI tiles, the `Final read` row, and TABS** on the move-out record | ratified in §6, **not built** — the action grid took the time. Listed in the conformance file's §5 and §7.2 |
| **The back-link WORDING** — four keys still render `The register` to four destinations | `DEF-CUS-5997`. The DESTINATIONS are all fixed; only the word is vague |
| **A browser walk of the parked-drafts change** | the click-through scripts are re-pointed but were never run against a running app |
| **A browser walk of the action bar** | its dom tests mount the real screen at the real address, which is the strongest proof available without a stack |

⚠ **THE BRANCH IS MERGE-BLOCKED AND WAS BEFORE TONIGHT.** `run_gates --changed` reports
**70 PASS · 55 FAIL · 5 SKIP**. None of the 55 belongs to tonight's lanes — one lane inspected
every one rather than sampling. **Yesterday's record (`10-scripts/gates/last-run.json`, written
2026-09-19 at `ea168efbc389`) reads 75 PASS · 53 FAIL · 2 SKIP**, so a day of heavy work moved
failures **53 → 55, net two worse**.

⚠ **AND THAT COMPARISON ALMOST COULD NOT BE MADE, FOR A STRUCTURAL REASON WORTH FIXING.**
`last-run.json` is gitignored by `10-scripts/gates/.gitignore:13` — deliberately, as a
per-machine record; the runner's own words are *"the next run ON THIS MACHINE will compare
against it"*. **But every lane works in its own `git worktree`, and an untracked file does not
exist in a fresh worktree.** So a lane running the gates always sees *"NOTHING TO COMPARE"* and
truthfully reports it, while the shared tree holds a perfectly good baseline. The comparison can
essentially never run where the work happens. **The durable fix is not to commit the 78 KB blob
(law 5 forbids committing a generated file) but to record the COUNT AND DATE in a tracked file
— three numbers a next session can actually use.**

### Two live defects a next session will trip over

* **`DEF-CUS-6011` — A `DataTable` CELL CANNOT HOLD STATE, AND THIS OWNS EVERY TABLE IN THE
  PRODUCT.** `columnDefs` is rebuilt on every render, so `flexRender` hands React a new component
  type and the whole cell subtree remounts — which destroys a `useState` inside a cell by the very
  re-render that setting it caused. The Discard button set `confirming`, the tab re-rendered, the
  component came back `false`, **and the dialog never opened**. Worked around by hoisting the
  dialog to the tab; `DataTable` itself is UNTOUCHED, so the next lane to put state in a cell hits
  it again. **The real fix is memoising `columnDefs`.** Nothing had ever put state in a cell
  before, so the trap had nothing to catch: remounting a STATELESS cell produces identical output.
* **`DEF-CUS-6012`** — `MoveOutsTab.tsx` gained a `draftState` column and its two hand-written
  callers were not updated: 4 failing tests and **the only two `tsc` errors in the front end**.

### The defect register's duplicate ids — see §4(d), which THIS FILE CORRECTS

Three lanes reported it and all three stopped at *"I would be guessing"*. That is disproved:
it is **three rows each, six different defects**, and every citation says in prose which one it
means. The repair is built and proved and needs `ALLOW_REGISTER_DELETIONS=1`.

---

## 3 · What needs the Product Owner, ranked

**1 · A final bill covering 43 days charges ONE month's base charge. One, or 1.4?**
Measured on the beta 2026-09-20: every brazosbend account's closing window is 1 Aug – 12 Sep,
43 days against a 31-day cycle. `gather._service_days` ends `return max(0, min(cycle_days,
days))`, so the factor can never exceed 1. **B4.3 is written for a PARTIAL period and says
nothing about an over-long one, so no signed rule covers it either way.** Filed as
`DEF-BIL-5986` with the figures. It may well be deliberate — a bill covering more than a cycle
is arguably a back-bill's job, and `backbill.price_day_weighted` already weights day by day.
**Do not guess: it is a live money figure on every account in the beta.**

**2 · Should `A disconnect` be greyed when the applicant holds no account anywhere?**
`OQ-356`, OPEN. `_verdict_for` returns `possible` for disconnect on every evidence state and the
code says by name that this is knowingly incomplete. A recommendation was put to the PO — grey
it using the same test transfer uses — and **no ruling was given.** A test now pins the current
behaviour so a later lane cannot quietly resolve it by choosing a value.

**3 · On a move-in, should a clerk be able to OPEN a document, or is seeing it enough?**
`DEF-CUS-6002`. The move-in shows each document's file name, what it proves and where it stands
— *Driving licence.pdf · Who they are · Verified* — and holds **zero clickable controls**, while
the server has had a download endpoint all along and the request's own tab uses it. **The
ratified words were "Document links or details", and the details ARE there**, so the absent link
may be no promise at all. A download control here is also a second door onto stored documents
with its own authorisation to get right.

---

## 4 · Traps that are live right now

**(a) THE SHARED TREE HELD A LOADED REVERT TWICE TONIGHT.** Both times `git status` looked
survivable and the damage was in what had been LEFT BEHIND. The procedure that found and fixed
it, in order:
  1. `git diff --name-only <tip>` = everything wrong · `git diff --name-only HEAD` = what a lane
     has touched. **The set difference is the stale half, and that half is safe to restore
     precisely because nobody has touched it.**
  2. Restore by WRITING the tip's bytes — `git show <tip>:<path> > <path>` — never
     `git checkout`, which law 11 bans. **Re-set the mode from `git ls-tree <tip>` in the same
     loop**: a shell redirect drops the executable bit every time, and a mode-only difference is
     invisible to every content check.
  3. ⚠ **THE DIFF LIES AFTERWARDS.** Five files still reported as deleted once their bytes were
     correct, because a file created AFTER the stale HEAD is untracked and `git diff` keeps
     calling it missing. **Verify byte-for-byte** (`diff <(git show <tip>:<path>) <path>`), not
     by reading the diff.
  4. For a file both touched AND differing, the deciding test is direction: **pure deletions with
     zero insertions is a REVERT and must be restored; additions are live work and must be left.**
     Both shared registers tonight were pure subtraction — 35 decision-log lines and 3 defect
     rows, zero live work — so restoring cost nothing and leaving them loaded would have cost
     seven lanes.

**(b) DEFECT IDS COLLIDED SIX TIMES ACROSS FOUR LANES IN ONE NIGHT.** Every one was caught, and
only because a lane re-derived from the REMOTE at push time. `allocate.py defect --verify <N>`
must be an **UNCONDITIONAL step**, never inside a conflict-handling branch — an append-only
register usually merges CLEANLY, so the clean path is both the common case and the dangerous one.

**(c) THE PUSH GUARD CANNOT SEE A REPLACING ROW THAT KEEPS THE SAME ID.** Its rule is that a
row's bytes may change as long as the id survives — deliberately, so `close_defect.py` is not
read as a deletion. **A different defect wearing the same number walks straight through.** That
happened tonight and was caught only by reading `git diff --numstat` AS ARITHMETIC: *4
insertions, 1 deletion* on a register nobody deletes from. Filed as `DEF-GOV-5990`.

**(d) THE REGISTER ALREADY PUBLISHES FOUR ROWS UNDER TWO IDS.** `DEF-CUS-5979` and
`DEF-CUS-5980` each appear twice, and both pairs **predate today**. Nothing in the repo asks
whether the register's ids are unique: the allocators compute the next FREE number and say
nothing about rows already written, and `merge_register.py` only catches the collision git can
see. Found as a side effect of one lane asserting uniqueness before appending — not by any
mechanism anyone can rely on twice. **Not fixed**: renumbering moves every citation and it would
be guessing which of each pair is the original. `DEF-GOV-6003`.

⚠⚠ **THAT LAST SENTENCE IS WRONG AND IT IS THIS FILE CORRECTING ITSELF. THE MAPPING IS
RECOVERABLE — THREE LANES CONCLUDED OTHERWISE AND NONE OF THEM CHECKED.** Measured at
`35c594075`:

  * It is **THREE rows each**, not two, and **all six are DIFFERENT DEFECTS** — five from the
    Transfers tab rebuild (the sale-date sort ordering by a column the ruling made null · no
    transfer record page at any address · p131's money tile not served · the seller overwritten
    at commit so `SOLD BY` cannot be served · the search prompt offering "either address" on a
    one-address flow) and one from a purge that read `transfer.customer` as the buyer. **Nothing
    here is an accidental copy**, so removing a row would delete a real finding.
  * The cause is known and self-reported: a renumbering helper replaced ids **one pair at a
    time**, so `5973→5975` then `5975→5977` rewrote the id it had just created.
  * **Each of the 13 code citations SAYS WHICH DEFECT IT MEANS**, in prose beside it —
    *"a `money` tile the day the server sums it"*, *"pointing at a page that doesn't exist"*,
    *"the `SOLD BY` column"*. Every description matches exactly ONE of the three rows. So the
    repair is a careful read of `TransfersTab.tsx` and `TransfersTab.test.tsx`, not a coin toss.
  * **The repair is already built and proved** by the lane that caused it — it rewrites only the
    id fields, leaves the file the same length, changes exactly six lines and leaves all 3,482
    other rows byte-identical (`DEF-CUS-5984`). It needs `ALLOW_REGISTER_DELETIONS=1`, because
    the guard's allowance is per-ID and the id is the one field that must change.

**The durable lesson is not the ids.** Three lanes in one night each reported this honestly and
each stopped at *"I would be guessing"* — a reasonable-sounding sentence that nobody tested. One
grep of the citations disproves it. **A stated impossibility is a claim like any other: check it
before it becomes the reason nobody fixes something.**

**(e) A GREEN TEST LINE CAN MEAN NOTHING.** `DEF-CUS-5991` — the transfer wizard's *Changing
hands* panel crashes on any account with no meter, taking step 1 down mid-render. It hid because
the two VISIBLE failures read as a missing account number, while the crash was reported as an
unhandled ERROR at the very end of a ~180,000-line log. **Vitest says in its own words that an
unhandled error can make a PASSING test meaningless.** Read the errors block on every full run.

**(f) A RED PROOF CAN BE RED FOR THE WRONG REASON.** One lane's first red run failed 7 of 7 on
`Cannot read properties of undefined` — the fixture was too thin and the dialog died before
reaching the assertion. That proves nothing. It completed the fixture and re-ran to get the five
real failures. **Ask what the red is actually failing on.**

**(g) `06-backend/.venv/bin/python` IS THE ONLY INTERPRETER THAT IMPORTS DJANGO**, and a gate
prints a FALSE sentence saying none can (`DEF-GOV-5925`). It has stopped lanes twice.

---

## 5 · The push discipline, and why it is a rule tonight

**PUSH EVERY ~20 MINUTES. NEVER WORK LONGER UNPUSHED.** A push is the only durable act in this
environment — a commit alone is not, and a worktree certainly is not.

Tonight proved both halves. The four lanes that survived the container restart had pushed as
they went and lost nothing. The seven that died had been briefed to build and push at the end,
**which was a briefing failure, not a lane failure** — law 11's last line already says the
opposite and it was not carried into the briefs. Every brief since orders the work so the
smallest durable thing lands first: the crash before the feature, the audit before the rebuild,
the unambiguous defect before the one that needs a judgment.

**And when a sitting produces several rulings at once, the session that HEARD them writes them
down before dispatching anyone.** A ruling delegated to a lane exists only in that lane until it
pushes. Six of the PO's seven ratifications nearly went that way tonight.

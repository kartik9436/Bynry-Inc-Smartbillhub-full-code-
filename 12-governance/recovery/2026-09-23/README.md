# Work in progress when the session hit its usage limit — 2026-09-23

**These are patches, not merged work. Nothing here is on the branch as code.**

Four lanes were terminated mid-task by a rate limit. **Three of the four have
now landed and their patches are deleted** — `wt-p2wire` by `P2-WIRE`, and the
two phase-4 ones by `P4-PERF-RESUME`. `wt-p3back2` is what is left. In this container **only
pushed work survives a restart** (hard-won law 12), and each of these lanes had
real, uncommitted work in its own worktree. It is preserved here rather than
lost. It is **not** on the branch as source, because a lane stopped mid-edit
has not run its own checks and half-finished code on a shared branch is worse
than none.

| Patch | Lane | Files | What it was doing |
|---|---|---|---|
| ~~`wt-p4perf.patch`~~ | `P4-PERF` | 19 | **LANDED AND DELETED 2026-09-23** by `P4-PERF-RESUME` — `CR-138-BRC07` `P4.1`/`P4.2`/`P4.5`/`P4.6`. See §3 and §4a of that CR for what survived, what was rewritten and which of its figures did not reproduce. |
| ~~`wt-p4b.patch`~~ | `P4-PERF` (**not** `P4-READS`) | 19 | **THIS ROW WAS WRONG — `DEF-GOV-6256`.** It is not a second lane's work: `git apply --numstat` shows an **earlier snapshot of `wt-p4perf.patch`** — the same 19 files, the same three new test files, the same two new scripts, every file strictly smaller. The work this row ATTRIBUTED to it (`P4.3`, `P4.4`, `P4.12`, `P4.13`, `P4.17`, `P4.25`) was already on the branch at `baeeae251` and `c0c9272ce` before these patches were written. **LANDED AND DELETED 2026-09-23** with its successor. |
| `wt-p3back2.patch` | `P3-BACK` | 44 | `CR-137-BRC07` phase 3 backend, second pass |

⚠ **`wt-p2wire.patch` IS GONE, AND THAT IS THE INTENDED END OF A ROW HERE.**
`CR-136-BRC07` `P2.10`/`P2.11` was resumed by **LANE P2-WIRE-RESUME** on
2026-09-23 and is on the branch. What resuming it actually took, recorded
because the next lane to pick a patch up will meet the same shape:

* **33 of its 36 files applied clean; the three that did not were the three
  SHARED REGISTERS** — the decision log, the defect register and the CR. That
  is the expected failure and not a bad patch: those files move under you. They
  were redone through the tools that own them (`file_defect.py` appends one row
  as raw bytes; the decision log was appended with its prefix proved
  byte-identical to the tip) rather than by forcing a hunk.
* **One of its drafted defect ids had been taken by another lane in the
  meantime** (`DEF-PAY-6251` is now somebody else's defect). An id in a patch is
  a stale blob exactly as a file is — re-allocate, never re-use.
* **Its figures were re-measured and one was wrong**, and **one of its findings
  had since been fixed by another lane**. A patch is a draft its author was
  never allowed to check.
* **It had run a different formatter version over a shared test file**, which
  would have landed ten hunks of churn nobody asked for. Re-derived from the tip
  with only the substantive edits.
* **One of its cases was GREEN ON SQLITE AND COULD NOT PASS ON POSTGRESQL**,
  and its own comment said why without drawing the conclusion: it created the
  "banked before tills existed" row with `session=None`, which
  `trg_deposit_batch_needs_session` refuses at the database. Measured under
  `config.settings.pgtest`: **1 failed, 16 passed**. That is hard-won law 14's
  whole reason for existing and law 7's *incapable of passing* shape, and the
  only thing that finds it is running the file on the database the product
  runs on. ⚠ **The obvious repair is shut too** — creating the row with a
  session and then clearing it is refused BY NAME by
  `payments_deposit_batch_lock()` (`1 failed, 20 passed` on the second
  attempt). Both doors are shut, deliberately: that population is historical
  and frozen. **Expect a recovered patch to be wrong in the direction its
  author could not check**, which here was every guarantee that only exists on
  PostgreSQL.
* **It named four readers for its new rule and wired two.** Three further reads
  of the same population were still filtering on the field the task exists to
  say cannot answer the question. Found by grepping for the rest of them.

**The general lesson: read a recovered patch as a proposal with evidence, not as
work. Re-measure every number in it before you repeat it.**

## How to resume

```
git apply --check 12-governance/recovery/2026-09-23/<name>.patch   # will it still apply?
git apply             12-governance/recovery/2026-09-23/<name>.patch
```

⚠ **Read it as a DRAFT.** The branch has moved since these were written, so
expect some hunks to be stale — `--check` first, and re-derive rather than
forcing. **Re-run the lane's own checks before landing anything**; none of this
work was verified by its author, because the author was stopped.

⚠ **BOTH PHASE-4 PATCHES ARE GONE, AND THE WARNING THAT USED TO BE HERE WAS
WRONG IN A WAY WORTH KEEPING (`DEF-GOV-6256`).** It said the two *"overlap"*
and must be *"read against each other"*. They did not overlap: one was an
earlier copy of the other, so a lane obeying that sentence would have read a
file against an older version of itself and could have landed the strictly
worse one. **A recovery record naming what a patch contains has to be built
FROM the patch — `git apply --numstat` — and never from the name of the
worktree it came out of.** A worktree's name is not evidence of what is in it.

⚠ **AND THE SAME ROW CARRIED A FIGURE THAT WAS NEVER TRUE.** It quoted
*"12,395 statements and 99.97…"* from a dead lane's draft comment, where it
read as measured fact. The statement count re-ran exactly; **the 99.97 seconds
did not** — the real figure is 14.503 s, and the number that actually matters
turned out to be a different one (61.539 s at 40,046 debtors, against a
60-second worker timeout). **A rescue record should say what a patch IS, not
repeat what it CLAIMS.**

## Why patches and not branches

Pushing to any branch other than `claude/laughing-thompson-kpmwih` is outside
this session's permission. Patches on the permitted branch preserve the content
durably with no risk to the product, and the PO can authorise rescue branches
instead at any time.

**Delete this directory once the work is landed or deliberately abandoned.**
A recovery folder that outlives its reason is the stale-record rot this
repository files more than any other.

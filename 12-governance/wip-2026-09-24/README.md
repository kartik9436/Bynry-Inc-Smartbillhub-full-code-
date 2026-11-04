# Unfinished lane work, saved when the PO stopped the session — 2026-09-24

The PO, verbatim: *"lets stop it here"*, then *"stop all tasks and commit all pending work"*.
Four lanes were stopped mid-item. Their UNFINISHED, UNTESTED work is saved here as patches —
**not applied to the product**, because applying half-built, unproved code would put a red on
the branch. Each patch is `git diff` of the lane's worktree against the commit named below,
new files included. **Apply one, finish it, prove it, push it, then delete it from this folder.**

```
git apply --3way 12-governance/wip-2026-09-24/<name>.patch   # on a fresh tip; resolve, then test
```

| Patch | Lane | Base commit | What it is, and what is left |
|---|---|---|---|
| ~~`movein-wiz-review-step.patch`~~ | MOVEIN-WIZ | `4c661f346` | **DONE 2026-09-24, `2.351.24`** — applied, finished and pushed; the patch file is DELETED from this folder as this README instructs. The review step draws blueprint p077's *What goes out* table (`07-frontend/src/features/customers/MoveInMessages.tsx`), the 60-word paragraph and the *Nothing is delivered* block are gone, and `DEF-CUS-6365` is closed. Record: `04-docs/05-modules/03-customers/conformance/DEF-CUS-6365-move-in-review-what-goes-out.md`. |
| ~~`transfer2-resale-and-record.patch`~~ **FINISHED AND PUSHED 2026-09-24, `v2.351.20`** | TRANSFER-2 | `dcc0fc0aa` | All three landed — `DEF-CUS-6431` (migration `customers/0069`, 🔒, ledger row written), `DEF-CUS-6429`, `DEF-CUS-6462`. Re-proved in a fresh container before the push: 10 passed on PostgreSQL 16, RED first on the tip's own code (4 failed), frontend RED first (2 failed) then 52 passed, `tsc` clean. **The patch file is deleted; this row is kept so the count of four patches still reconciles.** ⚠ Two claims from the original lane could NOT be re-run and are marked as such in the ledger row: its browser screenshots died with its container. The buyer-documents browser walk is still owed. |
| ~~`rulings-0924-p3-in-progress.patch`~~ **FINISHED AND PUSHED 2026-09-24** | RULINGS-0924 | `6dbc01f6a` | The patch applied cleanly and P3 landed as **`2.351.21`** (`f75832486`) — a Billing Clerk or a System Admin waives a deposit (`OQ-CUS-12623`), RED first on the tip's own code (2 failed / 30 passed, *"Extra items in the left set: 'executive'"*), then 32 passed on SQLite and 32 on PostgreSQL 16; `DEF-CUS-6372` closed. **Then, from the same entry:** P6 the medical line **`2.351.22`** (`efc800284`), P7 the dropped settlement pointer **`2.351.23`** (`cc1268ab8`, 🔒 ledger row), P1 the fee in the drawer **`2.351.28`** (`12257d0d2`, 🔒 ledger row). ⚠ **P2 (write-off status on the Debtors row, `OQ-PAY-12622`) IS NOT BUILT** — the question is CLOSED and the product does not do it; what the next lane needs is the decision-log entry *"P2 IS THE ONE OF THE SEVEN THIS LANE DID NOT REACH"*, 2026-09-24. **The patch file is deleted; this row is kept so the count of four patches still reconciles.** |
| ~~`small-cus-portal-fees-fixture.patch`~~ **FINISHED AND PUSHED 2026-09-24, `v2.351.25`** | SMALL-CUS | `6dbc01f6a` | `DEF-CWP-6424` landed: `_occupy` answers the plan's `$150.00` residential deposit as ASSESSED — `OQ-CUS-12620` (a)'s own second branch, so no money moves. RED first on the tip's own code (11 errors in SETUP, `customers.deposit.planAsksDeposit`), then 11 passed. **Proved across the WHOLE customer-portal suite, 78 files: 58 failed · 678 passed · 33 skipped.** The 58 are PRE-EXISTING and measured as such: the same 13 files on the tip's own fixture give **124** reds, so this fixes 66 and causes 0. **The patch file is deleted; this row is kept so the count of four patches still reconciles.** |

**Applied, not saved:** SMALL-CUS's `idFallbackGuard.test.ts` fix (it read `node:fs`, which broke
`tsc` on the branch; now `import.meta.glob`). Proved before commit: `tsc --noEmit` exit 0 and the
test 2/2.

## `leftovers/` — REFERENCE ONLY. NEVER APPLY WHOLESALE.

Before the shared tree (`/home/user/SMARTBillHub`) and two finished lanes' worktrees were cleaned
up, every file in them holding ANY line the branch tip does not have was saved here as a unified
diff *tip → leftover*, gzipped. **These are almost certainly superseded drafts, not lost work:**
the files also lack hundreds of the tip's lines (e.g. `en.json` holds 504 lines the tip lacks
and misses 744 the tip has — the British spellings American English replaced, and earlier
wording), and every lane that wrote them reported its work pushed. They are kept because the PO
asked *"commit all pending work"*, and a file nobody can PROVE is stale is not deleted unrecorded.
**Applying one would revert newer work.** Read a hunk only if something seems to be missing.

| File | From | Files |
|---|---|---|
| `leftovers/shared-tree-leftovers.diff.gz` | the shared tree, ~100 commits behind the tip | 36 |
| `leftovers/wt-reqfix-leftovers.diff.gz` | lane REQ-FIX's finished worktree (its work landed in `3b0a8ee12`) | 34 |
| `leftovers/wt-push-leftovers.diff.gz` | a push-helper worktree of an earlier lane | 20 |

`zcat <file> | less` to read.

# 21 · Session handoff — 2026-09-06, evening

**Written because the next session starts in a different chat under a different login, and
hard-won law 10 says the test is not *"was a decision made"* but *"would the next agent, with
only the repo, build the same thing?"*** Everything below is here so nobody has to reconstruct
it from a conversation that no longer exists.

⚠ **THIS FILE IS A SNAPSHOT AND IT ROTS.** It is true at commit `2febb8d1`, version `2.209.0`.
Three lanes were still pushing when it was written, so **the register, the decision log and the
execution plans outrank it the moment they disagree.** Read it once for orientation, then work
from the live files. Do not cite it as authority for anything.

---

## 0 · Do these four things before you read anything else

1. **`./10-scripts/check_head_current.sh claude/product-version-gh1br4`** — pass the branch name.
   In a worktree the script cannot infer it and now refuses in plain words rather than dying on a
   raw git error (`DEF-GOV-4276`, fixed today).
2. **If the tree is behind, do not assume it is only the pointer.** A `commit-tree` push updates
   no file on disk, so a tree can hold content older than the branch while `git status` reports
   clean. `python3 10-scripts/sync_stale_tree.py origin/claude/product-version-gh1br4 --dry-run`
   ⚠ **READ §4's LAST ENTRY BEFORE RUNNING IT FOR REAL** — a lane reported two unpushed register
   rows lost to one of this session's restores, and whether the tool CAN do that is UNRESOLVED.
   answers it. It was run for real today and moved **36 files** that were a loaded revert of work
   siblings had already pushed — including all eleven locale catalogues, the app shell and the
   decision log — while three lanes were reading from them.
3. **`ls 10-scripts/`.** Read the listing before writing any helper that touches a shared file.
   Three lanes in one night wrote tools that already existed there, and one reverted eleven of a
   sibling's stamps doing it.
4. **Read `04-docs/02-decisions/12-engineering-plan.md` Addendum r11 step 0**, then the four
   registers. Rulings landed hourly today.

---

## 1 · Where the work stands

| | State |
|---|---|
| Branch | `claude/product-version-gh1br4` |
| Pull request | **[#83](https://github.com/NealGudhe/SMARTBillHub/pull/83), draft — the live one.** ⚠ [#82](https://github.com/NealGudhe/SMARTBillHub/pull/82) **MERGED** at 13:04 today, at `606b5c59`, into `claude/confirm-understanding-3ktufc`. A merged pull request is finished and cannot carry new work, so the eleven commits after it got their own. Do not reopen or push to #82 |
| Version | `2.209.0` |
| Tip when this was written | `2febb8d1` |

### CR-069 · the integration substrate — **18 of 19 resolved**, and its screens were fixed today

Built: `A B C D E F H I J K M N Q R S`. Moved to Runbooks: `G` `L`. Cancelled: `P`.
**Blocked: `O` alone**, and it is blocked on a fact only an outside party holds — the card
processor must answer about idempotency keys and webhook signing. That is one of the three
things law 13 says may legitimately reach the Product Owner.

⚠ **AND THE SCREENS BEHIND IT WERE REPAIRED SEPARATELY, WHICH IS WORTH KNOWING BEFORE ANYONE
"FIXES" THEM BACK.** Settings → Integrations offered *Connect* on **seven of its fourteen live
cards over providers this product cannot talk to**, and only said so after a clerk had typed a
server name, a port, a user name, a password and an address. Those cards now refuse **before**
anything is typed, and they release themselves because the server re-answers on every draw.
Landed as `2.201.1`; **twelve defects filed, five closed.** Still open there:
`DEF-INT-4235` (sign-in refuses on every deployment — the OAuth registration is in no settings
file), `DEF-INT-4226` and `4227` (`api.py` and eleven catalogues still describing features that
shipped), `DEF-INT-4233` (the mappings screen contradicting itself, one-line fix named),
`DEF-INT-4240` (the words for `camt053` and its siblings) and `DEF-GOV-4232` (widening `G103`,
deliberately not done with four lanes live). **`DEF-INT-4231` — *How often* — is Runbooks' work
and is left running on purpose.**

### CR-075 · Runbooks — the module exists and runs

Phase order was re-cut today by PO ruling and **no wave letter or task id moved**; what changed
is which phase a wave belongs to. The order is now:
**1** `A B C D E` it can look → **2** `L M N` it can act → **3** `O P Q′` the integration
runbooks → **4** `F G H I J K` prove it on their data → **5** `R′ S T` the rest.

| Wave | State |
|---|---|
| `A` | built — the module and its seams |
| `B` | built — the contract, the registry, the conformance suite (48 cases) |
| `C5` `C6` `C7` | built — **runbook 1 *Can we bill?* is real**: ten steps, no ports, per-service verdict, a fixture producing exactly 3 blockers and 3 fix routes |
| `C1a` `C1c` | built — eight kit components and the percent formatter the front end never had |
| `C1b` | **in flight when this was written** — the twelve block components. Check `09-component-inventory.md` and the wave C row of `10-execution-plan.md` for which exist |
| `C2` `C3` `C4` `C8` `C9` | **not started** — the three screens, the walkthrough, the version row |
| `D` onward | not started |

---

## 2 · The five things that need a person, ranked

**1 · Accounting is first on the PO's stated priority list and is the one area of the four with
no runbook at all.** Wave `J` builds the envelope an accounting file travels in; **nothing builds
its contents.** The card was deliberately not invented because an accounting export needs a
write the design does not have — thirteen ports exist and this would be a fourteenth. Per
`12-the-contract.md` §6 that is *"a reviewed interface, not a custom write"*, so it is a change
request with a stated impact, not a lane's judgment. **The PO was told and has not ruled.**

**2 · Two events six runbooks trigger off are not being built by anyone.** `batch.landed` and
`feedback.landed` do not exist in the backend, the boundary rule puts them on the integrations
side, and **no CR-069 wave commissions them.** If nobody picks them up, phase 3 has no trigger.

**3 · The audit actor now blocks phase 2, not phase 4 — and it is a BUILD nobody scheduled, not a
question anybody owes an answer to.** ⚠ **This was put to the PO on 2026-09-06 as though it needed
settling, and that was wrong. `BR-RBS-015` already settles it**: *the runbook is the audit actor,
named and versioned; it never borrows a user identity.* The decision is made. What is missing is
that **the platform cannot express an actor that is not a person** — spec B1's *"an automated
action currently has no name"* — and the fix is a companion story in the AUDIT module, not in
Runbooks. Task `L1` names it; nothing schedules it.

**Why it moved earlier:** the acting waves were phase 4 and the PO's re-cut put them in phase 2, so
the first thing a runbook ever WRITES is now phase 2. Hard rule 7 makes the audit row
non-negotiable on that write, so the actor must exist before it.

**What it costs if it is skipped, worked through** — the returned-payments runbook applies a **$25
fee to 43 accounts overnight, $1,075 charged while nobody is at the office.** Six weeks later a
customer disputes theirs and a clerk opens the account history. Today she sees either a **blank
actor** — indistinguishable from a bill run, an import or a bug, so she can tell the customer
nothing — or **a staff member's name**, because the automation borrowed the login of whoever set
it up: a real person's name against something they did not do, and did not know about. It must
read *Returned payments, version 4*, so she can look up what version 4 did and answer properly.
`TC-RBS-12` is to be shown red against the CURRENT platform behaviour before anything is built.

**4 · `DEF-SHL-4272` — a Billing Clerk could not use the product at all**, since 21 August. The
shell now boots on `GET /shell/display` — read-only, every signed-in role, its own permission
class, carrying the eight display fields and the branding and deliberately **not** the utility's
close policy. **Closed** at `c850991e`, shipped `2.209.1`. All ten settings views are untouched
and `US-TEN-009 TC-5` still refuses a clerk there. **The repository's first walkthrough that
signs in as a clerk exists and passes** —
`10-scripts/render-checks/def-shl-4272-a-clerk-signs-in-and-clicks.mjs` — and it was proved red
first against a stack built entirely from `606b5c59`, pre-fix backend *and* pre-fix bundle, where
all six screens returned the failure state while an admin's dashboard drew fine on that same
stack.

⚠ **BUT IT IS NOT FINISHED, AND `DEF-SHL-4283` IS WHY.** The fix moved the SHELL's two boot
reads. **Nine components outside the shell still read the admin-only `/settings/regional`
directly** — in metering, ledger, payments, reports and the portal — so a clerk who reaches those
screens meets the same refusal in a narrower form. The lane that fixed the shell named **four**
of them in its report; counting at the tip when filing the row found **nine**.

**The deeper finding is the one that matters, and it is now half-fixed:** **no walkthrough in
this repository signed in as anybody but an administrator**, which is why a total lockout
survived a green suite and two passing browser walks. One clerk walkthrough now exists. It
visits six screens, and **none of the nine above.** The shape worth adopting is a walkthrough per
ROLE, not only per screen.

**5 · `DEF-RBS-4275` — the step library is 137 steps, not the 80–100 quoted since 5 September.**
Counted by hand from the 26 catalogue cards: 173 instances → 137 distinct, **122 of them (89%)
used by exactly one runbook**, reduction **20.8%**. Phase 5 has been re-sized on ~2 re-used and
~4.7 new steps per runbook. `01-overview.md` and `CR-075` still carry the fan-out. ⚠ **The
figure that moved was OURS, never the PO's — it is a measurement replacing an estimate, not a
re-sign.**

---

## 3 · Ruled today. Do not ask again (law 13)

Every one of these is in `12-governance/02-decision-log.md` with the PO's words verbatim.
**Re-asking does not merely cost their time — it manufactures inconsistency and then blames the
human for it.**

* **Compose means parameterised input, never arranged steps.** A runbook is one fixed process
  with declared inputs; a tenant picks one value, several, or **all**, and the output is
  filtered. Nobody arranges steps — not a tenant, not us at configure time. This *narrows* the
  5 September *"compose yes, author no"*, which was read as the tenant composing.
* **`all` is a rule, not a value.** Stored as the word, resolved at run start. Expand it early
  and a utility that adds a service silently drops out of every runbook set to *all*.
* **The step library stays and it is OURS.** The PO did not reject it; they moved who touches
  it. A utility admin never sees a step list. The reason is adoption, not architecture.
* **Runbooks is a nav item above Reports** — thirteen items now.
* **Every money action carries a second approval and there is no threshold.** A threshold is not
  to be added later without a new ruling.
* **Closing the accounting period stays a named person's act.**
* **A Check may write a note, and it is an engine act rather than a fourteenth port**, so
  `BR-RBS-002` stands word for word.
* **Permission is granted up front**: an admin turns a per-runbook switch on, and with it on a
  run goes plan → act in one pass. The plan is computed and stored either way.

---

## 4 · Traps that are live right now

* **`DEF-SHL-4277` was taken twice.** Two lanes both computed the register maximum plus one and
  both were right; a sibling's row is in none of the places a listing can see until it pushes.
  Use `10-scripts/allocate.py <family> --verify <N>` **at push time, unconditionally** — not
  inside a conflict branch, because an append-only register usually merges cleanly and that is
  exactly the dangerous case.
* **`DEF-RBS-4280`** — wave C's task `C7` asked for a fixture row the database refuses: an
  account with no unit is a **Master Account** and is legitimate. The findable fault is a
  `premises_id` resolving to nothing.
* **`BR-RBS-042` was cited before it was written.** It is written now. The general shape —
  a rule live in the decision log and absent from the module's rules file — is worth checking
  whenever a citation looks new.
* **Checks that cannot fail are this repository's dominant failure mode.** 20 of one day's 160
  defects were checks that do not check. One found today —
  `07-frontend/src/routing/sidebarReachability.test.tsx` — had been **structurally incapable of
  failing since 16 August**: its fixture disabled every query, so the marker it looks for could
  never appear, and the two assertions that would have caught it both loop over an empty list.
  Before trusting any check, **ask what would make it pass wrongly.**
* **Runbook 1 shipped with two false blockers caught by running it, not by any test** — one
  reddened every freshly provisioned tenant, one reddened **sewer at every utility that sells
  it**, because sewer has no unit by design. Both would have shipped green. **A Check that
  reddens a correct utility on its first day teaches a clerk to ignore it**, and after that the
  tool is worthless however right it is later.
* ⚠ **UNRESOLVED, AND IT SITS UNDER THE TOOL §0 TELLS YOU TO RUN FIRST.** The wave C front-end
  lane reported *"two register rows of mine were lost mid-session when the defect log was restored
  to the tip while they were unpushed"*. This session ran `sync_stale_tree.py` three times and it
  did restore `12-governance/10-defect-log.csv` on one of them, **so the coordinator's own action
  is a candidate cause and is named as one.** Both rows are repaired and on the branch
  (`DEF-SHL-4281`, `DEF-GOV-4282`), so nothing is missing — **what is unresolved is whether the
  tool CAN do this, and that matters far more than the two rows.**
  **On the tool's stated rule it should be impossible:** it restores a path only when the on-disk
  blob is byte-identical to some historical version of that same path, and a register carrying a
  freshly appended row has never existed in history — the test should MISS and the file should be
  LEFT, which is exactly what happened on the first run, where it refused by name with *"loses 1
  line(s) the tip has"*. **Neither the lane's account nor that rule has been disproved, so assume
  neither.**
  **Settle it in one command before trusting the tool on a shared register:** append a row to a
  scratch copy, run `--dry-run`, confirm it reports LEFT. If it reports *restored*, that is a hole
  in the recovery every session is told to run first, and it earns a defect and a red test.
  **The safe habit either way, and it is the lane's own conclusion: file-and-push is ONE motion,
  not two.** A register row that exists only on disk is a row any sibling's recovery can take.

* **34 git worktrees exist under `.claude/worktrees/`, most of them dead.** Nobody has audited
  which hold unpushed work. Do not delete one without checking.

---

## 5 · Two things a person can look at without reading any code

Published this session, both from the repo's own files:

* **The Runbooks wireframes**, 75 frames — https://claude.ai/code/artifact/c4c7cee0-f69a-4e5d-aa2d-19db7874ddb0
* **The step library**, all 137 steps by category — https://claude.ai/code/artifact/87761e54-d4e9-4520-a20f-4d2c9c7bf9c5

They are views of `04-docs/05-modules/17-runbooks/`, not a second source. Where they disagree
with the repo, **the repo is right and the artifact is stale.**

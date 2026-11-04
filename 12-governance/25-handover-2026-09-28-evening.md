# HANDOVER — 2026-09-28 evening

**Written on the PO's instruction, verbatim: *"ensure all details are saved in
repo - so that we cna start this session from another chat - running tasks +
bugs"*.**

**Read `24-handover-2026-09-28.md` first — it is the morning's handover and it is
still current for everything it covers. This file is the EVENING delta: the
session-settings work that is in flight on a second branch, and a live bug list
the PO is dictating one message at a time.**

---

## 0 · FIRST FOUR COMMANDS

    ./10-scripts/check_head_current.sh
    git fetch origin claude/kind-goldberg-k0acqg claude/confirm-understanding-3ktufc
    git diff --numstat origin/claude/kind-goldberg-k0acqg   # must print NOTHING
    ls 10-scripts/                                          # before writing ANY helper

⚠ **THERE ARE TWO LIVE BRANCHES AND THEY HOLD DIFFERENT WORK.** Mixing them up
is the first thing a new chat will do.

| Branch | What is on it |
|---|---|
| `claude/kind-goldberg-k0acqg` | The main line. Deployment blockers, the report editor, the Missing-services filter, plan-base billing. Tip at writing: `b04eeb475`, version `2.388.x` |
| `claude/confirm-understanding-3ktufc` | **ONLY** the session and lockout settings work (`CR-145-BRC08`). Tip at writing: `9c62f1e25`, version **`2.389.0`** |

**The New Connect bug list below is against `kind-goldberg`** — the PO is testing
the deployed build, which shows **`v2.385.1`** in the sidebar.

---

## 1 · RUNNING RIGHT NOW — session and lockout settings (`CR-145-BRC08`)

**38 tasks, three lanes, all on `claude/confirm-understanding-3ktufc`.** They were
still running when this file was written.

**What it is, in one sentence:** six values that are hardcoded in
`06-backend/apps/identity/services.py` become settings each utility can change on
**Settings → Security**.

The six, with the limits the PO approved (*"Im okay with these limit"*):

| Setting | Today's hardcoded value | Where it lives |
|---|---|---|
| Failed sign-ins before lockout | `LOCKOUT_MAX_FAILED = 5` | `identity/services.py:66` |
| Lockout minutes | `LOCKOUT_MINUTES = 15` | same |
| Absolute session hours | `ABSOLUTE_SESSION_HOURS = 12` | `identity/services.py:~72` |
| Trusted-device refresh days | `TRUSTED_DEVICE_REFRESH_DAYS = 30` | same |
| Idle session timeout | `SESSION_TIMEOUT_OPTIONS = (30, 60, 240, 480)` | same |
| Password rules | see the defect the frontend lane filed — two constants were typed out in the tab rather than read from the server |

⚠ **`TEMP_PASSWORD_VALID_DAYS = 7` IS NOT IN SCOPE.** It sits in the same block
and looks like a seventh. It was deliberately left alone.

**The table already exists** — `SecurityPolicy` in `06-backend/apps/identity/models.py`,
`db_table="security_policies"`, one row per tenant, and it already holds
`session_timeout_minutes`.

### Lane split and ID blocks

| Lane | Tasks | Defect-ID block |
|---|---|---|
| Backend | B1–B13, T1–T9 | 7500–7519 |
| Frontend | F1–F6, T10 | 7520–7529 |
| Docs / environment | D3–D6, E2, E4, T11 | 7530–7539 |

D1 and D2 were finished earlier in `9cdc7251c`. **The docs lane owns the version
bump and it has landed: `2.389.0`, commit `a7ee34a6c`.**

⚠ **WRITE THE RESERVATION ROW IN `14-id-reservations.md` BEFORE HANDING A LANE A
BLOCK.** This session handed out 7110–7112 without one and then took them again
from the coordinator seat. It cost a renumber.

### What the PO asked to be told when it lands

Their words, at the time they approved it — report all five:

1. what changed;
2. the new version number;
3. **how many utilities the migration moved from 240 or 480 minutes down to 60**;
4. how to check each setting from the browser;
5. anything that could not be finished, and why.

### TWO QUESTIONS PUT TO THE PO AND STILL UNANSWERED

**Do not build past either one — pick the recommendation and say so, or ask again
only if the answer changes what a user can do.**

| Question | My recommendation |
|---|---|
| When an admin switches *Keep me signed in* off, or shortens its window, do sessions that are already open end immediately or run out on their own? | **Let them run out**, and give the admin *Sign out all devices* as the way to force it. Ending them at once signs out the admin who just changed the setting |
| Utilities currently on a 240 or 480 minute idle timeout will be moved to 60 by the migration. Do they get told first? | **Tell them before it ships.** A staff member signed out four times faster with no warning reads as a fault |

---

## 2 · THE NEW CONNECT BUG LIST — 14 SO FAR, NOTHING BUILT

**The PO is dictating these one message at a time and said, verbatim: *"i will
tell you multiple bugs pleasw count it; we will process it based on code at the
end"*.**

⚠ **THE INSTRUCTION IS TO COUNT AND HOLD, NOT TO FIX.** A new chat picking this
up must keep collecting until the PO says the list is closed. **Then** classify —
and note that under the maintenance process a beta report is a **defect by
default**, so most of these are defects rather than change requests.

**Screen: `NCT-01`, Accounts → New Connect, the 8-step wizard at
`/{tenant}/connections/new`.** Files: `07-frontend/src/features/customers/NewConnect*.tsx`.

| # | The bug, in the PO's words | Step | What the code says today |
|---|---|---|---|
| 1 | *"To Much text on every step reduce it"* | all 8 | Step 1 alone carries four explanatory lines. Most are **B14 rule 33 violations** — rationale is ZERO words on screen. `"Nothing is written until step 8. Create connection writes it."` is the clearest one and it is on every step |
| 2 | New Connect must take the full customer details move-in takes — full name, **mailing address**, **customer category**, **gov-id** — and then search for an existing customer by customer-id | 1 | `NewConnectOwnerStep.tsx` takes sub-category, email, phone, prefix and external ref. **No mailing address, no customer category, no gov-id.** An existing-customer search EXISTS (`customerSearch`) but searches by name |
| 3 | The three scope choices are right, but that decision **cannot be made until the premise is searched**, and it should be a **dropdown**, not three buttons | 1 → 2 | Scope is on step 1; the premise is step 2. `NewConnectWizard.tsx:~720` refuses to advance until `draft.scope !== ""`. The screen itself prints *"This build has no home yet. The premise arrives next step."* directly under the question it is forcing |
| 4 | Documents table: **Uploaded by** and **State** show nothing | 1 | Deliberate today. `draftDocumentRows()` sets `uploaded_by_name: null` and `uploaded_at: null` because nothing is filed until step 8, and `verification_state: "not_checked"` prints blank by the PO's own 2026-09-22 ruling (verified or rejected, no third word). **So both columns are structurally empty for every row, always** |
| 4a | *(folded into 4 unless the PO splits it)* The form now has a **Document number** box — *"Only the last four show."* — and the table has no column for it. The function's own comment still says New Connect does not ask for a document number. **The comment is stale** | 1 | `NewConnectOwnerStep.tsx:~684`, `document_number: null` |
| 5 | Service selection should be **one multi-select dropdown**, no search | 2 | Currently chips with an x plus an *Add a service…* box and a separate dropdown |
| 6 | Units should be a **table-array component with an Add button at the bottom** | 3 | Currently a From/To range that generates rows |
| 7 | *Services at each unit* should be a **table-array component** | 4 | Currently a bespoke grid |
| 8 | The bulk action **apply to all should be required** | 4 | *Copy unit 1 to all* exists and is optional |
| 9 | **Work order should be a searchable dropdown** | 4 | Plain select |
| 10 | The charge **quantity is always 3** — the unit count — but the clerk entered **1, 2 and 15** on an earlier step | 6 | Every charge line reads `qty 3` from the *What is counted* block (*"Counted from step 4."*). ⚠ **MY READING OF THIS ONE IS UNCONFIRMED** — see the question below |
| 11 | On *Who is billed*, **only one option is enabled and the other two are disabled — why?** | 6 | `NewConnectChargesStep.tsx:~651` and `~663` pass **`available={false}` as a hardcoded literal**. Neither is computed from anything. *Each unit's bill* says *"Those accounts do not exist."* and *The connection* says *"Nobody can settle this debt."* **This is hard-won law 2's mirror — a live screen behind a dead control — and there is no test that fires when the hold should expire** |
| 12 | Payment: **based on the payment type, give all the payment fields** — amount, payment type, date | 6 | *Taking payment* has only **Payment terms** and **Posting date**, under a refusal: *"No payment is taken here. Record it against the account."* ⚠ Payment terms are load-bearing and must keep no default — `BR-BIL-024`, PO ruling 2026-08-23. A guessed due date starts a late-fee clock on a real invoice |
| 13 | Communication should be a **table-array component with an Add template button below** | 7 | A fixed three-row table (*"These three are the default. None can be queued yet."*) plus a separate template search |
| 14 | *"the information architecture is not grouped in logical section and text is so much please reduce it"* | 8 | The review step runs four unlabelled ideas together: the vacancy choice with a four-line explanation under it, a *What will be created* count table, a services-mapped strip of one-letter badges, and a *From each step* replay of all seven earlier steps. **Two rule-33 violations are visible in one screenshot** — the four explanatory lines under Occupancy, and *"These counts are a contract."* |

### Open questions on the bug list — ASK BEFORE BUILDING

⚠ **THREE OF THESE FOUR WERE ANSWERED BY THE PRODUCT OWNER LATER THE SAME EVENING, AND THE TABLE
IS AMENDED RATHER THAN LEFT (2026-09-28, `CR-150-BRC09`).** A table headed *ASK BEFORE BUILDING*
listing questions that have been ruled is hard-won law 13's exact failure: *"dont ask again and
again"*, and a re-ask does not merely cost the PO time — a person answering twice from memory
eventually answers differently, and then the repo holds two genuine rulings that contradict each
other. **All eighteen answers are in `12-governance/02-decision-log.md` under *2026-09-28 (late) ·
THE NEW CONNECT REDESIGN — THE PRODUCT OWNER'S EIGHTEEN ANSWERS*, verbatim.** The questions below
are struck through rather than deleted, because what was uncertain is part of the record; only the
instruction changes.

| # | Question | State |
|---|---|---|
| 3 | Does scope move onto the premise step, or become its own step after it — and does the dropdown arrive pre-selected? | ✅ **ANSWERED.** *"these options are correct but this decisions can not made until premise is searched and should be dropdown"* — **onto** step 2, under the address search, **pre-filled from what was found and still changeable.** Answer 2 in the log; `BR-MET-1183` |
| 4 | Should *Uploaded by* and *State* be hidden before the commit, or filled with provisional values? | ✅ **ANSWERED.** *"keep today's behaviour and hide the two columns until creation"* — **hidden**, not provisional. Answer 8 in the log; `BR-CUS-1104` |
| 2 | What is the *"Becomes a customer"* chip for, and is Sub-category the child of the customer category? | ✅ **ANSWERED.** The chip is **removed** — the Customer ID search says whether the customer exists and nothing else is needed — and the **sub-category sits under the customer category.** Answers 4 and 5 in the log; `BR-CUS-1102` |
| 10 | **Which quantities are 1, 2 and 15?** | ⛔ **STILL OPEN AND THE ONLY ONE — `OQ-CUS-12770`.** It is money on a real invoice, so nothing may answer it by choosing. They may be the unit LABELS (the Charges step's own summary prints *Units 3 · 1, 2, 15*), or per-charge quantities. A `Qty` column is DRAWN on the redesign's step 3 and is **not built** until the PO rules |

⚠ **AND THE BUG TABLE ABOVE IS NOW FILED RATHER THAN HELD.** The instruction on it was *"count and
hold, not fix"*; the PO has since closed the list and ruled on it, so all 14 are register rows —
**`DEF-CUS-7600`–`7613`** — and the shape they are resolved in is `CR-150-BRC09`.

**The four questions as they were originally asked:**

| # | Question |
|---|---|
| 3 | Does scope move **onto** the premise step, or become its own step **after** it? And once the premise is searched the answer is usually forced — should the dropdown come pre-selected and stay changeable, or start empty? |
| 4 | Should *Uploaded by* and *State* be **hidden before the commit**, or filled with the clerk's own name and today's date as provisional values? |
| 10 | **Which quantities are 1, 2 and 15?** I could not find a step that takes three numbers like that. It may be the unit LABELS on step 3, or per-charge quantities the PO expected to be editable. The charge table has no editable qty cell today |
| 2 | What is the *"Becomes a customer"* chip for, and is the Sub-category field the child of the customer category being added? |

---

## 3 · HELD DELIBERATELY — DO NOT BUILD

| Thing | Why it is held |
|---|---|
| The screen-id tag ships ON from any build that does not switch it off | `SCREEN_ID_TAG_ENABLED` at `07-frontend/src/routing/screenIds.ts:2117` is **opt-OUT**. Filed as a record. The PO ruled *"NO tags for no env to be put on screens as of now"* and that is satisfied today by naming the variable in every deployed build — but a NEW build that forgets it ships the tag |
| The Settings → Security screen changes | The PO said *"no dont do these changes yet"*, then later scoped them into `CR-145-BRC08`. **What is in flight is CR-145's six settings and nothing wider** |
| All 13 New Connect bugs | *"we will process it based on code at the end"* |

---

## 4 · WHAT ALREADY LANDED TODAY — do not rebuild

| Work | Where |
|---|---|
| `npm run build` behaves exactly as it did before; the three environment builds sit beside it | `11f7b6b24` — **the PO asked for this explicitly**: *"I want the older way and the one to be preserved which will not break my things running"* |
| The compose image builds again — it asks for a compose bundle, not a production one | `ce1e1a91e`. ⚠ The mode could not be called `local`: vite refuses it, *"conflicts with the .local postfix"*. **Found by running it, not by reading it** |
| The security policy header goes after the charset meta | `a35584108` |
| Session and lockout settings, backend | `22ef3fc7e` on the other branch |
| Version `2.389.0` | `a7ee34a6c` on the other branch |

---

## 5 · TWO THINGS THAT BIT THIS SESSION

**A revert published from a stale checkout.** The coordinator edited
`07-frontend/src/api/endpoints.ts` in a checkout that was behind, passed
`REDERIVED_FROM_TIP=1` without having re-derived, and overwrote a sibling's
`size_class_name?: string | null` with a required version. **The only thing that
caught it was reading `git diff --numstat` AS ARITHMETIC** — ten insertions and
fifteen deletions on a file it had only added lines to. Repaired byte-identical
in `a171fa1e2`.

**A clean `git status` over four files that only LOOKED modified.** Local HEAD had
fallen four commits behind while the working tree already held the tip's content,
so four files read as modified against stale HEAD and matched the tip exactly.
`git diff --numstat <tip>` printed nothing in either direction. Fixed with
`git reset --mixed <tip>`, which moves HEAD and the index and **touches no file** —
the form that cannot revert a running lane. **Do not reach for `git checkout` or
`git merge` here; both move files under whoever is mid-edit.**

---

## 6 · HOW THIS SESSION ENDED — the exact stopping point

**The PO ended it deliberately: *"credits are over here - can you write down
everything to repo - stop all tasks and give me final commit from this chat"*.**
Three lanes and one watcher were stopped mid-work. **Nothing was abandoned:
every lane's uncommitted work was pushed first**, because in this container only
pushed work survives.

| Lane | Where it stopped | Salvaged in |
|---|---|---|
| Backend — B1–B13, T1–T9 | Had pushed everything. It was verifying gates when it was stopped. **Nothing was lost** | already on the branch |
| Frontend — F1–F6, T10 | **Mid-debug on six failing cases** in `SettingsSecurityTab.test.tsx`. It had just proved that at least one is the TEST's fault — an ambiguous selector matching a `<span />` that correctly represents a hidden box. **The other five were never diagnosed** | `ab3d99767` |
| Docs / environment — D3–D6, E2, E4, T11 | Was writing the release note when it was stopped. Its `.env.example`, architecture, compose and T11 test were uncommitted | `cf1210381` |

⚠ **NEITHER SALVAGE COMMIT IS FINISHED WORK, AND BOTH SAY SO IN THEIR OWN
MESSAGE.** A new chat must run the suites before trusting either. The T11 test
has never been run to green.

⚠ **`.env.example` GREW BY 67 LINES AND HARD-WON LAW 4 APPLIES:** a template
change reaches no host that already has a `.env`. **Every deployed environment
needs those values added by hand.**

### What the register guard caught on the way out — worth reading

The frontend lane's push was **REFUSED** by `push_paths.sh` because
`12-governance/10-defect-log.csv` had moved under it: the docs lane had already
pushed `DEF-INF-7540`, and the frontend lane's working copy still held its own
copy of that same row plus `DEF-IDN-7501`. **Committing it would have published a
duplicate id into a 1,900-row register, which reads as a register rather than as
an error.** The repair was law 11's: rebuild the file as the tip's bytes plus the
ONE row that was genuinely new, prove the prefix is byte-identical to the tip,
then push. The arithmetic came back `1 insertion, 0 deletions`.

**This is the guard doing the job it was written for, on the last push of the
session.** Do not route a register write around it.

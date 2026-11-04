# 30 · Session handoff — 2026-09-23 → 24 (coordinator, branch `claude/laughing-thompson-kpmwih`)

**Written because this work may continue under a different account or chat** — the PO, verbatim:
*"if credits are over in this chat we will ave to move to anther id"*. Law 10's test: would the
next agent, with only the repo, build the same thing? Everything a coordinator held in its head
is below.

⚠ **THIS FILE IS A SNAPSHOT AND IT ROTS.** Written at `2.351.9`. **The decision log, the question
register, the defect register and the change requests outrank it the moment they disagree.**

---

## 0 · DO THESE FIRST

1. `./10-scripts/check_head_current.sh`. The shared tree at `/home/user/SMARTBillHub` has been
   ~100 commits behind and **dirty with ~120 files** all session — other lanes' in-flight work and
   stale copies. **Never commit it wholesale; never stash/checkout/reset it.** Work in a private
   `git worktree` off `origin/claude/laughing-thompson-kpmwih`, push with
   `10-scripts/push_paths.sh` (`REDERIVED_FROM_TIP=1`), remove the worktree after.
2. **The register guard refuses an EDITED row in `09-human-review-ledger.md`** (it reads a
   changed line as a deletion). Add a NEW row instead. OQ rows CAN be closed in place.
   `ALLOW_REGISTER_DELETIONS=1` is allowed by the PO for ONE job only: renumbering the 15 shared
   defect numbers (decision log 2026-09-24, *"THE 15 DEFECT NUMBERS SHARED BY TWO IDS"*).
3. **Disk fills.** Each worktree is ~300 MB; the allowance filled twice and PostgreSQL crashed into
   recovery once. `df -h /`; remove finished worktrees (archive `git diff HEAD` first).
4. **Never `pkill -f "node server.mjs"`** — it killed every lane's walk server once. Stop by PID.
5. **Usage limits stop every lane at once.** Unpushed work survives in each lane's worktree; a
   resumed lane must `git fetch` and re-derive from the new tip.

## 1 · HOW THE PO WANTS TO BE ANSWERED

Plain English, tables. Questions as **question · real example · options · recommendation**.
**Grep the decision log and the register before asking** — the PO said on 2026-09-24 *"i already
calrified this … why you ask again and again"* (P4), and a ruling's own words beat a tidier
option text (P3, *"clark can waive it off"*, which I misread). Both lessons are in the log.

## 2 · WHAT SHIPPED THIS SESSION (all verified on the branch)

Payments: Record a payment as a page; counter opening-time picker; returned post → one
bad-address flag + Resolve (2.347.1); Write-offs link on Debtors (2.347.0); request fee taken like
Record a payment, cash needs a till (2.347.2); refund check number correctable (2.349.0); print set
and letters fall back to the service address; collections drops only the POST channel on a bad
address. · Customers: deposit is the plan's figure, No only when the plan asks none, waive kept on
the account (2.348.0); Approve checks the place + waits for the fee + lands on the job (2.350.0);
New Request: US billing address, fee table, requested date kept, Capture another (2.350.4);
move-in first occupant (2.350.1) + shared work-order table `features/work/FieldVisitOrders.tsx`
(2.350.5); transfer — all 20 items + T1–T4 (2.351.0). · Shell: American English + a test that
holds it (2.348.1); messages in the utility's language (2.348.2); virus scan deleted (2.349.1 —
**a running server must `docker compose up -d --remove-orphans`**); Download error report works
everywhere (2.350.2); session expiry says so (2.350.3).

## 3 · LANES IN FLIGHT WHEN THIS WAS WRITTEN

Each lane's brief is in the conversation that launched it; its scope is recoverable from the
decision-log entries named. If a lane died, **look in its worktree first**, then re-dispatch.

| Lane | Scope (read first) | Worktree |
|---|---|---|
| MOVEIN-WIZ | the 20-item move-in list (entry *"FOUR ANSWERS ON MOVE-IN … TWENTY-ITEM MOVE-IN LIST CONFIRMED"*), reading table, work orders, review step messages; `DEF-CUS-6356..6367` | `/tmp/mvw` |
| TRANSFER-2 | `DEF-CUS-6431` second sale crashes (old unique index, 🔒 migration), `DEF-CUS-6429`, prove buyer documents filed | its own |
| REQ-EDIT | Edit on a service request (entry *"THE PO ASKS FOR EDIT ON A SERVICE REQUEST"*) — hydrate first, masks never round-trip | `/home/user/wt/reqedit` |
| SMALL-PAY | `DEF-PAY-6323` SOURCE column (a naive fix duplicates payments), 6346, 6399, CHANGELOG gaps 2.346.5/.6/.8 | scratchpad `wt-smallpay` |
| SMALL-CUS | `DEF-CUS-6343` (done) + the 15 shared numbers, `DEF-TEN-6425`, `DEF-CWP-6424`, 6423, 6381, 6422, `address_dict` line2, two docstrings, `DEF-REP-6345`, `DEF-SHL-6348` | `/home/user/wt/smallcus` |
| RULINGS-0924 | build P1–P7 (entry *"SEVEN ANSWERS IN ONE REPLY"*) | its own |

## 4 · OPEN WITH THE PO

**None open at writing** — P1–P7 were answered 2026-09-24. One offer made, not a question: keep
half-filled forms across a session expiry (today only Move-in's server draft and Parked forms
survive).

## 5 · QUEUED, NOT DISPATCHED

US-English round 2 (~373 backend strings + *standing charge → base charge*, *takings → cash
taken*, *chase → follow up*, *public holiday → holiday*, *query → question* — decided in the log);
`DEF-INT-5562` (~40 failure panels pass a no-op *Cancel*); `DEF-CUS-6419` (phone numbers print as
typed); `DEF-NOT-6355` (per-channel language setting read by nothing); `DEF-NOT-6379`.

## 6 · TRAPS THAT BIT TODAY

Migration numbers collided twice (customers 0066/0067/0068, payments 0042/0043) — check the leaf
immediately before pushing. Defect ids collided repeatedly — `allocate.py … --verify` at push, every
time. A red that appeared in another module's suite after a rule changed (`DEF-CWP-6424`) had no
owner until the coordinator filed it: **read every red you did not cause and file it.**


---

## 7 · STOPPED HERE — 2026-09-24, BY THE PO (read this before §3)

PO, verbatim: *"lets stop it here"*, then *"stop all tasks and commit all pending work"*, then
*"we will merege this pr in defaul branch and then start from default branch"*. **All lanes are
stopped.** §3's table is history: every lane there is either finished (on the branch) or stopped.
**The four stopped lanes' unfinished work is in `12-governance/wip-2026-09-24/`** as patches with a
README naming each one's base commit and what is left — apply, finish, prove, push, delete. The
branch was left with `tsc --noEmit` clean.

**Work never started (§5 still stands):** US-English round 2 · `DEF-INT-5562` · `DEF-CUS-6419` ·
`DEF-NOT-6355` · `DEF-NOT-6379` · a company's Tax ID not stored on a request · the SSN hint after a
re-type · reds with no owner: `DEF-BIL-6456`, `DEF-RBS-6457`, `DEF-CUS-6458`, `DEF-CUS-6433`,
`DEF-CUS-6426`, `DEF-PAY-6463`. **Waiting on the PO:** two confirmations — card/bank payments read
*Digital* (old demo rows keep *Counter*), and a bill with no mailing address prints to the property.

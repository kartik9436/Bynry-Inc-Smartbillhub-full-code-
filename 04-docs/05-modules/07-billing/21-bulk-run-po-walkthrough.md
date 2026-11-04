# Bulk bill run — the PO's walk-through (build plan C3)

Status: **READY FOR THE PO, NOT YET WALKED** (close-out lane, 2026-10-01; fixes re-photographed
2026-10-02). Every step below was clicked and photographed. The seven things the first walk found wrong
(`DEF-BIL-9004`–`9010`) are fixed, so **no step is marked STOP any more**. Nothing here asks you to rule
anything.

**Which build to look in:** **2.439.1 or later**. The number is printed at the bottom of the left menu.
Each step names two screenshots: the first walk's (on **2.437.2**, kept as the record of what was wrong)
and the re-walk's, named `after-…`, taken on **2.438.2 to 2.439.1** as each fix landed.

**Which world:** the 40,000-account utility, *Brazos Bend Utilities*. It holds one September run that was
already sent: **RUN-0002, 40,008 bills, $7,371,531.12, due 10/22/2026**. Steps 1–4 look at that run. Steps
5–11 start the **October** run on the same 40,015 accounts. Sign in as **Dana Whitfield**. The walk needs a
fresh copy of the world (see the end of this page), because pressing *Start checking* writes to it.

**What this walk proves, and what it cannot.** The tracker (`17-bulk-bill-run-tracker.md`) moves a row to
*Walked* only when you have seen it in a browser on a named build. After this walk, tell us which steps
looked right; we record each row against **2.439.1** and the steps you saw. Nothing is marked *Walked*
until you say so.

## Part A — the September run that was sent (40,008 bills)

**1 · Find the run.** Click **Billing**, then the **Past billing runs** tab.
You should see RUN-0002, *J72-RIVERSIDE*, 09/01/2026 – 09/30/2026, **Issued**, value **$7,371,531.12**.
The counts print with a comma: **40,008**, and **40,017** bills issued (fixed, `DEF-BIL-9007`).
Screenshots: `08-qa/screens/bulk-run-closeout-2026-10-01/after-01-past-billing-runs-1440.png`
(before: `01-past-billing-runs-1440.png`)

**2 · Open it.** Click **RUN-0002**. It opens on step 4, *Send*, with all four steps ticked.
You should see **40,008 bills sent**, Total **$7,371,531.12**, Due **10/22/2026**, Meter reads **Locked**.
The total appears in about 1 to 1.6 seconds; *Locked* a moment later.
The card on the right says **"40,008 bills sent"** under the total (fixed, `DEF-BIL-9008`).
Screenshots: `after-02-sept-sent-card-1440.png` (before: `02-sept-sent-card-1440.png`)

**3 · Who was not billed.** Scroll to **Not in this run** and click **Held 7**.
You should see 7 accounts held, each *Waiting on a decision*, plus **Nobody to bill 1** (Unit 112, no
account). 40,008 billed + 7 held = 40,015 accounts, the number the run started with. The heading reads
**7 accounts · 1 unit · pending** (it said *1 units* before, `DEF-BIL-9008`).
Screenshots: `after-03-sept-not-in-this-run-held-1440.png` (before: `02b-sept-not-in-this-run-held-1440.png`)

**4 · What the clerk decided.** Click the **Check report** tab at the top of the step.
You should see **Accounts checked 40,015 · Ready 40,008 · Blocked 0 · Need a decision 7**, then one line
per account with its problem and the answer given, for example AC-2026-00003, *No reading*, *Estimate (all
No reading)*, with who and when. It is read only: the run is sent.
Screenshot: `02c-sept-check-report-1440.png`

## Part B — the October run (40,015 accounts)

**5 · Scope.** Click **Billing → Start a billing run**. Type the run name *October 2026 · Riverside*, pick
cycle *J72-RIVERSIDE · Riverside*, period **10/01/2026 – 10/31/2026**, bill date **11/01/2026**, days to
pay **21**, template *Standard bill · v1*.
You should see, within about a minute: **2 warnings. You can still start.** (the period ends after today;
1 unit has nobody to bill), *Continuous — follows RUN-0002*, and on the right **Units 40,016 · Accounts
40,015 · Regular 40,015 · Master 0 · Meters 90,022**, **Last run total $7,371,531.12**, Due **11/22/2026**.
Screenshot: `03-oct-scope-filled-1440.png`

**6 · Start checking.** Press **Start checking**.
You should see **Checking accounts** at once, with **no Price button**, then its count moving:
*Checking accounts 1,400 of 40,015* about 30 seconds in. Leave and come back and it is still there.
The whole Check took **13 to 18 minutes** on our machine (two billing workers, a machine busy with
other work). Fixed: `DEF-BIL-9004`. Before the fix this step read *"Checked 0 accounts"* with a red
**Price 0 accounts** button for 20 seconds or more.
The re-walk photographed this by pressing **Check again** on the October run (the run already existed);
the screen is the same one *Start checking* opens. It appeared 1.3 seconds after the click.
Screenshots: `after-06-checking-at-once-1440.png`, `after-06b-checking-progress-1440.png`
(before: `defect-start-shows-price-0-accounts-1440.png`)

**7 · The Check's answer.** When it finishes you should see **Checked 40,015 accounts**, **Blocked 2**,
**Need a decision 40,013**, **Ready 0**, and on the left **No reading 40,010** (October has no meter readings
in this world yet), *Disputed reading 1*, *No plan 2*, *Price changed mid-period 4*.
(The re-walk's photograph is of a Check done after step 9's answer was saved, so it reads **Ready
40,009 · Need a decision 4**; the answer for all is remembered across a Check again.)
Screenshots: `after-07-check-results-1440.png` (first walk: `03b-oct-check-results-1440.png`)

**8 · Open No reading.** Click **No reading** on the left.
You should see the 40,010 accounts, a page at a time, with **Answer for all 40,010: Estimate · Hold · Bill
base, usage later**, *Estimate* already highlighted from Billing settings. The line under the heading
says **40,010 accounts** (it said *80,015*, counting meters, before `DEF-BIL-9005`). While *Estimate* is
the answer, the bar says **"Estimate needs a figure per account. Or choose another answer."**, which is
why Price does not count those accounts yet (`DEF-BIL-9006`).
Screenshots: `after-08-check-no-reading-answered-1440.png` (shows the pane after step 9; before:
`04-check-no-reading-1440.png`)

**9 · Answer for all.** Click **Bill base, usage later**.
You should see every row read *For all: Bill base, usage later*, **Ready 40,009**, **Need a decision 4**,
and the button become **Price 40,009 accounts**. One click answered 40,010 accounts.
Screenshot: `05-check-answered-for-all-1440.png`

**10 · Price.** Press **Price 40,009 accounts**.
You should see **Reading accounts — 3,500 of 40,015**, moving, while the bills are prepared, and then
*Calculating bills — n of 40,009*. Leave and come back while it runs and the run opens on the same
progress (*Reading accounts 4,900 of 40,015*), not on Sign off. Fixed: `DEF-BIL-9010`; before, it read
**"0 of —"** for about 11 minutes and a re-open landed on Sign off with dashes. The whole calculation
took **about 20 minutes** on our busy machine.
Screenshots: `after-09-calculating-reading-accounts-1440.png`, `after-10-reopened-mid-calculate-1440.png`
(before: `06-calculating-1440.png`, `07-calculating-reopened-on-sign-off-1440.png`)

**11 · Sign off.** When it finishes the run opens on **Sign off**.
You should see **Bills 40,009 of 40,015 accounts**, **this run's charges $1,270,167.00**, **amount due
$8,641,962.32** (it carries September's unpaid balances), due **11/22/2026**, and **Failed to draft 0**.
40,009 billed + 2 blocked + 4 held = 40,015. Every bill carries base charges only, no usage: that is what
*Bill base, usage later* means, and each account's usage comes on its next bill.
Sewer is priced from water's usage, so when water's usage waits, sewer's usage waits with it and only
sewer's base is billed now.
Fixed: `DEF-BIL-9009`. Before the fix this step read **Bills 4, $32.00, Failed to draft 40,005**; a first
fix still left **40,004** accounts failing on sewer, and the second fix cleared them.
Screenshots: `after-11-signoff-1440.png` (before: `08-oct-sign-off-1440.png`)

**Send** is not pressed on the October run in this walk. Step 2 is what a sent run looks like.

## What to tell us after the walk

For each step: *looked right*, *looked wrong* (say what), or *did not look*. We record it in the tracker
against build 2.439.1. No step is known to be wrong today.

## Setting up the world (for whoever runs the walk)

The PO's walk needs its own copy, because *Start checking* writes to the database. On the PostgreSQL 16
cluster at `127.0.0.1:55433`:

1. `createdb -T sbh_s14_40k <name>` — the 40,000-account world, September sent. Never write to
   `sbh_s14_40k` itself.
2. `manage.py migrate` on the copy as the database owner. On 2026-10-01 it was six rating migrations behind
   the tip (`0050`–`0055`).
3. Run the API as the RLS-enforced role `sbh_b27` (gunicorn, 3 workers, 60 s), a Celery worker on the
   `billing` queue with a broker, and `07-frontend/server.mjs` in front of a fresh build.

The lane's own copy, `closeout_40k`, holds the October run from this page (RUN-0003, 40,009 draft
bills, not signed off, re-checked after its drafts while being photographed). Do not walk on it.

# The wiring gap — why "built is not wired" keeps happening, and what closes it

**PO question, 2026-08-16, verbatim:** *"your backend might be working, but wthout
it connected to screens it os fnow use and thats what we are finding again and
again … how do we resolve these issues?"*

They are right, and this file exists because the answer is longer than a chat
reply and the next agent needs it. Hard-won law 2 already *names* the failure.
**This file explains why our checks cannot see it, and what would.**

---

## 1 · The scale of it

Five occurrences at **whole-module scale** in one release — billing, payments,
ledger and notifications each shipped a complete, tested engine behind no route
at all, and `06-backend/config/urls.py` records each. Notifications was **7,084
lines of tested engine behind an `api.py` of 72 BYTES.**

Then on 2026-08-16, a sixth of a new kind: **the "Start this run" button on the
bill-run wizard is enabled, issues no request, and shows no error.** The endpoint
behind it returns `201 Created` when called directly. The wizard renders. The
engine works. Nothing joins them.

## 2 · Why every check we own says it is fine

**Nothing we own looks at the running product.** Everything measures CODE:

| What it checks | What it proves | What it cannot see |
|---|---|---|
| 3,031 backend tests | the engine computes correctly | whether a button calls it |
| 1,250 frontend tests | a component renders when HANDED data | whether anything hands it any |
| 27 merge-blocking gates | structure, rules, money, isolation | rendered output |
| Golden money tests | the frozen figures are right | that a person can reach them |

**All 27 gates were green, golden was 33/33, and both suites passed, while the
Finance screen was dead and the billing button did nothing.**

Two specific blind spots, stated plainly:

* **A component test mounts a screen with data passed straight in.** It never asks
  *"does anything in the product pass this?"* — that is DEF-129's whole shape and
  G13 was built for the prop version of it. G13 cannot see a HANDLER that calls
  no endpoint.
* **An honest deferral is invisible in aggregate.** An engineer writes
  `E=deferred(no-frontend-half)`, which is TRUE and CORRECT, and nothing adds the
  honest deferrals up. R2's entire shape was 66 such stories.

## 3 · What has actually found it — all three, every time

1. **Loading the page.** On 2026-08-16 alone: the Finance crash, the dead billing
   button, an entire audit screen blanked by a two-file import cycle (DEF-175)
   while TypeScript, eslint and 1,250 tests all passed.
2. **The PO asking a question.** *"is this on screen or backend only?"* and *"are
   we able to generate bills from screen now?"* each found a critical fault that
   the session's own reporting had missed.
3. **The unreachable-stories register** (`10-scripts/gates/surface_debt.txt`) — a
   hand-maintained count with a merge-blocking gate. It is why that number went
   **66 → 9** rather than sitting at 66.

**Note what is NOT on that list: any automated check of the running product.**

## 4 · What closes it — three things, in order of value

### (a) A check that CLICKS — the highest-value work available

Sign in to a `load_sample_data` tenant, visit all 19 sidebar destinations, and
**press every primary button.** Fail if a screen renders an error boundary **OR
if a click issues no network request.**

**The second clause is the one that matters.** A button that does nothing is
invisible to everything else we own. This check would have caught the billing
button, the Finance crash and the blank audit screen — all three of today's.

It is cheaper than it sounds: `07-frontend/src/routing/sidebarReachability.test.tsx`
already enumerates all 19 destinations against the real route table. It simply
never renders them against real data, and never clicks anything.

**Prove it RED on the dead billing button before trusting it green (law 7).**

### (b) Close the "proved" gap

Same root cause, wider net. Measured 2026-08-16: **304 journeys declared, 52 with
a script that runs, 252 never written.** 156 stories are cited by any journey;
only 92 by one that executes.

Writing the 51 unwritten journeys that would add coverage takes `proved` from
**77 to ~141 stories** — with no new features and no PO decisions. Beyond ~60% the
ceiling is structural: **102 stories are named by no journey at all.**

**The gap between `built` (62%) and `proved` (30%) is the reading, not either
number: we have built roughly twice as much as we have ever watched a person use.**

### (c) Treat "the screen half is deferred" as a defect, not a note

Making the unreachable count **public and merge-blocking** is what moved it 66 → 9.
That discipline worked and should be extended one step:

**A screen that EXISTS but calls nothing is the next form of the same lie**, and
today proved we have no way to see it. `surface_debt.txt` answers *"has this story
a route?"* Nothing answers *"does this control reach its endpoint?"*

---

## 5 · A worked example of an honest zero, so it is not mistaken for this

Settings → Company reads **"0 sample records loaded"** while listing every block
as LOADED, over a tenant holding 137 invoices. **That is not a broken counter and
must not be "fixed" by making it count rows.**

`BR-TEN-057`'s `is_sample` tag needs a column on six tables owned by `metering`
and `assets`, and `tenancy` **may not edit another module's tables** (B1,
BR-TEN-013). So the product genuinely **cannot tell** which rows are sample rows,
says 0, and marks the block lines advisory. `seam_known_gaps.txt` parks it with an
`absent=` guard that expires the moment the column arrives.

**It is honest and it reads as broken** — which is its own, smaller defect, of
wording rather than of wiring. The distinction matters: the fix is a sentence, not
a counter.

---

## 6 · The seed data, since it is the same question

**No cron job. No background worker. No scheduler.** `POST /settings/sample-data/seed`
runs inline, and Settings → Company has **Load sample data** / **Remove sample
data** buttons that call it. Verified in a browser 2026-08-16.

**It is deliberately NOT automatic at signup** (BR-TEN-064 — *a human asks,
always*): a real utility signing up should not silently receive 48 fake customers.

**Why it did nothing for a new tenant until 2026-08-16:** the orchestrator, the
panel and all eight module seams existed and **not one module implemented
`seed_sample_records`** (DEF-153). Every block reported success over zero rows.
Eight documented seams, no implementation — the wiring gap again, one layer down.

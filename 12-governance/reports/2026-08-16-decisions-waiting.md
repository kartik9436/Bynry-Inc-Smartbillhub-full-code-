# Decisions waiting on the Product Owner — 2026-08-16

**Eleven decisions, gathered from six build lanes.** Each is written the way the
standing instruction requires: **a rule and a worked figure in plain English,
never an ID to go and look up.** The ID is at the end of each row so an engineer
can find it, and you never have to.

**None of these is a guess we are asking you to bless.** In every case the
product currently *refuses by name* or *says so on screen* rather than choosing —
which is why nothing is silently wrong today, and why each one costs a little
until it is answered.

---

## The four that block a utility from billing correctly

### 1 · Trash — a service with no meter

**A trash charge is a flat $18.00 a month and there is no meter to read.** The
bill run was fixed today so it no longer refuses those accounts, but nothing
signs *what a flat charge means for a service that normally prices by usage*.

**What it costs while unanswered: $1,728.00 across the demo utility** — trash
reaches no bill at all.

| | Option | What happens |
|---|---|---|
| **a** | A service with no meter bills its fixed charge and nothing else | Simple. A water meter nobody installed would then quietly bill $0.00 instead of refusing — the opposite error |
| **b** | The PLAN says which services are unmetered; only those skip the reading | Safer, and one more thing to set up per plan |
| **c** | Something else | |

*(OQ-246)*

### 2 · A base charge can be typed in two places

It can be set **on the plan** and **on the rate schedule**. When both are filled
in and they disagree, nothing says which wins.

**Today: that account's bill refuses by name rather than picking one.** Which is
right, but it means such a utility cannot bill at all.

| | Option |
|---|---|
| **a** | The plan wins — it is the customer-facing agreement |
| **b** | The rate schedule wins — it is the priced instrument |
| **c** | Refuse, as now, and make the screens prevent both being filled |

*(OQ-238)*

### 3 · Sewer at a percentage of water — before or after rounding

When sewer is billed as 40% of water, is the 40% taken on **the water figure the
bill prints**, or on **the unrounded number behind it**?

Pennies per bill, on every bill, forever — and the two answers drift apart over a
year of statements.

| | Option |
|---|---|
| **a** | On the printed water figure — a customer can check the bill with a calculator |
| **b** | On the unrounded figure — more accurate, and the bill will not appear to add up |

*(OQ-232)*

### 4 · A bill covering part of a month charges a whole month's standing charges

**On the frozen worked example a 20-day window's standing charges should be
$24.51 and come to $38.00 — the customer pays $13.49 too much.** The bill adds up
perfectly either way, so nobody would find it by looking at one.

The rule that divides those charges is finance-signed and untouched. What is
missing is **the number to divide by when there is no billing cycle**.

| | Option |
|---|---|
| **a** | The customer's own cycle length (~30 days) |
| **b** | The calendar month the window falls in |
| **c** | The window's own length — *this is today's behaviour and it is why the charge is full* |

**The warning is on screen before a clerk creates the bill**, and a test fails if
it ever disappears while still true. *(OQ-242)*

---

## The three about what a customer receives

### 5 · A one-time bill has no cycle, so it has no due date

A due date is the bill date plus **the cycle's** payment terms — and a one-time
bill belongs to no cycle.

**On a $184.20 move-out bill dated 6 August, the three plausible answers put it
due 27 Aug, 5 Sep, or the day it printed. The late fee is $8.13.**

Today the product **refuses to send it** rather than guess, and the screen says
so before the clerk starts. *(OQ-241)*

### 6 · A customer disputes a reading the bill already used

The dispute flow is signed and built: a clerk flags it, and the **next** run skips
that account. The signed rule says nothing about **the bill that already went
out** — which is the ordinary case, because people dispute a reading *because they
got the bill*.

**Today: the dispute records, the next run skips the account, and the bill already
sent stays issued, stays due, and its late fees keep running.** No credit, no
pause, no automatic correction was invented. *(OQ-245)*

### 7 · The Senior plan discount

The demo utility's spec asks for three rate plans, the third a discounted
"Senior" variant. **No signed document says the discount.**

**10% versus 20% is about $9 a month on an ordinary bill.** The plan is unseeded
until you say. *(OQ-240)*

---

## The two about what a screen tells staff

### 8 · What "the customer accounts add up to" should mean

The Finance screen's tie-out is a **release blocker**: it proves the books agree
with the bills.

Read literally, the signed rule compares receivables against a column **nothing in
this product has ever written** — so the screen would report *"difference
$152.32"* on a **perfectly healthy** utility, from its first day.

**A blocker that fires when nothing is wrong is the one everyone learns to
ignore.**

| | Option |
|---|---|
| **a** | Compare against the register a clerk can actually open — gives **$0.00 difference** on a healthy utility *(what is built)* |
| **b** | Compare against the empty column, as written |

### 9 · Brought-forward balances make the ageing report short

If a utility moved to us from another system, its opening balances are in the
books but on **no bill we issued** — so the ageing bands are short by exactly that
amount.

| | Option |
|---|---|
| **a** | Run, and say so in words on every report *(what is built)* |
| **b** | Refuse to run until those balances are loaded |

---

## The two housekeeping ones — cheap now, expensive later

### 10 · Ratify the report centre's names

`GET /reports` and five key strings are not named in any signed document; they
were derived from existing filenames. **Nothing is blocked.** But a key ends up
inside bookmarks, saved schedules and downloaded filenames — **renaming later
breaks a saved link and a file someone has already filed.** *(OQ-247)*

### 11 · Add a check for circular imports

A two-file import cycle **blanked an entire screen today** while TypeScript, the
linter and 1,250 tests all passed. Nothing in the 27 merge-blocking checks reads
how files reference each other; `madge --circular` catches it in seconds.

**Adding a merge-blocking check is a process event, so it is proposed rather than
granted.** It would be proved to fail on today's defect before being trusted.

---

## What is NOT on this list, deliberately

Two live faults are being fixed right now and need no ruling — **the Finance
screen crashes**, and **the "Start this run" button is wired to nothing so a
utility cannot bill from the screen at all.** Both were found by the PO asking a
question, not by any check we own.

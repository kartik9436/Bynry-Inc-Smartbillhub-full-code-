# What a person can actually do — 2026-08-16, second measure

The companion report counts stories. **This one counts jobs**: for every task a
utility's staff perform, can a person sit down and do it today?

**⚠ THIS VERSION CORRECTS THE MORNING ONE ON THE MOST IMPORTANT ROW.** The
earlier report said a person could *"run a billing run and issue real bills — YES,
proved by clicking."* **That was true of an earlier fixture and I restated it as
though it held for the seeded demo tenant. It does not.** The button that starts
a billing run issues no request at all. A click proof is evidence only about the
tenant, the build and the data it was performed against, and it expires when any
of the three changes.

Three answers only: **YES** (end to end) · **PARTLY** (with the blocker named) ·
**NO** (no way in).

---

## Setting up the utility

| The job | Today |
|---|---|
| Sign up and create my utility | **YES** |
| Sign in, recover a sign-in | **YES** |
| Company details, services, units of measure | **YES** |
| Add staff and give them roles | **YES** |
| Numbering, routes, cycles, holidays | **YES** |
| See everything anyone has done | **YES** |
| **See whether data retention has ever run** | **YES** — new today. It says *"never run"* as a finding with its reason, and states plainly that archived does **not** yet mean off-site |

## Prices

| The job | Today |
|---|---|
| Build a plan | **YES** |
| Price flat, tiered, time-of-use, %-of-water, capacity, demand | **YES** — all six |
| Say which meter register each time-of-use window reads | **YES** — new today. Without it the same meter bills **$88.60 or $122.40** |
| Price a **seasonal** tariff | **NO** — the screen says so rather than accepting a configuration nothing can price |
| Taxes and tax authorities | **YES** |

## Places, meters, customers

| The job | Today |
|---|---|
| Premises, units, streets | **YES** |
| Register, install, replace, retire meters (incl. bulk import) | **YES** |
| Open an account, move in, move out, change plan | **YES** |
| Import accounts in bulk | **YES** |
| One customer's whole picture — balance, ageing, bills, payments | **YES** |

## Reading meters

| The job | Today |
|---|---|
| Import readings; see what is flagged and decide | **YES** |
| Estimate a reading that could not be taken | **YES** |
| **Dispute a reading** | **YES** — new today. A reason is required, and the next bill run **refuses that account** rather than billing it as agreed. ⚠ What happens to a bill *already sent* is unruled: it stays issued, stays due, late fees keep running, and the screen says exactly that |
| **See solar import and export as a pair** | **YES** — new today. 684 kWh delivered against 120 kWh fed back. **The two are never subtracted**; that subtraction is the solar credit, which is not built, and a test fails if "564" ever appears |

## Billing

| The job | Today |
|---|---|
| **Run a billing run from the screen** | 🔴 **NO — the button does nothing.** Enabled, no request, no error, no message. The endpoint behind it returns 201 when called directly. This is the product's central action |
| Read a bill as the customer sees it | **YES** — including the tenant's own custom fields |
| See where a bill was sent | **YES** |
| Check a bill ties out to its charge lines | **YES** |
| Fix a bill, credit it, re-issue | **YES** |
| **First, final, ad-hoc, back-dated or penalty bill** | **YES** — new today. Account E2E-10001, 1 Aug–1 Sep: **$174.10 + $14.36 tax = $188.46**, and a second identical attempt is refused by name |
| Bill **sewer** (a % of water, no meter) | **YES** — fixed today. **93 lines, $2,979.68** at the frozen figure |
| Bill **trash** (flat, no meter) | 🔴 **NO** — **$18.00/month, $1,728.00 across the demo.** Needs one ruling, not code |
| Budget billing | **YES** |

## Money in

| The job | Today |
|---|---|
| Record a payment; allocate it correctly | **YES** |
| Bounced cheque, reversal, refund | **YES** |
| Chase what is owed | **YES** |
| **Write a payment plan** | **YES** — $267.30 less $50 down over six is **five at $36.22 and a final $36.20** |
| Approve a write-off | **YES** |
| Deposit batches; import a bank statement; reconcile | **YES** — including the card day that will not tie because the processor kept a fee |
| **Record post that came back** | **YES** — new today. One envelope from the bill it went out with, or the whole stack at once. Paper only; an email row says why it is greyed |

## The books

| The job | Today |
|---|---|
| Revenue and receivables | **YES** — the screen **crashed this morning** and is fixed and verified rendering |
| General ledger · tax remittance · month close · export | **YES** |
| Supplier invoices; bought vs billed | **YES** |
| **See revenue by address** | **YES** — new today. 500 Main St $247.87 · Oak Grove $16.42 · Marina Bay $289.40, adding to the $553.69 that previously could not be attributed |
| **Prove the books agree with the bills** | **YES** — new today. *The books say $152.32, the customer accounts say $152.32, difference $0.00.* On a fault: *books $0.00, register $153.50, difference −$153.50, **Release blocked*** — with no way to dismiss it |
| Have a **deposit** appear in the books | 🔴 **NO** — a $150.00 deposit is in the customer's record and **nowhere in the books**. The trial balance still foots, because the entry was never made on either side |

## Telling customers things

| The job | Today |
|---|---|
| See what would be sent; re-queue a failure | **YES** |
| See which letter a tone actually sends | **YES** — **Firm** sends the *10-day regulated disconnection notice*; **Final** the *48-hour certified letter* at real postage |
| **Send a past-due reminder or a payment receipt** | **YES** — new today, and **no utility had ever been able to produce a single letter before**. Both use the design pack's exact sentences, and a test checks them against that document |
| **Produce a disconnection notice** | **PARTLY** — the machinery is built; the wording is three questions with the PO |
| Actually send an email or SMS | **NO** — by ruling. Everything queues |

## Reports

| The job | Today |
|---|---|
| **Browse a library of reports** | **YES** — new today. 23 reports in three groups; **10 open and work** |
| AR ageing · billing register · revenue by service · payments by method | **YES** — each computed here, each stating its basis |
| The 13 that cannot be produced | **Greyed out and not clickable, each saying why.** 23 identical tiles with 13 opening onto empty tables would tell a utility *"nobody is 90+ days overdue"* when the truth is *"we cannot tell you"* |
| Group by premises | **YES** — the dimension landed today |
| Schedule a report by email | **NO** — rides the send queue, out by ruling |

---

## The short version

**A small water utility could run its month on this — except for one thing.**

It can set itself up, price six kinds of tariff, register meters and customers,
take and dispute readings, take money, chase debt, bank it, reconcile it, report
on it and close its books.

**Three things stop it:**

1. 🔴 **A clerk cannot start a billing run from the screen.** The button does
   nothing. Everything behind it works. This is the single blocker.
2. 🔴 **A utility with trash cannot bill it** — $1,728.00 across the demo. One
   ruling, not code.
3. 🔴 **Deposits never reach the books.**

**And one that blocks nothing but should be known:** nothing is ever *sent* to a
customer. Everything queues, by ruling.

# What a person can actually do with the product — 2026-08-16

The other status report counts stories, tests and gates. **This one counts jobs.**
It asks one question of every task a utility's staff actually perform: *can a
person sit down and do this today?*

Measured from the **61 screens the application routes** (`07-frontend/src/App.tsx`)
plus the faults found by running the product, not from story records.

Three answers only:

- **YES** — a person can do it end to end.
- **PARTLY** — they can start, and something specific stops them. It is named.
- **NO** — there is no way in.

---

## Setting up the utility

| The job | Today | What that means |
|---|---|---|
| Sign up and create my utility | **YES** | Public pricing page → signup wizard → the tenant provisions itself |
| Sign in, recover a sign-in | **YES** | |
| Enter company details, services, units of measure | **YES** | All Settings tabs |
| Add staff and give them roles | **YES** | |
| Set numbering, routes, cycles, holidays | **YES** | Holidays seed two years ahead automatically |
| See everything anyone has done | **YES** | Audit viewer, filterable, deep-linked per record |

## Prices

| The job | Today | What that means |
|---|---|---|
| Build a plan | **YES** | |
| Price flat, tiered, time-of-use, %-of-water, capacity, demand | **YES** | All six, in the wizard, priced by the engine |
| Say which meter register each time-of-use window reads | **YES** | Built today. Without it the same meter could bill **$88.60 or $122.40** |
| Price a **seasonal** tariff | **NO** | The wizard offers it and the engine cannot price it; the screen says so rather than accepting a configuration that would fail |
| Set taxes and tax authorities | **YES** | |
| Offer a discounted plan variant | **PARTLY** | Nothing stops you building one; the demo's Senior plan is unseeded because no signed document says the discount |

## Places, meters, customers

| The job | Today | What that means |
|---|---|---|
| Record premises, units, streets | **YES** | |
| Register meters, install, replace, retire | **YES** | Including bulk import |
| Open an account, move a customer in | **YES** | |
| Move a customer out, final read | **YES** | |
| Change an account's plan | **YES** | |
| Import accounts in bulk | **YES** | |
| See one customer's whole picture | **YES** | Balance, ageing, bills, payments, notes |

## Reading meters

| The job | Today | What that means |
|---|---|---|
| Import readings from a file | **YES** | Staged: upload → validate → preview → commit |
| See what got flagged and decide | **YES** | |
| Estimate a reading that could not be taken | **YES** | |
| Work by route and by cycle | **YES** | |
| Dispute a reading | **NO** | The flag renders, and there is no way for a person to raise one |
| See an import/export pair for solar | **NO** | The rule is enforced; the two channels are never shown as a pair |

## Billing

| The job | Today | What that means |
|---|---|---|
| Run a billing run and issue real bills | **YES** | **Proved by clicking** — bill `BL-2608-000006`, `$70.90`, its locked printed copy, and a balanced entry in the books |
| See what is about to be billed before committing | **YES** | Five phases, with a break list and retry |
| Read a bill as the customer sees it | **YES** | Including the tenant's own custom fields, in a Remarks section |
| See where a bill was sent | **YES** | Built today. It previously said *"that queue is not built"* on every bill |
| Check a bill ties out to its charge lines | **YES** | Built today, in plain words, with both figures when they disagree |
| Fix a bill, credit it, re-issue | **YES** | |
| Bill trash or sewer | **NO** | ⚠ Neither will ever have a meter reading, and the run refuses every account waiting for one |
| Produce a **first, final, ad-hoc, back-dated or penalty** bill | **NO** | ⚠ All five engines are built and tested; none has a screen. This is billing's whole remainder |
| Budget billing | **YES** | |

## Money in

| The job | Today | What that means |
|---|---|---|
| Record a payment | **YES** | |
| Allocate it correctly across a bill | **YES** | Usage and base → tax → fees last |
| Handle a bounced cheque, a reversal, a refund | **YES** | |
| Chase what is owed | **YES** | Collections ladder with real tiers |
| Write a payment plan | **YES** | Built today. Instalments to the penny — **$267.30 less $50 down over six is five at $36.22 and a final $36.20** |
| Approve a write-off | **YES** | |
| Cut the day's takings into deposit batches | **YES** | |
| Import a bank statement and reconcile | **YES** | Including the card day that does not tie because the processor kept a fee |

## The books

| The job | Today | What that means |
|---|---|---|
| See revenue and receivables | **YES** | |
| Read the general ledger | **YES** | |
| Tax remittance | **YES** | |
| Close a month | **YES** | |
| Export to my accounting package | **YES** | |
| Capture supplier invoices and see bought-vs-billed | **YES** | The figure an accounting package cannot produce and this can |

## Telling customers things

| The job | Today | What that means |
|---|---|---|
| See what would be sent, and re-queue a failure | **YES** | Built today |
| See which letter a tone actually sends | **YES** | Built today, and it matters: **Firm** sends the *10-day regulated disconnection notice*; **Final** sends the *48-hour certified letter* at real postage |
| Actually send an email or an SMS | **NO** | By decision, not omission — R2 queues and sends nothing |
| Produce a disconnection notice or dunning letter | **NO** | ⚠ **No tenant has ever had a notice template**, because nothing creates one, so every one is refused at render |
| Design a bill layout | **NO** | Cut by ruling — five ready-made layouts, one always the default |

## Reports

| The job | Today | What that means |
|---|---|---|
| Read one account's ledger | **YES** | |
| Group by premises | **PARTLY** | The report answers *not available* honestly — no journal line records a premises, so the dimension does not exist to report on |
| Browse a library of reports | **NO** | Deliberately unbuilt: there is no report catalogue behind it, and a page drawn over one would be a confident empty report |
| Dashboard | **YES** | |

---

## The short version

**A small water utility could run its month on this today** — set itself up, price
its services, register its meters and customers, take readings, bill them, take
the money, chase what is owed, bank it, reconcile it and close its books.

**Four things stop that being true for every utility:**

1. **A utility with trash or sewer cannot bill at all.** Any service with no
   meter refuses the whole run. This is the largest gap by customer impact.
2. **No utility can send a disconnection notice or a dunning letter**, because no
   notice template exists to render from.
3. **No one-time bills** — first, final, ad-hoc, back-dated or penalty.
4. **Nothing is actually sent** to a customer — everything queues, by ruling.

**And one that blocks evaluation rather than operation:** the demo data loads
95 bills as **drafts**, so payments, journal entries and the finance screens have
nothing to show until that is fixed.

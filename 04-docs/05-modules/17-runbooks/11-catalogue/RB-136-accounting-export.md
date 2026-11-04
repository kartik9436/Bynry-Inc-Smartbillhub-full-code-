# RB-136 — Runbook 36 · Accounting export

**On screen a clerk sees “Month-end journal file.”** The definition title above is the name on its card; the screen name is the display name in the templates library and on every wireframe.

⚠ **THIS IS THE THIRTY-SIXTH RUNBOOK AND THE FIRST ADDED AFTER THE ORIGINAL 1–35.** Nothing is renumbered. It exists because the Product Owner's own list of the four integration areas — *accounting · payment provider · emails · GIS* — had a runbook for three of them and **not for accounting, which is first on their list** (`01-overview.md` §8, `10-execution-plan.md` §6 row 3). Those two documents say the gap cannot be filled without a fourteenth port; **that statement was superseded on 2026-09-06** and both are amended in the same commit as this card. See *Why this needed no change request*, below.

## What it declares

| | |
|---|---|
| **Kind** | Check |
| **Category** (one home, from the fixed list of sixteen) | Finance |
| **Tags** | Finance · Accounting |
| **Phase** | 1d — it reads only the ledger, and every read it needs exists |
| **Trigger** | Manual · Schedule |
| **Subject and unit of work** | Period · the **accounting month** |
| **Step modes** | set · per record |
| **Result blocks it composes** | Verdict · KPIs · Records · Downloads |
| **Ports it holds** | — (a Check holds none) |
| **Proves** | US-RBS-042 |
| **Waits on** | `DEF-RBS-4312` — the file is composed and has **no download address yet** |

> A Check is constructed with **no ports**, so a write is not refused at runtime — it is unavailable (`BR-RBS-002`, `TC-RBS-1`). **Producing a download is not a write to a business record** (decision log 2026-09-06).

## What it answers

**Can this month be handed to the bookkeeper as a file, and what could not go in it?**

What the utility does today is type figures off a screen into QuickBooks, by hand, every month. This produces the file they import instead — and, just as importantly, the list of what could not be exported, each row naming the screen that fixes it.

## The file — ruled by the Product Owner, 2026-09-06, verbatim

> *"A plain general-journal CSV — date, account code, description, debit, credit, reference. Every accounting system on earth imports this, usually after a one-time column mapping. Safest default."*

**Six columns, in that order.** Not QuickBooks' own import format, not Sage's — the interchange shape every package reads after a one-time column mapping by the bookkeeper. A QuickBooks-shaped variant is a **later addition, not a rework**, because the same rows feed it.

```
date,account code,description,debit,credit,reference
2026-07-31,1000,Cash,0.00,145.04,2026-07
2026-07-31,1010,Undeposited funds,262.99,0.00,2026-07
2026-07-31,1200,Accounts receivable,19279.27,0.00,2026-07
2026-07-31,4100,Electric usage,0.00,13697.71,2026-07
```

*(the first four lines of a real run on the seeded utility — 25 lines over three months, `$68,317.12` on each side)*

### The four decisions behind it, recorded and not re-opened

1. **Debit and credit carry TWO decimals.** Money is stored to four and displayed at two (hard rule 2), and **a file is a display surface**.
2. **One file is ONE currency**, `CHAR(3)`, and it is in the file's name. Two currencies would be two files and a new question — never a seventh column added quietly.
3. **The export never invents an account code, and this is the whole design.** Export every line that maps; **report** every one that does not, each naming its fix route. A file with a guessed account code is worse than no file: it imports cleanly, puts money in the wrong place, and nobody finds out until a reconciliation.
4. **An unbalanced file is refused, not exported.** Hard rule 5. Both sides are summed over what is about to be written; if they differ **the whole file is refused** and the difference is named (*"Off by $14.25 · 2026-07"*). An accounting system rejects an unbalanced journal anyway; catching it here means a clerk reads a sentence instead of a stack trace from QuickBooks.

## Scope — how the set is decided

| Row | Value | Control |
|---|---|---|
| Months | **All** | dropdown — one, several, or *all* |
| Books | All | value, not editable on this screen |
| Currency | USD | value, not editable on this screen |

**The domain is the months this tenant has actually posted into** (`BR-RBS-042` clause 2 — every domain is tenant-resolved and never hardcoded; a domain of *the last twelve months* would offer eleven empty files to a utility that went live in August). ***All* is stored as the word and resolved when the run starts** (clause 1): a utility that saves *all* in September and posts into October gets October on its next run, with nothing to reconfigure.

The scope function also answers the count on the setup screen: **3 months · 824 journal lines behind 25 exportable rows** on the seeded utility.

## Parameters

| Parameter | Value on the card | Control | Read-only because it lives in Settings |
|---|---|---|---|
| Months | All | dropdown (`window`) | — |

**One parameter, and that is deliberate.** Runbook 1 declares a *Raise work items* toggle that nothing reads yet; a knob nothing reads is dead UI (hard-won law 2), so a second one here would be a second dead knob rather than consistency.

## Steps

Source: **6 steps · all read.** Steps run in the order shown, and the order is the guarantee — by the time step 6 composes the file, the balance and the currency have both been decided and it reads their verdicts rather than re-deciding them.

| # | Step | What it does | Mode |
|---|---|---|---|
| 1 | Months | What this run covers, and whether anything is posted at all | `read · set` |
| 2 | Figures | One month's books, as the **ledger** publishes them | `read · per record` |
| 3 | Currency | One file is one currency, and it is `CHAR(3)` | `read · set` |
| 4 | Balance | Both sides summed over the whole file; refuse if they differ | `read · set` |
| 5 | Account codes | What has no account behind it — reported, never guessed | `read · set` |
| 6 | The file | Compose the six columns, or say why there is not one | `read · set` |

**Step 2 is the only per-record step and the month is why.** One month is one savepoint and one record row, so a period whose read fails does not take the other months' figures with it — which is exactly what hard-won law 14's savepoint is for on PostgreSQL.

## Guards — what it may never touch

- It is a Check, so it holds **no ports** and writes nothing.
- **It writes no journal line.** Only the ledger posting service does (hard rule 5), so this runbook can tell a bookkeeper the books do not foot and it **cannot post the correction**.
- **It computes no money.** Every figure is `apps.ledger.exports.export_preview` for the window — the same rows S43 renders. `apps/ledger/exports.py` says why in its own words: *"a second summation here would be a second answer to what did July hold, and the day the two disagreed the ERP would hold the wrong one."* A runbook that re-summed the journal would be that second answer, and it would be the one on the bookkeeper's desk.
- **It records no export batch and asserts nothing to an auditor.** `apps.ledger.exports.create_export_batch` is the recorded, idempotent handover; this is a working file a clerk may re-run any number of times. That difference is what settles the open-month question below.

## What could not be exported — the three shapes

| What | Weight | Why it cannot reach the file | Fix route |
|---|---|---|---|
| An account carrying movement with a **blank code** | Blocker | There is nothing to put in the *account code* column, and inventing one is the worst thing an export can do | Finance |
| A **place in the books with no account behind it** | Warning | Money of that kind cannot post, so it never reaches the journal and cannot reach the file | Finance |
| An account **missing the target's reference** | Warning | Empty for a plain CSV by construction — a CSV addresses an account by code and name — and still read, because the same list is what refuses on the day a tenant exports to QuickBooks or Xero | Finance |

**The seeded utility has three of the second kind**: *Accrued expenses · Accumulated depreciation · Allowance doubtful accounts*. A designation reaches a clerk **in words** and never as `allowance_doubtful_accounts` (B14 rule 32).

## The open-month judgment, stated rather than left to be inferred

`BR-LED-017` requires a **closed** period before the ledger's recorded handover — *"the ERP never receives numbers that can still move"*. **That rule governs `create_export_batch`, which writes a batch and asserts *this is what we sent for July, once*.** This runbook records nothing and asserts nothing, and the Product Owner named exactly **one** refusal.

**So an open month is a WARNING that still carries its file.** The verdict says *"Ready, with notes · 3 months open"*, in words, and the download is there. Withholding it on a refusal nobody ruled would make the runbook useless on every tenant until somebody presses Close — while the clerk goes on typing figures by hand, which is the problem it exists to solve.

## Produces

### The run, on the seeded utility (real figures, 2026-09-06)

**Ready, with notes — “1 to fix · 3 months open.”**

| | |
|---|---|
| **Lines exported** | 25 |
| **Blocked** | 1 |
| **File total** | $68,317.12 |
| **File** | `journal-2026-07-to-2026-09-USD.csv` |

| What | Affects | Weight | Fix |
|---|---|---|---|
| Some postings have no account. | 3 of the books · Accrued expenses, Accumulated depreciation, Allowance doubtful accounts | Warning | Finish the mapping → |

Debits `$68,317.12` = credits `$68,317.12`, over three months: July `$19,735.30` · August `$33,515.82` · September `$15,066.00`.

## Why this needed no change request

**The accounting export is two things and only one of them was ever blocked** (decision log, 2026-09-06):

| | Needs | Status |
|---|---|---|
| A runbook produces a file **a clerk downloads and uploads** | Nothing new — a Check, and `downloads` is one of the twelve blocks | **This card** |
| The product **pushes** the file to the accounting system itself | A **fourteenth port** — an outbound write the thirteen do not cover | Still a change request nobody has raised |

⚠ **AND THE UNBLOCKED HALF IS THE ONE THAT MATTERS FIRST.** The ICP is North American utilities to 40,000 accounts run by 10–20 staff. A utility that size does not typically hold a live API credential for its accounting system; **a bookkeeper exports a file and imports it.**

## What is owed — `DEF-RBS-4312`

**The file is composed and tested against real books, and no address serves it yet.** The only download addresses this module mounts are `GET /runbooks/runs/{id}/results/{done|not-done}.csv`, whose columns are the **nine record columns** of `result_files.COLUMNS` — *Subject · Subject type · Planned · Outcome · Amount · Currency · Decided by · Reason · Fix* — which carry **no date and no account code**, so a general journal cannot be expressed in them; and the route's `re_path` alternation makes a third file name a **deliberate 404**.

**What is owed is one address and one writer**, and both are small: a `results/journal.csv` row on `07-endpoints.md`, a third arm on the `re_path`, and a view that streams `accounting_export.journal_csv(...)` inside `stream_within_tenant_context` exactly as `run_result_file` already does. **`journal_csv()` and `file_name()` are public in the definition module for that caller.** Until then the `downloads` block names the file the day the address exists, and the run's report carries the composed bytes so nothing has to be recomputed.

⚠ **This is hard-won law 2's mirror — a live computation behind a dead door — and nothing in the repository can see it**: a downloads block's payload is `{id, label, format}` and the id is never resolved against a route. The prevention filed with the defect is a check that resolves every promised file id through `config/urls.py`, the way `test_us_rbs_003_endpoints.py` already resolves the eight routes.

## What was run, and on which vendor

| | | |
|---|---|---|
| `tests/test_us_rbs_042_accounting_export.py` | **21 passed** | in-memory SQLite (the default suite) |
| `tests/test_us_rbs_042_pg.py` | **4 passed** | **real PostgreSQL** — the module prints `vendor=postgresql` on every case, so a reader can tell a real green from a skipped one |
| `tests/test_us_rbs_015_conformance.py` | **70 passed** with this runbook registered | SQLite |
| `10-scripts/gates/g115_runbooks_import_census.py` | **PASS** — 38 files, 9 seams, 13 ports, **0 bound**, no dynamic import, 13 self-test sabotages bite | — |
| `tests/test_us_led_005_gl_designations.py` · `tests/test_us_led_016_export.py` | **59 passed, 2 skipped** — the two reads `ledger` adds for this runbook break nothing already there | SQLite |
| `10-scripts/render-checks/rbs-accounting-export.mjs` | **every check passed** | a real browser on a live stack |

**The PostgreSQL half proves the two things SQLite cannot say anything about**: a run in one tenant's context reads that tenant's books and nothing else — asserted as a **figure**, `598.69` and never `1,197.38`, because a cross-tenant read would double it and *"there is a total"* would sail past — and that step 2 really is per-record, running once per month inside the engine's savepoint, which a `set`-mode mistake would hide from every other case in the suite.

⚠ **AND THE FIXTURE ITSELF TAUGHT SOMETHING ONLY A REAL RUN COULD.** The first draft posted an electric month on both tenants; `lonestar` is *"the isolation tenant (Water only)"* and refused by name with `metering.service_not_enabled` — **in the fixture rather than in the assertion**, which is the least useful place for a test to fail. The service is a parameter now and the reason is written into the helper.

## The walkthrough — what was actually clicked, 2026-09-06

`10-scripts/render-checks/rbs-accounting-export.mjs`, against a live stack (Django on `:8091`, the built SPA on `:8092`, the seeded `brazosbend` tenant on real PostgreSQL). It opens the **file** and parses it, then drives the **screen**.

**The file** — `journal-2026-07-to-2026-09-USD.csv`, opened with a CSV reader rather than grepped, because a description like *"Tax payable — Local · Bexar County"* is one cell:

* the header is the six columns in the Product Owner's order;
* **25 rows** — a header alone is not a file, so the count is asserted;
* **every** debit and credit cell carries exactly two decimals, asserted per cell rather than on a total, because one four-decimal cell in twenty-five is what a total hides;
* **debits `$68,317.12` = credits `$68,317.12`**, summed as integer cents so the footing is exact;
* every row names an account code — none blank, none invented;
* no database id and no rule id anywhere in it (B14 rules 31 and 32).

**The screen** — `RBS-006`, signed in as a clerk:

* the server serves exactly four of the twelve blocks — `verdict · kpis · records · downloads`;
* the head carries the verdict's own sentence, *"1 to fix · 3 months open."*;
* the three KPI tiles drew, and **the tile total and the file total are the same number** — two answers to *what did this month hold* is the failure `apps/ledger/exports.py` names, and this is where it would show;
* the blocked row drew with all four columns, and its fix route resolves to a real `/finance` link — asserted by ADDRESS, never as a present string;
* the Downloads control is drawn;
* nothing internal reaches the clerk, and the page does not scroll sideways at 1440.

⚠ **ONE FINDING THE WALKTHROUGH PRODUCED, AND IT IS NOT THIS RUNBOOK'S: `DEF-RBS-4313`.** `RunResult.tsx` hoists a **leading** verdict block into the page head as its sub-line and uses **only `count`** — `word`, `tone` and `detail` are dropped. So a clerk reads *"1 to fix · 3 months open."* and **never learns whether the word beside it is *Ready to import* or *No file***, which for this runbook is the difference between a month they can hand to their bookkeeper and one they cannot. It affects every runbook, including runbook 1, and the check asserts the state AS IT IS and names the defect — a check that quietly stopped looking would let the day it is fixed pass unnoticed.

## Screens

`RBS-004` (setup) and `RBS-006` (result), both **renderers** — this runbook is one Python module and **no frontend code** (`RB-020`). Its four blocks are four of the twelve and no thirteenth is minted (`BR-RBS-021`).

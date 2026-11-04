# The move-out surface against its blueprint — the list, the record, and the wizard

| | |
|---|---|
| Read | `05-prototype/02 Accounts Menu Blueprint.pdf`, **the 281-page edition** — list p116–p117, record p117–p118, wizard p109–p116. Rendered and read AS IMAGES (B14 rule 42) |
| Against | `07-frontend/src/features/customers/MoveOutsTab.tsx` (875 lines) · `MoveRecordPage.tsx` · `06-backend/apps/customers/move_record_reads.py` · `move_out_settlement.py` |
| Product at | `2.310.3` on the beta |
| Status | **THE LIST IS PO-RULED** in this session. The record and the wizard are read and not yet ruled. |

⚠ **PAGE NUMBERS HERE ARE THE 281-PAGE EDITION.** The PO uploaded it on 2026-09-19 and it landed on this branch at `74a2e6b52`. The previous 242-page copy numbered these screens p098/p104/p105. **Anything citing those numbers is reading last week's drawing.**

⚠ **THIS EDITION STATES ITS OWN AS-BUILT GAP, WHICH THE OLD ONE DID NOT.** Every screen carries a line of the form *"REDESIGN — PUBLISHED 2026-09-12, DRAWN TO THE RULINGS IN §13, NEVER BUILT. TODAY: …"*. For this surface it says, verbatim: **"no move-out record page exists, and nothing in the product ties a shortfall back to a landlord"** and, of the wizard, *"the product's move-out has six steps, and its deposit panel carries no actions and its shortfall no step; both were put back here"*.

---

## 1 · The Move-outs list — RULED 2026-09-19

### What already matches, and it is more than any other list on this surface
**All NINE columns are built and correctly named** — Reference · Account · Customer · Unit · Move-out date · Step · Final read · Settlement · State. **And all three drawn KPIs exist.** Nothing to change in either.

### The KPI strip — PO: *"Drop it"*, twice
| Drawing | Product | Ruling |
|---|---|---|
| **Open** | built | keep; sub-line cut to ≤6 words |
| **Leaving this week** | built | keep |
| **Final reads due** | built | keep; *"nothing settles without one"* is RATIONALE — cut |
| — | **Shortfalls to decide** | **DROP** |
| — | **Refunds to pay** | **DROP** |

### The copy — PO: *"you ahve to follow our UI rules - this is correct screen - too much text"*
**Roughly 78 words of prose sit under the table and almost none of it is lawful.** B14 rule 32 gives one sentence per section; rule 33 puts RATIONALE at zero words on screen.
| On screen today | Ruling |
|---|---|
| *"Opens newest first. Click Move-out date for soonest."* | **delete** — instructions for a control that explains itself |
| *"A move-out that has not gone through yet is not kept anywhere, so this list shows only the ones already closed. An account whose move-out is still being arranged is open and still billing, and it is not listed here."* | **delete** — 45 words of pure rationale |
| *"A closed account stays on this list. Nothing takes it off, because the final bill that would finish it cannot be seen from here."* | **delete** — rationale, and it names an internal limitation |
| the Settlement cell's three stacked lines | **collapse to ONE** — see below |
| *"Step not recorded"* · *"Not readable here"* | **CHECK whether the data exists before changing the words.** An honest absence is not a copy fault |

### The Settlement cell — three lines where the drawing has one
The product renders `Deposit held $0.00` / `Outstanding $5.00` / *"No settlement yet — the final bill is not readable"*. The drawing renders **`Short by $186.40`** or **`Refund $42.15`** — one figure and its direction. The blueprint's own rule: **"Settlement is a direction, not a status. One of these owes the utility $186.40 and one is owed $42.15 back, and they are the same kind of row."** Three stacked lines are the opposite of a direction.

### The toolbar — PO: *"we need toolbar - as per our UI rules"*
⚠ **THIS SECTION READ *"toolkit remain same … a proposal to add the drawing's four filter chips was OVERRULED"* AND THAT WAS THE WRONG REASON FOR THE RIGHT ANSWER.** The chips are not refused because the PO preferred otherwise — they are refused because **B14 rule 12 already forbids that pattern**, and the drawing draws the pattern our own rule replaced. Recording it as a PO overrule leaves the next lane free to re-propose it the moment a drawing shows it again.

**Rule 12 verbatim** (`04-docs/02-decisions/14-ui-conventions.md` line 46):
`[Search…] [All | filter chips ×] [+ Filter ▾] … [▦ Columns]`. Filters are removable chips; All is the default.

**Rule 32 bounds the row:** the first row is rule 12's set plus the IS-9 export and nothing else.

| Rule 12's set | On screen today | Ruling |
|---|---|---|
| `[Search…]` | *"Customer, account #, unit, or address…"* | **add `reference`** — it is the first drawn column and a clerk cannot search it |
| `[All]` — the default | present | — |
| applied-filter chips, removable `×` | only a `Closed` filter is declared | **verify a chip with an `×` renders when it is applied** |
| `[+ Filter ▾]` | present | — |
| `[▦ Columns]` | icon alone | **glyph + the word** |
| `[⇩ Export]` | ⚠ **ABSENT — and this row said "present" until 2026-09-19** | **do not draw it.** `apps/customers/` has no `exports.py` and registers no `move-outs` resource, so `BR-SHL-010` keeps it unrendered and `DEF-1005` carries it. Drawing it wires a control to a 404 |
| the drawing's four fixed segments | absent | **correctly absent — DO NOT ADD** |

**Why the segments are gone, from the code that removed them.** `07-frontend/src/components/FilterBar.tsx`'s own docstring: the strip was *"permanently occupying the toolbar, with the applied state visible only INSIDE… a user could not remove one filter without first finding the right select."* That is the defect rule 12 was written against.

**`10-scripts/gates/g43_list_toolbar_contract.py` already checks this.** Run it rather than eyeball it — and run it the way `run_gates` runs it, not `python3 <gate>.py` (CLAUDE.md law 7: two gates were announced green through an entry point the suite never uses).

### The interaction — PO: *"you ahve to imporve th itneraction design - allow to open the move out request"*
| Drawing | Product | Ruling |
|---|---|---|
| the reference opens the move-out record | plain text | **make the row open** |
| the account number opens the account | plain text | **link it** — the account page exists |
| `↗ Open` per row | absent | **add** |

⚠ **AND THE THING IT OPENS DOES NOT EXIST.** But the backend is closer than the drawing's note suggests: **`move_record_reads.py` filters `MoveRecord` by reference and does NOT restrict on `kind`**, so the `/moves/{ref}` endpoint very likely serves a move-out already. `MoveRecordPage.tsx` was built move-in only — it contains no move-out branch at all. **So this is a front-end shape, not a new backend.**

---

## 1b · WHAT WAS BUILT, 2026-09-19 — commit `7b8695616`

**BUILT and pending a browser walk:**

| Ruling | Defect | State |
|---|---|---|
| three KPI tiles, not five | `DEF-CUS-5897` | built — both dropped tiles stay on the PAYLOAD with a note that they now have no reader, because deleting a served field is `DEF-CUS-3653`'s shape in reverse |
| ~78 words of rationale off | `DEF-CUS-5898` | built — the key is gone from all eleven catalogues; the empty state's helper came 16 words → 5 |
| Settlement collapsed to one line | `DEF-CUS-5899` | built, **but it still states no direction** — see below |
| Reference, Account and `↗ Open` open something | `DEF-CUS-5900` | built — all three through `tenantPath` |

**NOT BUILT, and each for a reason that is not this screen's to overrule:**

* **The head — all five items.** The `ACCOUNTS` kicker, the title **The register**, `10 tabs · Move-outs · N still open`, the breadcrumb, and dropping the `Accounts 82` count all live in **`AccountsListPage.tsx`'s single `PageHeader`, which serves all ten tabs.** Renaming it from the Move-outs lane retitles the page under nine siblings. `MoveOutsTab.tsx` renders `<div data-embedded>` and no head at all. Rule 40's 32px is already set inside `PageHeader`.
* **`[▦ Columns]` has no word.** The control is `components/ColumnChooser.tsx`, shared by every `DataTable`. Adding the word from here changes every list in the product on one screen's authority — which is B14 rule 38's own reasoning, one layer up.
* **`[⇩ Export]`** — absent by `BR-SHL-010`, as corrected in the toolbar table above.

**Both are now ASSERTED in the suite rather than left in a comment**, so the day either lands the case goes red and names it — hard-won law 2's mirror (`DEF-CWP-3925`): when you write a hold, write the test that fires when the hold expires.

### ⚠ The Settlement one-liner is blocked on the BACKEND, not on the front end
`move_out_settlement_cell` hard-codes `landing: None` and `complete: False` and serves **no figure**, so `Short by $186.40` is not renderable from what the server sends, and deriving it in the browser is what that file's §2 forbids on a path that starts a collections ladder. The direction branch IS built, guarded on landing **and** figure — both halves or neither — and is unreachable until a figure is served. **The cell is one line today and it names no direction.**

### The search prompt was FALSE for about an hour, and is now TRUE — measured, not assumed
⚠ **THIS SECTION READ *"The search prompt is CURRENTLY FALSE"* AND WAS STALE WITHIN THE HOUR.** It was written when only the front half of `DEF-CUS-5896` had shipped — the prompt naming `reference` in all eleven languages over a `move_outs_queryset` with no `move_no` leg.

**The backend leg landed in `db0068d3e`** (*"The Move-outs list can be searched by the reference it prints first"*), and a browser walk measured it against the live API rather than reading the code:

| typed | rows |
|---|---|
| `MVO-26-0001` | **1** |
| `MVO-26-9999` | 0 |
| `ZZZZNOPE` | 0 |

It is tenant-scoped on `move_records` itself and filters `kind='move_out'`, so a move-**in** number cannot surface a move-out row under a reference that row does not print.

⚠ **THE LESSON IS THIS FILE'S OWN, AND IT IS THE ONE CLAUDE.md REPEATS MOST.** A record that states a live condition rots the moment the condition changes, and **nothing re-checks a paragraph**. This one survived less than an hour and was caught only because a browser walk happened to read it. The fix that generalises: **where a note states a condition, name the check that settles it** — here, the three queries above — so the next reader can re-run it in ten seconds instead of believing a sentence.

### Two divergences stamped rather than silently taken
1. **The four segment chips** are drawn on p117 and deliberately absent. Rule 12 governs the toolbar; `FilterBar.tsx`'s docstring records the defect the strip caused.
2. **`↗ Open` is TEXT, and B14 rule 15 says row actions are icons with tooltips, never text links** — RATIFIED and G37-enforced. Built as drawn because the PO ruled it on 2026-09-19 and approved the identical control on Move-ins the same day; re-asking would be law 13's bug. Stamped as an exception in the file. G37 does not fire on it (a plain `<Link>` in a cell, not a `<ButtonLink>` inside `<RowActions>`).
3. The drawing's `Open` caption reads *"not yet closed"*. **That would be false about our data** — the tile counts move-outs that HAVE closed. Ours reads *"closed, not yet finally billed"*, five words, already inside rule 33.

### A SECOND RULING LANDED ON THIS LIST THE SAME DAY — the unfinished move-outs

**PO, verbatim `yes`**, asked whether the Move-outs list should show move-outs
that have not finished yet. `BR-CUS-1080` is the rule and `DEF-CUS-5919` is the
row; both landed in **2.313.1**, commit `39d49754f`.

⚠ **THIS SECTION SAID THE OPPOSITE UNTIL THEN, AND SO DID THE CODE.** The
divergence table below still reads *"the tile counts move-outs that HAVE
closed"* — true of the tile, which did not move — but the paragraph that
justified it (*"a move-out in flight is not recorded anywhere"*) had been false
since `CR-035`. `wizard_parks` carries `flow='move_out'` with a real `step`.
**It was a WINDOW and never a missing column.**

| Drawn on p117 | Product now |
|---|---|
| a second row, `MVO-26-0087 · 2 of 6 · In progress` | **built, with real data** — a `wizard_parks` draft, its own step, and `In progress` or `Waiting` off `waiting_on` |
| `Completed` in the STATE cell | **built** (`DEF-CUS-5901`) — display only; the stored value is still `closed` |
| a reference on the in-flight row | **stated absence** — only a move-IN draft is numbered while it is in hand (`CR-122-BRC06`). `OQ-CUS-12489` |
| `↗ Open` on the in-flight row | **built, to a different address** — `/move-outs/new?parked=<id>`, because there is no record to open |

### Still open on this list
* the 45-word absence is now the **Open tile's hover text** — pre-existing, unchanged, and arguably still rule-33 rationale on screen. **Worth a ruling; nobody has touched it.**
* **the three KPI tiles still count the CLOSED rows only**, over a list that now holds both kinds. Deliberate, and recorded in the decision log with its reasoning: the ruling is about which ROWS the list holds, and `open_means` still says in the server's own words what the figure is. **The check that settles it:** `GET /move-outs` → `kpis.open_means == "closed_and_not_yet_finally_billed"`.
* **the parked-drafts panel above the table is still mounted**, so one unfinished move-out is on that screen twice. `OQ-CUS-12488` puts it to the PO with each option costed; removing it reverses their ruling of 2026-08-26. **The check that settles it:** `grep ParkedDraftsPanel 07-frontend/src/features/customers/AccountsListPage.tsx`.

### ✅ CLOSED since this file was written
* **the browser walk at 1280 and 1440 is DONE** — `10-scripts/po20260919_move_outs_unfinished_walkthrough.mjs`, **42 checks passed at both widths** against a booted stack, with a parked move-out planted and removed (`brazosbend`: 0 parked before, 0 after). It reads each door's href out of the tag it is about, not off the page.
* **maintenance step 7 is written** — `2.313.1` across `package.json`, `pyproject.toml` and the changelog, and on screen in the sidebar.

⚠ **THE TWO BULLETS ABOVE WERE STALE WITHIN HOURS, WHICH IS THIS FILE'S OWN
LESSON FIRING ON ITSELF** — see the paragraph above the divergence list: *"a
record that states a live condition rots the moment the condition changes, and
nothing re-checks a paragraph."* Each surviving bullet now names the check that
settles it, which is the cure that paragraph prescribes.

## 2 · The move-out record — `/moves/{ref}`, marked **Proposed** (read, not yet ruled)

**Head:** `← The register` · `MOVE-OUT MVO-26-0088` · the customer's name · chips `Completed` + **`Short by $186.40`** + `Moved out 01/28/2026` · the address line.

**What happened:** Account closed · Unit · Moved out on · Final read · **Unit now (`Vacant · standby off`)** · Committed by, with the time.

**How the money landed** — a bordered Settlement box: Closing balance `$336.40` · Deposit applied `$150.00` · **Short by `$186.40`**. `move_out_settlement.py` is where these come from.

**Where it could go** — three options, and **nothing preselected**:
| Option | What it means |
|---|---|
| Follow the customer | the debt stays theirs; collections chase them at their new address |
| **Tie back to the master** | `A-10001 · Elm Street Holdings LLC`. Their ladder restarts, and this account closes |
| Write it off | **needs a supervisor and a reason** |

> **Nothing is preselected. A default here would be the product deciding whose debt this is.**

### ⚠ TWO ACTIONS, AND THE SECOND ONE IS WHY THIS RECORD DIFFERS FROM THE MOVE-IN'S
The move-in record has **no** actions — it is history, and the blueprint argues that at length. **This one has `Open the account` AND `Tie the shortfall back`**, because *"a closed move-out can still be waiting on a decision"*.

The blueprint's argument, verbatim: **"One action, and it is a consent rather than a consequence. Written as an automatic rule, tying a shortfall back would move a departing tenant's debt onto a landlord who never agreed to it, silently, on every move-out in the product."**

### The `Tie the shortfall back` dialog
`Tie $186.40 back` · *"A-10432 closes; somebody else starts being chased"*
| Field | Value |
|---|---|
| Amount · From | `$186.40` · `A-10432 · Okafor, D. · closed 01/28/2026` |
| **To** | `A-10001 · Elm Street Holdings LLC` |
| **Why that account** | **the declared owner of 1408 Elm Street** |

> **The target is resolved by the server and cannot be typed.** There is no account box on this form: a transfer built against an ambiguous target is refused, so rather than validate a typed account number the screen never offers one.

⚠ **THAT IS THE MASTER-ACCOUNT WALK THIS REPOSITORY ALREADY ESTABLISHED** — `regular account → unit → premises → premises_owners → master_account_id` — and the drawing refuses to let a clerk type it. The walk is recorded in `move-in-wizard-against-its-blueprint.md`.

**What this will do — read it before you agree to it:**
| | |
|---|---|
| Now | `$186.40` moves to A-10001 and A-10432 settles at zero |
| Now | **The reminder ladder starts pointing at the landlord**, not the tenant who left |
| Now | this move-out closes and stops waiting on a decision |
| Later | Elm Street Holdings receives the notices for a debt their tenant ran up |

**BUILT? The page, no. The tie-back write, no — it is a money move between accounts with a supervisor gate on the write-off branch, and nothing in the product does it today.**

---

## 3 · The wizard — six steps, p109–p116 (read, not yet ruled)

Ends at **Review & close** at `?step=6`, committing `POST /accounts/{id}/move-out` and reading `GET /accounts/{id}/close-impact` at step 5. The settlement arithmetic is drawn in full: prior balance `$247.30` → final bill net `$89.10` → outstanding `$336.40` → deposit applied `−$150.00` → **short by `$186.40`**.

**TODAY, per the drawing:** the product's move-out already has six steps, **but its deposit panel carries no actions and its shortfall no step — both were put back in this redesign.**

Two further facts drawn on step 6: a red note that **the already-issued-bill check cannot run** (*"Billing has no invoices table, so this screen genuinely cannot know it — the server answers it at the commit, and every move-out carries the warning rather than implying the check passed"*), and that **the done screen carries both exits as links** — the closed account and a move-in on the freed unit.

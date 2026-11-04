# CR-094-BRC01 · step 1 · lane 4 — ending service, read against its blueprint

**Five screens, blueprint pages 98–131.** The move-out wizard (`S20`), its
standalone door, the close-out act, the transfer wizard (`S89`) and the disconnect
wizard (`S90`). Built 2026-09-12 at product version **`2.237.10`** (read off the
sidebar in the browser, not off `package.json`).

**Step 1 classifies. It fixes nothing.** No product code was changed by this lane.

---

## 0 · HOW EVERY FIGURE HERE WAS OBTAINED

| what | how |
|---|---|
| the drawings | `05-prototype/02 Accounts Menu Blueprint.pdf` at commit `033981d4f`, sha256 begins `c8d596bb505f5020ce4b9474`, rendered to PNG at scale 2 and **read as images**. ⚠ The text layer renders every digit as `&`; it was used only for prose, and every number below was read off a rendered page |
| the running product | a private stack: Django on `127.0.0.1:8600`, `vite build` + `server.mjs` on `127.0.0.1:8601`, PostgreSQL 16, tenant `brazosbend` seeded by `manage.py seed_demo` + `manage.py load_sample_data --tenant brazosbend` |
| the screens | Chromium at **1280 and 1440** via `10-scripts/cr094_lane4_ending_service_walkthrough.mjs`, signed in as the seeded owner |
| the server | `curl` against the same backend with a real session cookie |
| dates and rails | read off the rendered DOM (`innerText`, `getComputedStyle`, element attributes), never off source |

⚠ **B14 RULE 37 GOVERNS EVERY DRAWN NUMBER BELOW.** *A figure drawn in a wireframe
is an illustration, never a fact to build to.* Drawn figures are quoted here so a
step-2 lane can see the SHAPE the frame asks for; not one of them is a value to
build to, seed, or assert in a test. Where a drawn figure and a served figure are
both given, they are labelled.

### What I seeded, stated so it can be reproduced or undone

Nothing was invented and nothing new was written by hand. Two existing management
commands were run against an empty database:

* `python3 manage.py migrate` — 278 migrations, no schema change by this lane.
* `python3 manage.py seed_demo` — 3 tenants.
* `python3 manage.py load_sample_data --tenant brazosbend` — **73 accounts, 75
  payments, 79 premises, 131 units, 2 move records, 4 disconnect cases, 0
  transfers.** One block did not load and named itself (`SD-PRECONDITION`, the
  multi-property cheque) and the Accounts block seated 49 of 50.

**The walkthrough commits nothing.** It opens each wizard, advances by filling the
fields the step requires, and stops before every commit button. No account was
closed, no cut scheduled, no sale reassigned. Two `POST`s were made **against the
server directly** — `transfers/commit` and `accounts/{id}/close-out` — and both were
refused by the server, so nothing was written by them either; each refusal is quoted
below with its HTTP status.

---

## 1 · THE FIVE SCREENS, INVENTORIED

### Screen 08 · Move-out wizard · `S20` · `/:tenant/accounts/{accountId}/move-out` · p98–106

**Drawn:** six steps. **Built: six steps.** ⚠ The screen index's note for this row
reads *"six steps become five"* and is wrong in both directions — see `DEF-CUS-5077`.
The blueprint's own routes line reads `S20 · six steps`, its caption reads *"All 6
screens of this flow"*, and `BR-SHL-046` (PO, verbatim *"6 steps"*) is the ruling
that made it six.

| | drawn (p98–p103) | built (Chromium, 1280 and 1440) |
|---|---|---|
| kicker | `MOVE-OUT` | `MOVE-OUT` |
| title | `The account` (step 1) | `Close an account and free the unit.` |
| subtitle | `Step 1 of 6 · Find account` | `6 steps · final bill, deposit, and what happens to the unit…` then `Step 1 of 6` |
| header action | `Save & exit` | `Save & exit` |
| back link | `← Account A-10432` | `← Miller, Sarah` |
| step rail | 1 Find account · 2 **Date & final reads** · 3 Final bill & deposit · 4 The shortfall · 5 What happens next · 6 Review & close | 1 Find account · 2 **Date & final read** · 3 Final bill & deposit · 4 The shortfall · 5 What happens next · 6 Review & close |
| footer | `← Back` · `Continue →` · `Complete move-out ✓` on step 6 | `Save & exit` · **`Park`** · `Back` · `Continue` · `Complete move-out ✓` on step 6 |

Two copy divergences, both small and both real: the rail's step 2 is **singular**
in the product (`Date & final read`) and **plural** in the drawing, and step 2 renders
**two** read rows, so the drawing's plural is the right word. And the built footer
carries a third control, **`Park`**, that the drawing does not show — it is `CR-035`'s
park-and-resume and is correct; the drawing predates it.

**Step 1 · fields, character for character.**

*Drawn:* `Search for the account *` (required), help *"Account number, customer number,
name, service address or meter number."*, then a results table `ACCOUNT · CUSTOMER ·
SERVICE ADDRESS · STATUS · BALANCE` with a radio per row.

*Built:* **no search at all.** The step confirms:

> *"The account is the one you came from — the server closes the account named in
> the address bar, so there is no search on this step. Go back to Accounts to move
> a different one out."*

This is NOT a divergence to fix. The drawing's own right-hand note says the same
thing — *"Entered from the account's own page, this step confirms rather than
searches… Entered from the Move-outs tab, there is nothing in the URL and the search
above is the only way in"* — so the drawn search belongs to screen 09's door and the
frame illustrates the wrong one of the two. `MoveOutWizard.tsx`'s `E3` exception
records the same reasoning. **Classified: no finding.**

Read-only facts built on step 1: `Account A-10432` · `Name Miller, Sarah` ·
`Service address 1408 Elm Street · Unit A` · `Services E W` · `Since 02/05/2024` ·
`Status Active` · `Balance $247.30` with the sentence *"worked out from the ledger —
every posted charge, less every posted payment"*. The drawn panel carries twelve
further rows (customer number, category, autopay, paperless, preferred language,
mailing address, and a whole `The unit they are leaving` panel of nine). **The built
step carries six.** Recorded as a content gap for step 2 to size, not as a defect —
the drawing decides what a form CONTAINS (B14 rule 38's last clause).

**Step 2 · `Date & final read`.** Built fields, measured:
`moved_out_on` (**native `input[type="date"]`, no `min`, no `max`**), then one
`moveOut-read-<assetId>` text input and one `moveOut-estimate-<assetId>` checkbox
**per meter** — two of each on this unit. Drawn: the same shape, as a table
`METER · FINAL READ · READ DATE · COULD NOT BE READ` with a date per row. **The
drawn per-row read date is not built** — there is one move-out date for both reads.
Drawn figures on this step (illustrations): `01/28/2026`, `52,410`, `1,388`, `1,402`.

**Step 3 · `Final bill & deposit`.** Drawn: a priced final bill
(`Electric · 634 kWh … $71.40` · `Water · 14 kgal · estimated … $17.70` ·
`Final bill, net $89.10`), a four-option deposit disposition with three greyed and
each saying why, and a subtraction ending `Short by $186.40`.

Built: **no figure at all, and it says why.**

> *"Nothing on this step is a figure this product can work out yet, so nothing on it
> is shown as a figure. Each line names the rule it is waiting on."*

and then, verbatim: `Prior balance $247.30` · `Deposit on file $150.00` ·
`Interest accrued — Not accrued` · `Applied to the final bill — Nothing applied` ·
`Refund method — Not chosen here`. Both money figures display at **2 decimals**
(hard rule 2 satisfied on screen; the server serves them as `{stored:"247.3000",
display:"247.30"}`).

⚠ **THE DEPOSIT-INTEREST FIGURE IS SIGNED, IS ~2.3% OF A $150 DEPOSIT, AND IS NOT
TRACKED — AND THE SERVER SAYS SO IN ITS OWN WORDS.** `GET /accounts/{id}/close-impact`
answers, measured on `A-10432`:

> `"gaps": ["final_bill_not_stated","deposit_interest_not_accrued"]` … *"**WE-7
> freezes $3.50 on a $150 deposit held 14 months at 2%** and **GT-61 freezes $22.25
> on 89 months**; a principal-only settlement keeps that money on a bill that
> foots."*

The blueprint draws the same arithmetic on p100 (*"the agreed arithmetic for a
deposit held this long says `$153.50`"*) and again on transfer step 4. **This is a
❄️ FROZEN B4/B5 figure that the product does not compute**, and it renders as *not
recorded* rather than as `$0.00` — which is correct, because `$0.00` would be a
claim. **No finding filed: this is an existing, registered absence** (`BR-CUS-057`,
`GT-61`), and filing it would be filing a deliberate refusal. It is recorded here
because a step-2 lane pricing a final bill will meet it, and because the consequence
runs **against the customer**: a smaller amount applied makes the shortfall bigger.

**Step 4 · `The shortfall` — ⚠ THE ONE BREAK ON THIS SCREEN, AND IT IS ON THE MONEY.**
Measured in Chromium: step 4 fires `GET /api/brazosbendaccounts/<id>/close-impact`
and the server answers **404** (Django's HTML 404 page). The screen then renders

> *"The four paths arrive with the close-impact read and it has not answered yet.
> Nothing is assumed in its place, and no path is offered until the server has said
> which of them it can act on."*

— a stated absence over a transport failure. **No shortfall path is ever offered,
on any tenant.** `settleShortfall` has the identical bug. Filed **`DEF-CUS-5072`**.
Drawn for comparison: four paths (`Collect it` · `A payment plan` · `Transfer it to
the master account` · `Write it off`), a `Forwarding address` field, and a
`What each one would ask for` table naming `WHO CAN` per path.

**Step 5 · `What happens next` — NINE consequence panels, and this is B14 rule 11
honoured about as well as it gets in this product.** Built, measured:
`Premises` · `Unit` · `Assets` · `Plans, rates & discounts` · `Deposit` ·
`Payments` · `Open items` · `Sub-accounts` · `Collections & notices`. Each is a
`<details>` closed by default (B14 rule 32 satisfied by construction) and each
carries a provenance chip — **`DERIVED`**, **`EXPLICIT`**, **`CHECK`** — or states
that nothing served it. Drawn: the same nine facts in three panels plus a dashed
`SIX CONSEQUENCES THE PRODUCT CANNOT YET STATE`.

**Step 6 · `Review & close`.** Built commit label: **`Complete move-out ✓`** —
matching the drawing exactly, including the drawing's own note that the prototype's
*two* buttons became one. Rendered class is the **primary** tier, not danger, which
is correct: the blueprint's §09 compliance table lists rule 6 as PASS naming only
close-out and the disconnect as danger-tier subjects.

**Trace, verified:** door = the `S21` **Move-out** button at
`AccountDetailPage.tsx:713`, guarded. Commit = `POST /accounts/{id}/move-out`.
Reads `GET /accounts/{id}/close-impact` (twice — see the finding).

---

### Screen 09 · Move-out · standalone · `/:tenant/move-outs/new` · p107

**⚠ `NO COMMITMENT` — and the chip's provenance is not what the index says.**

The screen index's row 09 reads `EXISTS BEHIND · NO COMMITMENT` and says the state
column *"is the blueprint's own chip"*. Read off rendered page 107 **and** off the
text layer, the blueprint's header for screen 09 carries **one** chip,
`EXISTS BEHIND`; screen 10 three lines below carries **two**. The added chip is a
correct derivation — no `ACC-S` row in §12 names screen 09 — but it is stated as a
reading. Filed **`DEF-CUS-5079`**.

**What `NO COMMITMENT` means here, in the blueprint's own rule:** *"A screen no
specification covers carries `NO COMMITMENT` — that absence is the finding, not an
oversight."* So: **nobody has undertaken to build anything on this screen.** It is
not blocked, not broken and not scheduled. A step-2 lane must not read it as work.

**Built, measured.** The same `MoveOutWizard` component, entered with no account.
Six-step rail identical to screen 08. Step 1 becomes a real search:

> title `Find the account that is moving out` · *"A move-out closes one named
> account. Find it by its account number, the customer's name or the service
> address — the same search the accounts list uses."* · field `Account *` · help
> *"Type the account number as your lists show it (AC-2026-00025), the customer's
> name or the service address. An account id pasted in is used as it is."*

**Four doors verified in source**, each as the blueprint names it:
`AccountsListPage.tsx:1212` (header), `AccountsListPage.tsx:984` (tab primary),
`MoveOutsTab.tsx:769` (empty-state CTA), and the parked **Resume**.

⚠ **The account picker is a search box plus a `<select>`, not the drawn radio table.**
The same shared `accountFinder` serves screens 09, 11 and 12, so this divergence is
one component and three screens. The drawing's table carries columns the select
cannot (`STATUS`, `BALANCE`, `OWED`, `TIER`) and its purpose is visible on p98 and
p121 — two same-named accounts, one closed; two accounts, one already being sold.
**Recorded, not filed**: it is a shared-kit change (B14 rule 36's *add it to the kit*)
and `CR-093-BRC01` already owns the shared-component queue.

---

### Screen 10 · Close-out · `/:tenant/accounts/{accountId}/close-out` · p107–111

**⚠ `NO COMMITMENT`, AND THE REASON IS NAMED BY THE BLUEPRINT AND BY THE CODE.**
The blueprint's facts table reads: *"**No epic owns this screen.** Its own trace
block says so: the PO ruled the act on 2026-08-27 and no epic covers it, so a story
is owed. That absence is the finding, and this document does not invent a commitment
to fill it."*

**Confirmed in the source, still there today.** `CloseOutPage.tsx:4`:

> `//           ⚠ **NO STORY OWNS THIS SCREEN.** The PO ruled the ACT on`
> `//           2026-08-27 and no epic covers it — hard-won law 8. A story is OWED`
> `//           and is REPORTED rather than invented.`

`ACC-S7`'s *what done looks like on screen* is exactly the removal of that line.
**This is hard-won law 8 (*every screen needs a story*), reported and unresolved
since 2026-08-27 — 16 days.**

**It is not a wizard and has no rail, on either side.** Drawn as a single form with
a confirm page; built the same way.

| | drawn (p108) | built |
|---|---|---|
| kicker | `CLOSE OUT ACCOUNT` | *(none rendered)* |
| title | `Close out this account` | `Close out account` |
| subtitle | `A-11488 · Okafor, D. · cut on 08/18/2026` | *(none)* |
| back link | `← Account A-11488` | `← Back to the account` |
| header action | `Save & exit` | *(none)* |
| fields | `Closing this account out on *` (date) · `Why *` (textarea) · `Status it takes` (select) | `Closed out on` (**native `input[type="date"]`**) · `Why` (textarea) — **no status select** |
| commit | `Record the close-out`, then a confirm page and `Yes — close it out` | `Close out this account`, **danger tier confirmed at the rendered class** |

The drawn `Status it takes` select is deliberately absent: `CloseOutRequest` declares
`status?` optional and the wizard omits it so the server picks the tenant's own
seeded terminal status (`BR-CUS-055` is tenant-extensible). Recorded, not filed.

**B14 rule 6 · PASS, measured on the rendered `class` attribute** (not the prop —
the amendment of 2026-08-25 exists because a prop assertion was green on the broken
day): `bg-transparent text-danger-700 border-danger-500 hover:not-disabled:bg-danger-700`
— the outlined-fills-on-hover danger tier, exactly as rule 6 defines it.

**⚠ TWO INDEPENDENT BREAKS, AND EITHER ONE ALONE MAKES THE SCREEN UNUSABLE.**

1. **`DEF-CUS-5073` — the eligibility read 404s.** `closeOutEndpoints.ts:131`
   builds `accounts/{id}/close-out` with **no leading slash**, so `apiPath()` welds
   the tenant segment to `accounts` and the request goes to
   `/api/brazosbendaccounts/<id>/close-out`. Measured in the browser at 1280 and
   1440: **404**. The screen therefore renders `Account closed on (the cut date) —`,
   `Disconnection case: no reference`, `Outstanding balance: could not be read`, and
   `Close out this account` is **disabled**. It fails safe and it fails silent. The
   same path with one slash added answers **401** unauthenticated and **200**
   authenticated, with the server's real refusal in plain language:

   > `409 BIZ-STATE customers.account.close_out_still_occupying` — *"this account
   > still occupies its unit, so its departure is a MOVE-OUT and must be filed as
   > one… which is the same falsification BR-CUS-430 forbids in the other
   > direction."*

   That sentence never reaches a clerk.

2. **`DEF-CUS-5074` — the commit wraps its payload in an extra `body` key.**
   `client.post` is `post(path, body, options)`; `closeOutEndpoints.ts:145` calls
   `client.post(path(accountId), { body })`, so the wire payload is
   `{"body":{"closed_out_on":…,"reason":…}}`. Posted at the running server that shape
   answers **422 `VAL-002 customers.account.unknown_field`**, `field_errors:
   [{field:"body"}]`; the three fields sent flat answer the **409** above. **So even
   with the slash fixed, no close-out can be recorded on any tenant.**

**Drawn facts worth carrying to step 2** (illustrations, per rule 37, but the SHAPE
is the point): the record keeps **two dates** — the account's `closed_at` is the
**CUT** date and the act's own date is *closed out on*, recorded separately against
the clerk's name (`BR-CUS-431`) — and the drawing prices the cost of getting it wrong
as *"43 days"* of an empty unit (08/19 to 09/30, which arithmetic checks). The built
page states the same rule in its own words: *"The account closes on the date its
service was cut, not on the date you do this."*

Two stated absences drawn on this screen, both quoted in full:

* **`A LIST OF REASONS TO PICK FROM`** — *"There is none, and the sentence above is
  what gets recorded. Nothing in this product counts closures by reason, so how many
  did we close as written off last year has no answer."* **Built, verbatim:** *"Write
  it in your own words. There is no fixed list yet, so this cannot be counted in a
  report."* ✅ the drawn absence is honoured on screen.
* **`NOTHING HAS BEEN CHECKED FOR YOU`** — *"This act does not look up an active
  payment plan, an open dispute or an unbilled cycle, and IT IS NOT TELLING YOU THEY
  ARE CLEAR."* The built page carries a `What this screen is not telling you`
  section. ✅ honoured.

**Trace, verified:** one door, the `S21` **Close out** secondary at
`AccountDetailPage.tsx:738`, `GuardedButton` with a reason.

---

### Screen 11 · Transfer wizard · `S89` · `/:tenant/transfers/new` · p112–119

**⚠ THE LARGEST FINDING IN THIS LANE. THE SHIPPED SCREEN IS THE JOB THE PO REPLACED,
AND ITS COMMIT CANNOT SUCCEED.** Filed **`DEF-CUS-5075`**, severity critical.

**The ruling.** PO 2026-09-01, verbatim, quoted by the blueprint on p112:

> *"dont create new account - we reassing that account - bascailly I have sold my
> property - so account get transfer to new person or business; if I move to new
> location then it is new Service request"*

So a transfer is a **SALE**: the account, its number, its unit, its meters, its plan
and its whole ledger stay where they are, and **the customer changes**. The server
was rewritten that day.

| | drawn (p113–p118, the sale) | built (Chromium, 1280 and 1440) |
|---|---|---|
| title | `Find the account, and who is selling` | **`Same customer, moving to another of your addresses`** |
| subtitle | `Step 1 of 5 · Find the account` | **`Five steps · one job, not two. The deposit moves with them.`** and a **`Split into two`** control |
| rail | 1 Find the account · 2 The buyer · 3 Date of sale · 4 What they take on · 5 Review & confirm | **1 Leaving · 2 Final reads · 3 Arriving · 4 Money · 5 Review & confirm** |

**Every word of the built subtitle is the model the PO reversed.**

**And it cannot commit.** `TransferCommitPlan` sends `from_account_id`, `to_unit_id`,
`out_date`, `in_date`, `deposit_carry`, `arrears_follow`. `transfer_commit` reads
`from_account_id`, **`customer`**, **`field_visit`** and **`sold_on`** — so five of
the six keys sent are ignored and three of the four keys read are never sent.
Measured: posting the shipped payload at the running server on a customer-linked
account answers

> **`422 VAL-001 customers.transfer.buyer_required`**

It refuses at `set_new_customer`, **the second of the five staged writes**, naming a
field that appears on none of the five screens — exactly as the blueprint says.
(On an account with no customer link it refuses one stage earlier, `409
customers.transfer.from_account_has_no_customer`, which is a different and correct
refusal.)

**What the drawing asks for, recorded so step 2 has it:** step 2 `Who is buying it`
— `Customer kind` select · `Full name *` · a *"One identifier — and one is enough"*
group of `Social Security number` / `Driving licence` / `Phone` · `Email` ·
`Mailing address` select, with a refusal *"Needs one identifier to continue."*; a
right-hand **`Field visit — the changeover read`** table raising work orders, and a
`No visit needed` checkbox. Step 3 `The date of sale` — one date, `Nothing is
prorated at a sale`. Step 4 `What the buyer takes on` — the balance and deposit as
they stand, a `Before you continue` checkbox *"I have shown this to the buyer"*, and
**no fee**. Step 5 review with edit-back chips and a template picker; commit
**`Complete the sale ✓`**.

⚠ **TWO PARAGRAPHS OF THE BLUEPRINT STILL DESCRIBE THE OLD MODEL AND ITS OWN DRAWING
CONTRADICTS THEM.** p118's *"Where a transfer lands"* reads *"Onto the Transfers tab,
**with two dates rather than one**…"*, and the caption under it reads *"One customer,
two addresses — and the deposit that follows them"*. p119 draws that same tab and
states in the frame: *"**One date, because there is only one.** This used to be a
flow with an out date and an in date, because it closed one account and opened
another"*, over a table whose only date column is `SALE DATE`. **The frame is right
and the prose is stale** (the *frame wins* ruling of 2026-09-10). Filed
**`DEF-CUS-5078`** so a step-2 lane is told rather than left to notice.

⚠ **A drawn absence that is not quite true, and it matters to money.** Step 4's
dashed block reads *"THERE ARE NONE, AND THIS STEP TAKES NO PAYMENT — … There is no
change-of-ownership fee in this product: no rule sets one, **no table holds one**,
and no door would take the money."* The seeded catalogue **does** hold
`TRANSFER — Account transfer fee`; what it does not hold is an **amount**
(`charge_code_amounts` has no row for it). The absence is real and its stated cause
is not. Recorded here rather than filed as its own row — the corrected sentence
belongs to whoever builds the fee.

**Also drawn and worth carrying:** after a sale *"the account keeps the seller's
contact details and settings. Paperless is still on, the bill email is still the
seller's, and autopay is still running on the seller's bank instruction."* That is
drawn as an as-built fact and is a real hazard on a money path; it is the drawing's
own statement and no step-2 work is proposed for it here.

**Trace, verified:** three doors — `AccountsListPage.tsx:930` (tab primary),
`TransfersTab.tsx:709` (empty CTA), parked **Resume**.

---

### Screen 12 · Disconnect wizard · `S90` · `/:tenant/disconnects/new` · p120–131

**⚠ `BLOCKED` — the only screen in the whole Accounts surface carrying that chip.**
The blueprint's reason: *"It states more open questions than any other: seven of its
refusals name a decision nobody has made."*

**What `BLOCKED` means here:** the screen is built, routed, reachable and walkable
end to end — I walked all five steps — and **it cannot lawfully do its job**, because
a rule it needs does not exist. That is different from broken and different from
unbuilt, and a step-2 lane must not "finish" it.

**The rail matches the drawing exactly.** Built and drawn: 1 `Account & reason` ·
2 `Protections` · 3 `Notice & date` · 4 `Fees & consequences` · 5 `Review`.
Built title `Cut service at an address`, subtitle *"Five steps · notices, protections
and the date."* and a footer line on every step: *"nothing is cut until the scheduled
date."* Commit **`Schedule the disconnection ✓`**, and **B14 rule 6's danger tier is
confirmed on the rendered class** at 1280.

#### The blocker, established and taken no further

`ACC-S10` waits on *"the notice-date-plus-statutory-period calculation, rolled past
weekends and holidays. Nothing performs that roll today."* **Established:**

* the screen states it, verbatim: *"The earliest lawful cut date is not computed
  anywhere in this product. It is the notice date plus the statutory period, rolled
  forward past weekends and public holidays, and nothing performs that roll — so this
  screen cannot show it and cannot stop an unlawful date being chosen here."*
* the server states it: `transfer_disconnect_api.py:88` — *"It computes no date…
  `cut_on` is the caller's"*.
* **what the screen does instead, measured:** it offers `Scheduled cut date *` as a
  **native `input[type="date"]` with NO `min` attribute** — read off the element in
  Chromium, not from source — so **any date is accepted, including one before the
  notice**. Its help says so: *"Check it against the statutory period yourself —
  this screen has no floor to check it against."*
* and nothing downstream catches it: `GET /accounts/{id}/ladder` answers, in the
  server's own words, *"no runner, job, queue or timer in this product reads a date
  and acts on it (measured 2026-08-25)"* — tracked as `DEF-320`.

**⚠ THE QUESTION HAD NO ID. IT DOES NOW: `OQ-CUS-1810`, minted by this lane, OPEN.**
`DisconnectWizard.tsx`'s own `E3` block says *"a rule id for the weekend/holiday roll
does not exist in any signed document; REPORTED as a question owed rather than minted
here"* — and it was never minted. Measured 2026-09-12: no row and no section of
`01-open-questions.md` names it, and the decision log does not either. That is
hard-won law 1, and it means the blocker has had no route to the PO for as long as
the screen has existed.

**NOTHING HERE CHOOSES A PERIOD.** The drawing shows `Earliest lawful cut 05/14/2026`
counted from `The final notice, 05/09/2026`, and labels the final tier
`Final · 5-day`; `OQ-377`'s body works its example on **48 hours** from `B18`'s
fixture. **Neither is a signed rule and neither is quoted here as one** — B14 rule 37
makes a drawn figure an illustration, and `DisconnectWizard.tsx` records why the trap
bites: adding 48 hours implements *"+2 days"*, which agrees with `B18`'s fixture **by
luck**, because Aug 22 2026 is a Saturday. `ACC-S10`'s *what done looks like on
screen* quotes the drawn `05/14/2026`, which is the same hazard one document further
on and should not be copied into a test.

#### Two further blockers on this screen, both measured

* **`DEF-CUS-5076` — step 2 says no endpoint serves its checks, and that endpoint has
  been answering for fifteen days.** Built step 2 renders `Medical equipment on site`,
  `Weather moratorium` and `Active payment plan` as `—` under *"The product performs
  this check and no endpoint serves its finding to a screen yet, so the answer is not
  shown here."* Measured: **`GET /accounts/{id}/protections` answers 200** with all
  three outcomes, their lifetimes and reasons, plus a named `unavailable` for the
  dispute check — and **the step makes no request at all**. Dated with
  `git log -S`: the routes landed **2026-08-28** (`8700efbb9`); the front end's
  `⛔ NOT SERVED` docstrings were last touched **2026-08-25** (`16d9a6d51`). Six
  routes carry the same stale mark and **all six are mounted** (probed:
  `disconnects/schedule` POST 422 · `transfers/commit` POST 422 · `protections`,
  `ladder`, `reconnection-terms` all GET 200). This is the most safety-critical step
  in the product telling a clerk it cannot check a medical certificate while the
  server has the answer.
* **the fee codes — the blueprint is right about the effect and half right about the
  cause, and the correction matters.** The blueprint says *"None of the three is in
  any catalogue on this system."* Measured on `brazosbend`: the codes the module
  looks up are `CC-RECON`, `CC-DISC`, `CC-FIELD` (`disconnects.py:888`), and the
  seeded catalogue holds `RECON — Reconnection fee`, `DISC — Disconnect fee` and
  `RETURN-TRIP` — **near-misses under different spellings, none with an amount**.
  The server states the consequence itself: *"the demo seed spells its disconnect fee
  `DISC` and seeds no reconnection fee at all. So the code this module looks up
  resolves on no tenant in this tree today and every cut refuses until one is
  configured… **A RULING IS OWED.**"* **That ruling already has an id — `OQ-681`,
  OPEN** (*is `CC-RECON` a catalogue code the platform seeds, or a tenant setting?*).
  No new question minted; **a fix that simply adds `CC-RECON` would create a
  duplicate of `RECON`**, which is why the spelling is recorded here.

#### Step-by-step, drawn against built

* **Step 1 · `Account & reason`.** Drawn: a results table `ACCOUNT · CUSTOMER ·
  SERVICE ADDRESS · OWED · TIER` with radios; a `Reason` select; a `Which services`
  table `CUT · SERVICE · METER · WHAT HAPPENS TO IT`; `Where the ladder has got to`;
  and `The money — why the ladder is running` with the three bills footing exactly to
  the balance. Built: the shared search + `<select>`; **five reason radios with a
  sentence each** (`Non-payment — the ladder has run and they have not paid` ·
  `Unsafe installation — a hazard found on site` · `Tampering or theft — the meter
  has been interfered with` · `Premises abandoned — nobody is there and nobody is
  paying` · `The customer asked — they want service ended`) and the honest line
  *"The reason is recorded on the case and nothing in the product branches on it.
  Two cuts differing only in reason behave identically today."*; and, where the
  drawing shows a services table, *"No services are readable on this account yet, so
  there is nothing to decide per service."*
  Both sides carry the restrictor absence: drawn *"A RESTRICTOR INSTEAD OF A CUT …
  refused by name"*, built *"This product cannot record it, so a water cut here is a
  full cut or nothing"* (`OQ-385`, OPEN).
* **Step 2 · `Protections`.** Drawn: a ten-row `QUESTION · ANSWER · ANSWERED ON ·
  WHO ANSWERS IT` table, a `Record a protection` control, a `Certificate expires`
  date, a `Reference`, three `Or stop the ladder without a protection` radios and a
  `What happened` field — **with its own dashed block saying none of it is operable**.
  Built: **zero inputs**, and the split the drawing promises — *"Checked by the
  product"* (3) against *"Not checked by anything"* (7), with *"there is no summary,
  because a summary would be a clearance nobody computed."* ✅ the drawn absence is
  honoured; the stale sentence inside it is `DEF-CUS-5076`.
* **Step 3 · `Notice & date`.** Drawn: `What has gone out already` (3 notices), six
  outgoing channels, a four-field `Proof that it was served` block, and the computed
  locked date. Built: **four channels** (`Certified mail · Required` · `Email` ·
  `Text message` · `Door hanger` — the drawn `Posted` and `In the portal` are
  absent), **no proof-of-service fields at all**, and *"Which tier this account is on
  and when each notice was served are not served to this screen."* Plus a `Field
  work` section stating `OQ-383` in plain words: *"If a crew attends and does not cut
  … there is nowhere to record that. The case stays scheduled with a date in the
  past, which looks the same as one that has not come round yet."*
* **Step 4 · `Fees & consequences`.** Drawn: `CHARGE · CODE · AMOUNT · WHEN ·
  CHARGED?` (three codes, one charged), a `What must be cleared before service comes
  back` box, a `Take a payment now` form, a deposit election, and `What the cut will
  do` / `What it will not do`. Built: reached and rendered; the fee amounts are
  absent for the charge-code reason above.
* **Step 5 · `Review`.** Built commit `Schedule the disconnection ✓`, **danger tier
  confirmed**. The drawn title is `Review — nothing is cut today`, which is the whole
  point of the screen and is carried by the built footer line.

**Trace, verified:** four doors — `AccountsListPage.tsx:937`, `DisconnectsTab.tsx:915`,
parked **Resume**, and the `S21` icon rail's ⚡ **Disconnect notice**
(`accountRailReadiness.ts:291`).

---

## 2 · WHAT WAS SEEN IN A BROWSER AND WHAT WAS READ FROM THE CODE

Stated plainly, because *"walked"* and *"read"* are different evidence.

| screen | seen in Chromium | read from code / server only |
|---|---|---|
| 08 move-out | **all six steps**, 1280 and 1440; step 4's 404 observed on the wire | the commit (not pressed — it closes an account) |
| 09 standalone | step 1, both widths | steps 2–6 are the same component as 08 |
| 10 close-out | the form and its disabled commit, both widths | the confirm page and the account-afterwards page are **unreachable** behind `DEF-CUS-5073`; both `POST` shapes tested at the server |
| 11 transfer | step 1, both widths | the commit tested at the server (422) |
| 12 disconnect | **all five steps**, 1280 | the commit (not pressed) |

⚠ **The blueprint records *"Not walked."* for every one of these five screens.** They
are walked now, and three of the six findings below were found only by walking.

---

## 3 · FINDINGS, EACH ROUTED

**The routing question** (`22-product-maintenance-process.md`): *can a user do this
task in the product today?* No → BUILD. Yes → MAINTENANCE. **Ambiguous → DEFECT**
(`13-change-process.md` §1).

| id | finding | routing |
|---|---|---|
| `DEF-CUS-5072` | move-out step 4 404s and the 404 is dressed as a stated absence | **MAINTENANCE** — the screen is live and does not do what it says |
| `DEF-CUS-5073` | close-out cannot read its own eligibility; commit disabled, no reason shown | **MAINTENANCE** |
| `DEF-CUS-5074` | close-out commit wraps its payload in an extra `body` key → 422 | **MAINTENANCE** |
| `DEF-CUS-5075` | transfer wizard ships the replaced job; commit refuses `buyer_required` | **MAINTENANCE, and it is a redesign** — the maintenance process names the redesign case on purpose: a live screen redrawn end to end is maintenance, borrowing only the drawing step from Build |
| `DEF-CUS-5076` | disconnect protections step says *not served* over six mounted routes | **MAINTENANCE** |
| `DEF-CUS-5077` | the screen index's *"six steps become five"* | **MAINTENANCE** (documentation) |
| `DEF-CUS-5078` | the blueprint's transfer prose describes the model its own drawing replaced | **MAINTENANCE** (documentation) |
| `DEF-CUS-5079` | the index states screen 09's `NO COMMITMENT` chip as the blueprint's when it is derived | **MAINTENANCE** (documentation) |
| `OQ-CUS-1810` | the statutory period and its weekend/holiday roll | **PO — a fact only they hold** (law 13) |

**Not filed, deliberately, and each is a deliberate refusal rather than a break:**

* deposit interest rendering as *not recorded* rather than `$0.00` — `BR-CUS-057`,
  `GT-61`, already registered;
* move-out step 3 showing no priced final bill — the preview route is deliberately
  not served and the screen says so;
* the disconnect fee amounts — `OQ-681`, OPEN;
* the restrictor, the crew outcome, the new-service block and the four unreachable
  cut reasons — `OQ-382`–`OQ-385`, all OPEN and all stated on screen;
* `.date-input` and the *Today* shortcut (`ACC-S4`, UI-RULES 7) — already
  `DEF-MET-4974`, `partially-fixed`; **no duplicate row filed**. Note the difference
  on screen 12: `dsc_cut_on` has no `min` **because no floor exists**, which is
  `OQ-CUS-1810` and not a rule-7 miss;
* the account picker being a `<select>` rather than the drawn radio table — a shared
  kit change, and `CR-093-BRC01` owns the shared-component queue;
* move-out's commit being primary rather than danger — the blueprint's §09 lists
  rule 6 as PASS naming only close-out and the disconnect.

---

## 4 · THE SPECIFICATION REGISTER (§12), SETTLED FOR THIS LANE'S PART

The CR's §3b records that the blueprint disagrees with itself — its cover says **10**
specifications, and the index said **21**. **Read end to end at p207–p209: the table
holds SEVENTEEN rows and its highest id is `ACC-S21`.** `ACC-S11`, `S12`, `S13` and
`S19` are ids in use elsewhere in the document (S11–S13 as cards on p153, S19 minted
for `R9` on p198) and have **no row**, which §12's own opening — *"One row per
commitment, no exceptions"* — does not allow. The cover's **10** traces to §12's own
box (*"`ACC-S1`…`ACC-S10` is a series minted for this document"*) and to the §13
changelog entry *"Ten cards exist"*, both of which predate the rows for `S14`–`S21`.
A sibling lane reached the same figure independently and the screen index now reads
**SEVENTEEN rows, ids running to `ACC-S21`**.

**The four rows that name this lane's screens:**

| id | waits on | screens | status |
|---|---|---|---|
| `ACC-S4` | a shared `.date-input` component, which does not exist anywhere in `07-frontend` | 03 · 04 · **08 · 10 · 11 · 12** · 13 · 14 | Unverified |
| `ACC-S6` | a convention: a refusal written with a clock in it gets a test that fails when the clock runs out, in the same commit | 01 · 02 · 03 · 04 · **08 · 12** · 14 | Unverified |
| `ACC-S7` | an epic. The act was ruled 2026-08-27, the screen was built the same day, and no epic covers it | **10** | Unverified |
| `ACC-S10` | the notice-date-plus-statutory-period calculation, rolled past weekends and holidays | **12** | Unverified |

⚠ `ACC-S6` is hard-won law 2's own clause, and `DEF-CUS-5076` is that clause failing
on screen 12 today. ⚠ `ACC-S10`'s *what done looks like* quotes a **drawn** date;
B14 rule 37 forbids asserting one.

---

## 5 · §09 — WHERE THESE SCREENS DEPART FROM THE RULES

The blueprint finds **one** repo-wide violation and four of this lane's five screens
carry it: **UI-RULES 7 / B14 rule 7** — *"Date fields always use the date input
(calendar affordance, keyed entry, Today shortcut). Never a bare text input."*

Measured on my screens: every date is a native `input[type="date"]` —
`moved_out_on` (08/09), the close-out `Closed out on` (10), `dsc_cut_on` (12).
**No `.date-input` component exists in `07-frontend`**, so there is no Today shortcut
and the displayed format follows the browser locale rather than the tenant's, while
`DateCell` everywhere else formats per tenant. The blueprint's own fairness note
stands: a native date input is timezone-free, so the hazard that usually bites date
fields does not bite here — the violation is the missing shortcut and the
locale-dependent format.

**Checked and found compliant on this lane's screens:**

| rule | verdict | evidence |
|---|---|---|
| B14 rule 6 · danger tier | **PASS** | `Close out this account` and `Schedule the disconnection ✓` both carry the danger class, read off the rendered `class` attribute at 1280 |
| B14 rule 11 · consequence preview | **PASS** | move-out step 5's nine panels · close-out's `What this will write` · disconnect step 4's `What the cut will do` / `will not do` |
| B14 rule 32 · a stated absence is a closed `<details>` | **PASS** | move-out step 5's nine panels are `<details>`, closed by default |
| B14 rule 40 · page-head title 32px | **PASS** | `getComputedStyle` on the `h1` of all five screens at 1280 and 1440: **32px** on every one |
| hard rule 2 · money displays at 2 decimals | **PASS** | no money string with more than two decimals on any of the five screens at either width. ⚠ My first pass reported a hit and it was the sidebar's version string `v2.237.10`; the regex was corrected before the figure above was trusted |
| B14 rule 3 · steppers | **PASS** | 08/09 six-cell rail, 11 and 12 five-cell rails, wizard-actions footer; 10 is a single form and fakes no stepper |

---

## 6 · WHAT I COULD NOT CONFIRM, AND WHAT WOULD SETTLE IT

* **Close-out's second and third screens** (`?confirm=1` and the account afterwards).
  Unreachable behind `DEF-CUS-5073`. **Settled by:** the one-character fix, then a
  walk. Both `POST` shapes were tested at the server, so the commit's behaviour is
  known even though the screen is not.
* **No account on any seeded tenant is eligible for a close-out.** All three
  candidates refuse correctly (`still_occupying`, `already_terminal`). **Settled by:**
  driving an account to `disconnected` through the product's own `commit_cut`, which
  is itself blocked by the charge-code question (`OQ-681`). So the close-out screen's
  happy path cannot be reached on a seeded tenant today at all.
* **The transfer wizard's steps 2–5.** Step 1 renders and the commit was tested at
  the server; the intermediate steps were read from source. **Settled by:** a walk
  after `DEF-CUS-5075`, which will change every one of them.
* **Whether the drawn `Posted` and `In the portal` notice channels were removed
  deliberately.** The built step 3 offers four of the drawn six and says nothing about
  the other two. **Settled by:** the ruling behind `BR-CUS-039`'s channel list.
* **Whether `TRANSFER — Account transfer fee` is meant to be chargeable.** The code
  exists with no amount; the drawing says no fee exists. **Settled by:** a PO answer,
  which nobody has asked for and which this lane did not mint — there is no screen
  offering it and therefore nothing blocked.

---

## 7 · WHAT STEP 2 SHOULD NOT DO

* **Do not add a `min` to `dsc_cut_on`.** It would implement a period nobody ruled
  and would agree with the fixture by luck. `OQ-CUS-1810` first.
* **Do not assert `05/14/2026`, `$186.40`, `$153.50`, `43 days` or any other drawn
  figure in a test or a fixture.** B14 rule 37.
* **Do not fix only the slash on close-out.** `DEF-CUS-5074` is behind it and the
  screen stays unusable.
* **Do not build the transfer's two-date model** from p118's prose. `DEF-CUS-5078`.
* **Do not file the deposit-interest absence, the unpriced final bill, the restrictor
  or the fee amounts as defects.** Each is a registered, deliberate refusal.

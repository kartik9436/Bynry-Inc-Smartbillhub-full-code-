# CR-094-BRC01 · step 2 wave B — money on the account, and the account detail's false sentences

**Five register rows, six ids, one screen: `S21` `/:tenant/accounts/:accountId`
and its `S22` Record payment modal.** Shipped as **`2.237.11`**.

**Step 1 classified; this repaired.** The findings are
`CR-094-lane2-account-detail-step1.md` (F1–F4, F7) and
`CR-094-lane5-money-and-queue-step1.md` §3.

| row | severity | status |
|---|---|---|
| `DEF-CUS-4999` | high | **fixed** — the Record payment modal's two lines |
| `DEF-CUS-5008` | high | **duplicate of `DEF-CUS-4999`** — the same two lines, found twice |
| `DEF-CUS-4998` | medium | **fixed** — two surfaces denied a portal that ships |
| `DEF-CUS-5000` | low | **fixed** — the sub-type reached a clerk as a database word |
| `DEF-CUS-5005` | medium | **fixed** — Close out live on the one status it is not for |
| `DEF-CUS-5004` | low | **fixed** — three absence sentences on no screen, retired |
| `DEF-BIL-5090` | high | **FILED, NOT FIXED** — found by this lane; billing's file, another wave's |

---

## 0 · WHICH PROCESS, AND IT WAS DECIDED RATHER THAN ASSUMED

`22-product-maintenance-process.md`'s one question is about the USER, not the
code: **can a user do this task in the product today?** A clerk can record a
payment, read an account and close one out. All five rows are therefore
**MAINTENANCE**, and the three steps Build does not have were done first:

* **REPRODUCE** — the product was booted and driven before any code was read.
* **LOCATE** — the file actually mounted, which cost one real surprise: the
  Audit tab's false sentence is rendered by `accountDetailTabs.tsx`, not by
  either of the two files the brief named, and it is a `title=` attribute no
  screenshot shows.
* **BLAST RADIUS, both ways** — see §6. One finding (8 fixtures, five of them a
  concurrent wave's files) changed the shape of the fix.

---

## 1 · REPRODUCED FIRST, WITH THE STEP-1 INSTRUMENT

PostgreSQL 16 on `:5432` (`migrate --check` clean), Django on `127.0.0.1:8630`,
the SPA built with `vite build` and served by `server.mjs` on `:8631` with
`API_PROXY_TARGET` pointed at the backend — the same-origin shape the product
ships. Signed in as `dana@brazosbendutilities.com` on `brazosbend`.

`10-scripts/cr094_lane2_account_detail_walkthrough.mjs` re-run unchanged:
**15 pass · 9 fail · 1 not confirmed**, the same result step 1 recorded. Every
one of this wave's four screen faults reproduced, verbatim:

| fault | what the browser showed |
|---|---|
| money, shown | `2410.000000 USD` on the modal's balance line |
| money, pre-filled | `#amount` `inputValue()` = `2410.000000` |
| the note hint | `This flag is recorded and does nothing yet: there is no customer portal in this version, so no customer can read the note either way.` |
| the audit hover | `… There is no customer portal in this version, so no entry can come from a customer.` |
| the sub-type | `small_commercial` |
| Close out on `A-12048` (`pending_activation`) | **LIVE** |

⚠ **AND THE STEP-1 INSTRUMENT CARRIES ONE FALSE POSITIVE WORTH RECORDING**: its
over-precise-money regex returned `["2.237", "2410.000000"]` — the sidebar's
version badge `v2.237.10` matched as money. One true finding printed beside one
permanent false one trains its reader to skim both, so this wave's own
walkthrough strips `\bv?\d+\.\d+\.\d+\b` first and says why in the code.

---

## 2 · THE MONEY — `DEF-CUS-4999` / `DEF-CUS-5008`

**Two rows, ONE bug.** Lane 2 measured `2410.000000` on `A-11812`; lane 5
measured `247.300000` on `A-10432`, an hour apart. Both are
`AccountActions.tsx` lines 321 and 234. `4999` is closed `fixed`; `5008` is
closed `duplicate` with `4999` named in its own row — not left open to be fixed
a second time.

**Hard rule 2**, PO re-sign 2026-08-22, verbatim: *"MOney 4 decimal, percentage
6 decimal , display both 2 decimal"*.

### 2.1 · What was NOT wrong, stated first because it is where a lane will look

`accounts.balance` is `DecimalField(max_digits=18, decimal_places=6)` and hard
rule 2 says in terms that **existing 18,6 columns stay lawful containers — the
rule governs what is WRITTEN and what new columns declare**. DRF serving
`"2410.000000"` is correct on the wire too. **Only the display half was broken,
in exactly two lines of one file.** Both the code and the test now say so, so a
later lane cannot "fix" the column.

### 2.2 · Why it read as deliberate

`formatMoney`'s fallback for an amount it cannot parse is, at
`MoneyCell.tsx`, ``return `${amount} ${currency}` `` — **byte-identical to what
line 321 hard-coded**. The modal therefore rendered the shared formatter's
*error path* in place of its normal one, permanently, and a reviewer comparing
it against the codebase saw a shape the codebase genuinely contains elsewhere.

### 2.3 · The fix, and the one new function

`MoneyCell` renders the balance (`isAmountAbsent` before it, never `=== null` —
`DEF-176`, where an omitted key read `undefined`, took the money branch and
killed a whole Finance route). `formatMoneyInput` pre-fills the box.

**It lives beside `formatMoney` and not at the call site** (BR-SHL-023, one
money path) and shares its every decision: the same `DECIMAL_STRING_RE`, the
same `MONEY_DISPLAY_DECIMALS`, the same `roundingMode: "halfExpand"` (B4.4 ❄️
half-up), the same verbatim pass-through for a malformed amount, the same
refusal to touch a float.

**Its two differences are deliberate and are the reason it exists:**

* **THE LOCALE IS PINNED TO THE WIRE'S AND IS NOT A PARAMETER.** `formatMoney`
  takes the tenant's Regional format because it renders for eyes; this renders a
  value that goes BACK to the server, and `de-DE` produces `2410,00`, which the
  serializer refuses. Offering a caller a locale here would invite that bug.
* **AN ABSENT AMOUNT IS THE EMPTY STRING, not a throw and not a zero.**
  `formatMoney` raises `MoneyAmountAbsent` and that is right for a CELL; a
  required form field cannot render a sentence, and `0.00` is a number nobody
  read off a cheque that submits cleanly.

### 2.4 · Measured, before and after, on the same accounts

| | before | after |
|---|---|---|
| `A-10432` balance line | `247.300000 USD` | **`$247.30`** |
| `A-10432` `#amount` | `247.300000` | **`247.30`** |
| `A-11812` balance line | `2410.000000 USD` | **`$2,410.00`** |
| `A-11812` `#amount` | `2410.000000` | **`2410.00`** |

**The after-figures are COMPUTED values read back**, not class names: the box is
read with `inputValue()` and the balance as rendered text. A
`toContain("cell-money")` would pass over `247.300000` inside the right span,
which is the false pass the check is written to rule out.

---

## 3 · THE FALSE SENTENCES — `DEF-CUS-4998`

**Two surfaces, and a test that had been defending one of them.**

`AccountActions.test.tsx:295` asserted `toContain("no customer portal")`. So the
suite **required the false claim to be present** — `DEF-CUS-4298`'s recorded
shape, quoted in `accountDetailTabs.tsx` itself: *"The test asserted the
sentence was PRESENT, which is not the same question as whether it is TRUE."*
It was proved RED before the catalogue moved, and the failure quoted the whole
false sentence back.

### 3.1 · What is actually true, checked rather than assumed

* **`AccountNote.customer_visible` is still CAPTURED AND INERT.** Zero
  references to `AccountNote` anywhere under `apps/portal/` — no portal screen
  reads the table. So the flag doing nothing is TRUE; the REASON given for it
  had stopped being true.
* **A portal actor DOES reach `audit_log` today.**
  `apps/portal/credentials.py` writes `portal_credential.create` with
  `after={"actor": "portal:self-enrolment", …}` and `actor_user_id = None`. The
  old third sentence — *"no entry can come from a customer"* — was false on the
  record as well as in principle.

### 3.2 · The replacements

| key | now reads |
|---|---|
| `customers.account.note.customerVisibleInert` | **"Saved with the note. Nothing shows it to customers yet."** |
| `customers.account.audit.portalActorWhy` | **"Who acted is recorded. The channel is not."** |

Every sentence is within rule 33's cap (4 + 6 words, and 4 + 4). The hover's
automation clause was dropped rather than reworded: the VISIBLE line beside it
already says *"Every entry names who or what made it: a member of staff, an
automation, or the system"*, and repeating it is rule 32's description budget.

**All eleven catalogues moved together**, through `10-scripts/i18n_fanin.py` —
the tool that OWNS those files. Law 11's last clause is why it was looked for
rather than hand-rolled, and its round-trip was **proved byte-stable on all
eleven at 15,646 keys** before it was trusted. Diff: `2 insertions · 2
deletions` per catalogue, exactly the two rewritten lines.

---

## 4 · THE SUB-TYPE — `DEF-CUS-5000`

`small_commercial` on screen, beside a Category cell that correctly read
`Commercial`. B14 **rule 31** (*"no Databse ID on screen - that is a rule"*) and
rule 32.

**The label now travels on the wire beside the code**, mirroring the
`status` / `status_name` pair the same serialiser already serves four lines up.
It is not a front-end catalogue string and could not be one:
`account_subtypes` is **tenant-defined** — BR-CUS-067's twelve rows seed per
tenant and a tenant may add its own — so a catalogue of tenant data re-creates
`DEF-684` under a new key prefix. It costs no query (`account_subtype` is
already `select_related` in `account_queryset`), and a `django_assert_num_queries(0)`
case pins that.

**The fallback is the CODE and never a guess.** `accountCategoryName`'s own
reasoning: invent a label and `government` quietly starts reading as
"Municipal", the one substitution BR-CUS-094 forbids by name. A code on screen
is a fact about the DATA; a wrong word is a lie about it.

---

## 5 · CLOSE OUT — `DEF-CUS-5005`

**The blueprint's own truth table, `ACC-A05`, p27, read as an image:**

| ACCOUNT STATUS | SEEDED? | CLOSE OUT (as drawn) |
|---|---|---|
| Active | 68 accounts | Disabled |
| Marked disconnect | 1 | Disabled |
| Vacation hold | 1 | Disabled |
| Closed | 1 | Disabled |
| Pending activation | 1 | **Live — and should not be** |
| Disconnected | none | *the one status it is for, and it has no account* |

Its caption is the defect: **"the only status that opens this button is the one
it was not written for."**

**The cause.** The gate read `isOccupyingAccount(detail) || isClosedAccount(detail)`
— which covers `billable`, `billable_base_only` and `terminal` — and
`pending_activation` is `non_billable`, so a draft fell out of BOTH tests and
the control rendered live. It named **the states that refuse** and let
everything else through.

**The fix names the one state it IS for**, which is the shape that cannot rot: a
refusal list must be re-checked every time BR-CUS-055's tenant-extensible status
set grows, and an allow list of one need not — a status a tenant adds tomorrow
gets the refusal rather than the button. It mirrors
`close_out.eligibility`'s THIRD blocker, `not_a_cut_account`, and subsumes the
first two.

**By CODE and not by class, on `isDraftAccount`'s own recorded precedent:**
`disconnected` and `pending_activation` are BOTH `non_billable` (BR-CUS-107), so
the behaviour class cannot tell a cut account from a draft — which is exactly
this confusion. The server names the code too (`disconnects.CUT_STATUS_CODE`).

**It is a display guard and not the rule.** The server re-asks the whole question
under a lock and needs a disconnect case in state `cut` WITH a date, so a
`disconnected` account with no such case still gets
`close_out_not_a_cut_account`.

### 5.1 · ⚠ THE ALLOW ROW CANNOT BE WALKED ON THIS FIXTURE, AND THAT IS STATED RATHER THAN BLURRED

A gate that only ever refuses passes every *is it disabled here* assertion ever
written — hard-won law 7's *incapable of passing*. So the allow row matters more
than the five refusals, and it is proved by a **six-row truth table rendering
the real component** in `AccountDetailPage.test.tsx`, not in a browser.

`10-scripts/cr094_wave_b_seed_cut_account.py` drove the product's own disconnect
services to try to make the missing account — ladder opened, advanced to tier 3,
certified-mail service attested, cut scheduled, cut committed. It reaches a real
`cut` case and **stops short of a `disconnected` ACCOUNT**, because the product
refuses:

1. **`CC-RECON` is configured on NO tenant** — the demo seed spells its
   reconnection fee `RECON` — so `commit_cut` refuses every cut in this tree.
   `disconnects.py` reports the mismatch in its own words and says a ruling is
   owed. The script does what the refusal instructs (*"Configure the
   reconnection charge code, then cut"*) and mirrors the tenant's own `RECON`
   row; it decides nothing.
2. **`DEF-BIL-5090`** — §6.
3. **The cut bill is refused for want of a connection size**:
   `cut_bill.outcome = "blocked"`, *"service 'electric' has no connection size
   RECORDED on this connection … a size may not be guessed"*. The tenant holds
   **8 connections against 73 accounts**, so this is not one unlucky account.
   `commit_cut` therefore HOLDS BR-CUS-107's status
   (`CUT_BILL_BLOCKED_SO_STATUS_HELD`) — correctly, since writing it over a
   refused bill is `OQ-1170`'s $23.23 restored by a convenience.

**Inventing a meter size to light a screen up would be a fixture lying about a
household's plumbing**, so it was not done.

---

## 6 · BLAST RADIUS, BOTH WAYS

**What else uses what I changed.**

* `account_row` serves both the account LIST and the DETAIL, so
  `account_subtype_name` reaches both. Additive; no consumer reads a key that
  moved.
* Making it REQUIRED in `endpoints.ts` goes red in **8 fixtures** — measured:
  `AccountDetailPage.test.tsx`, `AccountsPage.test.tsx`,
  `DisconnectWizard.test.tsx`, `MoveEntryPoints.dom.test.tsx`,
  `MoveInWizard.test.tsx`, `MoveOutWizard.test.tsx`, `TransferWizard.test.tsx`,
  `screenVoice.guard.test.tsx`. **Five are a concurrent wave's files**, and a
  mass shared-file rewrite is what law 11 exists to prevent. It is therefore
  declared OPTIONAL, on the documented precedent of `premises_id?` eight lines
  above it in the same interface, **and the same debt is recorded there**: the
  wire really carries it on every row, one added line per fixture is owed, and
  the day it lands the `?` comes off.
* `formatMoneyInput` is new, so nothing else could break on it; `formatMoney`,
  `formatRate` and `MoneyCell` are untouched.

**What else USED what I removed.** Three catalogue keys were retired
(`customers.account.arrives.customer`, `.customerTitle`, `.usage`) and all three
were grepped for their CONSUMERS first — including the computed-key form
`t("…arrives." + x)` that `G112` exists for — **0 references each**. This is
hard rule 8's own lesson generalised (`DEF-CUS-3653`: before retiring a value,
grep for its consumers, because an absence is invisible to every check this repo
has), and the walkthrough asserts positively that the Customer panel still
renders the sentence it DOES use, so a retirement that took a live string with
it would fail.

**Retired rather than rendered**, on the precedent `accountDetailTabs.tsx` set
for `arrives.usageTrend` on 2026-09-07: *"A false sentence that no longer
renders is still a false sentence a grep will return."* All three were also
STALE, so rendering them was never an option — `arrives.usage` says no usage bar
can be drawn and the chart has drawn real readings since `DEF-CUS-4621`–`4626`;
`arrives.customer` says the duplicate check is still missing and
`identity_match.py` has been the built answer since `CR-056` W2, and its 39
words of roadmap prose are rule 33's zero-word class regardless.

---

## 7 · `DEF-BIL-5090` — FOUND HERE, FIXED NOWHERE

**`POST /accounts/{id}/disconnect-case/cut` cannot commit a cut.**
`billing/one_time.create_one_time_run` writes
`run_by_id=getattr(run_by, "pk", run_by)`. The API's actor is
`SimpleNamespace(id=…, role=…)` — **no `pk`** — so the whole namespace is written
into a UUID column:

```
django.core.exceptions.ValidationError:
  ["“namespace(id=UUID('01a08ad1-…'), role='system_admin')” is not a valid UUID."]
```

**Why every cut test passes.** `tests/test_us_met_helpers.staff_actor` returns
`SimpleNamespace(id=…, pk=…, role=…, user=…)` — **a fixture actor wider than the
production one**. `getattr(run_by, "pk")` resolves, and the suite proves the code
agrees with the fixture. That is hard-won law 7's *structurally incapable of
failing*, living in a fixture rather than in a gate, and it is the most reusable
finding of this wave.

`fee_bill.py` passes `run_by=actor` into the same writer, so the reconnection-fee
path has the same shape.

**NOT fixed here**: `apps/billing/` is another module and another wave's file,
and the cure is a judgment (one shared actor factory, or `actor.id` at every
write point) rather than a patch. Filed high.

---

## 8 · WHAT WAS SEEDED, DISCLOSED

* **`CC-RECON` configured on `brazosbend` at `$45.00`**, mirroring that tenant's
  own `RECON` row rather than a figure this lane chose.
* **`A-11996`** carries disconnect case **`DSC-26-0011`**, state `scheduled`,
  cut scheduled for 2026-09-07, and one issued **$45.00** reconnection-fee bill
  **`BL-2609-000093`**. Its status is still `active` — the cut bill was refused,
  so BR-CUS-107's status was held, which is the product behaving correctly.
* Nothing else. `A-11812`, `A-12048`, `A-10432`, `AC-2026-00043` and
  `AC-2026-00052` were deliberately excluded from the seed script's candidate
  set so a sibling lane re-running its step-1 measurements reads the same
  product it did.

---

## 9 · PROVED

**In a browser, at 1280 AND 1440: `10-scripts/cr094_wave_b_walkthrough.mjs` —
42 pass · 0 fail.** Screenshots and page text under `/tmp/cr094-wave-b`. Every
check prints what it looked for AND what it found instead (law 7's third habit).

⚠ **THE FIRST RUN FAILED THE SUB-TYPE ROW AT BOTH WIDTHS AND THE CODE WAS
RIGHT** — `runserver --noreload` was still holding the pre-fix serialiser in
memory. A browser proof taken against a stale process is not a proof of the
branch, and only the browser could have caught it: `tsc`, both unit suites and
every gate were green over it.

**Every new assertion shown RED first, in the harness that will run it** (law 7,
second half):

| assertion | the red it was shown |
|---|---|
| the modal's money | `value="2410.000000"` and `<span class="kv-v">2410.000000 USD</span>`, quoted from the rendered markup |
| the false sentence | the whole 24-word sentence quoted back by `not.toContain` |
| the sub-type | `<dt>Sub-type</dt><dd>small_commercial</dd>`, quoted |
| the Close out table | `pending_activation: Close out must be refused`, over a button rendered with no `disabled` attribute and no title |
| the served label | `KeyError: 'account_subtype_name'` |

**Suites, this wave's own files only** (a whole-suite total would not be
reproducible — four other `CR-094` waves were pushing throughout):

| file | after | before |
|---|---|---|
| `MoneyCell.test.tsx` | 22 passed | 17 |
| `AccountActions.test.tsx` | 28 passed | 26 |
| `AccountDetailPage.test.tsx` | 65 passed · 8 todo | 63 · 8 |
| `test_def_cus_5000_subtype_label.py` | 7 passed | new |

`tsc --noEmit` clean · `vite build` clean.

---

## 10 · WHAT THIS WAVE DID NOT TOUCH

The five ending-service screens (`MoveOutWizard`, `CloseOutPage`,
`closeOutEndpoints`, `TransferWizard`, `DisconnectWizard`),
`customers/selectors.py`'s list/sort code, the requests and import screens, the
starting-service wizards, and `DataTable` / `PageHeader` / `RowActions` /
`ListPager` / `KPIStrip.css`. Two lanes in one file is law 11 mechanism two, and
every check in that law passes over it.

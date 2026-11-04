# Billing §02 · STEP 2 — the bill detail and four of its tabs, BUILT

`CR-101-BRC03` · built 2026-09-14 · version **`2.263.0`** · branch
`claude/eager-johnson-r0k88b`

**Scope: entries 02 (the parent), 02.2 Charges, 02.3 Corrections, 02.4 Audit and
02.5 Sent.** Entry 01 (All bills) and entry 02.1 (Document) belong to other lanes
and nothing here touches them, with one stated exception recorded below.

**What step 1 routed to this lane, and what happened to it**

| | drawn | matched | differed | absent | built | not built |
|---|---|---|---|---|---|---|
| **02** parent | 19 | 8 | 3 | 8 | **10** | 1 |
| **02.2** Charges | 23 | 15 | 7 | 1 | **8** | 1 |
| **02.3** Corrections | 22 | 2 | 5 | 15 | **19** | 0 |
| **02.4** Audit | 21 | 13 | 3 | 5 | **0 — blocked** | 8 |
| **02.5** Sent | 15 | 7 | 4 | 4 | **8** | 1 |

**44 of the 55 drawn differences in this lane's five entries are built.** The
eleven that are not are named below, each with the reason, and eight of them are
one blocked entry.

---

## How it was built

**From the images, at 2× and 5×, never from the extracted text** (B14 rule 42).
The PDF was derived from the default branch by the lane itself —
`git show "origin/claude/confirm-understanding-3ktufc:05-prototype/04 Billing, As
Built.pdf"`, sha256 `137a2a48…c200971`, 14,363,163 bytes — rather than from any
copy, because a derived copy is a second source free to drift (hard-won law 5).
Pages p005–p028 at scale 2, plus three crops at 4× and 5× for the header's
emphasis, the *What happened* table and the credit-note columns.

**Walked in Chromium at 1440 AND 1280**, signed in as
`dana@brazosbendutilities.com` on tenant `brazosbend`, against a restarted
backend carrying this lane's own server change. Seven screenshots at 1440 are in
`SCRATCH/step2-shots/detail-*.png`; the structural capture is `walk.json`
beside them.

---

## Entry 02 · the parent — 10 built

| Drawn | Built |
|---|---|
| copy-the-bill-number glyph | a `<button>` inside the `<h1>`, with three states — a clipboard write can be refused over plain HTTP and both failure modes reject rather than throw, so the label says which happened and reverts |
| the customer's name, bold | `customer_name`, already served |
| the service address, linked | derived off `GET /accounts/{id}`, which walked to `premises` for it — **hard rule 8: the invoice carries no address column and must not grow one** |
| `$751.01 due 08/22/2026` | the money line, both halves bold |
| `billed 08/02/2026` | the issue date, which was on **no** screen in the product and is what a clerk checks a posted payment against |
| the account number BARE | it read `Account AC-2026-00011`; the drawing spends no word on a label in front of a string beginning `AC-` |
| a `…` overflow | `Print bill` and `Cancel this bill`, each keeping its reason |
| tab `Sent`, third of five | built — see 02.5 |
| `Corrections ₀` — a count | credit notes plus a replacement, so `0` is a real answer and is drawn as one |
| one pill, not two | the second pill (`Past-due unknown`) is gone; the fact still reads once, in words, on Charges |

**The emphasis is the drawing's and the step-1 diff has it backwards.** Its
element 26 reads *"`View the bill as sent` as the filled primary, `Fix this
bill` secondary"*. Measured at 5× on p015 — and identically on p018, p021, p022,
p024 and p027 — `Fix this bill` is the one BOXED control and `View the bill as
sent` is unboxed grey text. Built to the drawing; filed as **`DEF-BIL-5244`** so
a step-3 lane does not flip it back.

**NOT BUILT — 1.** The cycle still reads `CY-007` and the drawing names it
`Silver Creek — monthly`. `cycle_label` serves the CODE; the utility's own words
exist on the printed PDF and not on the payload. **`DEF-BIL-5245`.**

---

## Entry 02.2 · Charges — 8 built

**Seven columns become five.** `Accounting code` and `Rate version` ride under
the description. `Rate version` was **324 px of 1,086 — the widest column in the
table** — and the least-used thing on the screen. Nothing is lost: a line with no
accounting code at all still says so, which the first draft of the fold dropped
and `US-BIL-026 TC-2` caught.

**Four one-word group labels** — `AMOUNT · BY SERVICE · EVERY CHARGE · TAX` —
through the kit's own `Kicker`, which is the accent letterspaced label the
drawing shows and is already the product's vocabulary. No new visual decision.

**`Total` is bold.** It rendered at weight 400 / 13.5px while the same figure six
inches up rendered at 800 / 15px. That is p020's alignment finding 4, re-measured
on this branch and closed.

**One `Total tax` row instead of the same figure twice.** With a single authority
the per-authority subtotal and the bill's tax are the same number six pixels
apart; with two or more each still earns its line, because that is what OQ-1190's
ruling is for.

**NOT BUILT — 1, deliberately.** The `When this is due` panel STAYS on Charges.
The drawing moves it to the Document tab as `DATES`, and **the Document tab is
another lane's wave-2 work**. Removing it now would delete `Past due` and `Fees
on this bill` from the product with nowhere to land. The header's second pill was
removed in the same change precisely because that fact still reads here.

⚠ **AND THE DRAWING'S OWN PROSE OVER-CLAIMS, WHICH THIS LANE CONFIRMS RATHER
THAN DISCOVERS.** p020 concludes that folding the two text columns makes *"the
other four straighten out on their own"*. Measured on the redesigned frame at 6×:
`USAGE` is still LEFT-aligned beside two right-aligned money columns (finding 1),
and the base-charge row's two em-dashes still sit on opposite sides (finding 5).
**A lane that builds this drawing and then closes findings 1 and 5 will have
closed nothing.** This build matches the drawing, so both findings stand.

---

## Entry 02.3 · Corrections — 19 built, and the populated state rendered for the first time

The blueprint's own red rail says nobody had ever seen this state: *"the three
standings, the credit-note table and the replacement link have **never been
rendered together**."* They have now, on `BL-2607-000032`, with served values.

**Empty state** — `STANDING` (a green pill and one sentence) · `HISTORY`
(*Nothing to report.* and the rule about why nothing ever overwrites) · and
**`Fix this bill` on the tab**, which is the point of the redraw: the clerk who
clicks *Corrections* and finds none is the one who wants to start one.

**Populated state** — the `Replaced` pill and the link to the bill that counts
now; `WHAT HAPPENED` with one row per event in the drawn order (issued →
correction opened → approved → credit note → replacement), each with its date,
its reason **in words**, its actor with their role, and its effect; the **net
effect** footing the money column; and `CREDIT NOTES` kept as its own table in
the drawn column order.

### The server change this needed, and why it is not a browser sum

Four of the five drawn facts were not served at all. `GET /invoices/{id}/chain`
carried a number and an id per leg and nothing else. **Step 1 chipped this state
`Exists behind` and said the chip was a claim to CHECK rather than inherit — this
is the check, and the answer was no.** So `chain_of` is widened, additively:

* every leg carries `issued_at`, `total` and `currency` — **columns, read as
  stored**;
* every credit note carries its `reason` and its `issued_at`;
* the correction CASE comes with it, with its two actors as a **NAME and a ROLE
  and never an id** (B14 rule 31);
* **`net_effect`** — Σ(credit notes against this bill) + the replacement's total.

⚠ **`net_effect` IS THE ONE DERIVED FIGURE AND IT IS DERIVED ON THE SERVER.**
`BillDetailPage`'s own standing rule (PO 2026-08-30) is that the screen displays
what the server resolved; a browser-side sum of a customer's correction would be
a second implementation of an arithmetic no golden test can reach. It is summed
at the stored scale and rounded nowhere — hard rule 2 rounds at display and
`MoneyCell` is the display. **It moves no signed figure**: no B4 rule and no B5
golden test states a net-effect figure, and every input is a total the same table
already shows one row above. It is **`null`, never `0.0000`**, when nothing has
corrected the bill, because *nothing happened* and *it netted to zero* are
different claims and the engine has a warning for the second.

**Worked, live:** `BL-2607-000032` stays at `$137.70`; `CM-0001` credits
`−$137.70`; `BL-2607-000047` charges `$137.15`; the customer is **`−$0.55`**
better off. Three rows, no UPDATE, no DELETE — hard rule 4 satisfied on the one
real correction this tenant has.

**Two drawn details deliberately not followed.**
1. The drawn standing sentence names the replacement's DATE. Ours does not:
   BR-SHL-034 is one date formatter and a date interpolated into a translated
   string is formatted by whoever built the string. The date is one row below, in
   the table, through `DateCell`.
2. The drawing has no state for a bill that IS a replacement. The product has
   one and it is truthful — *This is the current bill* plus `Replaces bill`. Step
   1 recorded it as a gap in the drawing; it stays, in the STANDING group.

---

## Entry 02.4 · Audit — NOTHING BUILT, AND THAT IS THE ANSWER

Both of this entry's `BUILD THIS` bands are chipped **`Blocked`**, and the
drawing gives the reason in its own words: the tab is `AuditTab`, imported from
`@/features/metering/PremisesDetailPage`, and **six detail screens mount it**.
*"Fixing it here fixes it everywhere: the right outcome and the wrong blast
radius to take on inside a billing change. It needs its own change request."*

Its three faults are real and all three are re-measured — an oldest-first default
sort where the log it links to sorts newest-first, a raw ISO timestamp beside a
formatted one in the same row, and `+7 more` as an inert `<span>` hiding seven of
ten changed fields. They are filed as **`DEF-BIL-5240`** with `module = metering`
so the row lands with the code rather than with the screen it was seen on, beside
`DEF-MET-4764` and `DEF-MET-4765`.

**The change request has not been raised by this lane** — it is a metering CR and
raising it from a billing build is the blast radius the drawing warns about. It
is the outstanding item.

---

## Entry 02.5 · Sent — 8 built, a new tab

A MOVE plus one new group. The delivery table is the one that was the last panel
of the first tab, below four panels of provenance — rows, refusals and reasons
byte for byte — now third of five tabs.

* `Print` and `Customer portal` instead of `pdf_print` and `portal`; `Queued`
  instead of `queued`. **`DEF-BIL-5237`'s billing half.** The mechanism mattered
  more than the two keys: the codes resolved through `t(key, { defaultValue: raw
  })` and **both namespaces held 0 keys in all eleven catalogues**, so the
  fallback was not a fallback — it was the only path there had ever been.
* `HOW THEY HEAR FROM US` — the paperless election, the primary contact's email
  and the postal address. p028 calls this group *"a proposal, not a redraw …
  NEW and needs a customers read"*; the read already existed.

**NOT BUILT — 1.** The `in print set PS-0014` sub-line under `Print`. The
delivery row serves no print set. p028 says it is *"the same read that would fill
screen 01's Printed column"*, which step 1 called the largest item in §02 and
which belongs to entry 01's lane.

---

## The one thing this lane got wrong, and how it was found

**The Sent tab's second group label reached a live screen as
`BILLING.BILL.PANEL.HOWTHEYHEAR`.** One key of 52 was minted in the code and
missed in the catalogues — and nothing went red. `tsc` passed. All 27 cases of
the screen's own suite passed. Both other billing suites passed. The i18n parity
gate passed, **because parity is the eleven agreeing with each other and they
agreed perfectly about a key none of them had.**

It was found by opening the screen in a browser and reading it.

`BillDetailKeys.test.ts` is the part of that a machine can keep doing: every
`t("literal")` on this screen must exist in all eleven catalogues, and every
prefix the screen builds a key from at runtime must be a namespace with something
in it — which is what `DEF-BIL-5237` was. **Proved red before green twice**: once
on the real missing key in all eleven languages, and again after the file was
switched off `node:fs` onto Vite's `?raw`, because a guard proved through a path
nobody uses is no proof of the thing that matters.

Two smaller things the same walk found: the address rendered `Silver Creek TX,
78611` with a comma North American addresses do not have, and the replacement
link had lost the drawn `→`.

---

## Two reds on this branch that this lane did not cause, dated

Measured **2026-09-14** in a clean `git worktree` at the pristine tip
`cddb4f79`, with none of this lane's work in it — both fail there identically:

* `src/components/regionalReachesTheScreen.dom.test.tsx` — *nothing in the
  product falls back to a hand-written format any more* — names
  `DisconnectWizard.tsx`, `TransferWizard.tsx` and `RunHistory.tsx`. Already
  filed: **`DEF-SHL-4994`** (open) and **`DEF-SHL-5101`**.
* `src/features/billing/BillsPage.test.tsx` — `US-BIL-025 TC-2` — the search
  census expects three columns and the list offers four. Already filed:
  **`DEF-BIL-5132`** (open, 2026-09-13).

Neither is re-filed and neither is touched.

---

## What this file is not

It is not permission to build anything else. Entry 01 and entry 02.1 are other
lanes' and are untouched here except for one shared component — `SummaryPanel`
renders on both Document and Charges and takes the drawn label `AMOUNT`, which is
what **both** frames show.

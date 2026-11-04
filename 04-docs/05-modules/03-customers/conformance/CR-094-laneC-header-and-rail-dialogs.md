# CR-094-BRC01 · lane C — the four panels that open from the account's header and rail

**Screen `S21` · `/:tenant/accounts/:accountId`.** The four dialogs a clerk opens
from the account detail without leaving it: **Record payment** (header, primary) ·
**Adjust** (header) · **Activate account** (header) · **Add note** (rail icon 7 of
7). Drawn in `blueprint/02-account-detail.md` as `ACC-A06`, `ACC-A05`, `ACC-A03`
and `ACC-A15`; redrawn in `blueprint/16-service-requests-list.md` as R4's
`ACC-Q06`, `ACC-Q01`, `ACC-Q03` and `ACC-Q13`.

Built to **B14 rule 41**, ratified 2026-09-13: *"it is expected that Product UI
will match extactly the way it is given in Blueprint document… Everything else —
layout, grouping, order, labels, which facts appear — is the drawing's and is
built."*

---

## 1 · THE FIGURE THAT MATTERS

| | before | after |
|---|---|---|
| Record payment fields in the drawn ORDER | **7 of 8** — `purpose` was LAST, past the memo box | **8 of 8** |
| drawn helper sentences present on Record payment | **3 of 5** | **5 of 5** |
| Add note's helper attached to the drawn field | no — it was under `Note` | **yes — under `Title`** |
| Adjust fields marked required that the server refuses without | **1 of 2** (`Reason` was not) | **2 of 2** |
| dialogs whose sub-line carries the account number the drawing shows | **0 of 4** | **0 of 4** — `DEF-CUS-5168`, another lane's file |

**Four defects filed and fixed here** (`DEF-CUS-5164`, `5165`, `5166`, `5167`) and
**one filed and left** (`DEF-CUS-5168`).

---

## 2 · THE DRAWING, QUOTED — not linked (skill §1)

### `ACC-A06` · Record payment — *"a modal, not a wizard — one step, eight fields, and it commits"*

```
✕Record a payment
BRAMBLE BAKERY · A-11812
BALANCE
2410.000000 USD
worked out from the ledger — every posted charge, less every posted payment
Amount *                      Starts at the balance shown above and can be changed.
What this money is for *      Against bills · Deposit · Plan down payment · Prepayment
Posting date *                The day this payment counts from.
Clearing date                 The day the money actually arrived.
Method                        ACH · Card · Cash · Check · Lockbox · Money order · Wire.
Reference or cheque number    Whatever the customer can quote back.
Apply to                      Oldest open bill first · A specific bill · Carry as account credit · Split across bills
Memo                          Kept with the payment and read by anyone asking why later.
Cancel   Record payment
```
The frame's own caption: *"Three faults on this form, all drawn as they are. The
balance reads 2410.000000 USD and the amount field is pre-filled with the same six
decimals. Money displays to two."*

**R4's `ACC-Q06` puts the same eight in the same order**, under the headings THE
MONEY and WHERE IT GOES, with the same helper sentences word for word. **Two
independent drawings of one form agreeing on the order is what settles it** — the
order is the design and not an extraction accident.

### `ACC-A15` · Add note — *"two fields, two flags — and one of the flags does nothing yet"*

```
Add note
BRAMBLE BAKERY · A-11812
Title
Fill in a title, a note, or both.
Note
Pin to the top
Visible to the customer
This flag is recorded and does nothing yet: there is no customer portal in this
version, so no customer can read the note either way.
Cancel   Save note
```

### `ACC-A05` · Adjust and `ACC-A03` · Activate — **both drawings are OVERTAKEN**

The as-built frames draw `Adjust` **disabled**, carrying *"Adjustments are billing
rows, and billing is not built. There is no endpoint to post one to"*, and
`Activate account` as *"no wizard and no confirmation… the account is Active
before the page has finished redrawing."*

**Neither describes the product any more, and both changed on the day this lane
ran.** `Adjust` became a live dialog that morning (`DEF-CUS-5126`: every clause of
that refusal was false — `POST /accounts/{id}/payments` has taken
`type: "adjustment"` since `CR-059` CS-35 on 2026-09-02), and `Activate account`
became `ACC-S14`'s confirmation form in wave J. **Recorded, not followed** —
skill §16, *"r10 is right and the spec is stale; file it, don't follow it"*, read
in the other direction: here the PRODUCT is ahead of the as-built frame and the
remedy frames `ACC-Q01`/`ACC-Q03` are what it was built to.

---

## 3 · THE CENSUS — walked in Chromium at 1280 AND 1440, before and after

Driven against the production join (`npx vite build`, then `server.mjs` with
`API_PROXY_TARGET`), signed in as `dana@brazosbendutilities.com`, on the two
accounts the blueprint itself draws: **A-11812** (Bramble Bakery, active) and
**A-12048** (Kwan, Michael, pending activation — the only account in the
deployment `Activate account` can be opened on at all).

| dialog | card at 1280 | card at 1440 |
|---|---|---|
| Record a payment | 560 × 836 | 560 × 836 |
| Post adjustment | 560 × 648 | 560 × 648 |
| Activate this account | 560 × 836 | 560 × 836 |
| Add note | 560 × 516 | 560 × 516 |

Every one is inside the 836px cap `ModalShell` took at `ffe3a8152`, at both
widths, and none of them changed height by a pixel across this work.

**Record payment, read off the screen BEFORE:** `amount · posted_at · cleared_at ·
method · confirmation · apply_to · memo · purpose`. **AFTER:** `amount · purpose ·
posted_at · cleared_at · method · confirmation · apply_to · memo` — the drawn
order, and the one field that moved is `purpose`.

---

## 4 · WHAT THE DIFF FOUND, AND WHERE EACH GAP WENT

| # | what the drawing says | what the screen did | routed |
|---|---|---|---|
| 1 | `What this money is for` is the SECOND field | it was the LAST, past the memo box | **built** — `DEF-CUS-5164` |
| 2 | `Reference or cheque number` carries *"Whatever the customer can quote back."* | no helper at all | **built** — `DEF-CUS-5165` |
| 3 | `Memo` carries *"Kept with the payment and read by anyone asking why later."* | no helper at all | **built** — `DEF-CUS-5165` |
| 4 | `Fill in a title, a note, or both.` sits under `Title` | it sat under `Note` | **built** — `DEF-CUS-5166` |
| 5 | — (found against the SERVER, not the drawing) | `Adjust`'s `Reason` was optional on a form whose endpoint refuses without one | **built** — `DEF-CUS-5167` |
| 6 | the sub-line reads `BRAMBLE BAKERY · A-11812` | it reads `BRAMBLE BAKERY` | **filed, not built** — `DEF-CUS-5168`, `AccountDetailPage.tsx` is lane D's |
| 7 | `Adjust` is disabled with its reason | it is a live dialog | **drawing overtaken** — `DEF-CUS-5126`, same day |
| 8 | `Activate account` commits on the click | it opens `ACC-S14`'s confirmation | **drawing overtaken** — wave J |
| 9 | the inert-flag sentence names *"no customer portal in this version"* | it says *"Saved with the note. Nothing shows it to customers yet."* | **drawing overtaken** — `DEF-CUS-4998`, and the drawn sentence is now FALSE |

---

## 5 · THE ONE PLACE THIS SCREEN AND ITS TWIN NOW DISAGREE — said out loud

`S35`'s Record modal (`features/payments/PaymentsPage.tsx`) was reordered on
2026-09-03 after the PO walked the deployed form — *"too much text on the form and
Im not sure whether inputs are arranged in logical order"* (`DEF-3507`) — and the
answer taken there was **who paid → how much → when → how → what it is for**, with
`purpose` and `apply_to` ADJACENT at the foot, *"because purpose is the coarse
question and apply_to the fine one."*

**That fix names `S22` in its own trace header and never reached `S22`.** For ten
days the account-side form kept the exact shape the PO rejected — purpose at the
very bottom, on the far side of the memo box from the allocation choice — while
its twin two clicks away was fixed, and nothing noticed, because **`S35` has a
field-order test and `S22` had none.**

**This lane built the BLUEPRINT's order, not `S35`'s**, because rule 41 is
explicit that order is the drawing's, and because the blueprint draws it twice the
same way. The two forms now agree on seven of eight positions and differ on
`purpose`. **Whether they should be reconciled, and in which direction, is a
person's call and not this lane's** — it is the open half of `DEF-CUS-5164`.

---

## 6 · WHAT WAS DELIBERATELY NOT CHANGED

* **The three long helper sentences on Record payment** — `payments.form.postedAtHelp`,
  `clearedAtHelp` and `purposeHelp`, plus `customers.account.payment.methodHelp`.
  Each is longer than the sentence the drawing draws, and the drawing draws **no
  prose at all** under `Method` and `What this money is for` (it shows the option
  list, which the select already offers — B14 rule 32's *"a row never repeats what
  its own control offers"*). **Three of the four are `payments.form.*` keys shared
  with `S35`**, where `DEF-3507` deliberately moved that copy into a `<details>`
  CLOSED by default rather than deleting it. Re-wording them here would re-word
  another screen from this one's authority, which is exactly what B14 rule 38
  forbids for a kit change and what this lane has no mandate for. **Reported.**
* **`Adjust`'s form shape.** R4's `ACC-Q01` draws four sections, eleven fields, an
  approval block and a recap. It is `ACC-S14`'s, it is roughly fifty catalogue
  keys in eleven languages, and it is a wave rather than a conformance pass. The
  dialog built this morning is r10's `Post adjustment` with its three divergences
  already recorded in its own docstring.
* **R4's Record-payment additions** — the late fee, the credits available, the
  bill-by-bill allocation table and the outstanding remainder. `ACC-S14`'s own
  card says these *"wait on an open-bills call that already exists and on a
  late-fee figure that does not."* Not built, not promised.
* **The `Send statement` and `Adjust` entries in `accountQuickActions.ts`.** That
  file is not this lane's and its census now disagrees with `AccountActions.tsx`
  in two places: it still declares `adjust` as `held` (it is live) and
  `sendStatement` as a `form` (`UNAVAILABLE_ACTIONS` still holds it). **Reported
  to whoever owns that file — not edited here.**

---

## 7 · HOW IT WAS PROVED (step 2d)

**Nine new cases in `AccountActions.dom.test.tsx`, and SEVEN of them were shown
RED FIRST**, in a detached `git worktree` pinned at this lane's starting tip
`ffe3a8152`, through the harness that runs them (`npx vitest run`, never
`__main__`):

| what was broken (i.e. the product before this lane) | what went red |
|---|---|
| `purpose` last instead of second | *expected [ 'amount', 'posted_at', …(6) ] to deeply equal [ 'amount', 'purpose', …(6) ]* |
| no helper on `confirmation` | *expected '' to be 'Whatever the customer can quote back.'* |
| no helper on `memo` | *expected '' to be 'Kept with the payment and read by any…'* |
| `Reason` not marked required | *expected null not to be null* |
| the Adjust form submitting with no reason | *Unable to find an element with the text: Choose a reason…* |
| the note helper absent from `Title` | *expected '' to be 'Fill in a title, a note, or both.'* |
| the note helper still on `Note` | *expected 'Fill in a title, a note, or both.' to be ''* |

The two that passed at the pre-fix tip are **carried regression guards and are
declared as such in the file**: the two-decimal money case (fixed 2026-09-12 by
`DEF-CUS-4999`/`5008`, re-asserted here because this lane MOVED a field in that
form) and Add note's four-row order, which was already right.

⚠ **THE HELPER IS READ THE WAY A SCREEN READER READS IT**, through the input's own
`aria-describedby`, never by searching the page for the sentence. A page-text
assertion passes wherever the sentence happens to render, which is precisely the
defect `DEF-CUS-5166` is.

⚠ **`tsc` WAS ITSELF PROVED.** `./node_modules/.bin/tsc --noEmit` printing nothing
is indistinguishable from hard-won law 7's false pass, so a type error was
injected into `AccountActions.tsx` and the LOCAL binary — version **5.5.4** —
named it: `AccountActions.tsx(899,7): error TS2322: Type 'string' is not
assignable to type 'number'.` It was removed and the file verified byte-identical
before the run was trusted.

⚠ **NOT PROVED, AND SAID RATHER THAN IMPLIED: no pixel is asserted.** jsdom
computes no layout, so B14 rule 39's 5 / 6 / 20 figures have no check here or
anywhere in this repo. What the browser walk measured is the CARD, not the gaps.

---

## 8 · THE REDS THAT ARE NOT OURS, EACH DATED

**Measured as a subtraction rather than asserted**: the same two suites
(`src/features/customers` + `src/features/payments`) were run in a throwaway
`git worktree` pinned at the clean tip `f6fa3670d`, twice — once as the tip, once
with only this lane's two files copied in.

| | test files | failed | passed |
|---|---|---|---|
| the clean tip `f6fa3670d` | 3 | **13** | 1,237 |
| the clean tip **+ lane C** | 3 | **13** | **1,246** |

**The same thirteen, and nine more passing.** This lane caused no red.

| red | dated with `git log -S` | whose |
|---|---|---|
| `accountRailHoldExpiry.test.ts` — *the rail is still SEVEN*, got 8 | the eighth glyph (`communication`) landed in `300a51d33`, **2026-09-12 21:37** | `DEF-SHL-5131`, named in this lane's brief |
| `AccountPanelEdits.dom.test.tsx` TC-N7b — *a contact write is wrapped now* | `updateAccountContact` was added in `9a9e55c24`, **2026-09-13 09:36** | the write-doors lane; the refusal it guards has expired |
| `AccountDetailPage.test.tsx` — 13-vs-14 groups, 41-vs-46 rows | the UNIT group landed in `f6fa3670d`, **2026-09-13 13:30**; the counts were last set in `0968fc112`, 09:13 | lane D, same day |
| `AccountDetailPage.test.tsx` — *Statements are not built yet* | the sentence was replaced in `e14d22004`, **2026-09-13 04:42** | the Send-statement lane |
| `AccountDetailPage.test.tsx` — Meters/Services columns, `M-4021`, `>Electric<` | the Meters tab was rebuilt in `97e4edb8d`, **2026-09-13 09:31** | the money-tabs lane |

**Two further files fail in the SHARED tree and in neither worktree** —
`MoveEntryPoints.dom.test.tsx` (1) and `CloseOutPage.dom.test.tsx` (2). Both are
siblings' **uncommitted** edits to `MoveInWizard.tsx`, `MoveOutWizard.tsx` and
`closeOutEndpoints.ts`, on no branch at the time of writing.

**`G27` is the same story and it is worth stating precisely, because the shared
tree reports it as a failure:** in the shared tree G27 FAILS on
`ChangePlanWizard.tsx` (5 keys) and `PaymentPlanWizard.tsx` (1 key) and on a
coverage ratchet at 574 against a baseline of 558. **At the clean tip with this
lane's change applied it PASSES** — 482 absent against the same baseline, *"every
literal and config-carried translation key resolves in en.json"*. Both failing
files are a sibling's uncommitted work.

---

## 9 · A LANE COLLISION THAT COST NOTHING AND IS RECORDED ANYWAY

This lane fanned three keys into all eleven catalogues with `10-scripts/i18n_fanin.py`
at about 13:23. **Lane D's commit `f6fa3670d` at 13:30 published all three**, in
all eleven files, because a pathspec commit takes the whole working-tree content
of every path it names — CLAUDE.md law 11, mechanism five, `DEF-168` exactly.

**Nothing was lost and nothing had to be undone**: the eleven catalogues in the
shared tree were then byte-identical to the tip, so this lane pushes **no locale
file at all** and its keys are already on the branch. What it left for seven
minutes was three catalogue keys with no call site, which no gate in this repo
looks for.

It is written down because the mechanism is the one that DOES lose work when the
two lanes happen to touch the same key, and because the cheap habit that made it
harmless is the one worth repeating: **before pushing a shared file, diff your
copy against the pinned tip and find out who else has been in it.**

---

<!-- packet: CR-094-BRC01 step 2 lane C · blueprint 02-account-detail.md ACC-A03/A05/A06/A15 · 16-service-requests-list.md ACC-Q01/Q03/Q06/Q13 · 14-ui-conventions.md rules 31, 32, 33, 38, 39, 41 · CLAUDE.md hard rule 2, hard-won laws 2, 6, 7, 11 -->
<!-- generated: 2026-09-13 by the CR-094 lane C build lane -->

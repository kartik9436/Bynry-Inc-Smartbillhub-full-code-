# CR-140-BRC07 — a Write-offs link on the Debtors tab

**Raised:** 2026-09-23, by the Product Owner, answering `OQ-PAY-12613`.
**Branch:** `BRC07`, `claude/laughing-thompson-kpmwih`. Number from `allocate.py cr`, checked
free against the remote with `allocate.py cr --verify 140` at allocation and again at push.
**Version:** `2.347.0`.
**Classification:** **CHANGE**, **screen-shaped.** The product did what was agreed: blueprint
7·3b draws *one* door into the write-off approval queue, and one door is what shipped once
`DEF-PAY-6329` pointed it at the right screen. The PO has now asked for a second. That is a new
requirement, not our miss, so it is a change and not a defect (`13-change-process.md` §1).
**Screen owner:** lane WRITEOFFS-LINK, for the length of this change.
**Drawing file:** `05-prototype/06 Payments Page Blueprint.pdf` — p081 (7·1 Debtors, the head
the link sits in) and p086 (7·3b Write-offs, the queue it opens), rendered as images at 1.3.

---

## 0 · What arrived, in the requester's words

> *"3 Add a Write-offs link on the Debtors tab? (b) add it - fix it"*

**The case the PO was shown:** Dana asks for a **$1,202.40** write-off on Monday. On Tuesday she
wants to know whether it was approved. From Payments there is no way in: the only link to the
queue appears in the panel shown straight after a write-off is submitted.

---

## 1 · What is being reversed

**One drawn statement, and the PO has overridden it.** Blueprint p086, 7·3b's Doors row:
*"Finance → Revenue & AR. 1 door, and it works."* There are now two doors to the one queue.

**Nothing signed moves.** No ❄️ FROZEN B4/B5 figure, no business rule, no money path. The
`/finance/write-offs` route and `WriteOffQueuePage.tsx` stay deleted and unrouted (`CR-135`
P1.10) — one more door, never a second queue.

---

## 2 · Impact across the surfaces

| surface | impact |
|---|---|
| screens | **S34 Debtors (7·1) gains one link at its head**, beside the existing *Collections* link. It opens **S36 Revenue & AR**, where `WriteOffQueuePanel` lives. No other screen changes. |
| routes | none. The link goes through `financeTabPath(FINANCE_TAB_REVENUE)`, the one place that decides where a Finance tab lives — the same call the result panel's door uses since `DEF-PAY-6329`. |
| copy | one key, `payments.outstandings.writeOffs`, in all eleven catalogues through `10-scripts/i18n_fanin.py`, each in the destination's own word: *Write-offs · Ausbuchungen · Bajas · Bajas · Mises en perte · बट्टे खाते · Penghapusan · Stralci · 償却 · 대손 처리 · Baixas*. One word or two — a label (B14 rule 33). |
| API / schema / data | none. |
| roles | **see §4** — the link is not drawn for a role that cannot open Finance. |
| open questions | `OQ-PAY-12613` closed by the ruling (recorded by the coordinator). One new question raised in §6. |
| demo fixture | none. |

---

## 3 · What was already built that this makes wrong

**Nothing.** The change is additive. The result-panel door (`OutstandingsTab.tsx`,
`financeQueueHref`) is untouched and still opens the same address.

---

## 4 · A judgment where the rules ran out — who sees the link

**Revenue & AR is gated on A4's Finance cell (`finance_reconcile_export`), which
`identity/0003` gives a System Admin and an Executive and NOT a Billing Clerk.** Drawn for
a clerk, the link would open *"You don't have access"* — a working screen behind a dead door.

So the link is drawn **only where the Finance cell is not `—`**: `BR-SHL-003` already hides
navigation into a module a role cannot reach. While the cell is still unknown it IS drawn,
because `BR-SHL-025` says an unanswered permission read hides nothing (the server's 403 is the
boundary either way).

**Worked figure:** Dana as drawn on p081 is *"Dana Whitfield · System Admin"* — she sees the
link and reaches her $1,202.40 request. Sam, a Billing Clerk, sees *Collections* and no
*Write-offs*; he would have been refused on the other side.

---

## 5 · Proof

`07-frontend/src/features/payments/writeOffsHeadDoor.dom.test.tsx`, seven cases. It opens the
**app's own route table** (`APP_ROUTES`) at `/brazosbend/payments/outstandings`, proves the page
on screen is the Debtors tab (the mounted route, its `:tab` param and the strip's
`aria-selected`), reads the href **off the rendered anchor**, then **presses it in the same
router** and reads the destination back three ways: the address, the screen id (`S36` /
`FIN-01`, not `S56`) and the component mounted there (`RevenueArPage`, not
`GeneralLedgerPage`). It asserts the href does not start with `//` and is not
`/finance/write-offs`.

**Red first, on the tip (`ee0dd2be6`), in vitest:** 5 of 7 failed with
`Unable to find role="link" and name "Write-offs"`; the two absence cases passed, as an absence
should. **Then three mutations of the finished code, each restored byte-for-byte afterwards:**

| mutation | result |
|---|---|
| link points at the bare `/finance` — `DEF-PAY-6329`'s shape | 4 red: `expected '/brazosbend/finance' to be '/brazosbend/finance/revenue'` · `expected 'S56' to be 'S36'` |
| link drawn for every role | 1 red: the clerk case, `expected <a data-variant="secondary" …(3)></a> to be null` |
| tenant dropped from the href | 4 red: `expected '/finance/revenue' to be '/brazosbend/finance/revenue'` · `expected null to be 'S36'` |

Green after: 7 of 7. Neighbours green: `sevenTabs`, `writeOffQueueDoor`, `writeOffOneQueue`,
`counterDoors`, `PaymentsPage.test`, `debtorScreens`, `locales.test`.

**Two reds this lane did not cause, dated rather than waved at (hard-won law 7, habit 1):**

* `src/components/selectionToolbarWiring.test.ts` — 2 cases, red since `68db7d740`, when
  `OutstandingsTab.tsx` stopped composing the kit's `SelectionToolbar` (`DEF-PAY-6337`, already
  filed). This change does not touch `OutstandingsTab.tsx` and the count is unchanged.
* `eslint` on `PaymentsPage.tsx` — **24 `no-unused-vars` errors.** Measured by linting the
  file's own history: 0 until `f77dca804` left `COUNTER_START_ROUTE` imported and unused (1),
  then **23 more in `c5ed21bb9`** (the Record-a-payment page, `DEF-PAY-6317`), which moved the
  record form off this screen and left its imports and helpers behind. The same 24 with and
  without this change; none is on a line it wrote. Filed as `DEF-PAY-6368`.

---

## 6 · Still open — put to the PO by the coordinator, not decided here

**A Billing Clerk who requests a write-off still cannot see whether it was approved.** Both
doors (this link and the result panel's) lead to Revenue & AR, and A4 refuses Revenue & AR to a
clerk. If the clerk in the PO's case is a Billing Clerk rather than p081's System Admin, the
ruling does not reach her. Answering it means widening a signed permission row or showing a
request's status inside Payments, which is the PO's call, not this lane's.

---

## 7 · Version and rollback

`2.347.0` — a CHANGE level, allocated against the remote and re-verified at push.

**Rollback:** revert the commit. It removes one `ButtonLink`, one permission read that shares
an existing request, one catalogue key in eleven files, and one test file. No data, no route
and no schema is touched.

---

## 8 · Close

**Conformance diff (step 8's fourth row):** p081's head draws *Start counter →* and *Record
payment*. The running Debtors head draws the counter slot, *Collections* (`P0.9`) and now
*Write-offs* (this CR); the two links are there by ruling. Whether *Record payment* belongs on
the Debtors head is not this change's question and was not touched. **The closure bar's "a person did the task on
the screen" is still owed** — this lane proved it in the app's own router under vitest, not in
a browser.

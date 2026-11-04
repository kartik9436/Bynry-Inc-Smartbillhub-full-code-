# CR-094-BRC01 · step 2 wave L — the eight quick actions move OVER the account

**Screen `S21` · `/:tenant/accounts/:accountId`.** Builds **`BR-CUS-1051`**, PO
ruling 2026-09-13, verbatim: ***"Yes move the eight quick actions over the
account"***. Product **`2.242.0`**.

Wave J delivered `ACC-S14` for three of thirteen and left eight navigating away,
**correctly** — each already owned a complete, tested, multi-step form with
park-and-resume. This wave moves the CONTAINER and re-types none of the form.

---

## 1 · THE FIGURE THAT MATTERS

| | before this wave | after |
|---|---|---|
| open OVER the account | **3** of 13 | **11** of 13 |
| take the clerk off the account | **9** (finding `F12`) | **0** |
| held with their reason (`BR-SHL-025`) | 2 | **2** — `Adjust`, `Send statement` |
| lines of existing screen **mounted** | — | **8,838** |
| lines of existing screen **copied** | — | **0** |

The 8,838 is counted, not estimated: `MoveInWizard` 1,827 · `DisconnectWizard`
1,723 · `MoveOutWizard` 1,546 · `PaymentPlanWizard` 913 · `ChangePlanWizard` 895
· `FixABillTab` 759 · `BillDocumentPage` 740 · `CloseOutPage` 435. (`BR-CUS-1051`
says *"about 7,300"* — wave J's estimate of the six wizards. The rule is not
amended; its figure does rhetorical work, not arithmetic.)

**The whole of this wave's new code:** one 290-line container, two OPTIONAL props
on `ModalShell`, a three-line path fallback in `DisconnectWizard`, the route
table, and one catalogue key.

---

## 2 · THE JUDGMENT THE RULING LEFT OPEN: THE CONTAINER IS A **ROUTE**

The obvious build — a `useState` flag on `AccountDetailPage` — would have cost
three things and forced eight screens to be edited to get them back.

| a state-flag dialog would have cost | the nesting keeps it, free |
|---|---|
| `useParams().accountId` | five of the eight read their subject that way; **none needed a prop** |
| `?step=` across a reload | three park a half-finished job there |
| the exit | each screen already leaves by `navigate(accountDetailPath(accountId))`, which **un-matches the child and closes the dialog** |
| the address | every path is the string it already was |

⚠ **AND THIS IS WHY IT DOES NOT COLLIDE WITH THE *estimate precedent*.** The
skill's §5 table reserves *"needs an address a person can send"*, *"must survive a
refresh"* and *"more than one step"* for a SCREEN rather than a modal. **A ROUTED
dialog has all three.** B14 rule 30 stays DECLINED, nothing here is a rule, and a
lane meeting a different form asks the estimate test again rather than citing this.

---

## 3 · THE EIGHT, AND BOTH DOORS

| # | control | mounts | its account-scoped address | its OWN address, untouched |
|---|---|---|---|---|
| 1 | Move-out | `MoveOutWizard` | `/accounts/{id}/move-out` | also `/move-outs/new` |
| 2 | Move-in | `MoveInWizard` | `/accounts/{id}/move-in` | also `/move-ins/new` |
| 3 | Close out | `CloseOutPage` | `/accounts/{id}/close-out` | — |
| 4 | Print bill | `BillDocumentPage` | `/accounts/{id}/bills/{invoiceId}/document` | `/billing/bills/{id}/document` |
| 5 | Issue credit | `FixABillTab` | `/accounts/{id}/issue-credit?bill={id}` | `/billing/fix?bill={id}` |
| 6 | Change plan | `ChangePlanWizard` | `/accounts/{id}/change-plan` | — |
| 7 | Disconnect notice | `DisconnectWizard` | `/accounts/{id}/disconnect` | `/disconnects/new?account={id}` |
| 8 | Payment plan | `PaymentPlanWizard` | `/accounts/{id}/payment-plan` | — |

**Five addresses are the strings they already were** — a nesting, not a
re-addressing. **Three gain a second address and keep their first**, which is the
`/move-ins/new` precedent read again: two routes, one screen, one id, and no debt
count moves.

⚠ **`Print bill` is the only segment carrying a parameter**, because it is the
only one of the eight whose subject is a BILL. WHICH bill is still
`accountRailReadiness`'s derivation (the newest ISSUED one) and did not move.
⚠ **`Issue credit` mounts the TAB, not `BillsListPage`** — a clerk who pressed
*Issue credit* on one account did not ask for every bill in the utility.

---

## 4 · THE ONE SCREEN THAT NEEDED A LINE CHANGED

`DisconnectWizard` read its subject from `?account=` and nothing else. Mounted at
`/accounts/{id}/disconnect` it would have opened **the account finder over the
very account it was launched from**. It now falls back to
`useParams().accountId`; `/disconnects/new` and `/disconnects/new?account=`
behave exactly as before.

**No screen's post-commit navigation was changed.** `DisconnectWizard` still
finishes at the Disconnects tab and `MoveOutWizard` still parks to the parked
list — that is each screen's own contract **at both doors**, and changing it here
would change it for callers who never asked.

---

## 5 · THE DIALOG HEAD, AND WHY IT IS BARE

Seven of the eight draw their own `PageHeader` — kicker, 32px title (B14 rule 40),
roll-up, and a back arrow already pointing at this account. A dialog head with the
action's name too is **two headings on one surface**, which is the description
budget B14 rule 32 caps. So `ModalShell` gained `titleHidden`: the ✕ alone, with
the action's name as the dialog's `aria-label`.

**`Issue credit` is the declared exception.** `FixABillTab` is a TAB —
`BillsListPage` draws the head at its own address — so here the dialog supplies
the title. The flag is `ownsItsHeading` on the overlay row, and **a test reads
each mounted screen's source and fails when the flag stops being true of it**.

`ModalShell` also gained `size="wide"` (`w-[min(1120px,100%)]!`). Both props are
optional; absent means what it always did, so every existing caller renders
byte-for-byte as before. **No second dialog shell was written** (skill §7.2).

---

## 6 · HOW IT WAS PROVED (step 2d)

**42 cases across two files, green — and TEN sabotages each shown RED FIRST**,
through the harness that runs them (`npx vitest run`, never `__main__`):

| broken | went red |
|---|---|
| a child route deleted | *the account route owns children…* |
| a child pointed at the wrong screen | *each child opens the screen the overlay table names, BY COMPONENT* |
| `move-out` re-spelled `moveout` | *does not re-spell the five addresses…* + 6 more |
| `/disconnects/new` pointed elsewhere | *the disconnect wizard is still at /disconnects/new* |
| the dialog made to open unasked | *renders nothing at all on the bare account* |
| a half-resolved `:invoiceId` link built | *throws rather than putting :invoiceId in the URL bar* |
| `ownsItsHeading` flipped on `CloseOutPage` | *says a screen draws its own PageHeader only where it does* |
| `size="wide"` dropped | *is WIDE — a six-step wizard is not a 560px card* |
| the title hidden on the screen that has none | *draws a visible title for the one screen…* |
| an overlay left unreached | *every mounted action names an overlay the container actually declares* |

**And one case clicks.** `MoveEntryPoints.dom.test.tsx` now starts on the account,
presses *Move-out* through the real route table, and asserts the whole chain: the
URL, the dialog, the wizard's own H1, and **the account still rendered behind it**.
That is the nearest this suite gets to hard-won law 6.

⚠ **TWO ASSERTIONS THIS WAVE REALLY DID BREAK, AMENDED RATHER THAN DELETED.**
`MoveEntryPoints`' two account-scoped cases looked for `1408 Elm St · A` in the
whole document; both addresses now render the account behind the wizard, so both
found it TWICE. Scoped to the dialog they are **stronger** than they were — before,
a premise rendered by anything at all satisfied them. The *"no finder"* half of
each stays unscoped on purpose.

---

## 7 · WHAT WAS NOT DONE, AND THE REDS THAT ARE NOT OURS

**Not done:** the two held actions (the ruling names eight); documents, the
communication section and the account-edit surfaces (`ACC-S1`/`ACC-S15`).

**Not proved in a BROWSER.** The running product was not driven this wave, so
hard-won law 6's diff against the prototype is **owed**.

**Five reds on the branch, none caused here** — each measured RED at `feed3007f`,
the commit before this wave's first, in a throwaway worktree rather than asserted
from memory:

| red | dated |
|---|---|
| `screenIds.test.tsx` — five routes missing | `DEF-SHL-5116`, oldest `19e446875` of 2026-09-06. **This wave added eight rows and the diff is still exactly those five.** |
| `AccountDetailPage.test.tsx` TC-2, Meters tab | `DEF-CUS-5124`, filed 2026-09-12 |
| `accountRailHoldExpiry.test.ts` — rail is 8, test says 7 | **filed here as `DEF-SHL-5131`**; caused by `300a51d33`, 2026-09-12 |
| `BillsPage.test.tsx` US-BIL-025 TC-2 — 4 search columns, test says 3 | **filed here as `DEF-BIL-5132`** |
| `regionalReachesTheScreen.dom.test.tsx` — 3 `?? "UTC"` fallbacks | the offending lines are byte-identical at `feed3007f`; two of the three files were never touched here |

---

<!-- packet: CR-094-BRC01 step 2 wave L · BR-CUS-1051 · decision log 2026-09-13 · B14 rules 30 (declined), 32, 38, 39, 40 -->
<!-- generated: 2026-09-13 by the CR-094 wave L build lane · product 2.242.0 -->

---

## 8 · THE GATES, RUN BY NAME AND NOT AS A SUITE

The whole 123-gate suite runs the golden pytest suite and takes 40+ minutes on a
box carrying eight lanes, so the seven whose declared surface this wave touches
were run by name — **and each was run TWICE: once in the shared tree, once in a
private `git worktree` at the pinned tip**, because the shared tree carries four
other lanes' uncommitted work and a gate there is measuring them as much as us.

| gate | at the clean tip | whose |
|---|---|---|
| `G31` declared classes | **PASS**, 0 undeclared at a baseline of 0 | the 4 it reports in the shared tree are a sibling's uncommitted work |
| `G29` screen ids | **was FAIL → now PASS** | **ours** — see below |
| `G13` unwired props | FAIL — `AccountCommunicationDialog`, `portal/listTable` | not ours |
| `G27` translation keys | FAIL — `AccountCommunicationDialog`, 3 keys | not ours |
| `G15` i18n parity | FAIL — 292 new English values | **identical failure at `feed3007f`**, so not ours |
| `G07` human-owned | FAIL — four migrations | not ours; this wave wrote none |
| `G17` duplicate ids | FAIL — `4497`, `4512`, one more | not ours; ours are `5131`/`5132` |

⚠ **`G29` IS THE ONE THIS WAVE MOVED, AND IT WENT RED FIRST — WHICH IS THE
PROOF RATHER THAN AN INCONVENIENCE.** It read **PASS at 131 screens / 142
routes** at `feed3007f`, and this wave's three new addresses took it to
**134 / 145**, so it failed on exactly the rise it exists to catch. The ratchet
in `10-scripts/gates/screen_id_baseline.txt` now carries the block that explains
the move: three routes, **no new screen and no new id** — each row carries the
ids of the screen it MOUNTS, the `/move-ins/new` precedent — and
`screens_without_a1` rises by **two, not three**, because A1 numbers neither the
rendered bill document nor the disconnect wizard **at their existing addresses
either**, so a second address cannot be where an A1 id gets invented.

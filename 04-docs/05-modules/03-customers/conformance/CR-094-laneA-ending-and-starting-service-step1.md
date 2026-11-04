# Lane A · step 1 — move-out, move-in and close-out against their drawings

**Measured 2026-09-13 at `ffe3a8152` (v2.259.1), in a browser, signed in as a
billing clerk, at 1280 and 1440 — the staff app's two required widths.**
Thirteen screens opened: move-out steps 1–6, move-in steps 1–6, close-out.

**Scope.** Three of the twenty-two account actions:
`MoveOutWizard.tsx` · `MoveInWizard.tsx` · `CloseOutPage.tsx`.
**Excluded, and named so nobody reads silence as a pass:** the move-out and
move-in DONE screens, the `MVO-`/`MVI-` record pages, the Move-outs and Move-ins
tabs, the account Overview the three of them open over, and the eight-word
`RaiseFieldWork` panel they each mount (another lane's file — `DEF-CUS-5161`).

**The container is NOT in scope and is NOT a divergence.** The blueprint draws
all three as full pages with the app nav; `BR-CUS-1051` (PO, 2026-09-13 —
*"Yes move the eight quick actions over the account"*) is newer and rules the
CONTAINER. Everything the drawing puts INSIDE is what this file measures.

---

## 1 · The drawings, quoted

### Move-out — `blueprint/08-move-out-wizard.md`, pages 98–106

Every one of the six screens opens the same way:

```
←  Account A-10432
MOVE-OUT
The account                          ← step 1's own title, at 32px
Step 1 of 6 · Find account
Save & exit
1 Find account 2 Date & final reads 3 Final bill & deposit 4 The shortfall
5 What happens next 6 Review & close
```

and the six titles, in order, are
`The account` · `Date & final reads` · `Final bill & deposit` ·
`The shortfall` · `What happens next` · `Review & close`.

### Move-in — `blueprint/04-move-in-wizard.md`, pages 66–74

```
←  Account A-10432
MOVE-IN
The unit
Step 1 of 6 · Find unit
Save & exit
1 Find unit 2 Customer 3 Start & read 4 Account preferences 5 Deposit 6 Review
```

Titles: `The unit` · `Who is moving in?` · `Start date & reads` ·
`Account preferences` · `Deposit` · `Review`.

`blueprint/05-move-in-wizard-standalone.md` adds only the second address —
*"`/:tenant/move-ins/new` — the same MoveInWizard as screen 04, entered with no
account chosen"*, four doors, `Complete move-in ✓`.

### Close-out — `blueprint/10-close-out.md` → the text lives in `09-…-standalone.md`

Three screens drawn; the first is this lane's:

```
←  Account A-11488
CLOSE OUT ACCOUNT
Close out this account
A-11488 · Okafor, D. · cut on 08/18/2026
Save & exit

The account you are closing
  Account number   A-11488          Customer          Okafor, D.
  Customer number  C-00318          Category          Residential · Standard
  Status now       Disconnected · non-billable
  Service address  77 Rio Grande, Silver Creek, TX 78611
  Unit             U-001207 · Unit 2
  Services         Electric · Water Opened            06/03/2021

What was cut, and when
  Disconnect case  DSC-26-0114      Reason            Non-payment
  Services cut     Electric · Water Cut on            08/18/2026
  Final metered bill  $23.23 · 18 days of 31
  Base charges since  None — they stop at the cut
  Balance          $612.75 · unchanged since the cut

What you are recording
  Closing this account out on *   [date]  Today, or the day the decision was actually made.
  Why *                           [text]  A sentence, in your own words.
  Status it takes                 Closed ▼  A terminal status.
  A LIST OF REASONS TO PICK FROM — there is none.

What pressing this writes     WHAT | VALUE | WHY THAT          (5 rows)
What it will not do                                            (5 rows)
NOTHING HAS BEEN CHECKED FOR YOU
When it refuses               IF | WHAT YOU ARE TOLD           (6 rows)

←  Back to the account                        Record the close-out
```

⚠ **Rule 37 applies to every figure above.** `A-11488`, `$612.75`, `08/18/2026`,
`43 days` are ILLUSTRATIONS. No test in this lane asserts one and no fixture is
seeded from one.

---

## 2 · What is on screen today

| screen | head | step line | body |
|---|---|---|---|
| move-out 1–6 | kicker `MOVE-OUT`, H1 `Close an account and free the unit.` on **every** step, a 4-line roll-up | `Step 1 of 6` | six panels, close to the drawing |
| move-in 1–6 | kicker `MOVE-IN`, H1 `New occupant moving into a vacant unit.` on **every** step, roll-up opening **`Five steps.`** | **absent** | six panels, close to the drawing |
| close-out | kicker = the **account number**, H1 `Close out account`, **no roll-up** | n/a | 3 panels: what this will write · record the close-out · what this screen is not telling you |

---

## 3 · The diff, both directions, and where each one went

### Drawn and not on screen

| # | what | routed to |
|---|---|---|
| 1 | move-in's roll-up says **five** steps over a **six**-step rail | **BUILT** — derived from the declared list |
| 2 | the `Step N of 6 · <step name>` line has no step name (move-out) / no line at all (move-in) | **BUILT** on both |
| 3 | the 32px title is the FLOW's sentence, not the STEP's name | **`DEF-CUS-5160`** — not built, and the reason is in the row |
| 4 | close-out kicker `CLOSE OUT ACCOUNT`, title `Close out this account`, roll-up `<account> · <customer> · cut on <date>` | **BUILT** |
| 5 | close-out panel `The account you are closing`, nine rows | **BUILT** — `GET /accounts/{id}` already serves all nine and nothing called it |
| 6 | close-out panel `What was cut, and when`, seven rows | **BUILT** — four served after a read-only widening of the close-out preview; two stated absent |
| 7 | close-out `What pressing this writes` · `What it will not do` · `When it refuses` | **BUILT** |
| 8 | close-out's second and third drawn screens | **`DEF-CUS-5162`** |

### On screen and not drawn — kept, and why

The field-visit panel (move-out 2, move-in 3) and the park/resume controls
post-date the blueprint and are ruled work (`CR-070` wave P, `CR-035`). They
stay. The `Save & exit` the drawing puts in the head is in the wizard footer,
which is the shared frame's decision and not this screen's.

### Wrong, in neither direction

`DEF-CUS-5161` — the field-visit panel's lead sentence names a **move-out** on
the move-**in** screen, and on the transfer and service-request screens too.
`components/` is outside this lane.

---

## 4 · Where the missing rows come from

| drawn row | verdict |
|---|---|
| customer, customer number, category, status, address, unit, services, opened | **served** by `GET /accounts/{id}` — the screen simply never asked |
| disconnect case, cut on, balance | **served** by `GET /accounts/{id}/close-out` already |
| cut reason, services cut, the balance at the cut | **on the model** (`DisconnectCase.cut_reason`, `.services_cut`, `.outstanding_at_cut`) and not in the payload — served now, read-only |
| final metered bill, base charges since | **nothing exists** — billing has no invoices table. Stated as an absence, no column invented |

## 5 · Rule 33 against the drawing

Four drawn refusal sentences run past rule 33's six-word cap
(*"Enter the date you are closing this account out."* is nine). The screen keeps
this product's own wording, which `DEF-CUS-5087` wrote to that cap yesterday,
under the drawn `IF` label. A drawing that contradicts a signed rule is the one
thing rule 41 sends to the PO; this one does not need to go, because the rule
already has an answer on this screen and the answer is a day old.

---

# Close — what landed, measured (v2.260.0)

**Walked again in a browser at 1280 and 1440 after the build, with the eleven
catalogues live. The diff against the drawing is zero on presence, order and
labels for every row this lane owns.**

| measured | before | after |
|---|---|---|
| drawn panels on the close-out | 2 of 5 | **5 of 5** |
| drawn rows in *The account you are closing* | 0 of 9 | **9 of 9** |
| drawn rows in *What was cut, and when* | 0 of 7 | **7 of 7** (2 stated as not served) |
| wizard screens carrying `Step N of 6 · <name>` | 0 of 12 | **12 of 12** |
| the move-in's stated step count | `Five` over a six-step rail | derived from the list |
| close-out copy in the other ten languages | 0 keys | **94 keys, 0 pasted English** |
| translation-coverage debt (G27, baseline 558) | 482 | **452** |
| page title at 1280 and 1440 | 32px | 32px (B14 rule 40) |
| sideways scroll, any of the 7 frames walked | none | none |

**Guards proved RED first, in a `git worktree` at `ffe3a8152`, in `vitest`:**
ten — seven on the close-out (the cut date through the one formatter, the nine
account rows in order, the service badges, the two unserved figures, what the
press writes, the six refusals, and the rule-33 word count) and three on the
wizards (the derived step count, and the named step line on each).

**Required checks, after:** `tsc` clean of this lane's files ·
`acc02-tab-conformance` **0 divergence(s)** · `account-dialog-fit` **14 frames,
0 finding(s)** · `G27` the coverage ratchet green on this lane's keys · `G31`
**0 undeclared class(es)** and `routeBUtilities` **11/11**, which is the check
that owns `CloseOutPage.tsx` and compiles every class token for real.

## Reds, each dated

* **One was MINE and is fixed by me.** `MoveEntryPoints.dom.test.tsx` asked for
  the string `Step 1 of 6` exactly; the line gained a word. It is an anchored
  prefix now and still fails on `Step 1 of 5`, `Step 1 of 60` and `Step 2 of 6`.
  That file belongs to another lane; reporting a red you caused as somebody
  else's is the failure hard-won law 7 names.
* **Nine were red at `ffe3a8152` before this lane started** — measured by running
  them in a worktree at that commit, not asserted: `AccountDetailPage.test.tsx`
  and `AccountPanelEdits.dom.test.tsx`, 9 cases.
* **Four belong to files that landed while this lane worked** —
  `ChangePlanWizard.test.tsx` arrived in `f46197031`, and
  `accountRailHoldExpiry.test.ts` was named as pre-existing in this lane's own
  briefing.
* `G15` is red on **337** values pasted in English. **Zero of them are this
  lane's** — all 940 non-English values it adds were checked against `en.json`
  key by key.

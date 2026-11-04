# Billing blueprint · §09–§17 — the rulings, the registers, the build index

**Source.** `05-prototype/04 Billing, As Built.pdf`, pages **151–249**, read **as images**
(B14 rule 42; extraction on this PDF drops every slash, colon and digit from address lines).
Section boundaries were found by walking the pages, not taken from the brief: this lane was
told "roughly p180–p249" and the real first page of §09 is **p151**.

| § | Title | Pages |
|---|---|---|
| 09 | What happened when it was driven | 151–154 |
| 10 | Absence register | 154–158 |
| 11 | Rule compliance | 158–162 |
| 12 | Where to start — the build index | 162–168 |
| 13 | Cross-module | 168–172 |
| 14 | Specification register | 172–202 |
| 15 | What this pass changed, line by line | 202–206 |
| 16 | Appendix (rulings · judgments · open question · fields · A–K) | 206–215 |
| 17 | The rest of the screens, as built | 215–249 (H on p215; I/J/K on p246–249) |

⛔ **NOTHING HERE IS DECIDED, FILED OR ACTED ON.** This is step 1. The 27 rulings below are
transcribed so they can be COUNTED, not so they can be adopted. Whether the 15 that exist in
no file get written into the repository at all is a live question the coordinator has put to
the PO. **Do not copy any row of §1 into `12-governance/02-decision-log.md` on the strength of
this file.**

---

## 1 · Every ruling the document quotes — all 27, verbatim, with a repo check

The document's Appendix table (**p206–p208**) claims *"Fifteen of the twenty-seven exist
nowhere but here"*. **Both numbers check out.** I counted the rows on the images and ran the
greps myself.

| | Measured here | Document claims |
|---|---|---|
| Rulings in the table | **27** | 27 ✔ |
| Rows marked `NOWHERE` | **15** | 15 ✔ |
| Rows citing a repo home | **12** | 12 ✔ |
| Repo homes that actually resolve | **12 of 12** | — (the document asserted, did not show) |
| `NOWHERE` rows found by grep anywhere in the tree | **0 of 15** | — |

⚠ **The document contradicts itself about this number twice, in its own prose.** The count
(27/15) is right; two sentences around it are stale and a reader who quotes either is wrong:

* **p206, the red band beneath the "fifteen" sentence:** *"What the ruling costs is still true
  and worth saying once: **these twelve** cannot be grepped."* **Twelve, three lines below
  fifteen.** Twelve is the count before the three 2026-09-13 rulings (rows 25–27) were added.
* **p163, §12's build-component intro:** *"twelve of the **twenty-four** rulings exist in no
  file."* **24/12 against 27/15.** The build-component TABLE on p164 says `Rulings · 27 · 15
  exist nowhere but here`, so the section disagrees with itself one page apart.

**The count to carry forward is 27 and 15.** It is the one the two tables agree on and the one
I re-derived from the rows.

### Method for the "exists in the repo?" column

For each ruling, a fixed-string grep for a distinctive clause of the PO's own words across the
whole tree (`.git` and `node_modules` excluded), then a targeted check of
`12-governance/02-decision-log.md`, `12-governance/01-open-questions.md` and
`04-docs/05-modules/07-billing/02-business-rules.md`, plus the cited id where one is given.
**A grep returning nothing proves the grep was wrong, not that the thing is absent** — so
every `NOWHERE` row below was also searched for by SUBSTANCE (the rule it decides), not only
by its wording.

### 1.1 · The fifteen that exist in no file

Every one of these is a PO ruling given in chat on 2026-09-11, -12 or -13. **Grepped: 0 of 15
appear anywhere in the repository**, in any wording. The single string that does return a hit
— *"noting in repo"*, row 25 — hits exactly one file, `07-billing/blueprint/00-index.md`,
which is this same pass's own page map quoting the PDF. That is not a governance record.

| # | Ruling, verbatim | Date | Kind | What it decides (document's own column) | In repo? |
|---|---|---|---|---|---|
| 1 | *"we dont what full view of the document - you give a link to download but full view of document is not requires - it does not add any value to user"* | 2026-09-11 | new rule | The bill detail's embedded PDF viewer is removed; the document becomes a download link. | **NO** |
| 2 | *"our idea is to show all the data to billing clark before submitting the bill run - it kind of allow him to do all decision before hand, see the data correct the data and then submit it"* | 2026-09-11 | new rule (shapes a whole section) | The whole shape of §03: every decision is made before the run is submitted, not after. | **NO** |
| 3 | *"between step 1 and step 2 - we are bascially running pre bill check"* | 2026-09-11 | new rule | A pre-bill check runs stages 1–5 and writes nothing; screen 17.0 exists because of this. | **NO** |
| 4 | *"per conenction"* | 2026-09-11 | **new rule on a money path** | A master account's base charge is per connection, not per account. | **NO** |
| 5 | *"as per connection"* | 2026-09-11 | **new rule on a money path** | Each connection is governed by its own plan — its own taxes, fees and discounts. Worked: fee $0.57, bill $70.17. | **NO** |
| 6 | *"all dates should be date picker, all drop down should be drop down, all chips should be multi select"* | 2026-09-11 | new rule (UI, product-wide in effect) | Dates, dropdowns and chips across every billing screen; multi-select on chips is the new part. | **NO** |
| 7 | *"you can calculate it on screen - in such case we will have to show work in progress to clark"* | 2026-09-12 | new rule | The screen may compute and must then show a work-in-progress state; the rule stays on the server. | **NO** |
| 8 | *"we will ahve to make it wizard - 4 steps"* | 2026-09-12 | new rule (shapes a whole section) | Fix a bill becomes a four-step wizard — the whole of §06. | **NO** |
| 9 | *"so im confirming books wil be updated"* | 2026-09-12 | **confirmation on the ledger path** | Approval signs and execute posts, inside one transaction per bill. | **NO** |
| 10 | *"We will need Print bills as tab at Billing level"* | 2026-09-12 | new rule (shapes a whole section) | Print bills becomes the seventh Billing tab — the whole of §08. | **NO** |
| 11 | *"Budget bills run inside the regular cycle and must not run separately"* | 2026-09-12 | new rule | §05's shape, and why the bulk settle-up button was removed as a second writer. | **NO** |
| 12 | *"everything should be tagged with chip"* | 2026-09-13 | process ruling | The five-chip vocabulary and the commitment law this document is built on. | **NO** |
| 25 | *"We ahve to write everything in HTML artifact only Billing, as built - noting in repo"* | 2026-09-13 | **process ruling — and it is the one that creates the other fourteen** | Nothing is written to the repository. This artifact is the system of record for all of it — including this ruling. | **NO** (one hit, in this pass's own `00-index.md`) |
| 26 | *"Yes, if it is limit set in setting then - it is not hard coded; it should be based on setting"* | 2026-09-13 | **new rule on a money path** | The late-fee balance floor is tenant configuration, not a constant in the code. (`BIL-S102`, New build) | **NO** |
| 27 | *"you cannot change it here - it should be thorough process only"* | 2026-09-13 | new rule — **ratifies a refusal that until now rested on a docstring** | A charge line is never editable on the screen; a line changes only through the correction process. | **NO** |

⚠ **Four of these fifteen touch money or the ledger** — rows 4, 5, 9 and 26 — and one of them
(row 5) carries a worked figure (`fee $0.57, bill $70.17`) that exists in no golden test, no
business rule and no decision row.

⚠ **Row 27 is the one to read next to hard rule 4.** It ratifies the refusal that rule already
requires; it does not widen it. Nothing here asks to UPDATE an issued invoice line.

⚠ **Row 26 collides with nothing signed, but its FIGURE is unsettled.** §16's still-open
question (§3 below) is precisely *what balance the floor is measured against*, and that half
was never put to the PO. The ruling and the open question are two halves of the same rule.

### 1.2 · The twelve that do exist elsewhere — and all twelve resolve

Every citation in this half was checked against the file it names. **12 of 12 are real,
present, and say what the document says they say.**

| # | Ruling, verbatim | Date | Kind | Document's "where else it lives" | **Verified** |
|---|---|---|---|---|---|
| 13 | *"delivery is QUEUE-based … email ships W6"* | 2026-08-08 | new rule | `BR-BIL-016` CONFIRMED (PO A-7) | ✔ `07-billing/02-business-rules.md:23`, status CONFIRMED, PO A-7 2026-08-08 |
| 14 | *"B An export only"* | 2026-08-11 | ruling closing an open question | `BR-BIL-065` · `OQ-112` | ✔ `02-business-rules.md:97` quotes it verbatim; `01-open-questions.md:217` OQ-112 CLOSED quoting it |
| 15 | *"Give a running number always even for Draft"* | 2026-08-11 | new rule | `BR-BIL-063` | ✔ `02-business-rules.md:95`, verbatim, CONFIRMED 2026-08-11 |
| 16 | *"option A: the cap APPLIES"* | 2026-08-11 | ruling closing an open question | `OQ-104` CLOSED · `corrections.py:974` | ✔ `01-open-questions.md:209` OQ-104 CLOSED, option A, with its worked $1,840 figure |
| 17 | *"bulk APPLY of a late fee is allowed, bulk WAIVE is not"* | 2026-08-11 | new rule | `BR-BIL-060` CONFIRMED | ✔ `02-business-rules.md:92`, that exact carve-out, CONFIRMED |
| 18 | *"out platform will porvide standard 3 to 5 variouation of printed bill - user can use those only in V1"* | 2026-08-12 | new rule (scope) | decision log, 2026-08-12 | ✔ `02-decision-log.md:987`, PO verbatim, same day |
| 19 | *"Money 4 decimal, percentage 6 decimal, display both 2 decimal"* | 2026-08-22 | **re-sign of a hard rule** | hard rule 2 | ✔ `CLAUDE.md` hard rule 2, PO re-sign 2026-08-22 (repo's copy carries the leading *"We already confirmed this - "* the document drops) |
| 20 | *"it will be capture at the time of bulk billing - not here"* | 2026-08-23 | ruling closing an open question | `CR-029` D8③ · `OQ-241` CLOSED | ✔ `01-open-questions.md:340` OQ-241 CLOSED — RULED, verbatim, at CR-029 D8③ |
| 21 | *"you ahve to remove - Filters that arrive later … Export and column choices"* | 2026-08-27 | new rule | decision log · `CR-043` finding 10 | ✔ `02-decision-log.md:530`, both halves verbatim; also in `11-change-requests.md` |
| 22 | *"no Databse ID on screen - that is a rule"* | 2026-08-31 | new rule (B14) | B14 rule 31 | ✔ `14-ui-conventions.md:229`, rule 31 |
| 23 | *"Treat every number drawn in a wireframe as an illustration, never a fact to build to"* | 2026-09-10 | new rule (B14) | B14 rule 37 | ✔ `14-ui-conventions.md:56`, rule 37, verbatim, PO 2026-09-10 |
| 24 | *"in the forms for the fields. It starts with the field name. then the input field, and then it should show the helper text below that input field."* | 2026-09-11 | new rule (B14) | B14 rule 39 | ✔ `14-ui-conventions.md:58`, rule 39 — *one spacing scale, and a field is label → input → helper*, PO 2026-09-11 |

### 1.3 · What the routing looks like, if anyone ever files these

**Not done here, and deliberately.** For the coordinator:

* **12 rows are already in the repo** — nothing to do, and law 13 says do not re-ask them.
* **15 rows are ungreppable.** None of them is a re-ask: every one is a decision the PO gave
  once, in words, that no file carries.
* **None of the 15 reverses a signed rule on its face.** Rows 4, 5, 9 and 26 are money/ledger
  rules with no signed counterpart; row 27 ratifies an existing refusal; the rest are screen
  shape and process. **That is a reading of the text, not a clearance** — a lane proposing to
  file any of them still owes step 2 of the change process, quoting both sides.
* **The withdrawn commitment is `BIL-S101`** (p206): the card that used to undertake writing
  these to the repo was withdrawn by row 25 itself.

---

## 2 · Judgments taken in the document, because they were its own to take (§16, p208)

Two. Both are recorded with their figure, which is what makes them judgments rather than
questions. **Neither is in the repository either** — they inherit row 25's ruling.

| Decision | Taken | The figure it rests on |
|---|---|---|
| **An account is shown as in arrears at 60 days past due, or above twice its trailing average owed** | 2026-09-13 · `LANE JUDGMENT` | Screen 17.21 needed a threshold and had none. Ours because it decides when arrears are *surfaced*, moves no money and reverses no signed rule. 60 days / 2× average because both are already how the dunning ladder talks about age. **Revisable:** 30 or 90 is a setting, not a redraw. |
| **The pre-bill check runs in a worker with a progress state, and never inline** | 2026-09-13 · `ARITHMETIC` | **Measured: 137 ms per account on real PostgreSQL.** 25,000 accounts is **57 minutes**; the request wall is about **60 seconds**. Impossible above roughly **440 accounts**. `BIL-S41` already carries it. **It does not refuse above the bar** — it runs asynchronously and the screen fills in, because a refusal would leave a T5 utility unable to check at all. |

---

## 3 · The one question still open, and only the PO can close it (§16, p209)

Transcribed verbatim from the page. **It is not in `01-open-questions.md`** — the document
says so itself: *"It is here rather than in an open-questions register because nothing is
written to the repository — so this table is the register."*

> **Which balance does the late-fee floor test — the part that is actually ageing, or the
> whole bill?**
>
> A disputed amount does not age (`BR-MET-133` clause 4, ruled 2026-08-26). So on a **$1,000**
> bill with **$400** disputed, only **$600** ages, and the fee is **$9.00** rather than $15.00.
> That part is settled. What is not settled is which figure the floor is compared against:
>
> **On the ageing part:** a **$60** bill with **$40** disputed leaves **$20** ageing, which is
> under the floor — **no fee at all**. **On the whole bill:** $60 is over the floor, so a fee
> is charged on the $20. **The two readings differ by the entire fee on every small
> part-disputed bill.**
>
> **Why this is yours and not ours:** it changes what a customer is charged. Your 2026-09-13
> ruling settled that the floor is a *setting* rather than a constant, which is built as
> `BIL-S102` — but a setting still has to say what it is measured against, and that half was
> not in the question you answered. **One line closes it:** the ageing part, or the whole bill.

⚠ **`BR-MET-133` clause 4 exists and is cited correctly** — it is a Meter Reads rule, so this
question spans two modules. **This is the only thing in §09–§17 that looks like a genuine
PO-bound question**, and it is a money question.

---

## 4 · §09 — what happened when the product was driven

**Read every figure below against the document's own cover caveat**, which this lane is
required to carry forward: the walk was **front end only, no Django, no PostgreSQL, no real
row ever reached a screen**, and **4 of 15 screens were seen**.

| | |
|---|---|
| **Screens walked** | **4 of 15** |
| **Threw** (to a stack-trace page) | **6** |
| **Not reachable** (need a created run) | **5** |
| **Journeys walked** | **0**, of 350 in `08-qa/01-e2e/journeys/` |
| **Writes exercised** | **0** — no backend |

4 + 6 + 5 = 15, so the three columns partition the screen set exactly.

**Pass 1 — nothing stubbed: not one billing screen could be reached.** HTTP 200 on all ten
routes and the same frame every time — *"We couldn't load your regional settings."* with a
Retry, `navCount = 0`, **no left rail**. Cause: one boot read, `GET /shell/display` with
`retry:false`, gates the entire shell (`ShellWithSession.tsx:344–381`). Graded
`BY DESIGN, AND WORTH KNOWING`, not a defect. **The history beside it is the carry-forward
fact:** the same frame rendered over *every screen in the product* from 2026-08-21 to
2026-09-06 because the two reads it replaced were admin-gated and a Billing Clerk has no cell
for them (`DEF-SHL-4272`) — sixteen days, unseen, because every frontend test passes
formatting as a prop and every walkthrough in this repo signs in as a system admin.

**Pass 2 — three boot reads stubbed: four rendered, six threw.**

| # | Screen | Result | Severity |
|---|---|---|---|
| 01 | All bills | Rendered. Title 40px/800, 13-item rail, six tabs, search/filter/download/column-chooser/pager all present. Money at 2dp. **Five disabled controls.** | HEALTHY |
| 02 | One-time bill | Rendered. Step-1 buttons correctly disabled with no account chosen; rollup *"Not counted yet"* ×3 in the stated-absence style. | HEALTHY |
| 03 | Budget Bills | Rendered, empty list. | HEALTHY |
| 05 | Past billing runs | Rendered — **and this is the confirmation the audit was worth running for.** A full-width grey panel saying the list *"arrives with the billing run work"* over a module whose run wizard is live and whose run list is already mounted on step 1 of that wizard. | **THE JOURNEY COMPLETES, WRONGLY** |
| 04 | Fix a bill | `TypeError: Cannot read properties of undefined (reading 'map')` → *"Unexpected Application Error!"*, a JS stack trace, no left rail. | BLOCKS THE JOURNEY |
| 06 | Run bills wizard | `(servicesQuery.data ?? []).filter is not a function` — **the author's own fixture, not the product.** | MY FIXTURE |
| 07 | Pending queue | `TypeError: … (reading 'open')` → stack-trace page. | BLOCKS THE JOURNEY |
| 08 | Print bills | `TypeError: … (reading 'join')` → stack-trace page. | BLOCKS THE JOURNEY |
| 09 | Bill detail | `TypeError: … (reading 'previous_balance')`, then `(reading 'length')` → stack-trace page. | BLOCKS THE JOURNEY |
| 10 | Bill document | `TypeError: … (reading 'startsWith')` at `tenantPathFrom` → stack-trace page. | BLOCKS THE JOURNEY |

⚠ **"Six threw" is five product throws and one instrument fault.** Row 06 is the author's own
fixture returning an object where an array is served, and the document says so. A lane
quoting "six" without that split overstates the product by one.

**The one source fact that is NOT fixture-dependent, and it is the finding:** *"There is no
error boundary and no `errorElement` anywhere in the route tree."* A grep across the whole
non-test front end for `componentDidCatch`, `getDerivedStateFromError` and `errorElement`
returns **exactly one file** — `components/MoneyCell.tsx:326,330`. **Money rendering has a
boundary and nothing else does.** So any render-time throw on any billing screen presents a
clerk with a JavaScript stack trace instead of A18 §4's failure state, **and takes the
navigation with it**. Two prior instances are already filed and neither names the cause:
`DEF-176` and `DEF-RBS-4352`.

**Not walked, and why:** every data-shape behaviour, the five wizard steps after step 1, every
write in the module (create, preview, approve, execute, abandon, enrol, override, relevel,
remove, build print set, issue, release) and the three swallowed-failure paths. *"Every flow
in this document is graded UNVERIFIED unless its row says SEEN."*

⚠ **This container has PostgreSQL and a seeded tenant, which that one did not.** Every screen
it could not open is reachable here. That is the largest single gap between what this document
knows and what a lane can now measure.

**One more §09 count, taken from §15's changelog rather than from §09 itself (p203):**
*"§09 cited no commitment on any journey failure — **seventeen findings, six of them
blocking**, and not one said who would close it. All ten walked screens now cite theirs; the
six stack traces close on `BIL-S9`, the missing error boundary that is the one source fact
behind them."* **So §09 carries 17 findings of which 6 block**, against the 10 walk rows in the
table above — the two are different granularities and must not be conflated.

---

## 5 · §10 — the absence register

Built from the product's **own user-facing copy**, never from an auditor's impression. Every
row gets exactly one ruling.

| | |
|---|---|
| **Absence keys** | **78** — 61 reachable from 14 source files |
| **Holding a dead control** | **14** — visible and unusable |
| **Rotting holds** | **7** — proven against current code |
| **Dead copy** | **2** — unreachable in 11 catalogues |
| **Self-healed** | **9** — derived from a 404, not hardcoded |

**Contrast the document states itself:** the wireframes in `05-prototype/` state **zero**
absences; the product's own copy states **78**, fourteen of them holding a control a clerk can
see and cannot use.

**The seven rotting holds** — a refusal with a clock in it, correct when written and silently
false the day the thing it points at lands:

| | Hold | Why it is no longer true | Control held? |
|---|---|---|---|
| R1 | *"Who started a run, and what it came to in money, are not kept against the run — so neither can be shown here."* | `run_by = ForeignKey("identity.User")` is declared, populated and on the wire. **The money half is still true.** Half-rotten — and the half that landed is denied inside a rule citation, which is the form a lane is most likely to believe. | No — a panel |
| R2 | *"Usage is summed from meter reads, and that summary is not built — no number is drawn from nothing."* | `GET /accounts/{id}/usage` is mounted; its docstring says the figure is Σ over `meter_reads`. That is precisely the summary the copy says is not built. | No — a panel |
| R3 | *"The run does not gather base charges or schedule names."* | `gather.py:699–705` gathers base charges through a three-way precedence ladder. The true, narrower statement sits in the adjacent comment; the user-facing sentence generalised it into a false claim. | No — a cell |
| R4 | *"The saved copy exists but cannot be opened yet…"* | The page shipped **2026-08-16**; `App.tsx:932–935` routes it and `documents_api.py:454–456` serves it. | No — a panel |
| R5 | *"A billing run cannot be parked yet: nothing would list it."* | `PastRunsPanel` is defined and **mounted on step 1 of the same wizard**, fed by `GET /billing/runs`. **Parking is genuinely unbuilt** — so the control is right to refuse; **only its reason is false**, and it is the reason a clerk reads on six screens. | **YES — all 6 steps** |
| R6 | *"Bills cannot be downloaded yet. No export is built for this list."* | **The copy is still true** — `bills` is not in `EXPORT_RESOURCES`. What has rotted is its *evidence*: the source asserts in bold *"there is no `apps/billing/exports.py` at all"*, and that file now exists. **Flag for re-measurement, not deletion.** | **YES — the glyph** |
| R7 | *"…or the endpoint that reads a single bill has not been built yet — the two answer the same way."* | `invoices/<invoice_id>` is mounted at `api.py:2021`. The second disjunct is now false, so the sentence offers a clerk a possibility that cannot occur. | No |

**Two dead-copy keys** (`billing.arrives.run`, `billing.arrives.oneTime`) — strings in eleven
catalogues that can never render, because the router matches the real route before the
fallback. **Nine self-healed** — refusals gated on a live 404 probe, which *"became unreachable
the day its route landed, with no wording left standing and nothing to edit."*

> **The lesson the section draws, and it is the transferable one:** *"derive the absence from
> the response, never from a hardcoded sentence. Where the module did that, nine holds expired
> silently and correctly. Where it hardcoded a sentence, five are still lying."*

⚠ **Two method false-negatives the document caught on its own second pass, recorded because
the next person will hit them:** a literal-key grep **under-reported by sixteen** keys built as
template literals; and the dead-copy list was **entirely wrong the first time** — seven keys
have zero front-end call sites and are still rendered, because the **backend** ships them as
`message_key`. *"A register built from front-end greps alone mislabels all seven."*

---

## 6 · §11 — rule compliance

**One row per violation, never per screen.** Counted from the images: **17 rows** across
pages 159–162.

| Rule | Rows | Screens |
|---|---|---|
| **B14 31** (no database id is ever the visible value of a field) | **2** | 12 Budget Bills (raw `accounts.id`), 13 Fix a bill (raw `invoices.id`) |
| **Hard rule 2** (money 4dp stored, 2dp displayed) | **4** | 13 Fix a bill ×2, 12 Budget Bills ×2 |
| **B14 39** (label → input → helper) | **1** | 11 One-time bill — *inherited from the shared staff kit, all five field variants across 28 files, `DEF-SHL-4921`* |
| **B14 16** (pagination on every list table) | **3** | 12 Budget Bills, 13 Fix a bill, 14 Pending queue |
| **B14 32 / 4 / 12** | **4** | 13 Fix a bill (32), 05 step 2 · 07 step 4 (32), 02 Bill detail (4), 12 Budget Bills (12) |
| **Unassessable** — the rule names a class the shipped app does not declare | **1** | 04 step 1 · 11 One-time (B14 7 cites `.date-input`; the product uses `DatePickerField`) |
| **R14 flag** — struck, **NO VIOLATION** | **1** | 01 All bills (`_apply_order` applies `nulls_first=True` on descending, deliberately) |
| **Hard-won law 2's mirror** — a hold with no test that fires when it expires | **1** | 10 Past billing runs |
| **Total** | **17** | |

⚠ **Appendix G (p214) says "Seventeen rows" and then enumerates a breakdown that adds to
16.** Its summary omits the hard-won-law-2's-mirror row, which is not a B14 or hard-rule-2
category. **The row count of 17 is right; the breakdown line is short by one.**

⚠ **The column that matters is ENFORCED?, and it is the section's whole argument.** Eleven of
the seventeen read `RATIFIED ONLY` — *"in a repository where most UI rules are ratified and
unenforced, a green suite is evidence of nothing."* The others read `NOTHING CHECKS THIS`,
`NO GATE READS COMPUTED SPACING`, `A CLASS NOTHING DECLARES RENDERS AS NOTHING`,
`NOTHING ASKS WHETHER A REFUSAL IS STILL TRUE`, `THE RULE NAMES THE WRONG STYLE WORLD` and
`NO VIOLATION`. **Not one of the seventeen would have been caught by a machine.**

**Four rules the section states these screens are EXEMPT from, said out loud so nobody re-files
them:** B14 16 inside a wizard (steps 4 and 5) · **B14 21 (Tailwind): no violation anywhere in
billing** — all fifteen `.tsx` files are on `route-b-migrated.txt` and both billing stylesheets
are deleted, *"the `DEF-974` trap does not apply here"* · B14 15 (row actions) satisfied ·
B14 19 (placeholder) satisfied, and better than the prototype.

---

## 7 · §12 — the build index. **This is what step 2 is scoped from.**

### 7.1 · The nine that cost the most, in order — captured exactly

Ordered by **what their absence costs a person**, not by list order, effort or filed severity.
*"A field whose absence makes a clerk decide wrongly outranks ten cosmetic ones."*

| | Commitment | State | What a person cannot do today |
|---|---|---|---|
| 1 | `BIL-S90` | New build | A utility above 25,000 accounts **cannot run a cycle at all**. Not a slow run — no run. **The ICP moved to 40,000 on 2026-09-06 and the constant did not move with it.** |
| 2 | `BIL-S56` | **Blocked** | A leaving customer's deposit is not settled, so the final bill is wrong **in the direction nobody re-reads**. $153.50 applies before any path is chosen. |
| 3 | `BIL-S91` | New build | A clerk approves rows that show **no amount**. The decision looks made; the money was never computed. |
| 4 | `BIL-S92` | New build | An account whose meter simply was not read is **refused from the run**, so it never bills and nothing says so. |
| 5 | `BIL-S93` | New build | Every bill this product prints reaches a customer as **Courier with space-aligned columns**. It is the only artefact the customer ever sees. (`DEF-BIL-4524`, corroborated on p217: *"the page is Courier with space-aligned columns, which is what the drawing above shows, because that is what it is. **The drawing is not a placeholder.**"*) |
| 6 | `BIL-S9` | New build | Any render-time throw shows a clerk a **JavaScript stack trace and takes the navigation with it**. One boundary exists in the whole front end, and it is inside `MoneyCell`. |
| 7 | `BIL-S1` | **Exists behind** | Past billing runs shows a grey panel over a read that serves **twelve fields**. A clerk cannot answer *what did we bill last month, and who signed it off*. |
| 8 | `BIL-S61` | **Blocked** | An operator picks a correction reason and the system cannot say what it will do, because the reason table is not built. |
| 9 | `BIL-S102` | New build | Every utility inherits the same **$25 late-fee floor, written into the code**. A tenant cannot set its own, and nobody had ratified the number until 2026-09-13. |

⚠ **Number 1 is not a billing defect in the ordinary sense** — the document says so itself. It
is a constant that silently excludes the top of the market this product was re-scoped to serve.
**It is the item most directly connected to `CLAUDE.md`'s own ICP paragraph**, and its
companion figures are in the build-component table: `MAX_ACCOUNTS_PER_RUN_DEFAULT = 25_000`
and `MAX_BILLS_PER_PRINT_SET_DEFAULT = 25_000` against a 40,000 ICP (`DEF-BIL-4224`).

⚠ **Number 9's figure is the open question in §3 above.** Building `BIL-S102` without
answering *which balance the floor tests* builds a setting whose meaning is undecided.

### 7.2 · Every build component, and who undertook it

*"A build component is anything buildable, not just a screen."* **Two classes are the
finding: five of the thirteen guarantees are enforced by nothing at all, and 15 of the 27
rulings exist in no file.**

| Component class | Count | What is true of it | Undertaken by |
|---|---|---|---|
| Screens | **77** | every one carries a derived chip; 6 further anchors are layers of screen 17 or an evidence table | `BIL-S1` … all 101 |
| Drawings | **91** | **70 REDESIGN · 9 AS-BUILT measured · 12 AS-BUILT from code** — each says so in its own caption | — a caption is a statement, not work |
| Billing tabs | **7** | the six in the path plus Print bills, added by the 2026-09-12 ruling | `BIL-S70` Exists behind |
| Bill-detail tabs | **5** | Document · Charges · Corrections · Audit · **Sent**, the last one new | `BIL-S19` New read |
| Pickers | **194 from 23 sources** | every source named once in §01; **three of them do not exist yet** | `BIL-S31` New build |
| Table controls | search · filter · columns · pager, per list | **the pager is the one that breaches a standing NFR** | `BIL-S81` New build · `BIL-S13` Exists behind |
| Write surfaces | **12 named writes** | **none was exercised** — there was no backend | `BIL-S98` New build |
| Endpoints | **36 across 8 url modules** | the count is the masthead's; this document names 37 method+path strings, *"which is not the same measurement and is not a finding"* | — |
| Seams | **11 files, plus one *no seam* row** | `seam_batch` exists and the prepare pass does not use it | `BIL-S46` New read · `BIL-S96` New build |
| **Guarantees** | **13** | **5 of the 13 are enforced by nothing** — the last reads *"NOTHING, and it is why §10 exists"* | `BIL-S9` · `BIL-S12` · `BIL-S80` · `BIL-S81` · `BIL-S10` |
| Catalogue strings | **15,424 keys × 11 locales** | 2 can never render; **1 mistranslates *billing cycle* as *bicycle*** | `BIL-S88` · `BIL-S79` New build |
| Empty states & refusals | **7 rotted holds · 14 dead controls** | a refusal is true when written and rots silently; nothing checks | `BIL-S12` New build |
| Tests | **2 named as missing** | the hold-expiry test, and a seeded draft bill so four refusal states can be rendered at all | `BIL-S12` · `BIL-S98` New build |
| **Hardcoded caps** | **2** | `MAX_ACCOUNTS_PER_RUN_DEFAULT = 25_000` and `MAX_BILLS_PER_PRINT_SET_DEFAULT = 25_000` **against a 40,000 ICP** | `BIL-S90` New build |
| Stale comments | 2 measured | `late_fee.py:369` says `assess_late_fee` has *no production caller* — it has exactly one. `DEF-3153` is recorded FIXED and is half fixed | — corrected there; no product work |
| Migration-list entries | **15 of 15** | checked, and the document was right: all 15 non-test billing `.tsx` files are on `route-b-migrated.txt` | — nothing to do |
| **Rulings** | **27** | **15 exist nowhere but here** — an accepted risk with a ruling behind it, not an open gap | ruled 2026-09-13 · OUT OF SCOPE |
| Open defects relied on | **51 cited, 45 open** | 9 had no commitment until this pass | `BIL-S90` … `BIL-S98` |

⚠ **`BIL-S1 … all 101` against §14's "Of the 100 here".** One of the two is off by one; both
are the document's own figures, one page apart. **Neither is safe to quote as a count of
commitments** — count the register.

### 7.3 · The build index proper — every screen, its commitments, strongest state

Generated from the register in document order; **strongest state = the WORST state across the
commitments naming that screen**, so a row that says *build this* also says whether anything is
in the way. Section totals, read off the group headers:

| Section | Screens |
|---|---|
| §02 · The screens | 7 (01, 02, 02.1–02.5) |
| §03 · The bulk bill run | **31** (16, 17.0, 17, 17.1–17.22, 18, 19, 20, 20.1–20.3) |
| §04 · Single bills | 9 (21, 22.1–22.6, 23, 24) |
| §05 · Budget bills | 5 (25, 25.1–25.4) |
| §06 · Fix a bill | 9 (26, 26.1–26.8) |
| §07 · Past billing runs | 1 (27) |
| §08 · Bill printing | 2 (28, 28.1) |
| §17 · The rest, as built | 13 (03, 04–09, 10, 11, 12, 13, 14, 15) |
| **Total** | **77** ✔ matches the Screens component row |

⚠ **§12 says of itself that it used to be wrong, and names the failure.** *"It said the
drawings to build had moved into §02 and listed nine screens — 01 · 02.1–02.5 · 10 · 13 · 14.
That was written before §03–§08 existed. It named three screens that are now as-built evidence
in §17 and omitted every screen from 16 to 28.1 — about sixty drawings, including all of §04
to §08."* **The contents rail's ◆ marks (`10 ◆ · 13 ◆ · 14 ◆`) are from that same superseded
reading** — see §9 below, where §17 says outright that screen 14's redraw is now §03's screen
20 and *"Build 20, not this."*

---

## 8 · §13 · Cross-module, §14 · Specification register, §15 · What this pass changed

### §13 · Cross-module (p168–172)

Four questions, run once from above *"because these are the failures that belong to nobody"*.
**Both modules are named in every row** — a finding filed against one is a finding the other
module's owner never reads. Built from the ⇄ rows in §02's field tables, not from the import
graph.

**All four totals re-counted from the rows on p169–p171 by this lane, and all four hold.**

| Question | Claimed | **Counted here** |
|---|---|---|
| 1 · Does the handoff land? | 9 | **9** ✔ (notifications ×3, metering, rating ×2, customers, ledger, payments·ledger) |
| 2 · Does any module write another's tables? | 0 | **0** ✔ — *"I looked for the real test — an import that reaches a manager and calls `.create()`, `.update()` or `.delete()` — across all six cross-boundary imports, and found none."* |
| 3 · Does one fact have two homes? | 5 | **5** ✔ (who ran a run · a bill's name and address · a bill's status vs its run's · the late-fee floor · `BR-BIL-030` itself) |
| 4 · Does the same thing have two names? | 4 | **4** ✔ (what a customer owes · held here/in the books · mark for later · billing cycle) |

⚠ **Question 2's zero is not a clean bill, and the row says so.** `DEF-2845` is open and
partially fixed: it records *"seven imports in five files"*; this read counts **six `from
apps.*` imports across five files** and says *"the difference from seven is probably an import
form my pattern missed, and I would rather say so than round."* All six are reads or platform
services and one is the **sanctioned** shape (`register_export_resource` from `AppConfig.ready`
at `exports.py:236`) — *"a boundary bypassed, not a boundary violated."*

⚠ **Two rows in questions 3 and 4 are money findings worth carrying:** the **late-fee floor
exists as two constants** — billing's own and collections' — `DEF-205` open, *"two separate
copies of one ruled number… the classic second-copy-free-to-drift, on a money figure"*
(`BIL-S77`), which is the same figure ruling 26 and the open question in §3 are about; and
**`billing cycle` is translated as *bicycle* in Japanese and French** (`DEF-BIL-4759`, high,
open) — *"a Japanese bill line reads 'bicycle charge'. This is a bill a real customer reads."*

**Seam health, counted:** **ten seam files + one *no seam* row**, **94 named functions, and not
one returns a raw queryset** — no `return …objects.`, no `-> QuerySet`, no `return qs` in any of
them. Ten graded HEALTHY; `seam_batch.py` (8 functions) is the exception — it **exists, and
`DEF-2704` says the prepare pass does not use it per-account**, which is the 66,053-SQL-statement
finding.

**Eight rows carried `No commitment` until this pass** — *"not one of their defect ids was
named by any commitment card, which is what happens to a fault belonging to two modules and
therefore to neither."* All eight are undertaken now, by `BIL-S71`–`BIL-S79`.

**Named as the single highest-value thing a next pass should pick up (p172):** *"Five
documented seams still SUBSTITUTE a fact over tables that now exist."* That is §10's
rotting-hold shape one layer down, at the seam layer, and proving it needs reading five seam
implementations against five schemas — **more than this pass did**.

### §14 · Specification register (p172–202)

**One row per commitment, no exceptions.** *"If a thing is not here, nobody has undertaken to
build it — everything else in this document is description."*

**Re-counted by this lane rather than quoted** — the cards carry a `STATUS` line each, so they
can be counted without opening 29 pages: **100 `STATUS` lines, 100 `DONE LOOKS LIKE` lines, and
the chip beside each STATUS splits exactly as the document claims.**

| | Document's figure band | **Counted here** |
|---|---|---|
| Commitments | 100 | **100** ✔ |
| `Exists behind` — *behind a screen that does not ask for them* | 50 | **50** ✔ |
| `New build` | 38 | **38** ✔ |
| `New read` | 6 | **6** ✔ |
| `Blocked` | 6 | **6** ✔ |
| Minted across the three audit passes | 32 | not independently counted |
| **Withdrawn by a ruling** | 2 | not independently counted (`BIL-S101` is one — withdrawn by ruling 25) |

50 + 38 + 6 + 6 = 100 ✔, both as claimed and as counted.

⚠ **The id range sentence is stale.** The red band says *"These are `BIL-S1` … `BIL-S30`,
minted for this document"*, and the register itself runs to **`BIL-S102`**. Read the range
from the rows, not from the sentence.

⚠ **These ids are NOT repository ids and nothing is reserved.** *"They are not allocated into
the repository's live series… borrowing from any of them would make this look scheduled when it
is not."* The live series are `US-BIL-###`, `OQ-…`, `DEF-…`, `CR-###-BRC##`. **A `BIL-Snn` is
a pointer into a PDF, not a ticket.**

### §15 · What this pass changed (p202–206)

A changelog of the analysis, not the product. **3,058 words of running log, reduced to a
table.** The rows worth carrying:

* **The first reading:** four corrections to the author's own instrument, kept rather than
  tidied — a route glob that matched the app's own API modules, a stub envelope one level too
  deep, a dead-copy list that **mislabelled all seven** keys, and a literal-key grep that
  **under-reported by sixteen**. *"Each would have produced a confident report of something
  untrue."*
* **§03:** six steps became four. *"The obstacle was that money does not exist until step 4,
  so the decision step showed nulls and a clerk decided blind — and the fix was already built
  and uncalled since 11 August."*
* **§05–§08:** an alignment defect **the PO found that no check here could see** — a CSS rule
  naming only `td` left **143 of 143 numeric headings** left-aligned over right-aligned values,
  in every wireframe since screen 01.
* **The tag audit:** the four state chips were applied to **fifteen places out of eighty-five**;
  the distribution is the finding — **48 of 70 already exist behind a screen that does not ask
  for them**.
* **The duplication pass:** §14's index repeated **3,158 words** of the cards beneath it
  verbatim (67 of 70 waits-on texts byte-identical), and **§12 listed nine screens and omitted
  sixty**.
* Two of the corrections are corrections to the **repository's own registers** — *"a question
  recorded CLOSED whose body still describes the open world, and a business-rule sentence that
  went stale and was quoted onward"*. **Neither is filed**, for ruling 25's reason.

### ⚠ The two repository corrections, checked against the repo by this lane

They are the only findings in §09–§17 that are about OUR registers rather than about the
product, and they are the most directly actionable thing here. **p203 states them as:** *"Out
of scope rested on things that are not rulings. Re-tested against the repository, not against
this document's memory of it. **Two were wrong.** *A bill cannot be cancelled* cited `OQ-012`
as open — it is **CLOSED**, ruled into `BR-BIL-009`, which says build it. *Budget-billing
eligibility* repeated *"nothing publishes the flag"*, which that question's own row records as
stale for five days. **Two were right for the wrong reason**, and one — hand-editing a charge
line — has no ruling anywhere and is now a specification that waits on one."*

**Verified here, both:**

| Claim | Checked | Verdict |
|---|---|---|
| `OQ-012` is CLOSED, not open | `01-open-questions.md:131` — `**CLOSED(→BR-PAY-011,BR-BIL-009)** — as proposed + consequence messaging (PO R6)` | ✔ **The document is right.** `BR-BIL-009` is CONFIRMED at `02-business-rules.md:16`. This is `CLAUDE.md`'s own named trap — *a closed question's body describing the open world* — and here it reached a screen's out-of-scope verdict. |
| `OQ-237`'s *"nothing publishes the flag"* is stale | `01-open-questions.md:336` | ✔ **The document is right, and the row already carries the correction** — stamped 2026-08-21, `DEF-469`, *"⚠ HALF OF THIS ROW WENT STALE AND NOBODY NOTICED FOR FIVE DAYS"*. `budget_billing` is served at `apps/rating/selectors.py:445`. The row is still **OPEN — non-blocking** for the narrower half only. |

**Neither correction is filed anywhere**, because ruling 25 forbade this pass from writing to
the repository. **Filing them is repository hygiene, not a PO question** — but it is not this
lane's to do either, because step 1 files defects and this is a register body, not a defect.
**Named here so the coordinator can route it.**

---

## 9 · §17 — the rest of the screens, as built (p215–249)

**Thirteen screens, audited in full, moved here on 2026-09-12 at the PO's direction.**
*"Nothing was cut — every drawing, legend, spec table, data flow and field table is exactly as
it was, and every anchor still resolves."*

### ⛔ 9.1 · NOT ONE OF THE THIRTEEN CARRIES A DRAWING TO BUILD. **Three sources say otherwise and all three are stale.**

This is the largest correction this lane found, and it lands directly on how step 2 is scoped.

**What the three stale sources say:** the contents rail marks **`10 ◆ · 13 ◆ · 14 ◆`** in §17;
the lane brief repeats it; and **§17's own summary table on p215** says `10 Past billing runs ·
CARRIES A DRAWING`, `13 Fix a bill · CARRIES A DRAWING`, and marks only 14 `SUPERSEDED`.

**What the entries themselves say, read as images and confirmed across every §17 entry:**

| § 17 entry | Its own stamp, verbatim | Page |
|---|---|---|
| 03 Bill document | `No redraw.` *"This is the current state and there is nothing to build from it."* | 215 |
| 04 Run bills step 1 | `REDRAWN AS` §03 screen 16 *Scope*. **Build that one.** | 217 |
| 05 step 2 | `REDRAWN AS` §03 screen 17 *Check* — *"Three of the six steps collapse into this"* | 220 |
| 06 step 3 | `REDRAWN AS` §03 screen 17 *Check* — same collapse | 222 |
| 07 step 4 | `REDRAWN AS` §03 screen 17 *Check* — same collapse | 224 |
| 08 step 5 | `REDRAWN AS` §03 screen 18 *Sign off*. **Build that one.** | 226 |
| 09 step 6 | `REDRAWN AS` §03 screen 19 *Send*. **Build that one.** | 227 |
| **10 Past billing runs** | **`REDRAWN AS §07 screen 27 — Past billing runs. Build that one.`** and its drawing is stamped **`SUPERSEDED — This proposal is replaced by §07 screen 27. Kept as the earlier reading, not as work.`** | 229 |
| 11 One-time bill | `REDRAWN AS` §04's one-time wizard. **Build that one.** | 232 |
| 12 Budget Bills | `REDRAWN AS` §05's budget bills. **Build that one.** | 234 |
| **13 Fix a bill** | **`REDRAWN AS §06 screens 26–26.8 — the fix-a-bill wizard. Build that one.`** and its drawing is stamped **`SUPERSEDED — replaced by §06 screens 26–26.8`** | 236, 237 |
| **14 Pending queue** | **`REDRAWN AS §03 screens 20–20.3 — the held queue, at this same route. Build that one.`** · `SUPERSEDED` | 240, 241 |
| 15 Print bills | `REDRAWN AS` §08's bill printing. **Build that one.** | 244 |

⚠ **Precision of the destination column, stated so nobody over-trusts it.** Entries **03, 04,
10, 13 and 14** were opened as images and their destinations read off the page (04 reads
literally `REDRAWN AS §03 screen 16 Scope. Build that one.`). For **05–09, 11, 12 and 15** the
stamp's PRESENCE and its *"Build that one"* are proved from the text layer, but **the
destination NUMBER is dropped by extraction on this PDF** and was reconstructed from §12's
build index. **The stamps are certain; the eight reconstructed numbers are an inference to
re-check against the image before any of them is cited in a ticket.**

**§15 records exactly why, and it is the document correcting itself on p203:**

> ⚠ **Three screens were told to build twice, differently.** *"Screens **10, 13 and 14** each
> carried a BUILD THIS band **and** a REDRAWN AS stamp pointing somewhere else — **two drawings
> to build for one screen, which is exactly the confusion the PO warned about when the redraws
> moved.** The bands read `SUPERSEDED` now, naming the destination, and the drawings stay as the
> earlier reading rather than as work."*
>
> ⚠ **Seven as-built screens said "No redraw" and were redrawn.** *"My own stamp pass covered
> only screens 10–15, so **04, 05, 06, 07, 08, 09 and 14** all read *No redraw. There is nothing
> to build from it.* §03 replaces every one of them — six run steps into four screens. All seven
> now name their destination."*

**So the ◆ marks on 10, 13 and 14 are the residue of the superseded reading**, and the p215
summary table was never updated to match the entries beneath it. **A lane scoping step 2 off
the rail, off the brief, or off §17's own summary table would build three screens the document
explicitly tells it not to build.** The work for all three is in §03, §06 and §07.

**Where the eleven `BUILD THIS` drawings actually are, per §12's own reconciliation:** 01,
02.1, 02.2, 02.3 (two states), 02.4 (two states), 02.5, 10, 13, 14 is the OLD nine-screen list
that §12 itself says *"was written before §03–§08 existed… named three screens that are now
as-built evidence in §17 and omitted every screen from 16 to 28.1 — about sixty drawings."*
**The current build index is §12's generated table (§7.3 above), not that list.**

### 9.2 · Why each of the thirteen sits at the back

| What is here | Why it is at the back rather than in §02 |
|---|---|
| **03 Bill document** | A reading screen with no redraw in this pass. The bill detail's Document tab (02.1) is where a clerk actually goes. |
| **04–09 the six as-built run steps** | **These are the evidence §03 is measured against.** The *six steps become four* table and its element arithmetic both count against these six drawings. |
| **10 Past billing runs** | The panel saying the list arrives later is **false in both halves that matter**. At the back because it is not part of the run journey. **Its redraw is §07 screen 27.** |
| **11 One-time bill · 12 Budget Bills** | Billing outside the cycle. Untouched by the bulk-run redraw. |
| **13 Fix a bill** | Reached from a bill, never from a run. **Its redraw is §06 screens 26–26.8.** |
| **14 Pending queue** | **Its redraw is §03 screens 20–20.3, *Held queue*** — the one with the missing handle, the date picker and the filters. |
| **15 Print bills** | The best-behaved screen in the module. Its one weakness is the door. |

**Screen 03's caption, read as an image (p215):** `New build BIL-S9 · BIL-S79 · BIL-S93`,
`Exists behind BIL-S29`. Address `/:tenant/billing/bills/:invoiceId/document · BIL-05.document
· no A1 id`. Its as-built drawing was **composed from source and never rendered**, because the
screen threw on load — `(reading 'startsWith')` at `tenantPathFrom`.

**Screen 15 Print bills, the one positive verdict in the section (p246):** *"The best-behaved
screen in the module, and worth saying so in an audit that has mostly found the opposite: four
distinct refusals instead of one generic one, a fifth state for 'succeeded but produced no
file', an estimate derived from a measured constant with the measurement named, a manifest
deliberately not re-sorted, and an explicit twice-stated declaration that it writes nothing.
**Its one weakness is the door:** the channel that every bill depends on is reachable from
exactly one button on one screen, and no reachability test covers it."*

---

## 9A · Appendices I, J, K — read, and K matters for the ruling count

**Appendix I · every field and where its data comes from (p246–247).** **71 fields traced
across 15 screens** — `SERVED` 46 · `NOT SERVED` 16 (*the screen wants it; no read exists*) ·
`STUBBED` 5 (*fixed value regardless of input*) · `HARDCODED · DERIVED` 4 · **`NEVER TRACED` 0**
(*"an ungraded field is not a healthy one"*). 46 + 16 + 5 + 4 = 71 ✔.

**Appendix J · health, and what the grade rests on (p248–249).** *"A screen's health is the
worst of its fields, never an average. An average turns one broken field among nine into '90%
healthy', and the screen still does not work."*

* **J1 Fields** — the same 71, split 46 / 16 / 5 / 1 DEAD / 2 HARDCODED / 1 DERIVED / 0 NEVER
  TRACED. The single `DEAD` is `bill_runs.status` on screen 04, *"written once as `draft`,
  never advanced"*.
* **J2 Flows, one row per screen** — **4 SEEN · 11 UNVERIFIED or partly so.** *"No flow is
  graded WHOLE on a read alone without the word UNVERIFIED beside it."* Screen 14 Pending queue
  is graded `WHOLE and unbounded — correct at T7, 13,000 accounts short of T5`.
* **J3 Seams** — **10 HEALTHY** (94 functions, none returning a raw queryset) · **1 LEAKY by
  rule** (six imports in five files bypassing a seam, reads only, one the sanctioned
  registration shape) · **0 WRITING · 0 ABSENT**. `DEF-079`'s five substituting seams are
  **ungraded, named rather than guessed at**.

**Appendix K · everything an upgrade would drop, and who ruled it (p249).** **One row, and it
carries a quoted ruling** — the bill detail's embedded document viewer is removed, PO
2026-09-11. That is **ruling #1 of the 27 already counted**, so **K adds no ruling this lane
had not already transcribed.** Everything else across nine remedies carries over: eleven
elements move tab or group, four are relabelled, nothing else goes. **`Rows with no quoted
ruling: 0`** — *"that is the number this table exists to keep at zero, and a long K would mean
a document quietly proposing to shrink the product."*

**So the count of 27 is now a count of the whole document's ruling surface**, not just §16's
table: K was the only other appendix that quotes rulings, and its one row is already inside
the 27.

---

## 10 · Coverage — what this lane did and did not read, stated as counts

**Pages opened as images: 39 of the 99 in §09–§17** — p151–p172 (all 22), p179, p202, p203,
p206–p215 (all 10), p217, p229, p236, p240, p246, p248, p249.

**Pages NOT opened as images, and exactly what a reader loses by trusting this file over them:**

| Pages | What is there | What is therefore unverified |
|---|---|---|
| 173–178 | §14's index table rows (the 100-row index above the cards) | Nothing material — the **cards** were counted programmatically (100 STATUS lines, split 50/38/6/6) and that is the authoritative half. The index is the duplicated half §15 says was cut. |
| 180–201 | §14's remaining commitment cards | **Each card's *waits on* and *done looks like* text is unread.** The states are counted; the CONTENT of 94 of the 100 cards is not. **Step 2 must read the card for any `BIL-Snn` it scopes** — the chip says what the work waits on, the card says what done looks like. |
| 204–205 | the rest of §15's chip-audit table | Some of the three contradictions the chip audit found in the author's own work. p203 (the largest page of it) **was** read. |
| 216–228, 230–235, 237–239, 241–245, 247 | §17's per-screen drawings, spec tables, data flows and field tables | **The per-screen detail of the thirteen as-built screens is unread.** Their `REDRAWN AS` stamps were all confirmed (§9.1) and four entries were read in full (03, 10, 13, 14); the other nine were confirmed only at the stamp. |

**What was verified by counting rather than quoted, and this is the part to trust:**

| Claim | Source of my count |
|---|---|
| 27 rulings, 15 NOWHERE | rows counted on the p206–p208 images; every one grepped |
| 12 of 12 repo homes resolve | each cited id opened in its own file |
| 17 rule violations in §11 | rows counted on the p159–p162 images |
| 100 commitments · 50 / 38 / 6 / 6 | STATUS lines counted programmatically over §14's extracted text |
| 77 screens in the build index | section headers summed on the p165–p167 images |
| 9 · 0 · 5 · 4 cross-module findings | rows counted on the p169–p171 images |
| 13 §17 screens, **0 carrying a drawing to build** | every `REDRAWN AS` / `No redraw` stamp located and each of 10, 13, 14 opened as an image |

**What this file is not:** a specification, a diff, or evidence that any screen matches any
drawing. **No screen was walked in a browser for this lane and no product code was read**,
other than the eight register and rule files the ruling check required. Every judgment about
the PRODUCT in this file is the document's, re-stated; every count is mine.

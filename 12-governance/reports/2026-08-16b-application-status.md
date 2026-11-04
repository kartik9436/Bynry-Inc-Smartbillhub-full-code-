# Whole-application status — 2026-08-16, second measure

Re-measured after the second wave of build lanes. **Three lanes were still
running when this was taken**, so the figures move again after it. Every table
names the command that produced it.

Compare against `2026-08-16-application-status.md`, taken this morning.

---

## 1 · The whole application

| | This morning | **Now** |
|---|---|---|
| User stories | 258 | **258** |
| Stories with code | 190 (73%) | **199 (77%)** |
| Stories **built** — endpoint *and* screen | 141 (55%) | **159 (62%)** |
| Stories **proved** — a test or browser check runs them | 71 (28%) | **77 (30%)** |
| Stories with code **no human can reach** | 18 | **9** |
| Screens routed in the app | 61 | **65** |

`python3 10-scripts/module_report.py` · `10-scripts/gates/surface_debt.txt`

## 2 · Health

| Check | This morning | **Now** |
|---|---|---|
| Merge-blocking gates | 27 of 27 | **26 of 27** — the one failure is a live lane's file |
| Golden money tests (frozen finance figures) | 33 / 33 | **33 / 33** |
| Backend suite | 2,938 pass · 12 fail | **3,031 pass · 3 fail** |
| Frontend suite | 1,189 pass · 2 fail | **1,250 pass** |
| Open **critical** defects | 2 | **2** |
| Open defects, all severities | 42 of 167 | **45 of 180** |
| Questions awaiting the PO | 34 of 220 | **39 of 228** |

**Defects and questions both went UP, and that is the system working.** Thirteen
new defects were filed today by the lanes and by the PO's own questions — each
one is a fault that existed already and is now written down. A register that
only ever shrinks is a register nobody is filing into.

## 3 · Release by release

> The release column is inferred: the engineering plan (§209–212) defines R1–R4
> by *capability*, not by module, and three modules span releases. Story counts
> are exact; the attribution is a reading.

### R1 — "Set up your utility" · deployed and in use

| Module | Stories | Built | Proved | Unreachable |
|---|---|---|---|---|
| platform-shell | 19 | 14 | 4 | — |
| tenancy | 21 | 12 | 5 | — |
| identity | 11 | 4 | 2 | — |
| audit | 9 | **4** | 1 | — |
| rating | 19 | 11 | 3 | 4 |
| metering | 20 | **17** | 10 | — |
| assets | 12 | **10** | 5 | — |
| **R1** | **111** | **72** | **30** | **4** |

### R2 — "Bill"

| Module | Stories | Built | Proved | Unreachable |
|---|---|---|---|---|
| customers | 23 | 14 | 12 | — |
| billing | 31 | **25** | **14** | **0** |
| **R2** | **54** | **39** | **26** | **0** |

**Billing's unreachable count reached ZERO today** — the one-time bill tab gave
the last five finished engines their first door.

⚠ **But a utility still cannot bill from the screen.** The "Start this run"
button issues no request at all. See §4.

### R3 — "Collect & close the books"

| Module | Stories | Built | Proved | Unreachable |
|---|---|---|---|---|
| payments | 25 | **18** | 7 | 1 |
| ledger | 21 | **17** | **11** | 2 |
| reports | 19 | **7** | 0 | 1 |
| **R3** | **65** | **42** | **18** | **4** |

**Reports moved 1 → 7 built.** It was the largest hole in the product this
morning; the catalogue, viewer and four computed reports landed.

### R4 — "Switch on the world" · not started, by ruling

| Module | Stories | Built | Proved | Unreachable |
|---|---|---|---|---|
| notifications | 16 | 6 | 3 | 2 |
| integrations | 12 | 0 | 0 | — |
| **R4** | **28** | **6** | **3** | **2** |

## 4 · The nine unreachable stories are really two

| Counted | What | Build work? |
|---|---|---|
| notifications 2 | The dispatcher · the provider seam | **No — out of R2 by PO ruling.** *"I already confirm it before it Queue them."* Counted because they have code and no route, which is the only question the register answers |
| rating 4 | The pricing engine — usage, TOU, %-of-water, capacity | **No — a counting decision.** All four are built and reachable through the rate wizard and the bill run. They have no screen *of their own* and never will; the engine is a pure service |
| ledger 2 + payments 1 | Posting contracts · reversal pairs | **Yes — and it is ONE story counted twice**, because a payments seam cites it too |

**So: two genuine stories, counted three times. Two blocked by a ruling. Four are
a definition question.** Inside those two sits real work: **13 of 17 signed money
events post to the books and four do not** — the cutover batch, the first-bill
deposit line, the deposit application and the deposit interest. A utility takes a
**$150.00 deposit** and that money is in the customer's record and **nowhere in
its books**. The trial balance still foots, because the entry was never made on
either side.

## 5 · The two critical defects

**Both were found by the PO asking a question. Neither was found by any check.**

| | State |
|---|---|
| **A plan with trash cannot bill.** Sewer was fixed today — 93 lines, $2,979.68 at the frozen figure. Trash still reaches no bill: **$18.00/month, $1,728.00 across the demo** | **Open** — needs one ruling, not code |
| **The "Start this run" button is wired to nothing.** Enabled, issues no request, no error, no message. The endpoint behind it returns **201 Created** when called directly | **Open** — being fixed |

**Fixed today, and it belongs here because it was a regression we caused:** the
whole Finance screen crashed on the seeded tenant. This morning's fix for a tile
printing `null USD` made the money renderer refuse an absent amount — correct in
itself, and it turned every unguarded caller into an outage. **Now verified
rendering in a browser**, along with its GL, tax and export tabs.

## 6 · Two numbers to read carefully

**"Built 62%" is not "62% of the product exists."** It means both halves of a
story — endpoint and screen — are marked done. The engine work is far ahead:
**125,000+ lines** of tested backend against **77** screens. That gap IS R2's
original lesson.

**"Proved 30%" is the number to distrust least.** It counts what a test or a
browser check actually executes. It is low, and it is honest — and today it
proved its worth twice, because two faults that every other number said were fine
were found by loading a page.

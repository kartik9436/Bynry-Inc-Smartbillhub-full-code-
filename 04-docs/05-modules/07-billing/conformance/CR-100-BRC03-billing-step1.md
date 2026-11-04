# `CR-100-BRC03` · Billing, step 1 — the consolidated record

**One record a stranger can act on.** The evidence sits in seven files; this is the thing
that adds them up, and it is the file step 2 is scoped from.

| | |
|---|---|
| Module | **billing** · 7 route patterns · **15 screens a clerk can reach** |
| Drawing | `05-prototype/04 Billing, As Built.pdf` — **249 pages**, on the DEFAULT branch, **not on ours** |
| Branch | `claude/eager-johnson-r0k88b` · block `CR-100`–`CR-104`, suffix `BRC03` |
| Prior coverage | **NONE.** `07-billing/conformance/` did not exist. A genuine first pass |
| Status | **STEP 1 COMPLETE.** Nothing built. No `.tsx` or `.py` changed except two comment blocks a PO ruling ordered |

## ⛔ The framing — the briefing was inverted, and this is the finding everything else rests on

The briefing said: *"'AS BUILT' is in the title… a difference is DRIFT, not a build item."*
**Measured from the pages, the opposite is true.**

| Evidence | Where |
|---|---|
| **`DRAWINGS 91 — 70 redesign · 21 as-built`** | cover figure band, p1 |
| *"There is one drawing per screen and it is the one to build… Their current state is kept directly underneath, **collapsed and marked do not build this**"* | p2, in red |
| **§02: 8 drawings, ALL redesign.** §03–§08: **57 entries, 57 redesign, ZERO as-built** | measured page by page |
| 74 pages carry `REDESIGN` · 71 `NEVER BUILT` · 68 both · `AS BUILT` in caps: **1** | whole document |

**So Billing has almost nothing to have drifted FROM. The work is the redesign, not gap-closing.**
Reading it the briefing's way would have hunted drift that is not there and missed the build list.

⚠ **AND FIVE AS-BUILT FRAMES CANNOT BE READ AT ALL.** Every `As built today` block is a
**collapsed disclosure and the PDF renders it closed**, so the frames §09–§11 argue their
findings from **are not in the file**. **No §02 drift claim can be sourced from this document.**

## THE TWO-WAY DIFF — the deliverable, both directions, counted

| | §02 (7 entries) | §03–§08 (57 entries) | **TOTAL** |
|---|---|---|---|
| Drawn elements compared | 166 | 227 | **393** |
| — matching | 80 | 22 | **102** |
| — present, with a difference | 36 | 42 | **78** |
| — **drawn and NOT on the screen** | 49 | 158 | **207** |
| — could not judge | 1 | 4 | **5** |
| **On the screen and NOT drawn** | 23 | 31 | **54** |
| → **build** | 81 | 200 | **281** |
| → **defect** | 4 elements | 3 | **7** |
| → **question** | **0** | **0** | **0** |

**Entries with a comparable surface: 17 of 57 in §03–§08** — 39 have nothing to compare
against at all, which is what "mostly redesign" means in practice.

⚠ **ZERO QUESTIONS FROM THE DIFF**, and that is a real finding rather than an empty column:
**no drawing anywhere shows an edit on an issued bill.** Five drawings state hard rule 4
themselves — *"An issued bill takes no update and no delete… which is also why the
prototype's edit specific line items control cannot be ported."* **The money rule is honoured
by the design rather than fought.**

## THE WALK — what the blueprint could not do, and we could

> Its own cover: *"**Partial, front end only.** No backend — Django is not installed in this
> environment and there is no PostgreSQL… **So no real row ever reached a screen, and every
> data-shape behaviour went unwalked.**"* · **4 of 15 screens seen · 6 threw**

| | Blueprint | This pass |
|---|---|---|
| Screens opened | 4 of 15 | **15 of 15** |
| Address × width | 1440 only | **40 of 40** (20 × 1280 and 1440) |
| Screens that threw | **6** | **0** |
| Screens with real data | **0** | **8** |
| Could not judge | — | **7**, each named |

**Seeded to make the walk mean anything:** `invoices` 0 → **92** · `invoice_lines` 0 → **732**
· `bill_runs` 0 → **3** · `accounts` 0 → **72**. ⚠ **An empty table is not a table that
matched**; the seven unjudged screens are named with their reasons rather than called passes.

⚠ **TWO NEAR-MISSES WORTH MORE THAN THE RESULT.** The SPA had no `API_PROXY_TARGET`, so every
data call returned **502** while the page served **200** — *a walk started in that state would
have reported fifteen broken screens and every finding would have been false.* And the first
row counts read **0 everywhere** because the query ran without `app.tenant_id`: **RLS `FORCE`
returns zero rows rather than erroring.**

**The money path ties out exactly**, verified line by line against the database on
`BL-2608-000058`: every tier multiplication, subtotal **736.28**, tax `736.28 × 0.02 =
14.7256 → 14.73`, total **751.01** = `sum(invoice_lines)`. Units explicit, money to 2
decimals, *Cancel this bill* permanently disabled, service address derived by walking to
premises.

## WHAT THE REPOSITORY CLAIMED, AND WHETHER IT WAS TRUE

| | |
|---|---|
| Claims re-checked | **18** |
| **Already false** | **9 — half** |
| Confirmed true | 6 · stale-not-false 1 · unverifiable 2 |
| Endpoints claimed → measured | 36 across 8 → **41 across 9**, all **41 served** |
| Endpoints with **no caller** | **3** + 1 dead duplicate over a live route |
| Routes claimed / mounted | **7 / 7** |
| **Golden — document** | **33 checks PASS**, imports no application code |
| **Golden — ENGINE-VERIFIED** | **14 of 61** signed GTs |

⚠ **47 OF 61 SIGNED BILLING FIGURES HAVE NO TEST THAT RUNS THE ENGINE.** That is the honest
coverage number for the money path, and **`33/33` must never be quoted as engine proof.**

## THE RULINGS — 27 found, 15 rescued, 2 collide

The document declared itself the system of record by a PO ruling of 2026-09-13, and stated
its own cost: **15 of 27 rulings in no file, ungreppable.** **Both figures were CHECKED, not
quoted** — 27 of 27 found, **0 of 15** present anywhere in the tree, 12 of 12 with a claimed
home resolving. **PO ruled 2026-09-14: transcribe all 15.** Done, verbatim, 4 also into
`02-business-rules.md` as `BR-BIL-1034`–`1037`.

⚠ **TWO OF THE FIFTEEN COLLIDE WITH A SIGNED RULE AND ARE MARKED NOT BUILDABLE. BOTH ARE
MONEY, BOTH ARE OPEN, NEITHER WAS DECIDED.**

| | The collision | The money |
|---|---|---|
| **`"per conenction"`** 2026-09-11 | Reverses the PO's own ruling of **2026-08-31** (`CR-056`, `OQ-334`): *"one standing charge for the address."* ⚠ **The earlier ruling sits INSIDE a row whose status column reads `OPEN`** — the row's own text says *"a question answered in two rows gets two answers"* | **$64.00 per connection vs $52.00 pooled — $12.00/month on one building** |
| **`"as per connection"`** 2026-09-11 | Contradicts **`BR-RAT-062`** (CONFIRMED): *"tax is a BILL-level concept, never per-service… Fees are likewise bill-level"*, resting on ❄️ frozen **`B5 GT-17`** and B4's tax section | `$69.60 + $0.57 = $70.17` — the blueprint's own worked figure. ⚠ **`GT-17` is among the 47 with NO engine test** |

**Collision 2 is a formal STOP** under the change process: a frozen figure moves only by
finance re-sign.

## THE FOUR OTHER PO RULINGS OF 2026-09-14, AND WHAT THEY COST

| Ruling | Effect, measured |
|---|---|
| **The late-fee floor tests the AGEING PORTION** | ⚠ **Costs nothing to honour** — `late_fee.py:612` already computes `ageable_portion` before testing the floor at `:561`. The ruling **ratifies working code** a docstring had flagged unratified. `$25` floor untouched and still a module constant with no tenant setting (`BIL-S102`) |
| **`CLAUDE.md` hard rule 4's citation** | Fixed: **55 occurrences on 51 lines across 31 files** changed; **41 on 31 lines in 14 files deliberately LEFT**, each decided on its own sentence's subject. Four live surfaces that already cited `OQ-1340` and complained `CLAUDE.md` was wrong were moved to past tense |
| **The 25,000 cap STAYS** | ⚠ **THE PO SUPPLIED THE FACT AND IT REFUTED THE RECOMMENDATION.** *"utilities will devide them into nilling cycles"* — a run is scoped to a CYCLE, so a 40,000-account utility billing four cycles of 10,000 never approaches it. **`BIL-S90`, the document's TOP-COST ITEM, is wrong in both halves and should be re-ranked OUT of the top nine, not built.** Real cost: change one setting. Only the comment changed |
| **Finish step 1 first** | This record |

## DEFECTS — 13 Billing, plus 2 found in other modules while measuring

`DEF-BIL-5225` · `5226` · `5227` · `5228` · `5230` · `5231` · `5232` · `5233` · `5234` ·
`5235` · `5236` · `5237` · `5240` — and `DEF-GOV-5229`, `DEF-MET-5238`.

**The five that matter most:**

1. ⚠ **`DEF-MET-5238` — A TENANT CAN STILL SWITCH OFF A MONEY-PATH CHECK THE PO LOCKED.** The
   PO closed `OQ-1330` on **2026-09-03** (*"if we switch off reading unit check then we will
   have problem with data"*). **That ruling reached the decision log and nothing else:** the
   register row still reads `OPEN — non-blocking`, and `RULE_UNIT_MISMATCH` sits in the
   **switchable** list, not in `INTEGRITY_RULES`' locked seven. **Nothing went red because it
   fails safe at bill time**, which is exactly why nobody saw it. Found only because a lane
   had to read that row's status to carry out a different ruling.
2. **`DEF-BIL-5233`** — all **thirteen correction reasons** reach a clerk as raw `snake_case`
   enum codes **in every language**, on the control that decides whether a credit note
   issues. **Zero `billing.fix.reason.*` keys exist in any of the eleven catalogues** —
   counted. The server is right; the words do not exist.
3. **`DEF-BIL-5230`** — *Past billing runs* shows *"It arrives with the billing run work"*
   over **3 served runs**, with the same rows drawn one tab away. ⚠ **Every test asserting
   that copy passes BECAUSE the refusal is still there.**
4. **`DEF-BIL-5226`** — the hold-expiry test written to fire the day its route landed watches
   one hand-named file; the function landed in another. **It passes green over an expired
   hold**, and its failure message begins *"THAT IS GOOD NEWS."*
5. **`DEF-BIL-5234`** — `GET /billing/pending` takes no paging and re-sorts in Python: **a
   fifth `NFR-3` surface**, and the first outside payments.

## WHAT WAS NOT MEASURED — stated plainly

* **5 elements unjudged in the diff** and **7 screens in the walk**, each named with its
  reason — mostly states needing a run DRIVEN, which is a write and out of step 1's scope.
* **The five collapsed as-built frames** — not in the PDF. A property of the file.
* **60 of the 99 pages in §09–§17**, including §14's card BODIES. ⚠ **Step 2 must open the
  card for any `BIL-Snn` it scopes.**
* **`DEF-BIL-5097`'s twenty reds were not re-run.**
* Destination screen numbers for **8 of 13 `REDRAWN AS` stamps** were reconstructed from
  §12's build index, not read — extraction drops digits. **The stamps themselves are certain.**

## ⚠ WHAT STEP 2 MUST NOT INHERIT

1. **Not one of §17's thirteen screens carries a drawing to build.** Every entry stamps
   `REDRAWN AS … Build that one`. **Three sources say otherwise and all three are stale** —
   the contents rail's diamonds, **§17's own summary table on p215**, and this pass's lane
   briefs. §15 (p203) records why: those three each carried a band AND a stamp, *"exactly the
   confusion the PO warned about."* **Scoping off any of them builds three screens the
   document says not to build.**
2. **The document's build arithmetic does not reconcile.** p6 names **eleven** drawings to
   build, all in §02. The `BUILD THIS` band occurs on **14 pages** — 11 in §02, **2 in §03**
   (`16 Scope` p46, `17 Check` p51), 1 in an appendix. **Both numbers are 11 and only one is
   true of the pages**, which is how it survived a pass that was checking arithmetic.
3. **`BIL-S90` is not the top-cost item.** See the rulings table.
4. **Extraction is useless here, proved:** `/:tenant/billing · S30 · BIL-01` extracts as
   `tenantbilling … S  BIL` — every slash, colon and digit dropped. A map grepped from the
   text returns **zero** rows.
5. **`openapi/schema.json` is stale by 6,538 diff lines** of other lanes' work, and the
   CI-diff clause says any drift fails the build.
6. **`allocate.py` has no `BR-` family**, and mis-reports two others by counting ids where
   they are WRITTEN ABOUT rather than USED (`DEF-GOV-5224`).

## Coverage of this pass

**249 of 249 pages rendered.** Section maps for all of §02–§17. **Every screen walked at both
staff widths.** ⚠ **The document is drawn at 1440 ONLY, on purpose** — so **1280 findings are
PRODUCT findings, never drift from a drawing that does not exist.**

**Seven records, 4,295 lines**, all on the branch:
`blueprint/00-index.md` · `01-screens-in-journey-order.md` · `02-runs-single-budget-fix.md` ·
`03-rulings-and-registers.md` · `conformance/CR-100-BRC03-walk.md` · `-repo-claims.md` ·
`-diff-02.md` · `-diff-03-08.md`.

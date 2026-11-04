# J46 — An answer authored, published, read under a bill, voted on (`1,204` → `1,207`, a *No* that is its own event, and a tip slot that closes up)

---
id: J46
tier: 2
rules: [BR-CWP-093, BR-CWP-094, BR-CWP-095, BR-CWP-044, BR-CWP-007]
stories: [US-CWP-071, US-CWP-072, US-CWP-073]
# Wiring: every story above cites `J46` in its own `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J46.spec.ts`. Release 1.
# ⚠ `US-CWP-071` is BLOCKED on OQ-1398 (who keeps the answers current, in how
# many languages). The store, the three statuses, the variants with a VISIBLE
# needs-translating state, and the immediate publish are built; a translation
# workflow is NOT promised and this journey does not assert one.
---

**Intent.** The whole point of the smallest write in the portal: without it the back
office's *read this month* column is a column of zeroes and the utility cannot tell which
answer is doing the work. A clerk writes an answer, sets **also show on: the bill screen**
(one field, two placements — the utility writes it **once**), publishes — **immediately,
there is no approval step, and the screen says so** — and the same answer appears in the
public list, the signed-in list and **under the charges on the customer's bill**. Three
opens move the count `1,204` → `1,207`; a *No* lands as **its own event**. The second half
is the tip: one slot, on **and** in season, top of the list wins, and **when none is live
the slot is not in the DOM at all**.

**Upstream leaves (handoff in).** Tenant `pine-hill` live. The eight `help_answer` rows of
J33 (six published, one draft, one not shown), answer 1 *Why is my bill higher than last
month?* at position 1 with `1,204` reads this month, `also_show_on_screen` **NULL** at the
start. Six `tip` rows: *A running toilet can use 4,000 gallons a month.* — Usage looks
high, all year, ON · *Read the dials left to right, and ignore the red ones.* — Send a
reading, all year, ON · *Ask for a plan before the due date and late fees stop.* —
Overdue, all year, ON · *Watering before 10am loses less to evaporation.* — Usage,
**Jun–Sep**, ON · *Leave a tap dripping overnight when it freezes.* — Portal home,
**Dec–Feb**, **OFF** · *Your meter is yours to read any time — it is not locked.* — Every
reading, all year, ON. Maria Alvarez enrolled, bill `BL-2608-0141`. Clock **2 Sep 2026**.

**This journey leaves (handoff out).** Answer 1 with `also_show_on_screen = the bill
screen` and its `fr-FR` variant still `needs_translating`; `help_answer_feedback`: three
`read` rows and one `not_helpful` row (the same four J33 leaves — the two journeys describe
one write from two ends); a seventh tip (30 words, flagged); tip positions re-ordered.
Every back-office change audited. **No money table touched.**

**Fixture.** Staff screens `CWP-071` (list, drag to reorder) and `CWP-072` (editor) in the
**staff app** under *Settings → Configure → Customer portal → Help & answers*, System Admin
Sarah Miller; `CWP-073` Tips. Portal: `CWP-011` (public list), `CWP-059` (signed-in list),
`CWP-060` (one answer), `CWP-061` (the bill with the `AttachedAnswerCard`), `CWP-022`
(home, tip slot), `CWP-033`/`CWP-062` (usage, tip slot).

| # | Actor · action | Expected outcome (contract) | Downstream assertions (query · feedback rows · DOM · audit) | Rule |
|---|---|---|---|---|
| 1 | Sarah opens `CWP-071` | Eight rows with a leading **drag handle** ⋮⋮, Question / Topic chip / Status (`PUBLISHED` × 6 · `DRAFT` · `NOT SHOWN`) / Languages (*11 langs · 11 · 2 · English · 11 · 11 · 2 · English*) / **Read this month** (`1,204 · 842 · 790 · — · 611 · 508 · 410 · —`). Footer *Showing 1–8 of 8 · The order here is the order on the portal*. `InfoBar` *A missing translation is better than a missing answer.* | The `—` on the draft and the not-shown is an **absence**, not `0`. A Billing Clerk may edit content only if the tenant's own permission model says so — assert the gate matches it rather than inventing one | `US-CWP-071` TC-1/11 · B14 rule 31 |
| 2 | Opens answer 1 in `CWP-072`; sets **Also show on → the bill screen**; presses **Publish** | The rail `Panel.Warning` says **publishing is immediate — there is no approval step**. The **LANGUAGES** `MiniTable`: *English PUBLISHED · Español (México) PUBLISHED · Français **NEEDS TRANSLATING** · हिंदी PUBLISHED* … — so the utility can **see** what its French-speaking customers are not being shown | `help_answer.also_show_on_screen` written; one audit row. **Within the minute** the answer appears on `CWP-011`, `CWP-059` and **under the charges on `CWP-061`** — the utility wrote it **once** | BR-CWP-094 · `US-CWP-071` TC-4/7/9 |
| 3 | Maria opens `BL-2608-0141` (`CWP-028` → now `CWP-061`) | The `AttachedAnswerCard` sits **directly under the charges panel**: bold *Why is my bill higher than last month?* + `→`, grey two-line excerpt. Rail ⓘ *the answer is here because somebody put it here.* Every usage line still carries its unit | Opening it → `CWP-060`, and ONE `help_answer_feedback` `read` row. Two more opens (public and signed-in list) → **three** `read` rows total | BR-CWP-044 · `US-CWP-072` TC-6 |
| 4 | Back in `CWP-071` | Answer 1's read column reads **`1,207`** | Then Maria presses **No** on `CWP-060` → ONE `not_helpful` row; the read column **stays `1,207`** — a read and a vote are **two distinct events**. Assert four rows, two kinds | `US-CWP-071` TC-8 · `US-CWP-072` TC-4 |
| 5 | Sarah **drags row 3 to the top** | `position` rewritten; `CWP-011` and `CWP-059` show *How do I check for a leak?* first on the next load | Audit row for the reorder. The gate stays in the **query** (`status = published`) — reordering never surfaces the draft or the not-shown | BR-CWP-094 · `US-CWP-071` TC-5 |
| 6 | **the tip slot · Usage in September** — Maria opens `CWP-033` | `TipBar` under the page head: brand **TIP** · *Watering before 10am loses less to evaporation.* · `×`. **Exactly one** tip — `Jun–Sep`, ON, today 2 Sep. Dismiss → closes for that viewer and the page reflows | Clock fixture **1 Oct 2026** → the tip is **gone with no edit** — a seasonal tip appears and disappears on its own. `GET tips?screen=usage` returns one row in September and **an empty response in October, and an empty response is a normal response** | BR-CWP-095 · `US-CWP-073` TC-2 |
| 7 | **negative · the slot that is not there** — Maria opens `CWP-022` (home) | The only tip aimed at the home page is **OFF and Dec–Feb** — not showing **for two independent reasons** — and the home page has **no tip container in the DOM at all**. Not a placeholder, not an older tip, not an empty frame | Assert on the DOM: no `TipBar` element. Turning the tip ON in September still shows nothing (out of season); ON in December shows it | BR-CWP-095 · BR-CWP-093 · `US-CWP-073` TC-3 |
| 8 | **negative · two tips, one screen** — Sarah adds a second all-year ON tip targeting Usage, below the watering tip; then drags it above | With the watering tip on top: **one** renders — the watering tip. After the drag: **one** renders — the new one. Assert **exactly one** `TipBar` each time | *Top of the list wins where two match* is the tie-break and it follows the drag order. A tip of **thirty words** is accepted but **flagged in the editor** against the fifteen-word guidance — the rule is on the screen, not in a policy document | BR-CWP-095 · `US-CWP-073` TC-4/7/9 |
| 9 | **negative · no page of tips** | Maria tries `/pine-hill/portal/tips` and any browse route | **No such page and no such route** — a tip the customer went looking for would be an answer | `CWP-073`'s `TwoEqual` panels **A TIP IS NOT AN ANSWER** and **SEASONAL TIPS** state the rule on the back-office screen | BR-CWP-095 |
| 10 | **negative · nothing empty** — on the `oak-ridge` twin, unpublish every answer | `CWP-011`, its header link, `CWP-059`, `CWP-054`'s *might answer it now* panel and the `AttachedAnswerCard` slot under every bill are **all absent**. The customer is never told a count of what is hidden | The back office still lists the rows; the portal shows nothing and says nothing about it | BR-CWP-093 · BR-CWP-094 |
| 11 | **tenant isolation** | Sarah's Oak Ridge counterpart sees Oak Ridge's answers and tips only; an Oak Ridge session on the portal gets Oak Ridge's tips; Pine Hill's `1,207` is unmoved by Oak Ridge reads | RLS `FORCE` on `help_answer`, `help_answer_variant`, `help_answer_feedback`, `tip` | hard rule 1 · `US-CWP-071` TC-10 · `US-CWP-073` TC-8 |
| 12 | **INVARIANCE** | The French reader still got **English, not a blank**, on every surface, and nothing promised them a translation. No money table changed. Every back-office write has an audit row. The two hidden answers never left the back office; the read count moved only on opens, the vote count only on votes | Publishing changed what customers read **immediately** and the screen said so beforehand | BR-CWP-094 · `OQ-1398` |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | A translation being produced, reviewed or scheduled | `OQ-1398` — who keeps the answers current and in how many languages. **An ongoing job, not a build.** The visible `needs_translating` state is the boundary |
| b | The read count's **reset** at month end | Not specified by any story; *read this month* is asserted as a running figure within the month only — a lane should not invent the reset rule |

## Walked, in a browser — added 2026-09-04 by the CR-068 wave D build lane

`10-scripts/render-checks/cr068-d-help-tips-centres.mjs`, steps 1–5 and 8.

⚠ **STEP 4 ASSERTS THE MOVEMENT, NOT THE FIGURE, AND THE REASON IS WORTH
KEEPING.** *Read this month* is a real `COUNT(*)` over `help_answer_feedback`,
so every run of the walkthrough adds three reads: a hard `1,204 → 1,207` would
pass once and then read as a broken screen for ever after. The script records
the count immediately before the three opens and asserts `+3`, and separately
that pressing *No* moved that column by **nothing** — which is the claim the
story actually makes. `1,204` is the figure on a fresh seed and the script says
so on screen.

The walkthrough also puts the fixture back at the end of step 8 (every answer
republished, every centre re-shown), because the first version that did not
made its own second run fail on an empty portal.

# CR-085 lane 5 · STEP 2, WHAT CHANGED — bills and documents

**Six screens** — `/bills` · `/bills/:number` · `/bills/:number/comparison` ·
`/bills/:number/dispute` · `/bills/:number/document` · `/documents`. Written against
`CR-085-lane5-01-drawing.md` (the quoted blueprint), `-02-deltas.md` (the measured
differences) and `-03-registers.md` (the defects and the twelve unratified rules).

**Read `§5 WHAT I COULD NOT DO` before assuming a finding was fixed.** Three of this
lane's seven defects are NOT closed here and two of them are blocked by a file boundary
rather than by difficulty; one did not reproduce against the running server and is
recorded as hardening rather than as a fix.

---

## 1 · THE RULING, AND THE ONE PLACE IT COLLIDES WITH SIGNED LAW

**PO, 2026-09-11: the 8 September blueprint PDF is the design; the 3 September wireframe
images are superseded.** That settles every drawing-versus-drawing disagreement in
`-01-drawing.md` §8 mechanically. Applied:

| screen | was | now |
|---|---|---|
| `CWP-027` table | nine columns | **four** — `BILL · COVERS · AMOUNT · STATUS`, plus the row's two icons |
| `CWP-027` column heading | `PERIOD` | **`COVERS`** |
| `CWP-031` table | six columns | **four** — `DOCUMENT · KIND · SENT · HOW`, plus the row's two icons |
| `CWP-031` title | `Documents and letters` | **`Your documents`** |
| `CWP-031` sub-line | none | **`{{count}} documents`** |

### ⚠ `BR-CWP-043` AND THE FOUR COLUMNS CANNOT BOTH BE OBEYED, AND THIS IS NOT A LANE'S TO SETTLE

`BR-CWP-043` is **signed law** in `02-business-rules.md`:

> **Owing is a separate column from amount.** A $142.18 bill with $40.00 paid against it
> is neither a paid bill nor an unpaid one.  — CONFIRMED, blueprint `P13`

**Its own citation is the winning document.** `P13` and section 05 (pages 55–64) are the
same PDF, and section 05 draws four columns with no `OWING` among them. So the ruling does
not overturn the rule — **the ruling's own document contradicts itself**, and CLAUDE.md law
13 says the supersession of a signed rule must be stated and never assumed.

**What was built, and what it costs.** The four drawn columns, with the rule's SUBSTANCE
kept inside them: the `AMOUNT` cell carries a second line — *"$102.18 still owing"* — **only
where what is owed differs from what was charged**, which is exactly the part-paid case the
rule is written about. `part_paid` keeps its own chip and its own tone. So **no customer
loses a figure**; what is lost is the rule's letter, the separate column.
`Bills.dom.test.tsx` pins both halves, and the same line is drawn on the phone card so the
two renderings cannot disagree about one bill.

**This needs a ruling to close.** Either `BR-CWP-043` is amended to *"owing is shown
wherever it differs from the amount"*, or the bills table gets a fifth column and the
blueprint's section 05 is stamped as drawn without that rule in view. **Both are one
sentence to the PO and neither is ours.**

---

## 2 · THE SEVEN DEFECTS

| row | what it was | state |
|---|---|---|
| `DEF-CWP-4859` | `CWP-028`'s failed and loading branches threw the whole page head away | **already fixed** by lane 1's frame commit `01cfb545a` (`PortalScreen`); this lane added the R-10 ways out the card still had none of |
| `DEF-CWP-4860` | `CWP-031` printed *"Came back to us on ."* on every row — a bounce claim with an empty date | **fixed, and half of it did not reproduce** — see §3 |
| `DEF-CWP-4861` | `portal.bills.payHeld` in all eleven catalogues with no consumer | **fixed** — retired through `i18n_fanin.retire`, with five more the four-column ruling orphaned in the same commit |
| `DEF-CWP-4862` | `CWP-030`'s no-comparison branch drew the heading twice | **fixed** — the card carries the sentence and nothing else |
| `DEF-CWP-4863` | the dispute form's three helpers are not bound to their inputs | **NOT FIXED — blocked, §5** |
| `DEF-CWP-4864` | at 390 `/bills` is cards, the table is `display:none`, and the printed-bill door went with it | **fixed** — both row doors on the card, as WORDS |
| `DEF-CWP-4865` | the printed bill renders 165 × 213 px at 390 | **NOT FIXED — blocked, §5. Mitigated**: a phone-only *Open it full screen* pointing at the same `?view=1` stream |

---

## 3 · `DEF-CWP-4860` — SAID PLAINLY, BECAUSE HALF OF IT WAS MINE

The row read *"Came back to us on ."* — a statement that the post office returned the
customer's bill, with the date blank. **Two faults, and they are not equally true.**

**(a) The guard.** `filter((route) => route.returned_on !== null)` over a field typed
`string | null`. A key **absent** from the payload arrives as `undefined`, and
`undefined !== null` is true. `tsc` cannot see it because the type says the key is there.
⚠ **The live server always sends the key** — `notifications/correspondence_reads.py` writes
`row.returned_at.date().isoformat() if row.returned_at else None` — so **this reproduced
against a fixture and not against the running stack.** Step 1's walk stubbed the portal
endpoints (it had to: `portal_credential` holds 0 rows on the shared stack), and the stub
omitted the key. It is fixed as hardening. **Recorded rather than quietly deleted**, because
a finding that did not reproduce is worth more written down than erased.

**(b) The date was raw, and that one IS live.** `{ date: route.returned_on }` — an ISO
string in the middle of an English sentence, on a screen whose `SENT` column has gone
through the tenant's own formatter since `DEF-CWP-3994`. One file, two formats for one kind
of fact. It goes through `asDate` now.

---

## 4 · THE TWO RULES THAT ARE LAW

**R-10** — *"when a screen tells a customer something bad, the thing they can do about it
must be on that same screen, next to the message."* Every failed branch on the five screens
that have one now carries its ways out **inside the state card**, not in the head — a head
link would satisfy a looser reading and is a page's furniture rather than an answer to the
message. `Try again` is a real control on all five: it bumps an `attempt` counter in the
effect's dependency array and re-runs the read that failed. A way out wired to nothing is
`DEF-MET-4764`, and a required-prop-satisfied-by-`waysOut={[]}` would have been the same
defect with a type behind it.

| screen | ways out on the failed branch |
|---|---|
| `CWP-027` | `Try again` · `Get help →` (`/help`) — the drawing asks for *Retry, plus the phone number*; we hold no number on this payload, so the door is the screen that carries the office and emergency numbers |
| `CWP-028` | `Try again` · `Your bills` |
| `CWP-029` | `Try again` · `See the whole bill →` |
| `CWP-030` | `Try again` · `See the whole bill →` |
| `CWP-031` | `Try again` · `Get help →` |

**R-22** — *"differntiate it using text message"*. Every loading, empty and failed branch on
`CWP-027`, `CWP-030` and `CWP-031` is now `PortalState`, so each carries
`data-portal-state` and a sentence of its own. They were hand-rolled `Card`s holding one
grey `<p>` each — one picture, and the reader had to read the sentence to know which had
happened. ⚠ **`/documents`'s *queue unreachable* branch is marked `failed`, not `empty`,
although nothing is listed**: telling a customer of eleven months that we never wrote to
them is the exact fault that branch exists to prevent.

**Rule 32's budget, applied to two live refusals.** `portal.documents.queueUnavailable` was
33 words over three sentences and is now one. `portal.documents.none` was two sentences and
is now one. Both in all eleven catalogues.

**Lane 8's door.** `portal.bills.seeWholeBill` = *"See the whole bill →"* is the one
catalogue key for that destination and it has three call sites in this lane: the phone card
on `/bills`, the new door row on `/bills/:number/comparison`, and the failed states of
`CWP-029` and `CWP-030`. **Lane 8's Usage screen should read the same key** — `CPB-08` joins
a usage month to the bill line that produced it, and a customer who meets two phrasings of
*open the bill* rings about it. Asserted by ADDRESS in
`BillComparison.dom.test.tsx`, never by label.

---

## 5 · WHAT I COULD NOT DO

### 5.1 `DEF-CWP-4863` — the dispute form's helpers · **blocked by the file boundary**

`FormField` renders the helper as a bare sibling `<p>` with no `id`, and `TextInput` /
`SelectInput` accept no `aria-describedby`. So the binding cannot be made from the screen:
**every possible fix is in `07-frontend/src/portal/components/primitives.tsx`**, which this
lane was told not to touch. It is four lines there — give the helper
`id={`${props.id}-help`}`, and pass `aria-describedby` down — and it fixes every portal form
at once rather than one. **Handed to the lane that owns the kit.**

### 5.2 `DEF-CWP-4865` — the printed bill at 390 · **blocked by the same boundary**

`DocumentPreview` hardcodes `className="aspect-[8.5/11] w-[62%] …"` inside a
`grid place-items-center border p-6` frame. 62 % of a 1,026px column is a readable 605px;
62 % of a 316px one is 166px. **The fix is one responsive class on that component** —
`w-full md:w-[62%]`, and a smaller frame padding below `md` — in `primitives.tsx`.
⚠ The component also carries three arbitrary Tailwind values the skill forbids by name
(`w-[62%]`, `aspect-[8.5/11]`, `bg-[white]`); whoever fixes the width should take those too.

**What this lane did instead**, inside its own screen: a phone-only *Open it full screen*
anchor to the same `?view=1` stream the frame embeds — the KEPT bytes, not a re-render
(`BR-CWP-045`) — so a customer on a phone can actually read the document. The thumbnail is
still there and is still 166px wide.

### 5.3 The things the drawing asks for that nothing serves

| drawn | why not built |
|---|---|
| `Bills are kept for seven years` · `6 documents · kept for seven years` | **the retention period is a per-deployment setting** (`audit.retention.law` interpolates `{{years}}`) and nothing serves it to the portal. Printing *seven years* would be a screen making a promise about how long a utility keeps its records — the same family as *Came back to us on .*, and a worse one because a customer would act on it. The COUNT is built; the retention half is `CPB-15` and stays open |
| `↓ Download all as a spreadsheet` (both screens) | no endpoint exists. A control that downloads nothing is hard-won law 2 |
| `Pay $191.00 now` | `GET /portal/bills` serves no `total_owing`; an amount here would be browser arithmetic on money. **Owed: a served total** (this lane's own step-1 finding, unchanged) |
| `Due Aug 22, 2026 · in 9 days` on `CWP-028` | `PortalBillDetail` carries no `due_in_days` — only `PortalBill` does. A countdown computed in the browser is the fault `DEF-CWP-3980` put on the server on purpose |
| `Paid Jul 19` in the status chip | `PortalBill` carries no `paid_on` |
| `🖨 Print` · `— page 1 of 1 —` · `Email a copy` · multi-page navigation on `CWP-029` | the blueprint marks that screen `NO COMMITMENT`; nothing undertakes to build them |
| `ASK FOR A LETTER` on `CWP-031` (`CPB-14`) | no screen, no endpoint. Still open |

### 5.4 `Rows per page 50 / 100 / 200 / 500 / 1000`

A staff-vocabulary control on a consumer screen that neither drawing has — the blueprint
pages at 12. It is `ListPager` inside the shared `portal/components/listTable.tsx`, used by
every portal list, so changing it is a portal-wide decision and not this lane's. **Named
here so the next lane does not assume it was covered.**

### 5.5 `portal.documents.downloadHeld`

A seventh orphaned catalogue key of `DEF-CWP-4861`'s family — no call site, but it is quoted
by name inside two `holds.ts` comments, so a grep-based key check could read those as call
sites. **Left alone deliberately**; it should be retired with the note that quotes it.

---

## 6 · HOW IT WAS PROVED

**Every guard was broken FIRST and the failure quoted, then made green.** Four reverts, one
per file, each running the suite against the old behaviour:

* `Documents.tsx` — **7 red**, including
  `expected [ 'Document', 'Kind', 'Sent', …(3) ] to have a length of 5 but got 6` and
  `expected <span …(2)></span> to be null` (the bounce claim).
* `Bills.tsx` — **4 red**: the phone doors, the owing line, the ways out, the state kinds.
* `BillComparison.tsx` — **3 red**, including
  `expected [ <h1></h1>, <p …(1)></p> ] to have a length of 1 but got 2` (`DEF-CWP-4862`).
* `BillDetail.tsx` + `PrintedBill.tsx` — **3 red**: both R-10 cards and the full-screen door.

⚠ **ONE OF MY OWN CHECKS WAS INCAPABLE OF FAILING AND THE RED PROOF IS WHAT FOUND IT.**
The first draft of `DEF-CWP-4862`'s assertion counted `container.querySelectorAll("h1, h2,
h3")`. **`SectionTitle` renders a `<p>`** — so it would have found one match over the defect
and one over the fix, passed both times, and told nobody. It counts leaf nodes now. That is
law 7's *"ask what would make this check pass wrongly"*, and it took breaking the code to
see it.

**Two test fixtures were mounted bare and are now mounted under the real path pattern** —
`BillComparison.dom.test.tsx`'s `draw` and `BillDetail.dom.test.tsx`'s failed-read case.
Both built every address as `//portal/…`, a protocol-relative URL to another host that reads
as a perfectly good string to `toContain`. Neither file asserted a door before today, which
is why nothing noticed; both now assert one by address.

**Baseline before any edit: 19 files, 228 cases, all green; `tsc --noEmit` exit 0.** No red
in this lane's suites was inherited.

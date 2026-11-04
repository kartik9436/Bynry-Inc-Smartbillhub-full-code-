# Entries 04 · 05 · 06 — the three dialogs that act on one reading

**Source:** *Meter Reads — an as-built blueprint*, **pages 16–21** (entry 04 on
p16–p18, entry 05 on p18–p20, entry 06 on p20–p21). Read as rendered PNGs at
scale 2 with `10-scripts/pdf/pdf_render.py` and **looked at** — B14 **rule 42**,
PO 2026-09-13: *"When you use images to create screens your accuracy is higher;
hence dont create screens using only Text"*. The text layer was used only as an
index and to cross-check spelling.

**State chips:** 04 `EXISTS BEHIND` · `NEW BUILD` · `BLOCKED` (`MR-24` · `MR-31`)
· 05 `EXISTS BEHIND` · `NEW BUILD` (`MR-31`) · 06 `EXISTS BEHIND` · `NEW BUILD`
(`MR-31`)
**Screen id:** `S29` — all three are dialogs on entry 03 and have no address of
their own.
**Built:** 2026-09-14, `07-frontend/src/features/metering/ReadDetailPage.tsx`
(`OverrideModal` · `DisputeModal` · `ClearDisputeModal`), tests in
`ReadActionDialogs.test.tsx`.

⚠ **THE VALUES ARE ILLUSTRATIONS; THE LABELS, THE ORDER AND THE PRESENCE OF EACH
ROW ARE THE SPECIFICATION** (B14 rule 37, and the standing caveat in
`09-screen-conformance.md`). `MTR-0452`, `1,014`, `8 kgal` and
`site visit 09/04` are drawn values and none of them is built to.

---

## What is drawn, and what is built

| | entry 04 · Correct the reading | entry 05 · Dispute | entry 06 · Clear the dispute |
|---|---|---|---|
| Kicker | `READING · MTR-0452` | same | same |
| Title | `Correct the reading for MTR-0452` | `Dispute the reading for MTR-0452` | `Clear the dispute on MTR-0452` |
| Body, in order | ① `Corrected register value *` + helper · ② `Reason *` + helper · ③ consequence line | ① warning rail `Under dispute: 8 kgal` · ② `What is the customer disputing? *` + helper · ③ consequence line | ① `Note (optional)` + helper · ② consequence line |
| Footer | `Cancel` · `Record the correction` | `Cancel` · `Record the dispute` | `Cancel` · `Clear it and let the account bill` |

**All of that is built as drawn**, including the consequence sitting LAST,
immediately above the footer — which is also B14 rule 11 (*a "what this will do"
box before its commit button*), so the drawing and the rule agree here.

---

## Divergences

### 1 · The kicker names the REGISTER as well as the meter — B14 rule 38

**Drawn:** `READING · MTR-0452`.
**Built:** the reading's own kicker, `Reading · <meter> · <register>` —
`metering.read.kicker`, the same string the page behind the dialog renders.

**Why this is not a liberty taken with the drawing.** B14 **rule 38** names
*"what the kicker says"* in its own list of things that are **FORM CONSTRUCTION
rather than layout**, and says of all of them: *"the drawing loses, the
divergence is RECORDED in the conformance file, and nothing is built for it."*
This row is that record.

**What it is worth.** Step-1 **Q7**, PO 2026-09-14: *"Put this first. DEF-797
already cost 412 kW billed as 14 kWh — $154 against $4,532. Money path, so I'm
not classifying it"*. A reading filed against the wrong register is **permanent**
— `supersede_read` takes a value and a reason and nothing else, and metering
migration `0007`'s trigger freezes the channel — and a dialog **covers** the page
that names the register, so while one is open its kicker is the only place the
register appears. It said `Reads`: the screen you came from, not the row you are
about to change for ever.

⚠ **IT MAKES THE REGISTER VISIBLE AND NOT CHANGEABLE.** The four shapes the
blueprint puts on the table for the wrong-register case — a correction that
carries a channel · a re-register supersede · saying it on screen · refusing at
the import door — are **all unchosen**, and the PO declined to classify the
question. Nothing was built for any of them.

### 2 · Three consequence lines exceed B14 rule 33's cap — FOR THE PO

**This is the one thing rule 41 routes to the PO** (*"the only exception to the
rule can be in case any rule or BR is not matching or contrdicting - in such case
you can ask us"*), so it is **built as drawn** and raised rather than rewritten.

Rule 33: a **CONSEQUENCE stated before an irreversible act** is ≤ **6 words per
sentence, at most two**, and **never cut below clarity**.

| entry | the drawn sentence | sentences × words |
|---|---|---|
| 04 | *"The new value becomes the current reading; this one stays in the history."* | 1 × 13 |
| 05 | *"The reading is not changed, and the account leaves the next bill run until a System Admin clears it."* | 1 × 19 |
| 06 | *"The account returns to the next bill run and will be billed on this reading as it stands."* | 1 × 18 |

**Why it was not simply cut.** The blueprint's own copy pass measured
**seventeen** helper lines and floor notes against rule 33 and applied every cut
— and it did not measure these three, so the drawing states them deliberately.
Each also carries a fact a clerk repeats to a customer, which is the *never cut
below clarity* clause. A worked alternative for 04 that would fit — *"The new
value becomes current. This reading stays in the history."* (5 + 6) — is offered
so the question can be answered with a concrete figure rather than in principle.

### 3 · Entry 06 renders one sentence the drawing does not show

`metering.read.dispute.clearOutcome` — *"Clearing records that the reading stands
and the bill was always correct; if the reading is wrong, use the billed
correction instead."* — is on the screen and is **not** in the drawing, whose
field table counts this dialog as **2 of 2** items.

**Kept, deliberately.** It states **BR-MET-133 clause 3** in the clerk's words
(PO 2026-08-26: *"she is wrong → clear the marker, the bill was always correct"*),
it was added to correct a sentence that had said the opposite, and a test pins its
content. The blueprint's copy table records every line it cut; this one is in
neither that table nor the field table, which makes its absence an **omission in
a document that is exhaustive over itself, not over the product** — not a cut.
**Deleting a screen sentence that states a signed rule is a copy decision for the
PO, not for a build lane**, so it stands and is raised with divergence 2.

---

## What was deliberately NOT built

* **No register picker, and no channel on the correction.** Entry 04's own
  finding: `supersede_read` accepts two fields and the database freezes the rest.
  A control here would be a promise the database refuses.
* **No rounding, no unit, no estimate is chosen anywhere.** B4/B5 are ❄️ FROZEN
  and move only by a finance re-sign (HUMAN-GUIDE §6).
* **No date field and no dropdown** — none of the three dialogs draws one, so
  B14 rules 7 and 8 do not bite here.

## What the build fixed on the way

**Hard rule 3, on the correct-the-reading dialog.** The value helper interpolated
`read.unit ?? ""`, so a reading whose unit never arrived rendered **`In .`** — an
empty gap where the unit belongs, on the dialog that rewrites the number a bill is
computed from. It is a dash now (`unitOrDash`), which invents no unit and states
that there is none.

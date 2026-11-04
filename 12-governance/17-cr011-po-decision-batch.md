# CR-011 — the three answers we could not record, put back properly

**Date assembled:** 2026-08-19 · **For:** Product Owner, one sitting ·
**Assembled by:** the CR-011 closure lane · **Version:** 2.20.0

---

## Why this file exists, and why it is an apology as much as a request

On 2026-08-18 you answered a ten-item list in one message. Seven of those ten
are now done and closed; the closure record is in `11-change-requests.md` under
CR-011.

**Three of them we cannot record, and the fault is ours, not yours.** The list
was put to you as *identifiers* — "OQ-256 variant axes", "OQ-262 three
trigger-less events", "4180 + 8 cost rows" — which is exactly the form your own
standing instruction of 2026-08-11 forbids:

> *"you give me all these codes; im human dont understand"*

You answered *"okay"* to each, and **"okay" against a question nobody expanded
selects nothing.** A signature covers only what was shown, so writing those
three down as rulings would put your name over content you were never shown.

One of the three — the finance re-sign — was re-presented properly later the
same day and **is now signed and closed**; it is listed below only so the record
is complete. **Two remain**, and they are the whole ask here. A third question
is added: a yes/no that CR-011 itself flagged as "must not be assumed", so it
is not assumed.

**Nothing in this file has been decided by the agent that wrote it.** Where a
recommendation is given it is labelled as one and you may reject it.

---

## Summary

| # | The decision, in one line | Stalls a lane? | Registry |
|---|---|---|---|
| **1** | When a utility prints a bill, is paper size a SETTING or a separate document to edit? | no — nothing is built either way | OQ-256 |
| **2** | Three switches on the Notifications screen turn on something that never happens. Which of three fixes? | no — the rows are honest today | OQ-262 |
| **3** | Does the contract wording we provide carry a visible "check this with your own lawyer" line on the page a customer signs? | no | CR-011 item 9 |
| — | *(closed — the finance re-sign, listed for completeness)* | — | — |

---

## 1 · Paper size: a setting, or a second document? (OQ-256)

**Where this comes from.** On 2026-08-16 you told us to standardise how a
document's variations are described, verbatim: *"take this as input and
standardize the sizes - user lnaguage ; those where for sample and example
only"*. We agreed the old list mixed three unrelated things together, and split
them into **size/format · language · content**. That split is settled. **What
was never settled is what the SIZES actually are, and that is this question.**

**What the product does today, measured rather than remembered.** Every printed
document comes out on **US Letter, 8.5 × 11 inches**, and no screen offers a
choice. The only sentence about paper anywhere in our signed documents is
*"single page, letter/A4"*. Nothing anywhere mentions Legal.

**The decision, in plain English:** a utility in Europe or Canada needs A4. When
they switch to A4, are they **changing a setting** — same words, different
paper — or **editing a second copy of every document**?

**Option A — paper size is a SETTING. *(recommended)***
One "Paper size: Letter / A4" choice in Settings. Every printed document uses
it. **The wording exists once.** A utility fixing a typo in their past-due
letter fixes it once.
· What it costs you: a utility cannot make the A4 version say something
different from the Letter version. We know of no reason they would want to.
· **The figure:** the catalogue holds **37 document types** today. Under A it
stays 37, plus one setting.

**Option B — each size is its own document to edit.**
A utility edits "Past-due letter (Letter)" and "Past-due letter (A4)"
separately.
· What it costs you: **20 printable documents become 40**, and every wording
change, every legal review and every typo fix has to be made twice. If a
utility also runs two languages, it is 80.
· What it buys you: nothing we can name.

**Option C — add Legal (8.5 × 14) as a third size.**
· We would be inventing it. No document, rule or prototype in this project has
ever mentioned Legal, so we cannot tell you what it is for. Say the word if
your utilities use it and it becomes a real option.

**Not paper sizes, and not affected either way:** the **door hanger** and the
**postcard** are already their own document types with their own wording,
because they say different things — not the same letter on different paper.

**One consequence to know before you choose, because it lands on a screen you
have already seen:** the Templates list has a **"Variants"** column showing a
number. Under Option A that number keeps meaning what it means now. Under
Option B, "4" could mean four different letters or one letter on two papers in
two languages, and a number that can mean either is a number nobody can act on.

---

## 2 · Three switches that turn on nothing (OQ-262)

**Where this comes from.** The Notifications screen you asked for draws
**fifteen** events a utility can switch on. **Three of them have nothing behind
them** — no code anywhere in this product will ever fire them:

| The switch, as it reads on screen | What is missing |
|---|---|
| **High-usage alert** — *"email + text when a customer uses more than 200% of their average"* | The only 200% we have flags a METER READ for a clerk to check. It has never sent a customer anything. |
| **Daily digest, 8:00 AM** | Nothing assembles a day's figures and nothing runs at 8:00 AM. |
| **Security alerts** | We record what people do; nothing decides that one of those things is worth alerting anyone about. |

Today all three are **drawn, switchable, and each row says on its face that
nothing will fire.** That was a lane's judgement, not your ruling, which is why
it is here.

**Why it matters:** a switch a utility can turn ON that never does anything is
worse than a missing switch — it is a promise. A utility that turns on
high-usage alerts and later finds a customer's bill tripled with no warning
sent will believe we lost their alert.

**Option A — take the three switches off the screen** until something can fire
them. Smallest, most honest screen. Cost: the screen no longer matches the
requirement list you approved, which named all fifteen.

**Option B — leave them as they are: drawn, switchable, each saying nothing
fires.** *(what is shipped)* Cost: it relies on a utility reading the small
print beside a switch they just turned on.

**Option C — build the high-usage alert for real**, reusing the 200% we already
have. **This is a product decision with a customer on the other end of it:** it
means telling a customer their usage has doubled *before anyone has checked the
meter reading* — and a stuck or misread meter is the commonest cause of a
doubled reading. The other two (digest, security) stay on Option A or B.

**No recommendation offered.** A and B are ours to live with; C is a promise to
a customer and is yours.

---

## 3 · Does our contract wording say "check this with your lawyer" on the signed page? (CR-011 item 9)

**Where this comes from.** You ruled on 2026-08-18 that the four documents a
customer *signs* — the service agreement, the deposit agreement, the ACH
authorisation and the payment-plan agreement — must ship with wording a utility
can then change, verbatim: *"already answer - provide default and allow user to
change"*, and *"without default sample functionalities ill not work"*.

**That is built and you can see it on screen now.** What was deliberately NOT
decided, and is flagged in CR-011 as something we must not assume, is this:

**Our wording is visible to your STAFF today with a warning attached.** When a
System Admin opens one of the four, they read:

> *"This is wording SMARTBillHub provides as a starting point. It is not legal
> advice and it is not your lawyer's words… Read it against your own policies,
> edit anything that does not match them, and choose the date it takes effect."*

**The question is whether anything like that appears on the page the CUSTOMER
signs.** It does not today, and we have not put one there.

**Option A — nothing extra on the signed page.** The utility took our starting
point, edited it, and published it under their own name with their own date. It
is their document. This is how every document template product behaves.
*(recommended — and it is the current build, so choosing A costs nothing)*

**Option B — a line on the signed page.** The exact sentence, so you are ruling
on words and not on an idea:

> *"This agreement is provided by your utility. If you are unsure about any
> part of it, seek your own advice before signing."*

· What it costs: it appears on a document your utility's customers sign, in
their name, saying something they did not write. Some utilities will want it
removed, and then it has to be removable, which makes it another editable
field rather than a guarantee.

---

## Closed since, and listed only so the record is complete

**The finance re-sign of account 4180 and the eight cost accounts** was the
third item we could not record on 2026-08-18. It was **re-presented properly
the same day** — each account named in plain English with its number and what
it is for, with the explicit statement that no dollar figure was attached to
any of them — and you confirmed. It is signed and closed:
`06-backend/apps/ledger/chart.py` now reports **nothing pending re-signature**,
and two tests assert that emptiness so it cannot drift back.

The nine, as they were shown to you: **4180 Budget billing variance** (where
the difference lands when a budget-billing customer has paid more or less than
they actually used — the worked case was a **$50.87** variance that used to
block a bill), and the eight cost accounts **5100 Purchased power · 5110
Purchased water · 5120 Sewer treatment & disposal · 5130 Trash hauling &
disposal · 5140 Purchased gas · 5145 Broadband transport · 5200 Operations &
maintenance · 5300 Infrastructure**.

---

## For the next agent, not for the Product Owner

Registry rows: OQ-256 (question 1) · OQ-262 (question 2) · CR-011 item 9's
"what it does not settle" paragraph (question 3). The finance re-sign is
recorded on `apps/ledger/chart.py`'s module docstring and asserted by
`tests/test_us_led_005_gl_designations.py:606` and
`tests/test_us_led_017_cost_chart.py:373`.

**Do not re-ask any of these as an ID.** That is what produced this file.

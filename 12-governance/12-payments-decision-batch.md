# Payments & Collections — ONE decision batch for the Product Owner

**Date assembled:** 2026-08-11 · **For:** Product Owner, one sitting · **Assembled by:** payments research lane (no code written, nothing under `06-backend/apps/` or `07-frontend/src/` touched)

---

## Why this file exists

On 2026-08-11 you ruled that **all of collections comes into R2** — *"B All of collections A, plus
bounced payments, refunds, collections, payment plans, budget billing, bank reconciliation"*.

That is the largest scope item in the project so far. Four or five build lanes will now work
inside it at the same time, and **several of these areas carry their own money law rather than
being mechanical** — the engineering plan says so in its own words: NSF fees, refund routing,
budget-billing true-up and bank-reconciliation matching are rule-bearing.

If each lane finds its own questions as it codes, you get them one at a time over several days and
the lanes stall in between. **So every question was found first, and they are all here, once.**

## How this was assembled

1. Every payments specification was read end to end — the module overview, all 38 business rules,
   the field map, the flows, and all seven epics (25 stories, ~180 test cases).
2. The ledger side was read for where the money lands, plus the five end-to-end journeys that cross
   payments (bounced-cheque life, payment-plan life, budget-billing year, overpay-and-refund,
   lockbox day).
3. **The two finance-signed documents (the money-math rules and the golden tests, both frozen
   2026-08-08) were read as LAW, not as input.** Anything they settle is not in this file as a
   question — it is in the "already decided" list below, so nobody re-opens it. A day was lost this
   session treating one signed rule as an open design choice; that list exists to stop it happening
   again.
4. The open-questions registry was checked so nothing already asked is asked twice.
5. The clickable prototype's payments, collections and reconciliation screens were checked for what
   the product visibly promises.

**Nothing in this file has been decided by the agent that wrote it.** Where the specifications
already answer something, it is reported as answered and cited. Where they are silent, it is here
as your decision. Where a recommendation is given it is labelled as a recommendation and you may
reject it; several decisions have no recommendation and say so.

## How to read a decision

Each one is: a plain-English question with **real money in it**, taken from figures already in this
repo so you recognise them; two to four options with the consequence of each spelled out; whether a
lane stalls without it; and a source line at the end which is **for the next agent, not for you**.

**The figures you will keep seeing** (all already in the repo): the **$117.01** bill — $100.58 of
electricity and base charge, **$8.30** of tax, an **$8.13** late fee. The **$292.87** cheque. The
**$57.13** credit left over from an overpayment. The **$267.30** payment plan — $50 down, then five
payments of **$36.22** and a last one of **$36.20**. The budget-billing customer whose bills average
**$242** a month. The day's takings of **$471.39** in cheques and **$121.78** in cash.

---

## Summary — 20 decisions, 14 of which stall a lane

| # | The decision, in one line | Stalls a lane? | Registry |
|---|---|---|---|
| **A1** | Money reaches the bank on time but reaches our system late — is the customer late? | **YES** | OQ-131 |
| **B1** | A cheque bounces after we already refunded the change from it | **YES** | OQ-132 |
| **B2** | After a cheque bounces, where does the chasing-letter sequence restart? | **YES** | OQ-133 |
| **B3** | A cheque bounces after the day's banking was already signed off and locked | **YES** | OQ-134 |
| **C1** | Must a refund go back the way the money came in? | no | — |
| **C2** | Do we refund someone who owes us money on another account? | **YES** | OQ-135 |
| **C3** | Do we post a cheque for 43 cents? | no | — |
| **D1** | Someone in the chasing sequence pays part of what they owe — what happens next? | **YES** | OQ-136 |
| **D2** | Do we send a $8 certified letter to collect $2.40? | **YES** | OQ-137 |
| **D3** | After the final 48-hour notice — does anything actually disconnect in this release? | no | — |
| **D4** | Two buttons the prototype shows that no rule covers (collections agency, deposit flag) | no | — |
| **E1** | A customer on a payment plan gets a new monthly bill — what do they owe? | **YES** | OQ-138 |
| **E2** | Their payment arrives — does it go to the plan or to the new bill? | **YES** | OQ-139 |
| **E3** | The plan is signed but the down payment never arrives | no | — |
| **F1** | On budget billing, is the customer's balance the real bill or the level amount? | **YES** | OQ-140 |
| **F2** | What exactly is a "missed level payment" that drops someone off budget billing? | **YES** | OQ-141 |
| **F3** | Where does the once-a-year budget settle-up land in the books? | **YES** | OQ-142 |
| **G1** | Money taken today but banked Thursday — which account holds it in between? | **YES** | OQ-143 |
| **G2** | Card takings never equal the bank line, because the processor keeps its fee | **YES** | OQ-144 |
| **G3** | A line on the bank statement that matches nothing we recorded | no | — |

**Please answer the 14 marked YES first if the sitting is short.** The six marked "no" have a
defensible current behaviour and the lanes will build that behaviour and keep going; they are here
because you should still see them, and because the current behaviour is a consequence nobody chose
on purpose.

---

## ALREADY DECIDED — please do NOT re-open these

Every line here is signed, ruled or frozen. They are listed so this sitting spends no time on them,
and so no lane presents them back to you as a choice.

| Already decided | The decision | Where it was decided |
|---|---|---|
| The bounced-cheque fee | The customer is charged **your own NSF charge code**, whatever amount you set it to. The $30 on screen is a sample. It is never typed by staff and never hardcoded | B4 §NSF · BR-PAY-013 · BR-BIL-007 |
| What a bounce does | The payment is reversed with a new row (never edited), the bills it paid re-open, and **the original due date stands — the late-fee clock does not restart**. The bounce count goes up; at 2 (your setting) the account goes cash-only and off autopay. Worked and frozen: a $292.87 cheque bounces, $30 fee, balance **$322.87** | BR-PAY-013 · PE-7 · journey J12 |
| Who pays the bank's own charge | **You do.** The bank's fee appears on your statement, is explained during reconciliation with a reason, and lands in the signed **bank-fees account 6800**. This is not the customer's NSF fee — they are two different amounts | BR-PAY-019 · OQ-110 closure |
| Refunds | Only out of a real credit balance. Admin approval. Cheque or bank transfer in this release — **card refunds wait for the payment rails**. Books: customer-credit account down, cash down. The row is permanent; a lost cheque is voided by a reversing entry, never deleted | BR-PAY-014 · PE-9 ($57.13) |
| One person approving their own request | **Allowed in this release**, as long as both acts are recorded separately. Enforced separation of duties is a later release | BR-PAY-037 |
| Undoing a payment | Bank transfers 60 days, cards 120 days, cheques unlimited. Outside the window, or a closed month, needs Admin approval — never a dead end. The screen always says in plain words what will happen before you confirm | BR-PAY-011 · BR-PAY-030 |
| Which part of a bill a payment pays first | Oldest bill first; inside a bill: usage and base charge → taxes → **your own tenant-defined class** → fees and late charges last. Ruled by you on 2026-08-11 and already built and tested | BR-PAY-010 · BR-PAY-038 |
| The three loose ends of that same ruling | Already asked, already waiting for you — where the tenant-defined class is set up, whether there can be more than one, and what happens to bills issued before it existed. **Not re-asked here** | OQ-123 · OQ-124 · OQ-119 |
| Overpayments | Carried as an account credit, applied automatically to the next bill, refundable on request. Worked: pay $350 against $292.87 → **$57.13** carried | BR-PAY-010 · PE-4 |
| Taking money from a closed or disconnected account | **Always accepted**, in any account state, tagged to the account. Accepting money never changes the account's status by itself | BR-PAY-036 |
| The two dates on every payment | Posted (when it entered our system) and cleared (when the money actually arrived) — always both. Billing judges on-time by the posted date; bounces and bank matching use the cleared date. The posted date is typed by staff, with a sensible date pre-filled | BR-PAY-021 · BR-PAY-033 |
| The chasing sequence | Reminder 3 days after due → late fee → 10-day notice → 5-day notice → 48-hour certified final. All intervals are your settings. Paper this release; certified mail compulsory on the last one; medical-hold accounts are skipped and the skip is recorded. Every notice is written to a queue, never sent inline | BR-PAY-017 · BR-NOT-005 |
| "Days late" | Today minus the **oldest unpaid bill's due date** — everywhere in the product | BR-PAY-032 |
| Payment plans | Instalment = (balance − down payment) ÷ number, rounded to the cent, remainder on the **last** one. Worked and frozen: $267.30 − $50 over 6 → five of **$36.22** and a final **$36.20**. The customer's signature alone activates it — no counter-signature. One live plan per account. While it is active and current, chasing and disconnection pause. Two missed instalments void it | BR-CUS-043 · BR-CUS-044 · BR-PAY-016 · PE-13 |
| Budget billing arithmetic | Level = last 12 months' bills ÷ 12, rounded to whole dollars — worked and frozen: $2,904 → **$242**. Re-check every 6 months, re-level if it has drifted 20%. Staff may override with a reason, within 30% either way. The yearly settle-up is **not taxable** — tax was already charged on the real bills | BR-BIL-017 · OQ-068 · WE-8 |
| Bank reconciliation | Statement import; automatic match on **equal amount and date within 3 days** (a finance setting). Every difference must carry a reason and an account — **"force match anyway" does not exist**. Once reconciled the batch is locked; un-reconciling is the only way back and it is recorded | BR-PAY-019 · BR-PAY-004 · BR-PAY-035 |
| Which day a deposit batch belongs to | The **posted** day — the physical drawer day — not the day the bank credits it | BR-PAY-025 · BR-REP-013 (your ruling RQ-5) |
| Writing off a bad debt | Started in Payments, **approved in Finance** before any money moves; books: bad-debt expense 6900 up, receivables 1200 down | BR-PAY-020 · BR-LED-008 |
| Tax accounts | **One payable account per tax authority.** This is finance-signed law, not a design choice | B5 seed chart, line 74 |
| Duplicate imports and duplicate webhooks | Same file cannot be imported twice; the block names who imported it, when, and links to it | BR-PAY-023 · BR-PAY-028 |
| Money dated into a closed month | Posts forward into the earliest open month automatically, with a note | BR-TEN-038 |

---

# A · Recording and importing payments

### A1 · The money reached the bank on time. It reached our system late. Is the customer late?

**BLOCKING** — the import lane must stamp a date on every imported payment and cannot guess.

**The situation, with real numbers.** A customer's bill for **$117.01** is due **22 August**. They
post a cheque; the bank's lockbox receives it and banks it on **20 August**. The lockbox file comes
to us and a clerk imports it on **25 August**. Our rule says billing judges on-time by the *posted*
date (when it entered our system). So the system currently says this customer paid three days late
and charges them a late fee of **$8.13**, even though their money was in the bank two days early.

**Two of our own confirmed rules disagree about what the posted date should be here.** One says the
posted date at import comes from the file's own data. The other, in the import story, says the
posted date is the moment of the import commit. Somebody has to be right.

| Option | What it means | What it costs |
|---|---|---|
| **A — The file's bank date becomes the posted date** (so posted 20 Aug, cleared 20 Aug) | The customer is on time. The clerk can import a week late with no harm to any customer | The posted date no longer means "when it entered our system" for imports — two doors, two meanings |
| **B — The commit date is the posted date, as the import story says** (posted 25 Aug) | Consistent meaning of "posted" everywhere | Every customer who mails a cheque is at the mercy of how fast we import. A slow Monday costs customers $8.13 each. This is the behaviour today |
| **C — On-time = the EARLIER of the two dates, for imports and counter entries alike** | Customer-favourable and simple to explain to a regulator | Changes the on-time test itself, which billing already uses; the late-fee lane must be re-pointed |
| **D — Posted date defaults from the file but the clerk can override it** (this is what the rule already says the pre-fill should do) | Matches the confirmed pre-fill-and-override rule; staff keep judgement | A clerk who never looks at the field decides customers' late fees by inattention |

**Recommendation:** none — this is a customer-fairness policy call, not an engineering one. Worth
noting only that the late-fee boundary you ruled this morning went the customer-favourable way for
exactly this kind of ambiguity.

**Until you decide:** the import lane commits rows but marks the on-time evaluation with the open
question and does not charge a late fee off an imported payment.

*Source (for the next agent): BR-PAY-021 · BR-PAY-033 · US-PAY-003 TC-3 · field-map P-3 · GT-8 · OQ-131*

---

# B · Bounced payments

### B1 · The cheque bounces, but we already gave the customer the change from it

**BLOCKING** — the bounce routine must either allow a negative credit or refuse; it cannot guess.

**The situation, with real numbers.** On 19 July a customer pays **$350.00** against a balance of
**$292.87**. The extra **$57.13** becomes an account credit. On 24 July they ask for it back and we
post them a refund cheque for **$57.13** — money out of our bank, correctly approved. On 3 August
the original $350.00 cheque bounces.

Reversing the payment reverses $292.87 of bill payments (fine — those bills re-open) **and $57.13
of a credit that no longer exists**. The customer now owes us the original $292.87, the bounced-cheque
fee, and $57.13 of our money that is in their pocket.

| Option | What it means | What it costs |
|---|---|---|
| **A — The account credit is allowed to go negative** (−$57.13) and simply nets against the next bill | Nothing new to build; the arithmetic is right | A "credit balance" that is a debt is confusing on screen and in the books, and a negative credit balance can be refunded by a later mistake |
| **B — The $57.13 becomes a normal charge on the account** (its own reason code, like the bounce fee) | It reads correctly to staff and customer: "refund we sent you, on a cheque that bounced". Chaseable through the normal sequence | Needs a reason code and an account for it; slightly more to build |
| **C — Refuse to reverse and route it to a human** — the bounce cannot be processed automatically once any part of the money has left | Nothing wrong can be posted automatically | A clerk has to resolve it by hand every time, and "the bounce is stuck" is a bad state for a book to be in |

**Recommendation:** none. Note only that this repo's standing law is *corrections are new rows,
never edits*, which options A and B both satisfy.

**Until you decide:** the bounce routine handles the ordinary case and refuses this one, citing the
open question.

*Source: BR-PAY-013 · BR-PAY-014 · journeys J12, J15 · PE-4/PE-9 figures · OQ-132*

### B2 · After a cheque bounces, where does the chasing sequence restart?

**BLOCKING** — the sequence engine must pick a rung and cannot guess.

**The situation, with real numbers.** A bill for **$1,842.10** was due **6 July**. The customer paid
by cheque on 5 July, so the chasing sequence never started — correctly. On **2 September** the bank
returns the cheque. The bill is reinstated at its original due date and is now **58 days overdue**.

What is our first contact with this customer? Under the sequence, an account 58 days overdue is
past the reminder, past the 10-day notice, past the 5-day notice — it is at the **48-hour certified
final notice**. So the customer's first letter after their cheque bounced could be a certified
notice that their supply will be cut in two days.

| Option | What it means | What it costs |
|---|---|---|
| **A — The sequence restarts at the beginning** (friendly reminder first), regardless of how old the debt is | Humane and defensible; the customer gets told their cheque bounced before anything threatening arrives | A customer can reset the whole ladder by writing a cheque they know will bounce. The overdue money waits another two to three weeks |
| **B — The sequence resumes where the debt's age puts it** — 58 days overdue means the final notice | Nobody games it; the debt is genuinely two months old | A certified disconnection notice as the first contact after a bounce. In several states that is a regulatory complaint |
| **C — Restart at the beginning, but only once per account per year** — a second bounce resumes by age | Both concerns covered | A new setting and a counter to build and explain |

**Recommendation:** none — this is a consumer-protection judgement.

**Until you decide:** the bounce reinstates the balance and the sequence engine **pauses** that
account rather than choosing a rung, so nothing wrong is posted.

**Note:** the late-fee clock is a separate matter and is already settled — it never resets.

*Source: BR-PAY-013 · BR-PAY-017 · BR-PAY-032 · OQ-133*

### B3 · The cheque bounces after the day's banking was signed off and locked

**BLOCKING** — the reconciliation lane must either break a lock or leave a permanent mismatch.

**The situation, with real numbers.** A batch of eight cheques totalling **$2,840.00** was banked,
matched to the statement and **reconciled — which locks it permanently**. Three weeks later one of
those cheques, **#4021 for $100.00**, is returned. The bounce routine reverses the payment. But the
locked batch still says $2,840.00, and the payment inside it no longer exists as good money.

Our own rule for the *unlocked* case says the batch total is recomputed so it re-ties to the bank.
Doing that after the lock would be editing a signed-off financial record, which our top-level rules
forbid.

| Option | What it means | What it costs |
|---|---|---|
| **A — The locked batch never changes.** It is a historical record of what we banked that day, which is exactly what the bank saw. The bounce is a separate later event | Nothing is edited; the books stay honest; the bank statement for that day still ties | The batch screen shows $2,840.00 for a day where $100 later came back — staff must click through to see why |
| **B — Un-reconcile the batch, correct it, reconcile again** (already an audited action) | Batch always reflects reality | Re-opens a signed-off month; the bank line for that day then no longer matches the batch, so it can never be re-reconciled cleanly |
| **C — The bounce posts a visible reducing entry against the batch** without changing its total | Both figures visible, nothing edited | New concept to build and explain |

**Recommendation:** **A**, on the grounds that the batch is a record of what physically went to the
bank on that day and the bank agreed with it — but you may prefer the batch screen to show the
later reality, in which case say so and it becomes C.

**Until you decide:** the bounce routine refuses when the payment sits in a locked batch.

*Source: BR-PAY-004 · BR-PAY-013 · US-PAY-022 TC-2 · US-PAY-023 · OQ-134*

---

# C · Reversals and refunds

### C1 · Must a refund go back the way the money came in?

**NOT BLOCKING** — staff can choose today; the product will simply do whatever they pick.

**The situation, with real numbers.** A customer pays **$350.00** by card. **$57.13** is overpaid.
Card refunds do not exist in this release (they wait for the payment rails), so today a clerk can
refund that card overpayment by **cheque** — real money out of our bank, to an address, against
money that came from a card that may itself be disputed later.

| Option | What it means | What it costs |
|---|---|---|
| **A — Staff choose freely between cheque and bank transfer** (today's behaviour) | Nothing to build; maximum flexibility | Card money can leave as a cheque, and the cardholder can still charge back. That is the classic double-loss |
| **B — Money that came in on a card can only be refunded when card refunds exist** | Closes the double-loss | A customer with a card overpayment waits until a later release, or you refuse the card overpayment at the till |
| **C — Cheque and bank transfer allowed for anything, but card-sourced refunds need Admin approval with a reason** | Loss possible but never silent | One more approval step |

**Recommendation:** **C** — it matches how this product already handles every other risky money
action (allowed, but recorded and approved).

*Source: BR-PAY-014 · PE-9 · engineering plan addendum r9 ("refund routing" named rule-bearing)*

### C2 · Do we refund someone who owes us money on another account?

**BLOCKING** — the refund service must either look at other accounts or not; it cannot guess.

**The situation, with real numbers.** One customer record is linked to several accounts — that is
already how the product works, and it is the landlord case. This customer has **$57.13 in credit on
one account** and **$948.20 overdue by 91 days on another**, on which we have already sent a final
notice. They ring up and ask for their $57.13 back.

| Option | What it means | What it costs |
|---|---|---|
| **A — Refund it. The accounts are separate** | Simple, and legally cleanest where the accounts are genuinely different premises with different responsible parties | We post a cheque to someone we are about to disconnect for non-payment. Staff will find this absurd |
| **B — Block the refund and apply the credit to the debt automatically** | The money never leaves; the debt reduces | Moving money between accounts without asking can be unlawful where the account holders differ, even under one customer record |
| **C — Warn the clerk, show the other balances, let them decide, record the decision** | Human judgement where the law is fact-specific; a full audit trail either way | A clerk can still get it wrong; needs the cross-account look-up on the refund screen |

**Recommendation:** **C** — the same advisory-with-audit shape you have already chosen twice in this
product (duplicate-customer checks and plan-eligibility checks are both advisory, not enforced).

**Until you decide:** the refund service refuses when the customer has arrears elsewhere, citing the
open question, rather than silently paying out.

*Source: BR-PAY-014 · BR-CUS-054 (one customer, many accounts) · OQ-135*

### C3 · Do we post a cheque for 43 cents?

**NOT BLOCKING** — buildable either way; the sum is small but the postage is not.

**The situation, with real numbers.** A closed account has a **$0.43** credit. A cheque costs us an
envelope, a stamp and a clerk's minute. You have already ruled that at final settlement, balances
under **$5** are written off in **both directions** (tenant-adjustable 0–50). That ruling is about
final bills; a customer simply asking for their credit back comes through a different door and no
rule covers it.

| Option | What it means | What it costs |
|---|---|---|
| **A — The same $5 threshold applies to any refund** | One number, one rule, already yours | A customer asking for their $3 back is told no |
| **B — No threshold on a requested refund** — if they ask, they get it | Nobody is ever refused their own money | We post 43-cent cheques |
| **C — Threshold applies to automatic clean-ups only; a customer request always pays out** | Both | Two paths to explain |

**Recommendation:** **C**.

*Source: OQ-070 closure (final-settlement $5) · BR-PAY-014*

---

# D · Collections

### D1 · Someone in the chasing sequence pays part of what they owe. What happens next?

**BLOCKING** — the sequence engine evaluates every account every day and must know.

**The situation, with real numbers.** An account owes **$948.20** and is **91 days** overdue. The
final notice went out on 1 August. On 5 August the customer pays **$50.00**. Under the rules as
written, the sequence stops only on three things: money posted **by the due date**, an active
payment plan, or full settlement. A $50 payment on a 91-day-old debt is none of those — so the
48-hour certified disconnection notice goes out on schedule, two days after they paid us.

| Option | What it means | What it costs |
|---|---|---|
| **A — Nothing changes; the sequence continues** (today's behaviour) | Nobody stops a disconnection with a token $5 payment | We disconnect a customer who is paying us. This will produce complaints and it is the behaviour we would ship by accident |
| **B — Any payment pauses the sequence for a set number of days** (your number, a setting) | Rewards engagement; simple to explain to a customer: "pay something and we hold for 10 days" | Serial $5 payments can hold a large debt indefinitely unless you cap it |
| **C — A payment that clears the oldest overdue bill in full moves the sequence back a rung; anything less changes nothing** | Ties the pause to real progress | A customer paying half of a large bill gets no relief |
| **D — Any payment resets the sequence to the beginning** | Most forgiving | A large old debt can be held off forever with small payments |

**Recommendation:** none — this is your collections policy, and the four options produce visibly
different customer experiences. If it helps: B with a cap is what most small utilities do.

**Until you decide:** the sequence engine treats a partial payment as no change (option A) **but
will not send the final certified tier** to an account that has paid anything in the last 30 days,
and flags the account for a human. That is a deliberately conservative stub, not a decision.

*Source: BR-PAY-017 · BR-PAY-021 · BR-PAY-032 · OQ-136*

### D2 · Do we send an $8 certified letter to collect $2.40?

**BLOCKING** — the sequence engine needs a floor or an explicit "no floor".

**The situation, with real numbers.** An account pays its **$328.60** bill but keys the amount
wrong and leaves **$2.40** outstanding. Nothing in any rule stops the chasing sequence from running
on that $2.40: a reminder, then a late fee of **$5.00** (the minimum fee, which is more than twice
the debt), then a 10-day notice, then a 5-day notice, then a **certified 48-hour disconnection
notice** that costs about $8 in postage alone.

| Option | What it means | What it costs |
|---|---|---|
| **A — No floor; everything is chased** (today's behaviour) | Consistent | We spend $15 chasing $2.40, and threaten to disconnect over it |
| **B — A minimum balance setting below which the sequence never starts** — you name the seeded default | One setting, applies everywhere; small residues age quietly and get swept up by the next bill | Small debts accumulate for accounts that always underpay slightly |
| **C — A floor only on the expensive rungs** — reminders always go, but notices and certified mail need a balance above the threshold | Customer still gets told; we never spend more than the debt | Two numbers instead of one |

**Recommendation:** **C**, with **B** as an acceptable simpler answer. Either way **please give the
number** — the code will otherwise have no seeded default and every tenant will start at zero,
which is option A by accident.

*Source: BR-PAY-017 · BR-BIL-001 (minimum late fee $5.00) · OQ-137*

### D3 · After the final 48-hour notice — does anything actually disconnect in this release?

**NOT BLOCKING** — the sequence itself is fully buildable; this is a scope question.

**The situation.** The chasing sequence ends at a certified notice saying the supply will be cut in
48 hours. In the product as specified, **nothing then happens**: there is no work order, no
disconnection step, no state change, and the reconnection fee is shown on the notice but never
charged. Field visits and disconnection scheduling were explicitly left out of the payments module.

Your ruling brought "collections" into this release. Whether the *end* of collections is in it is
the open half.

| Option | What it means | What it costs |
|---|---|---|
| **A — This release ends at the notice.** Staff mark accounts for disconnection by hand and do the field work outside the system | Nothing more to build; matches what is specified today | The product promises a cut-off it cannot carry out, and the reconnection fee is never billed to anyone |
| **B — Add the disconnection step in this release**: an account state change, a work list, and the reconnection fee charged on restoration | The loop actually closes and the fee earns money | New work in this release, on top of the largest scope item so far |
| **C — Add only the state change and the fee; no field work list** | Small, closes the money hole | Field work still lives on paper |

**Recommendation:** **C** if you want the reconnection fee to be real money in this release;
otherwise **A** — but if it is A, please say so out loud, because the notice text promises
something the product will not do.

*Source: BR-PAY-017 · BR-CUS-039 · BR-CUS-055 (the "Marked disconnect" account state exists already)*

### D4 · Two buttons the prototype shows that no rule covers

**NOT BLOCKING** — both are currently excluded from this release, deliberately and on the record.

The write-off screen in the prototype offers **"Send to collections agency instead"** and **"Flag
these accounts so future service requires a deposit"**. Neither has any rule behind it, so both were
excluded rather than invented. With all of collections now in this release, you may want them.

| Option | What it means | What it costs |
|---|---|---|
| **A — Keep both out** (today) | Nothing to build | The buttons stay off the screen; staff who expect them will ask |
| **B — Bring in the deposit flag only** — a written-off customer who comes back must pay a deposit | Small: one flag, read at move-in where deposits are already computed | — |
| **C — Bring in both** | Complete | An agency hand-off is a real integration with an outside company: file format, fees, recall, and what happens when the agency collects. Not small |

**Recommendation:** **B**. The deposit flag is nearly free and protects real money; the agency
hand-off is a project of its own.

*Source: field-map discrepancies P-4 and P-5 · BR-PAY-020 · BR-RAT-020 (deposits by category)*

---

# E · Payment plans

### E1 · A customer on a payment plan gets a new monthly bill. What do they owe?

**BLOCKING** — nothing can display an amount due, and the chasing sequence cannot be evaluated, until this is answered.

**The situation, with real numbers.** A customer owes **$267.30** in arrears. They sign a plan: $50
down, then six payments of **$36.22** (last one $36.20) on the 1st of each month. The plan is
active, so chasing and disconnection are paused.

On 1 October their **new** monthly bill arrives for **$184.20** — ordinary current usage, nothing to
do with the arrears. What do they owe on 1 October: **$36.22**, or **$220.42**? And if they pay the
$36.22 and never pay the $184.20 again for six months, what happens? Today: nothing. Chasing is
paused because the plan is active and current, and only missed *instalments* count toward the two
misses that void a plan. A customer on a plan can stop paying their current bills entirely and the
product will not chase them for half a year.

| Option | What it means | What it costs |
|---|---|---|
| **A — The plan covers the old debt; current bills are due as normal, and failing to pay a current bill breaks the plan** (the standard "stay current" clause in US utility plans) | The hole closes. The customer's obligation is clear: pay this month's bill and your instalment | The agreement wording must say it, and a customer one day late on a current bill loses their plan unless you add grace |
| **B — Current bills are due as normal, but only missed instalments void the plan; the chasing sequence resumes for unpaid current bills only** | Softer; the plan survives a bad month on current usage | Two sequences running against one account — confusing on screen and in the notices |
| **C — New bills are absorbed into the plan and it re-amortises** | One number to pay, ever | The plan never ends for a customer who keeps using service; the arithmetic and the signed agreement both change every month |
| **D — Today's behaviour: current bills are due but nothing chases them while the plan runs** | Nothing to build | Six months of unpaid current usage, invisible. This is the accidental answer, not a chosen one |

**Recommendation:** **A** — it is the standard, it is what the agreement template can state plainly,
and it is the only option where the customer's total obligation is unambiguous. Please also say
whether a current bill paid a few days late should break the plan or whether it gets the same grace
period as everything else.

**Until you decide:** the plan lane builds the schedule, the notices and the void, and leaves the
"what is due this month" calculation raising the open question rather than choosing.

*Source: BR-CUS-043 · BR-PAY-016 · BR-PAY-019 · journey J13 · OQ-138*

### E2 · Their payment arrives. Does it go to the plan or to the new bill?

**BLOCKING** — the allocation engine already exists and will apply the ordinary rule unless told otherwise.

**The situation, with real numbers.** Same customer. The arrears sit in old bills; the new October
bill is **$184.20**. They send **$184.20**, clearly meaning to pay this month's bill. The confirmed
allocation rule is **oldest bill first** — so their $184.20 goes onto the old arrears bills that the
plan already covers, the October bill stays unpaid, and the account looks delinquent on current
usage while the plan is over-served.

| Option | What it means | What it costs |
|---|---|---|
| **A — Oldest bill first, always** (today's rule, applied without exception) | One rule, no special cases, already built | A customer on a plan can never pay their current bill. Every month they look delinquent |
| **B — Payments linked to the plan go to the plan schedule; everything else goes to the current bill first** | Matches what the customer means, both times | Needs the payment to know it is an instalment — the linkage exists in the design already |
| **C — Staff pick the target on every payment** (the "specific bill" option already on the form) | No new rule | Every plan payment becomes a manual decision — for a two-person utility that is the wrong default |

**Recommendation:** **B**. Note that this is a **narrow exception to the allocation order you signed**
— it does not change the order inside a bill, only which bill a plan-linked payment reaches first.
If you would rather not touch allocation at all, say A and accept the consequence in the last
column.

*Source: BR-PAY-010 · BR-PAY-012 (plan-down purpose) · BR-CUS-043 · OQ-139*

### E3 · The plan is signed but the down payment never arrives

**NOT BLOCKING** — the confirmed rule already says signature alone activates; the lane will build that.

**The situation, with real numbers.** A plan for **$267.30** with **$50 down** is signed on 1
September. Signature alone activates it, which immediately pauses chasing and disconnection. The
$50 never arrives. We have stopped collecting on a $267.30 debt in exchange for a signature.

| Option | What it means | What it costs |
|---|---|---|
| **A — Signature alone activates** (today's confirmed rule) | Frictionless; a customer can set up a plan over the phone | Chasing stops for a customer who has paid nothing |
| **B — Signature plus the down payment posted** | No pause without money | A customer signing at 4pm waits for their cheque to clear before they are protected |
| **C — Signature activates, but the plan voids automatically if the down payment is not posted within a set number of days** | Both | One more timer and notice |

**Recommendation:** **C**, but this changes a rule you have already confirmed, so it needs your word
rather than a lane's judgement. Until then the lane builds **A** exactly as confirmed.

*Source: BR-CUS-044 · BR-PAY-012 · PE-13*

---

# F · Budget billing (level pay)

### F1 · Is the customer's balance the real bill or the level amount?

**BLOCKING** — this decides what every screen, every ageing report and the chasing sequence say about a budget customer. It also decides F3.

**The situation, with real numbers.** A customer's bills average **$242** a month, so that is their
level. In July their **real** bill is **$292.87**. We recognise $292.87 of revenue and tax — that
part is settled and correct. The customer pays **$242**.

What does the account owe on 1 August? If the bill's amount due is the real **$292.87**, the
customer is **$50.87 short every month**: they appear in the 1–30 day ageing bucket, they show up on
the outstanding-balances screen, they earn a late fee, and the chasing sequence starts on them —
while doing exactly what we asked. By the third month they are $40.27 behind on paper (the frozen
sequence is −$50.87, then −$40.27, then +$2.98) even though they have never missed a payment.

| Option | What it means | What it costs |
|---|---|---|
| **A — The bill's amount due IS the level ($242).** The difference is held aside and settled once a year | Correct on every screen: the customer owes what we asked them to pay. No false ageing, no false late fees | The revenue we recognised but did not bill needs a home in the books until settle-up — see F3 |
| **B — The amount due is the real bill ($292.87); budget accounts are simply exempt from late fees and chasing** | No new bookkeeping | Every budget customer permanently shows as owing money and ages into the buckets. The outstanding-balances screen, the ageing report and the day's-sales-outstanding figure are all wrong by the total of every budget customer's variance |
| **C — The bill shows the real charges but carries a balancing line that brings the invoice total to the level** ("budget deferral −$50.87") | Amount due is the level, ageing is correct, and the bill explains itself to the customer | An extra line on every budget bill, which needs its own account — again F3 |

**Recommendation:** none between A and C — they are the same answer with different presentation.
**B is the one to avoid**, and B is closest to what the specification says today, which is why this
question is here.

**Until you decide:** the budget lane computes the level, the variance and the settle-up figures
(all frozen and testable) and does not write an amount due.

*Source: BR-BIL-017 · WE-8 · journey J09 · BR-PAY-032 · OQ-140*

### F2 · What exactly is a "missed level payment"?

**BLOCKING** — two missed payments drop a customer off budget billing, and no rule says what a miss is. The payments module is supposed to raise this event and has no definition of it.

**The situation, with real numbers.** The level is **$242**. In May the customer pays **$200** on
time. In June they pay **nothing**. In July they pay **$242** plus **$42** to catch up.

Is May a miss? Is June? Are they off budget billing in July, or square?

| Option | What it means | What it costs |
|---|---|---|
| **A — A miss is: nothing posted by the due date.** A partial payment counts as paid | Simple and forgiving; easy to explain | A customer paying $50 of $242 every month never drops off |
| **B — A miss is: less than the level posted by the due date** | Strict; protects the programme | A customer who is 10 cents short is treated the same as one who paid nothing |
| **C — A miss is a cumulative shortfall of a whole level payment or more** — track the running shortfall, not the events | Fairest, and self-correcting when they catch up | More to build, and "you have missed two payments" becomes harder to word in a notice |

**Recommendation:** **C** if you want the programme to be forgiving and accurate; **A** if you want
the simplest thing that ships. Both are defensible; **B** will generate complaints over cents.

**Until you decide:** the budget lane tracks the shortfall but does not drop anyone off.

*Source: BR-BIL-017 · US-BIL-020 TC-5 · journey J09 step 7 · OQ-141*

### F3 · Where does the yearly budget settle-up land in the books?

**BLOCKING for the ledger side of budget billing — and this one may need a finance signature, not just yours.**

**The situation, with real numbers.** Every month we recognise the real bill as revenue and tax —
**$292.87** in July — but ask the customer for **$242**. Over a year the difference accumulates
(**−$50.87**, then **−$40.27**, then **+$2.98** in the frozen worked example) and in the settle-up
month it is collected or credited in one line, which is **not taxable** because the tax was already
charged monthly. All of that is settled.

What is not settled is **which account the other side of that line touches**. The finance-signed
chart of accounts has no budget or deferral account. The eleven account designations you confirmed
this morning do not include one.

| Option | What it means | What it costs |
|---|---|---|
| **A — No new account needed: receivables carry the variance** | Nothing to add | Only coherent if F1 is answered "the customer owes the real bill" — otherwise receivables and the customer's stated balance disagree |
| **B — Use the already-signed "unbilled receivables" account (1210)** — revenue recognised, not yet billed, which is exactly what a budget variance is | The account exists, is signed, and already has a designation. Nothing new to sign | It is also used for month-end accruals, so the balance mixes two things unless reported by dimension (which the ledger already supports) |
| **C — Add a new signed account, e.g. "budget billing deferral"** | Cleanest reporting; the balance means one thing | **The chart of accounts is finance-signed and frozen. Adding an account is a finance re-signature, not an edit** — a separate step, however small |

**Recommendation:** **B**, on the grounds that it needs no new signature and the account already
means what we need it to mean. But please answer **F1 first** — if F1 says the customer owes the
real bill, the answer here is A and there is nothing to add.

*Source: B5 seed chart line 74 (frozen) · OQ-110 closure (eleven designations) · WE-8 · ledger workbook variation V-4 · OQ-142*

---

# G · Deposit batches and bank reconciliation

### G1 · Money taken today, banked Thursday. Which account holds it in between?

**BLOCKING** — every payment posts to the books, and the posting rule literally reads "cash/undeposited". Somebody must pick.

**The situation, with real numbers.** On Friday 8 August we take **$471.39** in cheques and
**$121.78** in cash across the counter. They are batched that day. They physically reach the bank
the following **Tuesday**, and appear on the statement then.

Our chart of accounts, signed by finance, contains **both** "1000 Cash" and "1010 Undeposited
funds", and this morning you confirmed designations for both. But nothing says when each is used,
and the two documents that show worked postings disagree: the frozen trial balance books customer
payments straight to **Cash**, while the account list describes Undeposited funds as exactly this
case — "taken but not yet banked".

| Option | What it means | What it costs |
|---|---|---|
| **A — Payments go straight to Cash when they clear.** Undeposited funds is never used | **This is what the frozen trial balance already shows** — no signed figure changes | Our Cash balance says money is in the bank days before it is. A bookkeeper reconciling by the book will query it |
| **B — Payments go to Undeposited funds; reconciling the batch moves it to Cash** | Textbook correct, and it makes the bank reconciliation meaningful | It makes reconciliation a bookkeeping event, and today's rule says batches post nothing at all. **It also changes the frozen trial balance, which is a finance re-signature** |
| **C — Cash for electronic money (transfers, cards), Undeposited funds for cash and cheques** | Matches physical reality closely | Two rules; still changes the frozen trial balance for the cheque case |

**Recommendation:** none, but the consequence is worth stating plainly: **A is the only option that
changes no finance-signed figure.** B and C are more correct bookkeeping and cost a re-signature.
Note also that the prototype's accounting hand-off screen already offers the bookkeeper a choice
between an operating-cash account and an undeposited-funds account, so the product has been
promising this choice all along.

**Until you decide:** the posting service refuses to post payments rather than pick an account.

*Source: EP-LED-01 posting table ("cash/undeposited") · LE-1 frozen trial balance · OQ-110 closure · PE-10 · OQ-143*

### G2 · Card takings never equal the bank line, because the processor keeps its fee

**BLOCKING** — this is the difference between a reconciliation that runs itself and one that a person works by hand every single day.

**The situation, with real numbers.** A day's card payments total **$5,120.40**. The processor
deposits **$4,972.90** — it kept **$147.50** in fees. Our matching rule is **equal amount, date
within three days**. $4,972.90 does not equal $5,120.40, so this never matches automatically. Every
card day becomes an exception a person opens, reads, explains with a reason and an account, and
closes. That is roughly **250 exceptions a year for one bank account**, for a utility with one or
two staff.

The same rule also cannot handle a bank that combines two of our deposits into one credit line, or
splits one deposit across two.

| Option | What it means | What it costs |
|---|---|---|
| **A — Leave it. Every card day is an exception worked by hand** (today's rule) | Every difference is deliberately explained by a human — which is exactly the control you asked for | About 250 manual reconciliations a year, and staff will start rubber-stamping them, which destroys the control |
| **B — Allow an expected-fee rule per bank account or method** — a difference inside the expected fee range is auto-explained, **still writing the reason and the account** | The control survives (nothing is unexplained) and the daily work disappears | You must set an expected fee range; a genuine error inside the range would be auto-explained too |
| **C — Allow several of our batches to match one bank line, and one batch to match several lines** | Fixes the combined-deposit case, which no setting can work around | More matching logic; the screen must show the grouping |
| **D — B and C together** | The reconciliation actually reconciles | Most to build |

**Recommendation:** **D** if card payments matter to your customers; **C** at minimum, because a
bank that combines deposits cannot be worked around by any setting and will simply leave batches
permanently unmatched. **Note this does not touch the "no force match" rule** — every difference
still carries a reason and an account.

*Source: BR-PAY-019 · BR-PAY-035 · US-PAY-021 · prototype figures (DEP-0804-CARD $5,120.40 vs $4,972.90) · OQ-144*

### G3 · A line on the bank statement that matches nothing we recorded

**NOT BLOCKING** — the wizard can show them and leave them; the question is what staff may then do.

**The situation.** The import screen already counts a fourth category: **"Not in our system"** — a
credit on the statement matching no batch of ours. In real life this is bank interest, a customer
who paid by transfer without telling us, a transfer from another of our own accounts, or a bank
error. Nothing in any rule says what staff may do with one, and nothing says whether the month can
be closed while any are outstanding. The month-end checklist says "bank rec current" without ever
defining it.

| Option | What it means | What it costs |
|---|---|---|
| **A — Show them, leave them; they are never resolved** | Nothing to build | Unexplained money on the statement forever, and "bank rec current" means nothing |
| **B — Staff may create a payment or a journal entry directly from an unmatched bank line, with a reason** | The statement can always be reconciled to zero | A route into the books from a bank file — needs the same approvals as any other money entry |
| **C — B, plus the month cannot be closed with unexplained lines unless Finance confirms with a reason** | Closes the loop; matches how month-end close already works (warn and confirm, never a hard lock) | One more checklist item |

**Recommendation:** **C**, since the month-end close already works exactly this way for everything
else.

*Source: prototype S38 "Not in our system" tile · BR-PAY-019 · BR-LED-006 · BR-LED-018*

---

## Findings — things to fix, not things to decide

These are not questions for you. They are contradictions found while reading, recorded so a lane
fixes them rather than quietly picking a side.

| # | Finding | What it needs |
|---|---|---|
| **F-1** ✅ **DONE 2026-08-11 (bank-rec lane)** | **Deposit batches: which day.** You ruled the batch day is the **posted** day (the drawer day). The deposits epic still says the batch groups on the **cleared** day and has a test case asserting it. One of them is stale — the ruling wins | Fixed: EP-PAY-06 US-PAY-020 (story text, TC-3, field-map row and acceptance bullet), 04-flows.md §1 and 03-field-map.md §6 all corrected and stamped, **DEF-065** filed, and `test_us_pay_020_tc3__the_batch_day_is_the_posting_day_not_the_clearing_day` now drives a payment posted 8 Aug / cleared 9 Aug and requires the **8 Aug** batch |
| **F-2** | **The imported posting date.** One confirmed rule says an import takes the posting date from the file; the import story says it is the commit moment. This is the evidence behind decision A1 | Resolved by A1; the loser gets a documentation fix |
| **F-3** | **The allocation maths file is not on the human-review guard list.** The file that decides which part of a bill a payment pays first carries both required review markers and its ledger row, but the guard's file list does not name it, so the guard does not check it. The file's own docstring reports this rather than fixing it | Add the path to the guard list (an owner outside the payments lane) |
| **F-4** | **The past-due filter was removed from the billing screen** because no payments module existed to answer it. Now one is being built. It was recorded at the time so it would be put back rather than read as a decision that it should not exist | The payments lane restores it when balances become answerable |

---

## What each lane does until these are answered

Per the prime directive, no lane resolves any of this by choosing a value. Concretely:

- **Recording and import** — builds fully; the on-time judgement on imported payments raises the open question rather than charging a late fee.
- **Bounced payments** — builds the ordinary case exactly as frozen ($292.87 → reversal → $30 fee → $322.87); refuses the refunded-credit case and the locked-batch case; pauses the chasing sequence rather than choosing a rung.
- **Refunds** — builds fully; refuses when the same customer has arrears on another account.
- **Collections** — builds the sequence, the notices and the history; treats a partial payment conservatively and will not send a certified final notice to anyone who has paid recently; no minimum-balance floor is invented.
- **Payment plans** — builds the schedule, the agreement, the notices and the void; does not compute "what is due this month" while a current bill is open.
- **Budget billing** — computes level, variance and settle-up (all frozen figures, all testable now); writes no amount due and drops nobody off.
- **Deposits and bank reconciliation** — builds batches, import, matching, exceptions and the lock; the posting service will not post a payment until the cash-versus-undeposited question is answered.

Every one of these is a `NotImplementedError` naming its open question, never a guess.

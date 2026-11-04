# CR-085 · lane 7 · WHEN MONEY IS TIGHT — the drawing, quoted

**Identify only. Nothing in this file changes product code.**

**Source.** `05-prototype/SMARTBillHub Customer Portal Blueprint.pdf`, section **07
"When money is tight"** (pages 73–86, screens 41–49) for nine of the ten routes, and
section **02**'s screen **08 "Prices and fees"** (pages 17–18) for the tenth,
`/fees`. Read with `10-scripts/pdf/pdf_text.py`, with `￾` and `­` stripped before
matching, as the lane brief requires. ⚠ **Page 129 is truncated mid-table**, so the
index rows for screens **48** and **49** are simply not in the file; everything below
for those two comes from their own spread (pages 83–86), which is complete.

**How to read it.** Labels are quoted **verbatim and in the order they are drawn**,
phone frame first then desktop, exactly as the blueprint lays them out. Per **B14
rule 37** every FIGURE below is an illustration and never a fact to build to; what is
binding is the **presence, the order and the words**. Per **B14 rule 38**, where the
drawing and our UI rules disagree about how a FORM is built, the UI rules win — which
bites on screen 42 and is said again there.

⚠ **THE WORDS MATTER MORE ON THESE NINE SCREENS THAN ANYWHERE ELSE IN THE PRODUCT.**
The drawing says so of itself on screen 41 — *"Anything that reads as a threat without
a route out is a failure of this screen"* — and that sentence is the standard the
findings file rules against.

---

## Screen 41 · Past due · `/:tenant/portal/overdue`
*EXISTS BEHIND · NO COMMITMENT*

**The question:** *"how bad is this, and what do I have to do to stop it? Anything that
reads as a threat without a route out is a failure of this screen."*

### PHONE · 390, in order
```
← Bills
PAST DUE
$247.30
Since Jul 22, 2026 · 22 days
Your service is scheduled to be shut off on Aug 27 unless this is paid or you
arrange something.
THREE WAYS OUT
  Pay $247.30 now
  Ask for a payment plan
  See if you qualify for help
```

### DESKTOP · 1280, in order
```
← Bills
PAST DUE
$247.30
Overdue since Jul 22, 2026 — 22 days
Your service is scheduled to be shut off on Aug 27, 2026
unless this is paid, or you arrange a plan, or help is approved.
WHAT MAKES UP THE $247.30
  July 2026 bill — due Jul 22            $176.20
  August 2026 bill — part still unpaid    $66.10
  Late fee, added Aug 1                    $5.00
  Total past due                         $247.30
THREE WAYS TO STOP THIS
  Pay $247.30 now
  Ask for a payment plan — from $20.61 a month
  See if you qualify for help paying
Any one of these stops the shut-off.
MEDICAL EQUIPMENT AT HOME?
If anyone in your home depends on electricity for medical equipment, tell us —
you may be protected from disconnection.
→ Your protections
```
(The phone frame draws the same breakdown under the shorter heading **WHAT IS PAST
DUE** with the rows `July bill $176.20 · August bill $66.10 · Late fee $5.00 · Total
$247.30`, and the shorter medical line *"If someone in your home relies on medical
equipment, tell us — different rules apply."*)

**FOR** — *"Telling a customer how serious this is, and giving them three ways out on
the same screen."*
**HOW YOU GET HERE** — *"Bills — the `Where things stand` list at the foot of the bills
page. That is the only door. Home does not link here, and it is not in the nav."*
**PRIMARY ACTION** — *"Pay is filled; the plan and the assistance route are outlined and
equally prominent as a pair. A customer who cannot pay must not have to leave to find
the alternative."*
**COGNITIVE LOAD** — *"The breakdown is itemised because customers frequently do not
recognise the total — they remember paying something. Naming the bills lets them
check."*
**TONE** — *"Factual and non-punitive. The date is stated exactly. There is no bold red
beyond the amount, no exclamation, and the sentence 'Any one of these stops the
shut-off' appears before the customer has to decide."*
**WORDS** — *"'Past due' and 'shut off' — the words the letter used. Not 'in arrears',
not 'cessation of supply'."*
**RULES** — *"Colour is never the only signal — the panel says 'Past due' in words. Bad
news always carries the way out."*
**STATES** — `LATE, NOT YET NOTICED` *"No shut-off date yet: says when one would be
issued."* · `NOTICE ISSUED` *"As drawn, with the date."* · `PROTECTED` *"Winter
moratorium or medical certificate: says the protection and its end date, and that the
debt still grows."* · `ALREADY DISCONNECTED` *"Leads with what it takes to restore, and
the reconnection fee, before anything else."*
**COMPONENTS** — `PortalFrame · Callout danger · ArrearsBreakdown · Button · Callout warn`

---

## Screen 42 · Ask for a payment plan · `/:tenant/portal/ask-for-a-plan` → `/plan-offer`
*EXISTS BEHIND · NO COMMITMENT*

**The question:** *"I cannot pay $247.30 this month — can I pay it over time, and will
you still cut me off?"*

### PHONE · 390, in order
```
← Past due
Ask for a payment plan
Spread what you owe over several months
What you owe                      $247.30
How many months?
  ( ) 3 months                $82.44 a month
  ( ) 6 months                $41.22 a month
  ( ) 12 months               $20.61 a month
No interest and no fee, on any of these.
While the plan runs
Your service is not disconnected as long as you keep to it, and you pay your new
bills as usual.
Ask for 3 months
Most plans are approved straight away.
```

### DESKTOP · 1280, in order
```
← Past due
Ask for a payment plan
What you owe today                $247.30
Choose how long
  ( ) 3 months — paid off by Nov 2026    $82.44 a month
  ( ) 6 months — paid off by Feb 2027    $41.22 a month
  ( ) 12 months — paid off by Aug 2027   $20.61 a month
First payment            Sep 1, 2026
No interest, no fee, on any length.
Ask for this plan
WHILE THE PLAN RUNS
  · Your service is not disconnected
  · No late fee is added to the planned amount
  · You pay your new monthly bills as normal, on top
IF YOU MISS ONE
We contact you before anything else happens. A missed payment does not cancel the
plan automatically — talk to us first.
THERE MAY BE HELP TOO
You might qualify for energy assistance, which pays part of the bill outright.
See help paying →
```

**FOR** — *"Giving a customer who cannot pay a way to stay connected, in one screen,
without phoning."*
**HOW YOU GET HERE** — *"Past due, Help paying and Home — three doors, the most of any
screen in this group, which is right for the thing a struggling customer most needs."*
**COGNITIVE LOAD** — *"Each option shows the monthly figure and the finish date — no
division, no calendar arithmetic. '$41.22 a month, paid off by Feb 2027' is one
decision, not two."*
**THE CRITICAL PANEL** — *"Whether service is protected during the plan is the question
behind the request. **It is answered beside the choice, not after submitting.**"*
**CROSS-LINK** — *"Assistance is offered here, because a customer asking for a plan is
exactly the one who may qualify for a grant — and most do not know it exists."*
**WORDS** — *"'Payment plan' and 'payment arrangement' both appear at least once,
because different utilities taught customers different names for the same thing."*
**STATES** — `APPROVED INSTANTLY` · `NEEDS REVIEW` (*"We will reply within one working
day"* — *"and protections hold in the meantime, stated"*) · `ALREADY ON A PLAN`
(*"Shows the existing one instead of taking a second"*) · `NOT ELIGIBLE` (*"Names why,
and offers the phone number — never a bare refusal to someone in difficulty"*)
**COMPONENTS** — `PortalFrame · RadioCard · Callout ok · Button`

⚠ **B14 rule 38 applies here and is stated rather than assumed.** *How* this form is
built — side-by-side fields, where the helper sits, the footer's button order — is our
UI rules' to decide (now **B14 rule 39**). *What the form contains* — a bounded choice
of terms, each showing its monthly figure and its finish date, with the protection
panel beside the choice — is the drawing's, and is quoted above.

---

## Screen 43 · The plan we can offer · `/:tenant/portal/plan-offer`
*NEW BUILD · COMMITMENT CPB-03 · COMMITMENT CPB-21*

**The question:** *"I asked for a plan — what are you actually offering, and do I have
to take it? The moment between the request and the agreement."*

### PHONE · 390, in order
```
← Payments
We can offer you this
For the $247.30 that is past due
6 MONTHS
$41.22
a month, from Sep 1 · paid off Feb 2027
WHAT YOU AGREE TO
  Pay $41.22 on the 1st, six times
  Pay your normal bills as usual
  No interest, no fee            $0.00
What we agree to
Your service stays on and no late fee is added, as long as you keep to it.
Accept this plan
Ask for different terms
This offer holds until Aug 27.
```

### DESKTOP · 1280, in order
```
← Payments
We can offer you this plan
For the $247.30 past due on account 4417-0114
THE SCHEDULE
  1 · Sep 1, 2026   $41.22
  2 · Oct 1, 2026   $41.22
  3 · Nov 1, 2026   $41.22
  4 · Dec 1, 2026   $41.22
  5 · Jan 1, 2027   $41.22
  6 · Feb 1, 2027   $41.20
  Total             $247.30 — no interest, no fee
ON TOP OF THIS, YOUR NORMAL BILLS CONTINUE
A typical month is about $180. So from September you would be paying roughly $221
a month in total until February.
WHILE YOU KEEP TO IT
  · Your service is not disconnected
  · No late fee on the planned amount
  · Pay your normal bills as usual
  · The shut-off notice dated Aug 27 is cancelled
Accept this plan
Ask for different terms
This offer holds until Aug 27, 2026.
Accepting is not a credit agreement and is not reported to anyone.
THERE MAY BE HELP AS WELL
A plan and energy assistance can run together — assistance may cover part of the
$247.30 outright.
→ See help paying
```

**FOR** — *"Turning a request into an agreement, with both sides' obligations on one
screen."*
**HOW YOU GET HERE** — *"Payments — one of the seven errand cards. Not from Past due,
which is where somebody who has just asked for a plan would look for the answer."*
**WHY IT IS ITS OWN SCREEN** — *"Asking and agreeing are different acts. The offer may
not match the request — a utility may counter with six months where twelve was asked —
and the customer must be able to see and decline it."*
**THE TOTAL BURDEN** — *"'Roughly $221 a month in total until February' is the number
that decides whether somebody can keep the plan. Showing the instalment alone sets
people up to fail in month two."*
**DIGNITY** — *"Says explicitly that this is not a credit agreement and is not reported.
That fear stops people accepting plans they can afford."*
**STATES** — `COUNTER-OFFER` · `EXPIRED` (*"Says the offer lapsed and re-offers, rather
than dead-ending someone in difficulty"*) · `DECLINED` (*"Returns to the past-due screen
with assistance still offered"*) · `ACCEPTED`
**COMPONENTS** — `PortalFrame · InstalmentList · Callout ok · Button`

---

## Screen 44 · Your plan · `/:tenant/portal/plan`
*NEW BUILD · COMMITMENT CPB-21*

**The question:** *"where am I up to, what is next, and am I still protected?"*

### PHONE · 390, in order
```
← Payments
Your payment plan
NEXT PAYMENT
$82.44
Due Oct 1, 2026 · 2 of 3
Pay $82.44 now
WHERE YOU ARE
  1 · Sep 1   $82.44   PAID
  2 · Oct 1   $82.44   DUE NEXT
  3 · Nov 1   $82.42
Left to pay                $164.86
You are protected. Service stays on while you keep to the plan.
Your normal monthly bills are separate and still due.
```

### DESKTOP · 1280, in order
```
← Payments
Your payment plan
3 months, agreed Aug 20, 2026 · $247.30 total
THE SCHEDULE
  1 · Sep 1, 2026   $82.44   PAID SEP 1
  2 · Oct 1, 2026   $82.44   DUE NEXT
  3 · Nov 1, 2026   $82.42
Paid so far          $82.44 of $247.30
Left to pay          $164.86
NEXT PAYMENT
$82.44
Due Oct 1, 2026 · in 18 days
Pay $82.44 now
Pay the whole $164.86
YOU ARE PROTECTED
Service stays on and no late fee is added, as long as you keep to the plan.
Your ordinary monthly bills are separate from this plan and are still due on their
own dates.
```

**FOR** — *"Showing a customer mid-plan exactly where they stand, so they never have to
phone to ask."*
**HOW YOU GET HERE** — *"Payments — one of the seven errand cards. That is the only door."*
**COGNITIVE LOAD** — *"Paid, due next and still to come are three visibly different
states. **'Left to pay' is computed for them.** Paying the balance off early is offered —
people in a plan often can, later."*
**THE SEPARATION** — *"That ordinary bills continue alongside the plan is the single most
misunderstood thing about payment plans, so it is stated on the screen rather than in
the agreement."*
**STATES** — `ON TRACK` (green) · `MISSED ONE` (*"Amber, not red: says what to do and by
when, and that protection continues until then"*) · `BROKEN` · `FINISHED` (*"Paid off
Nov 1 — nothing more is owed on this plan." A visible ending.*)
**COMPONENTS** — `PortalFrame · InstalmentList · StatusChip · Callout ok`

---

## Screen 45 · Help paying · `/:tenant/portal/help-paying`
*EXISTS BEHIND · NO COMMITMENT*

**The question:** *"is there money available, do I qualify, and how do I get it? Most
customers do not know these programmes exist."*

### PHONE · 390, in order
```
← Past due
Help paying your bill
Grants, discounts and one-off help
ENERGY ASSISTANCE
A federal grant that pays part of your bill. Most households under $3,660 a month
qualify.
Typical award                $300–$600
Check if you qualify
SENIOR DISCOUNT
15% off every bill if you are 65 or over.
→ Apply — proof of age needed once a year
LOW-INCOME CREDIT
$25.00 off every month if you are on a qualifying programme.
→ Apply — your agency confirms it for you
ONE-OFF EMERGENCY HELP
Local charities can help with a shut-off notice.
→ Find help near you
Applications open            Oct 1 – Mar 31
Check if you qualify
```

### DESKTOP · 1280, in order
```
← Past due
Help paying your bill
You may qualify for more than one of these at the same time.
ENERGY ASSISTANCE — THE BIGGEST ONE
A federal grant paid straight to us against your bill. It is not a loan and is not
repaid.
  Typical award              $300 – $600
  Household income limit     $3,660 a month for 4
SENIOR DISCOUNT · 15% OFF EVERY BILL
You are 65 or over. Proof once a year.
→ Apply
LOW-INCOME CREDIT · $25.00 A MONTH
If you are on a qualifying programme — your agency confirms it, you send nothing.
→ Apply
MEDICAL CERTIFICATE
Protects you from disconnection if someone at home relies on medical equipment.
→ Apply
ONE-OFF EMERGENCY HELP
Local charities and churches help with a shut-off notice.
→ Find help near you
```

**FOR** — *"Making assistance findable. In most utilities take-up is a fraction of
eligibility, and the commonest reason is that customers never learn the programmes
exist."*
**HOW YOU GET HERE** — *"Past due and Bills."*
**PRIMARY ACTION** — *"`Check if you qualify` on the largest programme. The rest are
quieter — but all are on one screen, because someone who qualifies for one usually
qualifies for several."*
**COGNITIVE LOAD** — *"Each programme states the amount and the qualifying test up
front. 'Most households under $3,660 a month' lets someone self-assess in two seconds
instead of starting an application to find out."*
**DIGNITY** — *"No language implying charity or failure. The grant is described as what
it is: money that exists, paid against the bill, not repaid."*
**STATES** — `ALREADY RECEIVING` · `APPLICATION OPEN` · `SEASON CLOSED` (*"Says when it
opens again rather than hiding the programme"*) · `NONE CONFIGURED` (*"Falls back to the
utility's own phone number — never an empty screen for someone in difficulty"*)
**RULES** — *"Every programme is tenant-configured; nothing here is hard-coded. Figures
come from the utility's own settings."*
**COMPONENTS** — `PortalFrame · ProgrammeCard · Button`

---

## Screen 46 · Your protections · `/:tenant/portal/protections`
*EXISTS BEHIND · NO COMMITMENT*

**The question:** *"can they actually cut me off right now? A customer who is
frightened needs the rules stated plainly and applied to their own situation."*

### PHONE · 390, in order
```
← Past due
Your protections
RIGHT NOW
You are protected until Mar 31, 2027.
Winter rules stop disconnection between Nov 1 and Mar 31.
The amount you owe still grows during this time.
WHAT PROTECTS YOU
  ❄  Winter, Nov 1 – Mar 31              APPLIES
  🏥  Medical equipment at home           → Apply
  ⚑  Active military service             → Apply
  📋  A payment plan you keep to          → Ask for one
  ⚖  An open dispute                     On the disputed part only
BEFORE ANY SHUT-OFF
  · A written notice, at least 10 days ahead
  · A phone call or a visit
  · Never on a Friday, a weekend or a public holiday
```

### DESKTOP · 1280, in order
```
← Past due
Your protections
WHERE YOU STAND RIGHT NOW
You cannot be disconnected until Mar 31, 2027. Texas winter rules stop
disconnection between Nov 1 and Mar 31 for customers who have asked for a payment
plan.
What you owe still grows during this time, and is due when the protection ends. A
plan is still the better route.
EVERY PROTECTION, AND WHETHER IT APPLIES TO YOU
  ❄  Winter moratorium · Nov 1 – Mar 31                    APPLIES TO YOU
  🏥  Medical equipment at home · renewed yearly            → Apply — a doctor's note
  ⚑  Active military service · while deployed              → Apply — service papers
  📋  A payment plan you are keeping to                     → Ask for one
  ⚖  An open dispute · the disputed amount only            Not currently open
  ☀  Extreme weather · declared heat or cold days          Automatic, no application
WHAT MUST HAPPEN BEFORE ANY SHUT-OFF
  1 · A written notice, at least 10 days beforehand
  2 · A phone call or a visit to the property
  3 · Never on a Friday, a weekend, or the day before a public holiday
  4 · Never while any application above is being decided
These are the rules your utility follows. If you think one was missed, tell us.
Something went wrong — tell us
```

**FOR** — *"Answering 'can they cut me off' with the customer's own situation, not a
policy document."*
**HOW YOU GET HERE** — *"Past due — the only door, so this screen is two clicks behind
one that Home does not link to."*
**COGNITIVE LOAD** — *"The verdict comes first, with its date. The full list is
underneath, each row marked applies / can apply / does not — so nobody has to read a
rulebook and work out which paragraph is theirs."*
**HONESTY** — *"'The amount you owe still grows during this time' is stated, because a
protection read as forgiveness produces a much worse spring."*
**STATES** — `PROTECTED` · `NOT PROTECTED` (*"Neutral, not alarming: says which could
apply and links each application"*) · `APPLICATION PENDING` · `EXPIRING` (*"Warns 30
days before a protection ends, with what happens then"*)
**RULES** — *"Rules vary by state and by utility, so every row is configured, never
hard-coded. **Icons always carry their words.**"*
**COMPONENTS** — `PortalFrame · Callout ok · ProtectionRow · StatusChip`

---

## Screen 47 · Budget billing · `/:tenant/portal/level-pay`
*NEW BUILD · COMMITMENT CPB-18*

**The question:** *"can I pay the same amount every month instead of a $92 bill in
March and a $229 one in July? And what happens to the difference?"*

### PHONE · 390, in order
```
← Help paying
Budget billing
The same amount every month, all year
YOU WOULD PAY
$171.40
every month, instead of $142 to $229
YOUR LAST 12 BILLS
The flat line is your budget amount.
THE HONEST PART
This spreads your bills — it does not lower them. Each summer we check, and if you
have paid too little or too much we settle up over the next year.
Start budget billing
You can stop at any time. Any difference is settled then.
```

### DESKTOP · 1280, in order
```
← Help paying
Budget billing
YOUR LAST 12 BILLS, AGAINST THE BUDGET AMOUNT
  Your lowest       $142.10
  Budget amount     $171.40
  Your highest      $228.75
  A year costs    $2,056.80
YOU WOULD PAY
$171.40
every month, starting with your September bill
Start budget billing
You can stop at any time.
HOW THE SETTLE-UP WORKS
  Every August we compare what you paid with what you used   once a year
  Paid too little — the shortfall is spread over the next 12 months   no interest
  Paid too much — it comes off your next bills   or refunded
  Your monthly amount is recalculated each August   we tell you first
THIS SPREADS, IT DOES NOT REDUCE
Over a year you pay the same total. What changes is that no single month is a shock.
```

**FOR** — *"Turning an unpredictable bill into a predictable one, without misleading
anyone into thinking it is cheaper."*
**HOW YOU GET HERE** — *"Help paying — **the only door**, and this is the finding worth
acting on: budget billing is a mainstream product for anyone with a lumpy bill, and it
is reachable only through a screen about hardship."*
**COGNITIVE LOAD** — *"The customer's own twelve bills are the argument. No hypothetical
example, no generic explanation — their real range, their real average, their real
annual total."*
**HONESTY** — *"'This spreads your bills — it does not lower them' is on the screen,
above the button."*
**WORDS** — *"'Budget billing' — what North American utilities call it. **'Level pay' is
the internal name and never appears.**"*
**STATES** — `ALREADY ON IT` · `NOT ENOUGH HISTORY` (*"We need about a year of bills to
work out a fair amount." Says when they will qualify.*) · `NOT ELIGIBLE` (*"Names the
reason — a past-due balance, usually — and links to the payment plan instead of
dead-ending"*) · `SETTLE-UP DUE`
**COMPONENTS** — `PortalFrame · BillHistoryBars · AmountCard · Button`

---

## Screen 48 · Where your budget billing stands · `/:tenant/portal/level-pay/standing`
*NEW BUILD · COMMITMENT CPB-18*

**The question:** *"I pay $171.40 every month — am I ahead or behind on what I have
actually used, and what happens in August?"*

### PHONE · 390, in order
```
← Budget billing
Where you stand
7 months into your budget year
YOU HAVE USED MORE THAN YOU HAVE PAID
$142.60
behind, so far
THE YEAR SO FAR
  Paid · 7 × $171.40      $1,199.80
  Actually used           $1,342.40
  Difference                $142.60
WHAT HAPPENS IN AUGUST
We work out the year, and spread anything owed over the next 12 months. On today's
figures that would add about $11.88 a month.
Your new monthly amount would be around $183.28.
Pay the $142.60 now instead
```

### DESKTOP · 1280, in order
```
← Budget billing
Where your budget billing stands
Budget year Sep 2025 – Aug 2026 · month 7 of 12 · $171.40 a month
PAID AGAINST USED, MONTH BY MONTH
  Paid so far     $1,199.80
  Used so far     $1,342.40
  Behind by         $142.60
  Months left              5
The flat line is what you pay. The bars are what you actually used.
WHY YOU ARE BEHIND
Your budget amount was worked out from last year. This summer has been hotter, so
June and July used more than the same months last year — $88.20 more between them.
BEHIND BY $142.60
Nothing is owed today. In August 2026 we settle the year and spread anything
outstanding over the next 12 months.
  That would add about        $11.88 a month
  New monthly amount          around $183.28
OR CLEAR IT NOW
Paying the $142.60 before August keeps next year's amount closer to today's.
Pay $142.60
Leaving budget billing settles the difference straight away.
→ Stop budget billing
```

**FOR** — *"The single biggest source of budget-billing complaints is the settle-up
arriving unexplained. This screen makes it visible every month instead of once a year."*
**HOW YOU GET HERE** — *"Budget billing, from two places on that screen."*
**COGNITIVE LOAD** — *"Behind or ahead is the headline. The consequence is computed —
'$11.88 a month, new amount around $183.28' — rather than leaving somebody to divide
$142.60 by twelve."*
**WHY YOU ARE BEHIND** — *"Attribution, not just arithmetic. 'June and July used $88.20
more than the same months last year' is actionable; 'you are behind' is not."*
**STATES** — `AHEAD` · `LEVEL` (*"You are within $12 of where you should be." Not an
empty screen.*) · `JUST STARTED` (*"Too early to say — we need three months." With the
review date.*) · `REVIEW DUE`
**COMPONENTS** — `PortalFrame · StandingChart · Callout warn · Button`

---

## Screen 49 · Money back · `/:tenant/portal/money-back`
*EXISTS BEHIND · NO COMMITMENT*

**The question:** *"my account is in credit — can I have it back, or does it just sit
there?"*

### PHONE · 390, in order
```
← Payments
Money back
YOU ARE IN CREDIT
$84.20
from your budget billing settle-up, Aug 5
WHAT WOULD YOU LIKE?
  ( ) Leave it on the account      Comes off your next bills
  ( ) Send it back to me           To bank ····4417, 5–7 days
Send me $84.20
Either way the money is yours. Leaving it on simply means smaller bills for a while.
```

### DESKTOP · 1280, in order
```
← Payments
Money back
WHERE THE CREDIT CAME FROM
  Budget billing settle-up · Aug 5, 2026        $71.40
  Overpayment on your July bill · Jul 19        $12.80
  Total credit                                  $84.20
What would you like to do?
  ( ) Leave it on the account — it comes off your next bills automatically
  ( ) Send it back to bank account ····4417 — arrives in 5 to 7 working days
Send me $84.20
YOUR CREDIT
$84.20
Enough to cover about half of a typical bill.
Either choice keeps the money yours. If you leave it here, your next bill is $84.20
smaller and we tell you so on it.
```

**FOR** — *"Telling a customer they have money owed to them, and letting them choose
what happens to it — instead of the credit sitting silently."*
**HOW YOU GET HERE** — *"Payments — one of the seven errand cards. That is the only door."*
**COGNITIVE LOAD** — *"Where the credit came from is itemised, because an unexplained
credit is as unsettling as an unexplained charge. Both options say what actually
happens next, with a timescale."*
**WORDS** — *"'Money back', not 'Credit balance refund'. 'You are in credit', not 'Your
account carries a credit balance'."*
**STATES** — `NO CREDIT` (*"There is nothing owed back to you at the moment." Says what
would create one.*) · `REFUND IN PROGRESS` · `BLOCKED` (*"Past-due amount elsewhere: says
the credit is offsetting it, and by how much"*) · `CLOSING ACCOUNT` (*"The final credit
is refunded automatically; the screen says so and no choice is offered"*)
**COMPONENTS** — `PortalFrame · Callout ok · CreditBreakdown · RadioCard`

---

## Screen 08 · Prices and fees · `/:tenant/portal/fees`
*NEW BUILD · COMMITMENT CPB-01 · COMMITMENT CPB-23*
*"**No door named.** This screen carries no `How you get here` row, though the
document's own rule E says every screen does. It is one of 37. See `CPB-23`."*

**The question:** *"what was this $45 for, and what else can you charge me? Published
prices, before they appear on a bill."*

### PHONE · 390, in order
```
← Help
Prices and fees
In force from Aug 1, 2026
💧 WATER · WHAT YOU USE
  First 5 kgal            $4.24 / kgal
  5 – 15 kgal             $6.89 / kgal
  Over 15 kgal            $8.48 / kgal
  Monthly base charge        $8.00
🚿 SEWER
  90% of the water you use   $5.00 / kgal
ONE-OFF FEES
  Connection                $45.00
  Reconnection              $45.00
  Returned payment          $30.00
  Card convenience fee       $2.95
  Paper bill          $2.00 / month
  Late payment    1.5%, at least $5.00
Bank payments are free. Paperless removes the $2.00.
```

### DESKTOP · 1280, in order
```
← Help
Prices and fees
In force from Aug 1, 2026 · approved by the city council · these are the prices on
your bill
💧 WATER
  First 5 thousand gallons                        $4.2400 per kgal
  Next 10 — 5 to 15 thousand gallons              $6.8900 per kgal
  Everything above 15 thousand gallons            $8.4800 per kgal
  Monthly base charge · 5/8 inch meter                    $8.00
Inclining tiers: the more you use, the more the next gallon costs.
🚿 SEWER
  Charged on 90% of the water you use             $5.0000 per kgal
  Monthly base charge                                     $9.00
🔥 FIRE LINE · SPRINKLER SUPPLY
  2 inch                                          $12.00 a month
  6 inch                                          $60.00 a month
Charged per line, by its size.
ONE-OFF AND MONTHLY FEES
  Connection $45.00 · Disconnection $45.00 · Reconnection $45.00 ·
  Seasonal turn-off or turn-on $25.00 · Move-out final read $20.00 ·
  Meter re-read, if you ask $20.00 · Meter accuracy test $25.00 ·
  Returned payment $30.00 · Card convenience fee $2.95 a payment ·
  Paper bill $2.00 a month · Late payment 1.5% of what is overdue, at least $5.00
FEES YOU CAN AVOID
Paying from a bank account is free. Going paperless removes the $2.00. Autopay
means no late fee.
```

**FOR** — *"Publishing what the utility charges, so a fee on a bill is never the first
time a customer sees it."*
**COGNITIVE LOAD** — *"Grouped as usage prices, then one-off fees, then a panel naming
the fees a customer can avoid — which is the only part most people act on."*
**MONEY** — *"Unit prices carry four decimals because that is what makes a bill line add
up; totals and flat fees carry two."*
**STATES** — `A CHANGE IS COMING` · `HISTORIC` · `NOT PUBLISHED` (*"The utility has not
turned this page on: the phone number, not an empty page"*) · `DIFFERENT BY SIZE`
**RULES** — *"Every figure comes from the utility's live rate schedules and charge
codes — nothing on this page is typed by hand, so it cannot disagree with a bill."*
**COMPONENTS** — `PortalFrame · PriceBlock · Callout ok`

⚠ **THE FIRE-LINE BLOCK IS THE ONLY PLACE IN SECTION 02 THAT TOUCHES `CR-063`.** It
draws two of the six seeded sizes at `$12.00` and `$60.00` a month, *"Charged per
line, by its size"* — which is `CLAUDE.md`'s *"the size class picks the price and the
COUNT multiplies it"*, drawn correctly, and it carries **no private hydrant**, which
is the `2026-09-03` removal already reflected. Nothing here asks for a change.

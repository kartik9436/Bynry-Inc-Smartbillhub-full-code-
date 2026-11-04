# 09 · Move-out wizard · standalone EXISTS BEHIND

**Source:** `accounts-blueprint.pdf`, pages 107–111. Extracted text, verbatim — **derived, do not edit.**

**14,126 characters over 5 page(s).**

⚠ **The blueprint prints this entry on the same page as 10 · Close-out EXISTS BEHIND NO COMMITMENT**, so the text below covers all of them. Read the heading you want.


---

```
How you get here The S21 Move-out button (AccountDetailPage.tsx:713), guarded so only an account that currently holds its unit can use it.
Primary action Complete move-out ✓ — one commit, not the design's two buttons, whose answer carries both exits as links so the chain survives.
Write surfaces Update POST /accounts/{id}/move-out, plus /settle-shortfall, /refund and /hold-excess. Reads GET /accounts/{id}/close-impact for step 5.
Walked Not walked.
Notable Step 5 draws nine consequence panels — premises, unit, assets, deposit, open bills, sub-accounts, payments, plan, collections — and each says whether it is derived,
explicitly served, or not served at all. This is UI-RULES 11 honoured about as thoroughly as it gets in this product.
Rules BR-CUS-025 · 030 · 031 · 056 · 081 · 082 · 096 · 1040 · BR-SHL-046
09 Move-out wizard · standalone EXISTS BEHIND
/:tenant/move-outs/new  — the same MoveOutWizard as screen 08, entered with no account chosen
What it is A second address. Step 1 becomes a real Find account search rather than a confirmation.
How you get here Four doors, mirroring move-in: header (AccountsListPage.tsx:1212), tab primary (:984), empty CTA (MoveOutsTab.tsx:769), parked Resume.
Walked Not walked.
10 Close-out EXISTS BEHIND NO COMMITMENT
/:tenant/accounts/:accountId/close-out  ·  no screen id  ·  the act, what it does, and the account after it
The question: "We cut this one in August and they never came back. Finish it — and
don't let me pretend the debt went away."
The act that ends an account whose supply was cut — and the one date in
this product that no correction can un-say. Ruled 2026-08-27, verbatim and in
full: "A disconnected customer can never be closed - Add a separate close-out act
— Cleaner in the record". The reasoning is part of the ruling: relaxing the
move-out door to admit a cut customer would file a disconnection AS a move-
out in a permanent record, and to a regulator those are not the same event. So
the two doors refuse each other in both directions, and this one writes the cut
date rather than the day the clerk pressed it — which on this account is the
difference between a unit being re-lettable on 08/19 and being refused for 43
days.
All 3 screens of this flow, drawn at 1280 and buildable as drawn. Real app
shell, real stepper, real field labels in the order the component renders them. A
SO Sam Ortiz
Billing Clerk
dashed block is a stated absence; a required field carries its asterisk (UI-RULES
10).
/brazosbend/accounts/a-11488/close-out
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
Account A-11488 / Close out account ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Account A-11488
CLOSE OUT ACCOUNT
Close out this account
A-11488 · Okafor, D. · cut on 08/18/2026
Save & exit
The account you are closing
Account number A-11488
Customer Okafor, D.
Customer number C-00318
Category Residential · Standard
Status now Disconnected · non-billable
Service address 77 Rio Grande, Silver Creek, TX 78611
Unit U-001207 · Unit 2
Services Electric · Water
Opened 06/03/2021
Disconnected is not closed, and that is why this screen exists. A cut leaves the account OPEN: it still owes
money, the customer can still pay it, and the supply can still be restored.
What was cut, and when
Disconnect case DSC-26-0114
Reason Non-payment
Services cut Electric · Water
Cut on 08/18/2026
Final metered bill $23.23 · 18 days of 31
Base charges since None — they stop at the cut
Balance $612.75 · unchanged since the cut
The final bill was raised at the cut, not today. Eighteen days of a $40.00 month is $23.23, and after the cut the balance
does not move except when they pay, when a correction is posted, or if service comes back.
What you are recording
Closing this account out on *
09/30/2026 📅
Today, or the day the decision was actually made.
Why *
Cut 08/18, no contact in six weeks, tenancy ended
and the landlord has re-let.
A sentence, in your own words.
Status it takes
Closed ▼
A terminal status.
A LIST OF REASONS TO PICK FROM
What pressing this writes
WHAT VALUE WHY THAT
The date the account
closed
08/18/2026 The CUT date — not
today
The account’s status Closed Terminal at last
Every open service
agreement
Ends
08/18/2026
The same day service
actually stopped
The disconnect case Closed out With today’s date and
your name on it
The record of the act One row Closed out, never closed
The date on the record is the CUT date, and getting that wrong costs
six weeks of an empty unit. Service ended on 08/18. If today’s date went on
the record instead, the next customer could not legally start before 10/01 — so
every one of the 43 days from 08/19 to 09/30 would be refused on a property
this utility was entitled to re-let the whole time.
Both dates are kept, on purpose. The record reads: service ended on the cut
date, and the account was closed out on this later day, by this person.
What it will not do
Take a final read No — the meter was read, or not, at the cut
Settle the deposit No — that is the payments side
Decide where the debt goes No — see the next screen
Write a move-out record No — this was not a move
Clear the balance No — $612.75 survives it
Nothing here is filed as a move-out, and that is the point of the whole act. A
customer whose supply was cut did not move out, and a permanent record saying
they did is not something a correction can un-say.
NOTHING HAS BEEN CHECKED FOR YOU
This act does not look up an active payment plan, an open dispute or an
unbilled cycle, and
IT IS NOT TELLING YOU THEY ARE CLEAR
. Whether any of the three should stop a terminal act or merely warn has never
been decided, and refusing on a blocker nobody agreed to would leave a dead
end with no way past it.
When it refuses
IF WHAT YOU ARE TOLD
Theaccountis Thisaccountisalreadyclosed.Correctinga
Close out this account · /brazosbend/accounts/a-11488/close-out · The act, what it writes, and the six ways it refuses
v2.234.15
SO
Sam Ortiz
Billing Clerk
There is none, and the sentence above is what gets recorded. Nothing in this product counts closures by reason, so how
many did we close as written off last year has no answer.
The account is
already closed
This account is already closed. Correcting a
close-out means a new record.
They still live there This customer still occupies the unit, so use
Move-out instead.
The supply was
never cut
Only an account whose service was cut can be
closed out.
Your date is
before the cut
The close-out date cannot be earlier than the cut
date.
You left the date
empty
Enter the date you are closing this account out.
You left the
reason empty
Say why this account is being closed out.
The second one is the door working, not failing. Somebody who still lives there
is a move-out; sending them through here would file a departure as a disconnection,
which is the same falsification as the other way round.
←  Back to the account Record the close-out
/brazosbend/accounts/a-11488/close-out?confirm=1
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
Account A-11488 / Close out account ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Account A-11488
CLOSE OUT ACCOUNT
What closing this account does
Read this before you press it · nothing has happened yet
Save & exit
The moment you press it
WHEN WHAT
Now The account becomes Closed and stops being billable
Now Its closing date is written as 08/18/2026, the cut day
Now Every service agreement on it ends on that same day
Now The disconnect case is marked closed out, with your name
Now The unit is free for somebody else from 08/19/2026
Now One record of the act — closed out, not closed
Now A fresh collections case opens at tier 1
The account, afterwards
Status Closed · terminal
Closed on 08/18/2026 · the cut date
Closed out on 09/30/2026 by S. Ortiz
Billed again Never
$6 2 h d
The money, and who chases it now
What is left
Balance at the cut $612.75
Paid since $0.00
Written off by this act $0.00
Still owed after closing $612.75
A new case opens Tier 1 · the first reminder
Against This account itself
Kind of ladder Collections — letters only
Can it reach a cut No
Deposit applied — not by this act
A closed account cannot be escalated to a disconnection, because
there is nothing left to disconnect. So the ladder that restarts is a
collections one: reminders, and then whatever this utility does about a debt it
cannot cut for.
Closing an account is not writing off what it owes. The balance survives the
What closing it does · /brazosbend/accounts/a-11488/close-out?confirm=1 · The account, the unit, the 43 days and the debt that outlives all three
v2.234.15
SO
Sam Ortiz
Billing Clerk
Balance $612.75 · unchanged
Can they still pay it Yes
Can it be reopened No — a correction is a new record
Closing is the one act no correction can un-say. Everything else in this product is fixed by writing a new row.
The unit
Released At the cut, 08/18/2026
Vacant since 08/19/2026
Earliest a move-in may start 08/19/2026
Days it has stood empty 43, to 09/30/2026
Owner billed while vacant Per the premises’ own setting
Those 43 days are why the cut date goes on the record. The utility could have re-let this property from the 19th of August.
closure untouched, and somebody is still asking for it the following week.
And who it is NOT chased from
Tied back to a master account No
The landlord Not written to, not asked
Where that is decided The move-out wizard, by a clerk
A residue nobody tied back does not become the landlord’s problem, and
therefore does not become the landlord’s letters. Moving a departing tenant’s
debt onto the owner of the building is a deliberate act with a name recorded against
it, and this screen does not collect that consent — so it must not have that effect.
What the customer receives
MESSAGE WHEN EXISTS?
That the account is closed On closing No
template
A final statement of what is
owed
On closing No
template
The tier-1 reminder With the new
ladder
Yes
So the first thing they hear about their account being closed is a
demand for $612.75. Nothing announces the closure itself — there is no
template for it and none for a closing statement. The only letter this produces is
the one asking for money.
WHAT A REGULATOR WOULD ASK FOR
Closures cannot be counted by reason, because the reason is a sentence
somebody typed. How many accounts did we close with a balance, and how
much did we write off is not a question this product can answer for any period.
←  Back Yes — close it out
/brazosbend/accounts/a-11488?tab=overview
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Accounts / Okafor, D. ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
←  Accounts
ACCOUNT A-11488  ·  CUSTOMER — OKAFOR, D.
Okafor, D.
Closed Not billable Residential · Standard Owes $612.75
In collections · tier 1
⌂ 77 Rio Grande · Unit 2  ·  Silver Creek, TX 78611  ·  Closed
08/18/2026
Record payment
What this account is now
Status Closed · terminal
Behaviour class Not billable
What a clerk can still do
ACTION LIVE? WHY
Record a payment Yes A payment is always accepted,
 h t th t t
Adjust
Move-out
Activate account
Move-in
Close out
The account afterwards · /brazosbend/accounts/a-11488?tab=overview · Closed, still owed, and every control that is off saying why
How you get here One door: the S21 Close out secondary (AccountDetailPage.tsx:738), live only on a cut, non-occupying, non-closed account.
Work
Finance
Runbooks
Reports
Settings
v2.234.15
SO
Sam Ortiz
Billing Clerk
✦
▩
▦
▤
⚙
Closed on 08/18/2026 · the day service was cut
Closed out on 09/30/2026 by S. Ortiz
Why Cut 08/18, no contact in six weeks, tenancy ended and the landlord has re-let.
Disconnect case DSC-26-0114 · closed out
Service agreements Both ended 08/18/2026
Last bill $23.23 · 08/18/2026
Next bill None — ever
Two dates, and they answer different questions.Closed on is when the customer stopped having service.
The money
Still owed
Balance $612.75
Deposit on file $0.00
Written off $0.00
Being chased $612.75
Collections case COL-26-0141 · opened 09/30/2026
Tier 1 of 3 · first reminder
Sequence Collections — letters only
Escalates to a cut No
Tied back to a master No
Closed, and still being chased. The two are not in conflict: closing ends the SERVICE relationship and settles nothing.
whatever the status
Write it off Yes With a supervisor and a reason —
a separate act
Read the bills, reads
and notes
Yes The whole history stays readable
for ever
Adjust the balance No Nothing left to adjust
Move them out No Already closed
Reopen it No A correction is a new record,
never an edit
Reconnect the supply No That was possible while it was
only disconnected
Every control that is off says why, on hover, instead of vanishing. A button
that disappears teaches a clerk nothing; one that is greyed out with a sentence on it
answers the question they were about to ring somebody about.
The last row is the one that changed at closing. While the account was
merely disconnected, paying the arrears and the reconnection fee would have
brought the supply back.
The unit they left
Unit U-001207 · Unit 2
Premises 77 Rio Grande · PR-0611
Occupied by Nobody
Vacant since 08/19/2026
A move-in may start On or after 08/19/2026
This account’s claim on it Ended at the cut
The unit was free from the day after the cut, not from the day the paperwork
was done. That is the whole reason the closing date is the cut date, and it is visible
here as the one place a clerk would notice if it were wrong.
What is still open elsewhere
WHAT REFERENCE STATE
Collections COL-26-0141 Tier 1
Disconnect case DSC-26-0114 Closed out
Complaints — none —
Service requests — none —
A DEPOSIT TO RETURN, OR TO APPLY
This account holds none. Where one is held, closing does not touch it — the
refund leg belongs to payments and is a different act on a different screen, so a
closed account with a deposit still on it is a thing somebody has to go and
finish.
```

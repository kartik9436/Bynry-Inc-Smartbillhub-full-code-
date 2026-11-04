# CR-085 · step 1 · lane 6 — PAYING · THE DRAWING, QUOTED

**Source:** `05-prototype/SMARTBillHub Customer Portal Blueprint.pdf`, **section 06
"Paying"** (pages 64–72) plus the two guest payment screens in section 02 (pages
13–17), read with `10-scripts/pdf/pdf_text.py`. Every label below is transcribed
from that text layer, in the order it renders, ⚠ **verbatim — not summarised**.
Where the extractor joined two words (`as` for a thin space, `tenantportalpay` for
a slashed route) the join is expanded and marked.

**Read this file before the delta file beside it.** The delta is only meaningful
against a drawing somebody can actually read; a link would get skimmed.

---

## 0 · WHICH SCREEN IS AT WHICH ADDRESS — READ THIS FIRST

⚠ **THE BLUEPRINT AND THE ROUTER DISAGREE ABOUT `/pay` AND `/pay-now`, AND THEY
ARE EXACTLY SWAPPED.**

| Blueprint says | Router actually mounts (`portalRoutes.tsx` · `screenIds.ts`) |
|---|---|
| screen **06** *Pay without signing in* at `/:tenant/portal/pay-now` | `/pay-now` = **`CWP-038` Pay now**, the SIGNED-IN screen |
| screen **07** *Your payment · without an account · done* at `/:tenant/portal/pay-now` | — |
| screen **35** *Pay now* at `/:tenant/portal/pay` + `/pay/check` | `/pay` = **`CWP-002` Quick pay · find the bill**, the GUEST screen |
| screen **36** *Check before you pay* at `/:tenant/portal/pay/check` | `/pay/check` = **`CWP-003` Quick pay · check and pay**, GUEST |
| screen **37** *Payment made* at `/:tenant/portal/pay/done` | `/pay/done` = **`CWP-004` Quick pay · done**, GUEST |

**The router wins, by the blueprint's own rule `R-13` — *a route existing is not a
door* — and by its own §13, which says in as many words: *"A route inferred from a
screen name is a guess. The router is the fact."*** §13 also records what that pass
actually did to the 81 route labels: it **added the missing tenant segment** and
nothing else. It never re-read each path against `App.tsx`, so screens 06/07 and
35/36/37 kept addresses derived from their own titles. **Nothing is renumbered and
no route moves; this table is the reconciliation, and it is why the delta file
reads blueprint 35/36/37 against `/pay-now` and blueprint 06/07 against
`/pay`,`/pay/check`,`/pay/done`.**

⚠ **AND THE CONTENT QUESTION SURVIVES THE ADDRESS QUESTION.** The blueprint gives a
SIGNED-IN customer **three screens** — choose (35), check (36), receipt (37). The
product gives **one** — `/pay-now`, with a three-step *stepper* inside it and an
in-place result panel. That is the largest single divergence in section 06 and it
is recorded as `L6-38.A` rather than assumed to be either right or wrong.

---

## 1 · Screen 06 · *Pay without signing in* — built at `/pay` as `CWP-002`

> **The question:** I have the bill in my hand and I just want to pay it. No
> account, no password, no sign-up.

**PHONE · 390**

```
Silver Creek Water
Pay a bill
No sign-in needed
Bill number
BL-2608-000042
▸ Where to find it — top right of your bill
ZIP code of the service address
78611
Find this bill
IS THIS THE RIGHT BILL?
Bill              BL-2608-000042
For               Jul 1 – Jul 31, 2026
Account           4417-0092
Name              Marcus Bell
Service address   1841 Quarry Hill Ct
                  Silver Creek, TX 78611
Amount due        $191.00
Due               Aug 22, 2026
Pay $191.00
A receipt is emailed to you. Nothing is stored.
```

**DESKTOP · 1280** — the guest bar (`Pay a bill · Report a problem · Prices ·
Help · Visit us`, 🌐 English, the phone number, `Sign in`), then:

```
Pay a bill
No sign-in needed — the bill number from the bill in front of you, and the ZIP code.
Bill number                        BL-2608-000042
   Top right of your bill, next to the date
ZIP code of the service address    78611
Find this bill

BILL BL-2608-000042
Jul 1 – Jul 31, 2026 · Issued Aug 5, 2026
Amount due   $191.00   by Aug 22, 2026
This bill belongs to  Marcus Bell · account 4417-0092
                      1841 Quarry Hill Ct, Silver Creek, TX 78611
Pay from   Bank account ····4417 · no fee ▾
Pay $191.00
Not the right bill? ▸ Try another bill number

WHAT YOU CAN SEE HERE
Only the amount due and the due date. Your bill history, usage and personal
details need a sign-in.

WORTH 60 SECONDS
A sign-in gets you your bills, your usage, autopay and paperless.
Create a sign-in instead
```

**FOR** — *Taking money from someone who will never sign up. Every barrier here is
a payment the utility does not receive today.*

**IT STARTS WITH THE BILL NUMBER** — *Not the account number. The person doing
this is holding one bill and wants that bill paid… An account number asks them to
think about a relationship; a bill number asks them to read the paper.*

**HOW THE FOUND BILL IS LAID OUT** — *Three bands, each owning its full width…
Band one: which bill … Band two: whose bill … Band three: the act.*

**WHAT THE FOUND BILL SHOWS** — *Seven facts, so nobody pays the wrong bill: bill
number · bill period · issued date · account number · name · service address ·
amount and due date.*

⚠ **THAT SEVEN-FACT LIST IS THE ONE BLOCK IN SECTION 06 THAT MUST NOT BE BUILT.**
`BR-CWP-019` is CONFIRMED and says a guest sees *"the amount owing and a masked
name, and nothing else about the account"*; `G92` reads `selectors.bill_lookup`
with `ast` every run. Four of the seven — account number, name, service address,
bill period — would put a stranger's home address and account number on a page
openable with a bill number taken off a doormat. **The drawing pre-dates the
rule.** It is the identical conflict `13-wireframe-delta.md` row `3.2` already
records one screen along, and it is recorded here so the next reader meets it
before building rather than after.

**WHAT IT MUST NOT EXPOSE** — *Only that bill. No history, no other bills, no
usage, no phone number, no email.* (This block and the one above contradict each
other inside the drawing.)

**THE SECURITY COST, STATED** — *rate-limit by address and by ZIP, refuse after a
few misses, and never say which half was wrong.*

**STATES**

| State | The drawing's words |
|---|---|
| NO MATCH | *One message for the pair — never "that bill exists but the ZIP is wrong". Rate-limited.* |
| ALREADY PAID | *"This bill was paid on Aug 19." Offers to pay the account's current balance instead.* |
| NEWER BILL EXISTS | *Says so and offers it: "A newer bill for August is also due."* |
| PAST DUE | *Shows the past-due amount and links to help paying — the same duty as anywhere else.* |
| CLOSED ACCOUNT | *Shows the final balance if one is owed, and says the account is closed.* |

**COMPONENTS** `PortalFrame · Field · AmountDueCard · Button`

---

## 2 · Screen 07 · *Your payment · without an account · done* — built at `/pay/done` as `CWP-004`

> **The question:** I paid without signing in — did it work, and how do I prove it
> later when I have no account to look it up in? A guest has no history to come
> back to, so this screen is the only record they get.

**PHONE · 390**

```
✓ Payment made
$191.00
Aug 13, 2026 · Visa ····8102
WRITE THIS DOWN
PMT-2608-0311
Your reference. You have no account to look this up in, so keep it.
↓ Download receipt
↗ Email it to me
WHERE YOU STAND
Account 4417-0092
Balance now      $0.00
Nothing is past due   CLEAR
NEXT TIME, IN 60 SECONDS
A sign-in keeps every receipt for you, and you would not have to find your
account number again.
Create a sign-in
```

**DESKTOP · 1280** adds:

```
Aug 13, 2026 at 2:41 PM · Visa ····8102 · includes a $2.95 card fee
Against                  Account 4417-0092 · August 2026 bill
Balance now              $0.00
Past due                 Nothing
On your card statement as  SILVER CREEK WATER
KEEP THIS REFERENCE
PMT-2608-0311
You paid without an account, so there is nowhere here to look this up again.
The receipt is the record.
↓ Download receipt   ↗ Email it to me
```

**WHY IT IS SEPARATE** — *The signed-in receipt can say "a copy is in Payments
whenever you need it". This one cannot. **The reference is therefore the loudest
thing after the amount**, with download and email offered before anything else.*

**THE CARD FEE** — *Stated on the receipt as part of the total, because a guest
cannot go back and check what they agreed to.*

**STATES** — `CLEARED A NOTICE` *"Your disconnection notice is cancelled."* ·
`DID NOT CLEAR IT` *Amber, not green: what is still owed and by when.* · `PENDING`
*A bank transfer that takes days says so, with the date it will land.* ·
`EMAIL FAILED` *The download still works and says so — the reference must not
depend on an email arriving.*

**RULES** — *Only the amount, the date and the balance are shown — a guest session
proves possession of a bill, not identity. No history, no personal details, no
other bills.*

⚠ **`Account 4417-0092`, `Balance now`, `Past due` AND `Against … August 2026
bill` ARE THE SAME `BR-CWP-019` CONFLICT AS §1.** The drawing's own RULES line
forbids what its own wireframe draws. Do not build the account block.

**COMPONENTS** `PublicFrame · Callout ok · ReferenceCard · ReceiptActions`

---

## 3 · Screen 35 · *Pay now* — built at `/pay-now` as `CWP-038`

Header: **`35 Pay now` · `NEW BUILD` · `COMMITMENT CPB-01`**

> **The question:** how much, from where, and what will it cost me to pay this
> way? **The fee must be visible before the button, not after.**

**PHONE · 390**

```
‹ Payments
Pay your bill
HOW MUCH
◉ The full amount            $191.00
○ Another amount             You choose
PAY FROM
◉ Bank account ····4417      NO FEE
○ Visa ····8102              +$2.95
+ Add a way to pay
```

**DESKTOP · 1280**

```
‹ Payments
Pay your bill
HOW MUCH
◉ The full amount due        $191.00
○ The past-due part only     Nothing is past due
○ Another amount             $ ____
WHAT YOU WILL PAY
Your bill      $191.00
Card fee       $0.00
Total          $191.00
        (phone column renders the same block as)
Your bill      $191.00
Card fee       $0.00
You will pay   $191.00
Pay $191.00
🔒 We never store your full card number.
PAY FROM
◉ Bank account ····4417 · Silver Creek Credit Union      NO FEE
○ Visa ····8102 · expires 04/28                          +$2.95 fee
○ A different card or account                            + Add
Pay $191.00
Taken today, Aug 13. Shows on your statement as SILVER CREEK WATER.
🔒 We never store your full card number. Your bank details are held by our
payment processor, not by us.
```

**FOR** — *Taking a payment with no uncertainty about the amount, the fee or the
date.*

**HOW YOU GET HERE** — *`Payments`, and the quick-pay flow. Home links to
`/:tenant/portal/pay-now`, the guest route, rather than here.* (See §0 — that
sentence is written against the blueprint's own swapped addresses.)

**PRIMARY ACTION** — *One button, and it names the figure: `Pay $191.00`. Never a
bare "Continue" — the button is the last thing read before money moves.*

**COGNITIVE LOAD** — *The fee is a line in the total, not a footnote. The fee-free
option is listed first and labelled. The customer never adds anything up.*

**NORTH AMERICAN CONVENTION** — *Bank transfer is free and card carries a
convenience fee — this is what customers expect and the screen states it rather
than surprising them at the end.*

**STATES**

| State | The drawing's words |
|---|---|
| PROCESSING | *Button disabled and reads "Taking your payment…". The page cannot be submitted twice.* |
| DECLINED | *Says the bank declined it and what to try; **the amount and method stay selected**.* |
| NOTHING DUE | *"You have nothing to pay right now." Offers to pay ahead rather than showing an empty form.* |
| CARD EXPIRED | *Flagged on the method before they press, not after.* |

**COMPONENTS** `PortalFrame · RadioCard · MethodRow · TotalPanel · Button`
**RULES** — *Money shown to two decimals. The payment is idempotent — a double
submit takes one payment.*

---

## 4 · Screen 36 · *Check before you pay* — NO ADDRESS OF ITS OWN IN THE PRODUCT

Header: **`36 Check before you pay` · `NEW BUILD` · `COMMITMENT CPB-01` ·
`COMMITMENT CPB-23`**, and the drawing's own red callout: *"**No door named.**
This screen carries no `How you get here` row, though the document's own rule E
says every screen does. It is one of 37. See `CPB-23`."*

> **The question:** before the money actually goes — is this the right amount,
> from the right place, and what will it cost me? **The last screen at which
> anything can be changed.**

**PHONE · 390**

```
‹ Pay
Check this, then pay
Your bill · August 2026     $191.00
Card fee                    $0.00
You will pay                $191.00
FROM
🏦 Bank ····4417            ✎ Change
Taken                       Today, Aug 13
On your statement as        SILVER CREEK WATER
THEN
Your balance becomes        $0.00
Next bill                   around Sep 5
Pay $191.00
Go back and change something
```

**DESKTOP · 1280**

```
‹ Pay
Check this, then pay
WHAT YOU ARE PAYING
August 2026 bill · BL-2608-000042 · due Aug 22     $191.00
Card convenience fee     $0.00 — you chose a bank account
Total to be taken        $191.00
From   Bank account ····4417 · Silver Creek Credit Union  ✎ Change
When   Today, Aug 13, 2026
It appears on your statement as   SILVER CREEK WATER
Pay $191.00
Go back and change something
AFTER THIS PAYMENT
Balance     $0.00
Past due    Nothing
Next bill   around Sep 5, 2026
🔒 Your bank details are held by our payment processor, not by us. We never see
or store your full account number.
```

**WHY IT IS ITS OWN SCREEN** — *The pay screen is a form; this is a confirmation.
Separating them means the total, the fee and the date are read once, deliberately,
rather than glanced at while choosing a card.*

**COGNITIVE LOAD** — *The statement descriptor is shown, because "what will this
look like on my bank statement" is a real question that produces chargebacks when
unanswered.*

**STATES** — `AMOUNT CHANGED` *If a payment landed while they were here, the total
is redrawn and says so before the button.* · `METHOD EXPIRED` *Caught here, not at
the processor: the row is flagged and Pay is disabled.* · `FEE APPLIES` *The fee
line is non-zero and the fee-free alternative is offered inline.* ·
`SESSION TIMED OUT` *Nothing is taken; the amount and method are kept.*

**COMPONENTS** `PortalFrame · TotalPanel · MethodRow · Button`
**RULES** — *The payment is idempotent — a double submit from this screen takes
one payment.*

---

## 5 · Screen 37 · *Payment made* — NO ADDRESS OF ITS OWN IN THE PRODUCT

Header: **`37 Payment made` · `NEW BUILD` · `CPB-01` · `CPB-22` · `CPB-23`**, and
the same *"No door named"* callout.

> **The question:** did it work, and is my disconnection notice cleared? **A
> confirmation that only says "success" answers half of it.**

**PHONE · 390**

```
✓ Payment made
$191.00
Aug 13, 2026 · from bank account ····4417
WHERE YOU STAND
Balance now   $0.00
Next bill     around Sep 5
Nothing is past due. Nothing else is needed.
YOUR RECEIPT
Reference     PMT-2608-0311
↓ Download receipt · ↗ Email it to me
Set up autopay so this is automatic
```

**DESKTOP · 1280**

```
✓ Payment made
$191.00
Aug 13, 2026 at 2:41 PM · from bank account ····4417 · reference PMT-2608-0311
YOUR RECEIPT
↓ Download receipt
↗ Email it to me
A copy is in Payments whenever you need it.
Your balance is now      $0.00
Nothing is past due      CLEAR
Your next bill arrives around   Sep 5, 2026
NEXT TIME
Autopay takes the bill on its due date, so you never have to remember.
Set up autopay
```

**COGNITIVE LOAD** — *The balance **after** the payment is on the confirmation. A
customer who was behind should not have to navigate anywhere to learn whether they
still are.*

**THE DISCONNECTION CASE** — *If a shut-off notice was outstanding, this screen
says in its own panel whether the payment clears it — and if it does not, exactly
what is still needed and by when.*

**STATES** — `CLEARED THE NOTICE` *Green panel: "Your disconnection notice is
cancelled." Named explicitly.* · `DID NOT CLEAR IT` *Amber, not green: "$56.30 is
still past due — the notice stands until Aug 20."* · `PENDING` *A bank transfer
that takes days says so, with the date it will land.* · `PARTLY PAID` *Shows the
remaining balance as the headline second figure.*

**WORDS** — *"Payment made", not "Transaction complete". The reference is the
customer's, not a database id.*

**COMPONENTS** `PortalFrame · Callout ok · BalancePanel · ReceiptActions`
**RULES** — *A payment is never edited afterwards; a correction is a new record.
This screen is a receipt, not a form.*

---

## 6 · Screen 38 · *Payments* — built at `/payments` as `CWP-041`

Header: **`38 Payments` · `EXISTS BEHIND` · `COMMITMENT CPB-23`** + *"No door
named."*

> **The question:** did my payment go through, and which bill did it go against?
> The second half is what a landlord or a disputed account needs.

**PHONE · 390**

```
Home  Bills  Payments  Help
Your payments
$191.00   Aug 13 · bank ····4417   CLEARED   August bill
$176.20   Jul 19 · Visa ····8102   CLEARED   July bill
$168.94   Jun 20 · bank ····4417   CLEARED   June bill
↓ Download all as a spreadsheet
```

**DESKTOP · 1280**

```
Your payments
3 payments · $536.14 in the last 12 months
DATE          AMOUNT    PAID FROM              WENT AGAINST        STATUS
Aug 13, 2026  $191.00   Bank account ····4417  August 2026 bill    CLEARED  ↓ Receipt
Jul 19, 2026  $176.20   Visa ····8102          July 2026 bill      CLEARED  ↓ Receipt
Jun 20, 2026  $168.94   Bank account ····4417  June 2026 bill      CLEARED  ↓ Receipt
↓ Download all as a spreadsheet · Payments are kept for seven years
```

**COGNITIVE LOAD** — *"Went against" is a column, not something to work out from
dates. A payment that was split across two bills says both.*

**STATES** — `PENDING` *Amber chip and the date it is expected — never shown as
cleared early.* · `RETURNED` *Red chip, the reason in plain words, the fee
charged, and what to do now.* · `REFUNDED` *Its own row referencing the original,
never an edit to it.* · `NONE YET` *"You have not made a payment yet." With the
amount due and a button.*

**WORDS** — *"Cleared", not "Settled" or "Posted". "Returned", not "NSF" — the fee
line can name the term, the status may not.*

**COMPONENTS** `PortalFrame · PaymentRow · StatusChip · Pagination`
**RULES** — *Server-side paging, no cap on how many a customer may have. Payment
rows are never rewritten.*

---

## 7 · Screen 39 · *Payment methods* — built at `/payment-methods` as `CWP-039`

Header: **`39 Payment methods` · `EXISTS BEHIND` · `NO COMMITMENT`**

> **The question:** what is on file, what is it costing me, and what breaks if I
> remove one?

**PHONE · 390**

```
‹ Payments
Ways to pay
🏦 Bank ····4417
   Silver Creek Credit Union        NO FEE
   Used by autopay
   ✎ Change · ✕ Remove
💳 Visa ····8102
   Expires 04/28                    +$2.95 a payment
   ✎ Change · ✕ Remove
+ Add a way to pay
🔒 We never see or store your full card number.
```

**DESKTOP · 1280**

```
‹ Payments
Ways to pay
2 on file
🏦 Bank account ····4417 · Silver Creek Credit Union     NO FEE
   Autopay uses this one · added Jun 2, 2026             ✎ Change · ✕ Remove
💳 Visa ····8102 · expires 04/28                         +$2.95 a payment
   Added Jul 19, 2026                                    ✎ Change · ✕ Remove
+ Add a way to pay

BEFORE YOU REMOVE ONE
Your bank account is the one autopay uses. Removing it turns autopay off, and
your bill would need paying by hand.

FEES
Bank account   No fee
Card           $2.95
The card fee is set by the card networks and passed on, not kept by us.
```

**HOW YOU GET HERE** — *`Payments` (an errand card), `Pay now` and `Autopay`. **Not
My details** — that screen has no link to it.*

**COGNITIVE LOAD** — *The fee sits on the method, so choosing later on the pay
screen needs no memory. Which method autopay depends on is labelled on the method
itself.*

**DESTRUCTIVE ACTION** — *Remove asks to confirm and names what it breaks — "This
turns autopay off" — rather than a generic "Are you sure?".*

**STATES** — `NONE ON FILE` *"You have no way to pay saved yet." One button, no
empty table.* · `EXPIRING SOON` *Amber flag 60 days out, with the change link,
before autopay fails.* · `EXPIRED` *Red, and autopay says it will fail — stated
here rather than discovered on the due date.* · `REMOVING THE LAST ONE` *Refused
with the reason if autopay is on; offers to turn autopay off first.*

**COMPONENTS** `PortalFrame · MethodCard · ConfirmDialog · Callout warn`
**RULES** — *Icons carry their words. Only the last four digits ever appear — no
full number, on any screen.*

---

## 8 · Screen 40 · *Autopay* — built at `/autopay` as `CWP-040`

Header: **`40 Autopay` · `NEW BUILD` · `COMMITMENT CPB-02`**

> **The question:** if I turn this on, what exactly gets taken, from where, and
> when — and can I stop it?

**PHONE · 390**

```
‹ Payments
Autopay
Autopay is on                       ON
We take the full bill on its due date.
WHAT HAPPENS NEXT
Amount   $191.00
On       Aug 22, 2026
From     Bank ····4417
No fee on a bank account.
SETTINGS
Take           The full bill ▾
When           On the due date ▾
Never more than  No limit ▾
Turn autopay off
We email you 5 days before each payment.
Save
```

**DESKTOP · 1280**

```
‹ Payments
Autopay
Your bill is paid automatically, so you never have to remember.
SETTINGS
Take                  The full bill ▾
When                  On the due date ▾
From                  Bank account ····4417 ▾
Never take more than  No limit ▾
A limit protects you from an unexpectedly large bill — anything above it waits
for you.
NEXT PAYMENT
$191.00
On Aug 22, 2026, from bank account ····4417. No fee.
YOU STAY IN CONTROL
· We email you 5 days before every payment
· You can turn it off at any time, including after the email
· A disputed amount is never taken
Turn autopay off
```

**FOR** — *Setting up automatic payment, and — the part that decides whether people
enrol — proving they stay in control.*

**HOW YOU GET HERE** — *`Payments` (an errand card) and `Payment methods`. **Not My
details**.*

**PRIMARY ACTION** — *Off state: `Turn autopay on`. On state: `Save`, with turning
it off as the quiet outlined option. **The destructive control is never the loudest
thing on the screen.***

**COGNITIVE LOAD** — *The next actual payment — figure, date, source — is shown
before any setting is touched. Nobody should have to imagine what their settings
will do.*

**THE TRUST PANEL** — *The advance email, the ability to cancel, and the
disputed-amount exclusion are the three objections to autopay, answered on the
screen where the decision is made.*

**STATES** — `OFF` *Explains what it would do with the customer's real figures,
then one button.* · `NO METHOD` *Offers to add one first rather than showing a form
that cannot be saved.* · `CARD EXPIRING` *Amber: says autopay will fail on the date
and offers to change the card.* · `LAST ONE FAILED` *Says which payment failed,
why, and what is owed now.*

**WORDS** — *"Autopay" — the North American term, not "Direct debit" or "Recurring
payment authorisation".*

**COMPONENTS** `PortalFrame · ToggleCard · Select · Callout ok · Button ghost`

---

## 9 · The two commitments this section owns, quoted from §12

**`CPB-01` · A customer can pay by card** — screens **35 · 36 · 37 · 6 · 8**.
*Waits on:* **No payment provider is wired.** *"Five separate pieces of copy say
so — "We cannot take card payments yet", "Card payments are not ready yet",
"Online payment arrives later this year", "We cannot take fees online yet", "This
account is cash only"."*
**WHAT DONE LOOKS LIKE ON SCREEN:** *A customer with $191.00 due presses Pay now,
enters a card, and the receipt reads "Paid $191.00 · Aug 14 · reference
PMT-2608-0311" with the balance underneath reading $0.00.* · **STATUS: UNVERIFIED**

**`CPB-02` · Autopay can actually draft a payment** — screen **40**.
*Waits on:* **The same missing provider as CPB-01, on a different flow. *We cannot
draft payments yet* holds the Turn autopay on button.**
**WHAT DONE LOOKS LIKE ON SCREEN:** *A customer turns autopay on, and the next bill
of $191.00 is drafted on Aug 22 without them opening the portal — the Autopay
screen reading "Next: $191.00 on Aug 22".* · **STATUS: UNVERIFIED**

---

## 10 · The unratified rules this section leans on, quoted from appendix A

**Twelve of the twenty-four rules in appendix A are marked `NO HOME` — *"stated
only here"*.** They are **proposals, not law**: no B14 rule, no BR, no decision-log
row. The three the brief names as biting this journey are marked ⚠.

| id | The rule as stated | Where |
|---|---|---|
| `R-04` | *No emoji as a section marker.* | Standards A |
| ⚠ `R-05` | *Amount due and due date appear in the same place on every screen.* | Standards B |
| `R-06` | *Never ask a customer to compute — show the difference, not two numbers.* | Standards B |
| ⚠ `R-07` | *One filled button per screen.* | Standards B |
| ⚠ `R-09` | *Never make a customer remember an account number to do something.* | Standards B |
| `R-10` | *Bad news never appears without the way out beside it.* — *"the strongest rule on the page"* | Standards B |
| `R-13` | *A route existing is not a door.* | Standards E |
| `R-15` | *Position, order and wording never move; a back-link sits under the bar, never inside it.* | Standards D |
| `R-18` | *Assistance is a first-class path, not a page behind a sign-in.* | Standards C |
| `R-19` | *The portal is a second channel; every bill is printed regardless.* | Standards C |
| `R-22` | *Three states — loading, empty, failed — can never render as the same picture.* | Masthead |
| `R-23` | *No sentence states a fact it does not derive.* | Masthead |

The twelve that DO have a home and that this section is measured against anyway:
`R-01` every icon carries its word (⚠ *"a phone has no hover"*), `R-03` colour is
never the only signal, `R-11` name/address/account ride in the frame, `R-12` no
database id (B14 rule 31), `R-16` money two decimals (CLAUDE.md hard rule 2),
`R-24` every screen restacks; nothing scrolls sideways.

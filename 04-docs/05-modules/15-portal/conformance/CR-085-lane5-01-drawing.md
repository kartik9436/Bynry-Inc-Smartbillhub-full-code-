# CR-085 lane 5 · THE DRAWING, QUOTED — bills and documents

**What this is.** `05-prototype/SMARTBillHub Customer Portal Blueprint.pdf` section 05
*The bill* (pages 55–64) and screen 60 *Documents* (pages 105–107), transcribed VERBATIM —
every label, every column, in the drawn order — so the next lane builds from a quote in
front of it rather than from a link it skims. Extracted with `10-scripts/pdf/pdf_text.py`,
with `￾` and `­` stripped before matching (the text layer joins words with them, and a
naive grep returns FALSE ABSENCES).

⚠ **THREE DRAWINGS COVER THESE SIX SCREENS AND THEY DO NOT AGREE.** The blueprint above;
the module's own captured pack `04-docs/05-modules/15-portal/wireframes/CWP-0{27,28,29,30,31}.png`;
and `08-screen-layouts.md`. The disagreements are NOT figures — B14 rule 37 cannot settle
them — they are **which columns a table has** and **which buttons a head carries**. They
are listed in §7 and they need a ruling, not a lane's judgement.

---

## 1 · Section 05 header, verbatim

> **05 · The bill**
> *Five screens. Everything a customer disputes, questions or files starts here, so this
> group carries the heaviest explanatory load — and the most chance to answer a question
> before it becomes a phone call.*

Five screens: **30 Bills · 31 One bill · 32 Why it costs this · 33 The printed bill ·
34 Something looks wrong.** State chips as drawn: 30 `EXISTS BEHIND` · 31 `EXISTS BEHIND` ·
32 `NEW BUILD` · 33 `EXISTS BEHIND` / `NO COMMITMENT` · 34 `BLOCKED`.
Four of the five carry *"No door named. This screen carries no How you get here row … It is
one of 37. See CPB-23."*

---

## 2 · Screen 30 — **Bills** (`/{tenant}/portal/bills`, built as `CWP-027`)

> *The question: which bill is which, and is any of them still unpaid? A list of dates and
> amounts answers neither.*

**PHONE · 390 — a stack of cards, in this order**

| drawn |
|---|
| `Home` `Bills` `Usage` `Help` |
| **`Your bills`** |
| `Every bill since you started, Jun 2026` |
| `Aug 2026` / `Jul 1 – Jul 31` / `$191.00` / `DUE AUG 22` / **`Pay $191.00 now`** |
| `Jul 2026` / `Jun 1 – Jun 30` / `$176.20` / `PAID JUL 19` |
| `Jun 2026` / `May 1 – May 31` / `$168.94` / `PAID JUN 20` |
| `↓ Download all as a spreadsheet` |

**DESKTOP · 1280**

Heading `Your bills`; sub-line `Every bill since you started, Jun 2026 · 3 bills`.
Columns, in order: **`BILL` · `COVERS` · `AMOUNT` · `STATUS`** — four, and no more.
Row 1 action `Pay now`; rows 2 and 3 ` View · ↓ PDF`.
Footer: `↓ Download all as a spreadsheet · Bills are kept for seven years`

**FOR** *Finding a specific bill, and seeing at a glance whether anything is still owed.*
**PRIMARY ACTION** *`Pay` on the unpaid bill only. Paid rows carry no filled button —
nothing to do means nothing to press.*
**COGNITIVE LOAD** *The month is the heading and the period is underneath, because customers
say "my August bill" and mean the one that arrived in August. Both are shown so neither
reading is wrong.*

**STATES, verbatim**

| state | drawn |
|---|---|
| LOADING | *"Three grey rows of the right height, so the page does not jump when they fill."* |
| NO BILLS YET | *"Your first bill will arrive after your first meter read, around Sep 30." Says when, not that the list is empty.* |
| FAILED | *"We could not load your bills." Retry, plus the phone number.* |
| MANY BILLS | *Paged at 12 with a year filter. Never a full unpaged list.* |

**WORDS** *Paid Jul 19, not Settled or Closed. Due Aug 22, not Payment due date: 08/22/2026.*
**COMPONENTS** `PortalFrame` `BillRow` `StatusChip` `Button` `Pagination`
**RULES** *Server-side paging, no cap. Bill number is the customer's reference and is shown;
the database id never is.*

---

## 3 · Screen 31 — **One bill** (`/bills/:number`, built as `CWP-028`)

> *The question: what am I actually paying for? Every line must name a service, a quantity,
> a unit and a price — the four facts that stop the call.*

**PHONE · 390** ` Bills` → `August 2026` → `Bill BL-2608-000042 · Jul 1 – Jul 31` →
`AMOUNT DUE` `$191.00` `Due Aug 22, 2026` **`Pay $191.00 now`** → then the service blocks.

**DESKTOP · 1280** ` Bills` → `August 2026` →
`Bill BL-2608-000042 · covers Jul 1 – Jul 31, 2026 · issued Aug 5`

Service blocks, in order, each line carrying quantity · unit · unit price · amount:

```
ELECTRIC   800 kWh at $0.1150 per kWh              $92.00
           Base charge                             $15.50
           Electric                               $107.50
WATER      First 5 kgal at $4.2400 per kgal        $21.20
           Next 3 kgal at $6.8900 per kgal         $20.67
           Base charge                              $5.63
           Water                                   $47.50
SEWER      7.2 kgal at $5.0000 per kgal
             — 90% of the water you used           $36.00
           Total for August                       $191.00
```

Right rail: `AMOUNT DUE` `$191.00` `Due Aug 22, 2026 · in 9 days` **`Pay $191.00 now`**, then
**`THIS BILL`** carrying, in order:
` Why does it cost this?` · `↓ Download the printed bill` · ` Something looks wrong` ·
` How your water is priced`

**PRIMARY ACTION** *`Pay`. Everything else — compare, download, dispute — is a quiet link.*
**COGNITIVE LOAD** *Every line carries quantity, unit and unit price, so the customer can
check the arithmetic themselves. A line reading only "$36.00" is the shape that generates a
call.*
**MONEY** *Two decimals on totals, four on unit prices — a rate genuinely is $4.2400 per
thousand gallons, and rounding it to $4.24 makes the line stop adding up.*

**STATES** — PAID *"The due card becomes 'Paid in full on Aug 19' and the button disappears
entirely."* · ESTIMATED READ *"A band above the lines: 'This bill is estimated — we could
not read your meter.' With what happens next."* · CORRECTED *"Shows the correction as its
own line, never by altering the original."* · NOT YOURS *"A bill number for another account
404s rather than confirming it exists."*

**COMPONENTS** `PortalFrame` `AmountDueCard` `ServiceBlock` `ChargeLine` `Button`
**RULES** *Quantity always with its unit, never assumed. Nothing on this screen is editable
— a bill is a record.*

---

## 4 · Screen 32 — **Why it costs this** (`/bills/:number/comparison`, built as `CWP-030`)

`NEW BUILD` · `COMMITMENT CPB-08` · `COMMITMENT CPB-23`

> *The question: why is this more than last time? The single most common reason a customer
> calls, and the one the portal can answer alone.*

**DESKTOP heading** `Why August costs $14.80 more than July` — **the ANSWER is the heading.**

**`WHERE THE DIFFERENCE CAME FROM`**, four attribution lines that sum exactly:

```
You used 60 kWh more electricity — 800 kWh, against 740 in July      +$6.90
You used 1 kgal more water — 8 kgal, against 7 in July               +$6.89
Sewer follows your water, at 90% of it                               +$4.50
The period was one day shorter — 31 days, against 32                 −$3.49
Total difference                                                    +$14.80
```

`Your prices did not change between these two bills.`
**`YOUR LAST 12 BILLS`** — `Lowest $142.10` `Average $171.40` `Highest $228.75`.
Phone adds a `PRICES DID NOT CHANGE` card and `THE LAST 12 MONTHS`.

**COGNITIVE LOAD** *The customer is never asked to subtract. The headline is the difference
itself; the parts add to it; a leftover is shown as "everything else", never hidden.*
**THE HARD PART** *Attribution must be honest. If the portal cannot split the difference …
it says which parts it could attribute and how much is unexplained, rather than guessing.*

**STATES** — CHEAPER *"Same layout, '$9.20 less than July', in green."* · NO PREVIOUS BILL
*"This is your first bill, so there is nothing to compare it with yet." Not an empty chart.*
· PRICES DID CHANGE *"The rate change is its own line and says so: 'Water prices rose on
Oct 1 · +$7.40'."* · ESTIMATED *"Says the comparison uses an estimated read."*

**WORDS** *"You used 60 kWh more", not "Consumption variance +60". "One fewer day in the
period", not "Proration adjustment".*
**COMPONENTS** `PortalFrame` `DifferenceCard` `AttributionList` `BillHistoryBars`

---

## 5 · Screen 33 — **The printed bill** (`/bills/:number/document`, built as `CWP-029`)

`EXISTS BEHIND` · `NO COMMITMENT` — **the blueprint believes this one is finished.**

> *The question: can I get the real bill, the one that matches the paper, for my landlord or
> my accountant?*

Phone and desktop both draw **the document itself, rendered on the page**:

```
SILVER CREEK WATER
PO Box 2210, Burnet, TX 78611 · (281) 555-0164
Service address   1841 Quarry Hill Ct / Silver Creek, TX 78611
Account 4417-0092        Bill BL-2608-000042
Electric · 800 kWh                            $107.50
Water · 8 kgal                                 $47.50
Sewer · 7.2 kgal                               $36.00
Amount due by 08/22/2026                      $191.00
— page 1 of 1 —
```

Rail **`THIS DOCUMENT`**: `↓ Download PDF` · `🖨 Print` ·
*"This is the same document we mailed on Aug 5. It never changes."*
Rail **`NEED IT ELSEWHERE?`**: `↓ Download as a spreadsheet` · ` Email a copy to yourself`

**HOW YOU GET HERE** *`Bills` and `One bill` — both build the link from the bill number.*
**PRIMARY ACTION** *`Download PDF`. Print is second because most people asking for this need
a file, not paper.*
**COGNITIVE LOAD** *The preview is the real document at real proportions, not a re-rendered
summary — so what downloads is never a surprise. **The page count is stated on screen.***
**TYPOGRAPHY** *Set as a document, not as terminal output.*

**STATES** — GENERATING *"Preparing your bill…" with the download disabled* · NOT AVAILABLE
*"An older bill predating the portal: says so and offers to post a copy."* · MULTI-PAGE
*"Page navigation appears only when there is more than one page."* · BLOCKED *"A viewer that
cannot start downloads gets a plain link, not a silent failure."*

**COMPONENTS** `PortalFrame` **`DocumentPreview`** `Button`

**The module's own pack agrees** — `wireframes/CWP-029.png` (P15) draws the same preview
pane with `↓ Download` and `🖨 Print` side by side, and adds *"The PDF is the legal artefact
and the screen above it is a convenience."*

---

## 6 · Screen 34 — **Something looks wrong** (`/bills/:number/dispute`, built as `CWP-055`)

`BLOCKED` · `COMMITMENT CPB-13` · `COMMITMENT CPB-23`

> *The question: I think this bill is wrong — what happens now, and do I still have to pay
> it? The second half is what they are really asking.*

```
 August 2026
Something looks wrong
About bill BL-2608-000042 · August 2026 · $191.00

What looks wrong?        [ The meter reading looks wrong ▾ ]
Which service?           [ Water ▾ ]
Tell us more             [ … ]
A photo, if it helps     📷 Add a photo of your meter — it helps us check faster
                         [ Send it ]
```

The five reasons, verbatim and in order:
`The amount is higher than I expected` · `I think the meter reading is wrong` ·
`I am being charged for a service I do not have` · `A payment I made is not shown` ·
`Something else`

Rail **`WHILE WE LOOK INTO IT`**:
> *The disputed amount is **not due** and no late fee is added to it. The rest of the bill
> is still due on Aug 22.*

Rail **`WHAT HAPPENS NEXT`**:
> *1 · We confirm within one working day · 2 · We check the reading, and re-read the meter if
> needed · 3 · We reply within 2 working days with what we found · 4 · If the bill was wrong,
> we correct it on your next one*

**THE CRITICAL PANEL** *What is owed while a dispute is open is stated **before** they send,
not after. It is the question behind the question, and leaving it out guarantees a phone call
whatever else the screen does.*
**WORDS** *"Something looks wrong", not "Raise a dispute" or "Billing enquiry". Customers do
not think of themselves as disputing.*
**STATES** — SENT · ALREADY DISPUTED · TOO LATE · PHOTO TOO LARGE.
**COMPONENTS** `PortalFrame` `Field` `Select` **`FileDrop`** `Callout warn` `Stepper`

---

## 7 · Screen 60 — **Documents** (`/{tenant}/portal/documents`, built as `CWP-031`)

`NEW BUILD` · `CPB-03` `CPB-14` `CPB-15` `CPB-19` `CPB-20`

> *The question: I need a letter proving I live here — or my landlord wants last year's
> bills. Where is everything you have sent me?*

**DESKTOP** heading `Your documents`, sub-line **`6 documents · kept for seven years`**.
Columns: **`DOCUMENT` · `KIND` · `SENT` · `HOW`** — four — each row ending `↓ PDF`.

```
August 2026 bill        Bill      Aug 5, 2026   Email + post   ↓ PDF
Payment receipt · $176.20  Receipt Jul 19, 2026 Email          ↓ PDF
July 2026 bill          Bill      Jul 5, 2026   Email + post   ↓ PDF
Welcome letter          Letter    Jun 2, 2026   Post           ↓ PDF
```

Rail **`ASK FOR A LETTER`** — *"A proof-of-service letter confirms you have had service at
this address, for a benefits claim, a bank, a landlord or a court."* `Ask for one`
*Usually ready the same day.*
Rail **`BULK`** — `↓ Download a year of bills as one file` · `↓ Download a spreadsheet of
everything`
**PHONE** a card list (`August bill` / `Aug 5, 2026 · PDF` / `↓`) plus `All kinds ▾` and a
`NEED SOMETHING ELSE?` card.

**HOW YOU GET HERE** *`Bills`. **Not My details.***
**COGNITIVE LOAD** *"How" says email, post or both, so somebody who never received a letter
can see whether it was posted.*
**STATES** — NONE YET *"Nothing has been sent to you yet." With the first bill's expected
date.* · BEING PREPARED · OLDER THAN SEVEN YEARS *"Says the retention period rather than
showing a gap."* · DOWNLOAD BLOCKED *"A plain link."*

---

## 8 · WHERE THE THREE DRAWINGS DISAGREE — a ruling is needed, not a judgement

| screen | blueprint (8 Sep 2026) | module pack `wireframes/*.png` | what is built |
|---|---|---|---|
| **30 Bills** table | `BILL · COVERS · AMOUNT · STATUS` — **4 columns** | `BILL · PERIOD · ISSUED · DUE · USAGE · AMOUNT · OWING · STATUS` — **8** | **8, matching the pack** |
| 30 footer | `↓ Download all as a spreadsheet · Bills are kept for seven years` | `Showing 1–5 of 5 · Rows per page 50` | pager with `Rows per page 50/100/200/500/1000` |
| 30 head actions | `Pay now` in the unpaid ROW | `↓ Download all` + `Pay $142.18` in the HEAD | `Pay` in the head, no amount, no `Download all` |
| **31 One bill** title | `August 2026`, number in the sub-line | `BL-2608-0141` as the TITLE | **month as the title** (blueprint) |
| 31 head actions | rail: `Why does it cost this?` `↓ Download the printed bill` `Something looks wrong` `How your water is priced` | head: `↓ PDF` `Query this bill` `Pay $142.18` | head: `Why is this different? →` only |
| 31 "something wrong" copy | — | *"Tell us before the due date and **we will hold the account while we look**."* | *"Tell us and somebody will look at this bill."* |
| **60 Documents** table | `DOCUMENT · KIND · SENT · HOW` — 4 | same 4, plus a `Columns` control | **6** — adds `WHAT WE KNOW` and `ACTIONS` |
| 60 heading | `Your documents` / `6 documents · kept for seven years` | `Everything we have sent you` | `Documents and letters`, no count, no retention |

**This is not rule 37's case.** Rule 37 settles a FIGURE drawn two ways. A column set and a
button row are not figures, and *"build the shape they agree on"* leaves a bills table with
four columns on one drawing and eight on another. `BR-CWP-043` (owing is its own column) is
signed law and the blueprint's four columns cannot hold it — which is itself evidence that
the blueprint's section 05 was drawn without that rule in view.

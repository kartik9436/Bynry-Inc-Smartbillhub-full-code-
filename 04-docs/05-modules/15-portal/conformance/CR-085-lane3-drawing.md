# CR-085 lane 3 — the drawing, quoted

**Source:** `05-prototype/SMARTBillHub Customer Portal Blueprint.pdf`, section **03
Starting and stopping service** — pages 30–47 of 129, screens **15–24**. Extracted with
`10-scripts/pdf/pdf_text.py` and stripped of the text layer's word-joining `\ufffe` and
soft hyphens, per the warning in `10-scripts/pdf/README.md`; **nothing else is changed.**

**Why it is quoted and not linked** (`react-tailwind-css-ui-generator` SKILL.md §1):
*"QUOTE the drawing into your working notes — do not link it. The labels, in order, in
front of you while you type. A link gets skimmed; a quote gets built."*

**The ten screens and the four routes they live on**

| # | Screen as the blueprint names it | Route as the router mounts it |
|---|---|---|
| 15 | Start service · 1 Address | `/:tenant/portal/start-service` |
| 16 | Start service · 2 When | `/:tenant/portal/start-service/:draft` |
| 17 | Start service · 3 About you | `/:tenant/portal/start-service/:draft` |
| 18 | Start service · 4 Check | `/:tenant/portal/start-service/:draft` |
| 19 | Finish starting service | `/:tenant/portal/start-service/:draft` |
| 20 | Stop service · 1 Which property | `/:tenant/portal/stop-or-restart` |
| 21 | Stop service · 2 When | `/:tenant/portal/stop-or-restart` |
| 22 | Stop service · 3 Where the final bill goes | `/:tenant/portal/stop-or-restart` |
| 23 | Stop service · 4 Check | `/:tenant/portal/stop-or-restart` |
| 24 | Your final bill | `/:tenant/portal/final-bill` |

⚠ **Ten screens, four addresses.** Five of the ten are STEPS of two wizards that each
live at one address, which is why the screen count is larger than the route count and why
a route-by-route walk sees four pages where the drawing draws ten.

⚠ **Two document faults found while quoting, reported rather than repaired:**

1. **Section 03's own commitment block reads `None.`** while **nine of its ten screen
   cards carry the chip `COMMITMENT CPB-23`** (screen 20 carries `NO COMMITMENT`). Both
   statements are in the same section and they contradict each other.
2. **Screen 20's body still says the flow is unreachable** — *"Nothing.
   `tenantportalstoporrestart` has no door anywhere in the portal — not from Home, not
   from My details, not from Your account, not in the nav… Filed as a defect; this whole
   four-step flow is currently unreachable."* — while **the same card's header already
   says `NOW: ANSWERED — the door was built`**. That is CLAUDE.md's *status column vs
   body* rot (`DEF-WRK-4030`) inside the blueprint itself: the header was edited when the
   ruling landed and the body, which is what a lane actually reads, was not. **The body is
   wrong: two doors exist** (`YourAccount.tsx:271`, `MyDetails.tsx:299`).

---

## The section, verbatim

```text
03
Starting and stopping service
Ten screens, and two four-step flows that mirror each other. Start is reached
before there is an account; stop is reached from inside one. They are drawn as
two flows and would be 
built as one
 — the same wizard component with different
steps configured, because the stepper, the read-back, the change links, the what-
happens-next panel and the refusal behaviour are identical work.

═══════════ PAGE 31 ═══════════
15
Start service · 1 Address
EXISTS BEHIND
COMMITMENT CPB-23
tenantportalstartservice
No door named.
 This screen carries no 
How you get here
 row, though the document's own rule E
says every screen does. It is one of 37. See 
CPB-23
.
15
 Start service · 1 Address 
tenantportalstartservice
The question:
 do you even serve this address, and with what? Asked first, before a single detail, because everything after it is wasted if the answer is no.
PHONE · 390
Silver Creek Water
🌐
 English 
▾
Start service
Step 1 of 4 · about 5 minutes
1 Address
2 When
3 About you
4 Check
Where do you need service?
1841 Quarry Hill Ct
Silver Creek
78611
📍
 Or use my location
Check this address

 
We serve this address.
Water · Sewer · Trash
Electric here is supplied by Pedernales Electric,
not by us.
Continue
DESKTOP · 1280
Silver Creek Water
 ·  Pay a bill  ·  Report a problem  ·  Prices  ·  Help  ·  Visit us
🌐
 English 

  ·  

 (281) 555-0164  ·  
Sign in
Start service
Step 1 of 4 · about 5 minutes · nothing is saved until step 4
1 Address
2 When
3 About you
4 Check
WHERE DO YOU NEED SERVICE?
Street address
1841 Quarry Hill Ct
Town
Silver Creek
ZIP code
78611
Is there a unit or apartment number?
Optional — Apt 2B
Check this address
📍
 Use my location
WE SERVE THIS ADDRESS
💧
 Water
Required
🚿
 Sewer
Required with water

 Trash
Optional · $18.00 a month
Electric at this address is supplied by
Pedernales Electric
, not by us. You will
need to contact them separately.
Continue
ALREADY A CUSTOMER?
If you are moving within our area, signing in
first carries your details and your payment
method across.

 Sign in

═══════════ PAGE 32 ═══════════
FOR
Answering "can I get service here" in one field, before anybody fills a form.
WHY IT IS STEP ONE
Every other question is wasted if the answer is no. A person who fills three steps and is then told the address is outside the area has spent five minutes
to learn something the first field knew.
WHAT THE CHECK
MUST SAY
Not just yes or no — 
which services
, which are required, which are optional and what they cost. And, where the utility knows it, 
who supplies the
rest
: "electric here is Pedernales Electric" saves a second search and a call.
COGNITIVE LOAD
Nothing is asked about the person yet. Location by one tap. The step count and the time are stated before the first field.
STATES
NOT OUR AREA
Says so immediately and names
who does serve it, where known.
ADDRESS NOT RECOGNISED
Offers the nearest matches rather
than refusing a typed address.
ALREADY HAS SERVICE
Says so: somebody else holds it,
or you do. Routes to sign-in or the
phone.
UNIT NEEDED
A multi-unit building asks which
unit, because service is per unit.
COMPONENTS
PublicFrame
Stepper
AddressField
ServiceAvailability
RULES
The address is checked against premises records; nothing here creates one. A unit refines a premises by label, not by a second address.
16
Start service · 2 When
EXISTS BEHIND
COMMITMENT CPB-23
tenantportalstartservice
No door named.
 This screen carries no 
How you get here
 row, though the document's own rule E
says every screen does. It is one of 37. See 
CPB-23
.
16
 Start service · 2 When 
tenantportalstartservice
The question:
 when do I need it on, which of the optional services do I want, and what will it cost to start?
PHONE · 390
Silver Creek Water
🌐
 English 
▾
When would you like it on?
1841 Quarry Hill Ct · step 2 of 4
✓
 1
2 When
3 About you
4 Check
Start from
DESKTOP · 1280
Silver Creek Water
 ·  Pay a bill  ·  Report a problem  ·  Prices  ·  Help  ·  Visit us
🌐
 English 

  ·  

 (281) 555-0164  ·  
Sign in
When would you like it on?
1841 Quarry Hill Ct, Silver Creek, TX 78611 · step 2 of 4
✓
 1 Address
2 When
3 About you
4 Check

═══════════ PAGE 33 ═══════════
09/14/2026
Earliest we can do is 09/10/2026
Is it a home or a business?
Home 

WHICH SERVICES?

 Water
Required

 Sewer
Required with water

 Trash · weekly
$18.00 a month
WHAT IT COSTS TO START
Connection fee
$45.00
Deposit
Decided at step 3
Charged on your first bill, not today.
Continue
Nobody needs to be home unless the water is off at the
street.
Start from
09/14/2026
Earliest is 09/10/2026 — we need
three working days
Home or business?
Home 

Which services?

 
Water
Required at this address

 
Sewer
Required with water · charged on 90% of your water

 
Trash
 · weekly collection, Tuesdays
Optional · $18.00 a month
Continue
WHAT IT COSTS TO START
Connection fee
$45.00
Deposit
Decided at step 3
On your first bill
$45.00 + any deposit
Nothing is taken today. A deposit, if one is
needed, depends on a credit check at the
next step.
ON THE DAY
Nobody needs to be home unless the water is
shut off at the street. If it is, we will call to
arrange a time.
A TYPICAL MONTHLY BILL HERE
about $96
Water, sewer and trash for a household of
three, based on this street.
FOR
The date, the services, and the two costs — one to start, one every month.
THE EARLIEST DATE
IS STATED
Before they type, not after they are refused. "Earliest is 09/10 — we need three working days" is one sentence that prevents a rejected form.
COGNITIVE LOAD
Required services are ticked and locked with the reason; only the genuinely optional one is a choice. The estimated monthly bill answers the question
behind the question — moving people want to know what they are signing up to, not just the joining fee.
STATES
DATE TOO SOON
Says the earliest date rather than
rejecting the typed one.
BUSINESS CHOSEN
The service list and the fees
change, and the screen says they
did.
NO OPTIONAL SERVICES
The list is shown as facts, not tick-
boxes, when nothing is optional.
NO ESTIMATE AVAILABLE
The panel is absent, not shown
with a dash.
COMPONENTS
PublicFrame
Stepper
DateField
ServicePicker
CostPanel

═══════════ PAGE 34 ═══════════
17
Start service · 3 About you
EXISTS BEHIND
COMMITMENT CPB-23
tenantportalstartservice
No door named.
 This screen carries no 
How you get here
 row, though the document's own rule E
says every screen does. It is one of 37. See 
CPB-23
.
17
 Start service · 3 About you 
tenantportalstartservice
The question:
 who are you, how do we reach you, and can you prove it? This is the step people abandon, because it is the one that needs a document they do
not have to hand.
PHONE · 390
Silver Creek Water
🌐
 English 
▾
About you
Step 3 of 4
✓
 1
✓
 2
3 About you
4 Check
Your name
Marcus Bell
Email
m.bell@example.com
Phone
(512) 555-0148
Date of birth
MM/DD/YYYY
Used for the credit check only. It decides whether a
deposit is needed.
Proof of identity
📎
Add a photo of your ID
DrivinglicencepassportorstateID
DESKTOP · 1280
Silver Creek Water
 ·  Pay a bill  ·  Report a problem  ·  Prices  ·  Help  ·  Visit us
🌐
 English 

  ·  

 (281) 555-0164  ·  
Sign in
About you
Step 3 of 4 · this is the only step that needs a document
✓
 1 Address
✓
 2 When
3 About you
4 Check
First name
Marcus
Last name
Bell
Email — where your bill will be sent
m.bell@example.com
Phone
(512) 555-0148
Date of birth
MM/DD/YYYY
Mailing address, if different
Same as the service address

Proof of identity
📎
Drop a file here, or choose one
A driving licence, passport or state ID · JPG, PNG or PDF · up to 10
MB
WHY WE ASK FOR EACH OF THESE
Name and address
Whose account it is
Email
Where the bill goes
Phone
Only if something goes wrong on the
day
Date of
birth
The credit check, which decides
the deposit
Photo
ID
Required by state rules before
service starts
NO ID TO HAND?
Send it later.
 Everything else is saved
and we hold your request for 30 days.
Service cannot start until it arrives, so
the sooner the better.

═══════════ PAGE 35 ═══════════
Driving licence, passport or state ID
JPG, PNG or PDF · up to 10 MB
Send it later instead
Continue
Choose a file
📄
 licence-front.jpg
2.1 MB · 

 added · 

 remove
Continue
Send my ID later
YOUR DOCUMENTS ARE PRIVATE
An ID is used to verify you and is deleted
once service starts. It is never shown on a bill
or shared.
FOR
Identity, contact and the credit check. It is the step that decides whether a deposit is charged, and the step most abandonments happen on.
EVERY FIELD SAYS
WHY
A panel naming what each one is for. People type a date of birth into a utility form with real hesitation; "the credit check, which decides the deposit" is
the difference between suspicion and cooperation.
THE DOCUMENT
DROP
Drag-and-drop with an explicit "choose a file", the accepted formats and the size limit stated 
before
 the attempt. An uploaded file is listed with its size
and a way to remove it — never a silent success.
SEND IT LATER
The escape hatch, offered as a real option rather than a failure. The commonest reason this form is abandoned is a document that is upstairs, in a car,
or at work — and somebody who leaves to fetch it does not come back. What it costs is stated: service cannot start until it arrives.
STATES
FILE TOO LARGE
Says the limit in plain terms and
keeps every typed field.
WRONG FORMAT
Names the formats accepted;
does not clear the drop zone.
DEPOSIT REQUIRED
Shown at step 4 with the reason
and what would remove it — never
as a surprise on the first bill.
SIGNED IN
Name, email, phone and mailing
address arrive pre-filled from the
account.
COMPONENTS
PublicFrame
Stepper
Field
FileDrop
AttachmentRow
Callout warn
18
Start service · 4 Check
EXISTS BEHIND
COMMITMENT CPB-23
tenantportalstartservice
No door named.
 This screen carries no 
How you get here
 row, though the document's own rule E
says every screen does. It is one of 37. See 
CPB-23
.
18
 Start service · 4 Check 
tenantportalstartservice
The question:
 is all of that right, what have I agreed to, and what happens next? The last screen before a request that starts a legal supply.

═══════════ PAGE 36 ═══════════
PHONE · 390
Silver Creek Water
🌐
 English 
▾
Check this, then send it
✓
 1
✓
 2
✓
 3
4 Check
SERVICE
Address
1841 Quarry Hill Ct
Silver Creek, TX 78611
From
Sep 14, 2026
Services
Water · Sewer · Trash

 Change
YOU
Name
Marcus Bell
Email
m.bell@example.com
ID
✓
 licence-front.jpg

 Change
WHAT YOU WILL BE CHARGED
Connection fee
$45.00
Deposit
$0.00
No deposit needed — the credit check passed.
On your first bill
$45.00
 I agree to the terms of service
Send my request
DESKTOP · 1280
Silver Creek Water
 ·  Pay a bill  ·  Report a problem  ·  Prices  ·  Help  ·  Visit us
🌐
 English 

  ·  

 (281) 555-0164  ·  
Sign in
Check this, then send it
Step 4 of 4 · nothing has been submitted yet
✓
 1 Address
✓
 2 When
✓
 3 About you
4 Check
SERVICE  
✎
 CHANGE
Service address
1841 Quarry Hill Ct, Silver Creek, TX 78611
Starting
Monday, Sep 14, 2026
Water
Residential Standard · tiered
Sewer
90% of the water you use
Trash
Weekly, Tuesdays · $18.00 a month
YOU  
✎
 CHANGE
Name
Marcus Bell
Email
m.bell@example.com
Phone
(512) 555-0148
Mailing address
Same as the service address
Proof of identity
✓
 licence-front.jpg · 2.1 MB
WHAT YOU WILL BE CHARGED
Connection fee
$45.00
Deposit
$0.00
On your first bill
$45.00
No deposit is needed — the credit check
passed. Nothing is taken today; both appear
on your first bill, around Oct 5.
WHAT HAPPENS NEXT
1 · We confirm by email within one working
day
2 · We turn the water on, on Sep 14
3 · Your first bill arrives around Oct 5
4 · You can create a sign-in as soon as we
confirm
 I agree to the 
terms of service
 

Send my request
Send is disabled until the box is ticked.
FOR
The read-back before a request that starts a legal supply and a billing relationship.
IT READS BACK
WHAT WILL BE
Every answer from the three steps before, each with a change link that returns to the step it came from — not a generic Back. This is the same
discipline the rate wizard's review needed and did not have.

═══════════ PAGE 37 ═══════════
STORED
THE DEPOSIT
VERDICT, HERE
With its reason. "No deposit is needed — the credit check passed" closes the question this whole flow raises at step 3, at the moment somebody is
deciding whether to press.
WHAT HAPPENS
NEXT
Four dated steps, so nobody has to phone to ask whether it worked. The confirmation window is stated before the request, not after.
STATES
DEPOSIT REQUIRED
The figure and the reason, and
what would remove it — not a bare
amount.
ID NOT ATTACHED
Says service cannot start until it
arrives, and how to send it.
Sending is still allowed.
ADDRESS TAKEN MEANWHILE
Refused with the reason and the
phone number; nothing typed is
lost.
SENT
A reference on screen and by
email, and the request appears
under Your requests once there is
an account.
COMPONENTS
PublicFrame
Stepper
ReadBack
CostPanel
Consent
19
Finish starting service
EXISTS BEHIND
COMMITMENT CPB-23
tenantportalstartservicedraft
No door named.
 This screen carries no 
How you get here
 row, though the document's own rule E
says every screen does. It is one of 37. See 
CPB-23
.
19
 Finish starting service 
tenantportalstartservicedraft
The question:
 I started this last night on my phone and had to stop — where was I, and what is still needed? The answer must be the 
fields themselves
, not a list
of what is missing. Somebody who returns has thirty seconds and a document in their hand.
PHONE · 390
Silver Creek Water
🌐
 English 
▾
Picked up where you left off
 · started Sep 6 ·
1841 Quarry Hill Ct
Two things left
About 3 minutes
Your name
MBll
DESKTOP · 1280
Silver Creek Water
 ·  Pay a bill  ·  Report a problem  ·  Prices  ·  Help  ·  Visit us
🌐
 English 

  ·  

 (281) 555-0164  ·  
Sign in
Picked up where you left off.
 You started this on Sep 6 for 1841 Quarry Hill Ct, Silver Creek, TX 78611.
Held until Oct 6
Two things left · about 3 minutes
✓
 1 Address
✓
 2 When
3 About you
4 Check

═══════════ PAGE 38 ═══════════
Marcus Bell
Phone
(512) 555-0148
Date of birth
MM/DD/YYYY
Proof of identity
📎
Drop a file here, or choose one
Driving licence, passport or state ID
JPG, PNG or PDF · up to 10 MB
📷
 Take a photo
Finish and send
ALREADY DONE

 Address · 1841 Quarry Hill Ct


 From Sep 14 · home


 Water · Sewer · Trash

We keep an unfinished request for 30 days — this one
until Oct 6.
ABOUT YOU — THE PART YOU DID NOT FINISH
First name
Marcus
Last name
Bell
Email — where your bill will be sent
m.bell@example.com
Phone
(512) 555-0148
Date of birth
MM/DD/YYYY
Still needed — for the credit check
Mailing address, if different
Same as the service address

Proof of identity — still needed
📎
Drop a file here, or choose one
A driving licence, passport or state ID · JPG, PNG or PDF · up to
10 MB
Choose a file
📷
 Take a photo
Finish and send
Save and come back later
ALREADY DONE  
NOTHING TO REDO

 Address · we serve
it
1841 Quarry Hill Ct
 


 Start date · home
Sep 14, 2026  


 Services
Water · Sewer · Trash  

WHAT IT WILL COST TO START
Connection fee
$45.00
Deposit
Decided once the date of birth
is in
THIS REQUEST EXPIRES
We hold an unfinished request for 30
days — this one until 
Oct 6, 2026
.
Nothing is lost before then, and we will
email you once before it goes.
FOR
Bringing back somebody who abandoned a move-in form — usually at the document, usually because it was upstairs or at work.
IT OPENS ON THE
FIELDS, NOT ON A
CHECKLIST
The first version of this screen listed what was still needed and made the clerk press 
Carry on
 to reach it. That is one more tap between a person
holding their licence and the thing that takes a photo of it. 
The unfinished step is the page
; what is already done is a small panel beside it, with
change links, not a progress report.
THE DOCUMENT
DROP
Drag-and-drop, 
choose a file
, and 
take a photo
 — the last is the one that matters on a phone, because the ID is in the person's hand and the camera
is one tap away. Formats and the size limit are stated before the attempt, and an added file is listed with its size and a way to remove it.
STILL-NEEDED
FIELDS ARE
MARKED
An accented border and one line underneath — "still needed, for the credit check". Everything already answered is pre-filled and editable, so a
returning person can correct a typo without starting over.

═══════════ PAGE 39 ═══════════
MARKED
THE EXPIRY, WITH A
DATE
A saved draft has a life and the date is on the screen, plus a promise to email before it goes. A form that quietly vanishes is worse than one that never
saved.
STATES
EXPIRED
Says so and offers to start again
with every answer it can still pre-
fill.
ADDRESS TAKEN MEANWHILE
Someone else took service there:
says so, with the phone number.
DATE NOW PAST
Asks for a new start date rather
than silently moving it.
NOTHING LEFT BUT THE ID
The page is the drop zone and one
button. No form at all.
COMPONENTS
PublicFrame
Stepper
Field
FileDrop
CameraCapture
DoneList
Callout warn
20
Stop service · 1 Which property
EXISTS BEHIND
NO COMMITMENT
tenantportalstoporrestart
WAS:
/stop-or-restart has no door anywhere in the portal
NOW:
 ANSWERED — 
the door was built.
YourAccounttsx
 now links to 
tenantportalstopor
restart
. Fixed by the doors wave, 
DEFCWP
.
20
 Stop service · 1 Which property 
tenantportalstoporrestart
The question:
 which one am I stopping, and all of it or part of it? Skipped entirely for the customer with one property and one set of services — which is most of
them.
PHONE · 390

 My details
Stop service
Step 1 of 4
1 Which
2 When
3 Final bill
4 Check
Which property?

 
1841 Quarry Hill Ct
4417-0092 · Water · Sewer · Trash

 
220 Lakeview Dr
4417-0155 · Water
DESKTOP · 1280
Silver Creek Water
Home
Bills
Usage
Payments
Requests
Help
My details
🌐
 English 

  ·  Sign out
Marcus Bell  ·  1841 Quarry Hill Ct, Silver Creek, TX 78611  ·  Account 
4417-0092
$191.00 due Aug 22
Stop service
Step 1 of 4 · nothing is stopped until you confirm at step 4
1 Which property
2 When
3 Final bill
4 Check
WHICH PROPERTY?

 
1841 Quarry Hill Ct
, Silver Creek, TX 78611 
· 4417-0092 · Water,
Sewer,Trash
NOT SURE WHICH YOU NEED?
Moving out
Stop all services

═══════════ PAGE 40 ═══════════
Stop everything, or just part?

 Stop all services
Closes the account

 Just stop trash
Keeps water and sewer on
Continue
Sewer, Trash

 
220 Lakeview Dr
, Burnet, TX 78611 
· 4417-0155 · Water
STOP EVERYTHING, OR JUST PART OF IT?

 
Stop all services
 — the account closes and a final bill is sent

 
Stop trash only
 — water and sewer stay on, the account stays
open

 
Pause for a season
 — $25.00, the account stays open, nothing is
billed for usage
Continue
Away for
the winter
Pause for a season — cheaper
than stopping and restarting
Do not want the trash
service
Stop trash
only
Stopping and restarting later costs $45.00 to
reconnect. Pausing costs $25.00 and keeps
your account number.
FOR
Landlords, people with two properties, and anybody who wants to drop one service rather than all of them.
HOW YOU GET HERE
Nothing.
tenantportalstoporrestart
 has 
no door anywhere in the portal
 — not from Home, not from My details, not from Your account,
not in the nav. The route is registered and the screen is built. Filed as a defect; this whole four-step flow is currently unreachable.
SKIPPED FOR MOST
PEOPLE
One account with no optional services means nothing to choose, so this step does not render — the flow opens on 
When
 and says "step 1 of 3". A
chooser with one option is furniture, exactly as everywhere else.
STOP IS NOT THE
ONLY ANSWER
A large share of stop requests are seasonal absences. Pausing costs $25.00 and keeps the account; stopping and restarting costs $45.00 to
reconnect. Naming the three situations in the customer's own words — moving out, away for the winter, do not want trash — routes them without
making them price it themselves.
STATES
ONE ACCOUNT, ALL
REQUIRED
Step absent. The flow is three
steps and says so.
LANDLORD ACCOUNT
Explains that service reverts to the
property owner rather than
stopping.
ALREADY SCHEDULED
Shows the stop already booked
and offers to change or cancel it.
CANNOT PAUSE
Where a utility does not offer it, the
option is absent rather than
refused.
COMPONENTS
PortalFrame
Stepper
RadioCard
GuidancePanel
21
Stop service · 2 When
EXISTS BEHIND
COMMITMENT CPB-23
tenantportalstoporrestart
No door named.
 This screen carries no 
How you get here
 row, though the document's own rule E

═══════════ PAGE 41 ═══════════
says every screen does. It is one of 37. See 
CPB-23
.
21
 Stop service · 2 When 
tenantportalstoporrestart
The question:
 what is the last day I need it, and does anyone have to be home? The date is the one thing on this whole flow a customer gets wrong, because they
pick their moving day rather than the day after.
PHONE · 390

 Which property
When should it stop?
1841 Quarry Hill Ct · step 2 of 4
✓
 1
2 When
3 Final bill
4 Check
Last day you need service
09/30/2026
You are billed up to and including this day.
Moving on the 30th?
 Pick the 30th, not the
29th — you will want water on moving day.
Why, if you would like to say
Moving out 

ON THE DAY
Final meter read
Sep 30
Anyone home?
Not needed
Continue
DESKTOP · 1280
Silver Creek Water
Home
Bills
Usage
Payments
Requests
Help
My details
🌐
 English 

  ·  Sign out
Marcus Bell  ·  1841 Quarry Hill Ct, Silver Creek, TX 78611  ·  Account 
4417-0092
$191.00 due Aug 22
When should it stop?
1841 Quarry Hill Ct, Silver Creek, TX 78611 · step 2 of 4
✓
 1 Which property
2 When
3 Final bill
4 Check
Last day you need service
09/30/2026
Earliest is 09/11 — we need three
working days
Why, if you would like to say
Moving out 

PICK YOUR MOVING DAY, NOT THE DAY BEFORE
You are billed 
up to and including
 Sep 30, and the water
stays on all that day. People commonly choose the 29th and
then have no water while they load the van.
Continue
ON THE DAY
We read your meter
Sep 30
Does anyone need to be home?
No
Is the water turned
off at the street?
Only if the
property will be
empty
IF YOU ARE COMING BACK
A seasonal pause keeps your account and
costs $25.00. Stopping and restarting later
costs $45.00 to reconnect.

 Go back and pause instead
FOR
The date, and the one misunderstanding that generates a call on moving day.
THE WARNING IS
THE POINT
"Billed up to and including"
 is stated at the field, and the consequence spelled out: people pick the day before they move, then have no water while
loading a van. One sentence prevents an emergency call and a reconnection fee.

═══════════ PAGE 42 ═══════════
THE EARLIEST DATE
IS STATED
Before they type. A stop needs a read scheduled, so it cannot be tomorrow, and saying so beats refusing afterwards.
THE WAY BACK
The seasonal alternative is offered again here, because "when" is the step at which somebody realises they are only going away for three months.
STATES
DATE ALREADY BILLED
Refused with the reason and the
earliest allowed — an issued bill is
never unpicked.
DATE TOO SOON
Says the earliest date rather than
rejecting the typed one.
FAR FUTURE
Accepted, with a note that we will
confirm nearer the time.
PROPERTY EMPTY
Asks whether to shut off at the
street, which prevents a burst pipe
in an empty house.
COMPONENTS
PortalFrame
Stepper
DateField
Callout warn
22
Stop service · 3 Where the final bill goes
EXISTS BEHIND
COMMITMENT CPB-23
tenantportalstoporrestart
No door named.
 This screen carries no 
How you get here
 row, though the document's own rule E
says every screen does. It is one of 37. See 
CPB-23
.
22
 Stop service · 3 Where the final bill goes 
tenantportalstoporrestart
The question:
 where do you send the last bill, and my deposit? A final bill posted to the address they have just left is the most expensive small failure in the whole
product.
PHONE · 390

 When
Where should the final bill go?
Step 3 of 4
✓
 1
✓
 2
3 Final bill
4 Check

 This address
1841 Quarry Hill Ct

 A new address
220 Lakeview Dr
DESKTOP · 1280
Silver Creek Water
Home
Bills
Usage
Payments
Requests
Help
My details
🌐
 English 

  ·  Sign out
Marcus Bell  ·  1841 Quarry Hill Ct, Silver Creek, TX 78611  ·  Account 
4417-0092
$191.00 due Aug 22
Where should the final bill go?
Step 3 of 4 · your final bill is sent around Oct 5
✓
 1 Which property
✓
 2 When
3 Final bill
4 Check
THE FINAL BILL

 Send it to 
this
1841 Quarry Hill Ct — only if somebody will still be
YOUR DEPOSIT COMES BACK
$150.00

═══════════ PAGE 43 ═══════════
Burnet
78611
Email — we will send it here too
m.bell@example.com
You have $150.00 on deposit.
 It comes
back to you, less anything owed, within 30
days.
Send my refund to
Bank ····4417 

Continue
address
there

 Send it to 
a new address
Street address
220 Lakeview Dr
Town
Burnet
State and ZIP
TX 78611
Email — we send a copy here as well
m.bell@example.com
Continue
$150.00
Less anything still owed on the final bill,
within 30 days of it being issued — which is
the rule, not our choice.
Send the refund to
Bank account ····4417 

Or by check to the address on the left.
WHY WE ASK TWICE
The bill goes to the forwarding address; the
refund goes wherever you say. They are
usually the same and occasionally not — a
refund to a closed bank account is a month of
phone calls.
FOR
The two things that go wrong after somebody leaves: the bill posted to the house they moved out of, and the deposit sent nowhere.
ITS OWN STEP, ON
PURPOSE
Buried at the foot of a single stop form, the forwarding address is the field people skip. Given a step of its own, with the deposit figure beside it, it is the
field they came to fill in.
THE DEPOSIT IS
SHOWN, NOT
MENTIONED
$150.00
, what is deducted, and the 30-day rule stated as a rule rather than a promise. It is the question every leaving customer phones about, and the
refund destination is asked here rather than assumed.
BILL AND REFUND
ARE SEPARATE
They are usually the same and occasionally not. A refund into an account being closed with the move is a month of phone calls, so the screen asks
rather than infers.
STATES
NO DEPOSIT HELD
The panel is absent, not shown as
$0.00 — nothing was ever taken.
MONEY OWED
Says the final bill is expected to
exceed the deposit, with the
estimate.
NO FORWARDING ADDRESS
Allowed, with a warning that the
bill goes to the old address.
EMAIL ONLY
Where the utility permits it, paper
can be declined — and it says the
bill is then email only.
COMPONENTS
PortalFrame
Stepper
AddressField
Callout ok
Select
RULES
A forwarding address is a mailing address on the customer, not a second address on the premises — the property keeps its own.
23
Stop service · 4 Check
EXISTS BEHIND
COMMITMENT CPB-23

═══════════ PAGE 44 ═══════════
tenantportalstoporrestart
No door named.
 This screen carries no 
How you get here
 row, though the document's own rule E
says every screen does. It is one of 37. See 
CPB-23
.
23
 Stop service · 4 Check 
tenantportalstoporrestart
The question:
 is that right, and what happens after I press it? Four dates, so nobody has to phone to ask whether it worked.
PHONE · 390

 Final bill
Check this, then confirm
✓
 1
✓
 2
✓
 3
4 Check
WHAT WILL HAPPEN
Stopping
1841 Quarry Hill Ct
Last day
Sep 30, 2026
Services
Water · Sewer · Trash
Final bill to
220 Lakeview Dr
Burnet, TX 78611

 Change
THEN
1 · Meter read
Sep 30
2 · Final bill
around Oct 5
3 · Due
around Oct 20
4 · Deposit back
by Nov 4
Stop service on Sep 30
You can cancel this up to Sep 29.
DESKTOP · 1280
Silver Creek Water
Home
Bills
Usage
Payments
Requests
Help
My details
🌐
 English 

  ·  Sign out
Marcus Bell  ·  1841 Quarry Hill Ct, Silver Creek, TX 78611  ·  Account 
4417-0092
$191.00 due Aug 22
Check this, then confirm
Step 4 of 4 · nothing is stopped until you press the button
✓
 1 Which property
✓
 2 When
✓
 3 Final bill
4 Check
WHAT WILL HAPPEN  
✎
 CHANGE
Property
1841 Quarry Hill Ct, Silver Creek, TX 78611
Account
4417-0092 — this account will close
Last day of service
Wednesday, Sep 30, 2026
Services stopping
Water · Sewer · Trash — all of them
Final bill posted to
220 Lakeview Dr, Burnet, TX 78611
Deposit refund to
Bank account ····4417
WHAT YOU WILL OWE
Service to Sep 30 · estimated
$86.20
Move-out final read
$20.00
Deposit held
−$150.00
Expected back to you
$43.80
WHAT HAPPENS NEXT
1 · We read your meter
Sep 30
2 · Your final bill is sent
around Oct 5
3 · It is due
around Oct 20
4 · Your deposit is returned
by Nov 4
Stop service on Sep 30
You can cancel this any time up to Sep 29.
AUTOPAY IS ON
Your final bill will be taken
automatically on its due date, from
bank ····4417. If that account is closing
with your move, change it now.

 Change autopay

═══════════ PAGE 45 ═══════════
An estimate — the final read decides it.
FOR
The read-back, the expected money, and the four dates — before an act that closes an account.
THE MONEY IS
ESTIMATED AND
SAYS SO
A leaving customer wants to know whether they owe or are owed. Showing 
$43.80 expected back
 with "the final read decides it" answers the
question honestly; showing nothing sends them to the phone.
THE AUTOPAY
WARNING
The one nobody thinks of: autopay will take the final bill from an account that may be closing with the move. Flagged here, with a change link, because
after this screen the customer stops visiting.
CANCELLABLE,
WITH A DATE
"You can cancel this up to Sep 29" — moves fall through, and a stop that cannot be undone is a reconnection fee.
SAME CODE, TWO
FLOWS
Start and stop are the same four-step component with different steps configured — stepper, read-back, change links, the what-happens-next panel
and the refusal behaviour are one implementation. Only the fields and the copy differ, which is why they are drawn as two flows and built as one.
STATES
BALANCE OUTSTANDING
Says what is owed and that it
moves to the final bill. Never
blocks the stop.
LANDLORD ACCOUNT
Says service reverts to the owner
rather than closing.
CONFIRMED
A reference, the four dates by
email, and the request appears
under Your requests.
AUTOPAY OFF
The amber panel is absent
entirely.
COMPONENTS
PortalFrame
Stepper
ReadBack
Timeline
Callout warn
24
Your final bill
EXISTS BEHIND
COMMITMENT CPB-23
tenantportalfinalbill
No door named.
 This screen carries no 
How you get here
 row, though the document's own rule E
says every screen does. It is one of 37. See 
CPB-23
.
24
 Your final bill 
tenantportalfinalbill
The question:
 I moved out three weeks ago — is that everything, and where is my deposit?
PHONE · 390
DESKTOP · 1280

═══════════ PAGE 46 ═══════════

 Home
Your final bill
1841 Quarry Hill Ct · closed Sep 30, 2026
COMING BACK TO YOU
$63.80
to bank ····4417, by Oct 30
HOW IT WORKED OUT
Final bill · Sep 1 – Sep 30
$86.20
Deposit held
−$150.00
Owed to you
$63.80
WHERE THE BILL WENT
220 Lakeview Dr, Burnet, TX 78611 — the
forwarding address you gave us.
↓ Download the final bill · Your account is now closed.
Silver Creek Water
Home
Bills
Usage
Payments
Requests
Help
My details
🌐
 English 

  ·  Sign out
Marcus Bell  ·  1841 Quarry Hill Ct, Silver Creek, TX 78611  ·  Account 
4417-0092
$191.00 due Aug 22

 Home
Your final bill
1841 Quarry Hill Ct, Silver Creek, TX 78611 · account closed Sep 30, 2026
THE FINAL BILL · SEP 1 – SEP 30, 2026
Electric · 412 kWh
$62.88
Water · 3 kgal
$18.35
Sewer · 2.7 kgal
$13.50
Move-out final read
$20.00
Trash · stopped Sep 30, 20 of 30 days
−$28.53
Final bill
$86.20
AND THEN
Deposit held since Jun 2, 2026
−$150.00
Coming back to you
$63.80
YOUR REFUND
$63.80
To bank account ····4417, by 
Oct 30, 2026
— 30 days from the final bill, as the rules
require.
WHERE WE SENT IT
220 Lakeview Dr, Burnet, TX 78611 — the
forwarding address you gave when you
stopped service.

 That is wrong — change it
↓ Download the final bill · This account is
closed and no further bills will be sent.
FOR
The last thing a leaving customer sees. It answers "is that everything" and "where is my deposit" without a call.
COGNITIVE LOAD
The refund is the headline, not the bill, because that is what they came for. The proration is itemised — "stopped Sep 30, 20 of 30 days, −$28.53" —
since a part-month charge is the commonest final-bill dispute.
THE FORWARDING
ADDRESS
Shown, with a way to correct it. A refund sent to the address they left is the most expensive small failure in the whole product.
STATES
YOU OWE US
Same layout inverted: the amount
dueistheheadlinewiththeways
REFUND SENT
Says the date it went and when to
expectitinthebank
NO DEPOSIT
The deposit row is absent, not
shownas$000—nothingwas
ESTIMATED FINAL READ
Says so and that the figure may
changeoncethemeterisread

═══════════ PAGE 47 ═══════════
due is the headline, with the ways
to pay.
expect it in the bank.
shown as $0.00 — nothing was
ever held.
change once the meter is read.
COMPONENTS
PortalFrame
Callout ok
ChargeLine
AddressField
Commitments in this section
Each card names what the work waits on and what a person could do once it is done. Nothing
outside a card is undertaken.
None.
```

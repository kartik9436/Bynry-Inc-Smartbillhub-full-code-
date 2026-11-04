# 15 · Customer Web Portal — the 18 end-to-end journeys

**Ids `J30` … `J47`.** `J1`–`J29` are the existing cross-module journeys and
`T3M-001`–`T3M-279` are the generated billing matrix; **next free was `J30`**, verified
2026-09-03.

⚠ **THE JOURNEY FILES IN `08-qa/01-e2e/journeys/` ARE NOT WRITTEN YET.** This file is the
authoritative description of all eighteen and the reservation of their ids; the
executable journey files are the next step and are named in
`12-governance/14-id-reservations.md` so no other lane takes the block. **A story's
`journeys:` frontmatter cites an id described here — do not read that as a file that
exists** (hard-won law 1: a citation claiming a guarantee is not the guarantee).

**Every journey below crosses modules, so every one has a handoff contract**: what
upstream leaves in the database for it, and what it must leave for downstream. Coding a
story without its journeys loaded is a prime-directive violation.

---

## Release 1 — the public front

### `J30` · Guest pays a bill they are holding
**Actor:** somebody with a paper bill and no account · **Screens:** `CWP-001` → `002` →
`003` → `004` · **Modules:** billing → payments → ledger → notifications
⚠ **RELEASE 5, NOT 1** — drawn here because it is the quick-pay journey and it belongs
beside `J31`. It cannot run until rails land.
**Upstream leaves:** an issued bill `BL-2608-0141`, `$142.18` owing, service postcode
`78702`. **This journey leaves:** one payment row, allocated by the utility's rule, one
audit entry, one receipt document, and **no account**. **The assertion that matters:**
the name renders `M. A••••••` and the response body contains no other field of the
customer record.

### `J31` · Guest reports a burst main and tracks it to *crew on site*
**Screens:** `CWP-006` → `007` → `012` · **Modules:** portal → customers (requests) →
metering (interruption)
**Leaves:** an `interruption` row with free-text location, an affected area of
*Elm St, 1400–1500*, a service request on the clerk's worklist carrying channel
`customer_portal`, and reference `RP-26-0412` on screen.
**Three assertions:** the reporter is **not** a customer and it still works · the
sixty-first submission in a minute is refused · `gas_smell` returns a phone number and
creates **nothing**.

### `J32` · *Can I get service here* → apply → paperless consent
**Screens:** `CWP-008` → `CWP-047` → `CWP-009` · **Modules:** portal → tenancy
(premises) → rating (fees) → customers (request) → portal (consent)
**Upstream leaves:** premises `31 Palm Ct` with Water/Sewer/Trash available and Electric
absent; connection fee `$185.00`, deposit `$150.00`.
**Leaves:** a draft request that survives a closed tab, then on submit a reference, a
document checklist in `AFTER YOU APPLY` state, **and a `portal_consent` row with its
wording version**. ⚠ **Nothing is charged today** and no document is demanded up front.

### `J33` · Guest reads an answer and ends at a person
**Screens:** `CWP-011` → `CWP-011/{slug}` → `CWP-054` · **Modules:** tenancy (content) →
customers (request)
**Assertions:** eight answers exist and **six** are shown — the draft and the not-shown
never leave the back office · a French reader (this said *Spanish* until 2026-09-03 — `DEF-CWP-3605`; the fixture's Spanish is PUBLISHED and its French NEEDS TRANSLATING) with no `fr` variant gets **English, not
a blank** · the answer ends in a route to a person, and pressing *No* is counted
separately from opening it.

### `J34` · Where you can walk in, on a day one counter is closed
**Screens:** `CWP-013` → `CWP-014` · **Modules:** tenancy (centres + holiday calendar)
**Assertions:** three centres exist and **two** are shown — the depot is `hidden`, which
is a state and not a deletion · the north counter reads *"Closed today · Opens Thursday
at 9:00am"* from the clock (its hours are Tue & Thu and 2 September 2026 is a Wednesday — the drawing said *Tuesday*, `DEF-CWP-3604`) · on Thanksgiving **both** read closed with nobody editing
the page · and four of the five action rows on `CWP-014` say **no**, which is the screen
doing its job.

### `J46` · An answer authored, published, read under a bill, voted on
**Screens:** `CWP-072` → `CWP-011` → `CWP-060` → `CWP-071`(back office) ·
**Modules:** tenancy → portal → tenancy
**Leaves:** the read count moves `1,204` → `1,207` and a *No* vote lands as its own
event. ⚠ **The whole point of the smallest write in the portal**: without it the back
office's read column is a column of zeroes and the utility cannot tell which answer is
doing the work.

## Release 2 — see everything, pay nothing

### `J35` · A billed customer who has never signed in, enrols cold
**Screens:** `CWP-015` → `016` → `017` → `018` → `022` · **Modules:** portal → customers
→ notifications
⚠ **The security journey.** Between *account matched* and *identity proven* the portal
knows which account is meant and has told the visitor **nothing**.
**Assertions:** three wrong tries locks fifteen minutes · the code goes **only** to the
`••• ••• 4218` already on file and never to an address typed on the previous screen · an
account with no phone and no email **dead-ends into "ring the office"** · the
consequence panel names the account, the services and the `$142.18` before the button.

### `J36` · The eleven-month cold return
**Screens:** `CWP-015` → `022` → `027` → `028` → `029` · **Modules:** portal → billing
**Upstream leaves:** four bills, one of them corrected and pointing at its replacement.
**Assertions:** the balance tile reads `$142.18` with *"Due 14 Sep · in 12 days"* · the
corrected bill `BL-2606-0137` **stays in the list**, greyed, naming `BL-2606-0147` ·
`owing` and `amount` are different columns · the PDF served is the file that was issued.

### `J37` · A landlord across four accounts, master over common areas
**Screens:** `CWP-020` → `023` → `022` · **Modules:** portal → customers → billing
**Upstream leaves:** one customer, four accounts — `$142.18`, `$0.00`, `$318.04`,
`$412.60` — one of them a master over common areas.
**Assertions:** the four total to **`$872.82`** and are **never merged into one invoice**
· the master is **one flat entry**, not a parent · switching accounts reloads every tab ·
and the tenants' own accounts are **not in the set** (`OQ-1397` until ruled).

## Release 3 — ask us for things

### `J39` · A self-read: submitted, validated, reviewed, billed, superseded
**Screens:** `CWP-035` → `034` → next bill run · **Modules:** portal → metering →
billing · ⚠ **blocked on `OQ-1393`**
**Assertions:** `158940` on a meter last read at `153040` is flagged against the
account's own `155 gal/day` — **about nineteen times usual, not eight** (the blueprint's
own §26 corrects that figure) · it can be sent anyway · it lands `awaiting_review` and
appears **on no bill** until a clerk clears it · **a later real read supersedes it and
the customer is not charged twice** · and it ran through the **same** validation service
a staff read runs through.

### `J40` · Move-out → final bill → deposit settled → refund sent
**Screens:** `CWP-046` → `048` → `032` → `045` · **Modules:** portal → customers →
metering → billing → payments → ledger · ⚠ **`OQ-1392`** on whether the customer may
close or only ask
**Leaves:** service to 17 September `$63.40`, deposit `−$150.00`, interest `−$3.20`, so
**`$89.80` owed to the customer** — a refund, **not a credit to carry forward**, because
there is no next bill.
⚠ **The danger-tier commit**, and the screen must state the distinction customers get
wrong: a move-out closes and settles; a disconnect leaves the account open and standing
charges keep running.

### `J45` · Paperless consent taken, then withdrawn
**Screens:** `CWP-009` → `025` · **Modules:** portal → notifications
**Assertions:** the consent carries a timestamp **and the wording version they saw** · it
is **never dated in the future** · withdrawal is one control away and the row is not
deleted · **existing paperless customers are never asked again** · and the
always-print column is honest rather than an off switch that does nothing.

### `J47` · A notice sent, a notice NOT sent, and post that came back
**Screens:** `CWP-068` → `031` → `024` · **Modules:** notifications → portal ·
⚠ **blocked on `OQ-1399`**
**Assertions:** `CWP-068` shows *"Final notice · 15 Sep · post · not sent, no forwarding
address"* — **the notice that never arrived is the one most visible** · two returned
letters show **above** the address field on `CWP-024` and fixing the address clears it ·
and a portal row is a record that a message **exists**, never proof it arrived.

## Release 4 — help before it goes wrong

### `J38` · The bill that went up → comparison → a query that holds the account
**Screens:** `CWP-028` → `030` → `055` → `034` · **Modules:** billing → rating →
metering → customers
**Assertions:** the four comparison lines `+$8.83`, `$0.00`, `+$4.29`, `−$9.38` sum to
**exactly** the `+$3.74` between `$138.44` and `$142.18` · the query **holds collection
on `$142.18`** and no late fee accrues · the bill itself **does not change** · the
disputed reading of 31 August carries a marker · and if the utility agrees the outcome
is a **corrected bill, a new document**, with the original still in the list.

### `J41` · A plan the customer asks for, and keeps
**Screens:** `CWP-057` → `042` → `043` · ⚠ **`OQ-1391`** · **on an account `$172.20` in arrears** — `CWP-057` is DRAWN with `$412.60`, which is `J43`'s `22 Palm Ct` fixture; the plan arithmetic every story signs is on `$172.20` (2026-09-03, `DEF-CWP-3606`)
**Assertions:** six months over `$172.20` with `$40.00` up front gives **five
instalments of `$22.03` and a final `$22.05`, totalling `$132.20`** — the remainder on
the last one, shown · late fees stop **only if the clerk left that election on** · **new
bills still arrive and still have to be paid** · two missed instalments end it and the
whole balance falls due.

### `J42` · A plan the utility offered, accepted on the customer's signature
**Screens:** `CWP-063` → `043` → `053` · **Modules:** payments → portal → notifications
⚠ **THE JOURNEY THE BLUEPRINT'S §17 AUDIT WAS WRITTEN FOR.** A clerk builds a plan, the
row sits at `agreement_sent`, and **the customer cannot see it, cannot accept it, and
hears about it only if somebody rings them.**
**Leaves:** `agreement_sent` → `active` **with the customer's signature date on it**, and
instalment 1 of 6 reading *To come*. **Assertion:** the offer expires 16 September and
after that the office must set it up again.

### `J43` · Overdue: the ladder, its cost, and the three protections
**Screens:** `CWP-057` → `056` → `064` · **Modules:** billing → customers → portal
**Assertions:** `$412.60` overdue by 19 days, first notice already sent 1 September, and
**"If it goes that far `$657.60`"** — `$412.60` plus a `$95.00` reconnection fee plus a
`$150.00` new deposit — beside a button that stops it · the three protections carry
**three different lifetimes and three different sentences** — a certificate that **ends
30 November**, a plan hold with **no date** that lifts the day an instalment is missed,
and a moratorium `1 December`–`1 March` **with no button at all** · ⚠ **and a customer at
the five-day notice is NEVER rendered as being at the ten-day one.**

### `J44` · A delegate is invited, acts, and is named in the audit
**Screens:** `CWP-026` → `021` → any pay or request · ⚠ **`OQ-1396`**
**Leaves:** a `portal_delegate` row reading *"Common areas · See · Download · 30 Jun
2027 · Invited"*, then after the bookkeeper **downloads a bill and adds a note to a request** — both inside *See · Download*, a set that holds no *Pay*; *Pay* itself is held until release 5 (this said *pays a bill* until 2026-09-03 — `DEF-CWP-3607`) — **an audit entry naming Kestrel
Bookkeeping, not Maria Alvarez.**
⚠ **This is the journey that fixes an audit problem the product would otherwise
inherit**: without named delegates every portal action by a family member is recorded as
the account holder, and the audit trail is quietly wrong on exactly the accounts where a
dispute is most likely.

---

## Journey → release → story index

| J | Journey | Release | Stories |
|---|---|---|---|
| `J30` | Guest quick pay | 5 | `US-CWP-003`–`006` |
| `J31` | Report a burst main, track it | 1 | `US-CWP-007`–`010` |
| `J32` | Availability → apply → consent | 1 | `US-CWP-012`–`014` |
| `J33` | Read an answer, end at a person | 1 | `US-CWP-072`, `066` |
| `J34` | Where you can walk in | 1 | `US-CWP-074` |
| `J35` | Enrol cold | 2 | `US-CWP-016`–`021` |
| `J36` | The eleven-month cold return | 2 | `US-CWP-023`, `032`–`034` |
| `J37` | Landlord across four accounts | 2 | `US-CWP-024`, `026`–`027` |
| `J38` | Bill went up → query | 4 | `US-CWP-035`, `065` |
| `J39` | Self-read end to end | 3 | `US-CWP-041`–`042` |
| `J40` | Move-out → final bill → refund | 3 | `US-CWP-037`, `049`, `061` |
| `J41` | A plan asked for | 4 | `US-CWP-051`–`052` |
| `J42` | A plan offered | 4 | `US-CWP-053` |
| `J43` | Overdue and the protections | 4 | `US-CWP-057`–`059` |
| `J44` | A delegate invited and named | 4 | `US-CWP-029`–`030` |
| `J45` | Paperless consent | 3 | `US-CWP-014`, `028` |
| `J46` | Answer authored → read → voted | 1 | `US-CWP-071`–`072` |
| `J47` | Notices sent and not sent | 3 | `US-CWP-028`, `036`, `039` |

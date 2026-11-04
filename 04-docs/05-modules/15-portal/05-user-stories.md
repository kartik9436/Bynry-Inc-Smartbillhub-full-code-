# 15 · Customer Web Portal — the 74 stories

**Epics `EP-CWP-01` … `EP-CWP-12` · Stories `US-CWP-001` … `US-CWP-074`.**
Both families are new and both are **zero-padded to three, chosen at birth** — the
spelling `CWP` screen ids took, allowed because neither series carries a citation yet.
Pattern `US-CWP-\d{3,5}(?!\d)`, and the lookahead is load-bearing (`DEF-2804`).

**Every one of the blueprint's 56 specifications has a home below, and every one of the
79 screens is cited by at least one story.** Checked both ways.

---

## 1 · The twelve epics

| Epic | Name | Stories | Release | Screens |
|---|---|---|---|---|
| `EP-CWP-01` | The public front, and the guard in front of it | 2 | 1 | `CWP-001` |
| `EP-CWP-02` | Quick pay for a guest | 4 | **5** | `CWP-002`–`004` |
| `EP-CWP-03` | Report a problem, and the interruption record | 5 | 1 | `CWP-005`–`007`, `012`, `058` |
| `EP-CWP-04` | Starting service before identity exists | 4 | 1 | `CWP-008`–`010`, `047` |
| `EP-CWP-05` | Getting in | 7 | 2 | `CWP-015`–`019` |
| `EP-CWP-06` | The shell, the account set, and delegated access | 9 | 2 · 4 | `CWP-020`–`026`, `065`, `076`–`079` |
| `EP-CWP-07` | Bills, documents and the explainer | 8 | 2 · 4 | `CWP-027`–`032`, `068` |
| `EP-CWP-08` | Usage, readings and equipment | 5 | 2 · 3 | `CWP-033`–`037` |
| `EP-CWP-09` | Paying, methods and autopay | 6 | **5** | `CWP-038`–`041`, `050` |
| `EP-CWP-10` | Plans, level pay, credits and arrears | 9 | 4 | `CWP-042`–`045`, `056`, `057`, `063`, `064`, `066` |
| `EP-CWP-11` | Requests, messages and disputes | 9 | 3 | `CWP-046`, `048`, `049`, `051`–`055`, `067` |
| `EP-CWP-12` | Published content and the back office | 6 | 1 | `CWP-011`, `013`, `014`, `059`–`062`, `069`–`075` |

⚠ **`EP-CWP-02` AND `EP-CWP-09` ARE RELEASE 5 AND EVERY SCREEN IN THEM SHIPS EARLIER,
HELD.** The Pay control appears in its normal place, disabled, carrying its reason
(`BR-CWP-056`). **Never hidden, and never live-but-inert.**

---

## 2 · A correction to `CR-068` §9 — five screen titles

`CR-068`'s screen table took five of its titles from the blueprint's §16 *"where the
customer meets it"* column rather than from the screen headings, and three of them are
shifted by one. **The ids do not move; the titles below are the blueprint's own.**

| CWP | Blueprint | `CR-068` §9 says | The blueprint's actual heading |
|---|---|---|---|
| `CWP-013` | `G13` | *One centre, its hours and its limits* | **Where you can walk in** |
| `CWP-014` | `G14` | *Pay in person, from Pay now* | **One service centre** |
| `CWP-060` | `P46` | *Under a bill, when it is attached* | **One answer** |
| `CWP-061` | `P47` | *Tips* | **An answer where the question is asked** |
| `CWP-062` | `P48` | *Nothing at all when none is live* | **A tip where it lands** |

**And four screens `CR-068` never numbered** — the blueprint's §26 admits they *"were
never counted"*:

| CWP | Blueprint | Screen |
|---|---|---|
| `CWP-076` | `M1` | Phone · Home — the balance and one button |
| `CWP-077` | `M2` | Phone · Pay — two fields, one consequence box |
| `CWP-078` | `M3` | Phone · A reading — standing at the meter |
| `CWP-079` | `M4` | Phone · Overdue — three ways out |

**Next free ground after this module: `CWP-080`.** Nothing is renumbered.

**Where to look for a screen's layout.** Every story names its screens by `CWP` id; the
picture of each is `wireframes/CWP-###.png`, the layout written from that picture is the
matching entry in `08-screen-layouts.md` (frame, template, regions top-to-bottom,
components), and every component named there is defined once, as Tailwind, in
`09-component-inventory.md`. A builder opens all three beside the story — the wireframe is
what hard-won law 6 says to diff the running app against. Where a drawing and a B14 rule
disagree, B14 wins and the layout entry says so.

---

## 3 · The 74 stories

`R` is the release. `⚠` marks a story that must be implemented **to the boundary and
stubbed** — `raise NotImplementedError("OQ-####")` — because a question it needs is
open.

### `EP-CWP-01` · The public front, and the guard in front of it

| Story | Title | Screens | Spec | R | Blocked by |
|---|---|---|---|---|---|
| `US-CWP-001` | The public front page — six errands, and sign-in as one card among them | `CWP-001` | `CP-36` | 1 | — |
| `US-CWP-002` | The anonymous throttle, and a fifteen-minute lockout on the two lookups worth guessing at | `CWP-002`, `CWP-012` | `CP-37` | 1 | — |

### `EP-CWP-02` · Quick pay for a guest

| Story | Title | Screens | Spec | R | Blocked by |
|---|---|---|---|---|---|
| `US-CWP-003` | Find the bill on a number and a postcode | `CWP-002` | `CP-07` | 5 | — |
| `US-CWP-004` | Check and pay, and the masked name that makes it safe | `CWP-003` | `CP-07`, `CP-08` | 5 | rails |
| `US-CWP-005` | Paid — a reference to keep, and the offer of a login | `CWP-004` | `CP-08` | 5 | rails |
| `US-CWP-006` | An idempotent inbound payment webhook | — | `CP-09` | 5 | `CP-08` |

### `EP-CWP-03` · Report a problem, and the interruption record

| Story | Title | Screens | Spec | R | Blocked by |
|---|---|---|---|---|---|
| `US-CWP-007` | Report a problem — and the reporter need not be a customer | `CWP-006` | `CP-13` | 1 | — |
| `US-CWP-008` | The interruption record and its affected-area rule | — | `CP-15` | 1 | — |
| `US-CWP-009` | Report sent — a reference a stranger can keep and look up | `CWP-007` | `CP-13`, `CP-14`, `CP-25` | 1 | — |
| `US-CWP-010` | Track anything — progress, and never data | `CWP-012` | `CP-14` | 1 | — |
| `US-CWP-011` | Outages and planned work | `CWP-058`, `CWP-005` | `CP-16` | 1 | ⚠ field-work scope `OQ-249` |

### `EP-CWP-04` · Starting service before identity exists

| Story | Title | Screens | Spec | R | Blocked by |
|---|---|---|---|---|---|
| `US-CWP-012` | Can I get service here — availability, fees and deposits, read publicly | `CWP-008` | `CP-11`, `CP-12` | 1 | — |
| `US-CWP-013` | About you — the applicant, and recognising a returning customer | `CWP-047` | `CP-13` | 1 | — |
| `US-CWP-014` | Check and send — and where paperless consent is taken | `CWP-009` | `CP-13` | 1 | — |
| `US-CWP-015` | Ask for a quick service | `CWP-010` | `CP-13` | 1 | — |

### `EP-CWP-05` · Getting in

| Story | Title | Screens | Spec | R | Blocked by |
|---|---|---|---|---|---|
| `US-CWP-016` | The front door — three doors stated as three doors | `CWP-015` | `CP-01` | 2 | — |
| `US-CWP-017` | Find my account, on three facts printed on the bill | `CWP-016` | `CP-01` | 2 | — |
| `US-CWP-018` | Prove it is you — a code, to a contact already on file | `CWP-017` | `CP-02` | 2 | — |
| `US-CWP-019` | Choose a password, and see what the login will let you do | `CWP-018` | `CP-01`, `CP-02` | 2 | — |
| `US-CWP-020` | Forgotten password — answered the same way either way | `CWP-019` | `CP-03` | 2 | — |
| `US-CWP-021` | The customer credential store and the portal session | — | `CP-01` | 2 | — |
| `US-CWP-022` | Step-up before a stored payment method changes | `CWP-039` | `CP-02` | 5 | `CP-08` |

### `EP-CWP-06` · The shell, the account set, and delegated access

| Story | Title | Screens | Spec | R | Blocked by |
|---|---|---|---|---|---|
| `US-CWP-023` | The portal shell — the utility's branding, an account switcher, six tabs | every `P` screen | `CP-06` | 2 | — |
| `US-CWP-024` | A balance read, per account and totalled across a login | `CWP-022`, `CWP-023` | `CP-05` | 2 | — |
| `US-CWP-025` | Portal home — one number, one date, one button | `CWP-022` | `CP-05`, `CP-18`, `CP-32`, `CP-43`, `CP-53` | 2 | — |
| `US-CWP-026` | All my accounts — four balances, totalled, never merged | `CWP-023` | `CP-05`, `CP-54` | 2 | ⚠ `OQ-1397` |
| `US-CWP-027` | Add another account to this login | `CWP-020` | `CP-06` | 2 | — |
| `US-CWP-028` | My details — what a customer may edit, and what they may not | `CWP-024` | `CP-35`, `CP-50` | 2 | — |
| `US-CWP-029` | People with access — a permission set, an expiry, and their own audit actor | `CWP-026` | `CP-04` | 4 | ⚠ `OQ-1396` |
| `US-CWP-030` | Accept an invitation, stated in both directions | `CWP-021` | `CP-04` | 4 | ⚠ `OQ-1396` |
| `US-CWP-031` | Your account — the deposit we hold, the exemption that lapses, the history | `CWP-065` | `CP-43`, `CP-45`, `CP-53` | 2 | — |

### `EP-CWP-07` · Bills, documents and the explainer

| Story | Title | Screens | Spec | R | Blocked by |
|---|---|---|---|---|---|
| `US-CWP-032` | Your bills — and owing is a separate column from amount | `CWP-027` | `CP-44` | 2 | — |
| `US-CWP-033` | One bill, line by line, grouped by service, every unit named | `CWP-028` | — | 2 | — |
| `US-CWP-034` | The bill as it was printed | `CWP-029` | `CP-06` | 2 | — |
| `US-CWP-035` | Why this bill is different — and the lines must sum to the difference | `CWP-030` | `CP-24` | 4 | — |
| `US-CWP-036` | Documents and letters — what we sent, when, and by which route | `CWP-031` | `CP-28`, `CP-49`, `CP-50` | 2 | — |
| `US-CWP-037` | Your final bill — where the deposit comes back | `CWP-032` | `CP-10`, `CP-27`, `CP-43` | 3 | — |
| `US-CWP-038` | A statement, or the transaction list named as one | `CWP-031`, `CWP-041` | `CP-28` | 3 | ⚠ `OQ-1395` |
| `US-CWP-039` | Every notice sent, and every notice deliberately not sent | `CWP-068` | `CP-49`, `CP-50` | 3 | ⚠ `OQ-1399` |

### `EP-CWP-08` · Usage, readings and equipment

| Story | Title | Screens | Spec | R | Blocked by |
|---|---|---|---|---|---|
| `US-CWP-040` | Usage — and the services that are not measured say so | `CWP-033` | `CP-04`, `CP-32` | 2 | — |
| `US-CWP-041` | Every reading, how it was taken, and why one was corrected | `CWP-034` | `CP-19`, `CP-20`, `CP-55` | 2 | — |
| `US-CWP-042` | Send your own reading — one validation, two sources | `CWP-035` | `CP-19` | 3 | ⚠ `OQ-1393` |
| `US-CWP-043` | Meters and equipment at the property | `CWP-037` | `CP-51` | 2 | — |
| `US-CWP-044` | Your usage looks high | `CWP-036` | `CP-29` | — | ⚠ no trigger exists |

### `EP-CWP-09` · Paying, methods and autopay

| Story | Title | Screens | Spec | R | Blocked by |
|---|---|---|---|---|---|
| `US-CWP-045` | Pay now — and where the payment will land, before it commits | `CWP-038` | `CP-08`, `CP-09`, `CP-48` | 5 | rails |
| `US-CWP-046` | Your payment methods — a token, never a card number — and why a control is refused | `CWP-039`, `CWP-040` | `CP-08`, `CP-48` | 5 | rails · ⚠ `OQ-1394` |
| `US-CWP-047` | Autopay — an intent that already exists, waiting for a charge that does not | `CWP-040` | `CP-08` | 5 | rails |
| `US-CWP-048` | Payments and receipts — and a bounce is two rows | `CWP-041` | `CP-09`, `CP-44`, `CP-47` | 2 | — |
| `US-CWP-049` | Refunds returned to the method the money came in on | `CWP-045` | `CP-10` | 5 | rails |
| `US-CWP-050` | Collecting a connection fee | `CWP-050` | `CP-38`, `CP-52` | 5 | rails |

### `EP-CWP-10` · Plans, level pay, credits and arrears

| Story | Title | Screens | Spec | R | Blocked by |
|---|---|---|---|---|---|
| `US-CWP-051` | Ask for a payment plan — and the last instalment carries the rounding | `CWP-042` | `CP-21` | 4 | ⚠ `OQ-1391` |
| `US-CWP-052` | Your payment plan, whole — not a monthly summary of it | `CWP-043` | `CP-21`, `CP-39`, `CP-40` | 4 | — |
| `US-CWP-053` | A plan the utility has offered you, and your signature on it | `CWP-063` | `CP-39` | 4 | — |
| `US-CWP-054` | Level pay — pay the same amount every month | `CWP-044` | `CP-46` | 4 | — |
| `US-CWP-055` | Where your level pay stands | `CWP-066` | `CP-46` | 4 | — |
| `US-CWP-056` | Credits and refunds in flight — and they are different things | `CWP-045` | `CP-10`, `CP-27` | 4 | — |
| `US-CWP-057` | What happens if this is not paid — the ladder, and what it would cost | `CWP-057` | `CP-21`, `CP-22`, `CP-41`, `CP-42`, `CP-47` | 4 | — |
| `US-CWP-058` | Help paying — three doors, and one of them is not a door | `CWP-056` | `CP-21`, `CP-23`, `CP-41` | 4 | ⚠ `OQ-1391` |
| `US-CWP-059` | What is protecting your supply — three lifetimes, three sentences | `CWP-064` | `CP-41`, `CP-42` | 4 | — |

### `EP-CWP-11` · Requests, messages and disputes

| Story | Title | Screens | Spec | R | Blocked by |
|---|---|---|---|---|---|
| `US-CWP-060` | What do you need — six cards, named by what the customer wants | `CWP-046` | `CP-13`, `CP-25`, `CP-56` | 3 | — |
| `US-CWP-061` | Moving out or moving on — and it cannot be undone | `CWP-048` | `CP-56` | 3 | ⚠ `OQ-1392` |
| `US-CWP-062` | Stop or restart service — and the screen names the cheaper option | `CWP-052` | `CP-56` | 3 | — |
| `US-CWP-063` | Track your request — the customer-visible half of the history | `CWP-051` | `CP-14`, `CP-25`, `CP-51`, `CP-52`, `CP-56` | 3 | — |
| `US-CWP-064` | Documents we need from you — the checklist is real, the upload box is not | `CWP-049` | `CP-56` | 3 | upload deferred |
| `US-CWP-065` | Dispute a bill or a reading — a marker, never an edit | `CWP-055` | `CP-20` | 3 | — |
| `US-CWP-066` | Ask a question, attached to the bill it is about | `CWP-054` | `CP-26` | 3 | — |
| `US-CWP-067` | Messages, and the portal as a fourth channel that WAITS | `CWP-053` | `CP-17`, `CP-18`, `CP-29`, `CP-39`, `CP-49` | 3 | ⚠ `OQ-1399` |
| `US-CWP-068` | A visit is booked at the property | `CWP-067` | `CP-51` | 3 | ⚠ field-work scope `OQ-249` |

### `EP-CWP-12` · Published content and the back office

| Story | Title | Screens | Spec | R | Blocked by |
|---|---|---|---|---|---|
| `US-CWP-069` | Portal settings — the address a utility could never find, the switch, and the five | `CWP-069` | `CP-30` | 1 | — |
| `US-CWP-070` | Branding — read from Company → Profile, and stored nowhere twice | `CWP-070` | `CP-30` | 1 | — |
| `US-CWP-071` | Help and answers in the back office — draft, translate, publish | `CWP-071`, `CWP-072` | `CP-31` | 1 | ⚠ `OQ-1398` |
| `US-CWP-072` | Help on the portal — the list, one answer, and the same answer under a bill | `CWP-011`, `CWP-059`, `CWP-060`, `CWP-061` | `CP-31`, `CP-34` | 1 | — |
| `US-CWP-073` | Tips — one slot, in season, and the page closes up when there is none | `CWP-073`, `CWP-062` | `CP-32` | 1 | — |
| `US-CWP-074` | Service centres — and *hidden* is a state, not a deletion | `CWP-074`, `CWP-075`, `CWP-013`, `CWP-014` | `CP-33` | 1 | — |

---

## 4 · Coverage, checked both ways

**All 56 specifications have a story.** `CP-01`…`CP-56`, no orphans.

**All 79 screens are cited.** `CWP-001`–`CWP-079`. The four phone screens are covered by
`US-CWP-023` (the shell renders them) and asserted in `US-CWP-024`, `US-CWP-045` and
`US-CWP-057`.

**Eleven stories are blocked and stub rather than guess:** `US-CWP-011`, `026`, `029`,
`030`, `038`, `039`, `042`, `046`, `051`, `058`, `061`, `067`, `068`. ⚠ **That is
thirteen, not eleven** — two of them (`US-CWP-011`, `US-CWP-068`) are blocked on the
field-work scope question `OQ-249` rather than on one of the nine new ones.

**Two stories carry no `CP-` spec** and are ours, derived and recorded rather than
inherited: `US-CWP-002` (the guard, which the blueprint states as prose in §7 and never
specifies) and `US-CWP-033` (one bill line by line, which the blueprint draws as an
existing capability with no commitment card because nothing needs building behind it).

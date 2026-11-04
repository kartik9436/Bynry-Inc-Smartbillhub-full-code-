# CR-094-BRC01 · step 2 wave K — `ACC-S16`, the communication section

**Built:** 2026-09-12 · **Branch block:** `BRC01` · **Screen:** 02 Account details (S21)
**Commitment, verbatim from the blueprint's own card:** *"A clerk can write to the
customer from the account, and see what has already been sent."*
**Drawing:** `R6`, pages 186–188 of `05-prototype/02 Accounts Menu Blueprint.pdf`
(pinned at `033981d4f`), read as RENDERED PAGES through `10-scripts/pdf/pdf_render.py`
— the text layer of that PDF prints every digit as `&` (CR-094 §3a).

---

## 0 · STEP 0 — IS THE PACKET CURRENT?

Checked, not assumed. What moved under this wave and what it changed:

| where | what it says | does it move this wave |
|---|---|---|
| `BR-NOT-013` (CONFIRMED, PO 2026-08-15) | *"DELIVERY IS OUT OF THIS RELEASE … No provider adapter exists or is coming on ANY channel, **print included**"* | **YES — it is the whole truth of this screen.** See §2 |
| `BR-NOT-010` as amended 2026-09-07 (`CR-084`, `BR-NOT-1031`) | a FIFTH channel, `portal`, *"the first one a customer can be reached on"* | **YES** — it is the one channel on this deployment that reaches a customer |
| `BR-NOT-005` | queue rows only; nothing is ever sent inline | YES — the commit is **Queue**, never **Send** |
| `BR-PAY-035` (CONFIRMED) | reminder tones map to the dunning-tier templates; *"free-text tones do not exist"* | YES — it is why four of the drawing's five kinds are refused here |
| `BR-NOT-008` (CONFIRMED) | a regulated ladder step ALWAYS renders the disconnect class whatever tone was picked | YES — same |
| `DEF-SHL-5116`, `DEF-SHL-5101` | two reds already on the branch | no — **not this lane's**, see §7 |

---

## 1 · WHAT THE DRAWING ASKS FOR — QUOTED, NOT SUMMARISED

`R6 · A Communication action on the account`, chip **NO COMMITMENT**:

> *"An eighth icon on the quick-action rail, and the dialog behind it in two views."*
> Asked for directly: *"add a communication action to the quick action sections. here
> the user can send quick communication to the customer."*
>
> *"Two views, because a collections call has two halves. **Write a message** composes
> one. **What has already gone out** answers the question a customer actually asks
> first."*

**The three product rules the drawing says shaped the form rather than decorating it,
verbatim:**

1. *"**Nothing is ever sent from a screen.** `BR-NOT-005`: the output of every notice
   path is queue rows, and there is no SMTP, ESP, Twilio or print-vendor call anywhere
   in the module. So the commit reads **Queue the message**, not Send, and the dialog
   says where it goes next. A wireframe with a Send button would promise an
   architecture this product has deliberately refused."*
2. *"**Free text does not exist on a regulated step.** `BR-PAY-035` fixes the tone to
   the tier … and `BR-NOT-008` renders the disconnect class whatever tone was picked.
   So the message box is live for a courtesy note and refused, with its reason, the
   moment a ladder step is chosen. What a customer was told has to be provable later."*
3. *"**A text message supplements a letter and never replaces it** (A19 rule 3). On a
   regulated kind the postal channel is ticked and cannot be unticked."*

And the drawing's own statement of the gap:

> *"**What already exists and what does not.** The outbound queue, its search and
> filters, its *failed and bounced first* sort, and **Resend** and **Requeue** are all
> served today. What does not exist is composing a message from an account: there is no
> ad-hoc send path anywhere in the module, which is the one thing `ACC-S16` is asking
> for."*

### 1.1 · The compose view `ACC-C01`, field by field, as drawn

| block | field | as drawn |
|---|---|---|
| WHAT TO SEND | `Kind of message *` | select — *A courtesy message · A payment reminder · A notice about the disconnection · A copy of a bill · Proof of the balance* |
| | `Template` | select — *Free message — you write it · Balance summary · Payment options · We have not heard from you.* |
| WHO IT GOES TO | `Customer` | read-only — *"Bramble Bakery · one contact, no customer record linked"* |
| | `Language` | read-only — *English*, helper *"From the account."* |
| | channel table | CHANNEL · GOES TO · ON FILE? — Email ✓ / Text message / Post. Helper: *"A channel with nothing on file is shown and cannot be ticked, so a clerk can see what is missing rather than wonder why an option vanished."* |
| THE MESSAGE | `Subject` | text, helper *"Shown on email only."* |
| | `Sign it as` | select — the utility · a named clerk · *The billing team* |
| | `Message` | textarea, helper *"Live for a courtesy message."* |
| | checkbox | *Attach the balance as a statement* |
| WHEN | `Queue it *` | select — *Now · On a date I choose* |
| | `On` | date, helper *"Nothing leaves before this date."* |
| REVIEW | recap | *What pressing the button will do* — Kind · Goes to · Channels · Signed · Queued, then the bold pair **It is queued, not sent** / **The outbound queue delivers it**, and *"This screen does not send anything. It writes a row on the outbound queue, and the queue delivers it."* |
| footer | | `Save as a draft` · `Cancel` · `Queue the message` |

### 1.2 · The history view `ACC-C02`, as drawn

Intro *"The first thing a customer asks on a collections call is what they have already
been sent."* · a search box and filters · columns **SENT ▼ · WHAT · CHANNEL · GOES TO ·
STATUS** and a row action · a pagination footer reading *"1–5 of 5 · failed and bounced
first, then newest · Rows per page 50 100"* · `Resend` on the failed row and `Open` on
the rest · the footer pair `Write a message` / `Close`.

Two annotations the drawing puts under the heading **WHAT A SENT MESSAGE DOES NOT TELL
YOU**, and they are constraints rather than copy:

> *"DELIVERED IS THE CARRIER'S WORD, NOT THE CUSTOMER'S. A delivered email reached a
> mailbox. Whether anybody opened it is not recorded, and this screen will not imply
> that it was."*
> *"A POSTED LETTER HAS NO DELIVERY DATE. Post is queued and handed to a print vendor;
> there is no confirmation to show except on certified mail, which has its own
> register."*

⚠ **The drawing's STATUS cells read `Delivered 09/12` and `Failed — number not
reachable`. Those are ILLUSTRATIONS (B14 rule 37) and this product cannot write
either** — see §2. The screen shows the vocabulary the code actually holds.

---

## 2 · THE ONE THING THAT DECIDES THIS WHOLE WAVE — WHAT REALLY HAPPENS TO A QUEUED MESSAGE

**Measured in the code, not read off a docstring** (hard-won law 1, and the docstring
here is out of date in the safe direction):

* `apps/notifications/provider_seam.py` resolves the vendor adapter as
  `apps.integrations.services.dispatch_outbound_batch`. **That function does not exist.**
  Grepped across `06-backend/`: **11 hits, every one of them a test monkeypatching it
  with `raising=False`, and none in `apps/integrations/`.** `apps/integrations` has
  grown to **14,722 lines** since the seam's docstring called it *"three docstrings and
  no code"* — so the docstring's REASON is stale and its CONCLUSION is still exactly
  right.
* So on this deployment **post, email and text message rest `queued` forever.**
  `BR-NOT-013` rules that this is correct output and not a defect.
* `in_app` delivers to the utility's own STAFF. **`portal` is the one channel that
  reaches a CUSTOMER** — this application is its provider (`BR-NOT-1031`, 2026-09-07).
* `delivered` and `bounced` are named in `delivery_ops.UNPOPULATED_STATUSES` as the two
  statuses **nothing in this repo can write**, on any channel.

**Consequence, and it is the reason this screen is worth building at all rather than a
reason not to:** a clerk on a collections call needs to know what was *written*, on
which route, and that nothing has *arrived*. A screen that said *"we emailed you"*
would be wrong on this deployment for every account. So:

* the commit button says **Queue the message**;
* the recap says **it is queued, not sent** — the drawing's own words, kept;
* the recap's second half does **not** claim *"the outbound queue delivers it"* on a
  channel with no provider. It names what is true of the channel chosen, from
  `provider_seam.channel_route`, which is data the product already computes.

This is a BUILD to a signed rule, not a value chosen for an open question: the absence
of sending is `BR-NOT-013`, CONFIRMED by the PO on 2026-08-15 and narrowed twice since.

---

## 3 · WHAT IS REUSED RATHER THAN REBUILT

| what the drawing needs | what already exists | new code |
|---|---|---|
| *What has already gone out* — list, search, filters, sort, pagination | `GET /outbound` with `f.account_id` — `selectors.queue_list_queryset`, triage sort *failed+bounced first, then newest*, `core.pagination.ListParams` | **none on the server** |
| its client | `getOutbound()` in `endpoints.ts`, which already declares `account_id` among its filters | none |
| Resend / Requeue | `POST /outbound/{id}/resend`, `/requeue` + their clients | none |
| the WRITE | `notifications.services.queue_document` — the ONLY writer of `outbound_messages` | a new entry point beside `customer_events.queue_account_closed`, and one line in the existing `apps/customers/notifications_seam.py` |
| rendering + the template pin | `template_service` / `rendering`, `catalogs.LISTINGS`, `seed_templates` | one seeded template class |
| the eighth icon | `AccountIconRail.tsx` — its `actions` prop is a `Record` over the ids, so an eighth that is not wired **does not compile** (hard-won law 2's shape, already built) | one id |

---

## 4 · WHAT THIS WAVE DELIBERATELY DOES NOT BUILD, AND WHY

1. **The four regulated kinds** — *a payment reminder · a notice about the
   disconnection · a copy of a bill · proof of the balance*. A payment reminder and a
   disconnection notice are the collections LADDER's acts: `BR-PAY-035` fixes the tone
   to the tier and `BR-NOT-008` fixes the class, and the ladder writes a
   `NoticeHistory` row that a queue row written from this dialog would not have. A
   notice with no tier and no history row is exactly the thing the drawing's own rule 2
   exists to prevent — *"what a customer was told has to be provable later."* They are
   offered and **refused by name with their reason on screen**, `BR-SHL-025`'s shape.
2. **Collapsing `Send statement` into this dialog.** The drawing raises it and declines
   to answer: *"collapsing a control a clerk already knows is a decision for the PO and
   not for a drawing."* Eight icons, not seven.
3. **Documents on an account** (`ACC-S8`) and **the thirteen quick actions**
   (`ACC-S14`) are other waves. Not touched.

---

## 5 · THE SPACING AND THE WORDS

B14 rule 39 (20px between fields, 16 between blocks, label → input → helper), rule 16
(every list carries its pagination footer), rule 32 (one sentence per section, no rule
id in clerk-facing copy), rule 33 (a label ≤ 3 words · a fact ≤ 6 · an instruction ≤ 6
per sentence · rationale is ZERO words on screen), rule 21 (Tailwind utilities, and the
new file is listed in `route-b-migrated.txt` in the same commit), rule 31 (no database
id is ever a visible value).

⚠ Rule 33 is why the drawing's *"Every row here is a row on the outbound queue"* (10
words, and rationale) is **not** rendered, and why the two amber annotation boxes are
constraints on what the screen may claim rather than paragraphs to print.

---

## 6 · WHAT WAS BUILT, AND WHAT IT MEASURED

| | |
|---|---|
| new server endpoints | **1** — `GET\|POST /accounts/{id}/communication` |
| new server READS for the history | **0** — `GET /outbound` with `f.account_id` already served it |
| new source kind | **1** — `message`, with NO print floor (see §4 below) |
| new template class | **1** — `account_message`, seeded; the library goes 38 → 39 listed, 33 → 34 seeded |
| rail glyphs | **7 → 8**, the new one first, live from its first commit |
| catalogue keys | **60**, in all eleven languages, each written in its own language |
| backend cases | **13**, all green · **3** guards proved RED first |
| DOM cases | **5**, all green · **2** guards proved RED first |
| neighbouring cases amended | **5** in `AccountDetailPage.test.tsx` + **3** counts in the notifications suites, each with its reasoning |

### 6.1 · THE MEASUREMENT THAT DECIDED THE SCREEN'S WORDS

`provider_seam` resolves the vendor adapter as
`apps.integrations.services.dispatch_outbound_batch`. **That function exists
nowhere in `apps/integrations`** — its **11** occurrences across `06-backend/`
are all tests monkeypatching it with `raising=False`. So post, email and text
rest `queued`, the commit reads **Queue the message**, and every channel row
carries `delivers`, served from the same `channel_route` the dispatcher branches
on. `BR-NOT-013` rules that correct output rather than a defect.

### 6.2 · WHY `message` AND NOT `account`

`account` carries the `BR-NOT-024` PRINT FLOOR. Filing a clerk's one-line email
under it would have **posted a letter with every message**, for ever. Proved by
doing it: the suite goes red with `assert {'email', 'pdf_print'} == {'email'}`.

### 6.3 · WHAT THIS WAVE GOT WRONG, RECORDED RATHER THAN TIDIED

* **Two class names that compile to nothing.** `text-muted` and `hover:text-fg`
  are not theme keys. `tsc` passed, every DOM assertion passed, and the text
  would have rendered at the default colour. `routeBUtilities.test.ts` named
  both — which is precisely what the migration ledger is for (skill §7.1).
* **A duplicate defect row, caught before it was published.** This lane filed
  `DEF-CUS-5126` for the Meters-tab red and a sibling had filed the same finding
  minutes earlier as `DEF-CUS-5124`, from the same commit and by the same
  worktree method. The row was removed from the working copy by a BYTE-SPLICE
  with the prefix proved byte-identical; the id is abandoned, not reused.
* **A push refused, correctly.** `push_paths.sh` refused the first frontend push
  because a sibling had landed wave I under it. Every file was re-derived on the
  new tip and re-proved there before the second attempt.

### 6.4 · OWED

* **The running product was not driven in a browser.** Hard-won law 6's diff
  against the prototype is this wave's gap and is stated rather than implied.
* **`Send statement` is still its own glyph.** `R6` raises whether it should
  collapse into this dialog and declines to answer: *"collapsing a control a
  clerk already knows is a decision for the PO and not for a drawing."* Eight
  glyphs, not seven-with-one-folded-in. Left as the drawing left it.

---

*Written before the code, per step W's timing rule. §6 was added as the build
proved things.*

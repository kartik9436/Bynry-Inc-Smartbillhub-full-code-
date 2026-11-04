# The move-in review's *What goes out* table — `DEF-CUS-6365`, item 7 of twenty

**Built 2026-09-24**, lane MOVEIN-WIZ. Closes `DEF-CUS-6365`. Screen `ACC-05`
step 6. Drawing: `05-prototype/02 Accounts Menu Blueprint.pdf` **p077, read AS
AN IMAGE at scale 5** (B14 rule 42), continuing onto p078's top.

The PO, verbatim, on their own screenshot:

> *"reduce this text; As per drawing you are not showing consumer communication
> related items email, contract, text , inapp message taht will be sent to
> cutomer once move-in is approve"*

…and the whole twenty-item list confirmed the same day: *"all these issues are
correct - fix it"*.

---

## 0 · What was on the screen before, measured

| what p077 draws | what `ACC-05` step 6 did on 2026-09-24 morning |
|---|---|
| a table headed *What goes out to the customer*, one row per message | a two-row definition list headed *What we'll send*, **typed into the wizard** |
| CHANNEL per row, read from the utility's own notification rules | `Email — not sent` and `Document — not produced`, fixed strings |
| TEMPLATE per row, the version the queue row would pin | nothing at all |
| — | a **60-word** paragraph, *What this move-in will not write* |
| — | a **57-word** block, *Nothing is delivered to the customer* |

**Both prose blocks were RATIONALE, which B14 rule 33 puts at ZERO words on
screen** — and both had clauses that had quietly become false. *"It does not …
commit an opening meter reading"* was written before step 3 grew a reading
table (`DEF-CUS-6362`, the day before); *"neither of the two above is sent,
queued or mailed"* was written before notifications grew in-app, a mailbox and
sender configuration. That is the defect's own `escape_reason`: a refusal
written when nothing existed, never re-read as the thing arrived.

---

## 1 · What is built

**A component, not a section of the wizard** (B14 rule 43):
`07-frontend/src/features/customers/MoveInMessages.tsx`, mounted by
`MoveInWizard.tsx`'s `ReviewStep`. It reuses `MoveMatrix` — the table the
move-out's own *What we will send* already draws — so the two move screens
cannot acquire two table styles.

Six columns, p077's own: **SEND · WHAT IT SAYS · TO · CHANNEL · TEMPLATE ·
WHEN**. Every cell but the heading comes from the server.

The read is `GET /move-ins/messages?category=&deposit_taken=&deposit_cleared=`
→ `customers.notifications_seam.move_in_message_plan` →
`notifications.customer_events.move_in_message_plan`, which decides each row
with **the same calls the save makes** — `services.channel_decision` per event
and `template_service.resolve` per class. The review and the queue therefore
cannot disagree.

| row | what it is | how its channels are decided |
|---|---|---|
| `move_in_welcome` | *The new account and its number* | `channel_decision(move, EMAIL, event_key=move_in_welcome)` — a move has no print floor, so a utility that switched the event off gets an empty list |
| `payment_received` | *A receipt for the deposit* — only when step 5 takes one | the `BR-NOT-022` receipt election, then print · email · text through the same decision (`BR-BIL-036` puts print's floor back last) |
| `deposit_received` | *The deposit has cleared* — only when that deposit also clears on the day | `channel_decision(account, EMAIL, event_key=deposit_received)` |
| `service_agreement` | *The service agreement* — the **contract** the PO named, always listed | **no channels, by construction** — see §2.3 |

---

## 2 · Five judgments this lane made, that the ruling did not

### 2.1 · The SEND tick is a FACT and not a choice

p077 draws a tick per row. `POST /accounts/{id}/move-in` has **no parameter for
which messages to queue** — `services.MOVE_IN_FIELDS` is the account create set,
and a key it does not know is REFUSED BY NAME rather than dropped. A live
checkbox over a door that would refuse it is hard-won law 2's mirror: the shape
that left five refusing cards and a dead sign-in bar on the portal's front page
for days (`DEF-CWP-3925`).

**So the box is rendered disabled (`BR-SHL-025`) and ticked from
`channels.length > 0`** — it reports whether this save really queues the row.
It follows the precedent one screen over: new-connect step 7 renders p091's
ticks the same way, for the same reason.

**The hold carries its own expiry test** (law 2's *write the test that fires
when the hold expires*): `MoveInMessages.dom.test.tsx` asserts every box is
`disabled`, so the day a *which messages* parameter is ruled, the suite goes red
and names the file to change.

### 2.2 · Two of p077's five rows are NOT drawn

p077 draws five rows. Two of them — *The readings this account opened on* and
*That a meter still has to be read* — are drawn **UNTICKED**, and **neither
names a template class this product holds anywhere**: no code in
`notifications.catalogs.LISTINGS`, no event key, no rule. The second's own
TEMPLATE cell reads *— none chosen* in the drawing itself.

**Building them would put two rows of pure `—` on the screen the PO asked to
carry LESS text.** They are left out, recorded here and in
`move_in_message_plan`'s docstring, and **the day either class is authored the
server's plan grows the row and this table draws it with no change to the
screen** — which is why every row comes from the server rather than from a list
in the component.

### 2.3 · The contract is listed, and listed as going out on nothing

The PO named *contract* in their own words and p077 draws it third, so the row
is there. But `services._move_in` **writes** a `service_agreements` row per
service at the unit and **queues nothing** for it: no event key exists, so no
rule can switch it on and no channel decision is taken.

Its `channels` is therefore `[]` **by construction rather than by a switch
somebody could turn on**, and its template resolves through
`contract_service_agreement` — which on a freshly seeded utility is absent,
because `BR-NOT-002` makes a contract version effective-dated and
`seed_notice_templates` refuses to seed a date nobody chose. **A dash in both
cells, and no sentence**: why a row has no channel is rationale, and rule 33
gives rationale zero words.

### 2.4 · The heading is *What goes out*, not *What goes out to the customer*

Rule 33 caps a heading at **three words**. Rule 34 wants **one pair of words**
for one thing across the product, and two shipped screens already say
***What goes out*** — new-connect step 7 (`customers.newConnect.step7.goesOut`)
and transfer step 5 (`customers.transfer.step5.outTitle`). Drawing the longer
form here would have made a third wording for one idea.

⚠ **THE PRODUCT NOW HAS TWO WORDINGS FOR THIS ONE PANEL AND IT IS RECORDED
RATHER THAN QUIETLY MATCHED.** Hours before this landed, the PO approved the
MOVE-OUT's equivalent panel **unchanged** — *"this is corret use it"* — and that
one is headed ***What we'll send*** (decision log, *"THE MONEY TABLE AND THE
MESSAGES TABLE, APPROVED (ACC-06 STEPS 4 AND 6)"*, columns Message · When ·
State). That was an approval of an existing panel, not a vocabulary ruling, and
the move-in is built to its OWN drawing (rule 41) — so **three screens say
*What goes out* and one says *What we'll send***. Unifying them is one string in
eleven catalogues and is the PO's call. The split is written down here so the
next copy audit finds it already known instead of filing it a second time.

### 2.5 · p078's *Choosing a template* picker and its four notes are NOT built

**RECORDED AS A DIVERGENCE, NOT DECIDED QUIETLY** (B14 rule 38's instruction).
The drawing continues onto p078 with a template search box, a table of every
published version with a radio column, and four explanatory paragraphs.

* **The four paragraphs are RATIONALE** — *"Everything here is queued, and
  nothing is sent"*, *"Print is the floor"*, *"A template resolves on three
  axes"*, *"The draft version is listed and cannot be picked"*. Rule 33 puts
  rationale at zero words on screen, and the PO's instruction in this very
  defect is *"reduce this text"*. They are not drawn.
* **The picker is informational in the drawing's own caption** — *"The template
  picker names the version that would be used and does not render it."* That
  information is **already in the TEMPLATE column of the table above it**, per
  row, resolved by the dispatcher's own call. A second table with a radio
  column over a commit that accepts no template choice would be a dead control
  (law 2) on a screen being trimmed.

**If the PO wants the picker on the review, it is a follow-up and this section
is the record of why it is absent today.** Nothing about it is claimed on
screen.

---

## 3 · Proof

| what | how |
|---|---|
| the old blocks are gone and the table is drawn | `MoveInWizard.test.tsx` — five cases, shown RED against the old screen first (*"expected … not to contain 'What this move-in will not write'"*, *"expected +0 to be 3"*, *"to contain 'This list could not be read.'"*), then green |
| the table behaves | `MoveInMessages.dom.test.tsx`, 12 cases. Three deliberate breaks were watched go red: every box ticked → the ticked/clear case; the box left live → the disabled case; the table drawn over an unanswered read → the `served: false` case |
| the plan's rows and their order | `06-backend/tests/test_def_cus_6365_move_in_messages.py` |
| the duplicated receipt list cannot drift | the same file's first case — **which existed only as a promise in a docstring until this lane wrote it** (hard-won law 1) |
| types | `npx tsc --noEmit`, exit 0 |
| rule 21 | `G31` PASS at ratchet 0; `routeBUtilities.test.ts` 11/11 with the new file listed |

# CR-163-BRC10 — New Connection details view: add fees after submission, send a message now, and the tab fixes around them

**Raised:** 2026-10-02, by the Product Owner, in chat, as part of the New Connection
programme (decision-log row of 2026-10-02 headed *"NEW CONNECTION — THE PO'S
SCREEN-BY-SCREEN REVIEW BECOMES ONE PROGRAMME"*, commit `56eb54ba9`). That row is the
ruling; nothing it settles is put back to the PO (hard-won law 13).
**Branch:** `claude/upbeat-dirac-olttw0` (`BRC10`, claimed by `CR-156-BRC10` in
`12-governance/14-id-reservations.md`). `10-scripts/allocate.py cr` answered **163**
against the remote. `--verify 163` answers *TAKEN* only because this lane's own first
commit (`735cbd25b`, the defect rows) names it in its subject — no sibling holds 163
(`git log --all --grep CR-163`, 2026-10-02).
**Lane:** NC-B. NC-A owns the lifecycle (`CR-162-BRC10`: Approve, Activate, the More
menu, Units and To-do tabs); NC-C the wizard; a defect lane the Done screen.
**Classification:** TWO NEW CAPABILITIES — a **CHANGE** (`13-change-process.md` §1) — and
twelve **DEFECTS** on a live screen, which go through `22-product-maintenance-process.md`
and are filed one by one in `12-governance/10-defect-log.csv`.

## 0 · What arrived, in the requester's words

The PO's Table 2 of the programme, items as the coordinator numbered them for this lane:

> **1** Raise work order: today it POSTs a "Meter set" with no form and no feedback → a
> form: job type, service, unit (or Whole build), target date; success toast naming the
> order; refusal shown.
> **2** Add fees after submission, until approval: pick a one-time charge code, qty,
> amount (price from the charge code where it has one) → adds to the connection's
> invoice the lawful way; shows on Charges.
> **14** Work tab Unit column shows the unit or "Whole build". **15** Whole-build orders
> show a wrong service (G Trade Tower CON-26-0136: "Installation Template" = Water,
> "Service connection" = Fire on a Battery/Solar build).
> **18** Each/Amount show "— Priced on the bill" while $90 was charged. **19** Qty
> "2.000000" → "2". **20** Paid so far: each payment — date, method (Cheque #4471), type,
> amount, receipt no. — linked to the payment record. **21** "Open payments" link works.
> **22** Invoice number and billed-to account are links. **23** "Take payment" greyed with
> "Nothing owed" when outstanding is 0.00.
> **24** Documents: View (eye) + file-name link. **25** Document label, not code;
> Required/State filled or dropped.
> **26** Messages: per row Send now, Preview, channel and recipient, Resend once sent —
> through notifications' existing path, audited. **27** When = sent date; a row with no
> template says how to add one, Send greyed.

## 1 · What signed statements move

| Statement | Where | What happens |
|---|---|---|
| *"Payments publishes an allocated SUM … no per-bill payment list"* | `connection_record._money` docstring | **Superseded**: `payments.selectors.payments_for_bills` publishes one row per payment. |
| Commit step 5 stamps each order with its template's own service | `connections.commit_connection` | **Corrected (DEF-MET-9179)**: a template's service is stamped only when the build carries it. |
| `OQ-NOT-12521` closed 2026-09-21 (option A: a `connection` message kind) | open-questions register | **Built** by item 26 — it was ruled and never built. |

No ❄️ B4/B5 figure moves. Item 2 is a money path (🔒) — see §4.

## 1b · Defects filed before fixing (step W)

`DEF-CUS-9177` (1) · `DEF-CUS-9178` (14) · `DEF-MET-9179` (15) · `DEF-CUS-9180` (18) ·
`DEF-CUS-9181` (19) · `DEF-CUS-9182` (20) · `DEF-CUS-9183` (21) · `DEF-CUS-9184` (22) ·
`DEF-CUS-9185` (23) · `DEF-CUS-9186` (24) · `DEF-CUS-9187` (25) · `DEF-CUS-9188` (27).

## 1c · Defects found on the way (dated reds, law 7)

`DEF-CUS-9205` — `DocumentCapture.dom.test.tsx`'s census of hosts went red when the
account documents tab adopted the kit (2.454.2); this lane's sixth host updated it ·
`DEF-MET-9206` — `test_new_connect_step7_messages::test_the_letter_that_asks_for_money_will_not_go_without_it`
expects `3030.0000` and gets `None`; red on the tip before this lane touched the file ·
`DEF-MET-9207` — `test_br_met_1187`'s builder makes a one-unit build, so every PostgreSQL
case using it is refused `master_needs_two_units` since 2.442.0 (skipped on sqlite, so
nothing reported it) · `DEF-MET-9208` — `G53`: `connection_fees.py` is a new money file
not yet on `human_owned.txt`; joining the list is the PO's call.

## 2 · Status

**DONE — `2.462.0`** (2026-10-02, lane NC-B). All fourteen items built and walked in a
browser on PostgreSQL 16.

## 3 · Impact

| Surface | What changed |
|---|---|
| Screen NCT-02, *Work* tab | **Raise work order** opens a form (job type from the tenant's published templates, the service — only one the build carries —, a unit or *Whole build*, a target date). A toast names the order (*Work order WO-… raised.*); a refusal stays in the dialog. The Unit column reads the unit or **Whole build**. |
| Screen NCT-02, *Charges* tab | Each line shows Qty (`2`, not `2.000000`), Each and Amount from the server (2 × $45.00 = $90.00), and the bill it is on. Invoice and Billed to are links. **Paid so far** is a table — date, method (*Check #4471*), type, amount, receipt (a link to the payment), state. *Open payments* opens the account's payments. **Add fee** (until approval) raises a new bill. |
| Screen NCT-02, header | **Take payment** is greyed with *Nothing owed* when the outstanding is $0.00. |
| Screen NCT-02, *Documents* tab | An eye opens the file in a new tab and the file name is a link (the account documents open route of 2.454.2, through the kit — rule 43). The document column shows its label; the Required and State columns are dropped where they said nothing. |
| Screen NCT-02, *Messages* tab | Per row: **Preview**, **Send now** (channel and recipient — owner, or the co-applicant on a channel they gave), and **Resend** once a copy exists. *When* shows the date and time it was queued. A row with no template says *No template — add one in Settings → Templates* and Send is greyed. |
| API | `POST /connections/{id}/fees` · `POST /connections/{id}/messages/{code}/send` · `GET /connections/{id}/messages/{code}/preview` · the record's `money` gains `bills`, `payments`, `invoice_id`, `billed_to_id` and per-line `each`/`line_total`; `communication` rows gain `template_available`, `sendable`, `sent_at`, `deliveries`, and the record gains `message_recipients`. `raise work order` accepts `template_id`, `due_at` and checks `unit_id` belongs to the build. |
| Data | **Metering 0068** — one new table, `connection_fee_bills` (which build an added bill belongs to), RLS-forced. No backfill. `notifications.SOURCE_TYPES` gains `connection` (a Python constant, no migration). |
| Commit path | Step 5 stamps an order's service only when the build carries it (`DEF-MET-9179`). Orders already stamped wrong on existing builds — `CON-26-0136`'s *Water* and *Fire* — are DATA and are not rewritten. |
| Messages | Create queues nothing (the PO's Q8, *messages fire on approval*). Approval (`fire_on_approval`, `CR-162-BRC10`) and *Send now* both go through one engine, `connection_messages.send_now`. Letters stay in the utility's language (`OQ-CUS-12619`). |
| Rating | `charge_by_code` also returns the code's `charge_type` (read only — an added fee must be one-time). |
| Open questions | `OQ-376` closed in the register (answered by `OQ-NOT-12521`, now built). `OQ-BIL-12377` (one fee bill per payer per day) is NOT widened; its body carries the new common case. |
| Catalogues | 67 keys × 11 languages, through `i18n_fanin.py`. |

## 4 · Money path (item 2)

`apps/metering/connection_fees.py` and metering 0068 are 🔒 and `HUMAN-REVIEW-PENDING`;
the review-ledger row is written in plain English with the figure: an **$800.00** quote,
a **$30.00** inspection added the next day, two bills, the first untouched, **Charged
$830.00**; the same day refused by name. Billing does the arithmetic through its existing
doors (`raise_and_issue_quote_bill` for a priced code; `raise_charge_fee` +
`issue_charge_fee` for a code priced "entered when used"); metering multiplies nothing.
Proved on PostgreSQL 16 (`tests/test_cr163_add_fee.py`, 9 passed + the PG case).

## 5 · Version and rollback

**Version `2.462.0`.** Rollback: revert the commits, then `migrate metering 0067`
(drops `connection_fee_bills`). A fee bill already raised stays a lawful issued bill
on its account — it is billing's row — and the build simply stops listing it under
Charges; a queued `connection` message stays in the queue and is read by nothing.
Redeploy front end and server together (the record's new keys are read by the new tabs).

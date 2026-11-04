# 26 · The transfer does not transfer — measured 2026-09-20

**Written so the next session starts from a measurement rather than a suspicion.**
The PO asked on 2026-09-20 for an end-to-end transfer walk, naming what to check:
*"see all transfer work corectly - property, address, assets, units - occupancy is
updated at unit. assets whow correct account - money part is correct, email,
communcation is send"*. It was run. **Every one of those four came back NO.**

⚠ **SNAPSHOT.** True at `0e7b4afd2`, version `2.319.0`. The registers and the decision
log outrank this file the moment they disagree.

---

## 1 · The measurement

    cd 06-backend && set -a && . ./.env && set +a && ../10-scripts/transfer_scenarios.sh

**19 failed · 9 passed · 96s.** The suite's own two numbers:

| | |
|---|---|
| NO FAILURE TODAY | **6 of 25** — nothing red, though some checks are still waiting |
| COMPLETE TODAY | **0 of 25** — no failure AND nothing left unasserted |

**Quote both.** Quoting only `0 of 25` makes it sound as though nothing works; `6 of 25`
with nothing red is the fairer headline, and the two answer different questions.

### What passes, exactly — and it is NOT "every refusal"

| Green | What it is |
|---|---|
| `RF1` `RF3` `RF4` `RF5` | refusals — no identifier · already mid-sale · already closed · nobody on file |
| `DR2` | a commit REFUSED at stage 5, leaving zero rows |
| `CT1` | a May sale that genuinely moves out in September — **counting, not a refusal** |

⚠ **`RF2` IS A REFUSAL AND IT IS RED.** *Selling to the person who already owns it*
COMMITS instead of being refused: `outcome: want 'refused', saw 'committed'` and
`refusal_name: want 'buyer_is_already_this_accounts_customer', saw None`. So it is
**four of five** refusals, not five. A first draft of this finding said *"every refusal
passes"* in the same breath as reporting RF2's failure — two claims that cannot both be
true, caught by the PO rather than by its author. **Count before reaching for a phrase.**

---

## 2 · THE ROOT CAUSE — one thing, not seventeen

**17 of the 19 red rows carry the identical failure signature.** Verbatim, 18 times:

    ✗ occupancy_at_unit: occupant_names_the_buyer: want True, saw False
                       · occupant_names_the_seller: want False, saw True

and 17 times:

    ✗ assets_and_account: names_the_buyer: want True, saw False
                        · names_the_seller: want False, saw True

### Why, traced to the line

* `metering/selectors.py:1422` — `"occupant": (account or {}).get("customer_name")`
* `customers/selectors.py:645` and `:1076` — `"customer_name": primary_contact_name(row)`

**So "who holds this" is read off a CONTACT row, not off `customer_accounts`.**

And the commit at `customers/transfers.py:2169` moves the LINK and nothing else:

    removed = models.CustomerAccount.objects.filter(tenant_id=…, account=account)
                                            .exclude(customer_id=buyer_id)
    seller_ids = sorted(…)
    removed.delete()
    transfer.customer_id = buyer_id

**The link is reassigned; `contacts` is never touched.** So the account changes hands in
one table and announces the seller from another. Occupancy, the asset rows and the
account header all read the second one.

⚠ **THIS IS A KNOWN ARCHITECTURAL SEAM, NOT A SURPRISE.** `CLAUDE.md`'s own B2 note says
*"contacts still hang off ACCOUNTS, not off the new customer row (r9 #1 flags the re-home
as an Eng-Lead disposition)"*. The transfer is the first flow that makes the seam bite,
because it is the first one where the account survives and the person changes.

---

## 3 · The other four keystones, with what each holds up

    seller_link_ended_not_deleted              40 check(s)
    premises_units_meters_assets_on_step_3     25 check(s)
    transfer_message_kind                      81 check(s)
    move_outs_exclusion_rewritten_for_the_sale  1 check(s)
    transfer_record_page_and_read              19 check(s)

* **`seller_link_ended_not_deleted`** — `removed.delete()` destroys the seller's row, so
  *who sold this property* survives only in `audit_log`, which is pruned. ⚠ **This needs a
  SCHEMA CHANGE and cannot be done by editing the service: `CustomerAccount` carries
  `tenant`, `customer`, `account` and `created_at` and has NO ended/period column.** Ending
  rather than deleting means a migration. Do not fake it by leaving the row and filtering
  in Python — the uniqueness is on the PAIR.
* **`transfer_message_kind`** — the commit queues NO message of any kind: not the buyer,
  not the seller. ⚠ **And the suite prints a fact bigger than transfer: 426 messages are
  queued in this product and NOT ONE has ever been sent — `sent_at` is null on every row.**
  Fixing the transfer's message reaches a queue that has never delivered anything.
* **`premises_units_meters_assets_on_step_3`** — the premises OWNER record still names the
  seller and wants matching by hand; the commit says so and nothing counts how often.
* **`transfer_record_page_and_read`** — the record PAGE was built 2026-09-20 and
  `GET /transfers/{ref}` is still not mounted, so the sale cannot be read back.

---

## 4 · What the suite did NOT check, in its own words

> **U1 · Whether a clerk can do any of this ON A SCREEN.** It drives the services and
> reads PostgreSQL back. It never opens a browser, so it cannot see a field that renders
> as a dash, a step that cannot be reached, or a `Save & exit` that loses what was typed.

⚠ **AND THIS FLOW HAS NO WALKTHROUGH SCRIPT.** `10-scripts/` holds one for the move-in
job, the move-out wizard, the account bar, the portal and nine CRs, **and none for a
transfer.** The suite names that as its own largest blind spot rather than counting
around it. The PO found `DEF-CUS-5934` — *"step 4 when last tick is press - uI breaks"* —
by clicking, and 39 green front-end cases and a clean `tsc` had all passed over it.

---

## 5 · Suggested order, and why

1. **The contacts seam.** One cause, ~35 checks, and it is the literal meaning of *the
   transfer does not transfer*. Everything else is a smaller claim.
2. **`RF2`** — refusing a sale to the existing owner. Small, self-contained, and it is a
   refusal that currently writes real rows.
3. **`seller_link_ended_not_deleted`** — needs the migration; do it deliberately, not as a
   side effect of (1).
4. **The message**, knowing the queue has never delivered.
5. **`GET /transfers/{ref}`**, which lights up a page that already exists.

**Re-run the suite after each and report BOTH numbers.** Baseline: `6 of 25` no-failure,
`0 of 25` complete, 19 failed / 9 passed.

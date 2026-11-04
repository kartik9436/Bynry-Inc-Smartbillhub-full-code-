# The transfer record page — what the database can actually answer today

**Read this before building `GET /transfers/{ref}`.** It is a measurement, not a
contract: nothing below is built, and the point of writing it down is that four
of the drawn record's facts **cannot be served at all** and a lane that
discovers that halfway through has already drawn them.

Measured 2026-09-20 against `e4bc49a0d`, on the blueprint's transfer-record page
(p132–p133). It is the sequel to `transfer-against-its-blueprint.md` in this
folder, whose §10 ranks this page **first** of everything the transfer surface
still needs — *"a clerk can make a sale and then has no way to read it back"* —
and correctly names the seller as its blocker. **Two of that file's findings are
now closed:** §10 item 5's `Mailing address` and `Matched an existing customer`
line both landed in `e4bc49a0d` under `BR-CUS-1081`.

---

## 1 · The reference exists. The drawing says it does not.

The drawn page carries a dashed panel:

> *"No transfer numbering series exists, so this sale carries no reference in the
> database today. The header is drawn as it will read once one is set up; until
> then the record is found by its account and its date."*

**Every sentence of that is false and has been since 2026-08-27.** `OQ-426`
closed that day on the PO's own words — *"Transfer TRF-26-0001 … follow same
logic that we are following for other numbers"* — the `transfer` series is
seeded at `TRF-{YY}-{0000}` in every provisioned tenant, `start_transfer`
allocates inside its own transaction, and
`test_cr039_wd_transfer_and_case_numbers` asserts a new tenant's first transfer
renders **`TRF-26-0001`**.

**So `GET /transfers/{ref}` is keyable on `transfers.transfer_no` today and
needs no numbering lane.** `DEF-CUS-5945` records how the drawing came to say
otherwise: three docstrings in `transfers.py` went on describing the open world
after the question closed, and the drawing was written from them.

⚠ **NULL is still possible and is a real answer**: a tenant provisioned before
the series was seeded has no catalogue row, and `_allocate_transfer_no` reports
rather than raises. Key the route on the reference and fall back to the id, the
way `/moves/{ref}` does — do not assume NULL means *no series exists*.

---

## 2 · Four facts have no durable home, and they are not the same kind of problem

| Drawn fact | Where it lives today | Servable? |
|---|---|---|
| Reference `TRF-26-00nn` | `transfers.transfer_no` | **yes** |
| `Sold on` | `transfers.out_date` | **yes** |
| Buyer, and the title's right-hand side | `transfers.customer_id` | **yes** |
| The account, its number, its unit | `transfers.from_account_id` | **yes** |
| Doors: *Open the customer* · *Open the account* | both ids are on the row | **yes** |
| `Refunded to the seller $0.00` · `Re-collected from the buyer $0.00` | **neither is stored and neither needs to be** — `BR-CUS-085` and `BR-CUS-1030` mean nothing is refunded and nothing is re-collected, so these are CONSTANTS of the rule | **yes** |
| The ledger's unbroken span (*"One continuous history, 38 months"*) | derivable from the account's own ledger | **yes**, as a query |
| **`Sold by`**, and the title's left-hand side | ⛔ **nowhere** | **no** — §3 |
| **The balance as it stood on the day** | ⛔ **nowhere** | **no** — §4 |
| **The deposit as it stood on the day** | ⛔ **nowhere** | **no** — §4 |
| **`Buyer matched or created`** | ⛔ **nowhere** | **no** — §4 |

All four absent facts exist only in `audit_log`, which is pruned on a retention
schedule. ⚠ **No document, screen or docstring may describe that as a permanent
record** — the same constraint `OQ-1340` puts on a corrected payment reference.

---

## 3 · The seller is PO-ruled and is NOT a column to add

**PO, 2026-09-20: *"we cannot override customer id - seller and buyer cstmer id
are unique those does not change"*** (decision log, *A customer id is never
overwritten*).

`reassign_account` deletes the seller's `customer_accounts` link row and
overwrites `accounts.customer_id`. The ruling is about identity and the shape
that follows is a **PERIOD on `customer_accounts`** — a sale ENDS the seller's
link and OPENS the buyer's, deleting neither — which makes ownership history a
query instead of a log scrape.

⛔ **That entry says in terms that it needs its own decision before it is built,
because it changes a link table three modules read, and that "a lane must not
simply add a column and move on."** So `Sold by` is blocked on that decision, not
on this lane's time. **Do not add `transfers.sold_by_customer_id`** — an earlier
draft of the buyer-capture work proposed exactly that and withdrew it.

**What the record page should do meanwhile:** put `Sold by` in the drawn *What
this record does not say* section with the reason, rather than leaving the title
half-empty or filling it from the audit log.

---

## 4 · The two money snapshots ARE ours, and the docstring already claims them

`reassign_account`'s own docstring says the row records *"who it moved from, who
it moved to, **and the balance and deposit AS THEY STOOD at the moment of
sale**"*. **It records none of the three** — hard-won law 1, a comment claiming a
guarantee is not the guarantee. The figures are computed at commit, put on the
response and the audit row, and never stored.

⚠ **AND THE DRAWING FORBIDS THE OBVIOUS WORKAROUND.** It says every figure is
*"as it stood on the day, not as it stands now"*. So the record page may **not**
read today's `accounts.balance` and label it as the sale's figure — that is a
wrong number on a money path, and it would be wrong by exactly the amount the
account has moved since.

**The fix is two nullable `NUMERIC(18,4)` columns on `transfers`** —
`balance_at_sale` and `deposit_at_sale` — written ONCE at commit as new facts,
never as corrections. `transfers` is none of hard rule 4's four tables and no PO
time is needed. ⚠ **The model docstring's "NO MONEY COLUMN" line must be amended
in the same commit, and the distinction stated**: it was written against a stored
`deposit_carried`, which would read as *money that moved on a path where nothing
moved*. A SNAPSHOT of what stood is a different fact and the ruling itself asks
for it.

`Buyer matched or created` is the third: `link_customer` returns it as
`match` and `reassign_account` puts it on the response. A nullable
`buyer_was_matched boolean` alongside the two money columns settles it.

⚠ **No back-fill, for any of the three.** Nothing in this database can say what a
past sale's balance was; a migration that guessed would put an invented figure on
a record a regulator may read. Report the count of transfers that predate the
columns and leave them — the posture `customers 0048` already takes for
`request_id`.

---

## 5 · The page has no actions, and that is an answer

The drawing is explicit: *"This record has no actions, and that is the answer
rather than a gap… Drawing a button here would invent a decision the product does
not offer."* **Serve doors, not decisions** — *Open the customer* and *Open the
account* — and follow the move record's `doors` shape rather than inventing one,
since that page reached the same conclusion independently.

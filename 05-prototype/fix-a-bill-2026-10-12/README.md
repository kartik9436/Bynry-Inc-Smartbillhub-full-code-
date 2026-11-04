# Fix a bill: the revamp drawing (2026-10-12)

These are the **drawing images** for the revamped Fix a bill. Per B14 rules 41/42, the screens are built **from these images**, not from text. They were captured at 1440 px wide, light theme, from the PO-reviewed mock-up `claude.ai/artifact/UZVnmZQ4m3SJsh6d4L867M` (version 10). The mock-up's HTML is kept beside them as `fix-a-bill-revamp.html`, so any state can be re-opened.

⚠ **Every figure is example data** (B14 rule 37: a drawn figure is an illustration, never a fact to build to). The SHAPE is the specification. Our UI standard decides spacing, sizes and tokens (B14 rule 44). The PO's instructions behind each part are in the decision log of 2026-10-12, under *FIX A BILL REVAMP*, items 1–11.

| # | Image | Step | What it shows |
|---|---|---|---|
| 01 | `01-bills-one-customer-one-bill.png` | Bills | Option cards inside step 1, the sub-option dropdown, the searchable account box and account card, and the bill list (radio) with totals |
| 02 | `02-bills-account-search-open.png` | Bills | The account search open: matches highlighted, Active/Closed, account number and address |
| 03 | `03-bills-one-customer-several-months.png` | Bills | Several months: tick boxes for the bills |
| 04 | `04-bills-bulk-billing-run.png` | Bills | Bulk · a billing run: the run picker, "Only part of it", bills covered, and what was left out |
| 05 | `05-bills-bulk-price-mistake.png` | Bills | Bulk · a price mistake: From–To plus what was wrong, and the bills it finds |
| 06 | `06-fix-one-bill-wrong-reading.png` | Fix | The one "What was wrong" table: one row, the derived *What happens*, Not done here, and the old bill beside the new bill laid out by rate type |
| 08 | `08-fix-one-bill-several-corrections.png` | Fix | Several rows (reading, plan, tax, charge) on one bill |
| 09 | `09-fix-several-months-with-goodwill-and-reprint.png` | Fix | Several months: Apply to as month chips, goodwill on one month, a reprint row, and What changes on the page |
| 10 | `10-fix-plan-change-rate-types.png` | Fix | Plan changed to Small Commercial: the rate types change (Tiered → Time of use + demand, Tiered → Flat), and missing lines show "—" |
| 11 | `11-fix-credit-only.png` | Fix | Goodwill only: *What happens: Credit only*, the old bill beside the credit note |
| 12 | `12-fix-reprint-only.png` | Fix | Address only: *Reprint only*, What changes on the page, amounts unchanged |
| 13 | `13-fix-wrong-deposit.png` | Fix | Wrong deposit: a Deposits section, held and not taxed |
| 14 | `14-fix-bulk-run.png` | Fix | Bulk run: the table applies to every bill, going up and going down shown apart, and the per-bill was/becomes table |
| 15 | `15-fix-bulk-price-mistake.png` | Fix | Bulk price mistake: the correct price comes from Plans & Rates |
| 16 | `16-check-clerk-finance-closed.png` | Check | For the customer, existing bills (never edited), and For finance closed for the clerk |
| 17 | `17-check-approver-finance-open.png` | Check | The same, with For finance open for the approver: entries, net per account, posting month |
| 18 | `18-check-bulk.png` | Check | Bulk check |
| 19 | `19-send-clerk.png` | Send | Summary card, "I checked the amounts", and Send for approval; nothing is saved before it |
| 20 | `20-send-waiting-for-approval.png` | Send | Waiting for approval, and who it was sent to |
| 21 | `21-send-approver-approve-and-issue.png` | Send | The approver's view: Approve and issue |
| 22 | `22-send-done-one-customer.png` | Send | Done: credit note and new bill numbers |
| 23 | `23-send-done-bulk.png` | Send | Done in bulk: done, failed and already done counts |
| 24 | `24-fix-data-sources-shown.png` | Fix | The same screen with every value tagged by its source: blue is served today, amber is new work |

**Not capturable as an image:** an open native dropdown. The *What was wrong* list is, in order:
- **Re-price:** Wrong reading · Wrong plan · Wrong rate · Wrong tax · A charge was missed · A charge was billed in error · Wrong discount · Wrong deposit · Wrong period or service · Theft, restated
- **Credit only:** Goodwill credit
- **Reprint only:** Customer name · Mailing address · Premises or unit label · Meter number or read dates · Template or language

Bulk offers Wrong plan, Wrong rate, Wrong tax, the two charge reasons, Wrong discount and Template or language. A price mistake offers the same set without Template or language.
